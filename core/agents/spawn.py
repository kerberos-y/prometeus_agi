import json
import os
from core.agent import Agent

class SpawnAgent:
    def __init__(self, save_path="knowledge/agents.json"):
        self.id = "agent_spawn"
        self.strength = 1.0
        self.save_path = save_path
        self.spawned = {}
        self.load()  # загружаем созданных агентов

    def spawn(self, pattern):
        if pattern not in self.spawned:
            new_agent = Agent(
                agent_id=f"agent_{pattern}",
                pattern=[pattern],
                response=f"Я знаю паттерн: {pattern}",
                strength=0.5
            )
            self.spawned[pattern] = new_agent
            self.save()
            return new_agent
        return None

    def get_all(self):
        return list(self.spawned.values())

    def save(self):
        data = {
            pattern: {
                "id": agent.id,
                "pattern": agent.pattern,
                "response": agent.response,
                "strength": agent.strength,
                "activations": agent.activations
            }
            for pattern, agent in self.spawned.items()
        }
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(self.save_path):
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for pattern, agent_data in data.items():
                agent = Agent(
                    agent_id=agent_data["id"],
                    pattern=agent_data["pattern"],
                    response=agent_data["response"],
                    strength=agent_data["strength"]
                )
                agent.activations = agent_data["activations"]
                self.spawned[pattern] = agent