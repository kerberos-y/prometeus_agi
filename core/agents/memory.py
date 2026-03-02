import json
import os

class MemoryAgent:
    def __init__(self, max_size=50, save_path="knowledge/memory.json"):
        self.id = "agent_memory"
        self.strength = 1.0
        self.save_path = save_path
        self.short_term = []
        self.max_size = max_size
        self.load()

    def remember(self, entry):
        self.short_term.append(entry)
        if len(self.short_term) > self.max_size:
            self.short_term.pop(0)
        self.save()

    def get_context(self, last_n=5):
        return self.short_term[-last_n:]

    def find_in_memory(self, keyword):
        results = []
        for entry in self.short_term:
            if keyword in str(entry).lower():
                results.append(entry)
        return results

    def save(self):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(self.short_term, f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(self.save_path):
            with open(self.save_path, "r", encoding="utf-8") as f:
                self.short_term = json.load(f)

    def clear(self):
        self.short_term = []
        self.save()