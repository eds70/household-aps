# backend/tests/test_materials.py
"""
Тесты модуля materials (Итерация 2).

Проверяют расчёт потребности в сырье и обнаружение дефицита.

ВАЖНО (по реальным расчётам ТЗ):
  - SALT:      нужно ~4500-4675 кг, на складе 3000 кг → ДЕФИЦИТ ~1500-1675 кг
  - FRAGRANCE: нужно ~1650-1720 кг, на складе 1500 кг → ДЕФИЦИТ ~150-220 кг
  - WATER:     запас ~275 кг (~0.3% от потребности) → WARNING (малый запас)
  - ALCOHOL:   запас ~1400 кг (~4.9% от потребности) → WARNING (малый запас)
  - GLYCERIN:  запас ~120 кг (~3.1% от потребности) → WARNING (малый запас)
  - BETAINE:   запас ~100 кг (~11% от потребности) → OK (больше 10%)
  - CHLORIDE:  запас ~1000 кг (~25% от потребности) → OK

ТЗ содержит ДВА реальных дефицита (SALT и FRAGRANCE), а не один.
Это ключевой демонстрационный кейс для Advisor'а.
"""

import pytest
from tests.fixtures import tz_case
from app.scheduler.materials import (
    calculate_batch_requirements,
    analyze_materials,
)


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _make_recipes():
    """Собирает recipes в формате DataLoader'а."""
    recipes = {}
    for pf in tz_case.PF_PRODUCTS:
        recipe_items = [
            {"material_id": item["material_code"], "qty_per_base": item["qty"]}
            for item in pf["recipe"]["items"]
        ]
        recipes[pf["code"]] = {
            "base_volume_kg": pf["recipe"]["base_volume_kg"],
            "items": recipe_items,
        }
    return recipes


def _make_materials():
    return {
        m["code"]: {
            "id": m["code"],
            "code": m["code"],
            "name": m["name"],
            "unit": m["unit"],
            "category": m["category"],
        }
        for m in tz_case.MATERIALS
    }


def _make_stocks():
    return {
        m["code"]: {"qty": m["stock"], "reserved_qty": 0}
        for m in tz_case.MATERIALS
    }


def _make_batches():
    """Собирает партии из фикстуры в формате DataLoader'а."""
    batches = []
    for i, b in enumerate(tz_case.BATCHES):
        batches.append({
            "id": f"batch_{i}",
            "product_id": b["pf_code"],
            "volume_kg": b["volume_kg"],
            "assigned_equipment_id": b["reactor_code"],
        })
    return batches


def _get_requirement(analysis, material_code):
    """Возвращает MaterialRequirement для заданного кода материала."""
    return next(
        (r for r in analysis.requirements if r.material_code == material_code),
        None,
    )


# ==========================================
# ТЕСТЫ: РАСЧЁТ ПО ОДНОЙ ПАРТИИ
# ==========================================

