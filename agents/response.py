"""
agent_response — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
============================================
Собирает финальный ответ из результатов поиска по графу.
Не обращается к БД напрямую — работает только с тем что передано в context.
"""

from __future__ import annotations

from core.agent import ReflexAgent


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

_NO_ANSWER: dict[str, str] = {
    "ru": "Я не знаю об этом. Можете объяснить?",
    "uk": "Я не знаю про це. Можете пояснити?",
    "en": "I don't know about this. Can you explain?",
    "de": "Ich weiß das nicht. Können Sie es erklären?",
    "fr": "Je ne sais pas. Pouvez-vous expliquer?",
    "es": "No lo sé. ¿Puede explicarlo?",
    "it": "Non lo so. Puoi spiegarlo?",
}


class ResponseAgent(ReflexAgent):

    def __init__(self) -> None:
        super().__init__("agent_response")

    def process(self, context: dict) -> dict | None:
        """
        Читает context["graph_results"] и context["intent"].
        Добавляет context["answer"] — готовый текст ответа.
        """
        results  = context.get("graph_results", [])
        intent   = context.get("intent", "statement")
        language = context.get("language", "ru")

        answer = self.build_response(results, intent, language)
        return {**context, "answer": answer}

    def build_response(
        self,
        results:  list[dict],
        intent:   str,
        language: str = "ru",
    ) -> str:
        if not results:
            return _NO_ANSWER.get(language, _NO_ANSWER["en"])

        lines = []
        for r in results:
            # Пропускаем нестандартные результаты (от LearnedAgent-ов)
            if "concept" not in r:
                if "hint" in r:
                    lines.append(r["hint"])
                continue

            concept    = r["concept"]
            relations  = r.get("relations", [])
            properties = r.get("properties", {})

            if "description" in properties:
                lines.append(f"{concept.capitalize()}: {properties['description']}")

            if not relations and "description" not in properties:
                lines.append(f"Знаю концепт '{concept}', но деталей мало.")
                continue

            shown = 0
            for rel in relations[:5]:
                # rel — это dict: {"from": ..., "relation": ..., "to": ..., "weight": ...}
                if not isinstance(rel, dict):
                    continue
                from_node = rel.get("from", "")
                relation  = rel.get("relation", "СВЯЗАН_С")
                to_node   = rel.get("to", "")
                weight    = rel.get("weight", 1.0)

                if weight < 0.2:  # не показываем слабые связи
                    continue

                template = _TEMPLATES.get(relation, "{from} — {to}")
                line = template.format(**{"from": from_node, "to": to_node})
                lines.append(line.capitalize() + ".")
                shown += 1

        no_answer = _NO_ANSWER.get(language, _NO_ANSWER["en"])
        return "\n".join(lines) if lines else no_answer