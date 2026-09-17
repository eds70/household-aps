# backend/app/scheduler/routing.py
"""
Модуль построения цепочек операций (routing) для партии.

Итерация 1 (исправление 2):
- Длительность слива считается корректно: кг ПФ → бутылки → минуты.
  Формула: bottles = volume_kg / bottle_volume_l;
           duration_min = bottles / fill_speed_per_min
- bottle_volume_l и fill_speed_per_min берутся из ГП (готовой продукции),
  связанной с ПФ через production_order.product_id.

Итерация 5:
- Добавлена поддержка обрезки цепочки для заблокированных партий.
  Если партия заблокирована лабораторией, build_routing может
  вернуть только операции ДО первой needs_lab операции (для отображения
  уже сделанного).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union


Number = Union[int, float, Decimal]


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


class TaskRole:
    REACTOR_OP = "REACTOR_OP"
    TANK_TRANSFER = "TANK_TRANSFER"
    TANK_HOLD = "TANK_HOLD"
    LINE_FILL = "LINE_FILL"
    WASH = "WASH"
    SETUP = "SETUP"
    LAB_BLOCK = "LAB_BLOCK"   # Итерация 5: маркер блокировки


class RouteType:
    DIRECT = "DIRECT"
    VIA_TANK = "VIA_TANK"


@dataclass
class RoutingStep:
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


# ==========================================
# ПОИСК РЕСУРСОВ
# ==========================================

def _find_reactor_for_batch(batch: Dict, equipment_map: Dict[str, Dict]) -> Optional[str]:
    eq_id = batch.get("assigned_equipment_id")
    return str(eq_id) if eq_id else None


def _find_tank_for_reactor(
        reactor_id: str,
        equipment_links: List[Dict],
        equipment_map: Dict[str, Dict],
) -> Optional[str]:
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
        product_code: str,
        equipment_links: List[Dict],
        equipment_map: Dict[str, Dict],
        products_map: Dict[str, Dict],
) -> Optional[str]:
    if tank_id:
        for link in equipment_links:
            if str(link["from_equipment_id"]) == tank_id:
                to_id = str(link["to_equipment_id"])
                target = equipment_map.get(to_id, {})
                if target.get("type") in ("FILLING_LINE", "MANUAL_STATION"):
                    return to_id

    if reactor_id:
        for link in equipment_links:
            if str(link["from_equipment_id"]) == reactor_id:
                to_id = str(link["to_equipment_id"])
                target = equipment_map.get(to_id, {})
                if target.get("type") in ("FILLING_LINE", "MANUAL_STATION"):
                    return to_id

    return None


# ==========================================
# РАСЧЁТ ДЛИТЕЛЬНОСТИ СЛИВА
# ==========================================

def _calc_fill_duration(
        batch: Dict,
        product: Dict,
        gp_product: Optional[Dict] = None,
) -> int:
    """
    Считает длительность слива партии на линию.

    Логика:
      1. Если есть ГП (gp_product) с bottle_volume_l и fill_speed_per_min:
         bottles = volume_kg / bottle_volume_l
         duration = bottles / fill_speed_per_min
      2. Если ГП нет, но у ПФ есть fill_speed_per_min — используем как скорость в кг/мин
      3. Fallback: 1 кг/мин

    Возвращает длительность в минутах (int, минимум 1).
    """
    volume_kg = _to_float(batch.get("volume_kg"), 0.0)
    if volume_kg <= 0:
        return 0

    if gp_product:
        bottle_volume = _to_float(gp_product.get("bottle_volume_l"), 0.0)
        fill_speed = _to_float(gp_product.get("fill_speed_per_min"), 0.0)
        if bottle_volume > 0 and fill_speed > 0:
            bottles = volume_kg / bottle_volume
            duration = bottles / fill_speed
            return max(1, int(duration))

    pf_fill_speed = _to_float(product.get("fill_speed_per_min"), 0.0)
    if pf_fill_speed > 0:
        duration = volume_kg / pf_fill_speed
        return max(1, int(duration))

    return max(1, int(volume_kg))


# ==========================================
# ПОСТРОЕНИЕ ЦЕПОЧКИ
# ==========================================

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

    Аргументы:
        batch:          dict партии
        product:        dict ПФ
        reactor:        dict реактора
        operations:     операции техкарты ПФ
        equipment_map:  {equipment_id: equipment_dict}
        equipment_links: связи оборудования
        products_map:   {product_id: product_dict}
        calc_duration:  функция расчёта длительности реакторных операций
        gp_product:     dict ГП (для слива) — опционально
        truncate_after_lab: Итерация 5 — если True, обрезать цепочку после
                            первой операции с needs_lab = TRUE. Используется
                            для отображения частичного прогресса заблокированной
                            партии.
    """
    if not operations:
        return []

    reactor_id = _find_reactor_for_batch(batch, equipment_map)
    if reactor_id is None:
        return []

    route_type = product.get("route_type", RouteType.DIRECT)

    tank_id: Optional[str] = None
    if route_type == RouteType.VIA_TANK:
        tank_id = _find_tank_for_reactor(reactor_id, equipment_links, equipment_map)

    line_id = _find_line_for_product(
        reactor_id=reactor_id,
        tank_id=tank_id,
        product_code=product.get("code", ""),
        equipment_links=equipment_links,
        equipment_map=equipment_map,
        products_map=products_map,
    )

    steps: List[RoutingStep] = []
    prev_op_id: Optional[str] = None
    parallel_group_last_op: Dict[str, str] = {}

    postponed_wash: Optional[Dict] = None
    postponed_pumping: Optional[Dict] = None

    # Итерация 5: если truncate_after_lab = True, обрезаем цепочку
    lab_seen = False

    for op in operations:
        op_id = str(op["id"])
        op_parallel_group = op.get("parallel_group_id")
        is_pumping = op.get("duration_formula") == "pumping"
        is_washing = op.get("duration_formula") == "washing"
        needs_lab = op.get("needs_lab", False)

        # Итерация 5: если нужно обрезать после лаборатории и мы уже видели lab —
        # останавливаемся
        if truncate_after_lab and lab_seen:
            break

        if is_washing:
            postponed_wash = op
            continue

        if is_pumping and route_type == RouteType.VIA_TANK and tank_id:
            postponed_pumping = op
            continue

        duration = calc_duration(op, batch, reactor, product)

        role = TaskRole.REACTOR_OP
        primary_eq = reactor_id
        secondary_eq: Optional[str] = None

        depends_on: List[str] = []
        is_parallel_with: List[str] = []

        if op_parallel_group:
            if op_parallel_group in parallel_group_last_op:
                is_parallel_with.append(parallel_group_last_op[op_parallel_group])
            else:
                if prev_op_id:
                    depends_on.append(prev_op_id)
            parallel_group_last_op[op_parallel_group] = op_id
        else:
            if prev_op_id:
                depends_on.append(prev_op_id)

        steps.append(RoutingStep(
            op_id=op_id,
            op=op,
            role=role,
            primary_equipment_id=primary_eq,
            secondary_equipment_id=secondary_eq,
            duration=duration,
            depends_on_op_ids=depends_on,
            is_parallel_with=is_parallel_with,
        ))

        prev_op_id = op_id

        # Итерация 5: помечаем, что лабораторная операция пройдена
        if needs_lab:
            lab_seen = True

    # Итерация 5: если обрезали после лабы — не добавляем TANK_TRANSFER/LINE_FILL/WASH
    if truncate_after_lab and lab_seen:
        # Помечаем последнюю операцию как крайнюю
        if steps:
            steps[-1].is_last_in_batch = True
            steps[0].is_first_in_batch = True
        return steps

    # TANK_TRANSFER
    last_op_before_fill = prev_op_id
    if postponed_pumping is not None and tank_id:
        duration = calc_duration(postponed_pumping, batch, reactor, product)
        op_id = str(postponed_pumping["id"])

        steps.append(RoutingStep(
            op_id=op_id,
            op=postponed_pumping,
            role=TaskRole.TANK_TRANSFER,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=tank_id,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
        ))
        prev_op_id = op_id
        last_op_before_fill = op_id

    # LINE_FILL
    if line_id:
        fill_duration = _calc_fill_duration(batch, product, gp_product)

        if route_type == RouteType.VIA_TANK and tank_id and postponed_pumping is not None:
            primary_eq = tank_id
            secondary_eq = line_id
        else:
            primary_eq = reactor_id
            secondary_eq = line_id

        fill_op_id = f"fill_{batch['id']}"
        steps.append(RoutingStep(
            op_id=fill_op_id,
            op={
                "id": fill_op_id,
                "name": "Слив на линию розлива",
                "duration_formula": "line_filling",
                "base_duration_mins": fill_duration,
                "needs_operator": True,
                "needs_lab": False,
                "needs_boiler": False,
                "needs_cooling_zone": False,
                "parallel_group_id": None,
            },
            role=TaskRole.LINE_FILL,
            primary_equipment_id=primary_eq,
            secondary_equipment_id=secondary_eq,
            duration=fill_duration,
            depends_on_op_ids=[last_op_before_fill] if last_op_before_fill else [],
        ))
        prev_op_id = fill_op_id

    # WASH
    if postponed_wash is not None:
        duration = calc_duration(postponed_wash, batch, reactor, product)
        op_id = str(postponed_wash["id"])

        steps.append(RoutingStep(
            op_id=op_id,
            op=postponed_wash,
            role=TaskRole.WASH,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=None,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
        ))

    # Флаги крайних операций
    reactor_ops = [s for s in steps if s.primary_equipment_id == reactor_id]
    if reactor_ops:
        reactor_ops[0].is_first_in_batch = True

        wash_steps = [s for s in steps if s.role == TaskRole.WASH]
        if wash_steps:
            wash_steps[-1].is_last_in_batch = True
        else:
            last_on_reactor = None
            for s in steps:
                if s.primary_equipment_id == reactor_id:
                    last_on_reactor = s
            if last_on_reactor is not None:
                last_on_reactor.is_last_in_batch = True

    return steps


def get_routing_summary(steps: List[RoutingStep]) -> Dict[str, Any]:
    return {
        "total_steps": len(steps),
        "roles": [s.role for s in steps],
        "primary_equipments": [s.primary_equipment_id for s in steps],
        "secondary_equipments": [s.secondary_equipment_id for s in steps],
        "total_duration": sum(s.duration for s in steps),
        "parallel_groups": len({
            s.op.get("parallel_group_id")
            for s in steps
            if s.op.get("parallel_group_id")
        }),
    }