# backend/app/scheduler/shift_regenerator.py
"""
Пересоздание смен в таблице shift согласно режиму (Итерация 11).

Вызывается при смене shift_mode через POST /api/v1/settings/shift-mode.

Логика:
  1. Определить интервалы смен по режиму (или взять shift_intervals из настроек).
  2. Удалить старые смены в диапазоне [date_from, date_to].
  3. Для каждой даты и каждого интервала создать смену.
  4. Выходные (сб, вс) — is_working = FALSE.
  5. Сбросить shift_id в scheduled_task для затронутых смен
     (старые UUID невалидны после пересоздания).
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.scheduler.shift_regenerator")

MSK = ZoneInfo("Europe/Moscow")

# ==========================================
# Диапазон по умолчанию: 90 дней от 2026-09-01
# ==========================================
DEFAULT_START_DATE = date(2026, 9, 1)
DEFAULT_DAYS_AHEAD = 90


# ==========================================
# Определение интервалов по режиму
# ==========================================

def get_intervals_for_mode(mode: str) -> Tuple[List[Dict[str, str]], int]:
    """
    Возвращает (intervals, duration_hours) для режима.

    Режимы:
      - 1x8:  одна 8-часовая смена 08:00–16:00
      - 3x8:  три смены 00–08, 08–16, 16–00
      - 2x12: две смены 08–20, 20–08

    Args:
        mode: "1x8" | "3x8" | "2x12"

    Returns:
        (intervals, duration_hours)
        intervals: список словарей {"start": "HH:MM", "end": "HH:MM"}
        duration_hours: длительность смены в часах
    """
    if mode == "1x8":
        return [{"start": "08:00", "end": "16:00"}], 8

    if mode == "3x8":
        return [
            {"start": "00:00", "end": "08:00"},
            {"start": "08:00", "end": "16:00"},
            {"start": "16:00", "end": "00:00"},
        ], 8

    # 2x12 — по умолчанию
    return [
        {"start": "08:00", "end": "20:00"},
        {"start": "20:00", "end": "08:00"},
    ], 12


# ==========================================
# Основная функция пересоздания смен
# ==========================================

async def regenerate_shifts(
        session: AsyncSession,
        org_id: UUID,
        mode: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        reset_shift_ids: bool = True,
) -> Dict[str, Any]:
    """
    Пересоздаёт смены в таблице shift согласно режиму.

    Args:
        session: сессия БД.
        org_id: UUID организации.
        mode: "1x8" | "3x8" | "2x12".
        date_from: начало диапазона (по умолчанию 2026-09-01).
        date_to: конец диапазона (по умолчанию date_from + 90 дней).
        reset_shift_ids: сбросить ли shift_id в scheduled_task.

    Returns:
        Статистика:
          {
            "mode": str,
            "deleted": int,
            "created": int,
            "reset_shift_ids": int,
            "date_from": str,
            "date_to": str,
            "days": int,
            "intervals": list,
            "duration_hours": int,
          }
    """
    # ==========================================
    # 1. Определяем параметры
    # ==========================================
    if date_from is None:
        date_from = DEFAULT_START_DATE
    if date_to is None:
        date_to = date_from + timedelta(days=DEFAULT_DAYS_AHEAD)

    intervals, duration_hours = get_intervals_for_mode(mode)

    logger.info(
        f"[regenerate_shifts] START: org={str(org_id)[:8]} mode={mode} "
        f"range=[{date_from}, {date_to}] intervals={len(intervals)}"
    )

    # ==========================================
    # 2. Удалить старые смены в диапазоне
    # ==========================================
    delete_result = await session.execute(
        text("""
            DELETE FROM shift
            WHERE organization_id = :org_id
              AND (starts_at AT TIME ZONE 'Europe/Moscow')::date >= :date_from
              AND (starts_at AT TIME ZONE 'Europe/Moscow')::date <= :date_to        
        """),
        {
            "org_id": org_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
    deleted_count = delete_result.rowcount or 0

    logger.info(f"[regenerate_shifts] Удалено старых смен: {deleted_count}")

    # ==========================================
    # 3. Создать новые смены
    # ==========================================
    created_count = 0
    current_date = date_from

    # Буфер для batch-insert (быстрее, чем по одной)
    batch_rows: List[Dict[str, Any]] = []

    while current_date <= date_to:
        dow = current_date.weekday()  # 0=пн, 5=сб, 6=вс
        is_weekend = dow >= 5

        for interval in intervals:
            start_time_str = interval["start"]
            end_time_str = interval["end"]

            start_h, start_m = map(int, start_time_str.split(":"))
            end_h, end_m = map(int, end_time_str.split(":"))

            # Начало в МСК
            starts_at = datetime(
                current_date.year,
                current_date.month,
                current_date.day,
                start_h,
                start_m,
                tzinfo=MSK,
            )

            # Конец — может быть на следующий день
            if end_h * 60 + end_m <= start_h * 60 + start_m:
                end_date = current_date + timedelta(days=1)
            else:
                end_date = current_date

            ends_at = datetime(
                end_date.year,
                end_date.month,
                end_date.day,
                end_h,
                end_m,
                tzinfo=MSK,
            )

            # Имя смены
            if len(intervals) == 1:
                name = f"Смена {current_date.strftime('%d.%m.%Y')}"
            else:
                name = (
                    f"Смена {current_date.strftime('%d.%m.%Y')} "
                    f"{start_time_str}-{end_time_str}"
                )

            if is_weekend:
                name += " (выходной)"

            batch_rows.append({
                "org_id": org_id,
                "name": name,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "is_working": not is_weekend,
                "comment": "Рабочая смена" if not is_weekend else "Выходной",
            })

        current_date += timedelta(days=1)

    # Пакетная вставка
    for row in batch_rows:
        await session.execute(
            text("""
                INSERT INTO shift
                    (organization_id, name, starts_at, ends_at,
                     is_working, comment)
                VALUES
                    (:org_id, :name, :starts_at, :ends_at,
                     :is_working, :comment)
            """),
            row,
        )
        created_count += 1

    logger.info(f"[regenerate_shifts] Создано новых смен: {created_count}")

    # ==========================================
    # 4. Сбросить shift_id в scheduled_task
    # ==========================================
    reset_count = 0
    if reset_shift_ids:
        reset_result = await session.execute(
            text("""
                UPDATE scheduled_task
                SET shift_id = NULL
                WHERE organization_id = :org_id
                  AND shift_id IS NOT NULL
            """),
            {"org_id": org_id},
        )
        reset_count = reset_result.rowcount or 0
        logger.info(
            f"[regenerate_shifts] Сброшено shift_id в задачах: {reset_count}"
        )

    # ==========================================
    # 5. Flush (без commit) — Итерация 12 (fix)
    # ==========================================
    # Раньше делали commit() — но это ломает транзакцию WhatIfRunner,
    # который применяет изменения в транзакции №1 и затем откатывает её.
    #
    # Используем flush() — данные видны внутри текущей сессии (для scheduler),
    # но не коммитятся в БД до явного commit() вызывающей стороны.
    #
    # Коммит делают вызывающие:
    #   - API POST /settings/shift-mode (в settings.py) — после вызова.
    #   - WhatIfRunner (в run_scenario) — НЕ коммитит для транзакции №1.
    await session.flush()

    days_count = (date_to - date_from).days + 1

    result = {
        "mode": mode,
        "deleted": deleted_count,
        "created": created_count,
        "reset_shift_ids": reset_count,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "days": days_count,
        "intervals": intervals,
        "duration_hours": duration_hours,
    }

    logger.info(f"[regenerate_shifts] DONE: {result}")

    return result