# backend/app/scheduler/routing.py
"""
Модуль построения цепочек операций (routing) для партии.

Итерация 1 (исправление 2):
- Длительность слива считается корректно: кг ПФ → бутылки → минуты.

Итерация 5:
- Добавлена поддержка обрезки цепочки для заблокированных партий.

Итерация 6:
- Добавлено поле operator_pool в RoutingStep.
- Для fill_* операций назначается LINE_OPERATOR или MANUAL_OPERATOR
  в зависимости от типа линии.
- Для реакторных операций — значение из operation_template.
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
    LAB_BLOCK = "LAB_BLOCK"


class RouteType:
    DIRECT = "DIRECT"
    VIA_TANK = "VIA_TANK"


# ==========================================
# ИТЕРАЦИЯ 6: КОНСТАНТЫ ПУЛОВ ОПЕРАТОРОВ
# ==========================================

class OperatorPool:
    REACTOR_OPERATOR = "REACTOR_OPERATOR"
    LINE_OPERATOR = "LINE_OPERATOR"
    MANUAL_OPERATOR = "MANUAL_OPERATOR"
    LAB = "LAB"


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
    # Итерация 6: пул операторов
    operator_pool: Optional[str] = None


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
# ИТЕРАЦИЯ 6: ПУЛ ДЛЯ ЛИНИИ
# ==========================================

def _get_line_operator_pool(line_equipment: Dict) -> Optional[str]:
    """
    Определяет пул операторов для линии розлива.

    Логика:
      - FILLING_LINE → LINE_OPERATOR
      - MANUAL_STATION → MANUAL_OPERATOR
    """
    line_type = line_equipment.get("type")
    if line_type == "MANUAL_STATION":
        return OperatorPool.MANUAL_OPERATOR
    if line_type == "FILLING_LINE":
        return OperatorPool.LINE_OPERATOR
    return None


# ==========================================
# РАСЧЁТ ДЛИТЕЛЬНОСТИ СЛИВА
# ==========================================

def _calc_fill_duration(
        batch: Dict,
        product: Dict,
        gp_product: Optional[Dict] = None,
) -> int:
    """Считает длительность слива партии на линию."""
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

    Итерация 6: назначает operator_pool для каждого шага.
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

    lab_seen = False

    for op in operations:
        op_id = str(op["id"])
        op_parallel_group = op.get("parallel_group_id")
        is_pumping = op.get("duration_formula") == "pumping"
        is_washing = op.get("duration_formula") == "washing"
        needs_lab = op.get("needs_lab", False)

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

        # Итерация 6: определяем пул операторов для операции
        operator_pool = op.get("operator_pool")
        if operator_pool is None and op.get("needs_lab", False):
            # Лабораторный анализ — пул LAB
            operator_pool = OperatorPool.LAB

        steps.append(RoutingStep(
            op_id=op_id,
            op=op,
            role=role,
            primary_equipment_id=primary_eq,
            secondary_equipment_id=secondary_eq,
            duration=duration,
            depends_on_op_ids=depends_on,
            is_parallel_with=is_parallel_with,
            operator_pool=operator_pool,
        ))

        prev_op_id = op_id

        if needs_lab:
            lab_seen = True

    if truncate_after_lab and lab_seen:
        if steps:
            steps[-1].is_last_in_batch = True
            steps[0].is_first_in_batch = True
        return steps

    # TANK_TRANSFER
    last_op_before_fill = prev_op_id
    if postponed_pumping is not None and tank_id:
        duration = calc_duration(postponed_pumping, batch, reactor, product)
        op_id = str(postponed_pumping["id"])

        operator_pool = postponed_pumping.get("operator_pool")

        steps.append(RoutingStep(
            op_id=op_id,
            op=postponed_pumping,
            role=TaskRole.TANK_TRANSFER,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=tank_id,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
            operator_pool=operator_pool,
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

        # Итерация 6: определяем пул для линии
        line_equipment = equipment_map.get(line_id, {})
        line_operator_pool = _get_line_operator_pool(line_equipment)

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
                "operator_pool": line_operator_pool,
            },
            role=TaskRole.LINE_FILL,
            primary_equipment_id=primary_eq,
            secondary_equipment_id=secondary_eq,
            duration=fill_duration,
            depends_on_op_ids=[last_op_before_fill] if last_op_before_fill else [],
            operator_pool=line_operator_pool,
        ))
        prev_op_id = fill_op_id

    # WASH
    if postponed_wash is not None:
        duration = calc_duration(postponed_wash, batch, reactor, product)
        op_id = str(postponed_wash["id"])

        operator_pool = postponed_wash.get("operator_pool")

        steps.append(RoutingStep(
            op_id=op_id,
            op=postponed_wash,
            role=TaskRole.WASH,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=None,
            duration=duration,
            depends_on_op_ids=[prev_op_id] if prev_op_id else [],
            operator_pool=operator_pool,
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
        "operator_pools": [s.operator_pool for s in steps if s.operator_pool],
    }