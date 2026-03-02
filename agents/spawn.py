"""
agent_spawn — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
=========================================
Создаёт новых LearnedAgent-ов из паттернов обнаруженных agent_pattern.
Персистентность — через AgentRegistry (SQLite).

Правило создания:
    паттерн встретился >= threshold раз
    AND агент с таким id ещё не существует в registry
    AND паттерн не является стоп-словом
"""

from __future__ import annotations

from core.agent import ReflexAgent, LearnedAgent, AgentRegistry


# Не создаём агентов для служебных токенов
_SPAWN_BLACKLIST = {
    "и","в","на","с","а","но","что","это","как","для","по","из","от","до",
    "за","при","или","не","он","она","они","мы","вы","я","то","же","бы",
    "the","a","an","and","or","but","in","on","at","to","of","for","is",
}

_MIN_PATTERN_LEN = 3   # минимум 3 символа в паттерне


class SpawnAgent(ReflexAgent):

    def __init__(self, registry: AgentRegistry) -> None:
        super().__init__("agent_spawn")
        self.registry = registry

    # ── process() — интерфейс агента ──────────────────────────────

    def process(self, context: dict) -> dict | None:
        """
        Читает context["spawn_candidates"] от agent_pattern.
        Создаёт новых LearnedAgent-ов через registry.
        Добавляет context["spawned"] — список id созданных агентов.
        """
        candidates = context.get("spawn_candidates", [])
        spawned = []

        for pattern in candidates:
            agent = self.spawn(pattern)
            if agent:
                spawned.append(agent.id)

        return {**context, "spawned": spawned}

    # ── Публичный API ─────────────────────────────────────────────

    def spawn(self, pattern: str) -> LearnedAgent | None:
        """
        Создаёт LearnedAgent для паттерна если его ещё нет.
        Регистрирует в AgentRegistry.
        Возвращает агента или None если уже существует / не прошёл фильтр.
        """
        if not self._should_spawn(pattern):
            return None

        agent_id = f"agent_{pattern}"
        if self.registry.get(agent_id):
            return None  # уже существует

        agent = LearnedAgent(
            agent_id=agent_id,
            topic=pattern,
            strength=0.5,
            meta={"born_from": "pattern", "pattern": pattern},
        )
        self.registry.register(agent)
        return agent

    # ── Внутренние ────────────────────────────────────────────────

    def _should_spawn(self, pattern: str) -> bool:
        if len(pattern) < _MIN_PATTERN_LEN:
            return False
        if pattern in _SPAWN_BLACKLIST:
            return False
        # Биграммы (содержат _) — проверяем обе части
        if "_" in pattern:
            parts = pattern.split("_")
            if any(p in _SPAWN_BLACKLIST for p in parts):
                return False
        return True