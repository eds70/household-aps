# backend/app/scheduler/routing.py
"""
Модуль построения цепочек операций (routing) для партии.

Итерация 1: корректный расчёт длительности слива.
Итерация 5: обрезка цепочки после лаборатории (truncate_after_lab).
Итерация 6: operator_pool для каждого шага.
Итерация 9 (fix #1):
  - Пулы COOLING_ZONE и BOILER теперь назначаются операциям
    с needs_cooling_zone=TRUE и needs_boiler=TRUE.
Итерация 9 (fix #2):
  - Разделены postponed_wash и postponed_pumping — раньше общая
    переменная postponed_op перезаписывалась, из-за чего терялся
    шаг TANK_TRANSFER.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union

# --- Константы ---

Number = Union[int, float, Decimal]


class TaskRole:
    """Роли задач в цепочке."""
    REACTOR_OP = "REACTOR_OP"
    TANK_TRANSFER = "TANK_TRANSFER"
    TANK_HOLD = "TANK_HOLD"
    LINE_FILL = "LINE_FILL"
    WASH = "WASH"
    SETUP = "SETUP"
    LAB_BLOCK = "LAB_BLOCK"


class RouteType:
    """Типы маршрутов."""
    DIRECT = "DIRECT"
    VIA_TANK = "VIA_TANK"


class OperatorPool:
    """Пулы ресурсов (операторы и оборудование)."""
    REACTOR_OPERATOR = "REACTOR_OPERATOR"
    LINE_OPERATOR = "LINE_OPERATOR"
    MANUAL_OPERATOR = "MANUAL_OPERATOR"
    LAB = "LAB"
    COOLING_ZONE = "COOLING_ZONE"   # Итерация 9 (fix)
    BOILER = "BOILER"               # Итерация 9 (fix)


class DurationFormula:
    """Формулы для расчета длительности."""
    WATER_LOADING = "water_loading"
    HEATING = "heating"
    MIXING = "mixing"
    COOLING = "cooling"
    PUMPING = "pumping"
    WASHING = "washing"
    LINE_FILLING = "line_filling"


@dataclass
class RoutingStep:
    """Один шаг в цепочке операций."""
    op_id: str
    op: Dict[str, Any]
    role: str
    primary_equipment_id: str
    secondary_equipment_id: Optional[str]
    duration: int
    depends_on_op_ids: List[str] = field(default_factory=list)
    is_parallel_with: List[str] = field(default_factory=list)
    is_first_in_batch: bool = False
    is_last_in_batch: bool = False
    operator_pool: Optional[str] = None


# --- Вспомогательные функции ---

def _to_float(value: Any, default: float = 0.0) -> float:
    """Безопасно приводит значение к float."""
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


def _find_reactor_for_batch(batch: Dict, equipment_map: Dict[str, Dict]) -> Optional[str]:
    """Находит реактор, закрепленный за партией."""
    eq_id = batch.get("assigned_equipment_id")
    return str(eq_id) if eq_id else None


def _find_tank_for_reactor(
        reactor_id: str,
        equipment_links: List[Dict],
        equipment_map: Dict[str, Dict],
) -> Optional[str]:
    """Находит накопительную емкость, подключенную к реактору."""
    for link in equipment_links:
        if str(link["from_equipment_id"]) == reactor_id:
            to_id = str(link["to_equipment_id"])
            target = equipment_map.get(to_id, {})
            if target.get("type") == "TANK":
                return to_id
    return None


def _find_line_for_product(
        reactor_id: Optional[str],
        tank_id: Optional[str],
        equipment_links: List[Dict],
        equipment_map: Dict[str, Dict],
) -> Optional[str]:
    """
    Находит линию розлива, подключенную к танку или напрямую к реактору.

    Итерация 9: убран неиспользуемый параметр product_code
    (и products_map) — функция не зависит от продукта.
    """
    # Приоритет 1: линия, подключенная к танку
    if tank_id:
        for link in equipment_links:
            if str(link["from_equipment_id"]) == tank_id:
                to_id = str(link["to_equipment_id"])
                target = equipment_map.get(to_id, {})
                if target.get("type") in ("FILLING_LINE", "MANUAL_STATION"):
                    return to_id

    # Приоритет 2: линия, подключенная к реактору
    if reactor_id:
        for link in equipment_links:
            if str(link["from_equipment_id"]) == reactor_id:
                to_id = str(link["to_equipment_id"])
                target = equipment_map.get(to_id, {})
                if target.get("type") in ("FILLING_LINE", "MANUAL_STATION"):
                    return to_id

    return None


def _get_line_operator_pool(line_equipment: Dict) -> Optional[str]:
    """Определяет пул операторов для линии розлива."""
    line_type = line_equipment.get("type")
    if line_type == "MANUAL_STATION":
        return OperatorPool.MANUAL_OPERATOR
    if line_type == "FILLING_LINE":
        return OperatorPool.LINE_OPERATOR
    return None


def _calc_fill_duration(
        batch: Dict,
        product: Dict,
        gp_product: Optional[Dict] = None,
) -> int:
    """Считает длительность слива партии на линию."""
    volume_kg = _to_float(batch.get("volume_kg"))
    if volume_kg <= 0:
        return 0

    if gp_product:
        bottle_volume = _to_float(gp_product.get("bottle_volume_l"))
        fill_speed = _to_float(gp_product.get("fill_speed_per_min"))
        if bottle_volume > 0 and fill_speed > 0:
            bottles = volume_kg / bottle_volume
            duration = bottles / fill_speed
            return max(1, int(duration))

    pf_fill_speed = _to_float(product.get("fill_speed_per_min"))
    if pf_fill_speed > 0:
        duration = volume_kg / pf_fill_speed
        return max(1, int(duration))

    # Fallback: 1 кг = 1 минута
    return max(1, int(volume_kg))


def _assign_operator_pool(
        op: Dict,
        line_equipment: Optional[Dict] = None,
) -> Optional[str]:
    """
    Назначает пул ресурса для операции.

    Итерация 9 (fix): добавлены ветки для COOLING_ZONE и BOILER.

    Приоритет (сверху вниз):
      1. Операции на линии (fill_*) → пул линии.
      2. Лабораторные операции → LAB.
      3. Охлаждение → COOLING_ZONE.
      4. Нагрев → BOILER.
      5. Явно заданный в шаблоне operator_pool.
      6. NULL (нет специфичного ресурса).
    """
    # 1. Операции на линии
    if line_equipment is not None:
        pool = _get_line_operator_pool(line_equipment)
        if pool:
            return pool

    # 2. Лабораторные операции
    if op.get("needs_lab"):
        return OperatorPool.LAB

    # 3. Охлаждение (Итерация 9, fix)
    if op.get("needs_cooling_zone"):
        return OperatorPool.COOLING_ZONE

    # 4. Нагрев (Итерация 9, fix)
    if op.get("needs_boiler"):
        return OperatorPool.BOILER

    # 5. Явно заданный пул из шаблона
    return op.get("operator_pool")


# --- Основная функция ---

def build_routing(
        batch: Dict,
        product: Dict,
        reactor: Dict,
        operations: List[Dict],
        equipment_map: Dict[str, Dict],
        equipment_links: List[Dict],
        products_map: Dict[str, Dict],
        calc_duration,
        gp_product: Optional[Dict] = None,
        truncate_after_lab: bool = False,
) -> List[RoutingStep]:
    """
    Строит цепочку шагов для партии.

    Итерация 9 (fix #2): postponed_wash и postponed_pumping — две
    отдельные переменные. Раньше обе отложенные операции писались
    в одну переменную postponed_op, из-за чего терялся шаг
    TANK_TRANSFER (если после pumping шёл washing).
    """
    if not operations:
        return []

    # 1. Определяем ключевые ресурсы
    reactor_id = _find_reactor_for_batch(batch, equipment_map)
    if reactor_id is None:
        return []

    route_type = product.get("route_type", RouteType.DIRECT)
    tank_id = _find_tank_for_reactor(reactor_id, equipment_links, equipment_map) if route_type == RouteType.VIA_TANK else None
    line_id = _find_line_for_product(reactor_id, tank_id, equipment_links, equipment_map)
    line_equipment = equipment_map.get(line_id, {}) if line_id else None

    # 2. Строим основную часть цепочки
    steps: List[RoutingStep] = []
    prev_op_id: Optional[str] = None
    parallel_group_last_op: Dict[str, str] = {}
    lab_seen = False

    # Итерация 9 (fix #2): раздельные переменные
    postponed_wash: Optional[Dict] = None
    postponed_pumping: Optional[Dict] = None

    for op in operations:
        op_id = str(op["id"])
        is_pumping = op.get("duration_formula") == DurationFormula.PUMPING
        is_washing = op.get("duration_formula") == DurationFormula.WASHING
        needs_lab = op.get("needs_lab", False)

        # Обрезка после лаборатории
        if truncate_after_lab and lab_seen:
            break

        # Откладываем перекачку и замывку "на потом"
        if is_washing:
            postponed_wash = op
            continue

        if is_pumping and route_type == RouteType.VIA_TANK and tank_id:
            postponed_pumping = op
            continue

        # Создаем обычный шаг
        duration = calc_duration(op, batch, reactor, product)
        depends_on, is_parallel_with = _calculate_dependencies(op, prev_op_id, parallel_group_last_op)

        steps.append(RoutingStep(
            op_id=op_id,
            op=op,
            role=TaskRole.REACTOR_OP,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=None,
            duration=duration,
            depends_on_op_ids=depends_on,
            is_parallel_with=is_parallel_with,
            operator_pool=_assign_operator_pool(op),
        ))
        prev_op_id = op_id

        if needs_lab:
            lab_seen = True

    if truncate_after_lab and lab_seen:
        return _finalize_steps(steps)

    # 3. Добавляем перекачку в танк (если есть)
    last_op_before_fill = prev_op_id
    if postponed_pumping is not None and tank_id:
        duration = calc_duration(postponed_pumping, batch, reactor, product)
        steps.append(RoutingStep(
            op_id=str(postponed_pumping["id"]),
            op=postponed_pumping,
            role=TaskRole.TANK_TRANSFER,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=tank_id,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
            operator_pool=_assign_operator_pool(postponed_pumping),
        ))
        prev_op_id = str(postponed_pumping["id"])
        last_op_before_fill = prev_op_id

    # 4. Добавляем слив на линию
    if line_id:
        fill_duration = _calc_fill_duration(batch, product, gp_product)
        fill_op_id = f"fill_{batch['id']}"

        primary_eq = tank_id if tank_id and route_type == RouteType.VIA_TANK else reactor_id
        fill_op = {
            "id": fill_op_id,
            "name": "Слив на линию розлива",
            "duration_formula": DurationFormula.LINE_FILLING,
            "needs_lab": False,
            "needs_cooling_zone": False,
            "needs_boiler": False,
        }

        steps.append(RoutingStep(
            op_id=fill_op_id,
            op=fill_op,
            role=TaskRole.LINE_FILL,
            primary_equipment_id=primary_eq,
            secondary_equipment_id=line_id,
            duration=fill_duration,
            depends_on_op_ids=[last_op_before_fill] if last_op_before_fill else [],
            operator_pool=_assign_operator_pool(fill_op, line_equipment),
        ))
        prev_op_id = fill_op_id

    # 5. Добавляем замывку
    if postponed_wash is not None:
        duration = calc_duration(postponed_wash, batch, reactor, product)
        steps.append(RoutingStep(
            op_id=str(postponed_wash["id"]),
            op=postponed_wash,
            role=TaskRole.WASH,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=None,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
            operator_pool=_assign_operator_pool(postponed_wash),
        ))

    return _finalize_steps(steps)


def _calculate_dependencies(op, prev_op_id, parallel_group_last_op) -> (List[str], List[str]):
    """Вычисляет зависимости для операции."""
    depends_on, is_parallel_with = [], []
    op_parallel_group = op.get("parallel_group_id")

    if op_parallel_group:
        if op_parallel_group in parallel_group_last_op:
            is_parallel_with.append(parallel_group_last_op[op_parallel_group])
        elif prev_op_id:
            depends_on.append(prev_op_id)
        parallel_group_last_op[op_parallel_group] = str(op["id"])
    elif prev_op_id:
        depends_on.append(prev_op_id)

    return depends_on, is_parallel_with


def _finalize_steps(steps: List[RoutingStep]) -> List[RoutingStep]:
    """Устанавливает флаги is_first_in_batch и is_last_in_batch."""
    if not steps:
        return []
    steps[0].is_first_in_batch = True
    steps[-1].is_last_in_batch = True
    return steps


def get_routing_summary(steps: List[RoutingStep]) -> Dict[str, Any]:
    """Возвращает сводку по цепочке."""
    return {
        "total_steps": len(steps),
        "roles": [s.role for s in steps],
        "primary_equipments": [s.primary_equipment_id for s in steps],
        "secondary_equipments": [s.secondary_equipment_id for s in steps],
        "total_duration": sum(s.duration for s in steps),
        "parallel_groups": len({s.op.get("parallel_group_id") for s in steps if s.op.get("parallel_group_id")}),
        "operator_pools": sorted(list({s.operator_pool for s in steps if s.operator_pool})),
    }