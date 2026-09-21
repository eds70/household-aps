# backend/tests/test_lab.py
"""
Тесты лабораторных блокировок (Итерация 5).

Проверяют:
  - Модели Pydantic (BlockBatchRequest, ApproveBatchRequest)
  - Логику _is_batch_blocked в планировщике
  - Обрезку routing (truncate_after_lab)
  - Feature-флаг enable_lab_blocking
"""

from datetime import timezone, timedelta

import pytest
from pydantic import ValidationError

from app.api.v1.lab_models import (
    BlockBatchRequest,
    UnblockBatchRequest,
    ApproveBatchRequest,
    RequestAnalysisRequest,
)
from app.scheduler.feature_flags import FeatureFlags
from app.scheduler.routing import (
    build_routing,
    TaskRole,
)
from tests.fixtures import tz_case

TZ = timezone(timedelta(hours=3))


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _make_equipment_map():
    m = {}
    for r in tz_case.REACTORS:
        m[r["code"]] = {
            "id": r["code"], "name": r["name"], "type": "REACTOR",
            "volume_kg": r["volume_kg"], "speed_coeff": r["speed_coeff"],
            "mixer_type": r["mixer_type"],
        }
    for t in tz_case.TANKS:
        m[t["code"]] = {
            "id": t["code"], "name": t["name"], "type": "TANK",
            "volume_kg": t["volume_kg"], "speed_coeff": t["speed_coeff"],
            "mixer_type": None,
        }
    for l in tz_case.FILLING_LINES:
        m[l["code"]] = {
            "id": l["code"], "name": l["name"], "type": l["type"],
            "volume_kg": None, "speed_coeff": None, "mixer_type": None,
        }
    m["BOILER"] = {
        "id": "BOILER", "name": "Бойлер", "type": "BOILER",
        "volume_kg": 2000, "speed_coeff": None, "mixer_type": None,
    }
    return m


def _make_links():
    return [
        {"from_equipment_id": f, "to_equipment_id": t, "is_direct": d}
        for (f, t, d) in tz_case.EQUIPMENT_LINKS
    ]


def _make_products_map():
    m = {}
    for p in tz_case.PF_PRODUCTS:
        m[p["code"]] = {
            "id": p["code"], "code": p["code"], "name": p["name"],
            "type": "PF", "route_type": p["route_type"],
            "viscosity_coeff": p["viscosity_coeff"],
        }
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


# ==========================================
# ТЕСТЫ: PYDANTIC-МОДЕЛИ
# ==========================================

def test_block_batch_request_valid():
    """Валидный запрос на блокировку."""
    req = BlockBatchRequest(
        reason="Вязкость вне нормы",
        comment="Доп. комментарий",
    )
    assert req.reason == "Вязкость вне нормы"
    assert req.comment == "Доп. комментарий"


def test_block_batch_request_short_reason():
    """Слишком короткая причина — ошибка валидации."""
    with pytest.raises(ValidationError):
        BlockBatchRequest(reason="ab")


def test_block_batch_request_empty_reason():
    """Пустая причина — ошибка валидации."""
    with pytest.raises(ValidationError):
        BlockBatchRequest(reason="")


def test_unblock_batch_request():
    """Разблокировка без обязательных полей."""
    req = UnblockBatchRequest()
    assert req.comment is None

    req2 = UnblockBatchRequest(comment="Одобрено")
    assert req2.comment == "Одобрено"


def test_approve_batch_request_passed():
    """Одобрение партии с PASSED."""
    req = ApproveBatchRequest(result="PASSED")
    assert req.result == "PASSED"


def test_approve_batch_request_failed():
    """Одобрение партии с FAILED."""
    req = ApproveBatchRequest(result="FAILED", comment="pH вне нормы")
    assert req.result == "FAILED"
    assert req.comment == "pH вне нормы"


def test_request_analysis_request():
    """Запрос анализа."""
    req = RequestAnalysisRequest(comment="Срочно")
    assert req.comment == "Срочно"


# ==========================================
# ТЕСТЫ: FEATURE-ФЛАГ
# ==========================================

def test_feature_flag_enable_lab_blocking_true():
    """Флаг включён."""
    flags = FeatureFlags({"enable_lab_blocking": "true"})
    assert flags.enable_lab_blocking is True


def test_feature_flag_enable_lab_blocking_false():
    """Флаг выключен."""
    flags = FeatureFlags({"enable_lab_blocking": "false"})
    assert flags.enable_lab_blocking is False


