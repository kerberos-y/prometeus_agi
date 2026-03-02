"""
agent_dialogue — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
=============================================
Отвечает за связность диалога:
- Разрешение кореференции (замена местоимений на последние концепты)
- Определение диалоговых актов (приветствие, прощание, благодарность)
- Управление контекстом
"""

from __future__ import annotations
from core.agent import ReflexAgent

PRONOUNS = {
    "ru": {"он", "она", "оно", "они", "это", "этот", "эта", "эти"},
    "en": {"he", "she", "it", "they", "this", "that", "these", "those"},
}

DIALOGUE_ACTS = {
    "greeting": {"привет", "здравствуй", "hello", "hi"},
    "thanks": {"спасибо", "благодарю", "thanks", "thank you"},
    "goodbye": {"пока", "до свидания", "bye", "goodbye"},
    "clarify": {"подробнее", "уточни", "explain more", "elaborate"},
}

class DialogueAgent(ReflexAgent):
    def __init__(self):
        super().__init__("agent_dialogue")

    def process(self, context: dict) -> dict | None:
        history = context.get("memory_context", [])
        if not history:
            return context

        text = context.get("query", "")
        language = context.get("language", "ru")
        meaningful = context.get("meaningful", [])

        # 1. Кореференция
        resolved = self._resolve_coreference(text, history, language)
        if resolved != text:
            context["resolved_query"] = resolved
            context["query"] = resolved

        # 2. Диалоговый акт
        act = self._detect_dialogue_act(text, language)
        context["dialogue_act"] = act

        # 3. Контекстный запрос
        if context.get("is_context_request") and not meaningful:
            last_topic = context.get("last_topic")
            if last_topic:
                context["meaningful"] = [last_topic]
                context["query"] = f"расскажи о {last_topic}"

        return context

    def _resolve_coreference(self, text: str, history: list, lang: str) -> str:
        words = text.lower().split()
        pronouns = PRONOUNS.get(lang, set())
        if not any(w in pronouns for w in words):
            return text

        for entry in reversed(history):
            if entry.get("role") in ("user", "agent"):
                concepts = entry.get("keywords", [])
                if concepts:
                    last_concept = concepts[0]
                    new_words = []
                    replaced = False
                    for w in words:
                        if not replaced and w in pronouns:
                            new_words.append(last_concept)
                            replaced = True
                        else:
                            new_words.append(w)
                    return " ".join(new_words)
        return text

    def _detect_dialogue_act(self, text: str, lang: str) -> str:
        text_lower = text.lower()
        for act, keywords in DIALOGUE_ACTS.items():
            if any(kw in text_lower for kw in keywords):
                return act
        return "statement"