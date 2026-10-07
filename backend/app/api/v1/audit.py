# backend/app/api/v1/audit.py
"""
API страницы «Аудит» (Итерация 13.3 + 16).

Объединяет события из 4 журналов:
  - material_stock_log   → изменения остатков материалов
  - reschedule_log       → перепланирования
  - lab_analysis_log     → лабораторные блокировки/одобрения
  - cz_scan_log          → сканы Честного Знака

Каждое событие нормализуется в единую модель AuditEvent
и отдаётся в отсортированном по времени виде (свежие — первыми).

Эндпоинты:
  GET    /api/v1/audit/log                — все события с фильтрами
  GET    /api/v1/audit/stats              — счётчики по источникам за период
  GET    /api/v1/audit/stats/series       — серии для дашборда (16.3)
  GET    /api/v1/audit/sources            — список источников
  GET    /api/v1/audit/saved-views        — мои сохранённые представления (16.2)
  POST   /api/v1/audit/saved-views        — создать представление (16.2)
  PUT    /api/v1/audit/saved-views/{id}   — обновить (16.2)
  DELETE /api/v1/audit/saved-views/{id}   — удалить (16.2)
  POST   /api/v1/audit/export.xlsx        — выгрузка в Excel (16.4)
"""
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user_id,
    get_db_session,
)
from app.scheduler.logging_config import setup_scheduler_logging
from .audit_models import (
    AUDIT_GROUP_BY,
    AUDIT_SEVERITIES,
    AUDIT_SOURCES,
    AuditEvent,
    AuditExportRequest,
    AuditFilterSpec,
    AuditListResponse,
    AuditSavedView,
    AuditSavedViewCreate,
    AuditSavedViewDeleteResponse,
    AuditSavedViewUpdate,
    AuditSavedViewsListResponse,
    AuditStatsResponse,
    AuditStatsSeriesPoint,
    AuditStatsSeriesResponse,
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


def _json_dumps(obj: Any) -> str:
    """
    Сериализация в JSON для передачи в CAST(:x AS jsonb).

    asyncpg не умеет напрямую работать с dict как JSONB-параметром
    без явного CAST — используем строку.
    """
    return json.dumps(obj, ensure_ascii=False, default=str)


def _post_filter(
        events: List[AuditEvent],
        actor_id: Optional[UUID],
        entity_type: Optional[str],
        delta_qty_from: Optional[float],
        delta_qty_to: Optional[float],
) -> List[AuditEvent]:
    """
    Пост-фильтрация событий по полям, которые сложно (или неудобно)
    фильтровать в SQL каждого источника:
      - actor_id (в CZ actor_id = NULL — это нормально)
      - entity_type
      - delta_qty_from/to (только у STOCK; у остальных — отсеиваем)
    """
    if actor_id is None and entity_type is None and \
            delta_qty_from is None and delta_qty_to is None:
        return events

    result: List[AuditEvent] = []
    entity_type_lower = entity_type.lower() if entity_type else None

    for e in events:
        # actor_id
        if actor_id is not None and e.actor_id != actor_id:
            continue

        # entity_type
        if entity_type_lower is not None:
            if not e.entity_type or e.entity_type.lower() != entity_type_lower:
                continue

        # delta_qty: применяется только к событиям, у которых есть это поле
        # (т.е. STOCK). У остальных источника delta_qty отсутствует —
        # если фильтр задан, такие события отсеиваются.
        if delta_qty_from is not None or delta_qty_to is not None:
            dq = e.details.get("delta_qty") if isinstance(e.details, dict) else None
            if dq is None:
                continue
            try:
                dq_f = float(dq)
            except (TypeError, ValueError):
                continue
            if delta_qty_from is not None and dq_f < delta_qty_from:
                continue
            if delta_qty_to is not None and dq_f > delta_qty_to:
                continue

        result.append(e)

    return result


# ==========================================
# STOCK: material_stock_log
# ==========================================

async def _fetch_stock_events(
        db: AsyncSession,
        org_id: UUID,
        limit: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        actor_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
) -> List[AuditEvent]:
    """
    Изменения остатков материалов.

    Итерация 16.1: добавлены SQL-фильтры actor_id и entity_type.
    entity_type для STOCK всегда 'material', поэтому если задан
    другой — сразу возвращаем [].
    """
    if entity_type and entity_type.lower() != "material":
        return []

    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.changed_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.changed_at <= :date_to")
        params["date_to"] = date_to
    if actor_id is not None:
        where.append("l.changed_by = :actor_id")
        params["actor_id"] = actor_id

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
        actor_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
) -> List[AuditEvent]:
    """
    Перепланирования.

    Итерация 16.1: SQL-фильтр по actor_id; entity_type для RESCHEDULE
    всегда 'schedule_version' — иначе сразу [].
    """
    if entity_type and entity_type.lower() != "schedule_version":
        return []

    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.created_at <= :date_to")
        params["date_to"] = date_to
    if actor_id is not None:
        where.append("l.created_by = :actor_id")
        params["actor_id"] = actor_id

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
        actor_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
) -> List[AuditEvent]:
    """
    Лабораторные блокировки/одобрения.

    Итерация 16.1: SQL-фильтр по actor_id; entity_type для LAB
    всегда 'batch'.
    """
    if entity_type and entity_type.lower() != "batch":
        return []

    where = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if date_from:
        where.append("l.performed_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("l.performed_at <= :date_to")
        params["date_to"] = date_to
    if actor_id is not None:
        where.append("l.performed_by = :actor_id")
        params["actor_id"] = actor_id

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
        actor_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
) -> List[AuditEvent]:
    """
    Сканы Честного Знака.

    Итерация 16.1:
      - entity_type для CZ всегда 'batch';
      - actor_id у CZ всегда NULL (камера — не пользователь).
        Если фильтр actor_id задан — возвращаем [] (нет совпадений).
    """
    if entity_type and entity_type.lower() != "batch":
        return []
    if actor_id is not None:
        # У сканов ЧЗ actor_id всегда NULL, фильтр не совпадёт ни с чем.
        return []

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
            actor_id=None,
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
# ОБЩАЯ ФУНКЦИЯ: собрать все события по фильтрам
# ==========================================

