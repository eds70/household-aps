# backend/tests/test_whatif_uses_plan_settings.py
"""
Тесты Итерации 13.14: whatif читает настройки из plan_settings.

Проверяют:
  1. Что WhatIfRunner.run_scenario() передаёт version_id=base_version_id
     в ProductionScheduler.
  2. Что whatif не читает horizon_hours/timeout_seconds из app_settings
     для самого расчёта (эти значения — только для override horizon/timeout).
  3. Что логика двух транзакций не нарушена.

Все тесты структурные — читают исходник через inspect.getsource.
БД не требуется.
"""
import inspect

import pytest

from app.scheduler import whatif as whatif_module
from app.scheduler.whatif import WhatIfRunner


# ==========================================
# 1. ПЕРЕДАЧА version_id В PRODUCTION SCHEDULER
# ==========================================

def test_run_scenario_passes_version_id_to_scheduler():
    """
    run_scenario() должен передавать version_id=base_version_id
    в ProductionScheduler.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)

    assert "ProductionScheduler(" in src, (
        "run_scenario() должен создавать ProductionScheduler"
    )
    assert "version_id=base_version_id" in src, (
        "run_scenario() должен передавать version_id=base_version_id "
        "в ProductionScheduler (Итерация 13.14)"
    )


def test_run_scenario_uses_base_version_id():
    """
    run_scenario() должен извлекать base_version_id из сценария.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "base_version_id" in src, (
        "run_scenario() должен использовать base_version_id сценария"
    )


def test_run_scenario_passes_session():
    """
    Итерация 12 (fix): run_scenario() должен передавать self.session,
    чтобы DataLoader видел незакоммиченные изменения.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "session=self.session" in src, (
        "run_scenario() должен передавать session=self.session "
        "в ProductionScheduler"
    )


# ==========================================
# 2. ЛОГИКА ДВУХ ТРАНЗАКЦИЙ
# ==========================================

def test_run_scenario_has_rollback_and_commit():
    """
    Итерация 12 (fix #2): run_scenario() использует rollback для
    транзакции №1 и commit для транзакции №2.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)

    assert "session.rollback()" in src, (
        "run_scenario() должен использовать session.rollback() "
        "для отката транзакции №1"
    )
    assert "session.commit()" in src, (
        "run_scenario() должен использовать session.commit() "
        "для сохранения результата в транзакции №2"
    )


def test_run_scenario_does_not_use_begin_nested():
    """
    Итерация 12 (fix): savepoint (begin_nested) больше не используется.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "begin_nested" not in src, (
        "run_scenario() НЕ должен использовать begin_nested() — "
        "заменено на 2 транзакции в Итерации 12 fix"
    )


def test_run_scenario_does_not_use_rollback_savepoint():
    """
    _RollbackSavepoint больше не используется в run_scenario.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "_RollbackSavepoint" not in src, (
        "_RollbackSavepoint больше не используется в run_scenario "
        "(заменён на rollback в Итерации 12 fix)"
    )


# ==========================================
# 3. МЕТРИКИ БАЗОВОГО ПЛАНА
# ==========================================

def test_run_scenario_computes_base_metrics():
    """
    run_scenario() должен вычислять metrics_base ДО отката транзакции №1.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "_compute_metrics(base_version_id)" in src, (
        "run_scenario() должен вызывать _compute_metrics(base_version_id)"
    )


def test_run_scenario_computes_result_metrics():
    """
    run_scenario() должен вычислять metrics_result ПОСЛЕ сохранения
    новой версии.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "metrics_result = await self._compute_metrics" in src, (
        "run_scenario() должен вычислять metrics_result после сохранения"
    )


# ==========================================
# 4. HORIZON/TIMEOUT — OVERRIDE ИЗ app_settings
# ==========================================

def test_run_scenario_reads_app_settings_for_override():
    """
    run_scenario() читает horizon_hours/timeout_seconds из app_settings,
    чтобы использовать как ДЕФОЛТ для параметров run (не для расчёта).

    ВАЖНО: это единственное место, где whatif обращается к app_settings.
    Сами настройки плана читает ProductionScheduler через plan_settings.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)
    assert "FROM app_settings" in src, (
        "run_scenario() должен читать horizon_hours/timeout_seconds "
        "из app_settings как дефолт для параметров расчёта"
    )


def test_run_scenario_override_only_for_horizon_and_timeout():
    """
    Единственное чтение app_settings в run_scenario — horizon_hours
    и timeout_seconds. Никаких других настроек.
    """
    src = inspect.getsource(WhatIfRunner.run_scenario)

    # Проверяем, что в SELECT упоминаются только horizon_hours и timeout_seconds
    assert "'horizon_hours'" in src or "\"horizon_hours\"" in src
    assert "'timeout_seconds'" in src or "\"timeout_seconds\"" in src

    # Проверяем отсутствие других критичных настроек из plan_settings
    # (они должны читаться ТОЛЬКО через ProductionScheduler/DataLoader)
    forbidden = [
        "shift_mode",
        "max_fill_percent",
        "cooling_degradation_factor",
        "cooling_zone_capacity",
    ]
    for key in forbidden:
        # Ищем в SQL-запросах к app_settings
        assert f"'{key}'" not in src or "FROM app_settings" not in src.split(f"'{key}'")[0], (
            f"run_scenario() не должен читать {key} из app_settings — "
            f"это настройка плана, её читает DataLoader"
        )


# ==========================================
# 5. DOCSTRING
# ==========================================

def test_module_docstring_mentions_iteration_13_14():
    """
    Модуль whatif.py должен упоминать Итерацию 13.14 в docstring.
    """
    doc = whatif_module.__doc__ or ""
    assert "13.14" in doc, (
        "Docstring модуля whatif.py должен упоминать Итерацию 13.14"
    )


def test_run_scenario_docstring_mentions_plan_settings():
    """
    Docstring run_scenario() должен упоминать plan_settings.
    """
    doc = WhatIfRunner.run_scenario.__doc__ or ""
    assert "plan_settings" in doc or "13.14" in doc, (
        "Docstring run_scenario() должен упоминать plan_settings "
        "или Итерацию 13.14"
    )


# ==========================================
# 6. SANITY: СИГНАТУРА И СТРУКТУРА
# ==========================================

def test_run_scenario_signature():
    """
    run_scenario() должна сохранить сигнатуру: scenario_id, horizon_hours,
    timeout_seconds. version_id передаётся через scenario["base_version_id"].
    """
    sig = inspect.signature(WhatIfRunner.run_scenario)
    params = set(sig.parameters.keys())

    assert "scenario_id" in params
    assert "horizon_hours" in params
    assert "timeout_seconds" in params

    # version_id НЕ должен быть отдельным параметром
    assert "version_id" not in params, (
        "version_id НЕ должен быть параметром run_scenario() — "
        "он берётся из scenario['base_version_id']"
    )


def test_whatif_runner_still_has_crud():
    """
    Sanity: все CRUD-методы WhatIfRunner на месте.
    """
    for method in (
            "create_scenario",
            "get_scenario",
            "list_scenarios",
            "update_scenario",
            "delete_scenario",
            "run_scenario",
            "compare",
    ):
        assert hasattr(WhatIfRunner, method), f"Нет метода {method}"


def test_whatif_runner_still_has_apply_methods():
    """
    Sanity: все _apply_* методы на месте.
    """
    for method in (
            "_apply_changes",
            "_apply_shift_mode",
            "_apply_capacity_changes",
            "_apply_order_changes",
            "_apply_calendar_changes",
            "_compute_metrics",
    ):
        assert hasattr(WhatIfRunner, method), f"Нет метода {method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])