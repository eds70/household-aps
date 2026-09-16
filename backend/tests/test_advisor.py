# backend/tests/test_advisor.py
"""
Тесты модуля advisor (Итерация 2).

Проверяют подсказки:
  - MATERIAL_SHORTAGE — ДВА критичных дефицита (SALT + FRAGRANCE) и
    WARNING про малый запас (< 10%): WATER, ALCOHOL
  - UNDERLOAD — неполная загрузка реактора
  - ROUTE_MISMATCH — VIA_TANK без танка

ВАЖНО: ТЗ содержит ДВА реальных дефицита сырья (соль и отдушка).
Это ключевой демонстрационный кейс Advisor'а.

Точные расчёты по ТЗ:
  - SALT:      нужно 4500 кг, есть 3000 кг → ДЕФИЦИТ 1500 кг (CRITICAL)
  - FRAGRANCE: нужно 1650 кг, есть 1500 кг → ДЕФИЦИТ  150 кг (CRITICAL)
  - WATER:     запас  3250 кг = 3.4% от потребности → WARNING
  - ALCOHOL:   запас  1400 кг = 4.9% от потребности → WARNING
  - GLYCERIN:  запас   400 кг = 11.1% от потребности → OK (> 10%)
  - BETAINE:   запас   100 кг = 11.1% от потребности → OK (> 10%)
  - CHLORIDE:  запас  1000 кг = 25% от потребности → OK
"""

import pytest
from tests.fixtures import tz_case
from app.scheduler.advisor import (
    analyze,
    check_material_shortage,
    check_underload,
    check_route_mismatch,
    TipCode,
    TipSeverity,
)
from app.scheduler.materials import analyze_materials


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _make_recipes():
    recipes = {}
    for pf in tz_case.PF_PRODUCTS:
        items = [
            {"material_id": item["material_code"], "qty_per_base": item["qty"]}
            for item in pf["recipe"]["items"]
        ]
        recipes[pf["code"]] = {
            "base_volume_kg": pf["recipe"]["base_volume_kg"],
            "items": items,
        }
    return recipes


def _make_materials():
    return {
        m["code"]: {"id": m["code"], "code": m["code"], "name": m["name"],
                    "unit": m["unit"], "category": m["category"]}
        for m in tz_case.MATERIALS
    }


def _make_stocks():
    return {
        m["code"]: {"qty": m["stock"], "reserved_qty": 0}
        for m in tz_case.MATERIALS
    }


def _make_equipment_map():
    m = {}
    for r in tz_case.REACTORS:
        m[r["code"]] = {"id": r["code"], "name": r["name"], "type": "REACTOR",
                        "volume_kg": r["volume_kg"]}
    for t in tz_case.TANKS:
        m[t["code"]] = {"id": t["code"], "name": t["name"], "type": "TANK",
                        "volume_kg": t["volume_kg"]}
    for l in tz_case.FILLING_LINES:
        m[l["code"]] = {"id": l["code"], "name": l["name"], "type": l["type"]}
    return m


def _make_products_map():
    m = {}
    for p in tz_case.PF_PRODUCTS:
        m[p["code"]] = {
            "id": p["code"], "code": p["code"], "name": p["name"],
            "type": "PF", "route_type": p["route_type"],
        }
    return m


def _make_links():
    return [
        {"from_equipment_id": f, "to_equipment_id": t, "is_direct": d}
        for (f, t, d) in tz_case.EQUIPMENT_LINKS
    ]


def _make_batches():
    return [
        {
            "id": f"batch_{i}",
            "product_id": b["pf_code"],
            "volume_kg": b["volume_kg"],
            "assigned_equipment_id": b["reactor_code"],
        }
        for i, b in enumerate(tz_case.BATCHES)
    ]


# ==========================================
# ТЕСТЫ: MATERIAL_SHORTAGE
# ==========================================

def test_material_shortage_two_critical_deficits():
    """
    По реальным расчётам ТЗ — ДВА критичных дефицита:
      - SALT (~1500 кг)
      - FRAGRANCE (~150 кг)
    """
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )
    tips = check_material_shortage(analysis)

    critical = [t for t in tips if t.severity == TipSeverity.CRITICAL]
    assert len(critical) == 2, (
        f"Ожидалось 2 CRITICAL, получено {len(critical)}: "
        f"{[t.details.get('material_code') for t in critical]}"
    )

    critical_codes = {t.details["material_code"] for t in critical}
    assert critical_codes == {"SALT", "FRAGRANCE"}


