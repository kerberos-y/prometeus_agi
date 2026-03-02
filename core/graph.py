"""
PROMETEUS AGI — Граф знаний
============================

Улучшенная версия:
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

# Настройка логгера
logger = logging.getLogger(__name__)

# Константы
WEIGHT_MAX = 1.0
WEIGHT_MIN = 0.0
WEIGHT_FORGET = 0.2   # ниже → связь удаляется
WEIGHT_SLEEP = 0.3    # ниже → связь «слабая»
DELTA_HEBBIAN = 0.05  # стандартный шаг усиления


class KnowledgeGraph:
    """
    Граф знаний PROMETEUS.

    Использование полностью совпадает с предыдущей версией,
    но добавлены оптимизации и улучшена надёжность.
    """

    def __init__(self, db_path: str = "knowledge/graph.db") -> None:
        self.graph = nx.MultiDiGraph()
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Единое соединение на весь жизненный цикл
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self._init_db()
        self._load_from_db()

    def close(self) -> None:
        """Закрывает соединение с БД."""
        if self.conn:
            self.conn.close()

    # ── Инициализация БД ──────────────────────────────────────────

    def _init_db(self) -> None:
        """Создаёт таблицы и индексы, если их нет."""
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    name       TEXT PRIMARY KEY,
                    properties TEXT DEFAULT '{}',
                    last_used  TEXT   -- время последней активации
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
        """Загружает весь граф из SQLite в MultiDiGraph."""
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
                f"KnowledgeGraph загружен: {self.graph.number_of_nodes()} узлов, "
                f"{self.graph.number_of_edges()} рёбер"
            )
        except Exception as e:
            logger.error(f"Ошибка загрузки графа из БД: {e}")
            raise

    # ── Добавление данных ─────────────────────────────────────────

    def add_concept(self, name: str, properties: dict | None = None) -> None:
        """Добавляет концепт в граф и сохраняет в БД."""
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
            logger.error(f"Ошибка добавления концепта '{name}': {e}")

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
        """
        # Гарантируем существование узлов
        if from_node not in self.graph:
            self.add_concept(from_node)
        if to_node not in self.graph:
            self.add_concept(to_node)

        # Проверяем наличие ребра с таким relation
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
            logger.error(f"Ошибка добавления связи {from_node} -[{relation}]-> {to_node}: {e}")

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

        delta > 0 → fire together, wire together (усиление)
        delta < 0 → пользователь сказал «неверно» (ослабление)

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

                # Обновляем last_used для обоих узлов
                self.conn.execute(
                    "UPDATE nodes SET last_used = ? WHERE name = ?",
                    (now, from_node)
                )
                self.conn.execute(
                    "UPDATE nodes SET last_used = ? WHERE name = ?",
                    (now, to_node)
                )
        except Exception as e:
            logger.error(f"Ошибка при активации связи {from_node}->{to_node}: {e}")

        if new_weight <= WEIGHT_FORGET:
            self._forget(from_node, to_node, relation, key)

    def _forget(
        self,
        from_node: str,
        to_node: str,
        relation: str,
        key: int | None = None,
    ) -> None:
        """Удаляет слабую связь (forgetting механизм)."""
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
            logger.debug(f"Forget: {from_node} --{relation}--> {to_node} (вес ≤ {WEIGHT_FORGET})")
        except Exception as e:
            logger.error(f"Ошибка при удалении связи {from_node}->{to_node}: {e}")

    # ── Поиск ─────────────────────────────────────────────────────

    def find(self, concept: str) -> dict | None:
        """
        Возвращает концепт со всеми его связями.
        Связи отсортированы по убыванию веса.
        """
        if concept not in self.graph:
            return None

        relations = []
        seen: set[tuple] = set()

        for u, v, data in self.graph.out_edges(concept, data=True):
            rel = data.get("relation", "СВЯЗАН_С")
            wght = data.get("weight", 1.0)
            key = (u, rel, v)
            if key not in seen:
                seen.add(key)
                relations.append({
                    "from": u,
                    "relation": rel,
                    "to": v,
                    "weight": round(wght, 3),
                })

        for u, v, data in self.graph.in_edges(concept, data=True):
            rel = data.get("relation", "СВЯЗАН_С")
            wght = data.get("weight", 1.0)
            key = (u, rel, v)
            if key not in seen:
                seen.add(key)
                relations.append({
                    "from": u,
                    "relation": rel,
                    "to": v,
                    "weight": round(wght, 3),
                })

        return {
            "concept": concept,
            "properties": dict(self.graph.nodes[concept]),
            "relations": sorted(relations, key=lambda x: -x["weight"]),
        }

    def related(
        self,
        concept: str,
        depth: int = 2,
        min_weight: float = 0.0,
    ) -> list[str]:
        """
        Возвращает связанные концепты в радиусе depth с фильтром по весу.
        Использует ручной BFS (быстрее, чем создание подграфа).
        """
        if concept not in self.graph:
            return []

        visited = {concept}
        frontier = [concept]

        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for _, v, data in self.graph.out_edges(node, data=True):
                    if v not in visited and data.get("weight", 1.0) >= min_weight:
                        visited.add(v)
                        next_frontier.append(v)
                # Если нужны и входящие связи, раскомментировать:
                # for u, _, data in self.graph.in_edges(node, data=True):
                #     if u not in visited and data.get("weight", 1.0) >= min_weight:
                #         visited.add(u)
                #         next_frontier.append(u)
            frontier = next_frontier

        visited.remove(concept)
        return list(visited)

    def search(self, keyword: str) -> list[str]:
        """
        Поиск концептов по подстроке в названии (использует индекс SQLite).
        """
        try:
            cursor = self.conn.execute(
                "SELECT name FROM nodes WHERE name LIKE ?",
                (f"%{keyword}%",)
            )
            return [row["name"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка поиска по ключу '{keyword}': {e}")
            return []

    def strongest_relations(self, concept: str, top_n: int = 5) -> list[dict]:
        """Топ N самых сильных связей концепта."""
        result = self.find(concept)
        if not result:
            return []
        return result["relations"][:top_n]

    # ── Методы для поиска структурных аналогий ───────────────────

    def get_edges_by_weight(self, min_weight: float = 0.6) -> list[dict]:
        """Возвращает все рёбра с весом выше порога."""
        cursor = self.conn.execute(
            "SELECT from_node, to_node, relation, weight FROM edges WHERE weight >= ?",
            (min_weight,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def find_structural_analogies(self, min_weight: float = 0.6) -> list[dict]:
        """
        Ищет пары рёбер с одинаковым отношением, но разными узлами.
        Возвращает список кандидатов для создания правил.
        """
        edges = self.get_edges_by_weight(min_weight)
        candidates = []
        # Группируем по отношению
        groups = {}
        for e in edges:
            rel = e["relation"]
            groups.setdefault(rel, []).append((e["from_node"], e["to_node"]))
        for rel, pairs in groups.items():
            if len(pairs) < 2:
                continue
            # Если в группе больше одной пары, считаем их кандидатами
            candidates.append({
                "relation": rel,
                "pairs": pairs
            })
        return candidates

    # ── Статистика ────────────────────────────────────────────────

    def stats(self) -> dict:
        weights = [d.get("weight", 1.0) for _, _, d in self.graph.edges(data=True)]
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "avg_weight": round(sum(weights) / len(weights), 3) if weights else 0.0,
            "sleeping_edges": sum(1 for w in weights if w < WEIGHT_SLEEP),
            "strong_edges": sum(1 for w in weights if w >= 0.8),
        }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"KnowledgeGraph(nodes={s['nodes']} | edges={s['edges']} | "
            f"avg_weight={s['avg_weight']})"
        )

    # ── Вспомогательные методы ────────────────────────────────────

    def _find_edge_key(
        self,
        from_node: str,
        to_node: str,
        relation: str,
    ) -> int | None:
        """Находит ключ ребра в MultiDiGraph по тройке (from, to, relation)."""
        if not self.graph.has_node(from_node) or not self.graph.has_node(to_node):
            return None
        edges = self.graph.get_edge_data(from_node, to_node)
        if edges is None:
            return None
        for key, data in edges.items():
            if data.get("relation") == relation:
                return key
        return None