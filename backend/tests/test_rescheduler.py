# backend/tests/test_rescheduler.py
"""
Тесты модуля rescheduler (Итерация 4).

Итерация 5: фильтрация заблокированных лабораторией партий.

Итерация 9 (A3): тесты переписаны под новую архитектуру.
Раньше Rescheduler клонировал задачи — теперь он запускает
ProductionScheduler.build_schedule() заново с pinned_tasks.

Что тестируем сейчас:
  - TaskSnapshot с op_id.
  - _build_pinned_tasks (гибридная логика: is_pinned + actual_start).
  - _find_affected_batch_ids (DELAY / BREAKDOWN / явные batch_ids).
  - _apply_delay / _apply_qty_change / _apply_breakdown (контрактные).
  - _load_tasks — фильтр is_lab_blocked.
  - RescheduleReason константы.
  - Sanity: diff в reschedule содержит новые поля
    (pinned_count, fallback_used).
"""

import inspect
from datetime import datetime, timezone, timedelta

import pytest

from app.scheduler.rescheduler import (
    Rescheduler,
    RescheduleReason,
    TaskSnapshot,
)
from tests.fixtures import tz_case

TZ = timezone(timedelta(hours=3))


# ==========================================
# ХЕЛПЕР: создание TaskSnapshot
# ==========================================

def _make_task(
        task_id: str,
        batch_id: str = "b1",
        op_id: str = None,
        equipment_id: str = "eq1",
        task_role: str = "REACTOR_OP",
        start_days: int = 0,
        status: str = "PLANNED",
        is_pinned: bool = False,
        actual_start: datetime = None,
) -> TaskSnapshot:
    """
    Создать тестовую задачу.

    Итерация 9: добавлены параметры op_id и actual_start.
    op_id — для A3 pinned (identity задачи в модели).
    actual_start — для гибридной логики pinned (начатые задачи).
    """
    start = datetime(2026, 9, 15, 8, 0, 0, tzinfo=TZ) + timedelta(days=start_days)
    end = start + timedelta(hours=2)
    return TaskSnapshot(
        id=task_id,
        batch_id=batch_id,
        op_id=op_id,
        equipment_id=equipment_id,
        linked_equipment_id=None,
        task_role=task_role,
        planned_start=start,
        planned_end=end,
        actual_start=actual_start,
        actual_end=None,
        status=status,
        is_pinned=is_pinned,
    )


# ==========================================
# ТЕСТЫ: _build_pinned_tasks (гибридная логика, A3)
# ==========================================

def test_pinned_when_is_pinned_true():
    """Задача с is_pinned=True попадает в pinned."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [_make_task("t1", is_pinned=True)]

    pinned = r._build_pinned_tasks(tasks, frozen_before=None)

    assert len(pinned) == 1
    assert pinned[0]["batch_id"] == "b1"
    assert pinned[0]["task_role"] == "REACTOR_OP"


def test_pinned_when_actual_start_set():
    """
    Задача с actual_start IS NOT NULL попадает в pinned.
    Это новая гибридная логика A3.
    """
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [
        _make_task(
            "t1",
            actual_start=datetime(2026, 9, 15, 8, 5, tzinfo=TZ),
        ),
    ]

    pinned = r._build_pinned_tasks(tasks, frozen_before=None)

    assert len(pinned) == 1
    assert pinned[0]["batch_id"] == "b1"


def test_not_pinned_when_only_planned():
    """Задача с planned_start, но без is_pinned и без actual_start — НЕ pinned."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [_make_task("t1")]

    pinned = r._build_pinned_tasks(tasks, frozen_before=None)

    assert len(pinned) == 0


def test_frozen_before_ignored_for_pinned():
    """
    frozen_before НЕ влияет на pinned (новая логика A3).

    Раньше: все задачи до frozen_before были pinned → конфликты
    setup-ограничений → no feasible solution.

    Теперь: frozen_before — только метаданные версии.
    """
    r = Rescheduler(org_id=tz_case.ORG_ID)

    # Задача ДО frozen_before, но без is_pinned/actual_start
    tasks = [_make_task("t1", start_days=0)]

    pinned = r._build_pinned_tasks(
        tasks,
        frozen_before=datetime(2026, 9, 20, 0, 0, tzinfo=TZ),
    )

    assert len(pinned) == 0, (
        "Задача до frozen_before НЕ должна быть pinned — "
        "frozen_before это только метаданные (A3)"
    )


def test_pinned_only_specific_tasks():
    """
    Только задачи с is_pinned=True ИЛИ actual_start попадают в pinned.
    Остальные — игнорируются.
    """
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [
        _make_task("t1"),                               # обычная
        _make_task("t2", is_pinned=True),               # pinned
        _make_task("t3", actual_start=datetime(2026, 9, 15, 9, 0, tzinfo=TZ)),  # started
        _make_task("t4"),                               # обычная
    ]

    pinned = r._build_pinned_tasks(tasks, frozen_before=None)

    assert len(pinned) == 2
    batch_ids = {p["batch_id"] for p in pinned}
    assert batch_ids == {"b1"}  # обе задачи — b1 (по умолчанию в _make_task)


