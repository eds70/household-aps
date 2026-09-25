# backend/app/api/v1/cz.py
"""
API интеграции с Честным Знаком (Итерация 8).

Эндпоинты:
  POST   /api/v1/cz/scan                — приём скана от камеры (API-key)
  GET    /api/v1/cz/batch/{id}/progress — прогресс маркировки партии
  GET    /api/v1/cz/pending             — партии в ожидании маркировки
  GET    /api/v1/cz/log                 — журнал сканирований
  GET    /api/v1/cz/stats               — сводка по маркировке
  POST   /api/v1/cz/scan/{id}/attach    — ручное сопоставление сироты
  DELETE /api/v1/cz/scan/{id}           — удаление скана

Аутентификация скана — через заголовок X-CZ-Api-Key.
Остальные эндпоинты — через JWT.

Итерация 11 (Шаг 5): чтение настроек через settings_reader (app_settings).
Итерация 13.14: опциональный version_id — настройки ЧЗ читаются
                из plan_settings плана (fallback на app_settings).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from app.scheduler.cz import (
    get_batch_progress,
    recalc_batch_cz_status,
    resolve_batch_for_scan,
)
from app.scheduler.feature_flags import FeatureFlags
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.settings_reader import (
    read_feature_flags,
    read_settings_dict,
    read_float,
    read_str,
    read_bool,
)
from .cz_models import (
    CzActionResponse,
    CzAttachRequest,
    CzPendingBatch,
    CzProgressResponse,
    CzScanLogResponse,
    CzScanRequest,
    CzScanResponse,
    CzStatsResponse,
)

router = APIRouter(prefix="/api/v1/cz", tags=["Честный Знак"])
logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

async def _check_cz_enabled(
        db: AsyncSession,
        org_id: UUID,
        version_id: Optional[UUID] = None,
) -> FeatureFlags:
    """
    Проверяет feature-флаг enable_cz_integration.

    Итерация 13.14: если version_id задан — флаг читается из plan_settings
    этого плана. Иначе — из app_settings.
    """
    flags = await read_feature_flags(db, org_id, version_id=version_id)
    if not flags.enable_cz_integration:
        raise HTTPException(
            status_code=400,
            detail="Интеграция с ЧЗ отключена (enable_cz_integration = false)",
        )
    return flags


async def _get_cz_settings(
        db: AsyncSession,
        org_id: UUID,
        version_id: Optional[UUID] = None,
) -> dict:
    """
    Возвращает словарь настроек ЧЗ.

    Итерация 13.14: если version_id задан — читаем из plan_settings.
    """
    settings = await read_settings_dict(
        db, org_id,
        keys=[
            "enable_cz_integration",
            "cz_completion_threshold",
            "cz_api_key",
            "enable_cz_auto_close",
        ],
        version_id=version_id,
    )

    flags = FeatureFlags({
        "enable_cz_integration": settings.get("enable_cz_integration"),
    })

    return {
        "enable_cz_integration": flags.enable_cz_integration,
        "threshold": read_float(settings.get("cz_completion_threshold"), 0.95),
        "api_key": read_str(settings.get("cz_api_key"), ""),
        "auto_close": read_bool(settings.get("enable_cz_auto_close"), False),
    }


async def _check_api_key(
        db: AsyncSession,
        org_id: UUID,
        x_cz_api_key: Optional[str],
        version_id: Optional[UUID] = None,
) -> None:
    """Проверяет API-ключ для вебхука от камер."""
    settings = await _get_cz_settings(db, org_id, version_id=version_id)
    expected = settings["api_key"]

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="cz_api_key не настроен в app_settings",
        )

    if x_cz_api_key != expected:
        log_with_context(
            logger, logging.WARNING,
            f"Неверный X-CZ-Api-Key для org={str(org_id)[:8]}",
            stage="cz_auth", org_id=str(org_id),
        )
        raise HTTPException(
            status_code=401,
            detail="Неверный или отсутствующий X-CZ-Api-Key",
        )


# ==========================================
# POST /scan — приём скана
# ==========================================

@router.post("/scan", response_model=CzScanResponse)
async def receive_scan(
        payload: CzScanRequest,
        x_cz_api_key: Optional[str] = Header(default=None, alias="X-CZ-Api-Key"),
        version_id: Optional[UUID] = Query(
            default=None,
            description="ID плана. Если не задан — настройки из app_settings.",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Приём скана кода ЧЗ от камеры технического зрения.

    Аутентификация — через заголовок X-CZ-Api-Key.
    Идемпотентность: повторный cz_code вернёт duplicate=true без
    изменения cz_marked_qty.
    """
    await _check_cz_enabled(db, org_id, version_id=version_id)
    await _check_api_key(db, org_id, x_cz_api_key, version_id=version_id)

    settings = await _get_cz_settings(db, org_id, version_id=version_id)

    # Время скана
    scanned_at = payload.scanned_at or datetime.now(timezone.utc)
    if scanned_at.tzinfo is None:
        scanned_at = scanned_at.replace(tzinfo=timezone.utc)

    # 1. Пробуем вставить скан (идемпотентно)
    insert_result = await db.execute(
        text("""
            INSERT INTO cz_scan_log
                (organization_id, batch_id, scheduled_task_id, cz_code, gtin,
                 qty, line_code, camera_id, scanned_at, comment)
            VALUES
                (:org_id, :batch_id, :task_id, :cz_code, :gtin,
                 :qty, :line_code, :camera_id, :scanned_at, :comment)
            ON CONFLICT (organization_id, cz_code) DO NOTHING
            RETURNING id
        """),
        {
            "org_id": org_id,
            "batch_id": payload.batch_id,
            "task_id": payload.task_id,
            "cz_code": payload.cz_code,
            "gtin": payload.gtin,
            "qty": payload.qty or 1.0,
            "line_code": payload.line_code,
            "camera_id": payload.camera_id,
            "scanned_at": scanned_at,
            "comment": payload.comment,
        },
    )
    inserted_row = insert_result.fetchone()

    # 2. Если INSERT не сработал — скан уже был (дубликат)
    if inserted_row is None:
        existing = await db.execute(
            text("""
                SELECT id, batch_id, scheduled_task_id
                FROM cz_scan_log
                WHERE organization_id = :org_id AND cz_code = :cz_code
            """),
            {"org_id": org_id, "cz_code": payload.cz_code},
        )
        row = existing.fetchone()
        await db.commit()

        log_with_context(
            logger, logging.INFO,
            f"Дубликат скана: cz_code={payload.cz_code[:30]}...",
            stage="cz_scan", org_id=str(org_id),
        )

        return CzScanResponse(
            id=row.id,
            cz_code=payload.cz_code,
            batch_id=row.batch_id,
            scheduled_task_id=row.scheduled_task_id,
            qty=payload.qty or 1.0,
            duplicate=True,
            resolved=row.batch_id is not None,
            message="Код уже был зарегистрирован ранее",
        )

    scan_id = inserted_row.id

    # 3. Определяем партию (fallback-сопоставление)
    resolved_batch_id, resolved_task_id = await resolve_batch_for_scan(
        session=db,
        org_id=org_id,
        batch_id=payload.batch_id,
        task_id=payload.task_id,
        line_code=payload.line_code,
        scanned_at=scanned_at,
    )

    # 4. Если нашли партию — обновляем её
    if resolved_batch_id is not None:
        await db.execute(
            text("""
                UPDATE cz_scan_log
                SET batch_id = :batch_id, scheduled_task_id = :task_id
                WHERE id = :scan_id
            """),
            {
                "batch_id": resolved_batch_id,
                "task_id": resolved_task_id,
                "scan_id": scan_id,
            },
        )

        qty = float(payload.qty or 1.0)
        await db.execute(
            text("""
                UPDATE batch
                SET cz_marked_qty = COALESCE(cz_marked_qty, 0) + :qty,
                    cz_last_scan_at = :scanned_at
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {
                "qty": qty,
                "scanned_at": scanned_at,
                "batch_id": resolved_batch_id,
                "org_id": org_id,
            },
        )

        # Пересчитываем статус маркировки
        await recalc_batch_cz_status(
            session=db,
            org_id=org_id,
            batch_id=resolved_batch_id,
            threshold=settings["threshold"],
        )

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Скан принят: cz_code={payload.cz_code[:30]}..., "
        f"batch={str(resolved_batch_id)[:8] if resolved_batch_id else 'NULL'}, "
        f"line={payload.line_code}, camera={payload.camera_id}",
        stage="cz_scan", org_id=str(org_id),
    )

    return CzScanResponse(
        id=scan_id,
        cz_code=payload.cz_code,
        batch_id=resolved_batch_id,
        scheduled_task_id=resolved_task_id,
        qty=payload.qty or 1.0,
        duplicate=False,
        resolved=resolved_batch_id is not None,
        message=(
            "Скан принят и сопоставлен с партией"
            if resolved_batch_id else
            "Скан принят, но не сопоставлен с партией (требуется ручное сопоставление)"
        ),
    )


# ==========================================
# GET /batch/{id}/progress
# ==========================================

@router.get("/batch/{batch_id}/progress", response_model=CzProgressResponse)
async def get_batch_cz_progress(
        batch_id: UUID,
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает прогресс маркировки партии."""
    await _check_cz_enabled(db, org_id, version_id=version_id)
    settings = await _get_cz_settings(db, org_id, version_id=version_id)

    progress = await get_batch_progress(
        session=db,
        org_id=org_id,
        batch_id=batch_id,
        threshold=settings["threshold"],
    )

    if not progress:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    return CzProgressResponse(**progress)


# ==========================================
# GET /pending
# ==========================================

@router.get("/pending", response_model=List[CzPendingBatch])
async def list_pending_batches(
        include_completed: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает партии, ожидающие маркировки.

    include_completed=false (по умолчанию) — только PENDING + IN_PROGRESS.
    include_completed=true — все, включая COMPLETED.
    """
    await _check_cz_enabled(db, org_id, version_id=version_id)
    settings = await _get_cz_settings(db, org_id, version_id=version_id)
    threshold = settings["threshold"]

    statuses = ["PENDING", "IN_PROGRESS"]
    if include_completed:
        statuses.append("COMPLETED")

    placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
    params = {"org_id": org_id, "limit": limit}
    for i, s in enumerate(statuses):
        params[f"s{i}"] = s

    result = await db.execute(
        text(f"""
            SELECT
                b.id AS batch_id,
                b.order_id,
                b.product_id,
                b.volume_kg,
                b.cz_status,
                b.cz_marked_qty,
                b.cz_last_scan_at,
                p.code AS product_code,
                p.name AS product_name,
                e.name AS equipment_name,
                gp.bottle_volume_l
            FROM batch b
            LEFT JOIN product p ON p.id = b.product_id
            LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
            LEFT JOIN production_order po ON po.id = b.order_id
            LEFT JOIN product gp ON gp.id = po.product_id
            WHERE b.organization_id = :org_id
              AND b.cz_status IN ({placeholders})
            ORDER BY
                b.cz_status DESC,
                b.cz_last_scan_at DESC NULLS LAST,
                b.id
            LIMIT :limit
        """),
        params,
    )

    out: List[CzPendingBatch] = []
    for row in result.fetchall():
        marked_qty = float(row.cz_marked_qty or 0)
        planned_qty: Optional[float] = None
        if row.bottle_volume_l and float(row.bottle_volume_l) > 0:
            planned_qty = float(row.volume_kg) / float(row.bottle_volume_l)
        progress_percent = 0.0
        if planned_qty and planned_qty > 0:
            progress_percent = min(100.0, (marked_qty / planned_qty) * 100.0)

        out.append(CzPendingBatch(
            batch_id=row.batch_id,
            order_id=row.order_id,
            product_id=row.product_id,
            product_code=row.product_code,
            product_name=row.product_name,
            equipment_name=row.equipment_name,
            volume_kg=float(row.volume_kg),
            cz_status=row.cz_status or "PENDING",
            marked_qty=marked_qty,
            planned_qty=planned_qty,
            progress_percent=progress_percent,
            last_scan_at=row.cz_last_scan_at,
        ))

    return out


# ==========================================
# GET /log
# ==========================================

@router.get("/log", response_model=List[CzScanLogResponse])
async def get_scan_log(
        batch_id: Optional[UUID] = Query(default=None),
        line_code: Optional[str] = Query(default=None),
        camera_id: Optional[str] = Query(default=None),
        only_unresolved: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=1000),
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Журнал сканирований с фильтрами."""
    await _check_cz_enabled(db, org_id, version_id=version_id)

    where_clauses = ["cz.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if batch_id:
        where_clauses.append("cz.batch_id = :batch_id")
        params["batch_id"] = batch_id
    if line_code:
        where_clauses.append("cz.line_code = :line_code")
        params["line_code"] = line_code
    if camera_id:
        where_clauses.append("cz.camera_id = :camera_id")
        params["camera_id"] = camera_id
    if only_unresolved:
        where_clauses.append("cz.batch_id IS NULL")

    query = text(f"""
        SELECT
            cz.id, cz.organization_id, cz.batch_id, cz.scheduled_task_id,
            cz.cz_code, cz.gtin, cz.qty, cz.line_code, cz.camera_id,
            cz.scanned_at, cz.created_at, cz.comment,
            p.code AS product_code, p.name AS product_name
        FROM cz_scan_log cz
        LEFT JOIN batch b ON b.id = cz.batch_id
        LEFT JOIN product p ON p.id = b.product_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY cz.scanned_at DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)

    return [
        CzScanLogResponse(
            id=row.id,
            organization_id=row.organization_id,
            batch_id=row.batch_id,
            scheduled_task_id=row.scheduled_task_id,
            cz_code=row.cz_code,
            gtin=row.gtin,
            qty=float(row.qty or 1),
            line_code=row.line_code,
            camera_id=row.camera_id,
            scanned_at=row.scanned_at,
            created_at=row.created_at,
            comment=row.comment,
            batch_name=f"Партия {str(row.batch_id)[:8]}" if row.batch_id else None,
            product_code=row.product_code,
            product_name=row.product_name,
        )
        for row in result.fetchall()
    ]


# ==========================================
# GET /stats
# ==========================================

@router.get("/stats", response_model=CzStatsResponse)
async def get_cz_stats(
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Сводная статистика по маркировке."""
    await _check_cz_enabled(db, org_id, version_id=version_id)
    settings = await _get_cz_settings(db, org_id, version_id=version_id)

    # Статусы партий
    statuses_result = await db.execute(
        text("""
            SELECT cz_status, COUNT(*) AS cnt
            FROM batch
            WHERE organization_id = :org_id
            GROUP BY cz_status
        """),
        {"org_id": org_id},
    )
    by_status = {row.cz_status or "PENDING": int(row.cnt) for row in statuses_result.fetchall()}

    # Сканы
    scans_result = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE batch_id IS NULL) AS unresolved
            FROM cz_scan_log
            WHERE organization_id = :org_id
        """),
        {"org_id": org_id},
    )
    scans_row = scans_result.fetchone()
    total_scans = int(scans_row.total or 0)
    unresolved_scans = int(scans_row.unresolved or 0)

    total_batches = sum(by_status.values())

    return CzStatsResponse(
        total_batches=total_batches,
        not_applicable=by_status.get("NOT_APPLICABLE", 0),
        pending=by_status.get("PENDING", 0),
        in_progress=by_status.get("IN_PROGRESS", 0),
        completed=by_status.get("COMPLETED", 0),
        total_scans=total_scans,
        unresolved_scans=unresolved_scans,
        threshold=settings["threshold"],
    )


# ==========================================
# POST /scan/{id}/attach — ручное сопоставление
# ==========================================

ALLOWED_ATTACH_ROLES = {"ADMIN", "PLANNER", "MASTER"}


@router.post("/scan/{scan_id}/attach", response_model=CzActionResponse)
async def attach_scan(
        scan_id: UUID,
        payload: CzAttachRequest,
        version_id: Optional[UUID] = Query(default=None),
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Ручное сопоставление скана-сироты с партией / задачей.

    Доступно: ADMIN, PLANNER, MASTER.
    """
    await _check_cz_enabled(db, org_id, version_id=version_id)

    role = current_user.get("role")
    if role not in ALLOWED_ATTACH_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: {sorted(ALLOWED_ATTACH_ROLES)}",
        )

    if payload.batch_id is None and payload.task_id is None:
        raise HTTPException(
            status_code=400,
            detail="Нужно указать batch_id или task_id",
        )

    # Проверяем скан
    scan_result = await db.execute(
        text("""
            SELECT id, batch_id, qty FROM cz_scan_log
            WHERE id = :scan_id AND organization_id = :org_id
        """),
        {"scan_id": scan_id, "org_id": org_id},
    )
    scan_row = scan_result.fetchone()
    if not scan_row:
        raise HTTPException(status_code=404, detail="Скан не найден")

    if scan_row.batch_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Скан уже сопоставлен с партией",
        )

    # Разрешаем batch_id через task_id
    batch_id = payload.batch_id
    task_id = payload.task_id

    if task_id is not None and batch_id is None:
        task_result = await db.execute(
            text("""
                SELECT batch_id FROM scheduled_task
                WHERE id = :task_id AND organization_id = :org_id
            """),
            {"task_id": task_id, "org_id": org_id},
        )
        task_row = task_result.fetchone()
        if not task_row:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        batch_id = task_row.batch_id

    if batch_id is None:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить batch_id",
        )

    # Проверяем batch
    batch_result = await db.execute(
        text("""
            SELECT id, cz_marked_qty FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    batch_row = batch_result.fetchone()
    if not batch_row:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    # Привязываем скан
    await db.execute(
        text("""
            UPDATE cz_scan_log
            SET batch_id = :batch_id,
                scheduled_task_id = :task_id,
                comment = COALESCE(:comment, comment)
            WHERE id = :scan_id
        """),
        {
            "batch_id": batch_id,
            "task_id": task_id,
            "comment": payload.comment,
            "scan_id": scan_id,
        },
    )

    # Обновляем партию
    qty = float(scan_row.qty or 1.0)
    await db.execute(
        text("""
            UPDATE batch
            SET cz_marked_qty = COALESCE(cz_marked_qty, 0) + :qty,
                cz_last_scan_at = NOW()
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"qty": qty, "batch_id": batch_id, "org_id": org_id},
    )

    settings = await _get_cz_settings(db, org_id, version_id=version_id)
    await recalc_batch_cz_status(
        session=db,
        org_id=org_id,
        batch_id=batch_id,
        threshold=settings["threshold"],
    )

    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Скан {str(scan_id)[:8]} сопоставлен с партией {str(batch_id)[:8]} "
        f"(пользователь {current_user.get('email')})",
        stage="cz_attach", org_id=str(org_id),
    )

    return CzActionResponse(
        id=scan_id,
        message=f"Скан сопоставлен с партией {str(batch_id)[:8]}",
        resolved=True,
    )


# ==========================================
# DELETE /scan/{id}
# ==========================================

@router.delete("/scan/{scan_id}", response_model=CzActionResponse)
async def delete_scan(
        scan_id: UUID,
        version_id: Optional[UUID] = Query(default=None),
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Удаление скана. Доступно только ADMIN.

    Если скан был привязан к партии — уменьшает cz_marked_qty
    и пересчитывает статус.
    """
    await _check_cz_enabled(db, org_id, version_id=version_id)

    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён. Требуется роль ADMIN",
        )

    result = await db.execute(
        text("""
            SELECT id, batch_id, qty FROM cz_scan_log
            WHERE id = :scan_id AND organization_id = :org_id
        """),
        {"scan_id": scan_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Скан не найден")

    batch_id = row.batch_id
    qty = float(row.qty or 1.0)

    await db.execute(
        text("DELETE FROM cz_scan_log WHERE id = :scan_id"),
        {"scan_id": scan_id},
    )

    if batch_id is not None:
        await db.execute(
            text("""
                UPDATE batch
                SET cz_marked_qty = GREATEST(COALESCE(cz_marked_qty, 0) - :qty, 0)
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {"qty": qty, "batch_id": batch_id, "org_id": org_id},
        )

        settings = await _get_cz_settings(db, org_id, version_id=version_id)
        await recalc_batch_cz_status(
            session=db,
            org_id=org_id,
            batch_id=batch_id,
            threshold=settings["threshold"],
        )

    await db.commit()

    log_with_context(
        logger, logging.WARNING,
        f"Скан {str(scan_id)[:8]} удалён (пользователь {current_user.get('email')})",
        stage="cz_delete", org_id=str(org_id),
    )

    return CzActionResponse(
        id=scan_id,
        message="Скан удалён",
        resolved=False,
    )