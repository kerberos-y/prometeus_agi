"""
agent_pattern — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
===========================================
Следит за повторяющимися токенами и парами токенов.
Когда паттерн достигает порога — сигнализирует agent_spawn.

Таблица: patterns
    token       TEXT PK
    count       INTEGER
    updated_at  TEXT
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime

from core.agent import ReflexAgent


class PatternAgent(ReflexAgent):

    def __init__(
        self,
        conn:      sqlite3.Connection,
        threshold: int = 3,
    ) -> None:
        super().__init__("agent_pattern")
        self.conn      = conn
        self.threshold = threshold
        self._counts: Counter = Counter()
        self._dirty:  set[str] = set()
        self._init_db()
        self._load()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    token      TEXT PRIMARY KEY,
                    count      INTEGER DEFAULT 1,
                    updated_at TEXT
                )
            """)

    def _load(self) -> None:
        rows = self.conn.execute("SELECT token, count FROM patterns").fetchall()
        self._counts = Counter({row["token"]: row["count"] for row in rows})

    # ── process() — интерфейс агента ──────────────────────────────

    def process(self, context: dict) -> dict | None:
        """
        Наблюдает за токенами из context["meaningful"].
        Добавляет в context["spawn_candidates"] — список паттернов для спауна.
        """
        tokens = context.get("meaningful", [])
        if not tokens:
            return context

        self._observe(tokens)

        spawn_candidates = self.should_spawn()
        return {
            **context,
            "spawn_candidates": spawn_candidates,
        }

    # ── Публичный API ─────────────────────────────────────────────

    def should_spawn(self) -> list[str]:
        """Паттерны достигшие порога — кандидаты на новый агент."""
        return [t for t, c in self._counts.items() if c >= self.threshold]

    def get_top(self, n: int = 10) -> list[tuple[str, int]]:
        return self._counts.most_common(n)

    def flush(self) -> None:
        """Пакетная запись dirty-паттернов в SQLite."""
        if not self._dirty:
            return
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.executemany(
                """INSERT INTO patterns (token, count, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(token) DO UPDATE SET count = excluded.count,
                   updated_at = excluded.updated_at""",
                [(t, self._counts[t], now) for t in self._dirty]
            )
        self._dirty.clear()

    # ── Внутренние ────────────────────────────────────────────────

    def _observe(self, tokens: list[str]) -> None:
        for t in tokens:
            self._counts[t] += 1
            self._dirty.add(t)
        # Биграммы
        for i in range(len(tokens) - 1):
            pair = f"{tokens[i]}_{tokens[i+1]}"
            self._counts[pair] += 1
            self._dirty.add(pair)
        # Пишем в БД каждые 10 изменений
        if len(self._dirty) >= 10:
            self.flush()