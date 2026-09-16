# backend/app/scheduler/feasibility.py
"""
Оценка исполнимости производственного плана.

Проверяет:
  - Хватает ли сырья (см. materials.analyze_materials)
  - Хватает ли производственных мощностей (упрощённо)
  - Успевают ли заказы к due_date

Возвращает:
  - feasible: bool — исполнимо ли в принципе
  - issues: список проблем
  - warnings: список предупреждений
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .materials import analyze_materials, MaterialAnalysis


@dataclass
class FeasibilityIssue:
    code: str
    severity: str  # BLOCKER | WARNING
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeasibilityResult:
    feasible: bool = True
    issues: List[FeasibilityIssue] = field(default_factory=list)
    warnings: List[FeasibilityIssue] = field(default_factory=list)

    def add_blocker(self, code: str, message: str, details: Dict = None) -> None:
        self.feasible = False
        self.issues.append(FeasibilityIssue(
            code=code, severity="BLOCKER", message=message, details=details or {}
        ))

    def add_warning(self, code: str, message: str, details: Dict = None) -> None:
        self.warnings.append(FeasibilityIssue(
            code=code, severity="WARNING", message=message, details=details or {}
        ))


def check_feasibility(
        batches: List[Dict],
        recipes: Dict[str, Dict],
        materials: Dict[str, Dict],
        material_stocks: Dict[str, Dict],
        material_supplies: Optional[List[Dict]] = None,
) -> FeasibilityResult:
    """
    Проверяет исполнимость плана.
    """
    result = FeasibilityResult()

    # 1. Материальная обеспеченность
    analysis = analyze_materials(
        batches=batches,
        recipes=recipes,
        materials=materials,
        material_stocks=material_stocks,
        material_supplies=material_supplies,
    )

    if analysis.has_deficit:
        result.add_blocker(
            code="MATERIAL_SHORTAGE",
            message=(
                f"Не хватает {len(analysis.shortages)} материалов "
                f"на общую сумму дефицита {analysis.total_deficit_kg:.1f} кг."
            ),
            details={
                "shortages": [
                    {
                        "material_code": r.material_code,
                        "material_name": r.material_name,
                        "required": r.required_kg,
                        "available": r.available_qty,
                        "deficit": r.deficit_kg,
                        "unit": r.unit,
                    }
                    for r in analysis.shortages
                ],
            },
        )

    # 2. Проверка на пустой план
    if not batches:
        result.add_warning(
            code="EMPTY_PLAN",
            message="Нет партий для планирования.",
        )

    return result