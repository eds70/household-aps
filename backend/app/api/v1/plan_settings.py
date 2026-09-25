# backend/app/api/v1/plan_settings.py
"""
API мастера настроек плана (Итерация 13.14).

Эндпоинты:
  GET  /api/v1/plan-settings/version/{version_id}       — настройки плана
  PUT  /api/v1/plan-settings/version/{version_id}       — массовое обновление
  POST /api/v1/plan-settings/version/{version_id}/reset — сброс к глобальным

Логика:
  - plan_settings — снапшот настроек для конкретного плана.
  - При создании schedule_version триггер копирует app_settings.
  - Мастер позволяет переопределить эти настройки ДО построения плана.
  - Планировщик (ProductionScheduler) читает plan_settings, а не app_settings.
"""
import json as _json
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
    CATEGORY_LABELS,
    _SETTINGS_BY_KEY,
    validate_setting,
)

router = APIRouter(prefix="/api/v1/plan-settings", tags=["Настройки плана"])
logger = logging.getLogger("app.api.plan_settings")

EDIT_ALLOWED_ROLES = {"ADMIN", "PLANNER"}


# ==========================================
# Модели
# ==========================================

class PlanSettingsUpdateRequest(BaseModel):
    """Массовое обновление plan_settings."""
    settings: Dict[str, Any] = Field(
        ...,
        description="Словарь {setting_key: new_value}",
    )


# ==========================================
# Проверки
# ==========================================

def _check_edit_role(current_user: dict) -> None:
    """Только ADMIN и PLANNER могут менять настройки плана."""
    role = current_user.get("role")
    if role not in EDIT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: {sorted(EDIT_ALLOWED_ROLES)}",
        )


async def _assert_version_exists(
        db: AsyncSession,
        version_id: UUID,
        org_id: UUID,
) -> None:
    """Проверяет, что schedule_version существует и принадлежит организации."""
    result = await db.execute(
        text("""
            SELECT id FROM schedule_version
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": org_id},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=404,
            detail=f"План {version_id} не найден",
        )


# ==========================================
# GET /version/{version_id}
# ==========================================

@router.get("/version/{version_id}")
async def get_plan_settings(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает все plan_settings для конкретного плана.

    Если для плана нет записей (старый план до миграции) —
    возвращается пустой settings, а UI может показать fallback на app_settings.
    """
    await _assert_version_exists(db, version_id, org_id)

    result = await db.execute(
        text("""
            SELECT setting_key, setting_value, value_type, category,
                   label, description, min_value, max_value, options,
                   display_order, is_system
            FROM plan_settings
            WHERE organization_id = :org_id AND schedule_version_id = :vid
            ORDER BY category, display_order
        """),
        {"org_id": org_id, "vid": version_id},
    )

    items = []
    settings_dict: Dict[str, Any] = {}
    for row in result.fetchall():
        items.append({
            "key": row.setting_key,
            "value": row.setting_value,
            "value_type": row.value_type,
            "category": row.category,
            "label": row.label,
            "description": row.description,
            "min_value": float(row.min_value) if row.min_value is not None else None,
            "max_value": float(row.max_value) if row.max_value is not None else None,
            "options": row.options,
            "display_order": row.display_order,
            "is_system": row.is_system,
        })
        settings_dict[row.setting_key] = row.setting_value

    return {
        "version_id": str(version_id),
        "settings": settings_dict,
        "schema": items,
        "categories": [
            {"key": k, "label": v}
            for k, v in CATEGORY_LABELS.items()
        ],
    }


# ==========================================
# PUT /version/{version_id}
# ==========================================

@router.put("/version/{version_id}")
async def update_plan_settings(
        version_id: UUID,
        payload: PlanSettingsUpdateRequest,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Массовое обновление plan_settings.

    Валидирует значения через `validate_setting` из `settings.py`.
    Системные настройки (`is_system = TRUE`) не обновляются.
    """
    _check_edit_role(current_user)
    await _assert_version_exists(db, version_id, org_id)

    updated: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for key, value in payload.settings.items():
        spec = _SETTINGS_BY_KEY.get(key)
        if spec is None:
            errors[key] = f"Неизвестная настройка: {key}"
            continue
        if spec.is_system:
            errors[key] = "Системная настройка — изменить нельзя"
            continue

        try:
            validated = validate_setting(key, value)
        except ValueError as e:
            errors[key] = str(e)
            continue

        # Сериализация в JSONB
        if isinstance(validated, bool):
            serialized = "true" if validated else "false"
        elif isinstance(validated, str):
            serialized = _json.dumps(validated)
        elif isinstance(validated, (int, float)):
            serialized = str(validated)
        else:
            serialized = _json.dumps(validated)

        await db.execute(
            text("""
                INSERT INTO plan_settings
                    (organization_id, schedule_version_id, setting_key,
                     setting_value, value_type, category, label, description,
                     min_value, max_value, options, display_order, is_system,
                     updated_at)
                VALUES
                    (:org_id, :vid, :key, CAST(:value AS jsonb), :vtype, :cat,
                     :label, :desc, :minv, :maxv, CAST(:options AS jsonb),
                     :order, :sys, NOW())
                ON CONFLICT (schedule_version_id, setting_key) DO UPDATE
                    SET setting_value = EXCLUDED.setting_value,
                        updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "vid": version_id,
                "key": key,
                "value": serialized,
                "vtype": spec.value_type,
                "cat": spec.category,
                "label": spec.label,
                "desc": spec.description,
                "minv": spec.min_value,
                "maxv": spec.max_value,
                "options": _json.dumps(spec.options) if spec.options else None,
                "order": spec.display_order,
                "sys": spec.is_system,
            },
        )
        updated[key] = validated

    if errors:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ошибки валидации: {errors}",
        )

    await db.commit()

    logger.info(
        f"plan_settings обновлены для {str(version_id)[:8]}: "
        f"{list(updated.keys())}"
    )

    return {
        "status": "success",
        "version_id": str(version_id),
        "updated_count": len(updated),
        "updated": updated,
    }


