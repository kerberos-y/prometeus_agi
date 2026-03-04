"""
agents/language.py — РОУТЕР ЯЗЫКОВОГО МОДУЛЯ  v3.2
====================================================
Загружает ОДИН языковой модуль из lang/ по переменной окружения.
Язык фиксирован для устройства — детекция не нужна.

Никаких языков внутри этого файла.

Установка языка:
    .env      : PROMETEUS_LANG=ru
    Linux/Mac : export PROMETEUS_LANG=ru
    Windows   : set PROMETEUS_LANG=ru

Поля, добавляемые в context:
    language      str        — язык устройства (= PROMETEUS_LANG)
    tokens        list[str]  — сырые токены
    stems         list[str]  — стемы параллельно tokens
    meaningful    list[str]  — значимые стемы (без стоп-слов, дедуп)
    intent        str        — question / command / greeting / statement
    is_question   bool
"""

from __future__ import annotations

import importlib
import logging
import os
from enum import Enum
from types import ModuleType

from core.agent import ReflexAgent

logger = logging.getLogger("prometeus.language")


# ══════════════════════════════════════════════════════════════════
# ЗАГРУЗКА ЯЗЫКОВОГО МОДУЛЯ
# ══════════════════════════════════════════════════════════════════

def _load_lang_module(lang_code: str) -> ModuleType:
    try:
        module = importlib.import_module(f"lang.{lang_code}")
        logger.info("Языковой модуль загружен: lang/%s.py", lang_code)
        return module
    except ModuleNotFoundError:
        raise RuntimeError(
            f"\n"
            f"  Языковой модуль '{lang_code}' не найден.\n"
            f"  Скачай нужный релиз: prometeus-{lang_code}-vX.X.zip\n"
            f"  Или измени переменную: export PROMETEUS_LANG=ru\n"
            f"  Доступные модули смотри в папке lang/\n"
        )


_LANG_CODE = os.environ.get("PROMETEUS_LANG", "ru").lower().strip()
_lang      = _load_lang_module(_LANG_CODE)

_LANG = _lang.LANG_CODE


# ══════════════════════════════════════════════════════════════════
# ТИПЫ
# ══════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    QUESTION  = "question"
    COMMAND   = "command"
    GREETING  = "greeting"
    STATEMENT = "statement"


# ══════════════════════════════════════════════════════════════════
# АГЕНТ
# ══════════════════════════════════════════════════════════════════

class LanguageAgent(ReflexAgent):
    """
    Роутер: токенизирует и стеммирует текст через загруженный lang-модуль.
    Один файл агента — один язык на устройстве.
    """

    def __init__(self) -> None:
        super().__init__("agent_language")
        logger.info("LanguageAgent готов | модуль=lang/%s.py", _LANG_CODE)

    def process(self, context: dict) -> dict | None:
        text: str = context.get("query", "")
        if not text:
            return None

        has_question_mark = "?" in text

        # 1. Токенизация
        tokens = _lang.tokenize(text)
        if not tokens:
            return None

        # 2. Стемминг
        stems = [_lang.stem(t) for t in tokens]

        # 3. Значимые стемы — без стоп-слов, длина > 2
        # Проверяем и токен, и стем: стоп-слово может изменить форму при стемминге
        stop = _lang.STOP_WORDS
        meaningful_raw = [
            stem_val
            for token, stem_val in zip(tokens, stems)
            if token     not in stop
            and stem_val not in stop
            and len(stem_val) > 2
        ]

        # 4. Дедупликация с сохранением порядка
        seen: set[str] = set()
        meaningful: list[str] = []
        for s in meaningful_raw:
            if s not in seen:
                seen.add(s)
                meaningful.append(s)

        # 5. Intent — по сырым токенам
        token_set = set(tokens)
        if token_set & _lang.GREETING_MARKERS:
            intent = Intent.GREETING
        elif token_set & _lang.QUESTION_MARKERS or has_question_mark:
            intent = Intent.QUESTION
        elif token_set & _lang.COMMAND_MARKERS:
            intent = Intent.COMMAND
        else:
            intent = Intent.STATEMENT

        logger.debug("lang=%s intent=%s tokens=%d meaningful=%s",
                     _LANG, intent.value, len(tokens), meaningful)

        return {
            **context,
            "language"   : _LANG,
            "tokens"     : tokens,
            "stems"      : stems,
            "meaningful" : meaningful,
            "intent"     : intent.value,
            "is_question": intent == Intent.QUESTION,
        }