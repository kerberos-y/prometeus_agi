"""
agent_search — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
==========================================
Поиск в Wikipedia API когда граф знаний не знает ответа.
Поддерживает несколько языков через subdomain API.
Обогащает граф новыми концептами рекурсивно.
"""

from __future__ import annotations

import urllib.request
import urllib.parse
import json
import re

from core.agent import ReflexAgent


# Маппинг языков → Wikipedia subdomain
_WIKI_LANG: dict[str, str] = {
    "ru": "ru", "uk": "uk", "en": "en",
    "de": "de", "fr": "fr", "es": "es",
    "it": "it", "pt": "pt", "pl": "pl",
    "zh": "zh", "ar": "ar",
}

_USER_AGENT = "PROMETEUS/0.3 (educational; offline-ai-project)"

# Признаки нерелевантных статей
_SKIP_KEYWORDS = [
    "кинофильм","фильм","деревня","село","город","альбом","песня",
    "округ","район","провинци","уезд","may refer","может означать",
    "disambiguation","значения","film","municipality","commune",
]

# Суффиксы грамматических форм — не концепты
_BAD_SUFFIXES = [
    "ого","ему","ому","ых","ими","ами","ей","ства","ению","ания",
    "ения","ости","ьных","ьные","ьной","ьного",
]


class SearchAgent(ReflexAgent):

    def __init__(self) -> None:
        super().__init__("agent_search")
        self._online_cache: bool | None = None  # кэш статуса сети

    # ── process() — интерфейс агента ──────────────────────────────

    def process(self, context: dict) -> dict | None:
        """
        Запускается когда graph_results пуст и is_online().
        Ищет значимые токены в Wikipedia.
        Добавляет context["search_results"] — список найденных объяснений.
        """
        results  = context.get("graph_results", [])
        language = context.get("language", "ru")
        meaningful = context.get("meaningful", [])

        if results or not meaningful:
            return context  # граф уже ответил — не ищем

        if not self.is_online():
            return {**context, "search_results": []}

        found = []
        for word in meaningful:
            if len(word) <= 2:
                continue
            explanation = self.search(word, language)
            if explanation:
                found.append({"word": word, "explanation": explanation, "language": language})

        return {**context, "search_results": found}

    # ── Публичный API ─────────────────────────────────────────────

    def is_online(self) -> bool:
        """Проверяет доступность сети (с кэшем на сессию)."""
        if self._online_cache is not None:
            return self._online_cache
        try:
            req = urllib.request.Request(
                "https://en.wikipedia.org",
                headers={"User-Agent": _USER_AGENT},
            )
            urllib.request.urlopen(req, timeout=3)
            self._online_cache = True
        except Exception:
            self._online_cache = False
        return self._online_cache

    def search(self, word: str, language: str = "ru") -> str | None:
        """
        Ищет слово в Wikipedia на нужном языке.
        Возвращает краткое объяснение или None.
        """
        lang = _WIKI_LANG.get(language, "en")
        try:
            encoded = urllib.parse.quote(word)
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("type") == "disambiguation":
                return None

            extract = data.get("extract", "")
            if any(kw in extract.lower() for kw in _SKIP_KEYWORDS):
                return None

            if extract:
                sentences = extract.split(".")
                return ". ".join(s.strip() for s in sentences[:2] if s.strip()) + "."

        except Exception:
            pass

        # Фолбэк: если не нашли на языке запроса — пробуем английский
        if language != "en":
            return self.search(word, "en")
        return None

    def enrich(
        self,
        word:       str,
        explanation: str,
        graph,                  # KnowledgeGraph
        persist_fn,             # callable(word, explanation, graph)
        console,
        depth:   int = 2,
        visited: set | None = None,
        language: str = "ru",
    ) -> None:
        """
        Рекурсивно обогащает граф связанными концептами.
        depth=2 по умолчанию (PDF: глубокое обогащение).
        """
        if visited is None:
            visited = set()
        if depth == 0 or word in visited:
            return

        visited.add(word)
        unknown = self._extract_unknown(explanation, graph)

        if unknown:
            console.print(f"[dim]Глубина {depth} — изучаю: {unknown[:5]}[/dim]")

        for token in unknown:
            if token in visited:
                continue
            result = self.search(token, language)
            if result:
                console.print(f"[dim]  → '{token}': {result[:80]}...[/dim]")
                graph.add_concept(token)
                for t in result.lower().split():
                    clean = re.sub(r"[^\w]", "", t)
                    if graph.find(clean) and clean != token:
                        graph.add_relation(token, clean, "СВЯЗАН_С", weight=0.6)
                persist_fn(token, result, graph)
                self.enrich(token, result, graph, persist_fn, console,
                            depth - 1, visited, language)

    # ── Внутренние ────────────────────────────────────────────────

    def _extract_unknown(self, explanation: str, graph) -> list[str]:
        """Находит слова из объяснения которых нет в графе."""
        unknown = []
        for token in explanation.lower().split():
            clean = re.sub(r"[^\w]", "", token)
            if (
                clean
                and len(clean) > 4
                and clean.isalpha()
                and not graph.find(clean)
                and not any(clean.endswith(s) for s in _BAD_SUFFIXES)
            ):
                unknown.append(clean)
        return list(set(unknown))