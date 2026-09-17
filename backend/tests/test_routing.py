# backend/tests/test_routing.py
"""
Тесты модуля routing (Итерация 1).

Проверяют построение цепочек операций:
- DIRECT: реактор → линия
- VIA_TANK: реактор → танк → линия
- Слив занимает два ресурса
- Замыв реактора идёт ПОСЛЕ слива (в конце цепочки)

Итерация 5: тесты обрезки цепочки после лаборатории (truncate_after_lab).
"""

import pytest

from app.scheduler.routing import (
    build_routing,
    TaskRole,
    get_routing_summary,
    _find_tank_for_reactor,
    _find_line_for_product,
)
from tests.fixtures import tz_case


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _make_equipment_map():
    m = {}
    for r in tz_case.REACTORS:
        m[r["code"]] = {"id": r["code"], "name": r["name"], "type": "REACTOR",
                        "volume_kg": r["volume_kg"], "speed_coeff": r["speed_coeff"],
                        "mixer_type": r["mixer_type"]}
    for t in tz_case.TANKS:
        m[t["code"]] = {"id": t["code"], "name": t["name"], "type": "TANK",
                        "volume_kg": t["volume_kg"], "speed_coeff": t["speed_coeff"],
                        "mixer_type": None}
    for l in tz_case.FILLING_LINES:
        m[l["code"]] = {"id": l["code"], "name": l["name"], "type": l["type"],
                        "volume_kg": None, "speed_coeff": None, "mixer_type": None}
    m["BOILER"] = {"id": "BOILER", "name": "Бойлер", "type": "BOILER",
                   "volume_kg": 2000, "speed_coeff": None, "mixer_type": None}
    return m


def _make_links():
    return [
        {"from_equipment_id": f, "to_equipment_id": t, "is_direct": d}
        for (f, t, d) in tz_case.EQUIPMENT_LINKS
    ]


def _make_products_map():
    m = {}
    for p in tz_case.PF_PRODUCTS:
        m[p["code"]] = {"id": p["code"], "code": p["code"], "name": p["name"],
                        "type": "PF", "route_type": p["route_type"],
                        "viscosity_coeff": p["viscosity_coeff"]}
    return m


def _make_operations_for_pf(pf_code):
    ops = []
    for row in tz_case.OPERATIONS[pf_code]:
        stage, name, duration, boiler, cooling, operator, lab, formula, group = row
        ops.append({
            "id": f"{pf_code}_op_{stage}",
            "product_id": pf_code,
            "stage_order": stage,
            "name": name,
            "base_duration_mins": duration,
            "needs_boiler": boiler,
            "needs_cooling_zone": cooling,
            "needs_operator": operator,
            "needs_lab": lab,
            "duration_formula": formula,
            "parallel_group_id": group,
            "operator_pool": "REACTOR_OPERATOR" if operator else None,
        })
    return ops


def _calc_duration(op, batch, equipment, product):
    return op.get("base_duration_mins", 60)


# ==========================================
# ТЕСТЫ: ПОИСК РЕСУРСОВ
# ==========================================

def test_find_tank_for_reactor1():
    tank = _find_tank_for_reactor("REACTOR_1", _make_links(), _make_equipment_map())
    assert tank == "TANK_1"


def test_find_tank_for_reactor2_is_none():
    tank = _find_tank_for_reactor("REACTOR_2", _make_links(), _make_equipment_map())
    assert tank is None


def test_find_line_for_reactor2_direct():
    line = _find_line_for_product(
        reactor_id="REACTOR_2",
        tank_id=None,
        product_code="PF_DISH",
        equipment_links=_make_links(),
        equipment_map=_make_equipment_map(),
        products_map=_make_products_map(),
    )
    assert line in ("LINE_1", "LINE_2")


def test_find_line_via_tank():
    line = _find_line_for_product(
        reactor_id="REACTOR_1",
        tank_id="TANK_1",
        product_code="PF_CREAM",
        equipment_links=_make_links(),
        equipment_map=_make_equipment_map(),
        products_map=_make_products_map(),
    )
    assert line == "LINE_1"


# ==========================================
# ТЕСТЫ: ПОСТРОЕНИЕ ЦЕПОЧКИ
# ==========================================

def test_build_routing_direct_dish():
    """Средство: DIRECT-маршрут, WASH в конце, LINE_FILL перед WASH."""
    batch = {"id": "b1", "product_id": "PF_DISH", "volume_kg": 7000,
             "assigned_equipment_id": "REACTOR_2"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_DISH"],
        reactor=_make_equipment_map()["REACTOR_2"],
        operations=_make_operations_for_pf("PF_DISH"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    # 8 операций (7 без WASH + WASH в конце) + 1 LINE_FILL = 9 шагов
    assert len(steps) == 9

    # Последний шаг — WASH
    assert steps[-1].role == TaskRole.WASH

    # Предпоследний — LINE_FILL
    assert steps[-2].role == TaskRole.LINE_FILL

    # У DIRECT-маршрута нет TANK_TRANSFER
    assert all(s.role != TaskRole.TANK_TRANSFER for s in steps)


def test_build_routing_via_tank_cream():
    """Крем-мыло: VIA_TANK — TANK_TRANSFER → LINE_FILL → WASH."""
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
             "assigned_equipment_id": "REACTOR_1"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    # 11 операций + 1 LINE_FILL = 12 шагов (TANK_TRANSFER заменяет pumping)
    assert len(steps) == 12

    # TANK_TRANSFER — предпоследний перед LINE_FILL
    transfer_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.TANK_TRANSFER)
    fill_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.LINE_FILL)
    wash_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.WASH)

    assert transfer_idx < fill_idx < wash_idx, (
        f"Порядок должен быть TANK_TRANSFER({transfer_idx}) → "
        f"LINE_FILL({fill_idx}) → WASH({wash_idx})"
    )

    # TANK_TRANSFER занимает REACTOR_1 + TANK_1
    transfer = steps[transfer_idx]
    assert transfer.primary_equipment_id == "REACTOR_1"
    assert transfer.secondary_equipment_id == "TANK_1"

    # LINE_FILL занимает TANK_1 + LINE_1
    line_fill = steps[fill_idx]
    assert line_fill.primary_equipment_id == "TANK_1"
    assert line_fill.secondary_equipment_id == "LINE_1"


