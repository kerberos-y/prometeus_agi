class ResponseAgent:
    def __init__(self):
        self.id = "agent_response"
        self.strength = 1.0
        self.templates = {
            "ЯВЛЯЕТСЯ_ЧАСТЬЮ": "{from} является частью {to}",
            "ЯВЛЯЕТСЯ":        "{from} является {to}",
            "ИМЕЕТ":           "{from} имеет {to}",
            "СОДЕРЖИТ":        "{from} содержит {to}",
            "СВЯЗАН_С":        "{from} связано с {to}",
            "ВКЛЮЧАЕТ":        "{from} включает {to}",
            "МОЖЕТ_БЫТЬ":      "{from} может быть {to}",
            "ПРОТИВОПОЛОЖНО":  "{from} противоположно {to}",
        }

    def build_response(self, results, intent):
        if not results:
            return "Я не знаю об этом. Можете объяснить?"

        lines = []
        for r in results:
            concept = r["concept"]
            relations = r["relations"]
            properties = r.get("properties", {})

            # Есть описание в свойствах узла
            if "description" in properties:
                lines.append(f"{concept.capitalize()}: {properties['description']}")

            if not relations and "description" not in properties:
                lines.append(f"Я знаю концепт '{concept}', но у меня мало информации о нём.")
                continue

            # Ограничиваем до 5 связей чтобы не спамить
            shown = 0
            for rel in relations:
                if shown >= 5:
                    break
                from_node, relation, to_node = rel
                template = self.templates.get(relation, "{from} — {to}")
                line = template.format(**{"from": from_node, "to": to_node})
                lines.append(line.capitalize() + ".")
                shown += 1

        return "\n".join(lines) if lines else "Я не знаю об этом. Можете объяснить?"