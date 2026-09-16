# backend/tests/test_tz_case.py
"""
Тесты на эталонный кейс из ТЗ (Раздел 4).

Проверяют:
1. Корректность данных фикстуры (количество, суммы, связи)
2. Соответствие ожидаемым результатам
3. Готовность инфраструктуры к интеграционным тестам планировщика

ВАЖНО: ТЗ содержит дефицит отдушки (1650 кг нужно, 1500 на складе).
Тест test_material_availability_expected проверяет, что дефицит
ОБНАРУЖЕН, а не что его нет.
"""

import pytest
from tests.fixtures import tz_case
from tests.fixtures import tz_expected


# ==========================================
# ТЕСТЫ ЦЕЛОСТНОСТИ ДАННЫХ
# ==========================================

def test_materials_count():
    """В ТЗ 11 материалов."""
    assert len(tz_case.MATERIALS) == 11


def test_materials_stock_match_tz():
    """Остатки материалов соответствуют ТЗ."""
    expected_stock = {
        "WATER": 100_000,
        "SALT": 3_000,
        "FRAGRANCE": 1_500,
        "GLYCERIN": 4_000,
        "BETAINE": 1_000,
        "ALCOHOL": 30_000,
        "CHLORIDE": 5_000,
        "BTL1": 30_000,
        "BTL5": 10_000,
        "BTL10": 10_000,
        "CAP": 40_000,
    }
    actual_stock = {m["code"]: m["stock"] for m in tz_case.MATERIALS}
    assert actual_stock == expected_stock


def test_pf_products_count():
    """3 полуфабриката: крем-мыло, средство для посуды, антисептик."""
    assert len(tz_case.PF_PRODUCTS) == 3


def test_gp_products_count():
    """4 готовых продукта."""
    assert len(tz_case.GP_PRODUCTS) == 4


def test_reactors_count():
    """4 реактора."""
    assert len(tz_case.REACTORS) == 4


def test_reactors_volumes_match_tz():
    """Объёмы реакторов соответствуют ТЗ."""
    expected = {
        "REACTOR_1": 5_000,
        "REACTOR_2": 10_000,
        "REACTOR_3": 8_000,
        "REACTOR_4": 5_000,
    }
    actual = {r["code"]: r["volume_kg"] for r in tz_case.REACTORS}
    assert actual == expected


def test_tanks_count():
    """1 накопительная емкость."""
    assert len(tz_case.TANKS) == 1
    assert tz_case.TANKS[0]["code"] == "TANK_1"
    assert tz_case.TANKS[0]["volume_kg"] == 5_000


def test_filling_lines_count():
    """3 линии розлива."""
    assert len(tz_case.FILLING_LINES) == 3


def test_boiler_volume():
    """Бойлер 2000 кг."""
    assert tz_case.BOILER["volume_kg"] == 2_000


def test_orders_count():
    """4 производственных заказа."""
    assert len(tz_case.ORDERS) == 4


def test_orders_target_qty_match_tz():
    """Целевые количества соответствуют ТЗ."""
    expected = {
        "GP_CREAM_1L": 20_000,
        "GP_CREAM_5L": 5_000,
        "GP_DISH_1L": 15_000,
        "GP_ANTISEPTIC_10L": 8_000,
    }
    actual = {o["gp_code"]: o["target_qty"] for o in tz_case.ORDERS}
    assert actual == expected


def test_batches_count():
    """28 партий (пересчитано точно по ТЗ)."""
    assert len(tz_case.BATCHES) == 28
    assert len(tz_case.BATCHES) == tz_case.EXPECTED["total_batches"]


def test_batches_volume_within_max_fill():
    """Объём каждой партии не превышает max_fill_percent от объёма реактора."""
    reactors = {r["code"]: r for r in tz_case.REACTORS}
    for batch in tz_case.BATCHES:
        reactor = reactors[batch["reactor_code"]]
        max_volume = reactor["volume_kg"] * 0.70
        assert batch["volume_kg"] <= max_volume, (
            f"Партия {batch['pf_code']} {batch['volume_kg']} кг "
            f"превышает 70% от {reactor['volume_kg']} кг "
            f"(макс {max_volume} кг)"
        )


