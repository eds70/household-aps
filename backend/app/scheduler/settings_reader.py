# backend/app/scheduler/settings_reader.py
"""
Единая точка чтения настроек из app_settings или plan_settings.

Итерация 11 (Шаг 5): замена прямых SQL-запросов к organization_settings
на централизованное чтение через этот модуль.

Итерация 13.14: добавлен параметр version_id во все функции.
  - Если version_id задан — читаем из plan_settings этого плана.
  - Если version_id не задан или для плана нет записей — из app_settings (fallback).

Использование:
    from app.scheduler.settings_reader import (
        read_feature_flags,
        read_setting,
        read_settings_dict,
    )

    # Глобальные настройки (обратная совместимость)
    flags = await read_feature_flags(db, org_id)

    # Настройки конкретного плана
    flags = await read_feature_flags(db, org_id, version_id=vid)
"""

import logging
from typing import Any, Dict, List, Optional
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
        version_id: Optional[UUID] = None,
) -> FeatureFlags:
    """
    Читает все feature-флаги (enable_*) из plan_settings или app_settings.

    Один SQL-запрос вместо N отдельных.

    Args:
        db: Сессия БД.
        org_id: UUID организации.
        version_id: если задан — читаем из plan_settings этого плана.
                    Если None или для плана нет записей — из app_settings.

    Returns:
        FeatureFlags с прочитанными значениями.
        Отсутствующие флаги берутся из DEFAULTS в FeatureFlags.
    """
    if version_id is not None:
        result = await db.execute(
            text("""
                SELECT setting_key, setting_value
                FROM plan_settings
                WHERE organization_id = :org_id
                  AND schedule_version_id = :version_id
                  AND setting_key LIKE 'enable_%'
            """),
            {"org_id": org_id, "version_id": version_id},
        )
        settings_dict = {
            row.setting_key: row.setting_value
            for row in result.fetchall()
        }
        if settings_dict:
            return FeatureFlags(settings_dict)

        # Fallback: у плана нет plan_settings (старый план) → app_settings
        log_with_context(
            logger, logging.WARNING,
            f"plan_settings пусты для {str(version_id)[:8]} — "
            f"feature-флаги читаются из app_settings",
            stage="settings_reader", org_id=str(org_id),
        )

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
        version_id: Optional[UUID] = None,
) -> Any:
    """
    Читает одну настройку из plan_settings (если version_id) или app_settings.

    Args:
        db: Сессия БД.
        org_id: UUID организации.
        key: Ключ настройки (например, 'cz_completion_threshold').
        default: Значение по умолчанию, если настройка не найдена.
        version_id: если задан — читаем из plan_settings этого плана.

    Returns:
        Значение настройки или default.
    """
    if version_id is not None:
        result = await db.execute(
            text("""
                SELECT setting_value
                FROM plan_settings
                WHERE organization_id = :org_id
                  AND schedule_version_id = :version_id
                  AND setting_key = :key
            """),
            {"org_id": org_id, "version_id": version_id, "key": key},
        )
        row = result.fetchone()
        if row is not None:
            return row.setting_value

    # Fallback на app_settings
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
        version_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Читает несколько настроек за один SQL-запрос.

    Args:
        db: Сессия БД.
        org_id: UUID организации.
        keys: Список ключей настроек.
        version_id: если задан — читаем из plan_settings этого плана.

    Returns:
        Словарь {setting_key: setting_value}.
        Отсутствующие ключи не попадают в результат.
    """
    if not keys:
        return {}

    if version_id is not None:
        result = await db.execute(
            text("""
                SELECT setting_key, setting_value
                FROM plan_settings
                WHERE organization_id = :org_id
                  AND schedule_version_id = :version_id
                  AND setting_key = ANY(:keys)
            """),
            {"org_id": org_id, "version_id": version_id, "keys": keys},
        )
        settings = {
            row.setting_key: row.setting_value
            for row in result.fetchall()
        }
        if settings:
            return settings

    # Fallback на app_settings
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


# ==========================================
# ВНУТРЕННИЙ ХЕЛПЕР (для логирования)
# ==========================================

def log_with_context(
        logger_obj,
        level: int,
        message: str,
        stage: Optional[str] = None,
        org_id: Optional[str] = None,
        **extra,
) -> None:
    """Обёртка для логирования с контекстом (импортируется локально)."""
    from .logging_config import log_with_context as _lwc
    _lwc(logger_obj, level, message, stage=stage, org_id=org_id, **extra)