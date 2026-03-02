class LanguageAgent:
    def __init__(self):
        self.id = "agent_language"
        self.strength = 1.0
        self.stop_words = [
            "что", "такое", "как", "где", "кто", "когда",
            "почему", "это", "и", "в", "на", "с", "а", "но",
            "же", "ли", "бы", "до", "по", "за", "из", "от"
        ]

    def process(self, text):
        text = text.lower().strip()

        for char in ["?", "!", ".", ",", ";", ":", "...", "…"]:
            text = text.replace(char, "")

        text = text.strip()
        tokens = text.split()

        meaningful_tokens = [t for t in tokens if t not in self.stop_words]

        intent = self.detect_intent(text)

        return {
            "original": text,
            "tokens": tokens,
            "meaningful": meaningful_tokens,
            "intent": intent
        }

    def detect_intent(self, text):
        questions = ["что", "кто", "где", "когда", "как", "почему", "сколько"]
        commands = ["покажи", "найди", "открой", "запусти", "включи", "выключи"]

        for q in questions:
            if q in text:
                return "question"
        for c in commands:
            if c in text:
                return "command"
        return "statement"