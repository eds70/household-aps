# backend/tests/test_routing.py
"""
Тесты модуля routing (Итерация 1).

Проверяют построение цепочек операций:
- DIRECT: реактор → линия
- VIA_TANK: реактор → танк → линия
- Слив занимает два ресурса
- Замыв реактора идёт ПОСЛЕ слива (в конце цепочки)

Итерация 5: тесты обрезки цепочки после лаборатории (truncate_after_lab).

Итерация 11 (Шаг 6): тесты учитывают разбиение длинных LINE_FILL
на подзадачи по shift_mode. Ожидания гибкие — проверяем наличие
fill_*_part* и отсутствие неожиданных ролей, а не точное число шагов.
"""

import pytest

from app.scheduler.routing import (
    build_routing,
    TaskRole,
    DurationFormula,
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
    for p in tz_case.GP_PRODUCTS:
        m[p["code"]] = {"id": p["code"], "code": p["code"], "name": p["name"],
                        "type": "GP",
                        "bottle_volume_l": p["bottle_volume_l"],
                        "fill_speed_per_min": p["fill_speed_per_min"]}
    return m


def _make_gp_product(gp_code: str):
    """Возвращает GP-продукт из фикстуры (для передачи в build_routing)."""
    for p in tz_case.GP_PRODUCTS:
        if p["code"] == gp_code:
            return {
                "id": p["code"],
                "code": p["code"],
                "name": p["name"],
                "bottle_volume_l": p["bottle_volume_l"],
                "fill_speed_per_min": p["fill_speed_per_min"],
            }
    return None


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


def _count_fill_parts(steps):
    """Сколько шагов LINE_FILL в цепочке (включая подзадачи)."""
    return sum(1 for s in steps if s.role == TaskRole.LINE_FILL)


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
    """Р2 → LINE_1 или LINE_2 (DIRECT-маршрут, без танка)."""
    line = _find_line_for_product(
        reactor_id="REACTOR_2",
        tank_id=None,
        equipment_links=_make_links(),
        equipment_map=_make_equipment_map(),
    )
    assert line in ("LINE_1", "LINE_2")


def test_find_line_via_tank():
    """Р1 → TANK_1 → LINE_1."""
    line = _find_line_for_product(
        reactor_id="REACTOR_1",
        tank_id="TANK_1",
        equipment_links=_make_links(),
        equipment_map=_make_equipment_map(),
    )
    assert line == "LINE_1"


# ==========================================
# ТЕСТЫ: ПОСТРОЕНИЕ ЦЕПОЧКИ
# ==========================================
# ВАЖНО (Итерация 11): LINE_FILL разбивается на подзадачи
# в зависимости от shift_mode. Тесты проверяют НАЛИЧИЕ ролей
# и порядок, а не точное число шагов.
# ==========================================

def test_build_routing_direct_dish():
    """
    Средство: DIRECT-маршрут, WASH в конце, LINE_FILL перед WASH.
    LINE_FILL разбит на N частей.
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
        gp_product=_make_gp_product("GP_DISH_1L"),
    )

    # Последний шаг — WASH
    assert steps[-1].role == TaskRole.WASH

    # Предпоследний — LINE_FILL (последняя часть слива)
    assert steps[-2].role == TaskRole.LINE_FILL

    # У DIRECT-маршрута нет TANK_TRANSFER
    assert all(s.role != TaskRole.TANK_TRANSFER for s in steps)

    # Есть хотя бы одна часть LINE_FILL
    fill_parts = _count_fill_parts(steps)
    assert fill_parts >= 1

    # REACTOR_OP-шагов ровно 7 (без WASH и LINE_FILL)
    reactor_ops = [s for s in steps if s.role == TaskRole.REACTOR_OP]
    assert len(reactor_ops) == 7


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
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )

    # TANK_TRANSFER → LINE_FILL → WASH
    transfer_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.TANK_TRANSFER)
    fill_indices = [i for i, s in enumerate(steps) if s.role == TaskRole.LINE_FILL]
    wash_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.WASH)

    assert transfer_idx < min(fill_indices), "TANK_TRANSFER должен быть до LINE_FILL"
    assert max(fill_indices) < wash_idx, "LINE_FILL должен быть до WASH"

    # TANK_TRANSFER занимает REACTOR_1 + TANK_1
    transfer = steps[transfer_idx]
    assert transfer.primary_equipment_id == "REACTOR_1"
    assert transfer.secondary_equipment_id == "TANK_1"

    # LINE_FILL занимает TANK_1 + LINE_1
    first_fill = steps[fill_indices[0]]
    assert first_fill.primary_equipment_id == "TANK_1"
    assert first_fill.secondary_equipment_id == "LINE_1"


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
        gp_product=_make_gp_product("GP_ANTISEPTIC_10L"),
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
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )
    parallel_steps = [s for s in steps if s.op.get("parallel_group_id")]
    # 4 шага (2 в GROUP1, 2 в GROUP2). Но с разбиением LINE_FILL
    # может быть больше — проверяем хотя бы группы GROUP1 и GROUP2.
    group1 = [s for s in parallel_steps if s.op["parallel_group_id"] == "GROUP1"]
    group2 = [s for s in parallel_steps if s.op["parallel_group_id"] == "GROUP2"]
    assert len(group1) >= 2
    assert len(group2) >= 2


def test_routing_summary():
    """get_routing_summary корректно считает шаги и роли."""
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
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )
    summary = get_routing_summary(steps)

    # Гибкие проверки: шагов >= 12 (11 операций + минимум 1 LINE_FILL)
    assert summary["total_steps"] >= 12
    assert summary["total_duration"] > 0
    assert "REACTOR_OP" in summary["roles"]
    assert "LINE_FILL" in summary["roles"]
    assert "WASH" in summary["roles"]
    assert summary["parallel_groups"] >= 2


def test_wash_depends_on_fill_for_direct():
    """
    DIRECT-маршрут: WASH зависит от LINE_FILL.

    По ТЗ (Раздел 3, п. 2) реактор освобождается ПОСЛЕ слива на линию.
    Значит, замыв идёт после слива.
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
        gp_product=_make_gp_product("GP_DISH_1L"),
    )
    wash = steps[-1]
    fill_steps = [s for s in steps if s.role == TaskRole.LINE_FILL]
    last_fill = fill_steps[-1]

    assert wash.role == TaskRole.WASH
    assert last_fill.op_id in wash.depends_on_op_ids, (
        "DIRECT: WASH должен зависеть от LINE_FILL (реактор освобождается после слива)"
    )


