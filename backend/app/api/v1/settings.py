# backend/app/api/v1/settings.py
"""
API для централизованных настроек приложения (Итерация 11).

Эндпоинты:
  GET  /api/v1/settings/schema             — реестр настроек (метаданные)
  GET  /api/v1/settings/categories         — список категорий
  GET  /api/v1/settings                    — все настройки
  GET  /api/v1/settings/category/{cat}     — настройки категории
  PUT  /api/v1/settings                    — массовое обновление
  PUT  /api/v1/settings/{key}              — обновление одной
  POST /api/v1/settings/shift-mode         — смена режима смен
                                              (+ пересоздание смен в БД)

Итерация 11 (Шаг 4): POST /shift-mode теперь пересоздаёт смены
через shift_regenerator.regenerate_shifts.
"""

import json
import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from app.scheduler.settings import (
    get_all_settings,
    get_categories,
    get_category_settings,
    get_settings_schema,
    update_setting,
    update_settings_bulk,
    CATEGORY_LABELS,
)
from app.scheduler.shift_regenerator import (
    get_intervals_for_mode,
    regenerate_shifts,
)

router = APIRouter(prefix="/api/v1/settings", tags=["Настройки"])
logger = logging.getLogger("app.api.settings")


# ==========================================
# Модели
# ==========================================

class SettingsUpdateRequest(BaseModel):
    """Массовое обновление настроек."""
    settings: Dict[str, Any] = Field(
        ...,
        description="Словарь {setting_key: new_value}",
    )


class SettingSingleUpdateRequest(BaseModel):
    """Обновление одной настройки."""
    value: Any = Field(..., description="Новое значение")


class ShiftModeRequest(BaseModel):
    """Смена режима смен."""
    shift_mode: str = Field(
        ...,
        description="Режим: 1x8 | 3x8 | 2x12",
    )


# ==========================================
# Вспомогательные
# ==========================================

EDIT_ALLOWED_ROLES = {"ADMIN", "PLANNER"}


def _check_edit_role(current_user: dict) -> None:
    role = current_user.get("role")
    if role not in EDIT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: {sorted(EDIT_ALLOWED_ROLES)}",
        )


# ==========================================
# GET /schema — реестр настроек
# ==========================================

@router.get("/schema")
async def get_schema():
    """Полный реестр настроек с метаданными."""
    return {
        "categories": get_categories(),
        "settings": get_settings_schema(),
    }


# ==========================================
# GET /categories — категории
# ==========================================

@router.get("/categories")
async def get_categories_endpoint():
    """Список категорий с человекочитаемыми названиями."""
    return get_categories()


# ==========================================
# GET / — все настройки
# ==========================================

@router.get("/")
async def get_all(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Все настройки организации."""
    return await get_all_settings(db, org_id)


# ==========================================
# GET /category/{category} — настройки категории
# ==========================================

@router.get("/category/{category}")
async def get_category(
        category: str,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Настройки одной категории."""
    if category not in CATEGORY_LABELS:
        raise HTTPException(
            status_code=404,
            detail=f"Категория '{category}' не найдена",
        )
    return await get_category_settings(db, org_id, category)


# ==========================================
# PUT / — массовое обновление
# ==========================================

@router.put("/")
async def update_all(
        request: SettingsUpdateRequest,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Массовое обновление настроек."""
    _check_edit_role(current_user)

    try:
        updated = await update_settings_bulk(db, org_id, request.settings)
        return {
            "status": "success",
            "updated": updated,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# PUT /{key} — обновление одной настройки
# ==========================================

@router.put("/{key}")
async def update_single(
        key: str,
        request: SettingSingleUpdateRequest,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновление одной настройки."""
    _check_edit_role(current_user)

    try:
        new_value = await update_setting(db, org_id, key, request.value)
        return {
            "status": "success",
            "key": key,
            "value": new_value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# POST /shift-mode — смена режима смен + пересоздание
# ==========================================

@router.post("/shift-mode")
async def change_shift_mode(
        request: ShiftModeRequest,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Смена режима смен с пересозданием смен в БД.

    Доступно только ADMIN.

    Логика:
      1. Валидация режима.
      2. Обновление настроек (shift_mode, shift_intervals,
         shift_duration_hours, work_start_time, work_end_time).
      3. Пересоздание смен в таблице shift (Итерация 11, Шаг 4).
      4. Сброс shift_id в задачах (старые UUID невалидны).

    ВАЖНО: после смены режима нужно пересчитать план.
    """
    # 1. Проверка прав
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён. Требуется роль ADMIN",
        )

    # 2. Валидация режима
    mode = request.shift_mode
    if mode not in ("1x8", "3x8", "2x12"):
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый режим: {mode}. Допустимые: 1x8, 3x8, 2x12",
        )

    # 3. Определяем интервалы
    intervals, duration_hours = get_intervals_for_mode(mode)

    # 4. Обновляем пользовательские настройки
    await update_setting(db, org_id, "shift_mode", mode)
    await update_setting(
        db, org_id, "work_start_time", intervals[0]["start"]
    )
    await update_setting(
        db, org_id, "work_end_time", intervals[-1]["end"]
    )

    # 5. Обновляем системные настройки (напрямую, минуя валидацию)
    await db.execute(
        text("""
            UPDATE app_settings
            SET setting_value = CAST(:value AS jsonb),
                updated_at = NOW()
            WHERE organization_id = :org_id
              AND setting_key = 'shift_intervals'
        """),
        {"org_id": org_id, "value": json.dumps(intervals)},
    )
    await db.execute(
        text("""
            UPDATE app_settings
            SET setting_value = CAST(:value AS jsonb),
                updated_at = NOW()
            WHERE organization_id = :org_id
              AND setting_key = 'shift_duration_hours'
        """),
        {"org_id": org_id, "value": str(duration_hours)},
    )
    await db.commit()

    logger.info(
        f"[shift-mode] org={str(org_id)[:8]} mode={mode} "
        f"intervals={intervals} duration={duration_hours}h"
    )

    # ==========================================
    # 6. ПЕРЕСОЗДАНИЕ СМЕН (Итерация 11, Шаг 4)
    # ==========================================
    try:
        regen_stats = await regenerate_shifts(
            session=db,
            org_id=org_id,
            mode=mode,
            reset_shift_ids=True,
        )
    except Exception as e:
        logger.error(
            f"[shift-mode] Ошибка пересоздания смен: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Настройки обновлены, но пересоздание смен "
                   f"завершилось ошибкой: {e}",
        )

    return {
        "status": "success",
        "shift_mode": mode,
        "shift_intervals": intervals,
        "shift_duration_hours": duration_hours,
        "regenerated": regen_stats,
        "message": (
            f"Режим изменён на «{mode}». "
            f"Пересоздано смен: {regen_stats['created']}, "
            f"сброшено привязок к сменам: {regen_stats['reset_shift_ids']}. "
            f"Рекомендуется пересчитать план на вкладке «Планирование»."
        ),
    }