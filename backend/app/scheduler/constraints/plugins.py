# backend/app/scheduler/constraints/plugins.py
"""
Плагины ограничений для планировщика.

Итерация 1: базовые ограничения (Boiler, CoolingZone, Operator).
Итерация 6:
  - OperatorPoolConstraint — учитывает пулы операторов.
  - LabConstraint — пул лаборантов.
Итерация 7:
  - CoolingDegradationConstraint — заменяет CoolingZoneConstraint.
    Ограничивает общее число одновременных охлаждений (capacity из
    resource_pool.COOLING_ZONE). Фактическая деградация (fast/slow)
    моделируется в core.py через связывание b_slow с пересечением
    cooling-интервалов.
Итерация 7 (fix):
  - Убран AddNoOverlap(fast_intervals): он был неверен, т.к. fast-интервалы
    могут быть неактивны (b_fast=0), а slow-интервалы при этом не
    эксклюзивны. Оставлен только AddCumulative(capacity) для общего
    ограничения зоны охлаждения.
"""

from typing import Dict, List, Optional

from ortools.sat.python import cp_model


# ==========================================
# БАЗОВЫЕ ПЛАГИНЫ
# ==========================================

class BoilerConstraint:
    """Один бойлер — не более 1 операции одновременно."""

    def apply(
            self,
            model: cp_model.CpModel,
            tasks: Dict[tuple, Dict],
            resource_pools: Optional[List[Dict]] = None,
    ) -> None:
        boiler_tasks = [t["interval"] for t in tasks.values() if t.get("needs_boiler")]
        if boiler_tasks:
            model.AddNoOverlap(boiler_tasks)


class CoolingDegradationConstraint:
    """
    Зона охлаждения с деградацией (Итерация 7).

    Логика:
      - Capacity зоны охлаждения берётся из resource_pool.COOLING_ZONE
        (по ТЗ — 2 реактора могут остывать одновременно).
      - Ограничение: не более `capacity` активных cooling-интервалов
        одновременно (fast ИЛИ slow — считаем вместе).

    Фактическое назначение fast/slow (кто именно замедлен) делается
    в core.py через явное связывание b_slow_i с пересечением интервалов.
    Этот плагин только ограничивает общее число параллельных охлаждений.
    """

    DEFAULT_CAPACITY = 2

    def apply(
            self,
            model: cp_model.CpModel,
            tasks: Dict[tuple, Dict],
            resource_pools: Optional[List[Dict]] = None,
    ) -> None:
        # Определяем capacity зоны охлаждения
        capacity = self.DEFAULT_CAPACITY
        if resource_pools:
            for pool in resource_pools:
                if pool.get("type") == "COOLING_ZONE":
                    capacity = int(pool.get("capacity") or self.DEFAULT_CAPACITY)
                    break

        # Собираем ВСЕ активные интервалы (fast + slow).
        # Каждый cooling-task имеет ровно один активный интервал
        # (fast XOR slow), поэтому суммируем оба списка.
        all_intervals = []

        for task in tasks.values():
            if not task.get("needs_cooling"):
                continue

            fast = task.get("fast_interval")
            slow = task.get("slow_interval")

            if fast is None or slow is None:
                # Fallback: если core.py не создал fast/slow,
                # используем обычный interval.
                if task.get("interval") is not None:
                    all_intervals.append(task["interval"])
                continue

            all_intervals.append(fast)
            all_intervals.append(slow)

        if all_intervals:
            # Общий cumulative: не более `capacity` активных интервалов.
            # Т.к. fast и slow взаимоисключающие (b_fast + b_slow == 1),
            # фактически это значит: не более `capacity` охлаждений.
            demands = [
                model.NewIntVar(1, 1, f"cooling_demand_{i}")
                for i in range(len(all_intervals))
            ]
            model.AddCumulative(all_intervals, demands, capacity=capacity)


# ==========================================
# ИТЕРАЦИЯ 6: ПУЛЫ ОПЕРАТОРОВ
# ==========================================

class OperatorPoolConstraint:
    """Учёт пулов операторов из resource_pool."""

    POOL_TYPES = {
        "REACTOR_OPERATOR",
        "LINE_OPERATOR",
        "MANUAL_OPERATOR",
    }

    def apply(
            self,
            model: cp_model.CpModel,
            tasks: Dict[tuple, Dict],
            resource_pools: Optional[List[Dict]] = None,
    ) -> None:
        if not resource_pools:
            return

        pool_capacity: Dict[str, int] = {}
        for pool in resource_pools:
            pool_type = pool.get("type")
            capacity = int(pool.get("capacity") or 0)
            if pool_type in self.POOL_TYPES and capacity > 0:
                pool_capacity[pool_type] = capacity

        for pool_type, capacity in pool_capacity.items():
            pool_tasks = [
                t["interval"]
                for t in tasks.values()
                if t.get("operator_pool") == pool_type
            ]
            if pool_tasks:
                demands = [
                    model.NewIntVar(1, 1, f"op_{pool_type}_{i}")
                    for i in range(len(pool_tasks))
                ]
                model.AddCumulative(pool_tasks, demands, capacity=capacity)


class LabConstraint:
    """Учёт пула лаборатории (LAB)."""

    def apply(
            self,
            model: cp_model.CpModel,
            tasks: Dict[tuple, Dict],
            resource_pools: Optional[List[Dict]] = None,
    ) -> None:
        capacity = 1
        if resource_pools:
            for pool in resource_pools:
                if pool.get("type") == "LAB":
                    capacity = int(pool.get("capacity") or 1)
                    break

        lab_tasks = [
            t["interval"]
            for t in tasks.values()
            if t.get("operator_pool") == "LAB"
        ]
        if lab_tasks:
            demands = [
                model.NewIntVar(1, 1, f"lab_demand_{i}")
                for i in range(len(lab_tasks))
            ]
            model.AddCumulative(lab_tasks, demands, capacity=capacity)


# ==========================================
# СПИСОК ПЛАГИНОВ
# ==========================================

CONSTRAINT_PLUGINS = [
    BoilerConstraint(),
    CoolingDegradationConstraint(),
    OperatorPoolConstraint(),
    LabConstraint(),
]