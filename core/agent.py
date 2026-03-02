"""
PROMETEUS AGI — Базовый класс агента
=====================================

Иерархия агентов:
    Agent (абстрактный базовый)
    ├── ReflexAgent   — прошиты при старте, никогда не умирают
    └── LearnedAgent  — рождаются из паттернов, могут засыпать и умирать

Жизненный цикл LearnedAgent:
    EMBRYO → ACTIVE → SLEEPING → DEAD

Персистентность:
    AgentRegistry сохраняет всех агентов в SQLite с единым соединением.
    load_all() восстанавливает состояние при перезапуске.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
import sqlite3
import json
import os


# ──────────────────────────────────────────────────────────────────
# ПЕРЕЧИСЛЕНИЯ
# ──────────────────────────────────────────────────────────────────

class AgentState(Enum):
    EMBRYO   = "embryo"    # только создан, ещё не активировался
    ACTIVE   = "active"    # работает нормально
    SLEEPING = "sleeping"  # слабый, но жив (strength 0.1–0.3)
    DEAD     = "dead"      # удалён из системы


class AgentType(Enum):
    REFLEX  = "reflex"   # базовые рефлексы — не умирают никогда
    LEARNED = "learned"  # выучены из паттернов — могут умереть
    DOMAIN  = "domain"   # доменные знания (медицина, погода...)


# ──────────────────────────────────────────────────────────────────
# БАЗОВЫЙ АГЕНТ
# ──────────────────────────────────────────────────────────────────

class Agent(ABC):
    """Абстрактный базовый агент системы PROMETEUS."""

    # Пороги силы
    STRENGTH_MAX     = 1.0
    STRENGTH_BORN    = 1.0   # начальная сила рефлекса
    STRENGTH_LEARNED = 0.5   # начальная сила выученного агента
    STRENGTH_SLEEP   = 0.3   # ниже — засыпает
    STRENGTH_DEATH   = 0.1   # ниже — умирает

    # Дельты изменения силы
    DELTA_ACTIVATE    = +0.05
    DELTA_WEAKEN      = -0.05
    DELTA_FEEDBACK_OK = +0.10
    DELTA_FEEDBACK_NO = -0.15

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType = AgentType.LEARNED,
        strength: float | None = None,
        meta: dict | None = None,
    ) -> None:
        self.id            = agent_id
        self.agent_type    = agent_type
        self.strength: float = strength if strength is not None else (
            self.STRENGTH_BORN if agent_type == AgentType.REFLEX
            else self.STRENGTH_LEARNED
        )
        self.activations:  int        = 0
        self.state:        AgentState = AgentState.EMBRYO
        self.created_at:   str        = datetime.utcnow().isoformat()
        self.activated_at: str | None = None
        self.meta:         dict       = meta or {}
        self._update_state()

    # ── Абстрактный метод ─────────────────────────────────────────

    @abstractmethod
    def process(self, context: dict) -> dict | None:
        """
        Основная логика агента.

        context содержит:
            tokens     : list[str]       — все токены запроса
            meaningful : list[str]       — значимые токены (без стоп-слов)
            intent     : str             — намерение (question / command / context)
            graph      : KnowledgeGraph  — ссылка на граф знаний
            memory     : list[dict]      — последние N записей памяти

        Возвращает dict с результатом или None если агент не применим.
        """
        ...

    def can_handle(self, context: dict) -> bool:
        """Может ли агент обработать контекст? По умолчанию — да (если жив)."""
        return self.is_alive()

    # ── Жизненный цикл ────────────────────────────────────────────

    def activate(self, context: dict) -> dict | None:
        """Вызывается шиной событий. Запускает process() и обновляет силу."""
        if not self.is_alive():
            return None

        result = self.process(context)

        if result is not None:
            self._change_strength(self.DELTA_ACTIVATE)
            self.activations += 1
            self.activated_at = datetime.utcnow().isoformat()
        else:
            # Агент не помог — слабеем вполсилы
            self._change_strength(self.DELTA_WEAKEN * 0.5)

        self._update_state()
        return result

    def feedback(self, positive: bool) -> None:
        """
        Обратная связь от пользователя или другого агента.
        positive=True  → "верно"   → усиляемся
        positive=False → "неверно" → слабеем
        """
        delta = self.DELTA_FEEDBACK_OK if positive else self.DELTA_FEEDBACK_NO
        self._change_strength(delta)
        self._update_state()

    def weaken(self, delta: float | None = None) -> None:
        """Явное ослабление агента (например, при forgetting)."""
        self._change_strength(-(delta if delta is not None else self.DELTA_WEAKEN))
        self._update_state()

    def is_alive(self) -> bool:
        """Рефлексы живут вечно. Остальные — пока сила выше порога смерти."""
        if self.agent_type == AgentType.REFLEX:
            return True
        return self.strength > self.STRENGTH_DEATH

    def is_sleeping(self) -> bool:
        return self.state == AgentState.SLEEPING

    # ── Внутренние методы ─────────────────────────────────────────

    def _change_strength(self, delta: float) -> None:
        if self.agent_type == AgentType.REFLEX:
            # Рефлексы не слабеют ниже 0.5
            self.strength = max(0.5, min(self.STRENGTH_MAX, self.strength + delta))
        else:
            self.strength = max(0.0, min(self.STRENGTH_MAX, self.strength + delta))

    def _update_state(self) -> None:
        if self.agent_type == AgentType.REFLEX:
            self.state = AgentState.ACTIVE
            return
        if self.strength <= self.STRENGTH_DEATH:
            self.state = AgentState.DEAD
        elif self.strength <= self.STRENGTH_SLEEP:
            self.state = AgentState.SLEEPING
        elif self.state in (AgentState.EMBRYO, AgentState.SLEEPING):
            self.state = AgentState.ACTIVE

    # ── Сериализация ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "agent_type":   self.agent_type.value,
            "strength":     self.strength,
            "activations":  self.activations,
            "state":        self.state.value,
            "created_at":   self.created_at,
            "activated_at": self.activated_at,
            "meta":         self.meta,
        }

    def __repr__(self) -> str:
        return (
            f"Agent({self.id} | {self.agent_type.value} | "
            f"{self.state.value} | strength={self.strength:.2f} | "
            f"activations={self.activations})"
        )


# ──────────────────────────────────────────────────────────────────
# РЕФЛЕКС-АГЕНТ — не умирает никогда
# ──────────────────────────────────────────────────────────────────

class ReflexAgent(Agent):
    """
    Базовые рефлексы системы. Всегда ACTIVE.
    Наследуй: LanguageAgent, MemoryAgent, PatternAgent, SpawnAgent...
    """

    def __init__(self, agent_id: str, meta: dict | None = None) -> None:
        super().__init__(agent_id, AgentType.REFLEX, strength=1.0, meta=meta)

    @abstractmethod
    def process(self, context: dict) -> dict | None:
        ...


# ──────────────────────────────────────────────────────────────────
# ВЫУЧЕННЫЙ АГЕНТ — рождается из паттернов, может умереть
# ──────────────────────────────────────────────────────────────────

class LearnedAgent(Agent):
    """
    Агент, рождённый SpawnAgent из повторяющегося паттерна.
    Специализируется на конкретной теме (topic).

    Жизненный цикл:
        SpawnAgent создаёт → EMBRYO
        Первая активация   → ACTIVE
        Долго не нужен     → SLEEPING
        strength < 0.1     → DEAD → AgentRegistry.cleanup_dead()
    """

    def __init__(
        self,
        agent_id: str,
        topic: str,
        strength: float | None = None,
        meta: dict | None = None,
    ) -> None:
        super().__init__(
            agent_id,
            AgentType.LEARNED,
            strength=strength,
            meta={"topic": topic, **(meta or {})},
        )
        self.topic = topic

    def can_handle(self, context: dict) -> bool:
        """Обрабатывает только если его тема упоминается в значимых токенах."""
        if not self.is_alive():
            return False
        meaningful = context.get("meaningful", [])
        return self.topic.lower() in [t.lower() for t in meaningful]

    def process(self, context: dict) -> dict | None:
        """
        Базовая реализация: возвращает подсказку по теме.
        Переопределяй в доменных агентах (medicine, weather...).
        """
        if not self.can_handle(context):
            return None
        return {
            "source": self.id,
            "topic":  self.topic,
            "hint":   f"Агент '{self.id}' специализируется на теме '{self.topic}'",
        }


# ──────────────────────────────────────────────────────────────────
# РЕЕСТР АГЕНТОВ (УЛУЧШЕННАЯ ВЕРСИЯ)
# ──────────────────────────────────────────────────────────────────

class AgentRegistry:
    """
    Хранит всех агентов в памяти и персистирует в SQLite.
    Использует единое соединение с БД для всех операций.

    Использование:
        registry = AgentRegistry()
        registry.register(agent)
        registry.load_all(factory)   # восстановить агентов при перезапуске

        agent  = registry.get("agent_language")
        active = registry.get_active()
        registry.sync()
        registry.cleanup_dead()
        registry.close()              # при завершении программы
    """

    def __init__(self, db_path: str = "knowledge/graph.db") -> None:
        self.db_path = db_path
        self._agents: dict[str, Agent] = {}
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Единое соединение на весь жизненный цикл
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Создаёт таблицу agents, если её нет."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id           TEXT PRIMARY KEY,
                    agent_type   TEXT    NOT NULL,
                    strength     REAL    DEFAULT 1.0,
                    activations  INTEGER DEFAULT 0,
                    state        TEXT    DEFAULT 'embryo',
                    created_at   TEXT,
                    activated_at TEXT,
                    meta         TEXT    DEFAULT '{}'
                )
            """)

    # ── CRUD ──────────────────────────────────────────────────────

    def register(self, agent: Agent) -> None:
        """Регистрирует агента в памяти и сохраняет в БД."""
        self._agents[agent.id] = agent
        self._save(agent)

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def remove(self, agent_id: str) -> None:
        """Удаляет агента из памяти и БД."""
        self._agents.pop(agent_id, None)
        with self.conn:
            self.conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    def _save(self, agent: Agent) -> None:
        """Сохраняет одного агента в БД (upsert)."""
        d = agent.to_dict()
        with self.conn:
            self.conn.execute("""
                INSERT INTO agents
                    (id, agent_type, strength, activations, state,
                     created_at, activated_at, meta)
                VALUES
                    (:id, :agent_type, :strength, :activations, :state,
                     :created_at, :activated_at, :meta)
                ON CONFLICT(id) DO UPDATE SET
                    strength     = excluded.strength,
                    activations  = excluded.activations,
                    state        = excluded.state,
                    activated_at = excluded.activated_at,
                    meta         = excluded.meta
            """, {**d, "meta": json.dumps(d["meta"], ensure_ascii=False)})

    # ── Восстановление из БД ──────────────────────────────────────

    def load_all(self, factory: AgentFactory) -> int:
        """
        Загружает LearnedAgent-ов из БД при перезапуске системы.
        ReflexAgent-ы регистрируются вручную в main.py — не трогаем.

        Возвращает количество восстановленных агентов.
        """
        loaded = 0
        rows = self.conn.execute(
            "SELECT * FROM agents WHERE agent_type != 'reflex'"
        ).fetchall()

        for row in rows:
            data = dict(row)
            data["meta"] = json.loads(data.get("meta") or "{}")
            # Пропускаем агентов, которые уже зарегистрированы вручную
            if data["id"] in self._agents:
                continue
            agent = factory.create(data)
            if agent is not None:
                self._agents[agent.id] = agent
                loaded += 1

        return loaded

    # ── Обслуживание ──────────────────────────────────────────────

    def sync(self) -> None:
        """Сохраняет состояние всех агентов в БД. Вызывай периодически."""
        for agent in self._agents.values():
            self._save(agent)

    def cleanup_dead(self) -> int:
        """
        Удаляет всех мёртвых агентов одним запросом.
        Возвращает количество удалённых.
        """
        dead_ids = [
            aid for aid, a in self._agents.items()
            if a.state == AgentState.DEAD
        ]
        if not dead_ids:
            return 0

        # Удаляем из памяти
        for aid in dead_ids:
            del self._agents[aid]

        # Удаляем из БД одним запросом с параметрами
        placeholders = ','.join(['?'] * len(dead_ids))
        with self.conn:
            self.conn.execute(f"DELETE FROM agents WHERE id IN ({placeholders})", dead_ids)

        print(f"[Registry] Удалено мёртвых агентов: {len(dead_ids)}")
        return len(dead_ids)

    def close(self) -> None:
        """Закрывает соединение с БД."""
        if self.conn:
            self.conn.close()

    # ── Запросы ───────────────────────────────────────────────────

    def get_active(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.state == AgentState.ACTIVE]

    def get_sleeping(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.state == AgentState.SLEEPING]

    def get_by_type(self, agent_type: AgentType) -> list[Agent]:
        return [a for a in self._agents.values() if a.agent_type == agent_type]

    def all(self) -> list[Agent]:
        return list(self._agents.values())

    def stats(self) -> dict:
        counts = {s.value: 0 for s in AgentState}
        for a in self._agents.values():
            counts[a.state.value] += 1
        return {
            "total":    len(self._agents),
            "by_state": counts,
            "by_type":  {t.value: len(self.get_by_type(t)) for t in AgentType},
        }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"AgentRegistry(total={s['total']} | "
            f"active={s['by_state']['active']} | "
            f"sleeping={s['by_state']['sleeping']} | "
            f"dead={s['by_state']['dead']})"
        )