def test_feature_flag_enable_lab_blocking_default():
    """Флаг по умолчанию — False."""
    flags = FeatureFlags({})
    assert flags.enable_lab_blocking is False


def test_feature_flag_enable_lab_blocking_bool():
    """Флаг как bool."""
    flags = FeatureFlags({"enable_lab_blocking": True})
    assert flags.enable_lab_blocking is True


# ==========================================
# ТЕСТЫ: TRUNCATE_AFTER_LAB В ROUTING
# ==========================================

def test_routing_truncate_after_lab_cream():
    """
    Крем-мыло: truncate_after_lab=True.
    Цепочка должна обрезаться после первой операции с needs_lab=True.
    У крем-мыла lab на этапе 5 (Лабораторный анализ).

    ВАЖНО: truncate_after_lab НЕ влияет на build_routing в текущей
    реализации для заблокированных партий — планировщик их просто
    пропускает. Этот тест проверяет саму возможность обрезки для
    отображения частичного прогресса.
    """
    batch = {
        "id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
        "assigned_equipment_id": "REACTOR_1",
    }
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

    # У крем-мыла операции 1-5 идут до первого lab (lab на 5)
    # Значит, должно остаться 5 операций
    assert len(steps) == 5, f"Ожидалось 5 шагов, получено {len(steps)}"

    # Последний шаг должен быть лабораторным
    last_op = steps[-1].op
    assert last_op.get("needs_lab") is True

    # Нет TANK_TRANSFER, LINE_FILL, WASH
    roles = [s.role for s in steps]
    assert TaskRole.TANK_TRANSFER not in roles
    assert TaskRole.LINE_FILL not in roles
    assert TaskRole.WASH not in roles


def test_routing_truncate_after_lab_antiseptic():
    """
    Антисептик: truncate_after_lab=True.
    У антисептика lab на этапе 3, потом ещё раз на 6.
    Должно остаться 3 шага (1, 2, 3).
    """
    batch = {
        "id": "b1", "product_id": "PF_ANTISEPTIC", "volume_kg": 5600,
        "assigned_equipment_id": "REACTOR_3",
    }
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

    assert len(steps) == 3, f"Ожидалось 3 шага, получено {len(steps)}"
    assert steps[-1].op.get("needs_lab") is True


def test_routing_truncate_after_lab_dish():
    """
    Средство: lab на этапе 4. Должно остаться 4 шага.
    """
    batch = {
        "id": "b1", "product_id": "PF_DISH", "volume_kg": 7000,
        "assigned_equipment_id": "REACTOR_2",
    }
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

    assert len(steps) == 4, f"Ожидалось 4 шага, получено {len(steps)}"
    assert steps[-1].op.get("needs_lab") is True


def test_routing_no_truncate_full_chain_cream():
    """
    Без truncate_after_lab — полная цепочка с разбиением LINE_FILL.
    """
    batch = {
        "id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
        "assigned_equipment_id": "REACTOR_1",
    }
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=False,
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )

    # 11 операций + N частей LINE_FILL. С разбиением — минимум 12.
    assert len(steps) >= 12

    roles = [s.role for s in steps]
    assert TaskRole.TANK_TRANSFER in roles
    assert TaskRole.LINE_FILL in roles
    assert TaskRole.WASH in roles

def test_routing_via_tank_wash_parallel_to_fill():
    """
    Итерация 13.4 (fix C1): для VIA_TANK-маршрута WASH должен
    зависеть только от TANK_TRANSFER, а не от LINE_FILL.

    Это позволяет solver'у разместить WASH параллельно сливу.
    """
    batch = {
        "id": "b1", "product_id": "PF_CREAM", "volume_kg": 3500,
        "assigned_equipment_id": "REACTOR_1",
    }
    steps = build_routing(
        batch=batch,
        product=_make_products_map()["PF_CREAM"],
        reactor=_make_equipment_map()["REACTOR_1"],
        operations=_make_operations_for_pf("PF_CREAM"),
        equipment_map=_make_equipment_map(),
        equipment_links=_make_links(),
        products_map=_make_products_map(),
        calc_duration=_calc_duration,
        truncate_after_lab=False,
        gp_product=_make_gp_product("GP_CREAM_1L"),
    )

    wash = next(s for s in steps if s.role == TaskRole.WASH)
    fill_steps = [s for s in steps if s.role == TaskRole.LINE_FILL]

    # WASH не должен зависеть ни от одной fill-части
    for fill_step in fill_steps:
        assert fill_step.op_id not in wash.depends_on_op_ids, (
            f"VIA_TANK: WASH не должен зависеть от {fill_step.op_id} "
            f"(замыв может идти параллельно)"
        )

