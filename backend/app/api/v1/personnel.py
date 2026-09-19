# backend/app/api/v1/personnel.py
"""
API персонала (Итерация 6).

Эндпоинты:
  GET  /api/v1/personnel/pools         — список пулов с загрузкой
  GET  /api/v1/personnel/pools/{id}    — один пул
  PUT  /api/v1/personnel/pools/{id}    — обновить capacity / name
  GET  /api/v1/personnel/load          — текущая загрузка всех пулов

Итерация 9: расширен PERSONNEL_POOL_TYPES — добавлены COOLING_ZONE
и BOILER.

Итерация 11 (Шаг 5): чтение флага enable_operator_pools через settings_reader.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.settings_reader import read_feature_flags
from .personnel_models import (
    PersonnelPoolResponse,
    PersonnelPoolUpdate,
    PersonnelPoolListResponse,
)

router = APIRouter(prefix="/api/v1/personnel", tags=["Персонал"])
logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# КОНСТАНТЫ
# ==========================================

PERSONNEL_POOL_TYPES = {
    "REACTOR_OPERATOR",
    "LINE_OPERATOR",
    "MANUAL_OPERATOR",
    "LAB",
    "COOLING_ZONE",
    "BOILER",
}

EDIT_ALLOWED_ROLES = {"ADMIN", "PLANNER"}


# ==========================================
# ПРОВЕРКА FEATURE-ФЛАГА
# ==========================================

async def _check_feature_flag(db: AsyncSession, org_id: UUID) -> None:
    """
    Проверяет, включён ли enable_operator_pools.

    Итерация 11 (Шаг 5): читает из app_settings через settings_reader.
    """
    flags = await read_feature_flags(db, org_id)
    if not flags.enable_operator_pools:
        raise HTTPException(
            status_code=400,
            detail="Пулы операторов отключены (enable_operator_pools = false)",
        )


# ==========================================
# RESOLVE VERSION_ID
# ==========================================

async def _resolve_version_id(
        db: AsyncSession,
        org_id: UUID,
        version_id: Optional[UUID],
) -> Optional[UUID]:
    """Определяет версию плана (последняя активная, если не задана)."""
    if version_id is not None:
        result = await db.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE id = :version_id AND organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": org_id},
        )
        if result.fetchone():
            return version_id
        raise HTTPException(
            status_code=404,
            detail=f"Версия плана {version_id} не найдена",
        )

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
    return row.id if row else None


# ==========================================
# COMPUTE POOL LOAD
# ==========================================

async def _compute_pool_load(
        db: AsyncSession,
        org_id: UUID,
        version_id: Optional[UUID],
        pool_type: str,
) -> tuple:
    """
    Считает загрузку пула в указанной версии плана.

    Возвращает: (scheduled_count, peak_concurrent).

    Алгоритм peak_concurrent — метод «заметающей прямой»:
      - Собираем все интервалы [start, end).
      - Идём по событиям: start = +1, end = -1.
      - Сортируем события: по времени, при равенстве — сначала -1.
      - Peak = максимум счётчика.
    """
    if version_id is None:
        return 0, 0

    result = await db.execute(
        text("""
            SELECT planned_start, planned_end
            FROM scheduled_task
            WHERE organization_id = :org_id
              AND schedule_version_id = :version_id
              AND operator_pool = :pool_type
        """),
        {
            "org_id": org_id,
            "version_id": version_id,
            "pool_type": pool_type,
        },
    )
    rows = result.fetchall()

    scheduled_count = len(rows)
    if scheduled_count == 0:
        return 0, 0

    events = []
    for row in rows:
        events.append((row.planned_start, +1))
        events.append((row.planned_end, -1))

    events.sort(key=lambda e: (e[0], e[1]))

    current = 0
    peak = 0
    for _, delta in events:
        current += delta
        if current > peak:
            peak = current

    return scheduled_count, peak


# ==========================================
# SQL ORDER BY для пулов
# ==========================================

_POOL_ORDER_BY = """
    CASE type
        WHEN 'REACTOR_OPERATOR' THEN 1
        WHEN 'LINE_OPERATOR'    THEN 2
        WHEN 'MANUAL_OPERATOR'  THEN 3
        WHEN 'LAB'              THEN 4
        WHEN 'COOLING_ZONE'     THEN 5
        WHEN 'BOILER'           THEN 6
        ELSE 99
    END
