class Agent:
    def __init__(self, agent_id, pattern, response, strength=1.0):
        self.id = agent_id
        self.pattern = pattern        # что активирует агента
        self.response = response      # что он делает
        self.strength = strength      # сила 0.0 - 1.0
        self.activations = 0          # сколько раз активировался

    def activate(self):
        self.activations += 1
        self.strength = min(1.0, self.strength + 0.1)
        return self.response

    def weaken(self):
        self.strength = max(0.0, self.strength - 0.05)

    def is_alive(self):
        return self.strength > 0.2

    def __repr__(self):
        return f"Agent({self.id}, strength={self.strength:.2f})"