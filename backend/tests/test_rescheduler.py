# backend/tests/test_rescheduler.py
"""
Тесты модуля rescheduler (Итерация 4).

Итерация 5: тесты фильтрации заблокированных лабораторией партий.
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.scheduler.rescheduler import (
    Rescheduler,
    RescheduleReason,
    TaskSnapshot,
)
from tests.fixtures import tz_case

TZ = timezone(timedelta(hours=3))


def _make_task(
        task_id: str,
        batch_id: str = "b1",
        equipment_id: str = "eq1",
        start_days: int = 0,
        status: str = "PLANNED",
        is_pinned: bool = False,
) -> TaskSnapshot:
    """Создать тестовую задачу."""
    start = datetime(2026, 9, 15, 8, 0, 0, tzinfo=TZ) + timedelta(days=start_days)
    end = start + timedelta(hours=2)
    return TaskSnapshot(
        id=task_id,
        batch_id=batch_id,
        equipment_id=equipment_id,
        linked_equipment_id=None,
        task_role="REACTOR_OP",
        planned_start=start,
        planned_end=end,
        actual_start=None,
        actual_end=None,
        status=status,
        is_pinned=is_pinned,
    )


# ==========================================
# ТЕСТЫ: IS_FROZEN
# ==========================================

def test_is_frozen_by_pin():
    """Задача с is_pinned=True заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", is_pinned=True)
    assert r._is_frozen(task, frozen_before=None) is True


def test_is_frozen_by_status_done():
    """Задача со статусом DONE заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", status="DONE")
    assert r._is_frozen(task, frozen_before=None) is True


def test_is_frozen_by_status_cancelled():
    """Задача со статусом CANCELLED заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", status="CANCELLED")
    assert r._is_frozen(task, frozen_before=None) is True


def test_is_frozen_by_frozen_before():
    """Задача началась до frozen_before — заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", start_days=0)
    frozen = datetime(2026, 9, 16, 0, 0, 0, tzinfo=TZ)
    assert r._is_frozen(task, frozen_before=frozen) is True


def test_not_frozen_when_after():
    """Задача после frozen_before — не заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", start_days=5)
    frozen = datetime(2026, 9, 16, 0, 0, 0, tzinfo=TZ)
    assert r._is_frozen(task, frozen_before=frozen) is False


def test_not_frozen_when_no_pin_no_frozen():
    """Обычная задача не заморожена."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1")
    assert r._is_frozen(task, frozen_before=None) is False


# ==========================================
# ТЕСТЫ: FIND_AFFECTED_BATCH_IDS
# ==========================================

def test_find_affected_by_delayed_task():
    """DELAY — затронута партия задержанной задачи."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [
        _make_task("t1", batch_id="b1"),
        _make_task("t2", batch_id="b2"),
        _make_task("t3", batch_id="b3"),
    ]
    affected = r._find_affected_batch_ids(tasks, {"delayed_task_id": "t2"})
    assert affected == {"b2"}


def test_find_affected_by_breakdown():
    """BREAKDOWN — затронуты все партии на сломанном оборудовании."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [
        _make_task("t1", batch_id="b1", equipment_id="eq1"),
        _make_task("t2", batch_id="b2", equipment_id="eq2"),
        _make_task("t3", batch_id="b3", equipment_id="eq1"),
        _make_task("t4", batch_id="b4", equipment_id="eq2"),
    ]
    affected = r._find_affected_batch_ids(tasks, {"broken_equipment_id": "eq1"})
    assert affected == {"b1", "b3"}


def test_find_affected_by_explicit_batch_ids():
    """QTY_CHANGE — явно указанные партии."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [
        _make_task("t1", batch_id="b1"),
        _make_task("t2", batch_id="b2"),
    ]
    affected = r._find_affected_batch_ids(tasks, {"affected_batch_ids": ["b2"]})
    assert affected == {"b2"}


def test_find_affected_no_changes():
    """Без изменений — ничего не затронуто."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [_make_task("t1", batch_id="b1")]
    affected = r._find_affected_batch_ids(tasks, {})
    assert affected == set()


# ==========================================
# ТЕСТЫ: FIND_SHIFT_ID
# ==========================================

def test_find_shift_id_exact():
    """Точное попадание в смену."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    shifts = [
        {
            "id": "shift1",
            "starts_at": datetime(2026, 9, 15, 8, 0, 0, tzinfo=TZ),
            "ends_at": datetime(2026, 9, 15, 20, 0, 0, tzinfo=TZ),
        },
    ]
    dt = datetime(2026, 9, 15, 10, 0, 0, tzinfo=TZ)
    assert r._find_shift_id(shifts, dt) == "shift1"


