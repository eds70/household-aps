# backend/app/scheduler/advisor.py
"""
Advisor — модуль подсказок планировщика.

Анализирует данные и план, возвращает список AdvisorTip'ов:
  1. MATERIAL_SHORTAGE — нехватка сырья (на сколько хватает).
  2. UNDERLOAD — неполная загрузка реактора.
  3. ROUTE_MISMATCH — продукт помечен VIA_TANK, но реактор без танка.
  4. EQUIPMENT_GAP — простой оборудования.
  5. OVERLOAD — перегрузка оборудования.

Подсказки возвращаются в порядке приоритета: CRITICAL → WARNING → INFO.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .materials import (
    analyze_materials,
    MaterialAnalysis,
    MaterialRequirement,
)


class TipSeverity:
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class TipCode:
    MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE"
    UNDERLOAD = "UNDERLOAD"
    ROUTE_MISMATCH = "ROUTE_MISMATCH"
    EQUIPMENT_GAP = "EQUIPMENT_GAP"
    OVERLOAD = "OVERLOAD"
    NO_REACTOR = "NO_REACTOR"


@dataclass
class AdvisorTip:
    """Одна подсказка."""
    code: str
    severity: str
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdvisorResult:
    """Все подсказки."""
    tips: List[AdvisorTip] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def add(self, tip: AdvisorTip) -> None:
        self.tips.append(tip)
        if tip.severity == TipSeverity.CRITICAL:
            self.critical_count += 1
        elif tip.severity == TipSeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    def sort_by_severity(self) -> None:
        order = {TipSeverity.CRITICAL: 0, TipSeverity.WARNING: 1, TipSeverity.INFO: 2}
        self.tips.sort(key=lambda t: order.get(t.severity, 99))


# ==========================================
# ПРОВЕРКА 1: НЕХВАТКА СЫРЬЯ
# ==========================================

def check_material_shortage(analysis: MaterialAnalysis) -> List[AdvisorTip]:
    """Превращает MaterialAnalysis в подсказки."""
    tips: List[AdvisorTip] = []

    for req in analysis.shortages:
        # На сколько партий хватит (приблизительно)
        coverage_pct = 0.0
        if req.required_kg > 0:
            coverage_pct = (req.available_qty / req.required_kg) * 100.0

        tips.append(AdvisorTip(
            code=TipCode.MATERIAL_SHORTAGE,
            severity=TipSeverity.CRITICAL,
            title=f"Нехватка сырья: {req.material_name}",
            message=(
                f"На весь план нужно {req.required_kg:.1f} {req.unit} "
                f"{req.material_name}, а доступно {req.available_qty:.1f} {req.unit}. "
                f"Дефицит: {req.deficit_kg:.1f} {req.unit} "
                f"(хватит на {coverage_pct:.0f}% плана)."
            ),
            details={
                "material_id": req.material_id,
                "material_code": req.material_code,
                "required": req.required_kg,
                "available": req.available_qty,
                "deficit": req.deficit_kg,
                "unit": req.unit,
                "coverage_pct": coverage_pct,
                "batches_affected": req.batches_affected,
            },
        ))

    # Информационные предупреждения о малом запасе (surplus < 10% required)
    for req in analysis.requirements:
        if req.deficit_kg > 0:
            continue  # уже добавили
        if req.required_kg <= 0:
            continue
        safety_margin = req.surplus_kg / req.required_kg
        if safety_margin < 0.10:
            tips.append(AdvisorTip(
                code=TipCode.MATERIAL_SHORTAGE,
                severity=TipSeverity.WARNING,
                title=f"Малый запас: {req.material_name}",
                message=(
                    f"{req.material_name}: потребность {req.required_kg:.1f} {req.unit}, "
                    f"доступно {req.available_qty:.1f} {req.unit}. "
                    f"Запас всего {req.surplus_kg:.1f} {req.unit} "
                    f"({safety_margin * 100:.0f}% от потребности)."
                ),
                details={
                    "material_id": req.material_id,
                    "material_code": req.material_code,
                    "required": req.required_kg,
                    "available": req.available_qty,
                    "surplus": req.surplus_kg,
                    "unit": req.unit,
                    "safety_margin_pct": safety_margin * 100,
                },
            ))

    return tips


# ==========================================
# ПРОВЕРКА 2: НЕПОЛНАЯ ЗАГРУЗКА РЕАКТОРА
# ==========================================

def check_underload(
        batches: List[Dict],
        equipment_map: Dict[str, Dict],
        max_fill_percent: float = 0.70,
        threshold: float = 0.50,  # ниже 50% — подсказка
) -> List[AdvisorTip]:
    """
    Проверяет партии, которые загружают реактор менее чем на threshold от max_fill_percent.
    """
    tips: List[AdvisorTip] = []

    for batch in batches:
        batch_id = str(batch["id"])
        eq_id = batch.get("assigned_equipment_id")
        if not eq_id:
            continue

        equipment = equipment_map.get(str(eq_id))
        if not equipment or equipment.get("type") != "REACTOR":
            continue

        volume_kg = float(batch.get("volume_kg") or 0)
        reactor_volume = float(equipment.get("volume_kg") or 0)
        if reactor_volume <= 0:
            continue

        max_fill_kg = reactor_volume * max_fill_percent
        fill_ratio = volume_kg / reactor_volume
        fill_ratio_of_max = volume_kg / max_fill_kg if max_fill_kg > 0 else 0

        if fill_ratio_of_max < threshold:
            # Показываем, сколько ещё «влезло» бы
            headroom_kg = max_fill_kg - volume_kg

            tips.append(AdvisorTip(
                code=TipCode.UNDERLOAD,
                severity=TipSeverity.INFO,
                title=f"Неполная загрузка: {equipment.get('name', '?')}",
                message=(
                    f"Партия {volume_kg:.0f} кг загружает {equipment.get('name', '?')} "
                    f"({reactor_volume:.0f} кг) на {fill_ratio * 100:.0f}%. "
                    f"Максимум по ТЗ: {max_fill_percent * 100:.0f}% "
                    f"({max_fill_kg:.0f} кг). Можно увеличить партию на {headroom_kg:.0f} кг."
                ),
                details={
                    "batch_id": batch_id,
                    "equipment_id": str(eq_id),
                    "equipment_name": equipment.get("name"),
                    "batch_volume_kg": volume_kg,
                    "reactor_volume_kg": reactor_volume,
                    "fill_ratio_pct": fill_ratio * 100,
                    "fill_ratio_of_max_pct": fill_ratio_of_max * 100,
                    "headroom_kg": headroom_kg,
                },
            ))

    return tips


# ==========================================
# ПРОВЕРКА 3: ROUTE_MISMATCH
# ==========================================

def check_route_mismatch(
        batches: List[Dict],
        products_map: Dict[str, Dict],
        equipment_map: Dict[str, Dict],
        equipment_links: List[Dict],
) -> List[AdvisorTip]:
    """
    Проверяет: продукт помечен VIA_TANK, но у реактора нет танка.
    В этом случае план выполним, но не так эффективно.
    """
    tips: List[AdvisorTip] = []

    # Индекс: реактор → есть ли танк
    reactor_has_tank: Dict[str, bool] = {}
    for link in equipment_links:
        from_id = str(link["from_equipment_id"])
        to_id = str(link["to_equipment_id"])
        target = equipment_map.get(to_id, {})
        if target.get("type") == "TANK":
            reactor_has_tank[from_id] = True

    seen_pairs: set = set()
    for batch in batches:
        product_id = str(batch["product_id"])
        eq_id = batch.get("assigned_equipment_id")
        if not eq_id:
            continue

        product = products_map.get(product_id, {})
        if product.get("route_type") != "VIA_TANK":
            continue

        pair = (product_id, str(eq_id))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        if not reactor_has_tank.get(str(eq_id), False):
            equipment = equipment_map.get(str(eq_id), {})
            tips.append(AdvisorTip(
                code=TipCode.ROUTE_MISMATCH,
                severity=TipSeverity.INFO,
                title=f"Маршрут через танк невозможен: {equipment.get('name', '?')}",
                message=(
                    f"Продукт {product.get('name', '?')} помечен VIA_TANK, "
                    f"но реактор {equipment.get('name', '?')} не подключён к накопительной ёмкости. "
                    f"Слив пойдёт напрямую на линию. Партии этого продукта на этом реакторе "
                    f"будут занимать реактор дольше."
                ),
                details={
                    "product_id": product_id,
                    "product_code": product.get("code"),
                    "equipment_id": str(eq_id),
                    "equipment_name": equipment.get("name"),
                },
            ))

    return tips


# ==========================================
# ПРОВЕРКА 4: ПРОСТОИ ОБОРУДОВАНИЯ
# ==========================================

def check_equipment_gaps(
        schedule_result: Optional[Dict],
        equipment_map: Dict[str, Dict],
        min_gap_hours: float = 8.0,
) -> List[AdvisorTip]:
    """
    Проверяет простои оборудования больше min_gap_hours.
    Использует результат расписания из последнего расчёта.
    """
    if not schedule_result or "tasks" not in schedule_result:
        return []

    tasks = schedule_result["tasks"]
    if not tasks:
        return []

    # Группируем по primary_equipment_id
    by_equipment: Dict[str, List[Dict]] = {}
    for task in tasks:
        eq_id = str(task.get("equipment_id") or "")
        if not eq_id:
            continue
        by_equipment.setdefault(eq_id, []).append(task)

    tips: List[AdvisorTip] = []

    for eq_id, eq_tasks in by_equipment.items():
        eq_tasks.sort(key=lambda t: t.get("start") or datetime.min)
        equipment = equipment_map.get(eq_id, {})
        eq_name = equipment.get("name", eq_id[:8])

        for i in range(len(eq_tasks) - 1):
            curr = eq_tasks[i]
            next_task = eq_tasks[i + 1]
            curr_end = curr.get("end")
            next_start = next_task.get("start")
            if not isinstance(curr_end, datetime) or not isinstance(next_start, datetime):
                continue

            gap_minutes = (next_start - curr_end).total_seconds() / 60.0
            if gap_minutes >= min_gap_hours * 60:
                tips.append(AdvisorTip(
                    code=TipCode.EQUIPMENT_GAP,
                    severity=TipSeverity.INFO,
                    title=f"Простой: {eq_name}",
                    message=(
                        f"{eq_name} простаивает {gap_minutes / 60:.1f} ч "
                        f"между операциями «{curr.get('operation_name', '?')}» "
                        f"и «{next_task.get('operation_name', '?')}»."
                    ),
                    details={
                        "equipment_id": eq_id,
                        "equipment_name": eq_name,
                        "gap_minutes": gap_minutes,
                        "gap_hours": gap_minutes / 60,
                        "before_op": curr.get("operation_name"),
                        "after_op": next_task.get("operation_name"),
                        "start": curr_end.isoformat() if isinstance(curr_end, datetime) else None,
                        "end": next_start.isoformat() if isinstance(next_start, datetime) else None,
                    },
                ))

    return tips


# ==========================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==========================================

def analyze(
        batches: List[Dict],
        products_map: Dict[str, Dict],
        equipment_map: Dict[str, Dict],
        equipment_links: List[Dict],
        recipes: Dict[str, Dict],
        materials: Dict[str, Dict],
        material_stocks: Dict[str, Dict],
        material_supplies: Optional[List[Dict]] = None,
        schedule_result: Optional[Dict] = None,
        max_fill_percent: float = 0.70,
        enable_material_constraints: bool = True,
        enable_advisor: bool = True,
) -> AdvisorResult:
    """
    Главная функция Advisor'а.

    Проверки:
      1. Нехватка сырья (если enable_material_constraints)
      2. Неполная загрузка реактора (если enable_advisor)
      3. ROUTE_MISMATCH (если enable_advisor)
      4. Простои оборудования (если есть schedule_result)
    """
    result = AdvisorResult()

    if not enable_advisor:
        return result

    # 1. Материальные ограничения
    if enable_material_constraints:
        analysis = analyze_materials(
            batches=batches,
            recipes=recipes,
            materials=materials,
            material_stocks=material_stocks,
            material_supplies=material_supplies,
        )
        for tip in check_material_shortage(analysis):
            result.add(tip)

    # 2. Неполная загрузка
    for tip in check_underload(
            batches=batches,
            equipment_map=equipment_map,
            max_fill_percent=max_fill_percent,
    ):
        result.add(tip)

    # 3. Route mismatch
    for tip in check_route_mismatch(
            batches=batches,
            products_map=products_map,
            equipment_map=equipment_map,
            equipment_links=equipment_links,
    ):
        result.add(tip)

    # 4. Простои
    for tip in check_equipment_gaps(
            schedule_result=schedule_result,
            equipment_map=equipment_map,
    ):
        result.add(tip)

    result.sort_by_severity()
    return result