def test_batch_requirements_cream():
    """Крем-мыло 3500 кг: рецептура ×35 от базы 100 кг."""
    batch = {"id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500}
    req = calculate_batch_requirements(batch, "PF_CREAM", _make_recipes())

    # Вода 85 × 35 = 2975
    assert req["WATER"] == pytest.approx(2975.0)
    # Соль 5 × 35 = 175
    assert req["SALT"] == pytest.approx(175.0)
    # Отдушка 2 × 35 = 70
    assert req["FRAGRANCE"] == pytest.approx(70.0)
    # Глицерин 8 × 35 = 280
    assert req["GLYCERIN"] == pytest.approx(280.0)


def test_batch_requirements_no_recipe():
    """Нет рецептуры — пустой результат."""
    batch = {"id": "b1", "product_id": "UNKNOWN", "volume_kg": 1000}
    req = calculate_batch_requirements(batch, "UNKNOWN", _make_recipes())
    assert req == {}


# ==========================================
# ТЕСТЫ: АНАЛИЗ ПО ВСЕМ ПАРТИЯМ
# ==========================================

def test_fragrance_deficit_detected():
    """
    Ключевой кейс ТЗ: дефицит отдушки.
    По реальным расчётам: нужно ~1650-1720 кг, на складе 1500 кг.
    """
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    assert analysis.has_deficit is True

    fragrance = _get_requirement(analysis, "FRAGRANCE")
    assert fragrance is not None
    assert fragrance.required_kg > 1500.0, (
        f"Отдушка должна требовать больше 1500 кг, а требуется {fragrance.required_kg}"
    )
    assert fragrance.available_qty == pytest.approx(1500.0)
    assert fragrance.deficit_kg > 0, "Отдушка должна быть в дефиците"


def test_salt_deficit_detected():
    """
    Второй дефицит ТЗ: соль экстра.
    Нужно ~4500-4675 кг, на складе 3000 кг → дефицит ~1500-1675 кг.
    """
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    salt = _get_requirement(analysis, "SALT")
    assert salt is not None
    assert salt.required_kg > 3000.0, (
        f"Соль должна требовать больше 3000 кг, а требуется {salt.required_kg}"
    )
    assert salt.available_qty == pytest.approx(3000.0)
    assert salt.deficit_kg > 1000.0, (
        f"Дефицит соли должен быть > 1000 кг, а он {salt.deficit_kg}"
    )


def test_materials_without_deficit():
    """Материалы без дефицита: BETAINE, CHLORIDE, а также вода/спирт/глицерин."""
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    for mat_code in ("BETAINE", "CHLORIDE", "WATER", "ALCOHOL", "GLYCERIN"):
        req = _get_requirement(analysis, mat_code)
        assert req is not None, f"Нет требования для {mat_code}"
        assert req.deficit_kg == 0, (
            f"{mat_code}: неожиданный дефицит {req.deficit_kg}"
        )


def test_total_deficit_includes_salt_and_fragrance():
    """Суммарный дефицит = SALT + FRAGRANCE (оба материала)."""
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    salt = _get_requirement(analysis, "SALT")
    fragrance = _get_requirement(analysis, "FRAGRANCE")

    assert salt.deficit_kg > 0
    assert fragrance.deficit_kg > 0

    expected_total = salt.deficit_kg + fragrance.deficit_kg
    assert analysis.total_deficit_kg == pytest.approx(expected_total)


def test_shortages_contain_salt_and_fragrance():
    """В shortages — SALT и FRAGRANCE (ровно два дефицита)."""
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    shortage_codes = {r.material_code for r in analysis.shortages}
    assert "SALT" in shortage_codes
    assert "FRAGRANCE" in shortage_codes


def test_requirements_sorted_by_deficit():
    """В requirements дефицитные материалы идут первыми, и SALT — первый (больший дефицит)."""
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    # Первые два — дефицитные
    first_two = {analysis.requirements[0].material_code, analysis.requirements[1].material_code}
    assert first_two == {"SALT", "FRAGRANCE"}

    # SALT первый (дефицит больше)
    assert analysis.requirements[0].material_code == "SALT"


def test_batches_affected_count():
    """Количество партий, использующих материал."""
    analysis = analyze_materials(
        batches=_make_batches(),
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )

    # Отдушка есть в крем-мыле (10 партий) и средстве (3 партии) = 13
    fragrance = _get_requirement(analysis, "FRAGRANCE")
    assert fragrance.batches_affected == 13

    # Бетаин только в средстве = 3
    betaine = _get_requirement(analysis, "BETAINE")
    assert betaine.batches_affected == 3


# ==========================================
# ТЕСТЫ: ГРАНИЧНЫЕ СЛУЧАИ
# ==========================================

def test_empty_batches():
    """Нет партий — нет требований."""
    analysis = analyze_materials(
        batches=[],
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=_make_stocks(),
    )
    assert analysis.has_deficit is False
    assert analysis.total_deficit_kg == 0.0
    assert len(analysis.shortages) == 0


def test_exact_match_no_deficit():
    """Потребность = запас → нет дефицита."""
    batches = [{"id": "b1", "product_id": "PF_CREAM", "volume_kg": 100}]
    stocks = {"FRAGRANCE": {"qty": 2, "reserved_qty": 0}}

    analysis = analyze_materials(
        batches=batches,
        recipes=_make_recipes(),
        materials=_make_materials(),
        material_stocks=stocks,
    )
    fragrance = _get_requirement(analysis, "FRAGRANCE")
    assert fragrance is not None
    assert fragrance.deficit_kg == 0
    assert fragrance.surplus_kg == pytest.approx(0.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])