import json
import os
from collections import Counter

class PatternAgent:
    def __init__(self, threshold=3, save_path="knowledge/patterns.json"):
        self.id = "agent_pattern"
        self.strength = 1.0
        self.save_path = save_path
        self.patterns = Counter()
        self.threshold = threshold
        self.load()

    def observe(self, tokens):
        for token in tokens:
            self.patterns[token] += 1
        for i in range(len(tokens) - 1):
            pair = f"{tokens[i]}_{tokens[i+1]}"
            self.patterns[pair] += 1
        self.save()

    def get_frequent(self):
        return [p for p, count in self.patterns.items()
                if count >= self.threshold]

    def should_spawn(self):
        return self.get_frequent()

    def save(self):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(dict(self.patterns), f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(self.save_path):
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.patterns = Counter(data)