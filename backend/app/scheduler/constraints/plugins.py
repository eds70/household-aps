from ortools.sat.python import cp_model
from typing import Dict, List, Any

class BoilerConstraint:
    def apply(self, model: cp_model.CpModel, tasks: Dict[tuple, Dict]) -> None:
        boiler_tasks = [t["interval"] for t in tasks.values() if t.get("needs_boiler")]
        if boiler_tasks:
            model.AddNoOverlap(boiler_tasks)

class CoolingZoneConstraint:
    def apply(self, model: cp_model.CpModel, tasks: Dict[tuple, Dict]) -> None:
        cooling_tasks = [t["interval"] for t in tasks.values() if t.get("needs_cooling")]
        if cooling_tasks:
            demands = [model.NewIntVar(1, 1, f"cool_demand_{i}") for i in range(len(cooling_tasks))]
            model.AddCumulative(cooling_tasks, demands, capacity=2)

class OperatorConstraint:
    def apply(self, model: cp_model.CpModel, tasks: Dict[tuple, Dict], max_operators: int = 3) -> None:
        operator_tasks = [t["interval"] for t in tasks.values() if t.get("needs_operator")]
        if operator_tasks:
            demands = [model.NewIntVar(1, 1, f"op_demand_{i}") for i in range(len(operator_tasks))]
            model.AddCumulative(operator_tasks, demands, capacity=max_operators)

CONSTRAINT_PLUGINS = [
    BoilerConstraint(),
    CoolingZoneConstraint(),
    OperatorConstraint(),
]
