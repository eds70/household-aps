# backend/app/api/v1/shift.py
"""
API сменного планирования и РМ мастера (Итерация 3).

Эндпоинты:
  GET  /api/v1/shift/list                    — список смен (диапазон дат)
  GET  /api/v1/shift/by-date/{date}          — смены на конкретную дату
  GET  /api/v1/shift/{shift_id}/tasks        — задания смены по рабочим центрам
  GET  /api/v1/shift/{shift_id}/carryover    — переходящие задания
  POST /api/v1/shift/task/{task_id}/fact     — внести факт

Итерация 5: в задачи добавлены поля is_lab_blocked, lab_status, lab_block_reason.
Итерация 7: в задачи добавлено поле cooling_mode.
Итерация 11 (fix): сравнение по МСК-дате вместо UTC-даты.
Итерация 11 (Шаг 5): чтение флага enable_shift_planning через settings_reader.
"""

import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.settings_reader import read_feature_flags
from .shift_models import (
    ShiftResponse,
    ShiftTaskResponse,
    ShiftTasksGrouped,
    ShiftTasksResponse,
    TaskFactRequest,
    TaskFactResponse,
)

router = APIRouter(prefix="/api/v1/shift", tags=["Сменное планирование"])
logger = setup_scheduler_logging(level=logging.INFO)

# ==========================================
# Итерация 11 (fix): часовой пояс для сравнения дат.
# ==========================================
MSK_TZ = "Europe/Moscow"


async def _check_shift_planning_enabled(
        db: AsyncSession, org_id: UUID
) -> None:
    """
    Проверяет feature-флаг enable_shift_planning.

    Итерация 11 (Шаг 5): читает из app_settings через settings_reader.
    """
    flags = await read_feature_flags(db, org_id)
    if not flags.enable_shift_planning:
        raise HTTPException(
            status_code=400,
            detail="Сменное планирование отключено (enable_shift_planning = false)",
        )


# ==========================================
# Resolve version_id
# ==========================================

async def _resolve_version_id(
        db: AsyncSession,
        org_id: UUID,
        version_id: Optional[UUID],
) -> Optional[UUID]:
    """
    Определяет, какую версию плана использовать.

    Логика:
      1. Если version_id передан явно — используем его.
      2. Иначе — берём последнюю активную версию (is_active = TRUE).
      3. Если активных нет — берём просто последнюю по created_at.
      4. Если версий нет вообще — возвращаем None.
    """
    if version_id is not None:
        result = await db.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE id = :version_id AND organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": org_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Версия плана {version_id} не найдена",
            )
        return version_id

    result = await db.execute(
        text("""
            SELECT id FROM schedule_version
            WHERE organization_id = :org_id AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"org_id": org_id},
    )
    row = result.fetchone()
    if row:
        return row.id

    result = await db.execute(
        text("""
            SELECT id FROM schedule_version
            WHERE organization_id = :org_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"org_id": org_id},
    )
    row = result.fetchone()
    return row.id if row else None


# ==========================================
# СПИСОК СМЕН
# ==========================================

