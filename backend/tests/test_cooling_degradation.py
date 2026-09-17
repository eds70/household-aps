# backend/tests/test_cooling_degradation.py
"""
Тесты деградации охлаждения (Итерация 7 + hotfix).

Проверяют:
  1. Feature-флаг enable_cooling_degradation.
  2. Модель b_slow ⟺ пересечение cooling-интервалов.
  3. Длительности fast = base, slow = base × factor.
  4. Capacity зоны охлаждения (2).
  5. API /gantt/ и /shift/ возвращают cooling_mode.

ВАЖНО (fix теста): все cooling-задачи создаются в ОДНОЙ CpModel.
Раньше каждая задача создавалась в изолированной модели, из-за чего
solver решал только первую, а переменные остальных оставались
неопределёнными. Отсюда ложные срабатывания тестов.
"""

from datetime import timedelta, timezone

import pytest

from app.scheduler.feature_flags import FeatureFlags

TZ = timezone(timedelta(hours=3))


# ==========================================
# ТЕСТЫ: FEATURE-ФЛАГ
# ==========================================

def test_feature_flag_cooling_degradation_enabled():
    """Флаг включён."""
    flags = FeatureFlags({"enable_cooling_degradation": "true"})
    assert flags.enable_cooling_degradation is True


def test_feature_flag_cooling_degradation_disabled():
    """Флаг выключен (по умолчанию)."""
    flags = FeatureFlags({})
    assert flags.enable_cooling_degradation is False


def test_cooling_degradation_factor_default():
    """Коэффициент по умолчанию — 1.3."""
    flags = FeatureFlags({})
    assert flags.get_float("cooling_degradation_factor", 1.3) == 1.3


def test_cooling_degradation_factor_from_settings():
    """Коэффициент читается из настроек."""
    flags = FeatureFlags({"cooling_degradation_factor": "1.5"})
    assert flags.get_float("cooling_degradation_factor", 1.3) == 1.5


# ==========================================
# ХЕЛПЕР: добавляет cooling-задачу в СУЩЕСТВУЮЩУЮ модель
# ==========================================

def _add_cooling_task(
        model,
        task_id: str,
        start_min: int,
        duration: int,
        slow_duration: int,
        horizon: int = 10000,
):
    """
    Добавляет cooling-задачу в СУЩЕСТВУЮЩУЮ модель.
    Возвращает task_dict.

    Все переменные — в одной модели. Иначе solver решает только
    первую модель, а переменные из других — undefined.
    """
    start = model.NewIntVar(start_min, start_min, f"start_{task_id}")
    b_fast = model.NewBoolVar(f"b_fast_{task_id}")
    b_slow = model.NewBoolVar(f"b_slow_{task_id}")
    model.Add(b_fast + b_slow == 1)

    fast_end = model.NewIntVar(0, horizon, f"fast_end_{task_id}")
    slow_end = model.NewIntVar(0, horizon, f"slow_end_{task_id}")

    model.Add(fast_end == start + duration)
    model.Add(slow_end == start + slow_duration)

    fast_interval = model.NewOptionalIntervalVar(
        start, duration, fast_end, b_fast, f"fast_{task_id}"
    )
    slow_interval = model.NewOptionalIntervalVar(
        start, slow_duration, slow_end, b_slow, f"slow_{task_id}"
    )

    chosen_end = model.NewIntVar(0, horizon, f"chosen_end_{task_id}")
    model.Add(chosen_end == fast_end).OnlyEnforceIf(b_fast)
    model.Add(chosen_end == slow_end).OnlyEnforceIf(b_slow)

    return {
        "start": start,
        "end": chosen_end,
        "fast_end": fast_end,
        "b_fast": b_fast,
        "b_slow": b_slow,
        "fast_interval": fast_interval,
        "slow_interval": slow_interval,
        "duration": duration,
        "slow_duration": slow_duration,
        "is_cooling_degraded": True,
    }


