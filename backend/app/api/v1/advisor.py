# backend/app/api/v1/advisor.py
"""
API для Advisor — подсказки планировщика и оценка исполнимости.

Итерация 2.
Итерация 7: cooling_degradation_factor + приоритет БД над in-memory.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.advisor import analyze as advisor_analyze
from app.scheduler.data_loader import DataLoader
from app.scheduler.feasibility import check_feasibility
from app.scheduler.feature_flags import FeatureFlags
from .models import (
    AdvisorResponse,
    AdvisorTipModel,
    FeasibilityResponse,
    FeasibilityIssueModel,
)

router = APIRouter(prefix="/api/v1/schedule", tags=["Advisor"])


def _read_float_setting(org_settings: dict, key: str, default: float) -> float:
    """Читает float из org_settings (JSONB-строка или число)."""
    raw = org_settings.get(key)
    if raw is None:
        return default
    try:
        if isinstance(raw, str):
            return float(raw.strip().strip('"').strip("'"))
        return float(raw)
    except (ValueError, TypeError):
        return default


async def _load_schedule_from_db(
        db: AsyncSession,
        org_id: UUID,
) -> Optional[dict]:
    """
    Загружает задачи последней активной версии из БД.
    Возвращает dict вида {"tasks": [...], "version_id": "..."} или None.
    """
    version_result = await db.execute(
        text("""
            SELECT id, name FROM schedule_version
            WHERE organization_id = :org_id AND is_active = TRUE
            ORDER BY created_at DESC LIMIT 1
        """),
        {"org_id": org_id},
    )
    v_row = version_result.fetchone()
    if not v_row:
        return None

    tasks_result = await db.execute(
        text("""
            SELECT
                st.id, st.batch_id,
                st.planned_start, st.planned_end,
                st.operator_pool, st.cooling_mode,
                ot.name AS operation_name,
                eq.name AS equipment_name
            FROM scheduled_task st
            LEFT JOIN operation_template ot ON ot.id = st.operation_template_id
            LEFT JOIN equipment eq ON eq.id = st.equipment_id
            WHERE st.organization_id = :org_id
              AND st.schedule_version_id = :version_id
        """),
        {"org_id": org_id, "version_id": v_row.id},
    )

    tasks = []
    for row in tasks_result.fetchall():
        duration = 0
        if row.planned_start and row.planned_end:
            duration = int((row.planned_end - row.planned_start).total_seconds() / 60)

        tasks.append({
            "id": str(row.id),
            "batch_id": str(row.batch_id) if row.batch_id else None,
            "operation_name": row.operation_name or "Операция",
            "equipment_name": row.equipment_name or "Unknown",
            "equipment_id": str(row.id),
            "start": row.planned_start,
            "end": row.planned_end,
            "duration": duration,
            "operator_pool": row.operator_pool,
            "cooling_mode": row.cooling_mode,
        })

    return {
        "tasks": tasks,
        "version_id": str(v_row.id),
        "version_name": v_row.name,
    }


@router.get("/advice", response_model=AdvisorResponse)
async def get_advice(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает подсказки Advisor'а."""
    loader = DataLoader(org_id=org_id)
    data = await loader.load_all()

    flags = FeatureFlags(data.get("org_settings", {}))

    max_fill = _read_float_setting(data["org_settings"], "max_fill_percent", 0.70)
    cooling_factor = _read_float_setting(
        data["org_settings"], "cooling_degradation_factor", 1.3
    )

    # ==========================================
    # Итерация 7 (fix): приоритет БД над in-memory.
    # ==========================================
    # In-memory `_last_schedule_result` может быть устаревшим
    # (например, если cooling_mode обновили в БД напрямую).
    # Сначала читаем актуальный active version из БД.
    schedule_result = await _load_schedule_from_db(db, org_id)

    # Fallback: если БД пуста — берём из памяти
    if not schedule_result:
        from .schedule import _last_schedule_result
        schedule_result = _last_schedule_result if _last_schedule_result else None

    result = advisor_analyze(
        batches=data["batches"],
        products_map=data["products"],
        equipment_map=data["equipment"],
        equipment_links=data["equipment_links"],
        recipes=data["recipes"],
        materials=data["materials"],
        material_stocks=data["material_stocks"],
        material_supplies=data["material_supplies"],
        schedule_result=schedule_result,
        max_fill_percent=max_fill,
        cooling_degradation_factor=cooling_factor,
        enable_material_constraints=flags.enable_material_constraints,
        enable_advisor=flags.enable_advisor,
    )

    return AdvisorResponse(
        tips=[
            AdvisorTipModel(
                code=t.code,
                severity=t.severity,
                title=t.title,
                message=t.message,
                details=t.details,
            )
            for t in result.tips
        ],
        critical_count=result.critical_count,
        warning_count=result.warning_count,
        info_count=result.info_count,
        generated_at=datetime.now(),
    )


@router.post("/feasibility", response_model=FeasibilityResponse)
async def check_plan_feasibility(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Проверяет исполнимость текущего плана."""
    loader = DataLoader(org_id=org_id)
    data = await loader.load_all()

    result = check_feasibility(
        batches=data["batches"],
        recipes=data["recipes"],
        materials=data["materials"],
        material_stocks=data["material_stocks"],
        material_supplies=data["material_supplies"],
    )

    return FeasibilityResponse(
        feasible=result.feasible,
        issues=[
            FeasibilityIssueModel(
                code=i.code, severity=i.severity, message=i.message, details=i.details
            )
            for i in result.issues
        ],
        warnings=[
            FeasibilityIssueModel(
                code=i.code, severity=i.severity, message=i.message, details=i.details
            )
            for i in result.warnings
        ],
    )