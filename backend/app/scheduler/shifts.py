# backend/app/scheduler/shifts.py
"""
Модуль работы со сменами (Итерация 3).

Функции:
  - Загрузка смен из БД
  - Определение смены для задачи по времени
  - Группировка задач по сменам
  - Поиск переходящих заданий
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from uuid import UUID
from decimal import Decimal

from .logging_config import setup_scheduler_logging, log_with_context


logger = setup_scheduler_logging(level=logging.INFO)


def _to_datetime(value: Any) -> Optional[datetime]:
    """Безопасно приводит значение к datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    return None


@dataclass
class Shift:
    """Смена."""
    id: str
    name: str
    starts_at: datetime
    ends_at: datetime
    is_working: bool
    comment: Optional[str] = None

    @property
    def duration_hours(self) -> float:
        return (self.ends_at - self.starts_at).total_seconds() / 3600

    def contains(self, dt: datetime) -> bool:
        """Попадает ли момент времени в смену (с учётом таймзон)."""
        # Приводим к одному типу (naive/aware)
        if dt.tzinfo is not None and self.starts_at.tzinfo is None:
            dt = dt.replace(tzinfo=None)
        elif dt.tzinfo is None and self.starts_at.tzinfo is not None:
            self_start = self.starts_at.replace(tzinfo=None)
            self_end = self.ends_at.replace(tzinfo=None)
            return self_start <= dt <= self_end
        return self.starts_at <= dt <= self.ends_at


def find_shift_for_time(shifts: List[Shift], dt: datetime) -> Optional[Shift]:
    """Находит смену, в которую попадает момент времени."""
    for shift in shifts:
        if shift.contains(dt):
            return shift
    return None


def find_shift_by_id(shifts: List[Shift], shift_id: str) -> Optional[Shift]:
    """Находит смену по ID."""
    for shift in shifts:
        if shift.id == shift_id:
            return shift
    return None


def get_shift_starting_at(shifts: List[Shift], date: datetime) -> Optional[Shift]:
    """
    Находит смену, которая начинается в указанный день.
    Полезно для страницы мастера (выбор смены по дате).
    """
    target_date = date.date() if isinstance(date, datetime) else date
    for shift in shifts:
        if shift.starts_at.date() == target_date:
            return shift
    return None


def group_tasks_by_shift(
        tasks: List[Dict],
        shifts: List[Shift],
) -> Dict[str, List[Dict]]:
    """
    Группирует задачи по shift_id.
    Если у задачи нет shift_id — определяет по start.
    """
    result: Dict[str, List[Dict]] = {}

    for task in tasks:
        shift_id = task.get("shift_id")

        if not shift_id:
            start = _to_datetime(task.get("start"))
            if start:
                shift = find_shift_for_time(shifts, start)
                if shift:
                    shift_id = shift.id

        if shift_id:
            result.setdefault(str(shift_id), []).append(task)

    return result


def find_carryover_tasks(
        prev_shift_id: str,
        tasks: List[Dict],
        shifts: List[Shift],
) -> List[Dict]:
    """
    Переходящие задания из предыдущей смены:
    задачи, у которых shift_id = prev_shift_id, но actual_end = None.
    """
    carryover = []
    for task in tasks:
        if str(task.get("shift_id") or "") != str(prev_shift_id):
            continue
        if task.get("actual_end") is None:
            carryover.append(task)
    return carryover


def get_previous_working_shift(
        shifts: List[Shift],
        current_shift_id: str,
) -> Optional[Shift]:
    """Находит предыдущую рабочую смену (не выходной)."""
    sorted_shifts = sorted(shifts, key=lambda s: s.starts_at)

    current_idx = None
    for i, s in enumerate(sorted_shifts):
        if s.id == current_shift_id:
            current_idx = i
            break

    if current_idx is None:
        return None

    for i in range(current_idx - 1, -1, -1):
        if sorted_shifts[i].is_working:
            return sorted_shifts[i]

    return None