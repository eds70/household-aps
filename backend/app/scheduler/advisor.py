# backend/app/scheduler/advisor.py
"""
Advisor — модуль подсказок планировщика.

Анализирует данные и план, возвращает список AdvisorTip'ов:
  1. MATERIAL_SHORTAGE — нехватка сырья.
  2. UNDERLOAD — неполная загрузка реактора.
  3. ROUTE_MISMATCH — продукт помечен VIA_TANK, но реактор без танка.
  4. EQUIPMENT_GAP — простой оборудования.
  5. COOLING_DEGRADATION — охлаждение с деградацией (Итерация 7).
  6. CZ_INCOMPLETE — партия слита, но не промаркирована (Итерация 8).

Подсказки возвращаются в порядке приоритета: CRITICAL → WARNING → INFO.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

from .materials import (
    analyze_materials,
    MaterialAnalysis,
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
    COOLING_DEGRADATION = "COOLING_DEGRADATION"     # Итерация 7
    CZ_INCOMPLETE = "CZ_INCOMPLETE"                 # Итерация 8


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

    for req in analysis.requirements:
        if req.deficit_kg > 0:
            continue
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
        threshold: float = 0.50,
) -> List[AdvisorTip]:
    """Проверяет партии с загрузкой реактора < threshold от max_fill."""
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
    """Проверяет: продукт VIA_TANK, но у реактора нет танка."""
    tips: List[AdvisorTip] = []

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
                    f"Слив пойдёт напрямую на линию."
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
    """Проверяет простои оборудования > min_gap_hours."""
    if not schedule_result or "tasks" not in schedule_result:
        return []

    tasks = schedule_result["tasks"]
    if not tasks:
        return []

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
                    },
                ))

    return tips


# ==========================================
# ПРОВЕРКА 5: ОХЛАЖДЕНИЕ С ДЕГРАДАЦИЕЙ (Итерация 7)
# ==========================================

def check_cooling_degradation(
        schedule_result: Optional[Dict],
        cooling_degradation_factor: float = 1.3,
) -> List[AdvisorTip]:
    """
    Проверяет операции охлаждения с деградацией.

    Логика:
      - Смотрим задачи с cooling_mode.
      - fast: обычная скорость.
      - slow: замедление ×factor.

    Возвращает:
      - WARNING, если есть slow (есть замедление).
      - INFO, если все fast, но были cooling-операции.
      - Пусто, если cooling нет.
    """
    if not schedule_result or "tasks" not in schedule_result:
        return []

    tasks = schedule_result["tasks"]
    if not tasks:
        return []

    cooling_tasks = [t for t in tasks if t.get("cooling_mode") in ("fast", "slow")]
    if not cooling_tasks:
        return []

    fast_tasks = [t for t in cooling_tasks if t.get("cooling_mode") == "fast"]
    slow_tasks = [t for t in cooling_tasks if t.get("cooling_mode") == "slow"]

    fast_count = len(fast_tasks)
    slow_count = len(slow_tasks)
    total = fast_count + slow_count

    tips: List[AdvisorTip] = []

    if slow_count > 0:
        delta_pct = (cooling_degradation_factor - 1.0) * 100.0
        slow_total_mins = sum(t.get("duration", 0) for t in slow_tasks)
        slow_total_if_fast = sum(
            int(t.get("duration", 0) / cooling_degradation_factor)
            for t in slow_tasks
        )
        extra_mins = slow_total_mins - slow_total_if_fast

        tips.append(AdvisorTip(
            code=TipCode.COOLING_DEGRADATION,
            severity=TipSeverity.WARNING,
            title=f"Охлаждение с деградацией: {slow_count} операций",
            message=(
                f"{slow_count} из {total} операций охлаждения выполняются "
                f"в замедленном режиме (×{cooling_degradation_factor}). "
                f"Это добавляет ~{extra_mins} мин к общему расписанию "
                f"({delta_pct:.0f}% замедление)."
            ),
            details={
                "total_cooling": total,
                "fast_count": fast_count,
                "slow_count": slow_count,
                "extra_minutes": extra_mins,
                "degradation_factor": cooling_degradation_factor,
                "slow_task_ids": [str(t.get("op_id") or t.get("id")) for t in slow_tasks],
            },
        ))
    else:
        tips.append(AdvisorTip(
            code=TipCode.COOLING_DEGRADATION,
            severity=TipSeverity.INFO,
            title=f"Охлаждение без деградации: {fast_count} операций",
            message=(
                f"Все {fast_count} операций охлаждения выполняются "
                f"в обычном режиме. Зона охлаждения не перегружена."
            ),
            details={
                "total_cooling": total,
                "fast_count": fast_count,
                "slow_count": 0,
            },
        ))

    return tips


# ==========================================
# ПРОВЕРКА 6: ПАРТИЯ СЛИТА, НО НЕ ПРОМАРКИРОВАНА (Итерация 8)
# ==========================================

def check_cz_incomplete(
        schedule_result: Optional[Dict],
        cz_completion_threshold: float = 0.95,
) -> List[AdvisorTip]:
    """
    Проверяет задачи слива (LINE_FILL), которые уже DONE,
    но партия не достигла порога маркировки ЧЗ.

    Логика (Итерация 8):
      - Смотрим задачи с task_role = 'LINE_FILL' и status = 'DONE'.
      - Для каждой проверяем связанную партию:
          batch.cz_status != 'COMPLETED' И task помечена как DONE.
      - Если партия не завершена по маркировке → WARNING.

    ВАЖНО: поля cz_status, cz_marked_qty, planned_qty должны быть
    переданы в schedule_result["tasks"]. Это делается в API-слое
    (advisor.py — эндпоинт /schedule/advice), который читает
    scheduled_task JOIN batch из активной версии.

    Если поля отсутствуют (например, для in-memory результата
    без ЧЗ) — проверка молча пропускается.
    """
    if not schedule_result or "tasks" not in schedule_result:
        return []

    tasks = schedule_result["tasks"]
    if not tasks:
        return []

    tips: List[AdvisorTip] = []

    for task in tasks:
        # Интересуют только завершённые задачи слива на линию
        role = task.get("role") or task.get("task_role")
        status = task.get("status")
        if role != "LINE_FILL":
            continue
        if status != "DONE":
            continue

        # Проверяем поля ЧЗ — они могут отсутствовать
        cz_status = task.get("cz_status")
        if cz_status is None:
            # В schedule_result нет информации о ЧЗ —
            # пропускаем проверку (нечего анализировать)
            continue

        if cz_status == "COMPLETED":
            continue

        # Не завершено → формируем подсказку
        marked_qty = float(task.get("cz_marked_qty") or 0)
        planned_qty = task.get("planned_qty")
        if planned_qty is not None:
            planned_qty = float(planned_qty)

        if planned_qty and planned_qty > 0:
            progress_percent = min(100.0, (marked_qty / planned_qty) * 100.0)
            progress_str = (
                f"{progress_percent:.0f}% "
                f"({marked_qty:.0f} из {planned_qty:.0f} бутылок)"
            )
        else:
            progress_percent = 0.0
            progress_str = f"{marked_qty:.0f} бутылок (план неизвестен)"

        batch_id = str(task.get("batch_id") or "?")
        task_id = str(task.get("id") or "?")

        tips.append(AdvisorTip(
            code=TipCode.CZ_INCOMPLETE,
            severity=TipSeverity.WARNING,
            title=f"Партия слита, но не промаркирована: {batch_id[:8]}",
            message=(
                f"Задача слива на линию завершена (status=DONE), "
                f"но маркировка ЧЗ не достигла порога "
                f"{cz_completion_threshold * 100:.0f}%. "
                f"Промаркировано: {progress_str}. "
                f"Возможен простой на отгрузке."
            ),
            details={
                "batch_id": batch_id,
                "task_id": task_id,
                "cz_status": cz_status,
                "marked_qty": marked_qty,
                "planned_qty": planned_qty,
                "progress_percent": progress_percent,
                "threshold": cz_completion_threshold,
                "product_name": task.get("product_name"),
                "equipment_name": task.get("equipment_name"),
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
        cooling_degradation_factor: float = 1.3,
        cz_completion_threshold: float = 0.95,     # Итерация 8
        enable_material_constraints: bool = True,
        enable_advisor: bool = True,
) -> AdvisorResult:
    """Главная функция Advisor'а."""
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

    # 5. Итерация 7: охлаждение с деградацией
    for tip in check_cooling_degradation(
            schedule_result=schedule_result,
            cooling_degradation_factor=cooling_degradation_factor,
    ):
        result.add(tip)

    # 6. Итерация 8: партия слита, но не промаркирована
    for tip in check_cz_incomplete(
            schedule_result=schedule_result,
            cz_completion_threshold=cz_completion_threshold,
    ):
        result.add(tip)

    result.sort_by_severity()
    return result