def test_pinned_includes_planned_times():
    """Pinned-задача сохраняет planned_start и planned_end."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    task = _make_task("t1", is_pinned=True)

    pinned = r._build_pinned_tasks([task], frozen_before=None)

    assert len(pinned) == 1
    assert pinned[0]["planned_start"] == task.planned_start
    assert pinned[0]["planned_end"] == task.planned_end


def test_pinned_empty_when_no_tasks():
    """Пустой список задач → пустой pinned."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    pinned = r._build_pinned_tasks([], frozen_before=None)
    assert pinned == []


# ==========================================
# ТЕСТЫ: _find_affected_batch_ids
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


def test_find_affected_empty_changes():
    """Пустой changes → пустой set."""
    r = Rescheduler(org_id=tz_case.ORG_ID)
    tasks = [_make_task("t1", batch_id="b1")]
    affected = r._find_affected_batch_ids(tasks, {})
    assert affected == set()


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
# ТЕСТЫ: ФИЛЬТРАЦИЯ ЗАБЛОКИРОВАННЫХ ПАРТИЙ (Итерация 5)
# ==========================================

def test_load_tasks_query_has_lab_blocked_filter():
    """
    Проверяет, что SQL-запрос _load_tasks содержит фильтр
    по batch.is_lab_blocked.
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler._load_tasks)
    assert "is_lab_blocked" in source, (
        "SQL в _load_tasks должен содержать фильтр is_lab_blocked "
        "(Итерация 5)"
    )
    assert "COALESCE(b.is_lab_blocked, FALSE) = FALSE" in source


# ==========================================
# ТЕСТЫ: КОНТРАКТ RESCHEDULE (A3 — новая архитектура)
# ==========================================

def test_reschedule_calls_production_scheduler():
    """
    Итерация 9 (A3): reschedule() должен вызывать ProductionScheduler
    (реальный пересчет), а не клонировать задачи.
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "ProductionScheduler" in source, (
        "reschedule() должен использовать ProductionScheduler (A3)"
    )
    assert "build_schedule" in source, (
        "reschedule() должен вызывать ProductionScheduler.build_schedule (A3)"
    )
    assert "pinned_tasks" in source, (
        "reschedule() должен передавать pinned_tasks (A3)"
    )


def test_reschedule_calls_schedule_saver():
    """
    Итерация 9 (A3): reschedule() должен сохранять через ScheduleSaver,
    а не вручную через INSERT.
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "ScheduleSaver" in source, (
        "reschedule() должен использовать ScheduleSaver (A3)"
    )
    assert "save_schedule" in source


def test_reschedule_has_fallback():
    """
    Итерация 9 (A3): reschedule() содержит fallback:
    если solver не нашёл решение с pinned — пробует без них.
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "fallback_used" in source, (
        "reschedule() должен логировать fallback_used (A3)"
    )
    assert "pinned_tasks=None" in source, (
        "reschedule() должен пробовать build_schedule(pinned_tasks=None) "
        "как fallback (A3)"
    )


def test_reschedule_diff_has_new_fields():
    """
    Итерация 9 (A3): diff в reschedule содержит новые поля:
    pinned_count, fallback_used, deactivated_versions.
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "pinned_count" in source, "diff должен содержать pinned_count (A3)"
    assert "fallback_used" in source, "diff должен содержать fallback_used (A3)"
    assert "deactivated_versions" in source, (
        "diff должен содержать deactivated_versions (A3)"
    )


def test_reschedule_updates_parent_version_id():
    """
    Итерация 9 (A3): reschedule() устанавливает parent_version_id
    у новой версии (через UPDATE schedule_version).
    """
    from app.scheduler import rescheduler as rescheduler_module

    source = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "UPDATE schedule_version" in source
    assert "parent_version_id" in source
    assert "frozen_before" in source


# ==========================================
# ТЕСТЫ: СОГЛАСОВАННОСТЬ ДАТА-КЛАССОВ
# ==========================================

def test_task_snapshot_has_op_id():
    """
    Итерация 9: TaskSnapshot должен иметь поле op_id
    (используется для pinned-identity).
    """
    task = _make_task("t1", op_id="op_42")
    assert task.op_id == "op_42"


def test_task_snapshot_has_actual_start():
    """TaskSnapshot.actual_start используется в гибридной логике A3."""
    now = datetime(2026, 9, 15, 9, 0, tzinfo=TZ)
    task = _make_task("t1", actual_start=now)
    assert task.actual_start == now


if __name__ == "__main__":
    pytest.main([__file__, "-v"])