"""


# ==========================================
# GET /pools — список пулов
# ==========================================

@router.get("/pools", response_model=PersonnelPoolListResponse)
async def list_pools(
        version_id: Optional[UUID] = Query(
            default=None,
            description="ID версии плана. Если не задан — последняя активная.",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает список пулов операторов с загрузкой в текущем плане."""
    await _check_feature_flag(db, org_id)

    resolved_version_id = await _resolve_version_id(db, org_id, version_id)

    version_name = None
    if resolved_version_id:
        v_result = await db.execute(
            text("SELECT name FROM schedule_version WHERE id = :vid"),
            {"vid": resolved_version_id},
        )
        v_row = v_result.fetchone()
        version_name = v_row.name if v_row else None

    result = await db.execute(
        text(f"""
            SELECT id, organization_id, name, type, capacity, comment, updated_at
            FROM resource_pool
            WHERE organization_id = :org_id
              AND type = ANY(:types)
            ORDER BY {_POOL_ORDER_BY}
        """),
        {"org_id": org_id, "types": list(PERSONNEL_POOL_TYPES)},
    )
    rows = result.fetchall()

    pools = []
    total_capacity = 0
    total_scheduled = 0

    for row in rows:
        scheduled_count, peak = await _compute_pool_load(
            db, org_id, resolved_version_id, row.type
        )
        capacity = int(row.capacity or 0)
        load_percent = (peak / capacity * 100.0) if capacity > 0 else 0.0

        pools.append(PersonnelPoolResponse(
            id=row.id,
            organization_id=row.organization_id,
            name=row.name,
            type=row.type,
            capacity=capacity,
            comment=row.comment,
            updated_at=row.updated_at,
            scheduled_count=scheduled_count,
            peak_concurrent=peak,
            load_percent=round(load_percent, 1),
        ))

        total_capacity += capacity
        total_scheduled += scheduled_count

    return PersonnelPoolListResponse(
        pools=pools,
        total_capacity=total_capacity,
        total_scheduled=total_scheduled,
        version_id=str(resolved_version_id) if resolved_version_id else None,
        version_name=version_name,
    )


# ==========================================
# GET /pools/{id} — один пул
# ==========================================

@router.get("/pools/{pool_id}", response_model=PersonnelPoolResponse)
async def get_pool(
        pool_id: UUID,
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает один пул по ID с загрузкой."""
    await _check_feature_flag(db, org_id)

    result = await db.execute(
        text("""
            SELECT id, organization_id, name, type, capacity, comment, updated_at
            FROM resource_pool
            WHERE id = :pool_id AND organization_id = :org_id
        """),
        {"pool_id": pool_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Пул не найден")

    resolved_version_id = await _resolve_version_id(db, org_id, version_id)
    scheduled_count, peak = await _compute_pool_load(
        db, org_id, resolved_version_id, row.type
    )
    capacity = int(row.capacity or 0)
    load_percent = (peak / capacity * 100.0) if capacity > 0 else 0.0

    return PersonnelPoolResponse(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        type=row.type,
        capacity=capacity,
        comment=row.comment,
        updated_at=row.updated_at,
        scheduled_count=scheduled_count,
        peak_concurrent=peak,
        load_percent=round(load_percent, 1),
    )


# ==========================================
# PUT /pools/{id} — обновить capacity
# ==========================================

@router.put("/pools/{pool_id}", response_model=PersonnelPoolResponse)
async def update_pool(
        pool_id: UUID,
        payload: PersonnelPoolUpdate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Обновляет capacity / name / comment пула.

    Доступно ролям: ADMIN, PLANNER.
    """
    await _check_feature_flag(db, org_id)

    role = current_user.get("role")
    if role not in EDIT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: {sorted(EDIT_ALLOWED_ROLES)}",
        )

    check = await db.execute(
        text("""
            SELECT id, type FROM resource_pool
            WHERE id = :pool_id AND organization_id = :org_id
        """),
        {"pool_id": pool_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Пул не найден")

    if payload.capacity is not None and payload.capacity < 0:
        raise HTTPException(
            status_code=400,
            detail="capacity не может быть отрицательным",
        )

    update_fields = []
    params = {"pool_id": pool_id, "org_id": org_id}

    if payload.name is not None:
        update_fields.append("name = :name")
        params["name"] = payload.name
    if payload.capacity is not None:
        update_fields.append("capacity = :capacity")
        params["capacity"] = payload.capacity
    if payload.comment is not None:
        update_fields.append("comment = :comment")
        params["comment"] = payload.comment

    if not update_fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    await db.execute(
        text(f"""
            UPDATE resource_pool
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = :pool_id AND organization_id = :org_id
        """),
        params,
    )
    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Пул {str(pool_id)[:8]} обновлён: {params}",
        stage="personnel_update", org_id=str(org_id),
    )

    return await get_pool(pool_id=pool_id, version_id=None, org_id=org_id, db=db)


# ==========================================
# GET /load — текущая загрузка (краткая)
# ==========================================

@router.get("/load")
async def get_load(
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Краткая информация о загрузке пулов.

    Возвращает компактный JSON:
    [
      {"type": "REACTOR_OPERATOR", "capacity": 3, "peak": 3, "load_percent": 100.0},
      ...
    ]
    """
    await _check_feature_flag(db, org_id)

    resolved_version_id = await _resolve_version_id(db, org_id, version_id)

    result = await db.execute(
        text(f"""
            SELECT type, capacity
            FROM resource_pool
            WHERE organization_id = :org_id
              AND type = ANY(:types)
            ORDER BY {_POOL_ORDER_BY}
        """),
        {"org_id": org_id, "types": list(PERSONNEL_POOL_TYPES)},
    )

    response = []
    for row in result.fetchall():
        _, peak = await _compute_pool_load(db, org_id, resolved_version_id, row.type)
        capacity = int(row.capacity or 0)
        load_percent = (peak / capacity * 100.0) if capacity > 0 else 0.0
        response.append({
            "type": row.type,
            "capacity": capacity,
            "peak": peak,
            "load_percent": round(load_percent, 1),
        })

    return response