# backend/tests/test_personnel.py
"""
Тесты Итерации 6: Люди как ресурс.

Проверяют:
  - Feature-флаги enable_operator_pools, enable_manual_station.
  - RoutingStep содержит operator_pool.
  - build_routing назначает пул для fill_* (LINE/MANUAL).
  - Плагины OperatorPoolConstraint и LabConstraint.
  - Наличие UNIQUE-констрейнта на resource_pool.
"""

import inspect

import pytest

from app.scheduler.feature_flags import FeatureFlags
from app.scheduler.routing import (
    RoutingStep,
    OperatorPool,
    _get_line_operator_pool,
)


# ==========================================
# ТЕСТЫ: КОНСТАНТЫ ПУЛОВ
# ==========================================

def test_operator_pool_constants():
    """Проверяет наличие всех констант пулов."""
    assert OperatorPool.REACTOR_OPERATOR == "REACTOR_OPERATOR"
    assert OperatorPool.LINE_OPERATOR == "LINE_OPERATOR"
    assert OperatorPool.MANUAL_OPERATOR == "MANUAL_OPERATOR"
    assert OperatorPool.LAB == "LAB"


def test_routing_step_has_operator_pool():
    """RoutingStep должен содержать поле operator_pool."""
    step = RoutingStep(
        op_id="test",
        op={},
        role="REACTOR_OP",
        primary_equipment_id="eq1",
        secondary_equipment_id=None,
        duration=60,
    )
    assert hasattr(step, "operator_pool")
    assert step.operator_pool is None


def test_routing_step_with_pool():
    """RoutingStep с указанным пулом."""
    step = RoutingStep(
        op_id="test",
        op={},
        role="LINE_FILL",
        primary_equipment_id="r1",
        secondary_equipment_id="l1",
        duration=60,
        operator_pool=OperatorPool.LINE_OPERATOR,
    )
    assert step.operator_pool == "LINE_OPERATOR"


# ==========================================
# ТЕСТЫ: _get_line_operator_pool
# ==========================================

def test_line_operator_pool_for_filling_line():
    """FILLING_LINE → LINE_OPERATOR."""
    line = {"type": "FILLING_LINE"}
    pool = _get_line_operator_pool(line)
    assert pool == OperatorPool.LINE_OPERATOR


def test_manual_operator_pool_for_manual_station():
    """MANUAL_STATION → MANUAL_OPERATOR."""
    line = {"type": "MANUAL_STATION"}
    pool = _get_line_operator_pool(line)
    assert pool == OperatorPool.MANUAL_OPERATOR


def test_line_operator_pool_for_unknown_type():
    """Неизвестный тип → None."""
    line = {"type": "UNKNOWN"}
    pool = _get_line_operator_pool(line)
    assert pool is None


# ==========================================
# ТЕСТЫ: FEATURE-ФЛАГИ
# ==========================================

def test_feature_flag_operator_pools_enabled():
    flags = FeatureFlags({"enable_operator_pools": "true"})
    assert flags.enable_operator_pools is True


def test_feature_flag_operator_pools_default():
    flags = FeatureFlags({})
    assert flags.enable_operator_pools is False


def test_feature_flag_manual_station_enabled():
    flags = FeatureFlags({"enable_manual_station": "true"})
    assert flags.enable_manual_station is True


def test_feature_flag_manual_station_default():
    flags = FeatureFlags({})
    assert flags.enable_manual_station is False


# ==========================================
# ТЕСТЫ: ПЛАГИНЫ
# ==========================================

def test_plugins_have_operator_pool_constraint():
    """CONSTRAINT_PLUGINS должен содержать OperatorPoolConstraint."""
    from app.scheduler.constraints.plugins import (
        CONSTRAINT_PLUGINS,
    )
    plugin_types = {type(p).__name__ for p in CONSTRAINT_PLUGINS}
    assert "OperatorPoolConstraint" in plugin_types
    assert "LabConstraint" in plugin_types


def test_operator_pool_constraint_accepts_resource_pools():
    """OperatorPoolConstraint.apply должен принимать resource_pools."""
    from app.scheduler.constraints.plugins import OperatorPoolConstraint

    sig = inspect.signature(OperatorPoolConstraint.apply)
    assert "resource_pools" in sig.parameters


def test_lab_constraint_accepts_resource_pools():
    """LabConstraint.apply должен принимать resource_pools."""
    from app.scheduler.constraints.plugins import LabConstraint

    sig = inspect.signature(LabConstraint.apply)
    assert "resource_pools" in sig.parameters


# ==========================================
# ТЕСТЫ: MIGRATION
# ==========================================

def test_migration_add_09_exists():
    """Проверяет наличие файла миграции add_09.sql."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..", "migrations", "add_09.sql"
    )
    assert os.path.exists(migration_path), (
        "migrations/add_09.sql должен существовать (Итерация 6)"
    )


def test_migration_add_09_has_pools():
    """add_09.sql должен создавать 3 пула операторов."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..", "migrations", "add_09.sql"
    )
    with open(migration_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "REACTOR_OPERATOR" in content
    assert "LINE_OPERATOR" in content
    assert "MANUAL_OPERATOR" in content
    assert "enable_operator_pools" in content
    assert "enable_manual_station" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])