def test_batches_pf_allowed_in_reactor():
    """Каждый ПФ варится только в разрешённых реакторах."""
    reactors = {r["code"]: r for r in tz_case.REACTORS}
    for batch in tz_case.BATCHES:
        reactor = reactors[batch["reactor_code"]]
        assert batch["pf_code"] in reactor["pf_codes"], (
            f"ПФ {batch['pf_code']} не может вариться в {batch['reactor_code']}"
        )


def test_batches_total_volume_per_order():
    """Суммарный объём партий соответствует заказу (в кг ПФ)."""
    # Крем-мыло 1л: 20000 кг ПФ (1 бут = 1 кг)
    # Крем-мыло 5л: 25000 кг ПФ (5000 бут × 5 кг)
    # Средство 1л: 15000 кг ПФ
    # Антисептик 10л: 80000 кг ПФ (8000 бут × 10 кг)
    expected_pf_kg = {
        "GP_CREAM_1L": 20_000,
        "GP_CREAM_5L": 25_000,
        "GP_DISH_1L": 15_000,
        "GP_ANTISEPTIC_10L": 80_000,
    }
    actual = {}
    for batch in tz_case.BATCHES:
        code = batch["order_gp_code"]
        actual[code] = actual.get(code, 0) + batch["volume_kg"]
    assert actual == expected_pf_kg


# ==========================================
# ТЕСТЫ ТЕХНОЛОГИЧЕСКИХ КАРТ
# ==========================================

def test_operations_count_per_pf():
    """Количество операций соответствует ожидаемому."""
    for pf_code, expected_count in tz_expected.EXPECTED_OPERATIONS_COUNT.items():
        actual = len(tz_case.OPERATIONS[pf_code])
        assert actual == expected_count, (
            f"{pf_code}: ожидалось {expected_count}, получено {actual}"
        )


def test_operations_stage_order_sequential():
    """Этапы операций идут последовательно (1, 2, 3, ...)."""
    for pf_code, ops in tz_case.OPERATIONS.items():
        stages = [op[0] for op in ops]
        assert stages == list(range(1, len(ops) + 1)), (
            f"{pf_code}: нарушен порядок этапов: {stages}"
        )


def test_operations_cream_has_two_cooling():
    """У крем-мыла два этапа охлаждения (по ТЗ)."""
    cream_ops = tz_case.OPERATIONS["PF_CREAM"]
    cooling_count = sum(1 for op in cream_ops if "Охлаждение" in op[1])
    assert cooling_count == 2


def test_operations_cream_has_two_lab():
    """У крем-мыла два лабораторных анализа (по ТЗ)."""
    cream_ops = tz_case.OPERATIONS["PF_CREAM"]
    lab_count = sum(1 for op in cream_ops if "Лабораторный" in op[1])
    assert lab_count == 2


def test_operations_pumping_only_for_tank_routing():
    """Операция перекачки в танк есть только у ПФ с route_type=VIA_TANK."""
    for pf in tz_case.PF_PRODUCTS:
        ops = tz_case.OPERATIONS[pf["code"]]
        has_pumping = any("Перекачка" in op[1] for op in ops)
        if pf["route_type"] == "VIA_TANK":
            assert has_pumping, f"{pf['code']} должен иметь операцию перекачки"


# ==========================================
# ТЕСТЫ МАТРИЦЫ ЗАМЫВКИ
# ==========================================

def test_setup_matrix_complete():
    """Матрица замывки покрывает все пары ПФ."""
    pf_codes = [pf["code"] for pf in tz_case.PF_PRODUCTS]
    for from_pf in pf_codes:
        for to_pf in pf_codes:
            assert (from_pf, to_pf) in tz_case.SETUP_MATRIX, (
                f"Нет замывки для пары ({from_pf}, {to_pf})"
            )


def test_setup_same_pf_is_30_min():
    """Замывка между партиями одного ПФ = 30 мин."""
    for pf in [p["code"] for p in tz_case.PF_PRODUCTS]:
        assert tz_case.SETUP_MATRIX[(pf, pf)] == 30


