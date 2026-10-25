# backend/app/api/v1/advisor.py
"""
API для Advisor — подсказки планировщика и оценка исполнимости.

Итерация 32 (fix #advisor-persistence):
  - Добавлено сохранение сдвигов (shifted_details) и заблокированных
    партий в таблицу advisor_note при первом запросе.
  - Добавлено восстановление этих данных из БД, если в памяти
    (_last_schedule_result) их нет (например, при просмотре истории).

Итерация 47 (fix #advisor-deadlock):
  - Временно ОТКЛЮЧЕНО сохранение заметок в БД (advisor_note),
    так как при одновременных запросах возникают дедлоки.
    Advisor теперь работает только в памяти.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
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
        version_id: Optional[UUID] = None,
) -> Optional[dict]:
    """Загружает задачи активной или указанной версии из БД."""
    if version_id is not None:
        version_result = await db.execute(
            text("""
                SELECT id, name, created_at FROM schedule_version
                WHERE id = :vid AND organization_id = :org_id
            """),
            {"vid": version_id, "org_id": org_id},
        )
    else:
        version_result = await db.execute(
            text("""
                SELECT id, name, created_at FROM schedule_version
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
        "version_created_at": v_row.created_at,
    }


async def _persist_advisor_notes(
        db: AsyncSession,
        org_id: UUID,
        version_id: UUID,
        tips: List[Any],
) -> None:
    """
    ВРЕМЕННО ОТКЛЮЧЕНО (вызывает дедлоки).
    Оставлено для обратной совместимости, но не вызывается.
    """
    pass


async def _load_advisor_notes_from_db(
        db: AsyncSession,
        org_id: UUID,
        version_id: UUID,
) -> Optional[Dict[str, Any]]:
    """
    Читает сохранённые advisor_note для версии.
    Возвращает {'postprocess_result': ..., 'skipped_batches': ...}
    или None, если записей нет.
    """
    res = await db.execute(
        text("""
            SELECT code, details
            FROM advisor_note
            WHERE schedule_version_id = :vid AND organization_id = :org_id
              AND code IN ('SHIFTED_TASKS', 'SKIPPED_BATCHES', 'OVERLAPS_AFTER', 'DEPENDENCY_VIOLATIONS')
        """),
        {"vid": version_id, "org_id": org_id},
    )
    rows = res.fetchall()
    if not rows:
        return None

    postprocess_result = {
        "shifted_tasks": 0,
        "overlaps_after": 0,
        "dependency_violations": 0,
        "shifted_details": [],
    }
    skipped_batches = []

    for r in rows:
        code = r.code
        details = r.details or {}

        if code == 'SHIFTED_TASKS':
            postprocess_result["shifted_tasks"] = details.get("shifted_count", 0)
            postprocess_result["shifted_details"] = details.get("sample", [])
        elif code == 'OVERLAPS_AFTER':
            postprocess_result["overlaps_after"] = details.get("overlaps_after", 0)
        elif code == 'DEPENDENCY_VIOLATIONS':
            postprocess_result["dependency_violations"] = details.get("dependency_violations", 0)
        elif code == 'SKIPPED_BATCHES':
            if details.get("batch_id"):
                skipped_batches.append({
                    "batch_id": details["batch_id"],
                    "reason": details.get("reason", "Неизвестно"),
                    "lab_status": details.get("lab_status"),
                    "product_id": details.get("product_id"),
                    "equipment_id": details.get("equipment_id"),
                })

    return {
        "postprocess_result": postprocess_result,
        "skipped_batches": skipped_batches,
    }