async def _collect_events(
        db: AsyncSession,
        org_id: UUID,
        spec: AuditFilterSpec,
) -> List[AuditEvent]:
    """
    Собирает события из всех источников по расширенному фильтру
    AuditFilterSpec (Итерация 16.1).

    Применяет:
      - SQL-фильтры (date, actor_id, entity_type) в каждом _fetch_*;
      - пост-фильтр _post_filter (actor_id/entity_type/delta_qty) на общий список;
      - фильтр severity, поиск, сортировку, обрезку по limit.
    """
    active_sources = spec.sources or list(AUDIT_SOURCES)
    if not active_sources:
        return []

    per_source_limit = _limit_per_source(spec.limit, len(active_sources))

    all_events: List[AuditEvent] = []

    fetchers = {
        "STOCK": _fetch_stock_events,
        "RESCHEDULE": _fetch_reschedule_events,
        "LAB": _fetch_lab_events,
        "CZ": _fetch_cz_events,
    }

    for src in active_sources:
        fetch_fn = fetchers.get(src)
        if not fetch_fn:
            continue
        try:
            events = await fetch_fn(
                db, org_id, per_source_limit,
                spec.date_from, spec.date_to,
                actor_id=spec.actor_id,
                entity_type=spec.entity_type,
            )
            all_events.extend(events)
        except Exception as e:
            logger.error(
                f"[audit] Ошибка загрузки {src} событий: {e}",
                exc_info=True,
            )

    # Пост-фильтр (delta_qty; подстраховка по actor_id/entity_type)
    all_events = _post_filter(
        all_events,
        actor_id=spec.actor_id,
        entity_type=spec.entity_type,
        delta_qty_from=spec.delta_qty_from,
        delta_qty_to=spec.delta_qty_to,
    )

    # Severity
    if spec.severity:
        all_events = [e for e in all_events if e.severity == spec.severity]

    # Поиск
    if spec.search:
        needle = spec.search.strip().lower()
        def _match(e: AuditEvent) -> bool:
            haystack = " ".join(filter(None, [
                e.title or "",
                e.description or "",
                e.entity_name or "",
                e.actor_name or "",
                ])).lower()
            return needle in haystack
        all_events = [e for e in all_events if _match(e)]

    # Сортировка DESC
    all_events.sort(key=lambda e: e.occurred_at, reverse=True)

    # Обрезка
    return all_events[:spec.limit]


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
        # Итерация 16.1: расширенные фильтры
        actor_id: Optional[UUID] = Query(
            default=None,
            description="Фильтр по ID пользователя-автора события",
        ),
        entity_type: Optional[str] = Query(
            default=None,
            description="Фильтр по типу сущности: material | batch | schedule_version",
        ),
        delta_qty_from: Optional[float] = Query(
            default=None,
            description="Минимальное изменение количества (только для STOCK-событий)",
        ),
        delta_qty_to: Optional[float] = Query(
            default=None,
            description="Максимальное изменение количества (только для STOCK-событий)",
        ),
        limit: int = Query(default=200, ge=1, le=2000),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Объединённый журнал аудита.

    Возвращает события из 4 источников, отсортированные по времени (DESC).
    """
    # Парсим sources (строка через запятую → список)
    parsed_sources: Optional[List[str]] = None
    if sources:
        parsed_sources = [s.strip().upper() for s in sources.split(",") if s.strip()]

    try:
        spec = AuditFilterSpec(
            sources=parsed_sources,
            date_from=date_from,
            date_to=date_to,
            severity=severity,
            search=search,
            actor_id=actor_id,
            entity_type=entity_type,
            delta_qty_from=delta_qty_from,
            delta_qty_to=delta_qty_to,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    events = await _collect_events(db, org_id, spec)

    by_source: Dict[str, int] = {s: 0 for s in AUDIT_SOURCES}
    for e in events:
        by_source[e.source] = by_source.get(e.source, 0) + 1

    return AuditListResponse(
        events=events,
        total=len(events),
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

    # Для статистики собираем все события за период без обрезки.
    all_events: List[AuditEvent] = []

    fetchers = (
        _fetch_stock_events,
        _fetch_reschedule_events,
        _fetch_lab_events,
        _fetch_cz_events,
    )
    for fetch_fn in fetchers:
        try:
            events = await fetch_fn(db, org_id, 5000, date_from, date_to)
            all_events.extend(events)
        except Exception as e:
            logger.error(
                f"[audit] Ошибка stats загрузки {fetch_fn.__name__}: {e}",
                exc_info=True,
            )

    by_source: Dict[str, int] = {s: 0 for s in AUDIT_SOURCES}
    by_severity: Dict[str, int] = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}

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
# ИТЕРАЦИЯ 16.3: СЕРИИ ДЛЯ ДАШБОРДА
# ==========================================

@router.get("/stats/series", response_model=AuditStatsSeriesResponse)
async def get_audit_stats_series(
        group_by: str = Query(
            default="day",
            description="Группировка: day | source | severity",
        ),
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
    Возвращает серии для графиков на дашборде.

    group_by='day'      → точки по дням (YYYY-MM-DD)
    group_by='source'   → точки по источникам (STOCK, RESCHEDULE, ...)
    group_by='severity' → точки по уровням (INFO, WARNING, CRITICAL)
    """
    group_by_norm = (group_by or "day").lower()
    if group_by_norm not in AUDIT_GROUP_BY:
        raise HTTPException(
            status_code=422,
            detail=f"group_by must be one of {AUDIT_GROUP_BY}",
        )

    date_from = datetime.utcnow() - timedelta(days=days)
    date_to = datetime.utcnow()

    # Собираем все события за период
    all_events: List[AuditEvent] = []
    fetchers = (
        _fetch_stock_events,
        _fetch_reschedule_events,
        _fetch_lab_events,
        _fetch_cz_events,
    )
    for fetch_fn in fetchers:
        try:
            events = await fetch_fn(db, org_id, 5000, date_from, date_to)
            all_events.extend(events)
        except Exception as e:
            logger.error(
                f"[audit] Ошибка series загрузки {fetch_fn.__name__}: {e}",
                exc_info=True,
            )

    # Агрегация
    buckets: Dict[str, int] = defaultdict(int)

    if group_by_norm == "day":
        for e in all_events:
            key = e.occurred_at.strftime("%Y-%m-%d")
            buckets[key] += 1
        # Заполняем пропущенные дни нулями
        points: List[AuditStatsSeriesPoint] = []
        cur = date_from.date()
        end = date_to.date()
        while cur <= end:
            key = cur.strftime("%Y-%m-%d")
            points.append(AuditStatsSeriesPoint(
                label=key,
                count=buckets.get(key, 0),
            ))
            cur += timedelta(days=1)

    elif group_by_norm == "source":
        for e in all_events:
            buckets[e.source] += 1
        points = [
            AuditStatsSeriesPoint(label=src, count=buckets.get(src, 0))
            for src in AUDIT_SOURCES
        ]

    else:  # severity
        for e in all_events:
            buckets[e.severity] += 1
        points = [
            AuditStatsSeriesPoint(label=sev, count=buckets.get(sev, 0))
            for sev in AUDIT_SEVERITIES
        ]

    return AuditStatsSeriesResponse(
        group_by=group_by_norm,
        date_from=date_from,
        date_to=date_to,
        total=len(all_events),
        points=points,
    )