def test_material_shortage_warning_for_low_margin():
    """
    WARNING про малый запас (< 10%) для:
      - WATER (~3.4%):   96750 нужно, 100000 есть
      - ALCOHOL (~4.9%): 28600 нужно, 30000 есть

    Без WARNING:
      - GLYCERIN — запас 11.1% (> 10%)
      - BETAINE  — запас 11.1% (> 10%)
      - CHLORIDE — запас 25% (> 10%)
    """
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )
    tips = check_material_shortage(analysis)

    warnings = [t for t in tips if t.severity == TipSeverity.WARNING]
    warning_codes = {t.details.get("material_code") for t in warnings}

    # Должны быть WATER и ALCOHOL
    assert "WATER" in warning_codes
    assert "ALCOHOL" in warning_codes

    # Не должны быть в WARNING
    assert "GLYCERIN" not in warning_codes, (
        f"GLYCERIN имеет запас ~11.1% (> 10%), не должен быть WARNING. "
        f"WARNING codes: {warning_codes}"
    )
    assert "BETAINE" not in warning_codes
    assert "CHLORIDE" not in warning_codes


# ==========================================
# ТЕСТЫ: UNDERLOAD
# ==========================================

def test_underload_detected():
    """Партия 2500 кг в реакторе 5000 при строгом пороге → неполная загрузка."""
    batches = [
        {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 2500,
         "assigned_equipment_id": "REACTOR_1"},
    ]
    tips_strict = check_underload(
        batches=batches,
        equipment_map=_make_equipment_map(),
        max_fill_percent=0.70,
        threshold=0.80,
    )
    assert len(tips_strict) >= 1
    assert tips_strict[0].code == TipCode.UNDERLOAD
    assert tips_strict[0].details["batch_volume_kg"] == 2500
    assert tips_strict[0].details["equipment_name"] == "Реактор 1"


def test_underload_not_detected_for_full_load():
    """Партия 3500 кг в реакторе 5000 → 70% (максимум) → не подсказка."""
    batches = [
        {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
         "assigned_equipment_id": "REACTOR_1"},
    ]
    tips = check_underload(
        batches=batches,
        equipment_map=_make_equipment_map(),
        max_fill_percent=0.70,
        threshold=0.50,
    )
    assert len(tips) == 0


# ==========================================
# ТЕСТЫ: ROUTE_MISMATCH
# ==========================================

def test_route_mismatch_detected():
    """Крем-мыло на Р2 (VIA_TANK), но Р2 не связан с танком → INFO."""
    batches = [
        {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 7000,
         "assigned_equipment_id": "REACTOR_2"},
    ]
    tips = check_route_mismatch(
        batches=batches,
        products_map=_make_products_map(),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
    )
    assert len(tips) >= 1
    assert tips[0].code == TipCode.ROUTE_MISMATCH
    assert tips[0].details["equipment_name"] == "Реактор 2"


def test_route_mismatch_not_detected_for_reactor_with_tank():
    """Крем-мыло на Р1 (VIA_TANK), Р1 связан с танком → нет подсказки."""
    batches = [
        {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
         "assigned_equipment_id": "REACTOR_1"},
    ]
    tips = check_route_mismatch(
        batches=batches,
        products_map=_make_products_map(),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
    )
    assert len(tips) == 0


# ==========================================
# ТЕСТЫ: ГЛАВНАЯ ФУНКЦИЯ ANALYZE
# ==========================================

def test_analyze_full_result():
    """Полный анализ возвращает все типы подсказок."""
    result = analyze(
        batches=_make_batches(),
        products_map=_make_products_map(),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
        material_supplies=None,
        schedule_result=None,
        max_fill_percent=0.70,
        enable_material_constraints=True,
        enable_advisor=True,
    )

    # Должны быть: 2 CRITICAL (SALT, FRAGRANCE) + WARNING + ROUTE_MISMATCH (INFO)
    assert result.critical_count >= 2
    codes = [t.code for t in result.tips]
    assert TipCode.MATERIAL_SHORTAGE in codes
    assert TipCode.ROUTE_MISMATCH in codes


def test_analyze_disabled():
    """Если advisor выключен — пустой результат."""
    result = analyze(
        batches=_make_batches(),
        products_map=_make_products_map(),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
        enable_advisor=False,
    )
    assert len(result.tips) == 0
    assert result.critical_count == 0


def test_analyze_material_only():
    """Если material_constraints выключен — нет подсказок про сырьё."""
    result = analyze(
        batches=_make_batches(),
        products_map=_make_products_map(),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
        enable_material_constraints=False,
        enable_advisor=True,
    )
    codes = [t.code for t in result.tips]
    assert TipCode.MATERIAL_SHORTAGE not in codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])