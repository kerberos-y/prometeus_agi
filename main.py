"""
PROMETEUS AGI — Точка входа v0.8 (с диалогом и аналогиями)
===================================================================
Добавлен DialogueAgent для управления диалогом и разрешения кореференции.
Исправлено: после Wikipedia концепты сразу добавляются в graph_results.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from core.graph import KnowledgeGraph
from core.agent import AgentRegistry, AgentFactory
from agents.language import LanguageAgent
from agents.memory   import MemoryAgent
from agents.pattern  import PatternAgent
from agents.spawn    import SpawnAgent
from agents.response import ResponseAgent
from agents.search   import SearchAgent
from agents.analogy  import AnalogyAgent
from agents.dialogue import DialogueAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("prometeus.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger  = logging.getLogger("prometeus.main")
console = Console()

DB_PATH    = "knowledge/graph.db"
SYNC_EVERY = 10


def add_concept_to_graph(word: str, explanation: str, graph: KnowledgeGraph) -> None:
    """Добавляет новый концепт в граф знаний и создаёт связи."""
    graph.add_concept(word, {"description": explanation})
    for token in explanation.lower().split():
        clean = token.strip('.,;:()-—»«"\'')
        if len(clean) > 2 and clean != word and graph.find(clean):
            graph.add_relation(word, clean, "СВЯЗАН_С", weight=0.8)
    console.print(f"[green]✓ '{word}' добавлено в граф знаний[/green]")


def process_query(
    query:    str,
    graph:    KnowledgeGraph,
    registry: AgentRegistry,
    language: LanguageAgent,
    memory:   MemoryAgent,
    dialogue: DialogueAgent,
    pattern:  PatternAgent,
    spawn:    SpawnAgent,
    analogy:  AnalogyAgent,
    response: ResponseAgent,
    search:   SearchAgent,
) -> None:
    """
    Context pipeline — каждый агент получает dict и возвращает обогащённый dict.
    """
    ctx: dict = {"query": query}

    # 1. Разбор языка
    ctx = language.process(ctx) or ctx
    console.print(
        f"\n[dim]lang={ctx.get('language')} | "
        f"intent={ctx.get('intent')} | "
        f"tokens={ctx.get('meaningful')}[/dim]"
    )

    # 2. Память
    ctx = memory.process(ctx) or ctx

    # 3. Диалог (кореференция, диалоговые акты)
    ctx = dialogue.process(ctx) or ctx

    # 4. Поиск в графе знаний
    graph_results = []
    search_tokens = ctx.get("meaningful", [])

    if ctx.get("is_context_request") and not search_tokens:
        for entry in ctx.get("memory_context", []):
            search_tokens.extend(entry.get("keywords", []))

    for token in search_tokens:
        found = graph.find(token)
        if found:
            graph_results.append(found)
            for rel in found.get("relations", [])[:3]:
                graph.activate(rel["from"], rel["to"], rel["relation"], delta=0.02)

    ctx["graph_results"] = graph_results

    # 5. Паттерны
    ctx = pattern.process(ctx) or ctx

    # 6. Спаун новых агентов
    ctx = spawn.process(ctx) or ctx
    if ctx.get("spawned"):
        console.print(f"[green]✓ Новые агенты: {ctx['spawned']}[/green]")

    # 7. Активация LearnedAgent-ов
    agent_hints = []
    for agent in registry.get_active():
        if agent.id.startswith("agent_") and agent.agent_type.value == "learned":
            if agent.can_handle(ctx):
                extra = agent.activate(ctx)
                if extra and isinstance(extra, dict) and "hint" in extra:
                    agent_hints.append(extra["hint"])
    ctx["agent_hints"] = agent_hints

    # 8. Аналогии
    ctx = analogy.process(ctx) or ctx
    analogies = ctx.get("analogies", [])

    # 9. Проверка наличия настоящих концептов
    has_concepts = any("concept" in r for r in graph_results)

    # 10. Поиск в Wikipedia, если граф не знает
    if not has_concepts:
        ctx = search.process(ctx) or ctx
        for item in ctx.get("search_results", []):
            word        = item["word"]
            explanation = item["explanation"]
            lang        = item.get("language", "ru")
            console.print(Panel(
                explanation,
                title=f"[cyan]Wikipedia: {word}[/cyan]",
                border_style="cyan",
            ))
            add_concept_to_graph(word, explanation, graph)
            # Сразу добавляем найденный концепт в результаты
            found = graph.find(word)
            if found:
                graph_results.append(found)
            # Рекурсивное обогащение
            search.enrich(word, explanation, graph, add_concept_to_graph, console,
                          depth=2, language=lang)
        ctx["graph_results"] = graph_results
        # Пересчитываем наличие концептов после добавления
        has_concepts = any("concept" in r for r in graph_results)

    # 11. Если всё ещё нет — спрашиваем пользователя
    if not has_concepts and not ctx.get("search_results"):
        for word in ctx.get("meaningful", []):
            if len(word) > 2 and not graph.find(word):
                console.print(
                    f"[yellow]Что такое '{word}'? (Enter — пропустить)[/yellow]"
                )
                explanation = input("  Объясни: ").strip()
                if explanation:
                    add_concept_to_graph(word, explanation, graph)
                    found = graph.find(word)
                    if found:
                        graph_results.append(found)
        ctx["graph_results"] = graph_results
        has_concepts = any("concept" in r for r in graph_results)

    # 12. Строим ответ
    ctx = response.process(ctx) or ctx
    answer = ctx.get("answer", "Не знаю.")

    # Добавляем аналогии, если они есть
    if analogies:
        analogy_lines = []
        for a in analogies:
            analogy_lines.append(f"По аналогии: {a['source']} → {a['target']} ({a['relation']})")
        answer += "\n\n" + "\n".join(analogy_lines)

    # Добавляем хинты от новых агентов, если нет концептов
    if agent_hints and not has_concepts:
        hints_text = "\n".join(agent_hints)
        answer = f"{answer}\n\n[dim](Подсказки от новых агентов: {hints_text})[/dim]"

    console.print(Panel(answer, title="[bold cyan]PROMETEUS[/bold cyan]", border_style="cyan"))

    # 13. Запоминаем ответ
    memory.remember_agent_response(answer, ctx.get("language", "ru"))

    # 14. История
    history = [e.text for e in memory.get_context(last_n=3)]
    console.print(f"[dim]История: {history}[/dim]")


def main() -> None:
    console.print(Panel(
        "[bold cyan]PROMETEUS AGI[/bold cyan]\n"
        "v0.8 — Диалог · Аналогии · Только SQLite · Hebbian learning",
        border_style="cyan",
    ))

    graph    = KnowledgeGraph(db_path=DB_PATH)
    registry = AgentRegistry(db_path=DB_PATH)

    language = LanguageAgent()
    memory   = MemoryAgent(conn=graph.conn)
    dialogue = DialogueAgent()
    pattern  = PatternAgent(conn=graph.conn)
    spawn    = SpawnAgent(registry=registry)
    analogy  = AnalogyAgent(conn=graph.conn)
    response = ResponseAgent()
    search   = SearchAgent()

    factory = AgentFactory()

    for agent in [language, memory, dialogue, pattern, spawn, analogy, response, search]:
        registry.register(agent)

    restored = registry.load_all(factory)
    if restored:
        console.print(f"[dim]Восстановлено из БД: {restored} агентов[/dim]")

    s = registry.stats()
    console.print(
        f"[dim]Реестр: {s['total']} агентов | "
        f"active={s['by_state']['active']} | "
        f"sleeping={s['by_state']['sleeping']}[/dim]\n"
    )

    def shutdown(sig=None, frame=None) -> None:
        console.print("\n[yellow]Завершение...[/yellow]")
        memory.flush()
        pattern.flush()
        registry.sync()
        registry.cleanup_dead()
        registry.close()
        graph.close()
        console.print("[green]Сохранено. До свидания.[/green]")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    console.print("[bold]Введите запрос (или 'выход')[/bold]")
    query_count = 0

    while True:
        try:
            query = input("\n> ").strip()
        except EOFError:
            shutdown()

        if query.lower() in {"выход", "exit", "quit"}:
            shutdown()

        if not query:
            continue

        process_query(
            query, graph, registry,
            language, memory, dialogue, pattern, spawn, analogy, response, search,
        )

        query_count += 1
        if query_count % SYNC_EVERY == 0:
            registry.sync()
            registry.cleanup_dead()


if __name__ == "__main__":
    main()