# ==========================================
# СПРАВОЧНИК ИСТОЧНИКОВ: GET /sources
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


# ==========================================
# ИТЕРАЦИЯ 16.2: СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ
# ==========================================

@router.get("/saved-views", response_model=AuditSavedViewsListResponse)
async def list_saved_views(
        user_id: UUID = Depends(get_current_user_id),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Список сохранённых представлений текущего пользователя.
    """
    result = await db.execute(
        text("""
            SELECT id, name, comment, filters, is_default,
                   display_order, created_at, updated_at
            FROM audit_saved_view
            WHERE organization_id = :org_id AND user_id = :user_id
            ORDER BY display_order, name
        """),
        {"org_id": org_id, "user_id": user_id},
    )

    views = [
        AuditSavedView(
            id=row.id,
            name=row.name,
            comment=row.comment,
            filters=row.filters or {},
            is_default=row.is_default,
            display_order=row.display_order,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in result.fetchall()
    ]

    return AuditSavedViewsListResponse(views=views, total=len(views))


@router.post(
    "/saved-views",
    response_model=AuditSavedView,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_view(
        payload: AuditSavedViewCreate,
        user_id: UUID = Depends(get_current_user_id),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Создать сохранённое представление.
    """
    # Проверяем уникальность имени
    exists = await db.execute(
        text("""
            SELECT 1 FROM audit_saved_view
            WHERE organization_id = :org_id AND user_id = :user_id
              AND name = :name
        """),
        {"org_id": org_id, "user_id": user_id, "name": payload.name},
    )
    if exists.fetchone():
        raise HTTPException(
            status_code=409,
            detail=f"Saved view with name {payload.name!r} already exists",
        )

    # Фильтры → JSONB
    filters_json = payload.filters.model_dump(mode="json")

    # Если is_default = True — снимаем флаг с других
    if payload.is_default:
        await db.execute(
            text("""
                UPDATE audit_saved_view
                SET is_default = FALSE
                WHERE organization_id = :org_id AND user_id = :user_id
                  AND is_default = TRUE
            """),
            {"org_id": org_id, "user_id": user_id},
        )

    result = await db.execute(
        text("""
            INSERT INTO audit_saved_view
                (organization_id, user_id, name, comment, filters,
                 is_default, display_order)
            VALUES
                (:org_id, :user_id, :name, :comment, CAST(:filters AS jsonb),
                 :is_default, :display_order)
            RETURNING id, name, comment, filters, is_default,
                      display_order, created_at, updated_at
        """),
        {
            "org_id": org_id,
            "user_id": user_id,
            "name": payload.name,
            "comment": payload.comment,
            "filters": _json_dumps(filters_json),
            "is_default": payload.is_default,
            "display_order": payload.display_order,
        },
    )
    row = result.fetchone()
    await db.commit()

    return AuditSavedView(
        id=row.id,
        name=row.name,
        comment=row.comment,
        filters=row.filters or {},
        is_default=row.is_default,
        display_order=row.display_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put("/saved-views/{view_id}", response_model=AuditSavedView)
async def update_saved_view(
        view_id: UUID,
        payload: AuditSavedViewUpdate,
        user_id: UUID = Depends(get_current_user_id),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Обновить сохранённое представление (частичное обновление).
    """
    # Проверяем владение
    check = await db.execute(
        text("""
            SELECT id FROM audit_saved_view
            WHERE id = :id AND organization_id = :org_id AND user_id = :user_id
        """),
        {"id": view_id, "org_id": org_id, "user_id": user_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Saved view not found")

    # Собираем SET-часть динамически
    sets: List[str] = []
    params: Dict[str, Any] = {
        "id": view_id,
        "org_id": org_id,
        "user_id": user_id,
    }

    if payload.name is not None:
        sets.append("name = :name")
        params["name"] = payload.name
    if payload.comment is not None:
        sets.append("comment = :comment")
        params["comment"] = payload.comment
    if payload.filters is not None:
        sets.append("filters = CAST(:filters AS jsonb)")
        params["filters"] = _json_dumps(payload.filters.model_dump(mode="json"))
    if payload.display_order is not None:
        sets.append("display_order = :display_order")
        params["display_order"] = payload.display_order
    if payload.is_default is not None:
        sets.append("is_default = :is_default")
        params["is_default"] = payload.is_default

    if not sets:
        # Ничего не меняем — возвращаем текущее
        result = await db.execute(
            text("""
                SELECT id, name, comment, filters, is_default,
                       display_order, created_at, updated_at
                FROM audit_saved_view WHERE id = :id
            """),
            {"id": view_id},
        )
        row = result.fetchone()
        return AuditSavedView(
            id=row.id, name=row.name, comment=row.comment,
            filters=row.filters or {}, is_default=row.is_default,
            display_order=row.display_order,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    # Если ставим is_default = True — снимаем с других
    if payload.is_default is True:
        await db.execute(
            text("""
                UPDATE audit_saved_view
                SET is_default = FALSE
                WHERE organization_id = :org_id AND user_id = :user_id
                  AND is_default = TRUE AND id != :id
            """),
            {"org_id": org_id, "user_id": user_id, "id": view_id},
        )

    sets_sql = ", ".join(sets)
    result = await db.execute(
        text(f"""
            UPDATE audit_saved_view
            SET {sets_sql}
            WHERE id = :id AND organization_id = :org_id AND user_id = :user_id
            RETURNING id, name, comment, filters, is_default,
                      display_order, created_at, updated_at
        """),
        params,
    )
    row = result.fetchone()
    await db.commit()

    return AuditSavedView(
        id=row.id, name=row.name, comment=row.comment,
        filters=row.filters or {}, is_default=row.is_default,
        display_order=row.display_order,
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.delete(
    "/saved-views/{view_id}",
    response_model=AuditSavedViewDeleteResponse,
)
async def delete_saved_view(
        view_id: UUID,
        user_id: UUID = Depends(get_current_user_id),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить сохранённое представление."""
    result = await db.execute(
        text("""
            DELETE FROM audit_saved_view
            WHERE id = :id AND organization_id = :org_id AND user_id = :user_id
            RETURNING id
        """),
        {"id": view_id, "org_id": org_id, "user_id": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Saved view not found")

    await db.commit()

    return AuditSavedViewDeleteResponse(
        status="deleted",
        id=row.id,
        message="Saved view deleted",
    )


# ==========================================
# ИТЕРАЦИЯ 16.4: ЭКСПОРТ В XLSX
# ==========================================

def _build_xlsx(
        events: List[AuditEvent],
        title: Optional[str] = None,
) -> bytes:
    """
    Генерирует xlsx-файл с событиями аудита.

    Колонки:
      Время | Источник | Важность | Тип | Заголовок | Описание |
      Сущность | Автор | Детали
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Аудит"

    # Заголовок (если задан) — отдельной строкой сверху
    row_offset = 0
    if title:
        ws.cell(row=1, column=1, value=title)
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws.merge_cells(
            start_row=1, start_column=1, end_row=1, end_column=9
        )
        row_offset = 1

    headers = [
        "Время", "Источник", "Важность", "Тип", "Заголовок",
        "Описание", "Сущность", "Автор", "Детали",
    ]
    header_fill = PatternFill(
        start_color="2C3E50", end_color="2C3E50", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1 + row_offset, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Данные
    for i, e in enumerate(events, start=1):
        r = i + 1 + row_offset
        details_str = _json_dumps(e.details) if e.details else ""

        ws.cell(row=r, column=1, value=e.occurred_at.strftime("%Y-%m-%d %H:%M:%S"))
        ws.cell(row=r, column=2, value=e.source)
        ws.cell(row=r, column=3, value=e.severity)
        ws.cell(row=r, column=4, value=e.event_type)
        ws.cell(row=r, column=5, value=e.title)
        ws.cell(row=r, column=6, value=e.description or "")
        ws.cell(row=r, column=7, value=e.entity_name or "")
        ws.cell(row=r, column=8, value=e.actor_name or "")
        ws.cell(row=r, column=9, value=details_str)

    # Ширины
    widths = [20, 12, 10, 16, 40, 60, 30, 24, 60]
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    # Freeze panes на шапке
    ws.freeze_panes = ws.cell(row=2 + row_offset, column=1)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.post("/export.xlsx")
async def export_audit_xlsx(
        payload: AuditExportRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Выгружает события аудита в xlsx по тем же фильтрам,
    что и /log (Итерация 16.4).

    Возвращает StreamingResponse с Content-Disposition: attachment.
    """
    # Принудительно ставим limit = max_rows (защита от гигантских выгрузок)
    spec = payload.filters.model_copy(update={"limit": payload.max_rows})

    events = await _collect_events(db, org_id, spec)

    xlsx_bytes = _build_xlsx(events, title=payload.title)

    filename = f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )