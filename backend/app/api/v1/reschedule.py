# backend/app/api/v1/reschedule.py
"""
API перепланирования (Итерация 4).

Эндпоинты:
  POST /api/v1/schedule/reschedule        — перепланировать
  GET  /api/v1/schedule/compare           — сравнить две версии
  PUT  /api/v1/schedule/task/{id}/pin     — закрепить/открепить задачу
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from typing import List
from uuid import UUID
import logging

from .reschedule_models import (
    RescheduleRequest,
    RescheduleResponse,
    CompareResponse,
    MovedTaskInfo,
    PinTaskRequest,
    PinTaskResponse,
)
from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.feature_flags import FeatureFlags
from app.scheduler.rescheduler import Rescheduler
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context


router = APIRouter(prefix="/api/v1/schedule", tags=["Перепланирование"])
logger = setup_scheduler_logging(level=logging.INFO)


async def _check_rescheduling_enabled(db: AsyncSession, org_id: UUID) -> None:
    """Проверяет feature-флаг enable_rescheduling."""
    result = await db.execute(
        text("""
            SELECT setting_value FROM organization_settings
            WHERE organization_id = :org_id AND setting_key = 'enable_rescheduling'
        """),
        {"org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Feature enable_rescheduling не настроен")

    flags = FeatureFlags({"enable_rescheduling": row.setting_value})
    if not flags.enable_rescheduling:
        raise HTTPException(status_code=400, detail="Перепланирование отключено (enable_rescheduling = false)")


@router.post("/reschedule", response_model=RescheduleResponse)
async def reschedule(
        request: RescheduleRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Перепланировать с учётом изменений.

    Типы изменений (reason):
      - DELAY: задержка операции.
        changes = {delayed_task_id: UUID}
      - BREAKDOWN: поломка оборудования.
        changes = {broken_equipment_id: UUID, breakdown_start: ISO, breakdown_end: ISO}
      - QTY_CHANGE: изменение объёма заказа.
        changes = {affected_batch_ids: [UUID, ...]}
      - MANUAL: ручное изменение.
        changes = {affected_batch_ids: [UUID, ...]}
    """
    await _check_rescheduling_enabled(db, org_id)

    rescheduler = Rescheduler(org_id=org_id)

    try:
        result = await rescheduler.reschedule(
            from_version_id=request.from_version_id,
            reason=request.reason,
            changes=request.changes,
            frozen_before=request.frozen_before,
            comment=request.comment,
        )
    except Exception as e:
        log_with_context(
            logger, logging.ERROR,
            f"Ошибка перепланирования: {e}",
            stage="reschedule", org_id=str(org_id),
        )
        raise HTTPException(status_code=500, detail=f"Ошибка перепланирования: {str(e)}")

    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)

    return RescheduleResponse(
        status=result.status,
        from_version_id=result.from_version_id,
        to_version_id=result.to_version_id,
        affected_tasks=result.affected_tasks,
        moved_tasks=result.moved_tasks,
        frozen_tasks=result.frozen_tasks,
        message=result.message,
        diff=result.diff,
    )


@router.get("/compare", response_model=CompareResponse)
async def compare_versions(
        v1: UUID = Query(..., description="ID первой версии"),
        v2: UUID = Query(..., description="ID второй версии"),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Сравнить две версии плана."""
    rescheduler = Rescheduler(org_id=org_id)

    result = await rescheduler.compare_versions(v1_id=v1, v2_id=v2)

    return CompareResponse(
        v1_id=result["v1_id"],
        v2_id=result["v2_id"],
        v1_task_count=result["v1_task_count"],
        v2_task_count=result["v2_task_count"],
        only_in_v1=result["only_in_v1"],
        only_in_v2=result["only_in_v2"],
        moved=[
            MovedTaskInfo(
                task_id=m["task_id"],
                batch_id=m.get("batch_id"),
                old_start=m["old_start"],
                old_end=m["old_end"],
                new_start=m["new_start"],
                new_end=m["new_end"],
                delta_minutes=m["delta_minutes"],
            )
            for m in result["moved"]
        ],
        unchanged_count=result["unchanged_count"],
        moved_count=result["moved_count"],
    )


@router.put("/task/{task_id}/pin", response_model=PinTaskResponse)
async def pin_task(
        task_id: UUID,
        request: PinTaskRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Закрепить или открепить задачу (не будет двигаться при перепланировании)."""
    await _check_rescheduling_enabled(db, org_id)

    result = await db.execute(
        text("""
            UPDATE scheduled_task
            SET is_pinned = :is_pinned
            WHERE id = :task_id AND organization_id = :org_id
            RETURNING id, is_pinned
        """),
        {"task_id": task_id, "org_id": org_id, "is_pinned": request.is_pinned},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await db.commit()

    return PinTaskResponse(
        task_id=str(row.id),
        is_pinned=bool(row.is_pinned),
        message="Задача закреплена" if row.is_pinned else "Задача откреплена",
    )