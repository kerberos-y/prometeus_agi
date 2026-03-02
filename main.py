import json
from rich.console import Console
from rich.panel import Panel
from core.graph import KnowledgeGraph
from core.agents.language import LanguageAgent
from core.agents.memory import MemoryAgent
from core.agents.pattern import PatternAgent
from core.agents.spawn import SpawnAgent
from core.agents.response import ResponseAgent
from core.agents.search import SearchAgent

console = Console()

def load_knowledge(graph, path="knowledge/base.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for concept in data["concepts"]:
        name = concept.pop("name")
        # concept теперь содержит description и другие свойства
        graph.add_concept(name, concept)
    for rel in data["relations"]:
        graph.add_relation(rel["from"], rel["to"], rel["type"], rel["weight"])

def learn(word, explanation, graph):
    with open("knowledge/base.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_names = [c["name"] for c in data["concepts"] if "name" in c]

    if word not in existing_names:
        # СОХРАНЯЕМ description прямо в концепт!
        data["concepts"].append({
            "name": word,
            "description": explanation
        })
    else:
        # Обновляем description если уже есть
        for c in data["concepts"]:
            if c.get("name") == word:
                c["description"] = explanation
                break

    explanation_tokens = explanation.lower().split()
    for token in explanation_tokens:
        if graph.find(token):
            already = any(
                r["from"] == word and r["to"] == token
                for r in data["relations"]
            )
            if not already:
                data["relations"].append({
                    "from": word,
                    "to": token,
                    "type": "СВЯЗАН_С",
                    "weight": 0.8
                })

    with open("knowledge/base.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]✓ '{word}' сохранено в базу знаний навсегда[/green]")

def process_query(query, graph, language, memory, pattern, spawn, response, search):
    # Шаг 1 — разбираем запрос
    parsed = language.process(query)
    console.print(f"\n[dim]Токены: {parsed['tokens']} | Значимые: {parsed['meaningful']} | Намерение: {parsed['intent']}[/dim]")

    # Шаг 2 — ищем значимые токены в графе
    results = []
    for token in parsed["meaningful"]:
        found = graph.find(token)
        if found:
            results.append(found)

    # Шаг 3 — если контекстный запрос ("расскажи", "подробнее") — берём из памяти
    if not results and parsed.get("is_context_request"):
        context = memory.get_context(last_n=3)
        for ctx in context:
            for token in ctx.get("tokens", []):
                found = graph.find(token)
                if found and found not in results:
                    results.append(found)
        if results:
            console.print(f"[dim]Контекстный запрос — использую память[/dim]")

    # Шаг 4 — запоминаем
    memory.remember({"query": query, "tokens": parsed["tokens"]})

    # Шаг 5 — наблюдаем паттерны
    pattern.observe(parsed["tokens"])
    frequent = pattern.should_spawn()

    # Шаг 6 — создаём новых агентов
    new_spawned = []
    if frequent:
        for p in frequent:
            new_agent = spawn.spawn(p)
            if new_agent:
                new_spawned.append(new_agent.id)

    if new_spawned:
        console.print(f"[green]✓ Новые агенты: {new_spawned}[/green]")
        console.print(f"[cyan]Всего агентов: {len(spawn.get_all())}[/cyan]")

    # Шаг 7 — строим текстовый ответ
    answer = response.build_response(results, parsed["intent"])
    console.print(Panel(answer, title="[bold cyan]PROMETEUS[/bold cyan]", border_style="cyan"))

    # Шаг 8 — если не знает И это не контекстный запрос — ищем в интернете
    if "Я не знаю" in answer and not parsed.get("is_context_request"):
        unknown = [
            t for t in parsed["meaningful"]
            if not graph.find(t) and len(t) > 2
        ]
        for word in unknown:
            explanation = None

            if search.is_online():
                console.print(f"[cyan]Ищу '{word}' в интернете...[/cyan]")
                explanation = search.search(word)
                if explanation:
                    console.print(Panel(
                        explanation,
                        title=f"[cyan]Найдено в Википедии: {word}[/cyan]",
                        border_style="cyan"
                    ))

                    # Добавляем в граф
                    graph.add_concept(word, {"description": explanation})
                    for token in explanation.lower().split():
                        clean = token.strip('.,;:()-—»«"\'')
                        if graph.find(clean):
                            graph.add_relation(word, clean, "СВЯЗАН_С", weight=0.8)
                    learn(word, explanation, graph)

                    # Рекурсивно изучаем незнакомые слова
                    console.print(f"[cyan]Изучаю связанные понятия...[/cyan]")
                    search.enrich(word, explanation, graph, learn, console, depth=2)

                    console.print(f"[green]Концептов в графе теперь больше![/green]")
                else:
                    console.print(f"[yellow]В интернете не нашёл. Что такое '{word}'? (пропустить — Enter)[/yellow]")
                    explanation = input("  Объясни: ").strip()
                    if explanation:
                        graph.add_concept(word, {"description": explanation})
                        for token in explanation.lower().split():
                            if graph.find(token):
                                graph.add_relation(word, token, "СВЯЗАН_С", weight=0.8)
                        learn(word, explanation, graph)
            else:
                console.print(f"[yellow]Нет интернета. Что такое '{word}'? (пропустить — Enter)[/yellow]")
                explanation = input("  Объясни: ").strip()
                if explanation:
                    graph.add_concept(word, {"description": explanation})
                    for token in explanation.lower().split():
                        if graph.find(token):
                            graph.add_relation(word, token, "СВЯЗАН_С", weight=0.8)
                    learn(word, explanation, graph)

    # Шаг 9 — показываем историю
    context = memory.get_context(last_n=3)
    console.print(f"[dim]История: {[c['query'] for c in context]}[/dim]")

def main():
    console.print(Panel(
        "[bold cyan]PROMETEUS AGI[/bold cyan]\nПрототип v0.2 — с памятью, поиском и текстовыми ответами",
        border_style="cyan"
    ))

    # Инициализация
    graph = KnowledgeGraph()
    language = LanguageAgent()
    memory = MemoryAgent()
    pattern = PatternAgent(threshold=2)
    spawn = SpawnAgent()
    response = ResponseAgent()
    search = SearchAgent()

    # Загрузка базы знаний
    load_knowledge(graph)

    console.print("\n[bold]Введите запрос (или 'выход' для остановки)[/bold]")

    while True:
        try:
            query = input("\n> ").strip()
            if query.lower() in ["выход", "exit", "quit"]:
                console.print("[yellow]Завершение. Всё сохранено.[/yellow]")
                break
            if query:
                process_query(query, graph, language, memory, pattern, spawn, response, search)
        except KeyboardInterrupt:
            console.print("\n[yellow]Завершение. Всё сохранено.[/yellow]")
            break

if __name__ == "__main__":
    main()