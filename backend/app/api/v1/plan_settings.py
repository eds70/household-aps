# backend/app/api/v1/plan_settings.py
"""
API мастера настроек плана (Итерация 13.14).

Эндпоинты:
  GET  /api/v1/plan-settings/version/{version_id}       — настройки плана
  PUT  /api/v1/plan-settings/version/{version_id}       — массовое обновление
  POST /api/v1/plan-settings/version/{version_id}/reset — сброс к глобальным

Итерация 13.14.1: PUT принимает опциональные метаданные плана
    (name, comment, version_type) и обновляет schedule_version.

Логика:
  - plan_settings — снапшот настроек для конкретного плана.
  - schedule_version — метаданные плана (name, comment, version_type).
  - PUT обновляет оба, если переданы соответствующие поля.
"""
import json as _json
import logging
from typing import Any, Dict, Optional
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

VALID_VERSION_TYPES = {"MONTHLY", "SHIFT", "WHAT_IF"}


# ==========================================
# Модели
# ==========================================

class PlanSettingsUpdateRequest(BaseModel):
    """
    Массовое обновление plan_settings + опционально метаданные плана.

    Если переданы name / comment / version_type — обновляется schedule_version.
    """
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь {setting_key: new_value}. Может быть пустым.",
    )
    # --- Итерация 13.14.1: метаданные плана ---
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Новое имя плана",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Новый комментарий",
    )
    version_type: Optional[str] = Field(
        default=None,
        description="Новый тип плана: MONTHLY | SHIFT | WHAT_IF",
    )


# ==========================================
# Проверки
# ==========================================

def _check_edit_role(current_user: dict) -> None:
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
    Возвращает настройки плана + метаданные schedule_version.
    """
    await _assert_version_exists(db, version_id, org_id)

    # Метаданные плана
    version_result = await db.execute(
        text("""
            SELECT name, comment, version_type
            FROM schedule_version
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": org_id},
    )
    v_row = version_result.fetchone()
    metadata = {
        "name": v_row.name if v_row else None,
        "comment": v_row.comment if v_row else None,
        "version_type": v_row.version_type if v_row else None,
    }

    # Настройки плана
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
        "metadata": metadata,
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
    Обновляет настройки плана + опционально метаданные schedule_version.

    Валидация настроек — через validate_setting.
    Системные настройки (is_system=TRUE) не обновляются.
    """
    _check_edit_role(current_user)
    await _assert_version_exists(db, version_id, org_id)

    # ==========================================
    # 1. Обновляем метаданные schedule_version (если переданы)
    # ==========================================
    metadata_updates: Dict[str, Any] = {}

    if payload.name is not None:
        metadata_updates["name"] = payload.name.strip()

    if payload.comment is not None:
        metadata_updates["comment"] = payload.comment

    if payload.version_type is not None:
        if payload.version_type not in VALID_VERSION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый version_type: {payload.version_type}. "
                       f"Допустимые: {sorted(VALID_VERSION_TYPES)}",
            )
        metadata_updates["version_type"] = payload.version_type

    if metadata_updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in metadata_updates.keys())
        params = {
            **metadata_updates,
            "vid": version_id,
            "org_id": org_id,
        }
        await db.execute(
            text(f"""
                UPDATE schedule_version
                SET {set_clause}
                WHERE id = :vid AND organization_id = :org_id
            """),
            params,
        )
        logger.info(
            f"[plan_settings] метаданные обновлены для {str(version_id)[:8]}: "
            f"{list(metadata_updates.keys())}"
        )

    # ==========================================
    # 2. Обновляем plan_settings (если переданы)
    # ==========================================
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

    return {
        "status": "success",
        "version_id": str(version_id),
        "metadata_updated": list(metadata_updates.keys()),
        "settings_updated_count": len(updated),
        "settings_updated": list(updated.keys()),
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
    Метаданные schedule_version НЕ трогает.
    """
    _check_edit_role(current_user)
    await _assert_version_exists(db, version_id, org_id)

    delete_result = await db.execute(
        text("""
            DELETE FROM plan_settings
            WHERE organization_id = :org_id AND schedule_version_id = :vid
        """),
        {"org_id": org_id, "vid": version_id},
    )
    deleted = delete_result.rowcount or 0

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

    return {
        "status": "success",
        "version_id": str(version_id),
        "deleted": deleted,
        "message": "Настройки плана сброшены к глобальным",
    }