# ==========================================
# POST /version/{version_id}/reset
# ==========================================

@router.post("/version/{version_id}/reset")
async def reset_plan_settings(
        version_id: UUID,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Сбрасывает plan_settings к глобальным app_settings.

    Полезно, если пользователь «переэкспериментировался» в мастере
    и хочет вернуться к дефолтным значениям.
    """
    _check_edit_role(current_user)
    await _assert_version_exists(db, version_id, org_id)

    # 1. Удаляем все plan_settings для этого плана
    delete_result = await db.execute(
        text("""
            DELETE FROM plan_settings
            WHERE organization_id = :org_id AND schedule_version_id = :vid
        """),
        {"org_id": org_id, "vid": version_id},
    )
    deleted = delete_result.rowcount or 0

    # 2. Копируем из app_settings
    await db.execute(
        text("""
            INSERT INTO plan_settings
                (organization_id, schedule_version_id, setting_key,
                 setting_value, value_type, category, label, description,
                 min_value, max_value, options, display_order, is_system)
            SELECT
                :org_id, :vid, s.setting_key, s.setting_value,
                s.value_type, s.category, s.label, s.description,
                s.min_value, s.max_value, s.options,
                s.display_order, COALESCE(s.is_system, FALSE)
            FROM app_settings s
            WHERE s.organization_id = :org_id
        """),
        {"org_id": org_id, "vid": version_id},
    )

    await db.commit()

    logger.info(
        f"plan_settings сброшены для {str(version_id)[:8]} "
        f"(удалено {deleted}, скопировано из app_settings)"
    )

    return {
        "status": "success",
        "version_id": str(version_id),
        "deleted": deleted,
        "message": "Настройки плана сброшены к глобальным",
    }