# backend/app/scheduler/settings_reader.py
"""
Единая точка чтения настроек из app_settings.

Итерация 11 (Шаг 5): замена прямых SQL-запросов к organization_settings
на централизованное чтение через этот модуль.

Преимущества:
  - Один SQL-запрос вместо N разных по коду.
  - Единый источник правды — app_settings.
  - Легко тестировать (можно замокать).
  - Легко мигрировать (если завтра перейдём на Redis — правим один файл).

Использование:
    from app.scheduler.settings_reader import (
        read_feature_flags,
        read_setting,
        read_settings_dict,
    )

    flags = await read_feature_flags(db, org_id)
    if flags.enable_cz_integration:
        ...
"""

import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .feature_flags import FeatureFlags
from .logging_config import setup_scheduler_logging

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ЧТЕНИЕ FEATURE-ФЛАГОВ
# ==========================================

async def read_feature_flags(
        db: AsyncSession,
        org_id: UUID,
) -> FeatureFlags:
    """
    Читает все feature-флаги (enable_*) из app_settings.

    Один SQL-запрос вместо N отдельных.

    Args:
        db: Сессия БД.
        org_id: UUID организации.

    Returns:
        FeatureFlags с прочитанными значениями.
        Отсутствующие флаги берутся из DEFAULTS в FeatureFlags.
    """
    result = await db.execute(
        text("""
            SELECT setting_key, setting_value
            FROM app_settings
            WHERE organization_id = :org_id
              AND setting_key LIKE 'enable_%'
        """),
        {"org_id": org_id},
    )
    settings_dict = {
        row.setting_key: row.setting_value
        for row in result.fetchall()
    }
    return FeatureFlags(settings_dict)


# ==========================================
# ЧТЕНИЕ ОДНОЙ НАСТРОЙКИ
# ==========================================

async def read_setting(
        db: AsyncSession,
        org_id: UUID,
        key: str,
        default: Any = None,
) -> Any:
    """
    Читает одну настройку из app_settings.

    Args:
        db: Сессия БД.
        org_id: UUID организации.
        key: Ключ настройки (например, 'cz_completion_threshold').
        default: Значение по умолчанию, если настройка не найдена.

    Returns:
        Значение настройки или default.
    """
    result = await db.execute(
        text("""
            SELECT setting_value
            FROM app_settings
            WHERE organization_id = :org_id
              AND setting_key = :key
        """),
        {"org_id": org_id, "key": key},
    )
    row = result.fetchone()
    if row is None:
        return default
    return row.setting_value


# ==========================================
# ЧТЕНИЕ НЕСКОЛЬКИХ НАСТРОЕК
# ==========================================

async def read_settings_dict(
        db: AsyncSession,
        org_id: UUID,
        keys: List[str],
) -> Dict[str, Any]:
    """
    Читает несколько настроек за один SQL-запрос.

    Args:
        db: Сессия БД.
        org_id: UUID организации.
        keys: Список ключей настроек.

    Returns:
        Словарь {setting_key: setting_value}.
        Отсутствующие ключи не попадают в результат.
    """
    if not keys:
        return {}

    result = await db.execute(
        text("""
            SELECT setting_key, setting_value
            FROM app_settings
            WHERE organization_id = :org_id
              AND setting_key = ANY(:keys)
        """),
        {"org_id": org_id, "keys": keys},
    )
    return {
        row.setting_key: row.setting_value
        for row in result.fetchall()
    }


# ==========================================
# УТИЛИТЫ ЧТЕНИЯ ТИПОВ
# ==========================================

def read_float(raw: Any, default: float) -> float:
    """
    Читает float из JSONB-значения.

    Обрабатывает: число, строку в кавычках, строку без кавычек.
    Возвращает default при любой ошибке.
    """
    if raw is None:
        return default
    try:
        if isinstance(raw, str):
            return float(raw.strip().strip('"').strip("'"))
        return float(raw)
    except (ValueError, TypeError):
        return default


def read_str(raw: Any, default: str) -> str:
    """Читает строку из JSONB-значения."""
    if raw is None:
        return default
    if isinstance(raw, str):
        return raw.strip().strip('"').strip("'")
    return str(raw)


def read_bool(raw: Any, default: bool = False) -> bool:
    """Читает bool из JSONB-значения."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(raw, (int, float)):
        return bool(raw)
    return default