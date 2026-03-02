"""
agent_language — УРОВЕНЬ 1, БАЗОВЫЙ РЕФЛЕКС
============================================
Задача: токенизация, определение языка, намерение.
НЕ хранит состояние. НЕ работает с контекстом (это agent_memory).
Возвращает dict совместимый с context{} в process_query().
"""

from __future__ import annotations

import re
from enum import Enum
from core.agent import ReflexAgent


# ── Типы ──────────────────────────────────────────────────────────

class Intent(str, Enum):
    QUESTION  = "question"
    COMMAND   = "command"
    STATEMENT = "statement"


# ── Определение языка (без зависимостей) ──────────────────────────

_FINGERPRINTS: dict[str, set[str]] = {
    "ru": {"и","в","не","на","что","с","как","это","по","но","из","он","я","а","то","за"},
    "uk": {"і","в","не","на","що","з","як","це","по","але","він","я","та","від","до"},
    "en": {"the","is","are","a","an","and","of","to","in","it","i","you","that","was","for"},
    "de": {"die","der","das","ist","und","in","ich","du","nicht","ein","eine","hat","mit"},
    "fr": {"le","la","les","est","et","un","une","je","tu","pas","que","de","il","elle"},
    "es": {"el","la","los","es","y","un","una","yo","no","que","de","en","por","con"},
    "it": {"il","la","è","e","un","una","io","non","che","di","in","per","con","si"},
    "zh": set(), "ar": set(),
}

_CYRILLIC_LANGS = ["ru", "uk"]
_LATIN_LANGS    = ["en", "de", "fr", "es", "it"]

def _detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    # Определяем скрипт по большинству символов
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    arabic   = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    chinese  = sum(1 for c in text if "\u4E00" <= c <= "\u9FFF")
    if arabic  > 3: return "ar"
    if chinese > 3: return "zh"

    candidates = _CYRILLIC_LANGS if cyrillic > 3 else _LATIN_LANGS
    words = set(text.lower().split())
    best, best_score = ("ru" if cyrillic > 3 else "en"), 0
    for lang in candidates:
        score = len(words & _FINGERPRINTS[lang])
        if score > best_score:
            best_score, best = score, lang
    return best


# ── Стоп-слова ────────────────────────────────────────────────────

_STOP: dict[str, set[str]] = {
    "ru": {"и","в","на","с","а","но","же","ли","бы","до","по","за","из","от","не",
           "он","она","они","мы","вы","я","это","то","так","уже","при","без","для","или","к","о"},
    "uk": {"і","в","на","з","а","але","же","чи","б","до","по","за","від","не",
           "він","вона","вони","ми","ви","я","це","те","так","вже","при","без","для","або","к"},
    "en": {"the","a","an","and","or","but","in","on","at","to","of","for","with",
           "is","are","was","were","it","this","that","i","you","he","she","they","we","not","no"},
    "de": {"die","der","das","ein","eine","und","oder","aber","in","auf","an","zu","von",
           "mit","ist","sind","war","ich","du","er","sie","wir","es","nicht","so","als"},
    "fr": {"le","la","les","un","une","et","ou","mais","dans","sur","à","de","est",
           "sont","je","tu","il","elle","nous","vous","ce","ne","pas","se","me"},
    "es": {"el","la","los","las","un","una","y","o","pero","en","a","de","del","es",
           "son","yo","tú","no","se","me","te","por","con","para","le"},
    "it": {"il","la","i","le","un","una","e","o","ma","in","a","di","da","è",
           "sono","io","tu","non","si","mi","ti","per","con","che","gli"},
}

# ── Маркеры намерений ─────────────────────────────────────────────

_QUESTIONS: dict[str, set[str]] = {
    "ru": {"что","кто","где","когда","как","почему","зачем","сколько","какой","какая","какие","чем"},
    "uk": {"що","хто","де","коли","як","чому","навіщо","скільки","який","яка","які"},
    "en": {"what","who","where","when","how","why","which","whose","whom"},
    "de": {"was","wer","wo","wann","wie","warum","welche","welcher","welches"},
    "fr": {"quoi","qui","où","quand","comment","pourquoi","quel","quelle"},
    "es": {"qué","quién","dónde","cuándo","cómo","cuál","cuánto"},
    "it": {"cosa","chi","dove","quando","come","perché","quale","quanto"},
}

_COMMANDS: dict[str, set[str]] = {
    "ru": {"покажи","найди","открой","запусти","включи","выключи","сделай","создай",
           "удали","отправь","расскажи","объясни","помоги","дай","напиши","выведи"},
    "uk": {"покажи","знайди","відкрий","запусти","увімкни","вимкни","зроби",
           "створи","видали","надішли","розкажи","поясни","допоможи"},
    "en": {"show","find","open","run","start","stop","create","delete","send",
           "tell","explain","help","give","write","get","list","make","display"},
    "de": {"zeige","finde","öffne","starte","stoppe","erstelle","lösche",
           "sende","erkläre","hilf","gib","schreibe","mache"},
    "fr": {"montre","trouve","ouvre","lance","arrête","crée","supprime",
           "envoie","explique","aide","donne","écris"},
    "es": {"muestra","encuentra","abre","ejecuta","detén","crea","elimina",
           "envía","explica","ayuda","da","escribe"},
    "it": {"mostra","trova","apri","avvia","ferma","crea","elimina",
           "invia","spiega","aiuta","dai","scrivi"},
}

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


# ── Агент ─────────────────────────────────────────────────────────

class LanguageAgent(ReflexAgent):
    """Базовый рефлекс — токенизация и разбор структуры запроса."""

    def __init__(self) -> None:
        super().__init__("agent_language")

    def process(self, context: dict) -> dict | None:
        """
        context["query"] — сырой текст запроса.
        Возвращает обогащённый context с полями:
            normalized, language, tokens, meaningful, intent, is_question
        """
        text = context.get("query", "")
        if not text:
            return None

        has_question_mark = "?" in text
        normalized = re.sub(r"\s+", " ", _PUNCT.sub(" ", text.lower())).strip()
        language   = _detect_language(normalized)
        tokens     = normalized.split()
        stop       = _STOP.get(language, _STOP["en"])
        meaningful = [t for t in tokens if t not in stop and len(t) > 1]

        # Намерение — проверяем по токенам (не подстроке!)
        token_set  = set(tokens)
        q_markers  = _QUESTIONS.get(language, _QUESTIONS["en"])
        c_markers  = _COMMANDS.get(language, _COMMANDS["en"])

        if token_set & q_markers or has_question_mark:
            intent = Intent.QUESTION
        elif token_set & c_markers:
            intent = Intent.COMMAND
        else:
            intent = Intent.STATEMENT

        return {
            **context,
            "normalized":  normalized,
            "language":    language,
            "tokens":      tokens,
            "meaningful":  meaningful,
            "intent":      intent.value,
            "is_question": intent == Intent.QUESTION,
        }