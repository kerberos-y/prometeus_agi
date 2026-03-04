"""
PROMETEUS AGI — Граф знаний  v2.1
===================================
Изменения v2.1:
  - find() fallback LIKE задокументирован как временный.
    После миграции старых данных — удалить блок "2. Fallback".

Изменения v2.0:
  - add_concept() принимает уже стеммированный ключ (name = стем).
  - find() ищет сначала точно, затем по подстроке (совместимость со старыми данными).

Оригинал:
  - Постоянное соединение с SQLite (без повторных открытий)
  - Индексированный поиск по подстроке через SQL
  - Оптимизированный BFS для related() без построения промежуточных графов
  - Логирование вместо print
  - Транзакционная защита при записи
  - Обновление last_used для узлов
  - Совместимость со старым API
  - Методы для поиска структурных аналогий (get_edges_by_weight, find_structural_analogies)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

import networkx as nx

logger = logging.getLogger(__name__)

WEIGHT_MAX    = 1.0
WEIGHT_MIN    = 0.0
WEIGHT_FORGET = 0.2
WEIGHT_SLEEP  = 0.3
DELTA_HEBBIAN = 0.05


class KnowledgeGraph:
    """
    Граф знаний PROMETEUS.
    Ключи узлов — стеммированные формы слов.
    Это обеспечивает точный поиск без LIKE-запросов.
    """

    def __init__(self, db_path: str = "knowledge/graph.db") -> None:
        self.graph = nx.MultiDiGraph()
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self._init_db()
        self._load_from_db()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    # ── Инициализация БД ──────────────────────────────────────────

    def _init_db(self) -> None:
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    name       TEXT PRIMARY KEY,
                    properties TEXT DEFAULT '{}',
                    last_used  TEXT
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node        TEXT    NOT NULL,
                    to_node          TEXT    NOT NULL,
                    relation         TEXT    NOT NULL,
                    weight           REAL    DEFAULT 1.0,
                    created_at       TEXT,
                    activated_at     TEXT,
                    activation_count INTEGER DEFAULT 0,
                    FOREIGN KEY(from_node) REFERENCES nodes(name) ON DELETE CASCADE,
                    FOREIGN KEY(to_node)   REFERENCES nodes(name) ON DELETE CASCADE,
                    UNIQUE(from_node, to_node, relation)
                );

                CREATE INDEX IF NOT EXISTS idx_edges_from   ON edges(from_node);
                CREATE INDEX IF NOT EXISTS idx_edges_to     ON edges(to_node);
                CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight);
                CREATE INDEX IF NOT EXISTS idx_nodes_name   ON nodes(name);
            """)

    def _load_from_db(self) -> None:
        try:
            cursor = self.conn.execute("SELECT name, properties FROM nodes")
            for row in cursor:
                try:
                    props = json.loads(row["properties"] or "{}")
                except json.JSONDecodeError:
                    props = {}
                self.graph.add_node(row["name"], **props)

            cursor = self.conn.execute(
                "SELECT from_node, to_node, relation, weight FROM edges"
            )
            for row in cursor:
                self.graph.add_edge(
                    row["from_node"],
                    row["to_node"],
                    relation=row["relation"],
                    weight=float(row["weight"]),
                )

            logger.info(
                "KnowledgeGraph загружен: %d узлов, %d рёбер",
                self.graph.number_of_nodes(),
                self.graph.number_of_edges(),
            )
        except Exception as e:
            logger.error("Ошибка загрузки графа из БД: %s", e)
            raise

    # ── Добавление данных ─────────────────────────────────────────

    def add_concept(self, name: str, properties: dict | None = None) -> None:
        """
        Добавляет концепт в граф.

        ВАЖНО: name должен быть уже стеммирован перед вызовом.
        Используй: graph.add_concept(_nlp.stem(word), {...})

        properties["description"] — читаемое описание (оригинал).
        properties["original"]    — оригинальная форма слова (опционально).

        Если концепт уже существует — обновляет properties.
        """
        properties = properties or {}
        self.graph.add_node(name, **properties)

        now = datetime.utcnow().isoformat()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO nodes (name, properties, last_used) VALUES (?, ?, ?)",
                    (name, json.dumps(properties, ensure_ascii=False), now),
                )
        except Exception as e:
            logger.error("Ошибка добавления концепта '%s': %s", name, e)

    def add_relation(
        self,
        from_node: str,
        to_node: str,
        relation: str,
        weight: float = 1.0,
    ) -> None:
        """
        Добавляет типизированную связь между концептами.
        Автоматически создаёт узлы, если их нет.
        Если такая же связь уже есть — обновляет вес.

        ВАЖНО: from_node и to_node должны быть стеммированы.
        """
        if from_node not in self.graph:
            self.add_concept(from_node)
        if to_node not in self.graph:
            self.add_concept(to_node)

        existing_key = self._find_edge_key(from_node, to_node, relation)
        if existing_key is not None:
            self.graph[from_node][to_node][existing_key]["weight"] = weight
        else:
            self.graph.add_edge(from_node, to_node, relation=relation, weight=weight)

        now = datetime.utcnow().isoformat()
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO edges
                        (from_node, to_node, relation, weight, created_at, activated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(from_node, to_node, relation) DO UPDATE SET
                        weight       = excluded.weight,
                        activated_at = excluded.activated_at
                """, (from_node, to_node, relation, weight, now, now))
        except Exception as e:
            logger.error(
                "Ошибка добавления связи %s -[%s]-> %s: %s",
                from_node, relation, to_node, e,
            )

    # ── Hebbian learning ──────────────────────────────────────────

    def activate(
        self,
        from_node: str,
        to_node: str,
        relation: str,
        delta: float = DELTA_HEBBIAN,
    ) -> None:
        """
        Усиливает или ослабляет связь (Hebbian learning).
        delta > 0 → fire together, wire together
        delta < 0 → пользователь сказал «неверно»
        Если вес падает ниже WEIGHT_FORGET — связь удаляется.
        """
        key = self._find_edge_key(from_node, to_node, relation)
        if key is None:
            return

        edge = self.graph[from_node][to_node][key]
        new_weight = min(WEIGHT_MAX, max(WEIGHT_MIN, edge["weight"] + delta))
        edge["weight"] = new_weight

        now = datetime.utcnow().isoformat()
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE edges
                    SET weight = ?, activated_at = ?,
                        activation_count = activation_count + 1
                    WHERE from_node = ? AND to_node = ? AND relation = ?
                """, (new_weight, now, from_node, to_node, relation))
                self.conn.execute(
                    "UPDATE nodes SET last_used = ? WHERE name = ?", (now, from_node)
                )
                self.conn.execute(
                    "UPDATE nodes SET last_used = ? WHERE name = ?", (now, to_node)
                )
        except Exception as e:
            logger.error("Ошибка при активации связи %s->%s: %s", from_node, to_node, e)

        if new_weight <= WEIGHT_FORGET:
            self._forget(from_node, to_node, relation, key)

    def _forget(
        self,
        from_node: str,
        to_node: str,
        relation: str,
        key: int | None = None,
    ) -> None:
        if key is None:
            key = self._find_edge_key(from_node, to_node, relation)
        if key is not None and self.graph.has_edge(from_node, to_node, key):
            self.graph.remove_edge(from_node, to_node, key)
        try:
            with self.conn:
                self.conn.execute(
                    "DELETE FROM edges WHERE from_node=? AND to_node=? AND relation=?",
                    (from_node, to_node, relation),
                )
            logger.debug(
                "Forget: %s --%s--> %s (вес ≤ %s)", from_node, relation, to_node, WEIGHT_FORGET
            )
        except Exception as e:
            logger.error("Ошибка при удалении связи %s->%s: %s", from_node, to_node, e)

    # ── Поиск ─────────────────────────────────────────────────────

    def find(self, concept: str) -> dict | None:
        """
        Ищет концепт в графе.

        Стратегия (в порядке приоритета):
            1. Точное совпадение — O(1), основной путь после v2.0.
            2. Поиск по подстроке через SQLite LIKE — временный fallback
               для совместимости со старыми записями в graph.db (до стемминга).
               TODO: удалить после миграции старых данных.

        concept должен быть стеммирован перед вызовом:
            graph.find(_nlp.stem("компьютеры"))  →  graph.find("компьютер")
        """
        # 1. Точное совпадение
        target = concept if concept in self.graph else None

        # 2. Fallback: подстрока — только для старых данных без стемминга.
        # Внимание: LIKE '%x%' может дать ложные совпадения (atom → anatomy).
        # Убрать этот блок после полной миграции graph.db.
        if target is None:
            try:
                row = self.conn.execute(
                    "SELECT name FROM nodes WHERE name LIKE ? LIMIT 1",
                    (f"%{concept}%",)
                ).fetchone()
                if row and row["name"] in self.graph:
                    target = row["name"]
            except Exception as e:
                logger.error("Ошибка поиска '%s': %s", concept, e)

        if target is None:
            return None

        # Собираем связи
        relations = []
        seen: set[tuple] = set()

        for u, v, data in self.graph.out_edges(target, data=True):
            rel  = data.get("relation", "СВЯЗАН_С")
            wght = data.get("weight", 1.0)
            key  = (u, rel, v)
            if key not in seen:
                seen.add(key)
                relations.append({
                    "from": u, "relation": rel,
                    "to": v, "weight": round(wght, 3),
                })

        for u, v, data in self.graph.in_edges(target, data=True):
            rel  = data.get("relation", "СВЯЗАН_С")
            wght = data.get("weight", 1.0)
            key  = (u, rel, v)
            if key not in seen:
                seen.add(key)
                relations.append({
                    "from": u, "relation": rel,
                    "to": v, "weight": round(wght, 3),
                })

        return {
            "concept":    target,
            "properties": dict(self.graph.nodes[target]),
            "relations":  sorted(relations, key=lambda x: -x["weight"]),
        }

    def related(
        self,
        concept: str,
        depth: int = 2,
        min_weight: float = 0.0,
    ) -> list[str]:
        """
        Возвращает связанные концепты в радиусе depth с фильтром по весу.
        Использует ручной BFS.
        """
        if concept not in self.graph:
            return []

        visited  = {concept}
        frontier = [concept]

        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for _, v, data in self.graph.out_edges(node, data=True):
                    if v not in visited and data.get("weight", 1.0) >= min_weight:
                        visited.add(v)
                        next_frontier.append(v)
            frontier = next_frontier

        visited.remove(concept)
        return list(visited)

    def search(self, keyword: str) -> list[str]:
        """Поиск концептов по подстроке в названии."""
        try:
            cursor = self.conn.execute(
                "SELECT name FROM nodes WHERE name LIKE ?",
                (f"%{keyword}%",)
            )
            return [row["name"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error("Ошибка поиска по ключу '%s': %s", keyword, e)
            return []

    def strongest_relations(self, concept: str, top_n: int = 5) -> list[dict]:
        result = self.find(concept)
        if not result:
            return []
        return result["relations"][:top_n]

    # ── Структурные аналогии ──────────────────────────────────────

    def get_edges_by_weight(self, min_weight: float = 0.6) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT from_node, to_node, relation, weight FROM edges WHERE weight >= ?",
            (min_weight,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def find_structural_analogies(self, min_weight: float = 0.6) -> list[dict]:
        edges = self.get_edges_by_weight(min_weight)
        groups: dict[str, list] = {}
        for e in edges:
            groups.setdefault(e["relation"], []).append((e["from_node"], e["to_node"]))
        candidates = []
        for rel, pairs in groups.items():
            if len(pairs) >= 2:
                candidates.append({"relation": rel, "pairs": pairs})
        return candidates

    # ── Статистика ────────────────────────────────────────────────

    def stats(self) -> dict:
        weights = [d.get("weight", 1.0) for _, _, d in self.graph.edges(data=True)]
        return {
            "nodes":          self.graph.number_of_nodes(),
            "edges":          self.graph.number_of_edges(),
            "avg_weight":     round(sum(weights) / len(weights), 3) if weights else 0.0,
            "sleeping_edges": sum(1 for w in weights if w < WEIGHT_SLEEP),
            "strong_edges":   sum(1 for w in weights if w >= 0.8),
        }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"KnowledgeGraph(nodes={s['nodes']} | edges={s['edges']} | "
            f"avg_weight={s['avg_weight']})"
        )

    # ── Вспомогательные ───────────────────────────────────────────

    def _find_edge_key(
        self,
        from_node: str,
        to_node: str,
        relation: str,
    ) -> int | None:
        if not self.graph.has_node(from_node) or not self.graph.has_node(to_node):
            return None
        edges = self.graph.get_edge_data(from_node, to_node)
        if edges is None:
            return None
        for key, data in edges.items():
            if data.get("relation") == relation:
                return key
        return None