def test_routing_truncate_flags():
    """После обрезки флаги is_first/is_last установлены."""
    batch = {
        "id": "b1", "product_id": "PF_ANTISEPTIC", "volume_kg": 5600,
        "assigned_equipment_id": "REACTOR_3",
    }
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

    assert steps[0].is_first_in_batch is True
    assert steps[-1].is_last_in_batch is True


# ==========================================
# ТЕСТЫ: ЛОГИКА БЛОКИРОВКИ В ПЛАНИРОВЩИКЕ
# ==========================================

def test_is_batch_blocked_flag_disabled():
    """
    Если feature-флаг выключен, _is_batch_blocked всегда возвращает False,
    даже если у партии is_lab_blocked=True.
    """
    from app.scheduler.core import ProductionScheduler

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler.flags = FeatureFlags({"enable_lab_blocking": "false"})

    batch = {"is_lab_blocked": True}
    assert scheduler._is_batch_blocked(batch) is False


def test_is_batch_blocked_flag_enabled():
    """
    Если feature-флаг включён, возвращает реальный статус блокировки.
    """
    from app.scheduler.core import ProductionScheduler

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler.flags = FeatureFlags({"enable_lab_blocking": "true"})

    assert scheduler._is_batch_blocked({"is_lab_blocked": True}) is True
    assert scheduler._is_batch_blocked({"is_lab_blocked": False}) is False
    assert scheduler._is_batch_blocked({}) is False


def test_is_batch_blocked_no_flags():
    """
    Если flags ещё не установлены (None), возвращает False.
    """
    from app.scheduler.core import ProductionScheduler

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    scheduler.flags = None

    assert scheduler._is_batch_blocked({"is_lab_blocked": True}) is False


def test_skipped_batches_initially_empty():
    """В начале планирования список пропущенных партий пуст."""
    from app.scheduler.core import ProductionScheduler

    scheduler = ProductionScheduler(org_id=tz_case.ORG_ID)
    assert scheduler.skipped_batches == []


# ==========================================
# ТЕСТЫ: СОГЛАСОВАННОСТЬ С ФИКСТУРОЙ
# ==========================================

def test_all_pfs_have_lab_operation():
    """Каждый ПФ из ТЗ имеет хотя бы одну операцию с needs_lab=True."""
    for pf_code, ops in tz_case.OPERATIONS.items():
        lab_ops = [op for op in ops if op[6] is True]  # индекс 6 = needs_lab
        assert len(lab_ops) >= 1, (
            f"ПФ {pf_code} не имеет ни одной операции needs_lab"
        )


def test_cream_has_two_lab_operations():
    """У крем-мыла 2 лабораторных анализа."""
    cream_ops = tz_case.OPERATIONS["PF_CREAM"]
    lab_count = sum(1 for op in cream_ops if op[6] is True)
    assert lab_count == 2


def test_dish_has_two_lab_operations():
    """У средства 2 лабораторных анализа."""
    dish_ops = tz_case.OPERATIONS["PF_DISH"]
    lab_count = sum(1 for op in dish_ops if op[6] is True)
    assert lab_count == 2


def test_antiseptic_has_two_lab_operations():
    """У антисептика 2 лабораторных анализа."""
    antiseptic_ops = tz_case.OPERATIONS["PF_ANTISEPTIC"]
    lab_count = sum(1 for op in antiseptic_ops if op[6] is True)
    assert lab_count == 2

def test_lab_api_has_auto_reschedule():
    """
    Итерация 13.4 (fix C3): в lab.py должны быть
    _auto_reschedule_after_lab и _get_active_version_id.
    """
    from app.api.v1 import lab as lab_module

    assert hasattr(lab_module, "_auto_reschedule_after_lab"), \
        "lab.py должен содержать _auto_reschedule_after_lab"
    assert hasattr(lab_module, "_get_active_version_id"), \
        "lab.py должен содержать _get_active_version_id"


def test_lab_block_accepts_background_tasks():
    """block_batch должен принимать BackgroundTasks."""
    import inspect
    from app.api.v1 import lab as lab_module

    src = inspect.getsource(lab_module)
    assert "BackgroundTasks" in src
    assert "background_tasks.add_task" in src
    assert "_auto_reschedule_after_lab" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])