@router.get("/list", response_model=List[ShiftResponse])
async def list_shifts(
        date_from: Optional[date] = Query(default=None),
        date_to: Optional[date] = Query(default=None),
        only_working: bool = Query(default=False),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Список смен за период.

    Итерация 11 (fix): сравнение по МСК-дате через
    (starts_at AT TIME ZONE 'Europe/Moscow')::date.
    """
    await _check_shift_planning_enabled(db, org_id)

    if date_from is None:
        date_from = date(2026, 9, 1)
    if date_to is None:
        date_to = date(2026, 9, 30)

    where_clauses = ["organization_id = :org_id"]
    params = {
        "org_id": org_id,
        "date_from": date_from,
        "date_to": date_to,
    }

    if only_working:
        where_clauses.append("is_working = TRUE")

    query = text(f"""
        SELECT id, name, starts_at, ends_at, is_working, comment
        FROM shift
        WHERE {' AND '.join(where_clauses)}
          AND (starts_at AT TIME ZONE '{MSK_TZ}')::date >= :date_from
          AND (starts_at AT TIME ZONE '{MSK_TZ}')::date <= :date_to
        ORDER BY starts_at
    """)

    result = await db.execute(query, params)
    return [
        ShiftResponse(
            id=row.id,
            name=row.name,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            is_working=row.is_working,
            comment=row.comment,
        )
        for row in result.fetchall()
    ]


# ==========================================
# СМЕНЫ ПО ДАТЕ
# ==========================================

@router.get("/by-date/{shift_date}", response_model=List[ShiftResponse])
async def get_shifts_by_date(
        shift_date: date,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Все смены на конкретную дату (по МСК).

    Итерация 11 (fix): возвращает СПИСОК смен, а не одну.
    """
    await _check_shift_planning_enabled(db, org_id)

    result = await db.execute(
        text(f"""
            SELECT id, name, starts_at, ends_at, is_working, comment
            FROM shift
            WHERE organization_id = :org_id
              AND (starts_at AT TIME ZONE '{MSK_TZ}')::date = :shift_date
            ORDER BY starts_at
        """),
        {"org_id": org_id, "shift_date": shift_date},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Смены на {shift_date} не найдены",
        )

    return [
        ShiftResponse(
            id=row.id,
            name=row.name,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            is_working=row.is_working,
            comment=row.comment,
        )
        for row in rows
    ]


# ==========================================
# ЗАДАНИЯ СМЕНЫ
# ==========================================

@router.get("/{shift_id}/tasks", response_model=ShiftTasksResponse)
async def get_shift_tasks(
        shift_id: UUID,
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Задания смены, сгруппированные по рабочим центрам."""
    await _check_shift_planning_enabled(db, org_id)

    resolved_version_id = await _resolve_version_id(db, org_id, version_id)

    shift_result = await db.execute(
        text("""
            SELECT id, name, starts_at, ends_at, is_working, comment
            FROM shift
            WHERE id = :shift_id AND organization_id = :org_id
        """),
        {"shift_id": shift_id, "org_id": org_id},
    )
    shift_row = shift_result.fetchone()
    if not shift_row:
        raise HTTPException(status_code=404, detail="Смена не найдена")

    shift = ShiftResponse(
        id=shift_row.id,
        name=shift_row.name,
        starts_at=shift_row.starts_at,
        ends_at=shift_row.ends_at,
        is_working=shift_row.is_working,
        comment=shift_row.comment,
    )

    if resolved_version_id is None:
        return ShiftTasksResponse(
            shift=shift,
            groups=[],
            total_tasks=0,
            carryover_count=0,
            done_count=0,
        )

    # Задачи смены
    tasks_result = await db.execute(
        text("""
            SELECT
                st.id, st.batch_id, st.planned_start, st.planned_end,
                st.actual_start, st.actual_end, st.actual_qty, st.material_load_at,
                st.task_role, st.status,
                st.equipment_id, eq.name AS equipment_name, eq.code AS equipment_code,
                st.linked_equipment_id, leq.name AS linked_equipment_name,
                ot.name AS operation_name,
                p.id AS product_id, p.code AS product_code, p.name AS product_name,
                b.volume_kg AS batch_volume,
                COALESCE(b.is_lab_blocked, FALSE) AS is_lab_blocked,
                b.lab_status AS lab_status,
                b.lab_block_reason AS lab_block_reason,
                st.cooling_mode
            FROM scheduled_task st
            LEFT JOIN equipment eq ON st.equipment_id = eq.id
            LEFT JOIN equipment leq ON st.linked_equipment_id = leq.id
            LEFT JOIN operation_template ot ON st.operation_template_id = ot.id
            LEFT JOIN batch b ON st.batch_id = b.id
            LEFT JOIN product p ON b.product_id = p.id
            WHERE st.shift_id = :shift_id
              AND st.organization_id = :org_id
              AND st.schedule_version_id = :version_id
            ORDER BY eq.name, st.planned_start
        """),
        {
            "shift_id": shift_id,
            "org_id": org_id,
            "version_id": resolved_version_id,
        },
    )

    tasks = tasks_result.fetchall()

    groups_dict: dict = {}
    done_count = 0

    for row in tasks:
        eq_id = str(row.equipment_id)
        duration = (
            int((row.planned_end - row.planned_start).total_seconds() / 60)
            if row.planned_start and row.planned_end else 0
        )

        task = ShiftTaskResponse(
            id=row.id,
            batch_id=row.batch_id,
            batch_name=(
                f"Партия {str(row.batch_id)[:8]}" if row.batch_id else None
            ),
            product_id=row.product_id,
            product_code=row.product_code,
            product_name=row.product_name,
            operation_name=str(row.operation_name or "Операция"),
            task_role=row.task_role,
            equipment_id=row.equipment_id,
            equipment_name=str(row.equipment_name or "Unknown"),
            linked_equipment_id=row.linked_equipment_id,
            linked_equipment_name=row.linked_equipment_name,
            planned_start=row.planned_start,
            planned_end=row.planned_end,
            actual_start=row.actual_start,
            actual_end=row.actual_end,
            actual_qty=float(row.actual_qty) if row.actual_qty else None,
            material_load_at=row.material_load_at,
            status=row.status or "PLANNED",
            duration_minutes=duration,
            is_carryover=False,
            is_lab_blocked=(
                bool(row.is_lab_blocked) if row.is_lab_blocked is not None else False
            ),
            lab_status=row.lab_status,
            lab_block_reason=row.lab_block_reason,
            cooling_mode=row.cooling_mode,
        )

        if task.status == "DONE":
            done_count += 1

        if eq_id not in groups_dict:
            groups_dict[eq_id] = {
                "equipment_id": row.equipment_id,
                "equipment_name": str(row.equipment_name or "Unknown"),
                "equipment_code": row.equipment_code,
                "tasks": [],
            }
        groups_dict[eq_id]["tasks"].append(task)

    # Переходящие задания
    prev_shift_result = await db.execute(
        text("""
            SELECT id, starts_at, ends_at
            FROM shift
            WHERE organization_id = :org_id
              AND is_working = TRUE
              AND starts_at < (SELECT starts_at FROM shift WHERE id = :shift_id)
            ORDER BY starts_at DESC
            LIMIT 1
        """),
        {"org_id": org_id, "shift_id": shift_id},
    )
    prev_shift_row = prev_shift_result.fetchone()

    carryover_count = 0
    if prev_shift_row:
        carryover_result = await db.execute(
            text("""
                SELECT
                    st.id, st.batch_id, st.planned_start, st.planned_end,
                    st.actual_start, st.actual_end, st.actual_qty, st.material_load_at,
                    st.task_role, st.status,
                    st.equipment_id, eq.name AS equipment_name, eq.code AS equipment_code,
                    st.linked_equipment_id, leq.name AS linked_equipment_name,
                    ot.name AS operation_name,
                    p.id AS product_id, p.code AS product_code, p.name AS product_name,
                    COALESCE(b.is_lab_blocked, FALSE) AS is_lab_blocked,
                    b.lab_status AS lab_status,
                    b.lab_block_reason AS lab_block_reason,
                    st.cooling_mode
                FROM scheduled_task st
                LEFT JOIN equipment eq ON st.equipment_id = eq.id
                LEFT JOIN equipment leq ON st.linked_equipment_id = leq.id
                LEFT JOIN operation_template ot ON st.operation_template_id = ot.id
                LEFT JOIN batch b ON st.batch_id = b.id
                LEFT JOIN product p ON b.product_id = p.id
                WHERE st.shift_id = :prev_shift_id
                  AND st.organization_id = :org_id
                  AND st.schedule_version_id = :version_id
                  AND st.actual_end IS NULL
                  AND st.status IN ('PLANNED', 'IN_PROGRESS')
                ORDER BY eq.name, st.planned_start
            """),
            {
                "prev_shift_id": prev_shift_row.id,
                "org_id": org_id,
                "version_id": resolved_version_id,
            },
        )

        for row in carryover_result.fetchall():
            eq_id = str(row.equipment_id)
            duration = (
                int((row.planned_end - row.planned_start).total_seconds() / 60)
                if row.planned_start and row.planned_end else 0
            )

            task = ShiftTaskResponse(
                id=row.id,
                batch_id=row.batch_id,
                batch_name=(
                    f"Партия {str(row.batch_id)[:8]}" if row.batch_id else None
                ),
                product_id=row.product_id,
                product_code=row.product_code,
                product_name=row.product_name,
                operation_name=str(row.operation_name or "Операция"),
                task_role=row.task_role,
                equipment_id=row.equipment_id,
                equipment_name=str(row.equipment_name or "Unknown"),
                linked_equipment_id=row.linked_equipment_id,
                linked_equipment_name=row.linked_equipment_name,
                planned_start=row.planned_start,
                planned_end=row.planned_end,
                actual_start=row.actual_start,
                actual_end=row.actual_end,
                actual_qty=float(row.actual_qty) if row.actual_qty else None,
                material_load_at=row.material_load_at,
                status=row.status or "PLANNED",
                duration_minutes=duration,
                is_carryover=True,
                is_lab_blocked=(
                    bool(row.is_lab_blocked) if row.is_lab_blocked is not None else False
                ),
                lab_status=row.lab_status,
                lab_block_reason=row.lab_block_reason,
                cooling_mode=row.cooling_mode,
            )

            if eq_id not in groups_dict:
                groups_dict[eq_id] = {
                    "equipment_id": row.equipment_id,
                    "equipment_name": str(row.equipment_name or "Unknown"),
                    "equipment_code": row.equipment_code,
                    "tasks": [],
                }
            groups_dict[eq_id]["tasks"].append(task)
            carryover_count += 1

    groups = [
        ShiftTasksGrouped(
            equipment_id=g["equipment_id"],
            equipment_name=g["equipment_name"],
            equipment_code=g["equipment_code"],
            tasks=g["tasks"],
        )
        for g in groups_dict.values()
    ]
    groups.sort(key=lambda g: g.equipment_name)

    return ShiftTasksResponse(
        shift=shift,
        groups=groups,
        total_tasks=len(tasks) + carryover_count,
        carryover_count=carryover_count,
        done_count=done_count,
    )


@router.get("/{shift_id}/carryover", response_model=List[ShiftTaskResponse])
async def get_carryover(
        shift_id: UUID,
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Переходящие задания из предыдущей рабочей смены."""
    await _check_shift_planning_enabled(db, org_id)

    resolved_version_id = await _resolve_version_id(db, org_id, version_id)
    if resolved_version_id is None:
        return []

    prev_result = await db.execute(
        text("""
            SELECT id FROM shift
            WHERE organization_id = :org_id
              AND is_working = TRUE
              AND starts_at < (SELECT starts_at FROM shift WHERE id = :shift_id)
            ORDER BY starts_at DESC
            LIMIT 1
        """),
        {"org_id": org_id, "shift_id": shift_id},
    )
    prev_row = prev_result.fetchone()
    if not prev_row:
        return []

    result = await db.execute(
        text("""
            SELECT
                st.id, st.batch_id, st.planned_start, st.planned_end,
                st.actual_start, st.actual_end, st.actual_qty, st.material_load_at,
                st.task_role, st.status,
                st.equipment_id, eq.name AS equipment_name,
                st.linked_equipment_id, leq.name AS linked_equipment_name,
                ot.name AS operation_name,
                p.id AS product_id, p.code AS product_code, p.name AS product_name,
                COALESCE(b.is_lab_blocked, FALSE) AS is_lab_blocked,
                b.lab_status AS lab_status,
                b.lab_block_reason AS lab_block_reason,
                st.cooling_mode
            FROM scheduled_task st
            LEFT JOIN equipment eq ON st.equipment_id = eq.id
            LEFT JOIN equipment leq ON st.linked_equipment_id = leq.id
            LEFT JOIN operation_template ot ON st.operation_template_id = ot.id
            LEFT JOIN batch b ON st.batch_id = b.id
            LEFT JOIN product p ON b.product_id = p.id
            WHERE st.shift_id = :prev_shift_id
              AND st.organization_id = :org_id
              AND st.schedule_version_id = :version_id
              AND st.actual_end IS NULL
              AND st.status IN ('PLANNED', 'IN_PROGRESS')
            ORDER BY eq.name, st.planned_start
        """),
        {
            "prev_shift_id": prev_row.id,
            "org_id": org_id,
            "version_id": resolved_version_id,
        },
    )

    return [
        ShiftTaskResponse(
            id=row.id,
            batch_id=row.batch_id,
            batch_name=(
                f"Партия {str(row.batch_id)[:8]}" if row.batch_id else None
            ),
            product_id=row.product_id,
            product_code=row.product_code,
            product_name=row.product_name,
            operation_name=str(row.operation_name or "Операция"),
            task_role=row.task_role,
            equipment_id=row.equipment_id,
            equipment_name=str(row.equipment_name or "Unknown"),
            linked_equipment_id=row.linked_equipment_id,
            linked_equipment_name=row.linked_equipment_name,
            planned_start=row.planned_start,
            planned_end=row.planned_end,
            actual_start=row.actual_start,
            actual_end=row.actual_end,
            actual_qty=float(row.actual_qty) if row.actual_qty else None,
            material_load_at=row.material_load_at,
            status=row.status or "PLANNED",
            duration_minutes=(
                int((row.planned_end - row.planned_start).total_seconds() / 60)
                if row.planned_start and row.planned_end else 0
            ),
            is_carryover=True,
            is_lab_blocked=(
                bool(row.is_lab_blocked) if row.is_lab_blocked is not None else False
            ),
            lab_status=row.lab_status,
            lab_block_reason=row.lab_block_reason,
            cooling_mode=row.cooling_mode,
        )
        for row in result.fetchall()
    ]


# ==========================================
# ВНЕСЕНИЕ ФАКТА
# ==========================================

@router.post("/task/{task_id}/fact", response_model=TaskFactResponse)
async def update_task_fact(
        task_id: UUID,
        fact: TaskFactRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Мастер вносит факт выполнения задания."""
    await _check_shift_planning_enabled(db, org_id)

    check_result = await db.execute(
        text("""
            SELECT id, status FROM scheduled_task
            WHERE id = :task_id AND organization_id = :org_id
        """),
        {"task_id": task_id, "org_id": org_id},
    )
    check_row = check_result.fetchone()
    if not check_row:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    allowed_statuses = {"PLANNED", "IN_PROGRESS", "DONE", "CANCELLED"}
    if fact.status and fact.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый status: {fact.status}. "
                   f"Допустимые: {allowed_statuses}",
        )

    update_fields = []
    params = {"task_id": task_id, "org_id": org_id}

    if fact.actual_start is not None:
        update_fields.append("actual_start = :actual_start")
        params["actual_start"] = fact.actual_start
    if fact.actual_end is not None:
        update_fields.append("actual_end = :actual_end")
        params["actual_end"] = fact.actual_end
    if fact.actual_qty is not None:
        update_fields.append("actual_qty = :actual_qty")
        params["actual_qty"] = fact.actual_qty
    if fact.material_load_at is not None:
        update_fields.append("material_load_at = :material_load_at")
        params["material_load_at"] = fact.material_load_at
    if fact.status is not None:
        update_fields.append("status = :status")
        params["status"] = fact.status

    if fact.actual_start is not None and not fact.status and check_row.status == "PLANNED":
        update_fields.append("status = :auto_status")
        params["auto_status"] = "IN_PROGRESS"

    if fact.actual_end is not None and not fact.status:
        update_fields.append("status = :auto_done")
        params["auto_done"] = "DONE"

    if not update_fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    query = text(f"""
        UPDATE scheduled_task
        SET {', '.join(update_fields)}
        WHERE id = :task_id AND organization_id = :org_id
        RETURNING id, status, actual_start, actual_end, actual_qty, material_load_at
    """)

    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось обновить задачу")

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Мастер внёс факт по задаче {str(task_id)[:8]}: "
        f"status={row.status}, actual_qty={row.actual_qty}",
        stage="shift_fact", org_id=str(org_id),
    )

    return TaskFactResponse(
        id=row.id,
        status=row.status,
        actual_start=row.actual_start,
        actual_end=row.actual_end,
        actual_qty=float(row.actual_qty) if row.actual_qty else None,
        material_load_at=row.material_load_at,
        message="Факт успешно внесён",
    )