# ==========================================
# ТЕСТЫ: МОДЕЛЬ ДЕГРАДАЦИИ
# ==========================================

def test_single_cooling_is_always_fast():
    """
    Единственная cooling-задача (нет других) — всегда fast.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.core import ProductionScheduler
    from tests.fixtures import tz_case

    model = cp_model.CpModel()
    t1 = _add_cooling_task(model, "t1", start_min=0, duration=100, slow_duration=130)

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler._apply_cooling_degradation_model(model, [t1])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.Value(t1["b_fast"]) == 1, "Одна cooling-задача должна быть fast"
    assert solver.Value(t1["b_slow"]) == 0


def test_two_sequential_coolings_both_fast():
    """
    Два охлаждения последовательно (не пересекаются):
    [0..100) и [100..200). Оба должны быть fast.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.core import ProductionScheduler
    from tests.fixtures import tz_case

    model = cp_model.CpModel()
    t1 = _add_cooling_task(model, "t1", start_min=0, duration=100, slow_duration=130)
    t2 = _add_cooling_task(model, "t2", start_min=100, duration=100, slow_duration=130)

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler._apply_cooling_degradation_model(model, [t1, t2])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    assert solver.Value(t1["b_fast"]) == 1, "t1 (не пересекается) должен быть fast"
    assert solver.Value(t2["b_fast"]) == 1, "t2 (не пересекается) должен быть fast"


def test_two_overlapping_coolings_both_slow():
    """
    Два охлаждения пересекаются: [0..200) и [100..300).
    Оба должны быть slow.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.core import ProductionScheduler
    from tests.fixtures import tz_case

    model = cp_model.CpModel()
    t1 = _add_cooling_task(model, "t1", start_min=0, duration=200, slow_duration=260)
    t2 = _add_cooling_task(model, "t2", start_min=100, duration=200, slow_duration=260)

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler._apply_cooling_degradation_model(model, [t1, t2])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    assert solver.Value(t1["b_slow"]) == 1, "t1 пересекается — slow"
    assert solver.Value(t2["b_slow"]) == 1, "t2 пересекается — slow"


def test_three_coolings_partial_overlap():
    """
    Три охлаждения: [0..100), [50..150), [200..300).
    Первые два пересекаются → slow. Третье — fast.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.core import ProductionScheduler
    from tests.fixtures import tz_case

    model = cp_model.CpModel()
    t1 = _add_cooling_task(model, "t1", start_min=0, duration=100, slow_duration=130)
    t2 = _add_cooling_task(model, "t2", start_min=50, duration=100, slow_duration=130)
    t3 = _add_cooling_task(model, "t3", start_min=200, duration=100, slow_duration=130)

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler._apply_cooling_degradation_model(model, [t1, t2, t3])

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    assert solver.Value(t1["b_slow"]) == 1, "t1 пересекается с t2 → slow"
    assert solver.Value(t2["b_slow"]) == 1, "t2 пересекается с t1 → slow"
    assert solver.Value(t3["b_slow"]) == 0, "t3 не пересекается → fast"
    assert solver.Value(t3["b_fast"]) == 1


