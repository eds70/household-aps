# backend/app/api/v1/lab.py
"""
API лаборатории (Итерация 5 + fix C3).

Эндпоинты:
  GET  /api/v1/lab/pending                — партии, ожидающие анализа / заблокированные
  GET  /api/v1/lab/batch/{batch_id}       — статус партии по лаборатории
  GET  /api/v1/lab/batch/{batch_id}/log   — журнал проверок партии
  POST /api/v1/lab/batch/{batch_id}/block     — заблокировать партию
  POST /api/v1/lab/batch/{batch_id}/unblock   — разблокировать (одобрить)
  POST /api/v1/lab/batch/{batch_id}/approve   — одобрить после анализа
  POST /api/v1/lab/batch/{batch_id}/request   — запросить анализ

Итерация 11 (Шаг 5): чтение флага enable_lab_blocking через settings_reader.
Итерация 13.4 (fix C3): авто-перепланирование после block/unblock/approve
    через BackgroundTasks.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.settings_reader import read_feature_flags
from .lab_models import (
    ApproveBatchRequest,
    BatchLabStatusResponse,
    BlockBatchRequest,
    LabActionResponse,
    LabAnalysisLogResponse,
    LabPendingBatchResponse,
    RequestAnalysisRequest,
    UnblockBatchRequest,
)

router = APIRouter(prefix="/api/v1/lab", tags=["Лаборатория"])
logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# КОНСТАНТЫ
# ==========================================

ALLOWED_ROLES = {"LAB", "MASTER", "ADMIN"}

VALID_LAB_STATUSES = {
    "NOT_REQUIRED",
    "PENDING_LAB",
    "APPROVED",
    "BLOCKED",
}


# ==========================================
# ПРОВЕРКИ
# ==========================================

async def _check_lab_blocking_enabled(db: AsyncSession, org_id: UUID) -> None:
    """
    Проверяет, включён ли feature-флаг enable_lab_blocking.

    Итерация 11 (Шаг 5): читает из app_settings через settings_reader.
    """
    flags = await read_feature_flags(db, org_id)
    if not flags.enable_lab_blocking:
        raise HTTPException(
            status_code=400,
            detail="Блокировка лабораторией отключена (enable_lab_blocking = false)",
        )


def _check_role(current_user: dict) -> None:
    """Проверяет, что у пользователя есть право управлять лабораторными блокировками."""
    role = current_user.get("role")
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: {sorted(ALLOWED_ROLES)}",
        )


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

async def _validate_scheduled_task_id(
        db: AsyncSession,
        org_id: UUID,
        scheduled_task_id: Optional[UUID],
) -> Optional[UUID]:
    """
    Проверяет, что scheduled_task_id существует в БД и принадлежит org_id.
    Если не существует или None — возвращает None (запись в лог будет без FK).
    """
    if scheduled_task_id is None:
        return None

    result = await db.execute(
        text("""
            SELECT id FROM scheduled_task
            WHERE id = :task_id AND organization_id = :org_id
        """),
        {"task_id": scheduled_task_id, "org_id": org_id},
    )
    row = result.fetchone()
    if row is None:
        log_with_context(
            logger, logging.WARNING,
            f"scheduled_task_id={scheduled_task_id} не найден в БД — "
            f"запись в журнал пойдёт без ссылки на задачу",
            stage="lab_validate", org_id=str(org_id),
        )
        return None

    return scheduled_task_id


async def _write_lab_log(
        db: AsyncSession,
        org_id: UUID,
        batch_id: UUID,
        action: str,
        result: Optional[str] = None,
        reason: Optional[str] = None,
        scheduled_task_id: Optional[UUID] = None,
        performed_by: Optional[UUID] = None,
        comment: Optional[str] = None,
) -> Optional[UUID]:
    """
    Создаёт запись в lab_analysis_log. Возвращает ID записи.
    """
    safe_task_id = await _validate_scheduled_task_id(db, org_id, scheduled_task_id)

    insert = await db.execute(
        text("""
            INSERT INTO lab_analysis_log
            (organization_id, batch_id, scheduled_task_id, action, result,
             reason, performed_by, comment)
            VALUES
            (:org_id, :batch_id, :task_id, :action, :result,
             :reason, :performed_by, :comment)
            RETURNING id
        """),
        {
            "org_id": org_id,
            "batch_id": batch_id,
            "task_id": safe_task_id,
            "action": action,
            "result": result,
            "reason": reason,
            "performed_by": performed_by,
            "comment": comment,
        },
    )
    row = insert.fetchone()
    return row.id if row else None


# ==========================================
# ИТЕРАЦИЯ 13.4 (fix C3): авто-перепланирование
# ==========================================

async def _get_active_version_id(
        db: AsyncSession,
        org_id: UUID,
) -> Optional[UUID]:
    """Возвращает ID последней активной версии плана или None."""
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


async def _auto_reschedule_after_lab(
        org_id: UUID,
        from_version_id: UUID,
        reason: str,
        comment: str,
) -> None:
    """
    Фоновая задача: запускает перепланирование с учётом изменения
    статуса лаборатории.

    Вызывается из эндпоинтов block/unblock/approve.

    Если перепланирование не удалось (например, нет активной версии) —
    просто логируем и не падаем. Мастер всегда может запустить
    вручную через /schedule.
    """
    from app.scheduler.rescheduler import Rescheduler

    try:
        rescheduler = Rescheduler(org_id=org_id)
        result = await rescheduler.reschedule(
            from_version_id=from_version_id,
            reason="MANUAL",
            changes={"source": "lab_auto_reschedule", "trigger": reason},
            comment=comment,
        )

        log_with_context(
            logger, logging.INFO,
            f"[C3] Авто-перепланирование после {reason}: "
            f"status={result.status}, "
            f"from={str(from_version_id)[:8]}, "
            f"to={str(result.to_version_id)[:8] if result.to_version_id else 'N/A'}, "
            f"tasks={result.moved_tasks}",
            stage="lab_auto_reschedule", org_id=str(org_id),
        )
    except Exception as e:
        log_with_context(
            logger, logging.ERROR,
            f"[C3] Ошибка авто-перепланирования после {reason}: "
            f"{type(e).__name__}: {e}",
            stage="lab_auto_reschedule", org_id=str(org_id),
        )


# ==========================================
# GET /pending — партии, ожидающие анализа / заблокированные
# ==========================================

@router.get("/pending", response_model=List[LabPendingBatchResponse])
async def list_pending_batches(
        include_blocked: bool = Query(default=True, description="Включать заблокированные"),
        include_pending: bool = Query(default=True, description="Включать ожидающие анализа"),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает партии, ожидающие анализа (PENDING_LAB) или заблокированные (BLOCKED)."""
    await _check_lab_blocking_enabled(db, org_id)

    statuses = []
    if include_pending:
        statuses.append("PENDING_LAB")
    if include_blocked:
        statuses.append("BLOCKED")

    if not statuses:
        return []

    placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
    params = {"org_id": org_id}
    for i, s in enumerate(statuses):
        params[f"s{i}"] = s

    query = text(f"""
        SELECT
            b.id AS batch_id,
            b.order_id,
            b.product_id,
            p.code AS product_code,
            p.name AS product_name,
            b.volume_kg,
            b.assigned_equipment_id AS equipment_id,
            e.name AS equipment_name,
            b.is_lab_blocked,
            b.lab_status,
            b.lab_block_reason,
            b.lab_blocked_at,
            b.planned_end,
            lt.id AS next_lab_task_id,
            lt.planned_start AS next_lab_task_start,
            lt.planned_end AS next_lab_task_end
        FROM batch b
        LEFT JOIN product p ON p.id = b.product_id
        LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
        LEFT JOIN LATERAL (
            SELECT st.id, st.planned_start, st.planned_end
            FROM scheduled_task st
            JOIN operation_template ot ON ot.id = st.operation_template_id
            WHERE st.batch_id = b.id
              AND ot.needs_lab = TRUE
              AND st.organization_id = :org_id
            ORDER BY st.planned_start
            LIMIT 1
        ) lt ON TRUE
        WHERE b.organization_id = :org_id
          AND b.lab_status IN ({placeholders})
        ORDER BY
            b.is_lab_blocked DESC,
            b.lab_blocked_at NULLS LAST,
            b.planned_end NULLS LAST,
            b.id
    """)

    result = await db.execute(query, params)
    return [
        LabPendingBatchResponse(
            batch_id=row.batch_id,
            order_id=row.order_id,
            product_id=row.product_id,
            product_code=row.product_code,
            product_name=row.product_name,
            volume_kg=float(row.volume_kg) if row.volume_kg else 0.0,
            equipment_id=row.equipment_id,
            equipment_name=row.equipment_name,
            is_lab_blocked=bool(row.is_lab_blocked),
            lab_status=row.lab_status or "NOT_REQUIRED",
            lab_block_reason=row.lab_block_reason,
            lab_blocked_at=row.lab_blocked_at,
            planned_end=row.planned_end,
            next_lab_task_id=row.next_lab_task_id,
            next_lab_task_start=row.next_lab_task_start,
            next_lab_task_end=row.next_lab_task_end,
        )
        for row in result.fetchall()
    ]


