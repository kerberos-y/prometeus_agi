"""
agent_analogy — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
===========================================
Ищет структурные аналогии в графе знаний и применяет обобщённые правила.
Хранит правила в отдельной таблице SQLite.

Логика:
1. При каждом запросе анализирует найденные концепты.
2. Ищет правила, которые можно применить к ним.
3. Если правило успешно применяется, добавляет выведенный концепт в результат.
4. Периодически запускает фоновый поиск новых аналогий (при достаточном количестве активаций).
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from collections import defaultdict
from core.agent import ReflexAgent


class AnalogyAgent(ReflexAgent):
    """
    Агент аналогий. Использует единое соединение с SQLite.
    """

    def __init__(self, conn: sqlite3.Connection):
        super().__init__("agent_analogy")
        self.conn = conn
        self._init_rules_table()
        self._search_counter = 0
        self._search_threshold = 10  # искать новые аналогии каждые N запросов

    def _init_rules_table(self):
        """Создаёт таблицу правил, если её нет."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern     TEXT UNIQUE,   -- JSON: {"relation": "...", "from_type": "...", "to_type": "..."}
                    relation    TEXT,          -- обобщённое отношение (например, "ГЕНДЕРНАЯ_ПАРА")
                    strength    REAL DEFAULT 1.0,
                    examples    TEXT,          -- JSON список примеров
                    created_at  TEXT,
                    updated_at  TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_strength ON rules(strength)")

    # ── process() — интерфейс агента ──────────────────────────────

    def process(self, context: dict) -> dict | None:
        """
        Принимает context с полем graph_results (список концептов).
        Добавляет поле analogies — список выведенных по аналогии утверждений.
        """
        # 1. Извлекаем концепты из graph_results
        concepts = []
        for item in context.get("graph_results", []):
            if "concept" in item:
                concepts.append(item["concept"])

        if not concepts:
            return context

        # 2. Ищем применимые правила
        analogies = []
        for concept in concepts:
            rules = self._find_applicable_rules(concept)
            for rule in rules:
                inferred = self._apply_rule(concept, rule)
                if inferred:
                    analogies.append({
                        "source": concept,
                        "relation": rule["relation"],
                        "target": inferred,
                        "rule_id": rule["id"]
                    })
                    # Усиливаем правило (Hebbian)
                    self._update_rule_strength(rule["id"], +0.05)

        # 3. Периодически запускаем поиск новых аналогий
        self._search_counter += 1
        if self._search_counter >= self._search_threshold:
            self._discover_new_rules()
            self._search_counter = 0

        return {**context, "analogies": analogies}

    # ── Поиск применимых правил ───────────────────────────────────

    def _find_applicable_rules(self, concept: str) -> list[dict]:
        """
        Возвращает все правила, которые могут быть применены к данному концепту.
        Пока просто все правила со strength > 0.3.
        В будущем можно фильтровать по типу концепта (например, одушевлённый/неодушевлённый).
        """
        cursor = self.conn.execute(
            "SELECT id, pattern, relation, strength, examples FROM rules WHERE strength > 0.3"
        )
        rows = cursor.fetchall()
        rules = []
        for row in rows:
            rule = dict(row)
            rule["pattern"] = json.loads(rule["pattern"]) if rule["pattern"] else {}
            rule["examples"] = json.loads(rule["examples"]) if rule["examples"] else []
            rules.append(rule)
        return rules

    def _apply_rule(self, concept: str, rule: dict) -> str | None:
        """
        Применяет правило к концепту. Возвращает выведенный концепт или None.
        Пример: если правило "ГЕНДЕРНАЯ_ПАРА" и концепт "актёр", ищем "актриса" в графе.
        Упрощённо: правило содержит шаблон преобразования (например, суффиксы).
        Для начала используем простой эвристический подход: ищем в графе концепт,
        который связан с исходным отношением rule["relation"].
        """
        # Проверяем, есть ли у исходного концепта связь с каким-то другим по этому отношению
        # (например, "актёр" -> "актриса" с отношением "ГЕНДЕРНАЯ_ПАРА")
        cursor = self.conn.execute(
            "SELECT to_node FROM edges WHERE from_node = ? AND relation = ? AND weight > 0.5",
            (concept, rule["relation"])
        )
        row = cursor.fetchone()
        if row:
            return row["to_node"]

        # Если нет прямой связи, пробуем обратную
        cursor = self.conn.execute(
            "SELECT from_node FROM edges WHERE to_node = ? AND relation = ? AND weight > 0.5",
            (concept, rule["relation"])
        )
        row = cursor.fetchone()
        if row:
            return row["from_node"]

        # Иначе ничего не выводим
        return None

    # ── Открытие новых правил ─────────────────────────────────────

    def _discover_new_rules(self):
        """
        Анализирует граф в поисках повторяющихся структур.
        Создаёт новые правила, если находит достаточно примеров.
        """
        # Находим все рёбра с весом > 0.6
        cursor = self.conn.execute(
            "SELECT from_node, to_node, relation, weight FROM edges WHERE weight > 0.6"
        )
        edges = cursor.fetchall()

        # Группируем по отношению
        groups = defaultdict(list)
        for e in edges:
            groups[e["relation"]].append((e["from_node"], e["to_node"]))

        for rel, pairs in groups.items():
            if len(pairs) < 3:
                continue  # нужно минимум 3 примера для обобщения

            # Пытаемся выделить общий паттерн: например, все пары имеют один и тот же тип преобразования
            # Пока создаём простое правило: отношение rel как обобщённое
            pattern = {"relation": rel}
            examples = [{"from": f, "to": t} for f, t in pairs]

            # Проверяем, нет ли уже такого правила
            existing = self.conn.execute(
                "SELECT id FROM rules WHERE pattern = ?", (json.dumps(pattern, ensure_ascii=False),)
            ).fetchone()
            if existing:
                continue

            # Создаём новое правило
            now = datetime.utcnow().isoformat()
            self.conn.execute("""
                INSERT INTO rules (pattern, relation, strength, examples, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                json.dumps(pattern, ensure_ascii=False),
                rel,
                0.8,  # начальная сила
                json.dumps(examples, ensure_ascii=False),
                now, now
            ))
            print(f"[agent_analogy] Новое правило: {rel} (на основе {len(pairs)} примеров)")

    def _update_rule_strength(self, rule_id: int, delta: float):
        """Усиливает или ослабляет правило (Hebbian learning)."""
        self.conn.execute(
            "UPDATE rules SET strength = strength + ?, updated_at = ? WHERE id = ?",
            (delta, datetime.utcnow().isoformat(), rule_id)
        )
        # Удаляем слишком слабые правила
        self.conn.execute("DELETE FROM rules WHERE strength < 0.2")

    # ── Публичный API для других агентов ──────────────────────────

    def get_rules(self, min_strength: float = 0.3) -> list[dict]:
        """Возвращает все активные правила."""
        cursor = self.conn.execute(
            "SELECT id, pattern, relation, strength, examples FROM rules WHERE strength >= ?",
            (min_strength,)
        )
        rows = cursor.fetchall()
        rules = []
        for row in rows:
            rule = dict(row)
            rule["pattern"] = json.loads(rule["pattern"]) if rule["pattern"] else {}
            rule["examples"] = json.loads(rule["examples"]) if rule["examples"] else []
            rules.append(rule)
        return rules