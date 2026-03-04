"""
lang/en.py — Языковой модуль: ENGLISH
======================================
Автономный файл. Никаких зависимостей кроме stdlib.
RAM: < 0.3 MB. Размер: ~7 KB.

Исправления:
  - Стеммер не режет слова длиной ≤ 5 символов (atom→atom, а не tom)
  - Вопросительные слова добавлены в STOP_WORDS (when→не попадает в граф)
  - Командные глаголы добавлены в STOP_WORDS (show, tell и т.д.)
"""

from __future__ import annotations
import re

# ══════════════════════════════════════════════════════════════════
# ИДЕНТИФИКАЦИЯ МОДУЛЯ
# ══════════════════════════════════════════════════════════════════

LANG_CODE = "en"
SCRIPT    = "latin"

FINGERPRINTS: frozenset[str] = frozenset({
    "the", "is", "are", "a", "an", "and", "of",
    "to", "in", "it", "i", "you", "that", "was", "for",
})


# ══════════════════════════════════════════════════════════════════
# ТОКЕНИЗАТОР
# ══════════════════════════════════════════════════════════════════

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

def tokenize(text: str) -> list[str]:
    """Убирает пунктуацию, lowercase, возвращает список токенов."""
    cleaned = re.sub(r"\s+", " ", _PUNCT.sub(" ", text.lower())).strip()
    return cleaned.split()


# ══════════════════════════════════════════════════════════════════
# СТЕММЕР — Porter lite
#
# ИСПРАВЛЕНИЕ: min_len=6 — слова короче 6 символов не стеммируются.
# Без этого "atom"(4) → "at", "ions"(4) → "i" и т.д.
# Порог 6 выбран по аналогии с русским модулем: большинство значимых
# английских корней имеют длину ≥ 4, и стемминг коротких слов
# даёт больше вреда, чем пользы.
# ══════════════════════════════════════════════════════════════════

_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("ational", "ate"), ("tional",  "tion"), ("enci",  "ence"),
    ("anci",    "ance"), ("izer",   "ize"),  ("ising", "ise"),
    ("izing",   "ize"),  ("alism",  "al"),   ("ation", "ate"),
    ("iness",   "i"),    ("fulness","ful"),  ("ousness","ous"),
    ("iveness", "ive"),  ("ication","ify"),  ("ness",  ""),
    ("ment",    ""),     ("ful",    ""),     ("ous",   ""),
    ("ive",     ""),     ("ize",    ""),     ("ise",   ""),
    ("ing",     ""),     ("tion",   ""),     ("sion",  ""),
    ("ed",      ""),     ("er",     ""),     ("est",   ""),
    ("ly",      ""),     ("es",     ""),     ("s",     ""),
)

# Минимальная длина слова для стемминга.
# Слова короче — возвращаем как есть.
_STEM_MIN_LEN = 6


def stem(word: str) -> str:
    """
    Porter-lite стеммер для английского.
    Слова короче _STEM_MIN_LEN символов возвращаются без изменений.

    Примеры:
        computers   → comput      (9 симв → стеммируем)
        atom        → atom        (4 симв → не трогаем)
        ions        → ions        (4 симв → не трогаем)
        quantum     → quantum     (7 симв → стеммируем, нет суффикса)
        defining    → defin       (8 симв → стеммируем)
    """
    w = word.lower().strip()

    # Короткие слова не стеммируем — они и так в нормальной форме
    if len(w) < _STEM_MIN_LEN:
        return w

    for suffix, replacement in _SUFFIXES:
        if w.endswith(suffix):
            candidate = w[: len(w) - len(suffix)] + replacement
            if len(candidate) >= 3:
                return candidate

    # Защита: если стем получился короче 3 — возвращаем оригинал
    return w


# ══════════════════════════════════════════════════════════════════
# СТОП-СЛОВА
#
# ИСПРАВЛЕНИЕ: добавлены вопросительные слова и командные глаголы.
# Они не являются концептами и не должны попадать в граф.
# ══════════════════════════════════════════════════════════════════

STOP_WORDS: frozenset[str] = frozenset({
    # Артикли и предлоги
    "the", "a", "an", "in", "on", "at", "to", "of", "for",
    "with", "from", "by", "as", "into", "about", "up", "out",
    "over", "under", "between", "through", "after", "before",
    # Союзы и частицы
    "and", "or", "but", "so", "if", "not", "no", "nor",
    # Вспомогательные глаголы
    "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    # Местоимения
    "it", "this", "that", "i", "you", "he", "she", "they", "we",
    "me", "him", "her", "them", "us", "my", "your", "his", "its",
    "our", "their", "these", "those",
    # Вопросительные — не концепты, не должны идти в граф
    "what", "who", "where", "when", "how", "why",
    "which", "whose", "whom",
    # Прочее
    "show",    "tell",    "explain",  "describe",  # команды — не концепты
})


# ══════════════════════════════════════════════════════════════════
# МАРКЕРЫ INTENT
# ══════════════════════════════════════════════════════════════════

QUESTION_MARKERS: frozenset[str] = frozenset({
    "what", "who", "where", "when", "how", "why",
    "which", "whose", "whom",
})

COMMAND_MARKERS: frozenset[str] = frozenset({
    "show",     "find",    "open",    "run",      "start",
    "stop",     "create",  "delete",  "send",     "tell",
    "explain",  "help",    "give",    "write",    "get",
    "list",     "make",    "display", "calculate","compute",
    "translate","compare", "check",   "define",   "add",
})

GREETING_MARKERS: frozenset[str] = frozenset({
    "hi", "hello", "hey", "greetings", "howdy",
})


# ══════════════════════════════════════════════════════════════════
# ДИАЛОГ — используется agent_dialogue и agent_response
# ══════════════════════════════════════════════════════════════════

PRONOUNS: frozenset[str] = frozenset({
    "he", "she", "it", "they", "this", "that", "these", "those",
})

DIALOGUE_ACTS: dict[str, frozenset[str]] = {
    "greeting": frozenset({"hi", "hello", "hey", "greetings", "howdy"}),
    "thanks":   frozenset({"thanks", "thank", "thank you", "thx"}),
    "goodbye":  frozenset({"bye", "goodbye", "see you", "farewell"}),
    "clarify":  frozenset({"elaborate", "explain more", "more details", "go on"}),
}

RESPONSES: dict[str, str] = {
    "no_answer": "I don't know about this. Can you explain?",
    "greeting":  "Hello! How can I help?",
    "thanks":    "You're welcome!",
    "goodbye":   "Goodbye!",
    "clarify":   "Let me clarify...",
}