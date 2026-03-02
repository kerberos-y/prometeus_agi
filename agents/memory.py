"""
agent_memory — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
==========================================
Краткосрочная память диалога. Хранится в SQLite (та же graph.db).
НЕ хранит долгосрочные знания — это граф знаний (Уровень 2).

Таблица: memory
    id          INTEGER PK AUTOINCREMENT
    role        TEXT     — "user" | "agent"
    text        TEXT     — исходный текст
    language    TEXT     — ISO 639-1
    intent      TEXT     — question | command | statement
    keywords    TEXT     — JSON список значимых токенов (концептов)
    created_at  TEXT     — ISO timestamp
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from core.agent import ReflexAgent


@dataclass
class MemoryEntry:
    role:       str
    text:       str
    language:   str   = "ru"
    intent:     str   = "statement"
    keywords:   list  = field(default_factory=list)  # список концептов
    created_at: str   = field(default_factory=lambda: datetime.utcnow().isoformat())
    id:         Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Фразы контекстного запроса ────────────────────────────────────

_CONTEXT_PHRASES: dict[str, list[str]] = {
    "ru": ["расскажи подробнее","подробнее","расскажи больше","ещё",
           "что ты знаешь","продолжай","и что","дальше","что ещё"],
    "uk": ["розкажи докладніше","докладніше","розкажи більше","ще",
           "що ти знаєш","продовжуй","далі","що ще"],
    "en": ["tell me more","more details","elaborate","go on",
           "what else","continue","explain more","keep going"],
    "de": ["erzähl mehr","mehr details","weiter","und dann","was noch"],
    "fr": ["dis m'en plus","plus de détails","continue","quoi d'autre"],
    "es": ["cuéntame más","más detalles","continúa","qué más"],
}

def _is_context_request(text: str, language: str) -> bool:
    text_lower = text.lower().strip()
    phrases = _CONTEXT_PHRASES.get(language, []) + _CONTEXT_PHRASES.get("en", [])
    return any(p in text_lower for p in phrases)


class MemoryAgent(ReflexAgent):
    """
    Краткосрочная память сессии.
    Пишет в SQLite и держит deque в RAM для быстрого доступа.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        max_size:       int = 50,
        autosave_every: int = 5,
    ) -> None:
        super().__init__("agent_memory")
        self.conn          = conn
        self.max_size      = max_size
        self.autosave_every = autosave_every
        self._cache: deque[MemoryEntry] = deque(maxlen=max_size)
        self._unsaved = 0
        self._init_db()
        self._load()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    role       TEXT    NOT NULL,
                    text       TEXT    NOT NULL,
                    language   TEXT    DEFAULT 'ru',
                    intent     TEXT    DEFAULT 'statement',
                    keywords   TEXT    DEFAULT '[]',
                    created_at TEXT
                )
            """)
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_created ON memory(created_at)"
            )

    def _load(self) -> None:
        """Загружает последние max_size записей из БД в кэш."""
        try:
            rows = self.conn.execute(
                "SELECT * FROM memory ORDER BY id DESC LIMIT ?",
                (self.max_size,)
            ).fetchall()
            for row in reversed(rows):
                self._cache.append(MemoryEntry(
                    id=row["id"],
                    role=row["role"],
                    text=row["text"],
                    language=row["language"],
                    intent=row["intent"],
                    keywords=json.loads(row["keywords"] or "[]"),
                    created_at=row["created_at"],
                ))
        except Exception as e:
            print(f"[agent_memory] Ошибка загрузки: {e}")

    def process(self, context: dict) -> dict | None:
        """
        Принимает context из agent_language.
        Сохраняет запрос в память.
        Добавляет в context:
            memory_context     — последние N записей
            is_context_request — пользователь просит продолжить тему?
            last_topic         — последнее ключевое слово
        """
        text      = context.get("query", "")
        language  = context.get("language", "ru")
        intent    = context.get("intent", "statement")
        keywords  = context.get("meaningful", [])

        if text:
            entry = MemoryEntry(
                role="user",
                text=text,
                language=language,
                intent=intent,
                keywords=keywords,
            )
            self._remember(entry)

        last_n = context.get("memory_window", 5)
        recent = list(self._cache)[-last_n:]

        last_topic = None
        if recent:
            for entry in reversed(recent):
                if entry.keywords:
                    last_topic = entry.keywords[0]
                    break

        return {
            **context,
            "memory_context":     [e.to_dict() for e in recent],
            "is_context_request": _is_context_request(text, language),
            "last_topic":         last_topic,
        }

    # ── Публичный API ──────────────────────────────────────────

    def remember_agent_response(self, text: str, language: str = "ru") -> None:
        """Запомнить ответ агента (для истории диалога)."""
        self._remember(MemoryEntry(role="agent", text=text, language=language))

    def get_context(self, last_n: int = 5) -> list[MemoryEntry]:
        return list(self._cache)[-last_n:]

    def find(self, keyword: str) -> list[MemoryEntry]:
        kw = keyword.lower()
        return [e for e in self._cache
                if kw in e.text.lower() or kw in e.keywords]

    def clear(self) -> None:
        self._cache.clear()
        with self.conn:
            self.conn.execute("DELETE FROM memory")

    def size(self) -> int:
        return len(self._cache)

    def _remember(self, entry: MemoryEntry) -> None:
        self._cache.append(entry)
        self._unsaved += 1
        if self._unsaved >= self.autosave_every:
            self._flush()

    def _flush(self) -> None:
        new_entries = [e for e in self._cache if e.id is None]
        if not new_entries:
            self._unsaved = 0
            return
        try:
            with self.conn:
                for e in new_entries:
                    cursor = self.conn.execute(
                        """INSERT INTO memory (role, text, language, intent, keywords, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (e.role, e.text, e.language, e.intent,
                         json.dumps(e.keywords, ensure_ascii=False), e.created_at)
                    )
                    e.id = cursor.lastrowid

            self.conn.execute("""
                DELETE FROM memory WHERE id NOT IN (
                    SELECT id FROM memory ORDER BY id DESC LIMIT ?
                )
            """, (self.max_size,))
            self.conn.commit()
            self._unsaved = 0
        except Exception as ex:
            print(f"[agent_memory] Ошибка записи: {ex}")

    def flush(self) -> None:
        self._flush()