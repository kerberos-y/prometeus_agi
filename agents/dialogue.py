"""
agent_dialogue — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
=============================================
Отвечает за связность диалога:
  - Разрешение кореференции (замена местоимений на последний концепт)
  - Определение диалоговых актов
  - Управление контекстным запросом

ИСПРАВЛЕНИЕ: кореференция проверяет RAW токены (context["tokens"]),
а не стемы — местоимения стеммируются и теряют форму.
Пример: "он" после стемминга может стать чем угодно или
отфильтроваться как стоп-слово до того как dialogue увидит его.
"""

from __future__ import annotations
from core.agent import ReflexAgent
from agents.language import _lang


class DialogueAgent(ReflexAgent):

    def __init__(self) -> None:
        super().__init__("agent_dialogue")

    def process(self, context: dict) -> dict | None:
        history    = context.get("memory_context", [])
        text       = context.get("query", "")
        # Используем RAW токены — до стемминга и фильтрации
        raw_tokens = context.get("tokens", text.lower().split())
        meaningful = context.get("meaningful", [])

        # 1. Кореференция — по raw токенам, местоимения ещё не отфильтрованы
        if history:
            resolved = self._resolve_coreference(text, raw_tokens, history)
            if resolved != text:
                context["resolved_query"] = resolved
                context["query"]          = resolved

        # 2. Диалоговый акт
        context["dialogue_act"] = self._detect_dialogue_act(text)

        # 3. Контекстный запрос без ключевых слов — берём тему из памяти
        if context.get("is_context_request") and not meaningful:
            last_topic = context.get("last_topic")
            if last_topic:
                context["meaningful"] = [last_topic]
                context["query"]      = f"расскажи о {last_topic}"

        return context

    # ── Внутренние методы ─────────────────────────────────────────

    def _resolve_coreference(
        self, text: str, raw_tokens: list[str], history: list
    ) -> str:
        """
        Если в raw_tokens есть местоимение из _lang.PRONOUNS —
        заменяем первое вхождение на последний концепт из истории.

        Работаем с raw_tokens (оригинальные слова запроса),
        а не со стемами — стемы могут быть уже отфильтрованы.
        """
        pronouns = _lang.PRONOUNS
        if not any(w in pronouns for w in raw_tokens):
            return text

        # Последний концепт из истории (от новых к старым)
        for entry in reversed(history):
            concepts = entry.get("keywords", [])
            if concepts:
                last_concept = concepts[0]
                new_tokens   = []
                replaced     = False
                for w in raw_tokens:
                    if not replaced and w in pronouns:
                        new_tokens.append(last_concept)
                        replaced = True
                    else:
                        new_tokens.append(w)
                return " ".join(new_tokens)

        return text

    def _detect_dialogue_act(self, text: str) -> str:
        """
        Определяет диалоговый акт по ключевым словам из _lang.DIALOGUE_ACTS.
        """
        text_lower = text.lower()
        for act, keywords in _lang.DIALOGUE_ACTS.items():
            if any(kw in text_lower for kw in keywords):
                return act
        return "statement"