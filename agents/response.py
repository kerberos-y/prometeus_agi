"""
agent_response — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
============================================
Собирает финальный ответ. Если есть диалоговый акт (greeting, thanks, goodbye) – 
возвращает соответствующий ответ, игнорируя результаты графа.
"""

from __future__ import annotations
from core.agent import ReflexAgent

_TEMPLATES = {
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

_NO_ANSWER = {
    "ru": "Я не знаю об этом. Можете объяснить?",
    "uk": "Я не знаю про це. Можете пояснити?",
    "en": "I don't know about this. Can you explain?",
    "de": "Ich weiß das nicht. Können Sie es erklären?",
    "fr": "Je ne sais pas. Pouvez-vous expliquer?",
    "es": "No lo sé. ¿Puede explicarlo?",
    "it": "Non lo so. Puoi spiegarlo?",
}

_DIALOGUE_RESPONSES = {
    "greeting": {
        "ru": "Привет! Чем могу помочь?",
        "en": "Hello! How can I help?",
        "de": "Hallo! Wie kann ich helfen?",
        "fr": "Bonjour! Comment puis-je aider?",
        "es": "¡Hola! ¿Cómo puedo ayudar?",
        "it": "Ciao! Come posso aiutare?",
    },
    "thanks": {
        "ru": "Пожалуйста!",
        "en": "You're welcome!",
        "de": "Gern geschehen!",
        "fr": "Je vous en prie!",
        "es": "¡De nada!",
        "it": "Prego!",
    },
    "goodbye": {
        "ru": "До свидания!",
        "en": "Goodbye!",
        "de": "Auf Wiedersehen!",
        "fr": "Au revoir!",
        "es": "¡Adiós!",
        "it": "Arrivederci!",
    },
}


class ResponseAgent(ReflexAgent):
    def __init__(self) -> None:
        super().__init__("agent_response")

    def process(self, context: dict) -> dict | None:
        results = context.get("graph_results", [])
        language = context.get("language", "ru")
        dialogue_act = context.get("dialogue_act")

        # Приоритет: диалоговые ответы
        if dialogue_act and dialogue_act in _DIALOGUE_RESPONSES:
            answer = _DIALOGUE_RESPONSES[dialogue_act].get(language, _DIALOGUE_RESPONSES[dialogue_act]["en"])
            return {**context, "answer": answer}

        # Обычный ответ из графа
        answer = self._build_from_graph(results, language)
        return {**context, "answer": answer}

    def _build_from_graph(self, results: list[dict], language: str) -> str:
        if not results:
            return _NO_ANSWER.get(language, _NO_ANSWER["en"])

        lines = []
        for r in results:
            if "concept" not in r:
                if "hint" in r:
                    lines.append(r["hint"])
                continue

            concept = r["concept"]
            properties = r.get("properties", {})
            if "description" in properties:
                lines.append(f"{concept.capitalize()}: {properties['description']}")

            for rel in r.get("relations", [])[:5]:
                from_node = rel.get("from", "")
                relation  = rel.get("relation", "СВЯЗАН_С")
                to_node   = rel.get("to", "")
                weight    = rel.get("weight", 1.0)
                if weight < 0.2 or from_node == to_node:
                    continue
                template = _TEMPLATES.get(relation, "{from} — {to}")
                line = template.format(**{"from": from_node, "to": to_node})
                lines.append(line.capitalize() + ".")

        return "\n".join(lines) if lines else _NO_ANSWER.get(language, _NO_ANSWER["en"])