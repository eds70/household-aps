# backend/app/api/v1/advisor.py
"""
API для Advisor — подсказки планировщика и оценка исполнимости.

Итерация 2.
Итерация 7: cooling_degradation_factor + приоритет БД над in-memory.
Итерация 8: cz_status, cz_marked_qty, planned_qty + cz_completion_threshold.
Итерация 11 (Шаг 5): чтение настроек через settings_reader (app_settings).
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
from app.scheduler.settings_reader import (
    read_settings_dict,
    read_float,
)
from .models import (
    AdvisorResponse,
    AdvisorTipModel,
    FeasibilityResponse,
    FeasibilityIssueModel,
)

router = APIRouter(prefix="/api/v1/schedule", tags=["Advisor"])


async def _load_schedule_from_db(
        db: AsyncSession,
        org_id: UUID,
) -> Optional[dict]:
    """
    Загружает задачи последней активной версии из БД.
    Возвращает dict вида {"tasks": [...], "version_id": "..."} или None.

    Итерация 8: добавлены cz_status, cz_marked_qty, planned_qty
    для подсказки CZ_INCOMPLETE.
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
                st.task_role, st.status,
                ot.name AS operation_name,
                eq.name AS equipment_name,
                b.cz_status, b.cz_marked_qty,
                gp.bottle_volume_l,
                b.volume_kg
            FROM scheduled_task st
            LEFT JOIN operation_template ot ON ot.id = st.operation_template_id
            LEFT JOIN equipment eq ON eq.id = st.equipment_id
            LEFT JOIN batch b ON b.id = st.batch_id
            LEFT JOIN production_order po ON po.id = b.order_id
            LEFT JOIN product gp ON gp.id = po.product_id
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

        # Итерация 8: считаем плановое количество бутылок по партии
        planned_qty = None
        if row.volume_kg is not None and row.bottle_volume_l is not None:
            try:
                bottle_vol = float(row.bottle_volume_l)
                if bottle_vol > 0:
                    planned_qty = float(row.volume_kg) / bottle_vol
            except (ValueError, TypeError):
                planned_qty = None

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
            # Итерация 8
            "role": row.task_role,
            "task_role": row.task_role,
            "status": row.status,
            "cz_status": row.cz_status,
            "cz_marked_qty": float(row.cz_marked_qty) if row.cz_marked_qty else 0.0,
            "planned_qty": planned_qty,
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
    """
    Возвращает подсказки Advisor'а.

    Итерация 11 (Шаг 5): настройки читаются из app_settings.
    """
    loader = DataLoader(org_id=org_id)
    data = await loader.load_all()

    flags = FeatureFlags(data.get("org_settings", {}))

    # ==========================================
    # Итерация 11 (Шаг 5): читаем настройки из app_settings.
    # ==========================================
    settings = await read_settings_dict(
        db, org_id,
        keys=[
            "max_fill_percent",
            "cooling_degradation_factor",
            "cz_completion_threshold",
        ],
    )

    max_fill = read_float(settings.get("max_fill_percent"), 0.70)
    cooling_factor = read_float(
        settings.get("cooling_degradation_factor"), 1.3
    )
    cz_threshold = read_float(
        settings.get("cz_completion_threshold"), 0.95
    )

    # ==========================================
    # Итерация 7 (fix): приоритет БД над in-memory.
    # ==========================================
    schedule_result = await _load_schedule_from_db(db, org_id)

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
        cz_completion_threshold=cz_threshold,     # Итерация 8
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