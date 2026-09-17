# backend/app/scheduler/constraints/plugins.py
"""
Плагины ограничений для планировщика.

Итерация 1: базовые ограничения (Boiler, CoolingZone, Operator).
Итерация 6:
  - OperatorPoolConstraint — учитывает пулы операторов из resource_pool.
  - LabConstraint — учитывает пул лаборантов.
  - Плагины получают resource_pools из data_loader.
"""

from typing import Dict, List, Optional

from ortools.sat.python import cp_model


# ==========================================
# СТАРЫЕ ПЛАГИНЫ (Итерация 1)
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


class CoolingZoneConstraint:
    """Зона охлаждения — не более capacity реакторов одновременно."""

    def apply(
            self,
            model: cp_model.CpModel,
            tasks: Dict[tuple, Dict],
            resource_pools: Optional[List[Dict]] = None,
    ) -> None:
        capacity = 2
        if resource_pools:
            for pool in resource_pools:
                if pool.get("type") == "COOLING_ZONE":
                    capacity = int(pool.get("capacity") or 2)
                    break

        cooling_tasks = [t["interval"] for t in tasks.values() if t.get("needs_cooling")]
        if cooling_tasks:
            demands = [model.NewIntVar(1, 1, f"cool_demand_{i}") for i in range(len(cooling_tasks))]
            model.AddCumulative(cooling_tasks, demands, capacity=capacity)


# ==========================================
# ИТЕРАЦИЯ 6: ПУЛЫ ОПЕРАТОРОВ
# ==========================================

class OperatorPoolConstraint:
    """
    Учёт пулов операторов из resource_pool.

    Для каждого пула (REACTOR_OPERATOR, LINE_OPERATOR, MANUAL_OPERATOR)
    создаётся отдельный AddCumulative с capacity из resource_pool.

    Логика:
      - Задачи фильтруются по `operator_pool` (строка).
      - Задачи без пула или с неизвестным пулом — игнорируются.
      - BOILER и COOLING_ZONE обрабатываются отдельными плагинами.
    """

    # Пул → тип в resource_pool
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

        # Индекс: type → capacity
        pool_capacity: Dict[str, int] = {}
        for pool in resource_pools:
            pool_type = pool.get("type")
            capacity = int(pool.get("capacity") or 0)
            if pool_type in self.POOL_TYPES and capacity > 0:
                pool_capacity[pool_type] = capacity

        # Для каждого пула — свой AddCumulative
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
    """
    Учёт пула лаборатории (LAB).

    По умолчанию capacity=1 — один лаборант.
    """

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
    CoolingZoneConstraint(),
    OperatorPoolConstraint(),
    LabConstraint(),
]