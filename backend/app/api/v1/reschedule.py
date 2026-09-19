# backend/app/api/v1/reschedule.py
"""
API перепланирования (Итерация 4).

Эндпоинты:
  POST /api/v1/schedule/reschedule        — перепланировать
  GET  /api/v1/schedule/compare           — сравнить две версии
  PUT  /api/v1/schedule/task/{id}/pin     — закрепить/открепить задачу
  PUT  /api/v1/schedule/task/{id}/move    — переместить задачу (C2)

Итерация 11 (Шаг 5): чтение флага enable_rescheduling через settings_reader.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.rescheduler import Rescheduler
from app.scheduler.settings_reader import read_feature_flags
from .reschedule_models import (
    RescheduleRequest,
    RescheduleResponse,
    CompareResponse,
    MovedTaskInfo,
    PinTaskRequest,
    PinTaskResponse,
    MoveTaskRequest,
    MoveTaskResponse,
)

router = APIRouter(prefix="/api/v1/schedule", tags=["Перепланирование"])
logger = setup_scheduler_logging(level=logging.INFO)


async def _check_rescheduling_enabled(db: AsyncSession, org_id: UUID) -> None:
    """
    Проверяет feature-флаг enable_rescheduling.

    Итерация 11 (Шаг 5): читает из app_settings через settings_reader.
    """
    flags = await read_feature_flags(db, org_id)
    if not flags.enable_rescheduling:
        raise HTTPException(
            status_code=400,
            detail="Перепланирование отключено (enable_rescheduling = false)",
        )


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


# ==========================================
# MOVE TASK (Итерация 9, C2: drag-and-drop)
# ==========================================

@router.put("/task/{task_id}/move", response_model=MoveTaskResponse)
async def move_task(
        task_id: UUID,
        request: MoveTaskRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Перемещает задачу на новое время (drag-and-drop на Ганте).

    Логика:
      1. Валидирует существование задачи.
      2. Проверяет new_end > new_start.
      3. Проверяет, что длительность не изменилась.
      4. Обновляет planned_start, planned_end.
      5. Ставит is_pinned = TRUE (пользователь явно зафиксировал).
      6. Возвращает обновлённую задачу.

    Не пересчитывает остальной план. Для этого — POST /schedule/reschedule.
    """
    await _check_rescheduling_enabled(db, org_id)

    # 1. Проверяем, что задача существует и принадлежит орг
    check = await db.execute(
        text("""
            SELECT id, planned_start, planned_end, is_pinned
            FROM scheduled_task
            WHERE id = :task_id AND organization_id = :org_id
        """),
        {"task_id": task_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # 2. Валидация времени
    if request.new_end <= request.new_start:
        raise HTTPException(
            status_code=400,
            detail="new_end должен быть позже new_start",
        )

    # 3. Проверка длительности
    original_duration = (row.planned_end - row.planned_start).total_seconds()
    new_duration = (request.new_end - request.new_start).total_seconds()

    if abs(new_duration - original_duration) > 60:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Длительность задачи не должна меняться при перемещении. "
                f"Было: {int(original_duration / 60)} мин, "
                f"стало: {int(new_duration / 60)} мин."
            ),
        )

    # 4. Обновляем
    result = await db.execute(
        text("""
            UPDATE scheduled_task
            SET planned_start = :new_start,
                planned_end = :new_end,
                is_pinned = TRUE
            WHERE id = :task_id AND organization_id = :org_id
            RETURNING id, planned_start, planned_end, is_pinned
        """),
        {
            "task_id": task_id,
            "org_id": org_id,
            "new_start": request.new_start,
            "new_end": request.new_end,
        },
    )
    updated = result.fetchone()
    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"C2: задача {str(task_id)[:8]} перемещена: "
        f"{row.planned_start} → {request.new_start}",
        stage="move_task", org_id=str(org_id),
    )

    return MoveTaskResponse(
        task_id=str(updated.id),
        planned_start=updated.planned_start,
        planned_end=updated.planned_end,
        is_pinned=bool(updated.is_pinned),
        message="Задача перемещена и закреплена (is_pinned=TRUE)",
    )