def test_setup_diff_pf_is_90_min():
    """Замывка между разными ПФ = 90 мин."""
    pf_codes = [pf["code"] for pf in tz_case.PF_PRODUCTS]
    for from_pf in pf_codes:
        for to_pf in pf_codes:
            if from_pf != to_pf:
                assert tz_case.SETUP_MATRIX[(from_pf, to_pf)] == 90


# ==========================================
# ТЕСТЫ КАЛЕНДАРЯ
# ==========================================

def test_calendar_has_four_weekends():
    """4 выходных периода (сб-вс) в сентябре 2026."""
    weekends = [e for e in tz_case.CALENDAR_EVENTS if e["event_type"] == "WEEKEND"]
    assert len(weekends) == 4


def test_calendar_has_reactor3_repair():
    """Ремонт Р3 с 10 по 20 сентября."""
    repairs = [e for e in tz_case.CALENDAR_EVENTS if e["event_type"] == "REPAIR"]
    assert len(repairs) == 1
    repair = repairs[0]
    assert repair["equipment_code"] == "REACTOR_3"
    assert repair["starts_at"].day == 10
    assert repair["ends_at"].day == 21  # 20 число включительно, значит конец 21-го 00:00


def test_calendar_breakdown_after_planning():
    """Аварийная остановка Р4 (25-28.09) — для сценария перепланирования."""
    assert len(tz_case.CALENDAR_EVENTS_AFTER_PLANNING) == 1
    event = tz_case.CALENDAR_EVENTS_AFTER_PLANNING[0]
    assert event["event_type"] == "BREAKDOWN"
    assert event["equipment_code"] == "REACTOR_4"
    assert event["starts_at"].day == 25


# ==========================================
# ТЕСТЫ РЕСУРСНЫХ ПУЛОВ
# ==========================================

def test_resource_pools_count():
    """4 ресурсных пула."""
    assert len(tz_case.RESOURCE_POOLS) == 4


def test_operators_capacity_is_3():
    """3 аппаратчика (по ТЗ)."""
    operators = [p for p in tz_case.RESOURCE_POOLS if p["type"] == "OPERATOR"][0]
    assert operators["capacity"] == 3


def test_cooling_zone_capacity_is_2():
    """2 реактора могут остывать одновременно (по ТЗ)."""
    cooling = [p for p in tz_case.RESOURCE_POOLS if p["type"] == "COOLING_ZONE"][0]
    assert cooling["capacity"] == 2


def test_boiler_capacity_is_1():
    """Бойлер один."""
    boiler = [p for p in tz_case.RESOURCE_POOLS if p["type"] == "BOILER"][0]
    assert boiler["capacity"] == 1


# ==========================================
# ТЕСТЫ РЕЦЕПТУР
# ==========================================

def test_cream_recipe_sums_to_100():
    """Рецептура крем-мыла на 100 кг."""
    recipe = tz_case.PF_PRODUCTS[0]["recipe"]
    assert recipe["base_volume_kg"] == 100
    total = sum(item["qty"] for item in recipe["items"])
    assert total == 100


def test_dish_recipe_sums_to_100():
    """Рецептура средства для посуды на 100 кг."""
    recipe = tz_case.PF_PRODUCTS[1]["recipe"]
    assert recipe["base_volume_kg"] == 100
    total = sum(item["qty"] for item in recipe["items"])
    assert total == 100


def test_antiseptic_recipe_sums_to_100():
    """Рецептура антисептика на 100 кг."""
    recipe = tz_case.PF_PRODUCTS[2]["recipe"]
    assert recipe["base_volume_kg"] == 100
    total = sum(item["qty"] for item in recipe["items"])
    assert total == 100


def test_all_recipe_materials_exist():
    """Все материалы из рецептур есть в справочнике материалов."""
    material_codes = {m["code"] for m in tz_case.MATERIALS}
    for pf in tz_case.PF_PRODUCTS:
        for item in pf["recipe"]["items"]:
            assert item["material_code"] in material_codes, (
                f"{pf['code']}: материал {item['material_code']} не найден"
            )


