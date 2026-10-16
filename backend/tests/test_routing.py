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

Итерация 18 (fix #gap):
  - Проверка, что у всех шагов max_gap_after_minutes = 0.

Итерация 19 (fix #parallel-last):
  - Проверка, что после параллельной группы зависит только
    операция с МАКСИМАЛЬНОЙ длительностью (устраняет 38-часовые
    разрывы между группой и следующим шагом).

Итерация 19 (fix #parallel-tests):
  - Проверка, что параллельные операции имеют is_parallel_with,
    указывающий на «якорь» группы.
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
        gp_product=_make_gp_product("GP_DISH_1L"),
    )

    assert steps[-1].role == TaskRole.WASH
    assert steps[-2].role == TaskRole.LINE_FILL
    assert all(s.role != TaskRole.TANK_TRANSFER for s in steps)

    fill_parts = _count_fill_parts(steps)
    assert fill_parts >= 1

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

    transfer_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.TANK_TRANSFER)
    fill_indices = [i for i, s in enumerate(steps) if s.role == TaskRole.LINE_FILL]
    wash_idx = next(i for i, s in enumerate(steps) if s.role == TaskRole.WASH)

    assert transfer_idx < min(fill_indices), "TANK_TRANSFER должен быть до LINE_FILL"
    assert max(fill_indices) < wash_idx, "LINE_FILL должен быть до WASH"

    transfer = steps[transfer_idx]
    assert transfer.primary_equipment_id == "REACTOR_1"
    assert transfer.secondary_equipment_id == "TANK_1"

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

    assert summary["total_steps"] >= 12
    assert summary["total_duration"] > 0
    assert "REACTOR_OP" in summary["roles"]
    assert "LINE_FILL" in summary["roles"]
    assert "WASH" in summary["roles"]
    assert summary["parallel_groups"] >= 2


def test_wash_depends_on_fill_for_direct():
    """DIRECT-маршрут: WASH зависит от LINE_FILL."""
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
    assert last_fill.op_id in wash.depends_on_op_ids


def test_wash_depends_on_tank_transfer_for_via_tank():
    """VIA_TANK-маршрут: WASH зависит от TANK_TRANSFER, а НЕ от LINE_FILL."""
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
    assert len(transfer_steps) == 1
    assert len(fill_steps) >= 1

    transfer = transfer_steps[0]
    last_fill = fill_steps[-1]

    assert transfer.op_id in wash.depends_on_op_ids
    assert last_fill.op_id not in wash.depends_on_op_ids


# ==========================================
# ТЕСТЫ: ОБРЕЗКА ПОСЛЕ ЛАБОРАТОРИИ (Итерация 5)
# ==========================================

def test_truncate_after_lab_cream():
    """Крем-мыло: обрезка после первой lab-операции."""
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
    """Антисептик: lab на этапе 3, значит остаётся 3 шага."""
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
    """Средство: lab на этапе 4, значит остаётся 4 шага."""
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
    """truncate_after_lab=False — полная цепочка с разбиением LINE_FILL."""
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

    assert steps[-1].role == TaskRole.WASH

    reactor_ops = [s for s in steps if s.role == TaskRole.REACTOR_OP]
    fill_steps = [s for s in steps if s.role == TaskRole.LINE_FILL]
    wash_steps = [s for s in steps if s.role == TaskRole.WASH]

    assert len(reactor_ops) == 6
    assert len(fill_steps) >= 1
    assert len(wash_steps) == 1

    pumping_steps = [
        s for s in steps
        if s.op.get("duration_formula") == "pumping"
    ]
    assert len(pumping_steps) == 0


def test_pumping_skipped_for_direct_route():
    """Итерация 13.6: для DIRECT-маршрута PUMPING-операции пропускаются."""
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

    assert not any(s.role == TaskRole.TANK_TRANSFER for s in steps)

    pumping_steps = [
        s for s in steps
        if s.op.get("duration_formula") == DurationFormula.PUMPING
    ]
    assert len(pumping_steps) == 0


def test_pumping_preserved_for_via_tank_route():
    """Итерация 13.6: для VIA_TANK-маршрута PUMPING → TANK_TRANSFER."""
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

    transfer_steps = [s for s in steps if s.role == TaskRole.TANK_TRANSFER]
    assert len(transfer_steps) == 1

    transfer = transfer_steps[0]
    assert transfer.primary_equipment_id == "REACTOR_1"
    assert transfer.secondary_equipment_id == "TANK_1"


# ==========================================
# ИТЕРАЦИЯ 18 (fix #gap): ТЕСТЫ ЗАЗОРОВ
# ==========================================

def test_max_gap_after_minutes_default_zero():
    """
    Итерация 18 (fix #gap): у всех шагов цепочки
    max_gap_after_minutes = 0 (по ТЗ операции идут непрерывно).

    Проверяем для PF_DISH (DIRECT) и PF_CREAM (VIA_TANK).
    """
    for pf_code, gp_code, reactor in [
        ("PF_DISH", "GP_DISH_1L", "REACTOR_2"),
        ("PF_CREAM", "GP_CREAM_1L", "REACTOR_1"),
    ]:
        batch = {
            "id": f"b_{pf_code}",
            "product_id": pf_code,
            "volume_kg": 5000,
            "assigned_equipment_id": reactor,
        }
        steps = build_routing(
            batch=batch,
            product=_make_products_map()[pf_code],
            reactor=_make_equipment_map()[reactor],
            operations=_make_operations_for_pf(pf_code),
            equipment_map=_make_equipment_map(),
            equipment_links=_make_links(),
            products_map=_make_products_map(),
            calc_duration=_calc_duration,
            gp_product=_make_gp_product(gp_code),
        )

        assert len(steps) > 0, f"Цепочка для {pf_code} пуста"

        for step in steps:
            assert step.max_gap_after_minutes == 0, (
                f"{pf_code}: шаг {step.op_id} ({step.op.get('name')}) "
                f"имеет max_gap_after_minutes="
                f"{step.max_gap_after_minutes}, ожидалось 0"
            )


# ==========================================
# ИТЕРАЦИЯ 19 (fix #parallel-last): ТЕСТЫ ЗАВИСИМОСТЕЙ ПОСЛЕ ГРУППЫ
# ==========================================

def test_parallel_deps_use_max_duration():
    """
    Итерация 19 (fix #parallel-last): для PF_DISH после группы
    GROUP1 (Перемешивание 120 мин ∥ Охлаждение 90 мин) операция
    «Лабораторный анализ» зависит ОТ ОДНОЙ операции —
    Перемешивания (длительность 120 > 90).

    Это устраняет разрывы: раньше «Лаб.анализ» зависел от обеих
    операций группы и получал только нижние границы (gap не применялся).
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

    # Находим операции группы GROUP1 (Перемешивание, Охлаждение)
    group1_steps = [
        s for s in steps
        if s.op.get("parallel_group_id") == "GROUP1"
    ]
    assert len(group1_steps) == 2, (
        f"Ожидалось 2 операции в GROUP1, получено {len(group1_steps)}"
    )

    # Определяем, какая из них длиннее
    mixing = next(
        (s for s in group1_steps if s.duration == 120), None
    )
    cooling = next(
        (s for s in group1_steps if s.duration == 90), None
    )
    assert mixing is not None, "Перемешивание (120 мин) не найдено"
    assert cooling is not None, "Охлаждение (90 мин) не найдено"

    # Операция сразу после GROUP1 — «Лабораторный анализ»
    # (следуем по depends_on_op_ids: ищем шаг, который зависит от группы)
    lab_step = None
    for s in steps:
        for dep_id in s.depends_on_op_ids:
            if dep_id in (mixing.op_id, cooling.op_id):
                lab_step = s
                break
        if lab_step:
            break

    assert lab_step is not None, (
        "Не найдена операция, зависящая от GROUP1"
    )

    # Итерация 19: depends_on ДОЛЖЕН содержать ТОЛЬКО Перемешивание (120 мин),
    # а НЕ обе операции группы.
    assert mixing.op_id in lab_step.depends_on_op_ids, (
        f"«{lab_step.op.get('name')}» должна зависеть от Перемешивания "
        f"(max duration=120). depends_on={lab_step.depends_on_op_ids}"
    )
    assert cooling.op_id not in lab_step.depends_on_op_ids, (
        f"«{lab_step.op.get('name')}» НЕ должна зависеть от Охлаждения "
        f"(duration=90 < 120). depends_on={lab_step.depends_on_op_ids}"
    )
    assert len(lab_step.depends_on_op_ids) == 1, (
        f"Ожидался ровно 1 предок, получено "
        f"{len(lab_step.depends_on_op_ids)}: {lab_step.depends_on_op_ids}"
    )


def test_parallel_deps_use_max_duration_cream():
    """
    Для PF_CREAM после GROUP1 (Перемешивание 90 мин ∥ Охлаждение 120 мин)
    «Лабораторный анализ» зависит от ОХЛАЖДЕНИЯ (120 > 90).
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

    group1_steps = [
        s for s in steps
        if s.op.get("parallel_group_id") == "GROUP1"
    ]
    assert len(group1_steps) == 2

    mixing = next((s for s in group1_steps if s.duration == 90), None)
    cooling = next((s for s in group1_steps if s.duration == 120), None)
    assert mixing is not None, "Перемешивание (90 мин) не найдено"
    assert cooling is not None, "Охлаждение (120 мин) не найдено"

    lab_step = None
    for s in steps:
        for dep_id in s.depends_on_op_ids:
            if dep_id in (mixing.op_id, cooling.op_id):
                lab_step = s
                break
        if lab_step:
            break

    assert lab_step is not None
    assert cooling.op_id in lab_step.depends_on_op_ids, (
        f"«{lab_step.op.get('name')}» должна зависеть от Охлаждения "
        f"(max duration=120)"
    )
    assert mixing.op_id not in lab_step.depends_on_op_ids
    assert len(lab_step.depends_on_op_ids) == 1


# ==========================================
# ИТЕРАЦИЯ 18 (fix #parallel): is_parallel_with
# ==========================================

def test_parallel_ops_share_start():
    """
    Итерация 18 (fix #parallel): у «Охлаждения» (второй операции
    группы) должен быть заполнен is_parallel_with, указывающий
    на первую операцию группы («Перемешивание»).

    Это гарантирует, что в core.py они получат одинаковый start.
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

    # Операции с parallel_group_id
    parallel_steps = [
        s for s in steps if s.op.get("parallel_group_id")
    ]
    # Первая в каждой группе — is_parallel_with пустой.
    # Вторая — is_parallel_with = [op_id первой].
    anchors = [
        s for s in parallel_steps if not s.is_parallel_with
    ]
    followers = [
        s for s in parallel_steps if s.is_parallel_with
    ]

    # Ожидаем 2 анкера (GROUP1 + GROUP2) и 2 followers
    assert len(anchors) == 2, (
        f"Ожидалось 2 анкера групп, получено {len(anchors)}"
    )
    assert len(followers) == 2, (
        f"Ожидалось 2 followers (вторые операции групп), "
        f"получено {len(followers)}"
    )

    # Каждый follower должен ссылаться на анкер своей группы
    for f in followers:
        group = f.op.get("parallel_group_id")
        anchor = next(
            a for a in anchors
            if a.op.get("parallel_group_id") == group
        )
        assert f.is_parallel_with == [anchor.op_id], (
            f"Follower группы {group} должен ссылаться на "
            f"{anchor.op_id}, а ссылается на {f.is_parallel_with}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])