def test_build_routing_wash_last():
    """WASH — всегда последний шаг."""
    batch = {"id": "b1", "product_id": "PF_ANTISEPTIC", "volume_kg": 5600,
             "assigned_equipment_id": "REACTOR_3"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_ANTISEPTIC"],
        reactor=_make_equipment_map()["REACTOR_3"],
        operations=_make_operations_for_pf("PF_ANTISEPTIC"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    assert steps[-1].role == TaskRole.WASH
    # WASH занимает только реактор
    wash = steps[-1]
    assert wash.primary_equipment_id == "REACTOR_3"
    assert wash.secondary_equipment_id is None


def test_build_routing_no_reactor():
    batch = {"id": "b1", "product_id": "PF_DISH", "volume_kg": 7000,
             "assigned_equipment_id": None}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_DISH"],
        reactor={},
        operations=_make_operations_for_pf("PF_DISH"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    assert steps == []


def test_routing_parallel_group_cream():
    """У крем-мыла есть параллельные группы GROUP1 и GROUP2."""
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
             "assigned_equipment_id": "REACTOR_1"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    parallel_steps = [s for s in steps if s.op.get("parallel_group_id")]
    assert len(parallel_steps) == 4

    group1 = [s for s in parallel_steps if s.op["parallel_group_id"] == "GROUP1"]
    assert len(group1) == 2
    assert group1[1].is_parallel_with == [group1[0].op_id]


def test_routing_summary():
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
             "assigned_equipment_id": "REACTOR_1"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    summary = get_routing_summary(steps)
    assert summary["total_steps"] == 12
    assert summary["total_duration"] > 0
    assert "REACTOR_OP" in summary["roles"]
    assert "LINE_FILL" in summary["roles"]
    assert "WASH" in summary["roles"]
    assert summary["parallel_groups"] == 2


def test_wash_depends_on_fill():
    """WASH зависит от LINE_FILL (по ТЗ замыв после слива)."""
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
             "assigned_equipment_id": "REACTOR_1"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
    )
    wash = steps[-1]
    fill = steps[-2]
    assert wash.role == TaskRole.WASH
    assert fill.role == TaskRole.LINE_FILL
    assert fill.op_id in wash.depends_on_op_ids


# ==========================================
# ТЕСТЫ: ОБРЕЗКА ПОСЛЕ ЛАБОРАТОРИИ (Итерация 5)
# ==========================================

def test_truncate_after_lab_cream():
    """
    Крем-мыло: обрезка после первой lab-операции.
    Lab на этапе 5, значит остаётся 5 шагов.
    """
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
             "assigned_equipment_id": "REACTOR_1"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=True,
    )
    assert len(steps) == 5
    assert steps[-1].op.get("needs_lab") is True
    assert steps[-1].is_last_in_batch is True
    assert steps[0].is_first_in_batch is True


def test_truncate_after_lab_antiseptic():
    """
    Антисептик: lab на этапе 3, значит остаётся 3 шага.
    """
    batch = {"id": "b1", "product_id": "PF_ANTISEPTIC", "volume_kg": 5600,
             "assigned_equipment_id": "REACTOR_3"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_ANTISEPTIC"],
        reactor=_make_equipment_map()["REACTOR_3"],
        operations=_make_operations_for_pf("PF_ANTISEPTIC"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=True,
    )
    assert len(steps) == 3
    assert steps[-1].op.get("needs_lab") is True


def test_truncate_after_lab_dish():
    """
    Средство: lab на этапе 4, значит остаётся 4 шага.
    """
    batch = {"id": "b1", "product_id": "PF_DISH", "volume_kg": 7000,
             "assigned_equipment_id": "REACTOR_2"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_DISH"],
        reactor=_make_equipment_map()["REACTOR_2"],
        operations=_make_operations_for_pf("PF_DISH"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=True,
    )
    assert len(steps) == 4
    assert steps[-1].op.get("needs_lab") is True


def test_truncate_after_lab_false_full_chain():
    """
    truncate_after_lab=False — полная цепочка.
    """
    batch = {"id": "b1", "product_id": "PF_ANTISEPTIC", "volume_kg": 5600,
             "assigned_equipment_id": "REACTOR_3"}
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_ANTISEPTIC"],
        reactor=_make_equipment_map()["REACTOR_3"],
        operations=_make_operations_for_pf("PF_ANTISEPTIC"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=False,
    )
    # 8 операций + 1 LINE_FILL = 9 (у антисептика DIRECT-маршрут)
    assert len(steps) == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])