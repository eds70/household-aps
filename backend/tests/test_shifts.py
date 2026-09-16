# backend/tests/test_shifts.py
"""
Тесты модуля shifts и API сменного планирования (Итерация 3).
"""

import pytest
from datetime import datetime, timezone, timedelta
from tests.fixtures import tz_case
from app.scheduler.shifts import (
    Shift,
    find_shift_for_time,
    find_shift_by_id,
    get_shift_starting_at,
    group_tasks_by_shift,
    find_carryover_tasks,
    get_previous_working_shift,
)


TZ = timezone(timedelta(hours=3))


def _make_shifts():
    """Собирает Shift-объекты из фикстуры."""
    return [
        Shift(
            id=f"shift_{i:02d}",
            name=s["name"],
            starts_at=s["starts_at"],
            ends_at=s["ends_at"],
            is_working=s["is_working"],
            comment=s["comment"],
        )
        for i, s in enumerate(tz_case.SHIFTS, start=1)
    ]


# ==========================================
# ТЕСТЫ: ФИКСТУРА
# ==========================================

def test_shifts_count():
    """30 смен в сентябре."""
    assert len(tz_case.SHIFTS) == 30
    assert len(tz_case.SHIFTS) == tz_case.EXPECTED_SHIFTS["total"]


def test_working_shifts_count():
    """22 рабочих смены (без выходных)."""
    working = [s for s in tz_case.SHIFTS if s["is_working"]]
    assert len(working) == 22
    assert len(working) == tz_case.EXPECTED_SHIFTS["working"]


def test_shift_duration_is_12h():
    """Смена длится 12 часов."""
    for s in tz_case.SHIFTS:
        duration = (s["ends_at"] - s["starts_at"]).total_seconds() / 3600
        assert duration == 12.0


def test_shift_starts_at_8am():
    """Смена начинается в 08:00."""
    for s in tz_case.SHIFTS:
        assert s["starts_at"].hour == 8
        assert s["starts_at"].minute == 0


def test_weekends_are_not_working():
    """Суббота и воскресенье — нерабочие смены."""
    for s in tz_case.SHIFTS:
        dow = s["starts_at"].weekday()
        if dow >= 5:  # сб или вс
            assert s["is_working"] is False, f"{s['name']} должен быть выходным"
        else:
            assert s["is_working"] is True, f"{s['name']} должен быть рабочим"


# ==========================================
# ТЕСТЫ: ПОИСК СМЕНЫ
# ==========================================

def test_find_shift_for_time():
    """Находим смену по моменту времени."""
    shifts = _make_shifts()
    # 15.09.2026 10:00 попадает в смену 15.09
    dt = datetime(2026, 9, 15, 10, 0, 0, tzinfo=TZ)
    shift = find_shift_for_time(shifts, dt)
    assert shift is not None
    assert "15.09.2026" in shift.name


def test_find_shift_for_time_not_found():
    """Момент вне смен (ночь) — не находим."""
    shifts = _make_shifts()
    # 22:00 — после смены
    dt = datetime(2026, 9, 15, 22, 0, 0, tzinfo=TZ)
    shift = find_shift_for_time(shifts, dt)
    assert shift is None


def test_find_shift_by_id():
    """Поиск смены по ID."""
    shifts = _make_shifts()
    shift = find_shift_by_id(shifts, "shift_15")
    assert shift is not None
    assert "15.09.2026" in shift.name


def test_find_shift_by_id_not_found():
    """Несуществующий ID."""
    shifts = _make_shifts()
    shift = find_shift_by_id(shifts, "nonexistent")
    assert shift is None


def test_get_shift_starting_at():
    """Находим смену по дате."""
    shifts = _make_shifts()
    dt = datetime(2026, 9, 20, 0, 0, 0, tzinfo=TZ)
    shift = get_shift_starting_at(shifts, dt)
    assert shift is not None
    assert shift.starts_at.day == 20


# ==========================================
# ТЕСТЫ: ГРУППИРОВКА ЗАДАЧ
# ==========================================

def test_group_tasks_by_shift():
    """Группировка задач по shift_id."""
    shifts = _make_shifts()

    tasks = [
        {"id": "t1", "shift_id": "shift_01", "start": datetime(2026, 9, 1, 9, 0, tzinfo=TZ)},
        {"id": "t2", "shift_id": "shift_01", "start": datetime(2026, 9, 1, 10, 0, tzinfo=TZ)},
        {"id": "t3", "shift_id": "shift_02", "start": datetime(2026, 9, 2, 9, 0, tzinfo=TZ)},
    ]

    groups = group_tasks_by_shift(tasks, shifts)
    assert "shift_01" in groups
    assert "shift_02" in groups
    assert len(groups["shift_01"]) == 2
    assert len(groups["shift_02"]) == 1


def test_group_tasks_auto_detect_shift():
    """Если shift_id не указан — определяется по start."""
    shifts = _make_shifts()

    tasks = [
        {"id": "t1", "start": datetime(2026, 9, 15, 10, 0, tzinfo=TZ)},
    ]

    groups = group_tasks_by_shift(tasks, shifts)
    # shift_15 — 15.09.2026
    assert "shift_15" in groups
    assert len(groups["shift_15"]) == 1


# ==========================================
# ТЕСТЫ: ПЕРЕХОДЯЩИЕ ЗАДАНИЯ
# ==========================================

def test_find_carryover_tasks():
    """Переходящие: shift_id = prev, actual_end = None."""
    shifts = _make_shifts()

    tasks = [
        {"id": "t1", "shift_id": "shift_01", "actual_end": None},
        {"id": "t2", "shift_id": "shift_01", "actual_end": datetime(2026, 9, 1, 15, 0, tzinfo=TZ)},
        {"id": "t3", "shift_id": "shift_02", "actual_end": None},
    ]

    carryover = find_carryover_tasks("shift_01", tasks, shifts)
    assert len(carryover) == 1
    assert carryover[0]["id"] == "t1"


def test_get_previous_working_shift():
    """Предыдущая рабочая смена (не выходной)."""
    shifts = _make_shifts()

    # shift_07 = 07.09.2026 — понедельник (рабочий)
    # shift_05 = 05.09.2026 — суббота (выходной)
    # shift_06 = 06.09.2026 — воскресенье (выходной)
    # Предыдущая РАБОЧАЯ смена — shift_04 = 04.09.2026 (пятница)
    prev = get_previous_working_shift(shifts, "shift_07")
    assert prev is not None
    assert prev.id == "shift_04"
    assert prev.is_working is True


def test_get_previous_working_shift_first():
    """Для первой смены нет предыдущей."""
    shifts = _make_shifts()
    prev = get_previous_working_shift(shifts, "shift_01")
    assert prev is None

def test_get_previous_working_shift_mid_month():
    """Проверяем переход через выходные в середине месяца."""
    shifts = _make_shifts()

    # shift_12 = 12.09.2026 — суббота (выходной)
    # shift_13 = 13.09.2026 — воскресенье (выходной)
    # shift_14 = 14.09.2026 — понедельник (рабочий)
    # Предыдущая рабочая для 14.09 — 11.09 (пятница) = shift_11
    prev = get_previous_working_shift(shifts, "shift_14")
    assert prev is not None
    assert prev.id == "shift_11"
    assert prev.is_working is True