def test_no_degradation_means_all_fast():
    """
    Пустой список cooling-задач — модель не падает.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.core import ProductionScheduler
    from tests.fixtures import tz_case

    model = cp_model.CpModel()
    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)

    # Не должно выбросить исключение
    scheduler._apply_cooling_degradation_model(model, [])


# ==========================================
# ТЕСТЫ: PLUGIN
# ==========================================

def test_cooling_degradation_constraint_respects_capacity():
    """
    CoolingDegradationConstraint не должен падать при capacity=2.
    """
    from ortools.sat.python import cp_model
    from app.scheduler.constraints.plugins import CoolingDegradationConstraint

    model = cp_model.CpModel()
    tasks = {
        ("b1", "op1"): {
            "needs_cooling": True,
            "fast_interval": model.NewOptionalIntervalVar(
                0, 100, model.NewIntVar(0, 1000, "e1"),
                model.NewBoolVar("b1"), "f1",
            ),
            "slow_interval": model.NewOptionalIntervalVar(
                0, 130, model.NewIntVar(0, 1000, "e1s"),
                model.NewBoolVar("b1s"), "s1",
            ),
        },
    }

    plugin = CoolingDegradationConstraint()
    plugin.apply(
        model,
        tasks,
        resource_pools=[{"type": "COOLING_ZONE", "capacity": 2}],
    )


def test_cooling_degradation_constraint_does_not_use_nooverlap():
    """
    Регрессия: constraint НЕ должен содержать AddNoOverlap(fast_intervals).
    """
    import inspect
    from app.scheduler.constraints.plugins import CoolingDegradationConstraint

    source = inspect.getsource(CoolingDegradationConstraint.apply)

    assert "AddNoOverlap" not in source, (
        "CoolingDegradationConstraint не должен использовать AddNoOverlap — "
        "это ломает модель деградации (см. hotfix Итерации 7). "
        "Ограничение capacity делается через AddCumulative."
    )


# ==========================================
# ТЕСТЫ: КОНТРАКТ API
# ==========================================

def test_gantt_task_model_has_cooling_mode():
    """
    Pydantic-модель GanttTask должна содержать поле cooling_mode.
    """
    from app.api.v1.models import GanttTask

    fields = GanttTask.model_fields
    assert "cooling_mode" in fields, (
        "GanttTask должен иметь поле cooling_mode"
    )
    assert fields["cooling_mode"].default is None


def test_shift_task_model_has_cooling_mode():
    """
    ShiftTaskResponse должен содержать cooling_mode.
    """
    from app.api.v1.shift_models import ShiftTaskResponse

    fields = ShiftTaskResponse.model_fields
    assert "cooling_mode" in fields, (
        "ShiftTaskResponse должен иметь поле cooling_mode (Итерация 7)"
    )


def test_gantt_api_returns_cooling_mode_in_sql():
    """
    SQL-запрос в gantt.py должен выбирать st.cooling_mode.
    """
    import inspect
    from app.api.v1 import gantt as gantt_module

    source = inspect.getsource(gantt_module)
    assert "st.cooling_mode" in source, (
        "gantt.py должен выбирать st.cooling_mode из scheduled_task"
    )


def test_shift_api_returns_cooling_mode_in_sql():
    """
    SQL-запросы в shift.py должны выбирать st.cooling_mode.
    """
    import inspect
    from app.api.v1 import shift as shift_module

    source = inspect.getsource(shift_module)
    assert source.count("st.cooling_mode") >= 2, (
        "shift.py должен выбирать st.cooling_mode минимум в 2 запросах"
    )


# ==========================================
# ТЕСТЫ: SQL-СХЕМА
# ==========================================

def test_cooling_mode_column_exists_in_schema():
    """
    init_schema.sql должен содержать колонку cooling_mode.
    """
    import os

    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "init_schema.sql"
    )
    with open(schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "cooling_mode" in content
    assert "idx_scheduled_task_cooling_mode" in content


def test_migration_add_10b_exists():
    """Миграция add_10b.sql должна существовать."""
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_10b.sql"
    )
    assert os.path.exists(path), "migrations/add_10b.sql должен существовать"


def test_migration_add_10b_adds_cooling_mode():
    """add_10b.sql должен добавлять колонку cooling_mode."""
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_10b.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "cooling_mode" in content
    assert "ALTER TABLE scheduled_task" in content


# ==========================================
# ТЕСТЫ: ЧИСЛОВЫЕ ОЖИДАНИЯ
# ==========================================

def test_expected_values_are_consistent():
    """
    Sanity-check: fast = base, slow = base × 1.3.
    """
    base = 218  # партия 7000 кг на R2 (10000 л)
    factor = 1.3
    slow = int(base * factor)

    assert slow == 283


if __name__ == "__main__":
    pytest.main([__file__, "-v"])