@router.get("/advice", response_model=AdvisorResponse)
async def get_advice(
        version_id: Optional[UUID] = Query(
            default=None,
            description="ID плана. Если не задан — активный.",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает подсказки Advisor'а (без сохранения в БД).
    """
    loader = DataLoader(org_id=org_id, version_id=version_id)
    data = await loader.load_all()

    flags = FeatureFlags(data.get("org_settings", {}))

    settings = await read_settings_dict(
        db, org_id,
        keys=[
            "max_fill_percent",
            "cooling_degradation_factor",
            "cz_completion_threshold",
        ],
        version_id=version_id,
    )

    max_fill = read_float(settings.get("max_fill_percent"), 0.70)
    cooling_factor = read_float(
        settings.get("cooling_degradation_factor"), 1.3
    )
    cz_threshold = read_float(
        settings.get("cz_completion_threshold"), 0.95
    )

    schedule_result = await _load_schedule_from_db(db, org_id, version_id)

    postprocess_result: Optional[Dict[str, Any]] = None
    skipped_batches: Optional[List[Dict[str, Any]]] = None
    horizon_minutes: int = 30 * 24 * 60

    # 1. Пытаемся взять из памяти (если только что строили)
    from .schedule import _last_schedule_result
    if _last_schedule_result and schedule_result and (
            str(_last_schedule_result.get("version_id")) ==
            schedule_result.get("version_id")
    ):
        postprocess_result = _last_schedule_result.get("postprocess_result")
        skipped_batches = _last_schedule_result.get("skipped_batches")

    # 2. Если в памяти нет — читаем из БД (advisor_note)
    if schedule_result and (not postprocess_result or not skipped_batches):
        db_notes = await _load_advisor_notes_from_db(
            db, org_id, UUID(schedule_result["version_id"])
        )
        if db_notes:
            if not postprocess_result:
                postprocess_result = db_notes["postprocess_result"]
            if not skipped_batches:
                skipped_batches = db_notes["skipped_batches"]

    if not schedule_result:
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
        cz_completion_threshold=cz_threshold,
        enable_material_constraints=flags.enable_material_constraints,
        enable_advisor=flags.enable_advisor,
        postprocess_result=postprocess_result,
        skipped_batches=skipped_batches,
        horizon_minutes=horizon_minutes,
    )

    # ==========================================
    # ВРЕМЕННО ОТКЛЮЧЕНО: сохранение заметок в БД
    # (вызывает дедлоки при одновременных запросах)
    # ==========================================
    # if schedule_result and schedule_result.get("version_id"):
    #     try:
    #         vid = UUID(schedule_result["version_id"])
    #         await _persist_advisor_notes(db, org_id, vid, result.tips)
    #     except Exception as e:
    #         import logging
    #         logging.getLogger(__name__).warning(
    #             f"[advisor] не удалось сохранить заметки: {e}"
    #         )
    #         await db.rollback()

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


@router.get("/advisor-notes")
async def get_advisor_notes(
        version_id: Optional[UUID] = Query(
            default=None,
            description="ID плана. Если не задан — активный.",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает сохранённые AdvisorNotes для указанной версии.
    """
    if version_id is None:
        v_res = await db.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE organization_id = :org_id AND is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """),
            {"org_id": org_id},
        )
        row = v_res.fetchone()
        if not row:
            return {"version_id": None, "notes": []}
        version_id = row.id

    res = await db.execute(
        text("""
            SELECT id, severity, code, title, message, details, created_at
            FROM advisor_note
            WHERE schedule_version_id = :vid AND organization_id = :org_id
            ORDER BY
                CASE severity
                    WHEN 'CRITICAL' THEN 0
                    WHEN 'WARNING' THEN 1
                    ELSE 2
                END,
                created_at DESC
        """),
        {"vid": version_id, "org_id": org_id},
    )

    notes = []
    for r in res.fetchall():
        notes.append({
            "id": str(r.id),
            "severity": r.severity,
            "code": r.code,
            "title": r.title,
            "message": r.message,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "version_id": str(version_id),
        "notes": notes,
        "total": len(notes),
    }


@router.post("/feasibility", response_model=FeasibilityResponse)
async def check_plan_feasibility(
        version_id: Optional[UUID] = Query(
            default=None,
            description="ID плана. Если не задан — активный.",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Проверяет исполнимость текущего плана."""
    loader = DataLoader(org_id=org_id, version_id=version_id)
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