def test_find_shift_id_fallback():
    """Fallback — ближайшая смена по starts_at."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    shifts = [
        {
            "id": "shift1",
            "starts_at": datetime(2026, 9, 15, 8, 0, 0, tzinfo=TZ),
            "ends_at": datetime(2026, 9, 15, 20, 0, 0, tzinfo=TZ),
        },
        {
            "id": "shift2",
            "starts_at": datetime(2026, 9, 16, 8, 0, 0, tzinfo=TZ),
            "ends_at": datetime(2026, 9, 16, 20, 0, 0, tzinfo=TZ),
        },
    ]
    dt = datetime(2026, 9, 15, 22, 0, 0, tzinfo=TZ)
    result = r._find_shift_id(shifts, dt)
    assert result == "shift2"


def test_find_shift_id_no_shifts():
    """Нет смен — None."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    assert r._find_shift_id([], datetime.now()) is None


# ==========================================
# ТЕСТЫ: RESCHEDULE REASONS
# ==========================================

def test_reschedule_reason_constants():
    """Константы RescheduleReason."""
    assert RescheduleReason.DELAY == "DELAY"
    assert RescheduleReason.BREAKDOWN == "BREAKDOWN"
    assert RescheduleReason.QTY_CHANGE == "QTY_CHANGE"
    assert RescheduleReason.MANUAL == "MANUAL"


# ==========================================
# ТЕСТЫ: ФИКСТУРА СЦЕНАРИЕВ
# ==========================================

def test_reschedule_scenarios_fixture():
    """Проверяем, что в фикстуре есть сценарии перепланирования."""
    from tests.fixtures import tz_expected
    assert len(tz_expected.RESCHEDULE_SCENARIOS) == 3

    names = [s["name"] for s in tz_expected.RESCHEDULE_SCENARIOS]
    assert "Задержка операции на 2 часа" in names
    assert "Аварийная остановка Р4 (25-28.09)" in names
    assert "Увеличение объёма заказа на 50%" in names


def test_reschedule_delay_scenario():
    """Сценарий задержки."""
    from tests.fixtures import tz_expected
    delay_scenario = next(
        s for s in tz_expected.RESCHEDULE_SCENARIOS if s["reason"] == "delay"
    )
    assert delay_scenario["params"]["delay_minutes"] == 120


def test_reschedule_breakdown_scenario():
    """Сценарий поломки."""
    from tests.fixtures import tz_expected
    breakdown = next(
        s for s in tz_expected.RESCHEDULE_SCENARIOS if s["reason"] == "breakdown"
    )
    assert breakdown["params"]["equipment_code"] == "REACTOR_4"


def test_reschedule_qty_change_scenario():
    """Сценарий изменения объёма."""
    from tests.fixtures import tz_expected
    qty_change = next(
        s for s in tz_expected.RESCHEDULE_SCENARIOS if s["reason"] == "qty_change"
    )
    assert qty_change["params"]["new_qty"] == 30000


# ==========================================
# ИТЕРАЦИЯ 5: ТЕСТЫ ФИЛЬТРАЦИИ ЗАБЛОКИРОВАННЫХ ПАРТИЙ
# ==========================================

def test_load_tasks_query_has_lab_blocked_filter():
    """
    Проверяет, что SQL-запрос _load_tasks содержит фильтр
    по batch.is_lab_blocked.
    """
    import inspect
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler._load_tasks)
    assert "is_lab_blocked" in source, (
        "SQL в _load_tasks должен содержать фильтр is_lab_blocked "
        "(Итерация 5)"
    )
    assert "COALESCE(b.is_lab_blocked, FALSE) = FALSE" in source


def test_rescheduler_has_count_blocked_tasks_method():
    """Метод _count_blocked_tasks должен существовать."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    assert hasattr(r, "_count_blocked_tasks")
    assert callable(r._count_blocked_tasks)


def test_reschedule_result_diff_has_skipped_fields():
    """
    Проверяет, что в исходнике reschedule() в diff упоминаются
    поля skipped_blocked_tasks и skipped_blocked_batches.
    """
    import inspect
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "skipped_blocked_tasks" in source
    assert "skipped_blocked_batches" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])