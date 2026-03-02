class LanguageAgent:
    def __init__(self):
        self.id = "agent_language"
        self.strength = 1.0
        self.stop_words = [
            "что", "такое", "как", "где", "кто", "когда",
            "почему", "это", "и", "в", "на", "с", "а", "но",
            "же", "ли", "бы", "до", "по", "за", "из", "от"
        ]
        # Фразы которые означают "расскажи о последнем контексте"
        self.context_phrases = [
            "расскажи что знаешь",
            "раскажи что знаешь",
            "что ты знаешь",
            "расскажи подробнее",
            "подробнее",
            "расскажи больше",
            "что об этом знаешь",
            "расскажи",
        ]

    def process(self, text):
        text_clean = text.lower().strip()
        for char in ["?", "!", ".", ",", ";", ":", "...", "…"]:
            text_clean = text_clean.replace(char, "")
        text_clean = text_clean.strip()

        tokens = text_clean.split()
        meaningful_tokens = [t for t in tokens if t not in self.stop_words]
        intent = self.detect_intent(text_clean)

        # Проверяем — это контекстный запрос?
        is_context_request = any(
            phrase in text_clean for phrase in self.context_phrases
        )

        return {
            "original": text_clean,
            "tokens": tokens,
            "meaningful": meaningful_tokens,
            "intent": intent,
            "is_context_request": is_context_request
        }

    def detect_intent(self, text):
        questions = ["что", "кто", "где", "когда", "как", "почему", "сколько"]
        commands = ["покажи", "найди", "открой", "запусти", "включи", "выключи"]
        context_commands = ["расскажи", "раскажи", "объясни", "подробнее"]

        for c in context_commands:
            if c in text:
                return "question"
        for q in questions:
            if q in text:
                return "question"
        for c in commands:
            if c in text:
                return "command"
        return "statement"