# ──────────────────────────────────────────────────────────────────
# ФАБРИКА АГЕНТОВ — нужна для load_all()
# ──────────────────────────────────────────────────────────────────

class AgentFactory:
    """
    Восстанавливает агентов из строк БД при перезапуске.

    Расширяй через register_builder() для своих типов:
        factory = AgentFactory()
        factory.register_builder("domain", DomainAgent.from_dict)
    """

    def __init__(self) -> None:
        self._builders: dict[str, callable] = {}
        self.register_builder("learned", self._build_learned)

    def register_builder(self, agent_type: str, builder: callable) -> None:
        """builder(row: dict) → Agent"""
        self._builders[agent_type] = builder

    def create(self, row: dict) -> Agent | None:
        builder = self._builders.get(row.get("agent_type"))
        if builder is None:
            return None
        try:
            return builder(row)
        except Exception as e:
            print(f"[AgentFactory] Ошибка восстановления {row.get('id')}: {e}")
            return None

    @staticmethod
    def _build_learned(row: dict) -> LearnedAgent:
        meta  = row.get("meta") or {}
        topic = meta.get("topic", row["id"])
        agent = LearnedAgent(
            agent_id=row["id"],
            topic=topic,
            strength=row.get("strength", 0.5),
            meta=meta,
        )
        agent.activations  = row.get("activations", 0)
        agent.created_at   = row.get("created_at", agent.created_at)
        agent.activated_at = row.get("activated_at")
        # Восстанавливаем состояние из БД напрямую
        try:
            agent.state = AgentState(row["state"])
        except (KeyError, ValueError):
            agent._update_state()
        return agent