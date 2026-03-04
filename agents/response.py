"""
agent_response — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
============================================
Собирает финальный ответ из результатов графа.

Никакого хардкода языков — ответные фразы берутся из _lang.RESPONSES:
    _lang.RESPONSES["no_answer"] — если граф ничего не нашёл
    _lang.RESPONSES["greeting"]  — если dialogue_act == greeting
    _lang.RESPONSES["thanks"]    — если dialogue_act == thanks
    _lang.RESPONSES["goodbye"]   — если dialogue_act == goodbye
"""

from __future__ import annotations
from core.agent import ReflexAgent
from agents.language import _lang

# Шаблоны связей — универсальные, не зависят от языка
_TEMPLATES: dict[str, str] = {
    "ЯВЛЯЕТСЯ_ЧАСТЬЮ": "{from} является частью {to}",
    "ЯВЛЯЕТСЯ":        "{from} является {to}",
    "ИМЕЕТ":           "{from} имеет {to}",
    "СОДЕРЖИТ":        "{from} содержит {to}",
    "СВЯЗАН_С":        "{from} связано с {to}",
    "ВКЛЮЧАЕТ":        "{from} включает {to}",
    "МОЖЕТ_БЫТЬ":      "{from} может быть {to}",
    "ПРОТИВОПОЛОЖНО":  "{from} противоположно {to}",
    "IS_A":            "{from} is a {to}",
    "HAS":             "{from} has {to}",
    "RELATED_TO":      "{from} is related to {to}",
    "PART_OF":         "{from} is part of {to}",
}


class ResponseAgent(ReflexAgent):

    def __init__(self) -> None:
        super().__init__("agent_response")

    def process(self, context: dict) -> dict | None:
        results      = context.get("graph_results", [])
        dialogue_act = context.get("dialogue_act")

        # Приоритет: диалоговые ответы
        if dialogue_act and dialogue_act in _lang.RESPONSES:
            return {**context, "answer": _lang.RESPONSES[dialogue_act]}

        # Обычный ответ из графа
        return {**context, "answer": self._build_from_graph(results)}

    # ── Внутренние методы ─────────────────────────────────────────

    def _build_from_graph(self, results: list[dict]) -> str:
        """
        Собирает текстовый ответ из результатов поиска по графу.
        Сначала выводит description концепта, затем его связи.
        """
        if not results:
            return _lang.RESPONSES["no_answer"]

        lines = []
        for r in results:
            if "concept" not in r:
                # LearnedAgent мог вернуть просто hint
                if "hint" in r:
                    lines.append(r["hint"])
                continue

            concept    = r["concept"]
            properties = r.get("properties", {})

            # Показываем оригинальную форму если есть, иначе стем
            display = properties.get("original", concept)

            if "description" in properties:
                lines.append(f"{display.capitalize()}: {properties['description']}")

            for rel in r.get("relations", [])[:5]:
                from_node = rel.get("from", "")
                relation  = rel.get("relation", "СВЯЗАН_С")
                to_node   = rel.get("to", "")
                weight    = rel.get("weight", 1.0)

                if weight < 0.2 or from_node == to_node:
                    continue

                template = _TEMPLATES.get(relation, "{from} — {to}")
                lines.append(template.format(**{"from": from_node, "to": to_node}).capitalize() + ".")

        return "\n".join(lines) if lines else _lang.RESPONSES["no_answer"]