# ==========================================
# ТЕСТЫ МАТЕРИАЛЬНОЙ ОБЕСПЕЧЕННОСТИ
# ==========================================
# ВАЖНО: ТЗ содержит дефицит отдушки.
# Тесты должны проверять, что дефицит ОБНАРУЖЕН (для Advisor),
# а не что сырья хватает.

def test_material_shortage_detected_for_fragrance():
    """
    Отдушка: нужно 1650 кг, на складе 1500 кг — дефицит 150 кг.
    Это реальный дефицит по ТЗ, Advisor должен его найти.
    """
    # Расчёт по ТЗ (все заказы)
    cream_kg = 20_000 + 25_000  # Крем-мыло 1л + 5л
    dish_kg = 15_000            # Средство
    # Антисептик отдушку не использует

    fragrance_need = cream_kg * 0.02 + dish_kg * 0.05  # 900 + 750 = 1650
    fragrance_stock = 1_500

    # Дефицит ЕСТЬ
    assert fragrance_need > fragrance_stock
    assert fragrance_need == tz_expected.EXPECTED_ADVICE["fragrance_need_kg"]
    assert fragrance_stock == tz_expected.EXPECTED_ADVICE["fragrance_stock_kg"]
    assert (fragrance_need - fragrance_stock) == tz_expected.EXPECTED_ADVICE["fragrance_deficit_kg"]


def test_material_availability_ok_for_other_materials():
    """Остальные материалы (бетаин, спирт, хлорид) — хватает."""
    dish_kg = 15_000
    antiseptic_kg = 80_000

    # Бетаин
    betaine_need = dish_kg * 0.06  # 900
    betaine_stock = 1_000
    assert betaine_need <= betaine_stock
    assert betaine_need == tz_expected.EXPECTED_ADVICE["betaine_need_kg"]

    # Спирт
    alcohol_need = dish_kg * 0.04 + antiseptic_kg * 0.35  # 600 + 28000 = 28600
    alcohol_stock = 30_000
    assert alcohol_need <= alcohol_stock
    assert alcohol_need == tz_expected.EXPECTED_ADVICE["alcohol_need_kg"]

    # Хлорид
    chloride_need = antiseptic_kg * 0.05  # 4000
    chloride_stock = 5_000
    assert chloride_need <= chloride_stock
    assert chloride_need == tz_expected.EXPECTED_ADVICE["chloride_need_kg"]


# ==========================================
# ТЕСТЫ СВЯЗЕЙ ОБОРУДОВАНИЯ
# ==========================================

def test_equipment_links_reactor1_to_tank():
    """Р1 → Танк 1."""
    assert ("REACTOR_1", "TANK_1", True) in tz_case.EQUIPMENT_LINKS


def test_equipment_links_tank_to_line1():
    """Танк 1 → Линия 1."""
    assert ("TANK_1", "LINE_1", True) in tz_case.EQUIPMENT_LINKS


def test_equipment_links_reactor4_to_line3():
    """Р4 → Линия 3 (ручной слив)."""
    assert ("REACTOR_4", "LINE_3", True) in tz_case.EQUIPMENT_LINKS


def test_line1_connected_to_reactor1_and_reactor2():
    """Линия 1 подключена к Р1 и Р2."""
    line1 = next(l for l in tz_case.FILLING_LINES if l["code"] == "LINE_1")
    assert "REACTOR_1" in line1["connected_to_reactors"]
    assert "REACTOR_2" in line1["connected_to_reactors"]


def test_line3_is_manual():
    """Линия 3 — ручная станция."""
    line3 = next(l for l in tz_case.FILLING_LINES if l["code"] == "LINE_3")
    assert line3["type"] == "MANUAL_STATION"


# ==========================================
# ТЕСТЫ ОЖИДАЕМЫХ РЕЗУЛЬТАТОВ
# ==========================================

def test_expected_totals():
    """Ожидаемые общие количества совпадают с фактическими в фикстуре."""
    assert tz_case.EXPECTED["total_batches"] == len(tz_case.BATCHES)
    assert tz_case.EXPECTED["total_orders"] == len(tz_case.ORDERS)
    assert tz_case.EXPECTED["reactors_count"] == len(tz_case.REACTORS)
    assert tz_case.EXPECTED["lines_count"] == len(tz_case.FILLING_LINES)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])