def test_wash_depends_on_tank_transfer_for_via_tank():
    """
    VIA_TANK-маршрут: WASH зависит от TANK_TRANSFER, а НЕ от LINE_FILL.

    Итерация 13.4 (fix C1): по ТЗ реактор освобождается после перекачки
    в накопительную ёмкость. Значит, замыв может идти параллельно сливу
    на линию — это ускоряет makespan.
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
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )

    wash = steps[-1]
    transfer_steps = [s for s in steps if s.role == TaskRole.TANK_TRANSFER]
    fill_steps = [s for s in steps if s.role == TaskRole.LINE_FILL]

    assert wash.role == TaskRole.WASH
    assert len(transfer_steps) == 1, "Ожидается ровно один TANK_TRANSFER"
    assert len(fill_steps) >= 1, "Ожидается хотя бы один LINE_FILL"

    transfer = transfer_steps[0]
    last_fill = fill_steps[-1]

    assert transfer.op_id in wash.depends_on_op_ids, (
        "VIA_TANK: WASH должен зависеть от TANK_TRANSFER"
    )
    assert last_fill.op_id not in wash.depends_on_op_ids, (
        "VIA_TANK: WASH НЕ должен зависеть от LINE_FILL "
        "(замыв может идти параллельно сливу)"
    )
    
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
        gp_product=_make_gp_product("GP_CREAM_1L"),
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
        gp_product=_make_gp_product("GP_ANTISEPTIC_10L"),
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
        gp_product=_make_gp_product("GP_DISH_1L"),
    )
    assert len(steps) == 4
    assert steps[-1].op.get("needs_lab") is True

def test_truncate_after_lab_false_full_chain():
    """
    truncate_after_lab=False — полная цепочка с разбиением LINE_FILL.

    Итерация 13.6 (fix #roles): для PF_ANTISEPTIC (route_type=DIRECT)
    операция PUMPING («Перекачка в накопительную ёмкость») ПРОПУСКАЕТСЯ,
    потому что у антисептика нет танка — слив идёт напрямую на линию.

    Было: 8 операций → 7 REACTOR_OP + 1 WASH
    Стало: 7 операций (8 − 1 PUMPING) → 6 REACTOR_OP + 1 WASH
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
        gp_product=_make_gp_product("GP_ANTISEPTIC_10L"),
    )

    # Последний — WASH
    assert steps[-1].role == TaskRole.WASH

    reactor_ops = [s for s in steps if s.role == TaskRole.REACTOR_OP]
    fill_steps = [s for s in steps if s.role == TaskRole.LINE_FILL]
    wash_steps = [s for s in steps if s.role == TaskRole.WASH]

    # Итерация 13.6: PUMPING пропускается для DIRECT-маршрута.
    # У PF_ANTISEPTIC 8 операций, из них 1 PUMPING → 7 реальных.
    # Из 7: 6 REACTOR_OP + 1 WASH (WASH выносится отдельно).
    assert len(reactor_ops) == 6, (
        f"Ожидалось 6 REACTOR_OP (8 операций − 1 PUMPING − 1 WASH), "
        f"получено {len(reactor_ops)}"
    )
    assert len(fill_steps) >= 1
    assert len(wash_steps) == 1

    # PUMPING не должен попасть в цепочку ни в какой роли для DIRECT
    pumping_steps = [
        s for s in steps
        if s.op.get("duration_formula") == "pumping"
    ]
    assert len(pumping_steps) == 0, (
        "PUMPING-операция не должна попадать в цепочку "
        "для DIRECT-маршрута (нет танка)"
    )

def test_pumping_skipped_for_direct_route():
    """
    Итерация 13.6 (fix #roles): для DIRECT-маршрута PUMPING-операции
    пропускаются (нет танка — нечего перекачивать).
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
        gp_product=_make_gp_product("GP_ANTISEPTIC_10L"),
    )

    # Ни одного TANK_TRANSFER (DIRECT — без танка)
    assert not any(s.role == TaskRole.TANK_TRANSFER for s in steps)

    # Ни одной PUMPING-операции
    pumping_steps = [
        s for s in steps
        if s.op.get("duration_formula") == DurationFormula.PUMPING
    ]
    assert len(pumping_steps) == 0


def test_pumping_preserved_for_via_tank_route():
    """
    Итерация 13.6 (fix #roles): для VIA_TANK-маршрута PUMPING
    превращается в TANK_TRANSFER.
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
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )

    # Должна быть ровно одна TANK_TRANSFER
    transfer_steps = [s for s in steps if s.role == TaskRole.TANK_TRANSFER]
    assert len(transfer_steps) == 1

    # TANK_TRANSFER занимает реактор + танк
    transfer = transfer_steps[0]
    assert transfer.primary_equipment_id == "REACTOR_1"
    assert transfer.secondary_equipment_id == "TANK_1"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])