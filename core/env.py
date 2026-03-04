"""
core/env.py — Минимальный парсер .env
======================================
Stdlib only. Никаких зависимостей.
Размер: ~1 KB. RAM: < 0.1 MB.

Загружает .env в os.environ при старте.
Вызывать один раз в самом начале main.py — до всех импортов агентов.

Формат .env:
    PROMETEUS_LANG=ru
    PROMETEUS_DEVICE=iot
    # Это комментарий
    DB_PATH=knowledge/graph.db
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    """
    Читает .env файл и загружает переменные в os.environ.
    Существующие переменные окружения НЕ перезаписывает —
    системные переменные имеют приоритет над .env.

    Поддерживает:
        KEY=value
        KEY="value with spaces"
        KEY='value with spaces'
        # комментарии
        пустые строки
    """
    env_path = Path(path)
    if not env_path.exists():
        return  # нет .env — молча пропускаем, это нормально

    with env_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Пропускаем пустые строки и комментарии
            if not line or line.startswith("#"):
                continue

            # Разбиваем по первому =
            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip()

            # Убираем кавычки если есть
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]

            # Не перезаписываем если уже задано в системе
            if key and key not in os.environ:
                os.environ[key] = value