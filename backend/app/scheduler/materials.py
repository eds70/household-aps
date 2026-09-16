# backend/app/scheduler/materials.py
"""
Расчёт потребности в сырье и проверка обеспеченности.

Используется:
  - Advisor'ом для подсказок о дефиците
  - Feasibility для оценки исполнимости плана

Логика:
  1. Для каждой партии находим рецептуру её ПФ.
  2. Пропорционально объёму партии считаем потребность в каждом материале:
     required = qty_per_base × (batch.volume_kg / recipe.base_volume_kg)
  3. Суммируем по всем партиям → общая потребность.
  4. Сравниваем с остатками + поставками → получаем дефицит/профицит.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union


Number = Union[int, float, Decimal]


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class MaterialRequirement:
    """Потребность в одном материале по всем партиям."""
    material_id: str
    material_code: str
    material_name: str
    unit: str
    required_kg: float  # или unit
    stock_qty: float
    reserved_qty: float
    available_qty: float  # stock - reserved
    deficit_kg: float  # >0 если не хватает
    surplus_kg: float  # >0 если запас есть
    batches_affected: int = 0  # сколько партий используют материал
    batches_covered: int = 0   # сколько партий можно покрыть (эвристика)


@dataclass
class MaterialAnalysis:
    """Общий результат анализа обеспеченности."""
    requirements: List[MaterialRequirement] = field(default_factory=list)
    has_deficit: bool = False
    total_deficit_kg: float = 0.0
    shortages: List[MaterialRequirement] = field(default_factory=list)


def calculate_batch_requirements(
        batch: Dict,
        product_id: str,
        recipes: Dict[str, Dict],
) -> Dict[str, float]:
    """
    Считает потребность в материалах для одной партии.
    Возвращает {material_id: qty}.
    """
    recipe = recipes.get(str(product_id))
    if not recipe or not recipe.get("items"):
        return {}

    base_volume = _to_float(recipe.get("base_volume_kg"), 100.0)
    if base_volume <= 0:
        return {}

    batch_volume = _to_float(batch.get("volume_kg"), 0.0)
    scale = batch_volume / base_volume

    return {
        item["material_id"]: _to_float(item["qty_per_base"]) * scale
        for item in recipe["items"]
    }


def analyze_materials(
        batches: List[Dict],
        recipes: Dict[str, Dict],
        materials: Dict[str, Dict],
        material_stocks: Dict[str, Dict],
        material_supplies: Optional[List[Dict]] = None,
) -> MaterialAnalysis:
    """
    Считает общую потребность по всем партиям и сравнивает с остатками.

    Возвращает MaterialAnalysis со списком MaterialRequirement.
    """
    # 1. Суммируем потребность по всем партиям
    total_required: Dict[str, float] = {}
    batches_per_material: Dict[str, set] = {}

    for batch in batches:
        product_id = str(batch["product_id"])
        batch_id = str(batch["id"])
        req = calculate_batch_requirements(batch, product_id, recipes)
        for material_id, qty in req.items():
            total_required[material_id] = total_required.get(material_id, 0.0) + qty
            batches_per_material.setdefault(material_id, set()).add(batch_id)

    # 2. Считаем доступное количество: остатки + поставки (упрощённо)
    # В реальности нужно учитывать дату поставки vs дату старта партии.
    # Здесь — упрощённо: все поставки считаем доступными.
    supply_per_material: Dict[str, float] = {}
    if material_supplies:
        for sup in material_supplies:
            mat_id = str(sup.get("material_id"))
            if not mat_id:
                continue
            qty = _to_float(sup.get("qty"), 0.0)
            supply_per_material[mat_id] = supply_per_material.get(mat_id, 0.0) + qty

    # 3. Формируем требования
    analysis = MaterialAnalysis()
    all_material_ids = set(total_required.keys()) | set(material_stocks.keys())

    for mat_id in all_material_ids:
        material = materials.get(mat_id)
        if not material:
            continue

        required = total_required.get(mat_id, 0.0)
        stock = material_stocks.get(mat_id, {})
        stock_qty = _to_float(stock.get("qty"), 0.0)
        reserved_qty = _to_float(stock.get("reserved_qty"), 0.0)
        available = max(0.0, stock_qty - reserved_qty)
        available_with_supply = available + supply_per_material.get(mat_id, 0.0)

        deficit = max(0.0, required - available_with_supply)
        surplus = max(0.0, available_with_supply - required)

        req = MaterialRequirement(
            material_id=mat_id,
            material_code=material.get("code", "?"),
            material_name=material.get("name", "?"),
            unit=material.get("unit", "kg"),
            required_kg=required,
            stock_qty=stock_qty,
            reserved_qty=reserved_qty,
            available_qty=available_with_supply,
            deficit_kg=deficit,
            surplus_kg=surplus,
            batches_affected=len(batches_per_material.get(mat_id, set())),
        )
        analysis.requirements.append(req)

        if deficit > 0:
            analysis.has_deficit = True
            analysis.total_deficit_kg += deficit
            analysis.shortages.append(req)

    # Сортируем: сначала дефицитные, потом по убыванию потребности
    analysis.requirements.sort(
        key=lambda r: (r.deficit_kg == 0, -r.required_kg)
    )
    analysis.shortages.sort(key=lambda r: -r.deficit_kg)

    return analysis