# ==========================================
# GET /batch/{id} — статус партии по лаборатории
# ==========================================

@router.get("/batch/{batch_id}", response_model=BatchLabStatusResponse)
async def get_batch_lab_status(
        batch_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает текущий статус партии по лаборатории."""
    await _check_lab_blocking_enabled(db, org_id)

    result = await db.execute(
        text("""
            SELECT
                b.id AS batch_id,
                b.product_id,
                p.code AS product_code,
                p.name AS product_name,
                b.volume_kg,
                b.is_lab_blocked,
                b.lab_status,
                b.lab_block_reason,
                b.lab_blocked_at,
                b.lab_blocked_by,
                u.full_name AS lab_blocked_by_name,
                e.name AS equipment_name
            FROM batch b
            LEFT JOIN product p ON p.id = b.product_id
            LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
            LEFT JOIN app_user u ON u.id = b.lab_blocked_by
            WHERE b.id = :batch_id AND b.organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    return BatchLabStatusResponse(
        batch_id=row.batch_id,
        product_id=row.product_id,
        product_code=row.product_code,
        product_name=row.product_name,
        volume_kg=float(row.volume_kg) if row.volume_kg else 0.0,
        is_lab_blocked=bool(row.is_lab_blocked),
        lab_status=row.lab_status or "NOT_REQUIRED",
        lab_block_reason=row.lab_block_reason,
        lab_blocked_at=row.lab_blocked_at,
        lab_blocked_by=row.lab_blocked_by,
        lab_blocked_by_name=row.lab_blocked_by_name,
        equipment_name=row.equipment_name,
    )


# ==========================================
# GET /batch/{id}/log — журнал проверок
# ==========================================

@router.get("/batch/{batch_id}/log", response_model=List[LabAnalysisLogResponse])
async def get_batch_lab_log(
        batch_id: UUID,
        limit: int = Query(default=50, ge=1, le=500),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает журнал проверок лаборатории по партии."""
    await _check_lab_blocking_enabled(db, org_id)

    result = await db.execute(
        text("""
            SELECT
                l.id, l.organization_id, l.batch_id, l.scheduled_task_id,
                l.action, l.result, l.reason,
                l.performed_by, u.full_name AS performed_by_name,
                l.performed_at, l.comment
            FROM lab_analysis_log l
            LEFT JOIN app_user u ON u.id = l.performed_by
            WHERE l.batch_id = :batch_id AND l.organization_id = :org_id
            ORDER BY l.performed_at DESC
            LIMIT :limit
        """),
        {"batch_id": batch_id, "org_id": org_id, "limit": limit},
    )

    return [
        LabAnalysisLogResponse(
            id=row.id,
            organization_id=row.organization_id,
            batch_id=row.batch_id,
            scheduled_task_id=row.scheduled_task_id,
            action=row.action,
            result=row.result,
            reason=row.reason,
            performed_by=row.performed_by,
            performed_by_name=row.performed_by_name,
            performed_at=row.performed_at,
            comment=row.comment,
        )
        for row in result.fetchall()
    ]


# ==========================================
# POST /batch/{id}/request — запросить анализ
# ==========================================

@router.post("/batch/{batch_id}/request", response_model=LabActionResponse)
async def request_analysis(
        batch_id: UUID,
        payload: RequestAnalysisRequest,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Помечает партию как ожидающую лабораторного анализа (PENDING_LAB)."""
    await _check_lab_blocking_enabled(db, org_id)
    _check_role(current_user)

    check = await db.execute(
        text("""
            SELECT id, lab_status FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    await db.execute(
        text("""
            UPDATE batch
            SET lab_status = 'PENDING_LAB'
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )

    log_id = await _write_lab_log(
        db=db,
        org_id=org_id,
        batch_id=batch_id,
        action="REQUESTED",
        result="PENDING",
        performed_by=UUID(current_user["user_id"]),
        comment=payload.comment,
    )

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Запрошен анализ для партии {str(batch_id)[:8]}",
        stage="lab_request", org_id=str(org_id),
    )

    return LabActionResponse(
        batch_id=batch_id,
        action="REQUESTED",
        is_lab_blocked=False,
        lab_status="PENDING_LAB",
        message="Партия помечена как ожидающая анализа",
        log_id=log_id,
    )


# ==========================================
# POST /batch/{id}/block — заблокировать партию
# ==========================================

@router.post("/batch/{batch_id}/block", response_model=LabActionResponse)
async def block_batch(
        batch_id: UUID,
        payload: BlockBatchRequest,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Блокирует партию лабораторией."""
    await _check_lab_blocking_enabled(db, org_id)
    _check_role(current_user)

    check = await db.execute(
        text("""
            SELECT id, is_lab_blocked FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    if row.is_lab_blocked:
        raise HTTPException(
            status_code=400,
            detail="Партия уже заблокирована",
        )

    user_id = UUID(current_user["user_id"])

    await db.execute(
        text("""
            UPDATE batch
            SET is_lab_blocked = TRUE,
                lab_status = 'BLOCKED',
                lab_block_reason = :reason,
                lab_blocked_at = NOW(),
                lab_blocked_by = :user_id
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {
            "batch_id": batch_id,
            "org_id": org_id,
            "reason": payload.reason,
            "user_id": user_id,
        },
    )

    log_id = await _write_lab_log(
        db=db,
        org_id=org_id,
        batch_id=batch_id,
        action="BLOCKED",
        result="FAILED",
        reason=payload.reason,
        scheduled_task_id=payload.scheduled_task_id,
        performed_by=user_id,
        comment=payload.comment,
    )

    await db.commit()

    log_with_context(
        logger, logging.WARNING,
        f"Партия {str(batch_id)[:8]} ЗАБЛОКИРОВАНА лабораторией. "
        f"Причина: {payload.reason}",
        stage="lab_block", org_id=str(org_id),
    )

    # ==========================================
    # C3: авто-перепланирование
    # ==========================================
    active_version_id = await _get_active_version_id(db, org_id)
    if active_version_id is not None:
        background_tasks.add_task(
            _auto_reschedule_after_lab,
            org_id=org_id,
            from_version_id=active_version_id,
            reason="block",
            comment=(
                f"Авто-перепланирование после блокировки партии "
                f"{str(batch_id)[:8]}: {payload.reason}"
            ),
        )
        log_with_context(
            logger, logging.INFO,
            f"[C3] Запущено фоновое перепланирование после блокировки "
            f"партии {str(batch_id)[:8]}",
            stage="lab_block", org_id=str(org_id),
        )

    return LabActionResponse(
        batch_id=batch_id,
        action="BLOCKED",
        is_lab_blocked=True,
        lab_status="BLOCKED",
        message=f"Партия заблокирована: {payload.reason}",
        log_id=log_id,
    )


# ==========================================
# POST /batch/{id}/unblock — разблокировать (общее)
# ==========================================

@router.post("/batch/{batch_id}/unblock", response_model=LabActionResponse)
async def unblock_batch(
        batch_id: UUID,
        payload: UnblockBatchRequest,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Разблокирует партию."""
    await _check_lab_blocking_enabled(db, org_id)
    _check_role(current_user)

    check = await db.execute(
        text("""
            SELECT id, is_lab_blocked FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    if not row.is_lab_blocked:
        raise HTTPException(
            status_code=400,
            detail="Партия не заблокирована",
        )

    user_id = UUID(current_user["user_id"])

    await db.execute(
        text("""
            UPDATE batch
            SET is_lab_blocked = FALSE,
                lab_status = 'APPROVED',
                lab_block_reason = NULL,
                lab_blocked_at = NULL,
                lab_blocked_by = NULL
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )

    log_id = await _write_lab_log(
        db=db,
        org_id=org_id,
        batch_id=batch_id,
        action="UNBLOCKED",
        result="PASSED",
        performed_by=user_id,
        comment=payload.comment,
    )

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Партия {str(batch_id)[:8]} РАЗБЛОКИРОВАНА лабораторией",
        stage="lab_unblock", org_id=str(org_id),
    )

    # ==========================================
    # C3: авто-перепланирование
    # ==========================================
    active_version_id = await _get_active_version_id(db, org_id)
    if active_version_id is not None:
        background_tasks.add_task(
            _auto_reschedule_after_lab,
            org_id=org_id,
            from_version_id=active_version_id,
            reason="unblock",
            comment=(
                f"Авто-перепланирование после разблокировки партии "
                f"{str(batch_id)[:8]}"
            ),
        )
        log_with_context(
            logger, logging.INFO,
            f"[C3] Запущено фоновое перепланирование после разблокировки "
            f"партии {str(batch_id)[:8]}",
            stage="lab_unblock", org_id=str(org_id),
        )

    return LabActionResponse(
        batch_id=batch_id,
        action="UNBLOCKED",
        is_lab_blocked=False,
        lab_status="APPROVED",
        message="Партия разблокирована и одобрена",
        log_id=log_id,
    )


# ==========================================
# POST /batch/{id}/approve — одобрить после анализа
# ==========================================

@router.post("/batch/{batch_id}/approve", response_model=LabActionResponse)
async def approve_batch(
        batch_id: UUID,
        payload: ApproveBatchRequest,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Одобряет партию после успешного лабораторного анализа."""
    await _check_lab_blocking_enabled(db, org_id)
    _check_role(current_user)

    if payload.result not in ("PASSED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail="result должен быть PASSED или FAILED",
        )

    check = await db.execute(
        text("""
            SELECT id, is_lab_blocked, lab_status FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    user_id = UUID(current_user["user_id"])

    if payload.result == "FAILED":
        # Блокируем партию
        await db.execute(
            text("""
                UPDATE batch
                SET is_lab_blocked = TRUE,
                    lab_status = 'BLOCKED',
                    lab_block_reason = :reason,
                    lab_blocked_at = NOW(),
                    lab_blocked_by = :user_id
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {
                "batch_id": batch_id,
                "org_id": org_id,
                "reason": payload.comment or "Анализ не пройден",
                "user_id": user_id,
            },
        )
        new_status = "BLOCKED"
        is_blocked = True
        reason = payload.comment or "Анализ не пройден"
        action = "BLOCKED"
    else:
        # Одобряем партию
        await db.execute(
            text("""
                UPDATE batch
                SET is_lab_blocked = FALSE,
                    lab_status = 'APPROVED',
                    lab_block_reason = NULL,
                    lab_blocked_at = NULL,
                    lab_blocked_by = NULL
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {"batch_id": batch_id, "org_id": org_id},
        )
        new_status = "APPROVED"
        is_blocked = False
        reason = None
        action = "APPROVED"

    log_id = await _write_lab_log(
        db=db,
        org_id=org_id,
        batch_id=batch_id,
        action=action,
        result=payload.result,
        reason=reason,
        performed_by=user_id,
        comment=payload.comment,
    )

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Партия {str(batch_id)[:8]}: анализ {payload.result}",
        stage="lab_approve", org_id=str(org_id),
    )

    # ==========================================
    # C3: авто-перепланирование
    # ==========================================
    # Для FAILED тоже перепланируем — партия заблокирована и должна
    # быть исключена из плана. Для PASSED — возвращаем в план.
    active_version_id = await _get_active_version_id(db, org_id)
    if active_version_id is not None:
        background_tasks.add_task(
            _auto_reschedule_after_lab,
            org_id=org_id,
            from_version_id=active_version_id,
            reason=f"approve_{payload.result.lower()}",
            comment=(
                f"Авто-перепланирование после анализа партии "
                f"{str(batch_id)[:8]} ({payload.result})"
            ),
        )
        log_with_context(
            logger, logging.INFO,
            f"[C3] Запущено фоновое перепланирование после "
            f"{payload.result} партии {str(batch_id)[:8]}",
            stage="lab_approve", org_id=str(org_id),
        )

    return LabActionResponse(
        batch_id=batch_id,
        action=action,
        is_lab_blocked=is_blocked,
        lab_status=new_status,
        message=(
            f"Партия одобрена (PASSED)"
            if payload.result == "PASSED"
            else f"Партия заблокирована (FAILED): {reason}"
        ),
        log_id=log_id,
    )