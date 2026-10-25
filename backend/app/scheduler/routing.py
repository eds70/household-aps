# backend/app/scheduler/routing.py
"""
Модуль построения цепочек операций (routing) для партии.

Итерация 34 (fix #capability-check):
  - Добавлена проверка: если реактор, к которому привязана партия,
    не имеет capability для этого ПФ, партия пропускается.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)

Number = Union[int, float, Decimal]

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

class OperatorPool:
    REACTOR_OPERATOR = "REACTOR_OPERATOR"
    LINE_OPERATOR = "LINE_OPERATOR"
    MANUAL_OPERATOR = "MANUAL_OPERATOR"
    LAB = "LAB"
    COOLING_ZONE = "COOLING_ZONE"
    BOILER = "BOILER"

class DurationFormula:
    WATER_LOADING = "water_loading"
    HEATING = "heating"
    MIXING = "mixing"
    COOLING = "cooling"
    PUMPING = "pumping"
    WASHING = "washing"
    LINE_FILLING = "line_filling"

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
    operator_pool: Optional[str] = None
    max_gap_after_minutes: int = 0

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
        equipment_links: List[Dict],
        equipment_map: Dict[str, Dict],
        gp_product_id: Optional[str] = None,
        equipment_capability: Optional[List[Dict]] = None,
) -> Optional[str]:
    if gp_product_id and equipment_capability:
        candidates = [
            cap for cap in equipment_capability
            if str(cap["product_id"]) == str(gp_product_id)
        ]

        if candidates:
            if reactor_id and len(candidates) > 1:
                lines_from_reactor = set()
                for link in equipment_links:
                    if str(link["from_equipment_id"]) == reactor_id:
                        lines_from_reactor.add(str(link["to_equipment_id"]))
                if tank_id:
                    for link in equipment_links:
                        if str(link["from_equipment_id"]) == tank_id:
                            lines_from_reactor.add(str(link["to_equipment_id"]))

                connected = [
                    cap for cap in candidates
                    if str(cap["equipment_id"]) in lines_from_reactor
                ]
                if connected:
                    candidates = connected

            return str(candidates[0]["equipment_id"])

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

def _get_line_operator_pool(line_equipment: Dict) -> Optional[str]:
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

    return max(1, int(volume_kg))

def _assign_operator_pool(
        op: Dict,
        line_equipment: Optional[Dict] = None,
) -> Optional[str]:
    if line_equipment is not None:
        pool = _get_line_operator_pool(line_equipment)
        if pool:
            return pool

    if op.get("needs_lab"):
        return OperatorPool.LAB

    if op.get("needs_cooling_zone"):
        return OperatorPool.COOLING_ZONE

    if op.get("needs_boiler"):
        return OperatorPool.BOILER

    return op.get("operator_pool")

def _split_fill_duration(
        total_duration: int,
        shift_mode: str = "2x12",
) -> List[int]:
    if shift_mode == "1x8":
        max_part = 6 * 60
    elif shift_mode == "3x8":
        max_part = 6 * 60
    elif shift_mode == "2x12":
        max_part = 10 * 60
    else:
        max_part = 8 * 60

    if total_duration <= max_part:
        return [total_duration]

    num_parts = (total_duration + max_part - 1) // max_part
    base_part = total_duration // num_parts
    remainder = total_duration - base_part * num_parts

    parts = [base_part] * num_parts
    for i in range(remainder):
        parts[i] += 1

    return parts

def _apply_gap_defaults(steps: List[RoutingStep]) -> List[RoutingStep]:
    if not steps:
        return steps

    for step in steps:
        gap = int(step.op.get("wait_after_mins", 0) or 0)
        if gap < 0:
            gap = 0
        step.max_gap_after_minutes = gap

    return steps

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
        equipment_capability: Optional[List[Dict]] = None,
        truncate_after_lab: bool = False,
        shift_mode: str = "2x12",
) -> List[RoutingStep]:
    """Строит цепочку шагов для партии."""
    if not operations:
        log_with_context(
            logger, logging.WARNING,
            f"[routing] Пропущена партия {batch.get('id')}: "
            f"у продукта {product.get('code', product.get('id'))} "
            f"(type={product.get('type', '?')}) "
            f"нет operation_template. "
            f"Партия выпадет из плана.",
            stage="routing",
        )
        return []

    reactor_id = _find_reactor_for_batch(batch, equipment_map)
    if reactor_id is None:
        return []

    # ==========================================
    # Итерация 34 (fix #capability-check):
    # Проверяем, что реактор может варить этот ПФ.
    # ==========================================
    product_id = str(product.get("id", ""))
    if equipment_capability and product_id:
        can_produce = any(
            str(cap.get("equipment_id")) == reactor_id
            and str(cap.get("product_id")) == product_id
            for cap in equipment_capability
        )
        if not can_produce:
            log_with_context(
                logger, logging.WARNING,
                f"[routing] Пропущена партия {batch.get('id')}: "
                f"реактор {reactor.get('name', reactor_id)} "
                f"не предназначен для варки продукта "
                f"{product.get('code', product_id)}. "
                f"Партия выпадет из плана.",
                stage="routing",
            )
            return []

    route_type = product.get("route_type", RouteType.DIRECT)
    tank_id = (
        _find_tank_for_reactor(reactor_id, equipment_links, equipment_map)
        if route_type == RouteType.VIA_TANK
        else None
    )

    gp_product_id = (
        str(gp_product["id"]) if gp_product and gp_product.get("id") else None
    )
    line_id = _find_line_for_product(
        reactor_id=reactor_id,
        tank_id=tank_id,
        equipment_links=equipment_links,
        equipment_map=equipment_map,
        gp_product_id=gp_product_id,
        equipment_capability=equipment_capability,
    )
    line_equipment = equipment_map.get(line_id, {}) if line_id else None

    steps: List[RoutingStep] = []
    prev_op_id: Optional[str] = None
    parallel_group_last_op: Dict[str, str] = {}
    group_ops_by_id: Dict[str, List[Tuple[str, int]]] = {}

    lab_seen = False
    postponed_wash: Optional[Dict] = None
    postponed_pumping: Optional[Dict] = None

    for op in operations:
        op_id = str(op["id"])
        is_pumping = op.get("duration_formula") == DurationFormula.PUMPING
        is_washing = op.get("duration_formula") == DurationFormula.WASHING
        needs_lab = op.get("needs_lab", False)

        if truncate_after_lab and lab_seen:
            break

        if is_washing:
            postponed_wash = op
            continue

        if is_pumping:
            if route_type == RouteType.VIA_TANK and tank_id:
                postponed_pumping = op
            continue

        duration = calc_duration(op, batch, reactor, product)
        depends_on, is_parallel_with = _calculate_dependencies(
            op, prev_op_id, parallel_group_last_op, group_ops_by_id, duration
        )

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

    # 4. Слив на линию
    if line_id:
        fill_duration = _calc_fill_duration(batch, product, gp_product)
        fill_op_id = f"fill_{batch['id']}"

        primary_eq = (
            tank_id
            if tank_id and route_type == RouteType.VIA_TANK
            else reactor_id
        )

        fill_op_template = {
            "id": fill_op_id,
            "name": "Слив на линию розлива",
            "duration_formula": DurationFormula.LINE_FILLING,
            "needs_lab": False,
            "needs_cooling_zone": False,
            "needs_boiler": False,
        }

        part_durations = _split_fill_duration(
            fill_duration,
            shift_mode=shift_mode,
        )

        if len(part_durations) == 1:
            steps.append(RoutingStep(
                op_id=fill_op_id,
                op=fill_op_template,
                role=TaskRole.LINE_FILL,
                primary_equipment_id=primary_eq,
                secondary_equipment_id=line_id,
                duration=fill_duration,
                depends_on_op_ids=(
                    [last_op_before_fill] if last_op_before_fill else []
                ),
                operator_pool=_assign_operator_pool(
                    fill_op_template, line_equipment
                ),
            ))
            prev_op_id = fill_op_id
        else:
            num_parts = len(part_durations)
            prev_part_id = last_op_before_fill

            for i, part_dur in enumerate(part_durations):
                part_id = f"{fill_op_id}_part{i + 1}"
                part_op = {
                    **fill_op_template,
                    "id": part_id,
                    "name": (
                        f"Слив на линию розлива "
                        f"(часть {i + 1}/{num_parts})"
                    ),
                }

                steps.append(RoutingStep(
                    op_id=part_id,
                    op=part_op,
                    role=TaskRole.LINE_FILL,
                    primary_equipment_id=primary_eq,
                    secondary_equipment_id=line_id,
                    duration=part_dur,
                    depends_on_op_ids=(
                        [prev_part_id] if prev_part_id else []
                    ),
                    operator_pool=_assign_operator_pool(
                        part_op, line_equipment
                    ),
                ))
                prev_part_id = part_id

            prev_op_id = prev_part_id

    # 5. Замыв реактора
    if postponed_wash is not None:
        duration = calc_duration(postponed_wash, batch, reactor, product)

        if route_type == RouteType.VIA_TANK and tank_id:
            wash_deps = [last_op_before_fill] if last_op_before_fill else []
        else:
            wash_deps = [prev_op_id] if prev_op_id else []

        steps.append(RoutingStep(
            op_id=str(postponed_wash["id"]),
            op=postponed_wash,
            role=TaskRole.WASH,
            primary_equipment_id=reactor_id,
            secondary_equipment_id=None,
            duration=duration,
            depends_on_op_ids=wash_deps,
            operator_pool=_assign_operator_pool(postponed_wash),
        ))

    return _finalize_steps(steps)

def _calculate_dependencies(
        op,
        prev_op_id,
        parallel_group_last_op,
        group_ops_by_id,
        current_duration,
):
    depends_on, is_parallel_with = [], []
    op_parallel_group = op.get("parallel_group_id")

    if op_parallel_group:
        if op_parallel_group in parallel_group_last_op:
            is_parallel_with.append(parallel_group_last_op[op_parallel_group])
        elif prev_op_id:
            depends_on.append(prev_op_id)

        parallel_group_last_op[op_parallel_group] = str(op["id"])
        group_ops_by_id.setdefault(op_parallel_group, []).append(
            (str(op["id"]), int(current_duration))
        )
    else:
        if prev_op_id:
            prev_group_id: Optional[str] = None
            for gid, ops in group_ops_by_id.items():
                for (oid, _dur) in ops:
                    if oid == prev_op_id:
                        prev_group_id = gid
                        break
                if prev_group_id:
                    break

            if prev_group_id is not None:
                ops_in_group = group_ops_by_id[prev_group_id]
                if ops_in_group:
                    last_op_id, _last_dur = max(
                        ops_in_group, key=lambda pair: pair[1]
                    )
                    depends_on.append(last_op_id)
                else:
                    depends_on.append(prev_op_id)
            else:
                depends_on.append(prev_op_id)

    return depends_on, is_parallel_with

def _finalize_steps(steps: List[RoutingStep]) -> List[RoutingStep]:
    if not steps:
        return []

    steps[0].is_first_in_batch = True
    steps[-1].is_last_in_batch = True

    _apply_gap_defaults(steps)

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
        "operator_pools": sorted(list({
            s.operator_pool for s in steps if s.operator_pool
        })),
        "max_gap_after_minutes": [s.max_gap_after_minutes for s in steps],
    }