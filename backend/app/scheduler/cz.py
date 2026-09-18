# backend/app/scheduler/cz.py
"""
Модуль интеграции с Честным Знаком (Итерация 8).

Содержит:
  - resolve_batch_for_scan: fallback-сопоставление скана с партией.
  - recalc_batch_cz_status: пересчёт статуса маркировки партии.
  - compute_planned_qty: расчёт ожидаемого количества бутылок по партии.

Логика сопоставления скана с партией:
  1. Если передан batch_id — используем его (с проверкой org).
  2. Если передан task_id — берём batch_id из задачи.
  3. Иначе — ищем по line_code + scanned_at среди активных LINE_FILL задач.
  4. Если не нашли — скан остаётся «сиротой» (batch_id = NULL).

Логика статуса маркировки:
  - PENDING       — 0 сканов.
  - IN_PROGRESS   — 0 < marked / planned < threshold.
  - COMPLETED     — marked / planned >= threshold.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


Number = Union[int, float, Decimal]


def _to_float(value: Any, default: float = 0.0) -> float:
    """Безопасно приводит значение к float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ==========================================
# СОПОСТАВЛЕНИЕ СКАНА С ПАРТИЕЙ
# ==========================================

async def resolve_batch_for_scan(
        session: AsyncSession,
        org_id: UUID,
        batch_id: Optional[UUID],
        task_id: Optional[UUID],
        line_code: Optional[str],
        scanned_at: datetime,
) -> Tuple[Optional[UUID], Optional[UUID]]:
    """
    Определяет, к какой партии и задаче относится скан.

    Возвращает: (batch_id, scheduled_task_id).
    Если batch_id передан явно — возвращаем его.
    Если task_id — берём batch_id из задачи.
    Если только line_code — ищем активную LINE_FILL задачу.
    """
    # 1. Явно передан batch_id
    if batch_id is not None:
        check = await session.execute(
            text("""
                SELECT id FROM batch
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {"batch_id": batch_id, "org_id": org_id},
        )
        if check.fetchone():
            return batch_id, task_id
        log_with_context(
            logger, logging.WARNING,
            f"batch_id={batch_id} не найден в БД — пробую fallback",
            stage="cz_resolve", org_id=str(org_id),
        )

    # 2. Явно передан task_id — берём batch_id из задачи
    if task_id is not None:
        check = await session.execute(
            text("""
                SELECT batch_id FROM scheduled_task
                WHERE id = :task_id AND organization_id = :org_id
            """),
            {"task_id": task_id, "org_id": org_id},
        )
        row = check.fetchone()
        if row:
            return row.batch_id, task_id
        log_with_context(
            logger, logging.WARNING,
            f"task_id={task_id} не найден в БД — пробую fallback",
            stage="cz_resolve", org_id=str(org_id),
        )

    # 3. Fallback: ищем по line_code + время
    if line_code:
        # Ищем активную LINE_FILL задачу на этой линии
        # Окно поиска: ±2 часа от scanned_at (бутылку могут сканировать
        # чуть раньше или позже по плану)
        window_start = scanned_at - timedelta(hours=2)
        window_end = scanned_at + timedelta(hours=2)

        result = await session.execute(
            text("""
                SELECT st.id AS task_id, st.batch_id
                FROM scheduled_task st
                JOIN equipment e ON e.id = st.equipment_id
                WHERE st.organization_id = :org_id
                  AND e.code = :line_code
                  AND st.task_role = 'LINE_FILL'
                  AND st.planned_start <= :window_end
                  AND st.planned_end >= :window_start
                ORDER BY
                    ABS(EXTRACT(EPOCH FROM (st.planned_start - :scanned_at)))
                LIMIT 1
            """),
            {
                "org_id": org_id,
                "line_code": line_code,
                "window_start": window_start,
                "window_end": window_end,
                "scanned_at": scanned_at,
            },
        )
        row = result.fetchone()
        if row:
            log_with_context(
                logger, logging.INFO,
                f"Fallback-сопоставление: line={line_code} → "
                f"task={str(row.task_id)[:8]}, batch={str(row.batch_id)[:8]}",
                stage="cz_resolve", org_id=str(org_id),
            )
            return row.batch_id, row.task_id

    # 4. Не удалось сопоставить — скан «сирота»
    log_with_context(
        logger, logging.WARNING,
        f"Скан не сопоставлен: line={line_code}, scanned_at={scanned_at}",
        stage="cz_resolve", org_id=str(org_id),
    )
    return None, None


# ==========================================
# РАСЧЁТ ОЖИДАЕМОГО КОЛИЧЕСТВА БУТЫЛОК
# ==========================================

async def compute_planned_qty(
        session: AsyncSession,
        org_id: UUID,
        batch_id: UUID,
) -> Optional[float]:
    """
    Считает ожидаемое количество бутылок (ГП) по партии.

    Логика:
      - Находим order_id партии.
      - Находим ГП этого заказа (product через production_order).
      - Считаем: bottles = volume_kg / bottle_volume_l.
      - bottle_volume_l берём у ГП (product.bottle_volume_l).

    Возвращает None, если не удалось посчитать.
    """
    result = await session.execute(
        text("""
            SELECT
                b.volume_kg,
                gp.bottle_volume_l
            FROM batch b
            JOIN production_order po ON po.id = b.order_id
            JOIN product gp ON gp.id = po.product_id
            WHERE b.id = :batch_id
              AND b.organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        return None

    volume_kg = _to_float(row.volume_kg, 0.0)
    bottle_volume_l = _to_float(row.bottle_volume_l, 0.0)

    if volume_kg <= 0 or bottle_volume_l <= 0:
        return None

    return volume_kg / bottle_volume_l


# ==========================================
# ПЕРЕСЧЁТ СТАТУСА МАРКИРОВКИ ПАРТИИ
# ==========================================

async def recalc_batch_cz_status(
        session: AsyncSession,
        org_id: UUID,
        batch_id: UUID,
        threshold: float,
) -> Dict[str, Any]:
    """
    Пересчитывает cz_status партии на основе cz_marked_qty / planned_qty.

    Возвращает dict с актуальным состоянием:
      {
        "batch_id": str,
        "cz_status": str,
        "marked_qty": float,
        "planned_qty": Optional[float],
        "progress_percent": float,
      }
    """
    # Текущее состояние
    result = await session.execute(
        text("""
            SELECT cz_marked_qty, cz_status
            FROM batch
            WHERE id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        return {
            "batch_id": str(batch_id),
            "cz_status": "PENDING",
            "marked_qty": 0.0,
            "planned_qty": None,
            "progress_percent": 0.0,
        }

    marked_qty = _to_float(row.cz_marked_qty, 0.0)
    planned_qty = await compute_planned_qty(session, org_id, batch_id)

    # Определяем новый статус
    if planned_qty is None or planned_qty <= 0:
        # Не можем посчитать план — оставляем IN_PROGRESS, если есть сканы
        new_status = "IN_PROGRESS" if marked_qty > 0 else "PENDING"
        progress_percent = 0.0
    else:
        progress_percent = min(100.0, (marked_qty / planned_qty) * 100.0)

        if marked_qty <= 0:
            new_status = "PENDING"
        elif (marked_qty / planned_qty) >= threshold:
            new_status = "COMPLETED"
        else:
            new_status = "IN_PROGRESS"

    # Обновляем статус, если изменился
    if new_status != (row.cz_status or "PENDING"):
        await session.execute(
            text("""
                UPDATE batch
                SET cz_status = :status
                WHERE id = :batch_id AND organization_id = :org_id
            """),
            {
                "status": new_status,
                "batch_id": batch_id,
                "org_id": org_id,
            },
        )
        log_with_context(
            logger, logging.INFO,
            f"cz_status партии {str(batch_id)[:8]}: "
            f"{row.cz_status} → {new_status} "
            f"({marked_qty:.0f} / {planned_qty if planned_qty else '?'} шт.)",
            stage="cz_recalc", org_id=str(org_id),
        )

    return {
        "batch_id": str(batch_id),
        "cz_status": new_status,
        "marked_qty": marked_qty,
        "planned_qty": planned_qty,
        "progress_percent": progress_percent,
    }


# ==========================================
# ПОЛУЧЕНИЕ ПРОГРЕССА ПАРТИИ
# ==========================================

async def get_batch_progress(
        session: AsyncSession,
        org_id: UUID,
        batch_id: UUID,
        threshold: float,
) -> Dict[str, Any]:
    """
    Возвращает полную информацию о прогрессе маркировки партии.

    Используется эндпоинтом GET /api/v1/cz/batch/{id}/progress.
    """
    result = await session.execute(
        text("""
            SELECT
                b.id, b.product_id, b.volume_kg,
                b.cz_marked_qty, b.cz_status, b.cz_last_scan_at,
                p.code AS product_code, p.name AS product_name
            FROM batch b
            LEFT JOIN product p ON p.id = b.product_id
            WHERE b.id = :batch_id AND b.organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        return {}

    marked_qty = _to_float(row.cz_marked_qty, 0.0)
    planned_qty = await compute_planned_qty(session, org_id, batch_id)

    if planned_qty and planned_qty > 0:
        progress_percent = min(100.0, (marked_qty / planned_qty) * 100.0)
    else:
        progress_percent = 0.0

    # Количество сканов
    scans_result = await session.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM cz_scan_log
            WHERE batch_id = :batch_id AND organization_id = :org_id
        """),
        {"batch_id": batch_id, "org_id": org_id},
    )
    scans_row = scans_result.fetchone()
    scans_count = int(scans_row.cnt) if scans_row else 0

    return {
        "batch_id": row.id,
        "product_id": row.product_id,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "planned_qty": planned_qty,
        "marked_qty": marked_qty,
        "progress_percent": progress_percent,
        "cz_status": row.cz_status or "PENDING",
        "threshold": threshold,
        "last_scan_at": row.cz_last_scan_at,
        "scans_count": scans_count,
    }