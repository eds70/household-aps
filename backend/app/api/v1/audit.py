# backend/app/api/v1/audit.py
"""
API страницы «Аудит» (Итерация 13.3).

Объединяет события из 4 журналов:
  - material_stock_log   → изменения остатков материалов
  - reschedule_log       → перепланирования
  - lab_analysis_log     → лабораторные блокировки/одобрения
  - cz_scan_log          → сканы Честного Знака

Каждое событие нормализуется в единую модель AuditEvent
и отдаётся в отсортированном по времени виде (свежие — первыми).

Эндпоинты:
  GET /api/v1/audit/log              — все события с фильтрами
  GET /api/v1/audit/stats            — счётчики по источникам за период
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.logging_config import setup_scheduler_logging
from .audit_models import (
    AUDIT_SOURCES,
    AuditEvent,
    AuditListResponse,
    AuditStatsResponse,
)

router = APIRouter(prefix="/api/v1/audit", tags=["Аудит"])
logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _to_float(v) -> Optional[float]:
    """Decimal → float (безопасно)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _limit_per_source(limit: int, sources_count: int) -> int:
    """
    Распределяет общий лимит по источникам.

    Берём чуть больше, чем limit / sources_count, чтобы после
    сортировки и слияния точно хватило на итоговый limit.
    """
    if sources_count <= 0:
        return limit
    return max(limit, limit // sources_count + 10)


# ==========================================
# STOCK: material_stock_log
# ==========================================

async def _fetch_stock_events(
        db: AsyncSession,
        org_id: UUID,
        limit: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
) -> List[AuditEvent]:
    """Изменения остатков материалов."""
    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.changed_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.changed_at <= :date_to")
        params["date_to"] = date_to

    result = await db.execute(
        text(f"""
            SELECT
                l.id, l.action, l.changed_at, l.changed_by,
                l.old_qty, l.new_qty, l.delta_qty,
                l.old_reserved_qty, l.new_reserved_qty,
                l.source, l.reason,
                m.id AS material_id, m.code AS material_code, m.name AS material_name,
                u.full_name AS actor_name
            FROM material_stock_log l
            LEFT JOIN material m ON m.id = l.material_id
            LEFT JOIN app_user u ON u.id = l.changed_by
            WHERE {' AND '.join(where)}
            ORDER BY l.changed_at DESC
            LIMIT :limit
        """),
        params,
    )

    events: List[AuditEvent] = []
    for row in result.fetchall():
        delta = _to_float(row.delta_qty) or 0.0

        # Severity: расход → WARNING, приход → INFO
        severity = "WARNING" if delta < 0 else "INFO"

        action_label = {
            "INSERT": "Создание",
            "UPDATE": "Изменение",
            "DELETE": "Удаление",
        }.get(row.action, row.action)

        old_q = _to_float(row.old_qty)
        new_q = _to_float(row.new_qty)

        title = f"{row.material_code or '?'}: {action_label}"

        if old_q is not None and new_q is not None:
            description = f"{old_q:.2f} → {new_q:.2f} (Δ {delta:+.2f})"
        elif new_q is not None:
            description = f"Установлено {new_q:.2f}"
        elif old_q is not None:
            description = f"Было {old_q:.2f}"
        else:
            description = row.reason or ""

        events.append(AuditEvent(
            id=row.id,
            source="STOCK",
            event_type=row.action,
            severity=severity,
            title=title,
            description=description,
            entity_type="material",
            entity_id=row.material_id,
            entity_name=(
                f"{row.material_code} — {row.material_name}"
                if row.material_code else None
            ),
            actor_id=row.changed_by,
            actor_name=row.actor_name,
            occurred_at=row.changed_at,
            details={
                "source": row.source,
                "reason": row.reason,
                "delta_qty": delta,
                "old_qty": old_q,
                "new_qty": new_q,
                "old_reserved_qty": _to_float(row.old_reserved_qty),
                "new_reserved_qty": _to_float(row.new_reserved_qty),
            },
        ))
    return events


# ==========================================
# RESCHEDULE: reschedule_log
# ==========================================

async def _fetch_reschedule_events(
        db: AsyncSession,
        org_id: UUID,
        limit: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
) -> List[AuditEvent]:
    """Перепланирования."""
    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.created_at <= :date_to")
        params["date_to"] = date_to

    result = await db.execute(
        text(f"""
            SELECT
                l.id, l.reason, l.created_at, l.created_by,
                l.from_version_id, l.to_version_id,
                l.affected_task_count, l.moved_task_count,
                l.frozen_before, l.comment,
                u.full_name AS actor_name
            FROM reschedule_log l
            LEFT JOIN app_user u ON u.id = l.created_by
            WHERE {' AND '.join(where)}
            ORDER BY l.created_at DESC
            LIMIT :limit
        """),
        params,
    )

    events: List[AuditEvent] = []
    for row in result.fetchall():
        reason_label = {
            "DELAY": "Задержка",
            "BREAKDOWN": "Поломка",
            "QTY_CHANGE": "Изменение объёма",
            "MANUAL": "Ручное",
        }.get(row.reason, row.reason)

        # BREAKDOWN — критично
        severity = "CRITICAL" if row.reason == "BREAKDOWN" else "INFO"

        events.append(AuditEvent(
            id=row.id,
            source="RESCHEDULE",
            event_type=row.reason,
            severity=severity,
            title=f"Перепланирование: {reason_label}",
            description=(
                f"Затронуто {row.affected_task_count or 0} задач, "
                f"перенесено {row.moved_task_count or 0}"
            ),
            entity_type="schedule_version",
            entity_id=row.to_version_id,
            entity_name=row.comment,
            actor_id=row.created_by,
            actor_name=row.actor_name,
            occurred_at=row.created_at,
            details={
                "from_version_id": str(row.from_version_id) if row.from_version_id else None,
                "to_version_id": str(row.to_version_id) if row.to_version_id else None,
                "affected_tasks": row.affected_task_count,
                "moved_tasks": row.moved_task_count,
                "frozen_before": row.frozen_before.isoformat() if row.frozen_before else None,
            },
        ))
    return events


# ==========================================
# LAB: lab_analysis_log
# ==========================================

async def _fetch_lab_events(
        db: AsyncSession,
        org_id: UUID,
        limit: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
) -> List[AuditEvent]:
    """Лабораторные блокировки/одобрения."""
    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.performed_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.performed_at <= :date_to")
        params["date_to"] = date_to

    result = await db.execute(
        text(f"""
            SELECT
                l.id, l.action, l.result, l.reason,
                l.performed_at, l.performed_by, l.comment,
                l.batch_id,
                b.volume_kg,
                p.code AS product_code, p.name AS product_name,
                u.full_name AS actor_name
            FROM lab_analysis_log l
            LEFT JOIN batch b ON b.id = l.batch_id
            LEFT JOIN product p ON p.id = b.product_id
            LEFT JOIN app_user u ON u.id = l.performed_by
            WHERE {' AND '.join(where)}
            ORDER BY l.performed_at DESC
            LIMIT :limit
        """),
        params,
    )

    events: List[AuditEvent] = []
    for row in result.fetchall():
        action_label = {
            "REQUESTED": "Запрошен анализ",
            "APPROVED": "Одобрено",
            "BLOCKED": "Заблокировано",
            "UNBLOCKED": "Разблокировано",
            "EXTENDED": "Продлено",
        }.get(row.action, row.action)

        # BLOCKED — WARNING, остальное INFO
        severity = "WARNING" if row.action == "BLOCKED" else "INFO"

        description_parts = []
        if row.product_code:
            description_parts.append(f"Продукт: {row.product_code}")
        if row.volume_kg is not None:
            description_parts.append(f"Объём: {float(row.volume_kg):.0f} кг")
        if row.reason:
            description_parts.append(f"Причина: {row.reason}")
        if row.comment:
            description_parts.append(row.comment)

        events.append(AuditEvent(
            id=row.id,
            source="LAB",
            event_type=row.action,
            severity=severity,
            title=f"Лаборатория: {action_label}",
            description=" • ".join(description_parts) if description_parts else None,
            entity_type="batch",
            entity_id=row.batch_id,
            entity_name=(
                f"{row.product_code} — {row.product_name}"
                if row.product_code else None
            ),
            actor_id=row.performed_by,
            actor_name=row.actor_name,
            occurred_at=row.performed_at,
            details={
                "action": row.action,
                "result": row.result,
                "reason": row.reason,
                "batch_id": str(row.batch_id) if row.batch_id else None,
            },
        ))
    return events


# ==========================================
# CZ: cz_scan_log
# ==========================================

async def _fetch_cz_events(
        db: AsyncSession,
        org_id: UUID,
        limit: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
) -> List[AuditEvent]:
    """Сканы Честного Знака."""
    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.scanned_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.scanned_at <= :date_to")
        params["date_to"] = date_to

    result = await db.execute(
        text(f"""
            SELECT
                l.id, l.cz_code, l.gtin, l.qty,
                l.line_code, l.camera_id,
                l.scanned_at, l.batch_id,
                b.cz_status,
                p.code AS product_code, p.name AS product_name
            FROM cz_scan_log l
            LEFT JOIN batch b ON b.id = l.batch_id
            LEFT JOIN product p ON p.id = b.product_id
            WHERE {' AND '.join(where)}
            ORDER BY l.scanned_at DESC
            LIMIT :limit
        """),
        params,
    )

    events: List[AuditEvent] = []
    for row in result.fetchall():
        is_unresolved = row.batch_id is None
        severity = "WARNING" if is_unresolved else "INFO"

        if is_unresolved:
            title = "ЧЗ: скан-сирота (не сопоставлен)"
        else:
            title = "ЧЗ: скан сопоставлен"

        description_parts = []
        if row.line_code:
            description_parts.append(f"Линия: {row.line_code}")
        if row.camera_id:
            description_parts.append(f"Камера: {row.camera_id}")
        if row.gtin:
            description_parts.append(f"GTIN: {row.gtin}")
        description_parts.append(f"Код: {row.cz_code[:24]}...")

        events.append(AuditEvent(
            id=row.id,
            source="CZ",
            event_type="SCAN_UNRESOLVED" if is_unresolved else "SCAN",
            severity=severity,
            title=title,
            description=" • ".join(description_parts),
            entity_type="batch",
            entity_id=row.batch_id,
            entity_name=(
                f"{row.product_code} — {row.product_name}"
                if row.product_code else None
            ),
            actor_id=None,          # камера не пользователь
            actor_name=row.camera_id or "Камера ТС",
            occurred_at=row.scanned_at,
            details={
                "cz_code": row.cz_code,
                "gtin": row.gtin,
                "qty": _to_float(row.qty),
                "line_code": row.line_code,
                "camera_id": row.camera_id,
                "cz_status": row.cz_status,
                "resolved": not is_unresolved,
            },
        ))
    return events


# ==========================================
# ГЛАВНЫЙ ЭНДПОИНТ: GET /log
# ==========================================

@router.get("/log", response_model=AuditListResponse)
async def get_audit_log(
        sources: Optional[str] = Query(
            default=None,
            description=(
                    "Список источников через запятую: STOCK,RESCHEDULE,LAB,CZ. "
                    "Если не задан — все."
            ),
        ),
        date_from: Optional[datetime] = Query(default=None),
        date_to: Optional[datetime] = Query(default=None),
        severity: Optional[str] = Query(
            default=None,
            description="Фильтр по важности: INFO | WARNING | CRITICAL",
        ),
        search: Optional[str] = Query(
            default=None,
            description="Поиск по title/description/entity_name (подстрока, регистронезависимо)",
        ),
        limit: int = Query(default=200, ge=1, le=2000),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Объединённый журнал аудита.

    Возвращает события из 4 источников, отсортированные по времени (DESC).
    """
    # --- Определяем, какие источники включать ---
    if sources:
        requested = [s.strip().upper() for s in sources.split(",") if s.strip()]
        # Оставляем только валидные
        active_sources = [s for s in requested if s in AUDIT_SOURCES]
    else:
        active_sources = list(AUDIT_SOURCES)

    if not active_sources:
        # Ничего не запрошено — вернём пустой ответ
        return AuditListResponse(
            events=[],
            total=0,
            by_source={s: 0 for s in AUDIT_SOURCES},
        )

    # --- Распределяем лимит по источникам ---
    per_source_limit = _limit_per_source(limit, len(active_sources))

    # --- Собираем события ---
    all_events: List[AuditEvent] = []

    if "STOCK" in active_sources:
        try:
            stock_events = await _fetch_stock_events(
                db, org_id, per_source_limit, date_from, date_to,
            )
            all_events.extend(stock_events)
        except Exception as e:
            logger.error(f"[audit] Ошибка загрузки STOCK событий: {e}", exc_info=True)

    if "RESCHEDULE" in active_sources:
        try:
            reschedule_events = await _fetch_reschedule_events(
                db, org_id, per_source_limit, date_from, date_to,
            )
            all_events.extend(reschedule_events)
        except Exception as e:
            logger.error(f"[audit] Ошибка загрузки RESCHEDULE событий: {e}", exc_info=True)

    if "LAB" in active_sources:
        try:
            lab_events = await _fetch_lab_events(
                db, org_id, per_source_limit, date_from, date_to,
            )
            all_events.extend(lab_events)
        except Exception as e:
            logger.error(f"[audit] Ошибка загрузки LAB событий: {e}", exc_info=True)

    if "CZ" in active_sources:
        try:
            cz_events = await _fetch_cz_events(
                db, org_id, per_source_limit, date_from, date_to,
            )
            all_events.extend(cz_events)
        except Exception as e:
            logger.error(f"[audit] Ошибка загрузки CZ событий: {e}", exc_info=True)

    # --- Фильтр по severity ---
    if severity:
        severity_upper = severity.upper()
        all_events = [e for e in all_events if e.severity == severity_upper]

    # --- Поиск по подстроке ---
    if search:
        needle = search.strip().lower()
        def _match(e: AuditEvent) -> bool:
            haystack = " ".join(filter(None, [
                e.title or "",
                e.description or "",
                e.entity_name or "",
                e.actor_name or "",
                ])).lower()
            return needle in haystack
        all_events = [e for e in all_events if _match(e)]

    # --- Сортировка по времени (DESC) ---
    all_events.sort(key=lambda e: e.occurred_at, reverse=True)

    # --- Подсчёт по источникам (до обрезки) ---
    by_source: dict = {s: 0 for s in AUDIT_SOURCES}
    for e in all_events:
        by_source[e.source] = by_source.get(e.source, 0) + 1

    total = len(all_events)

    # --- Обрезаем до limit ---
    events_page = all_events[:limit]

    return AuditListResponse(
        events=events_page,
        total=total,
        by_source=by_source,
    )


# ==========================================
# СТАТИСТИКА: GET /stats
# ==========================================

@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
        days: int = Query(
            default=7,
            ge=1,
            le=365,
            description="Период в днях (по умолчанию — последние 7)",
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Сводная статистика по источникам за последние N дней.

    Возвращает количество событий по каждому источнику + общий total
    + разбивку по severity.
    """
    date_from = datetime.utcnow() - timedelta(days=days)
    date_to = datetime.utcnow()

    # Загружаем все события за период без обрезки — берём большой лимит.
    # Для страницы статистики это ок (объёмы небольшие).
    all_events: List[AuditEvent] = []

    for fetch_fn in (
            _fetch_stock_events,
            _fetch_reschedule_events,
            _fetch_lab_events,
            _fetch_cz_events,
    ):
        try:
            events = await fetch_fn(db, org_id, 5000, date_from, date_to)
            all_events.extend(events)
        except Exception as e:
            logger.error(
                f"[audit] Ошибка stats загрузки {fetch_fn.__name__}: {e}",
                exc_info=True,
            )

    by_source: dict = {s: 0 for s in AUDIT_SOURCES}
    by_severity: dict = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}

    for e in all_events:
        by_source[e.source] = by_source.get(e.source, 0) + 1
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1

    return AuditStatsResponse(
        period_days=days,
        date_from=date_from,
        date_to=date_to,
        total=len(all_events),
        by_source=by_source,
        by_severity=by_severity,
    )


# ==========================================
# ДОПОЛНИТЕЛЬНЫЙ ЭНДПОИНТ: GET /sources
# ==========================================

@router.get("/sources")
async def get_audit_sources():
    """
    Возвращает список доступных источников аудита для UI.
    """
    return {
        "sources": [
            {
                "key": "STOCK",
                "label": "Изменения остатков",
                "description": "Журнал material_stock_log",
            },
            {
                "key": "RESCHEDULE",
                "label": "Перепланирования",
                "description": "Журнал reschedule_log",
            },
            {
                "key": "LAB",
                "label": "Лаборатория",
                "description": "Блокировки и одобрения (lab_analysis_log)",
            },
            {
                "key": "CZ",
                "label": "Честный Знак",
                "description": "Сканы ЧЗ (cz_scan_log)",
            },
        ],
    }