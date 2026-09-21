# backend/tests/test_whatif.py
"""
Тесты модуля whatif (Итерация 12).

Проверяют:
  1. Pydantic-модели (WhatIfScenarioCreate, WhatIfScenarioUpdate, ...).
  2. ЧтоIfRunner CRUD (без реальной БД — через mock/структурные проверки).
  3. Структуру методов _apply_*.
  4. Хелперы (_json_dumps, _read_int, _percent_change).
  5. Наличие миграции add_16.sql и полей в init_schema.sql.
  6. Наличие эндпоинтов в роутере whatif.

Тесты НЕ работают с реальной БД — проверяют структуру кода и Pydantic.

Итерация 12 (fix): run_scenario использует 2 транзакции
вместо savepoint. Обновлены 3 теста:
  - test_whatif_runner_has_build_logic_in_run (было: _build_and_save)
  - test_whatif_runner_source_uses_two_transactions (было: uses_savepoint)
  - test_whatif_runner_source_rollbacks_changes (было: raises_rollback)
"""

import inspect
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.whatif_models import (
    WHATIF_STATUS_VALUES,
    ORDER_ACTIONS,
    CALENDAR_ACTIONS,
    WhatIfScenarioCreate,
    WhatIfScenarioUpdate,
    WhatIfScenarioResponse,
    WhatIfScenarioListItem,
    WhatIfRunRequest,
    WhatIfRunResponse,
    WhatIfCompareResponse,
    WhatIfMetrics,
)
from app.scheduler.whatif import (
    WhatIfRunner,
    WhatIfRunResult,
    _RollbackSavepoint,
    _json_dumps,
    _read_int,
    _percent_change,
)


# ==========================================
# 1. ТЕСТЫ PYDANTIC-МОДЕЛЕЙ
# ==========================================

def test_whatif_status_values_constant():
    """Константа статусов содержит все 4 значения."""
    assert set(WHATIF_STATUS_VALUES) == {"DRAFT", "RUNNING", "DONE", "FAILED"}


def test_order_actions_constant():
    """Константа действий заказов."""
    assert set(ORDER_ACTIONS) == {
        "add_order", "cancel_order", "change_qty", "change_due_date",
    }


def test_calendar_actions_constant():
    """Константа действий календаря."""
    assert set(CALENDAR_ACTIONS) == {"add", "remove"}


def test_scenario_create_minimal():
    """Минимальный сценарий — только обязательные поля."""
    base_id = uuid4()
    req = WhatIfScenarioCreate(
        name="Test scenario",
        base_version_id=base_id,
    )
    assert req.name == "Test scenario"
    assert req.base_version_id == base_id
    assert req.comment is None
    assert req.changes == {}


def test_scenario_create_short_name_rejected():
    """Слишком короткое имя — ошибка."""
    with pytest.raises(ValidationError):
        WhatIfScenarioCreate(
            name="ab",
            base_version_id=uuid4(),
        )


def test_scenario_create_long_name_rejected():
    """Слишком длинное имя — ошибка."""
    with pytest.raises(ValidationError):
        WhatIfScenarioCreate(
            name="x" * 201,
            base_version_id=uuid4(),
        )


def test_scenario_create_with_changes():
    """Сценарий с полным changes."""
    base_id = uuid4()
    req = WhatIfScenarioCreate(
        name="+20% заказ",
        base_version_id=base_id,
        comment="Увеличиваем крем-мыло",
        changes={
            "orders": [
                {"action": "change_qty",
                 "order_id": str(uuid4()),
                 "new_qty": 30000}
            ],
            "shift_mode": "3x8",
            "resource_capacity": {"REACTOR_OPERATOR": 4},
        },
    )
    assert req.changes["shift_mode"] == "3x8"
    assert len(req.changes["orders"]) == 1


def test_scenario_update_all_optional():
    """Update — все поля опциональны."""
    req = WhatIfScenarioUpdate()
    assert req.name is None
    assert req.comment is None
    assert req.changes is None


def test_run_request_defaults():
    """Run request — дефолты None для override."""
    req = WhatIfRunRequest()
    assert req.horizon_hours is None
    assert req.timeout_seconds is None


def test_run_request_with_overrides():
    """Run request с override."""
    req = WhatIfRunRequest(horizon_hours=1440, timeout_seconds=900)
    assert req.horizon_hours == 1440
    assert req.timeout_seconds == 900


def test_metrics_model():
    """Метрики — все 6 полей."""
    m = WhatIfMetrics(
        makespan_minutes=12526.0,
        makespan_hours=208.77,
        total_tasks=267,
        blocked_tasks=0,
        cooling_slow_tasks=3,
        cz_incomplete_tasks=5,
    )
    assert m.total_tasks == 267
    assert m.cooling_slow_tasks == 3


def test_compare_response_minimal():
    """Сравнение — базовая модель заполнена."""
    base_metrics = WhatIfMetrics(
        makespan_minutes=12000.0,
        makespan_hours=200.0,
        total_tasks=267,
        blocked_tasks=0,
        cooling_slow_tasks=3,
        cz_incomplete_tasks=5,
    )
    resp = WhatIfCompareResponse(
        scenario_id=uuid4(),
        scenario_name="Test",
        scenario_status="DRAFT",
        base_version_id=uuid4(),
        base_metrics=base_metrics,
    )
    assert resp.result_metrics is None
    assert resp.makespan_delta_minutes is None


def test_compare_response_full():
    """Сравнение — полная модель."""
    base = WhatIfMetrics(
        makespan_minutes=12000.0,
        makespan_hours=200.0,
        total_tasks=267,
        blocked_tasks=0,
        cooling_slow_tasks=3,
        cz_incomplete_tasks=5,
    )
    result = WhatIfMetrics(
        makespan_minutes=14000.0,
        makespan_hours=233.3,
        total_tasks=280,
        blocked_tasks=1,
        cooling_slow_tasks=5,
        cz_incomplete_tasks=8,
    )
    resp = WhatIfCompareResponse(
        scenario_id=uuid4(),
        scenario_name="+20%",
        scenario_status="DONE",
        base_version_id=uuid4(),
        result_version_id=uuid4(),
        base_metrics=base,
        result_metrics=result,
        makespan_delta_minutes=2000.0,
        makespan_delta_percent=16.67,
        total_tasks_delta=13,
        blocked_tasks_delta=1,
        cooling_slow_tasks_delta=2,
        cz_incomplete_tasks_delta=3,
    )
    assert resp.makespan_delta_minutes == 2000.0
    assert resp.total_tasks_delta == 13


def test_scenario_response_with_attributes():
    """Response строится из dict — проверяем from_attributes."""
    assert WhatIfScenarioResponse.model_config.get("from_attributes") is True


def test_scenario_list_item_minimal():
    """ListItem — компактная модель."""
    item = WhatIfScenarioListItem(
        id=uuid4(),
        name="Test",
        base_version_id=uuid4(),
        status="DRAFT",
        created_at=datetime.now(timezone.utc),
    )
    assert item.status == "DRAFT"
    assert item.result_version_id is None


def test_run_response_minimal():
    """RunResponse — минимальная модель."""
    resp = WhatIfRunResponse(
        scenario_id=uuid4(),
        status="RUNNING",
        message="Расчёт запущен",
    )
    assert resp.status == "RUNNING"
    assert resp.result_version_id is None
    assert resp.compare is None


# ==========================================
# 2. ТЕСТЫ WHATIFRUNNER (структурные)
# ==========================================

def test_whatif_runner_has_crud_methods():
    """WhatIfRunner имеет все CRUD-методы."""
    methods = [
        "create_scenario",
        "get_scenario",
        "list_scenarios",
        "update_scenario",
        "delete_scenario",
        "run_scenario",
        "compare",
    ]
    for m in methods:
        assert hasattr(WhatIfRunner, m), f"Нет метода {m}"
        assert callable(getattr(WhatIfRunner, m))


def test_whatif_runner_has_apply_methods():
    """WhatIfRunner имеет все _apply_* методы."""
    methods = [
        "_apply_changes",
        "_apply_shift_mode",
        "_apply_capacity_changes",
        "_apply_order_changes",
        "_apply_add_order",
        "_apply_cancel_order",
        "_apply_change_qty",
        "_apply_change_due_date",
        "_apply_calendar_changes",
        "_apply_add_calendar_event",
        "_apply_remove_calendar_event",
    ]
    for m in methods:
        assert hasattr(WhatIfRunner, m), f"Нет метода {m}"


def test_whatif_runner_has_build_logic_in_run():
    """
    Итерация 12 (fix): логика запуска scheduler встроена в run_scenario.
    Отдельного метода _build_and_save больше нет.

    Проверяем, что внутри run_scenario вызываются ProductionScheduler
    и ScheduleSaver.
    """
    source = inspect.getsource(WhatIfRunner.run_scenario)

    assert "ProductionScheduler" in source, (
        "run_scenario должен использовать ProductionScheduler"
    )
    assert "ScheduleSaver" in source, (
        "run_scenario должен сохранять результат через ScheduleSaver"
    )


def test_whatif_runner_has_compute_metrics():
    """_compute_metrics — есть."""
    assert hasattr(WhatIfRunner, "_compute_metrics")


def test_whatif_runner_source_uses_two_transactions():
    """
    Итерация 12 (fix): run_scenario использует 2 отдельные транзакции
    вместо savepoint.

    Проверяем наличие begin(), rollback(), commit() и отсутствие begin_nested().
    """
    source = inspect.getsource(WhatIfRunner.run_scenario)

    assert "session.begin()" in source, (
        "run_scenario должен использовать session.begin() "
        "для явной транзакции"
    )
    assert "session.rollback()" in source, (
        "run_scenario должен использовать session.rollback() "
        "для отката изменений"
    )
    assert "session.commit()" in source, (
        "run_scenario должен использовать session.commit() "
        "для сохранения результата"
    )

    # Savepoint больше не используется.
    assert "begin_nested" not in source, (
        "run_scenario НЕ должен использовать begin_nested() "
        "(заменено на 2 транзакции в Итерации 12 fix)"
    )


def test_whatif_runner_source_rollbacks_changes():
    """
    Итерация 12 (fix): run_scenario делает rollback транзакции №1
    (с временными изменениями), сохраняя результат в транзакции №2.

    Проверяем наличие логирования фаз и отсутствие _RollbackSavepoint.
    """
    source = inspect.getsource(WhatIfRunner.run_scenario)

    # Должны быть явные фазы (логирование).
    has_phase = (
            "Phase 1" in source
            or "фазы 1" in source
            or "[Phase 1]" in source
    )
    assert has_phase, (
        "run_scenario должен логировать фазу 1 (изменения + scheduler)"
    )

    # _RollbackSavepoint не используется в новой архитектуре.
    assert "_RollbackSavepoint" not in source, (
        "_RollbackSavepoint больше не используется "
        "(заменён на rollback) в Итерации 12 fix"
    )


def test_whatif_runner_apply_changes_order():
    """_apply_changes применяет изменения в правильном порядке."""
    source = inspect.getsource(WhatIfRunner._apply_changes)
    # shift_mode ДО orders
    idx_shift = source.find("shift_mode")
    idx_orders = source.find("orders")
    assert idx_shift >= 0 and idx_orders >= 0
    assert idx_shift < idx_orders, (
        "shift_mode должен применяться раньше orders"
    )


def test_rollback_savepoint_exception():
    """
    _RollbackSavepoint хранит payload.

    Класс сохранён для обратной совместимости (не используется
    в новой архитектуре, но публичный символ оставлен).
    """
    payload = {"key": "value"}
    exc = _RollbackSavepoint(payload)
    assert exc.payload == payload
    assert isinstance(exc, Exception)


def test_run_result_to_dict():
    """WhatIfRunResult.to_dict() корректно сериализует."""
    from uuid import uuid4
    vid = uuid4()
    result = WhatIfRunResult(
        status="DONE",
        result_version_id=vid,
        wall_time_seconds=78.5,
        message="OK",
        metrics_base={"makespan_minutes": 12000.0},
    )
    d = result.to_dict()
    assert d["status"] == "DONE"
    assert d["result_version_id"] == str(vid)
    assert d["wall_time_seconds"] == 78.5
    assert d["metrics_base"]["makespan_minutes"] == 12000.0


def test_run_result_to_dict_with_none():
    """to_dict() с result_version_id=None."""
    result = WhatIfRunResult(status="FAILED", error_message="oops")
    d = result.to_dict()
    assert d["status"] == "FAILED"
    assert d["result_version_id"] is None
    assert d["error_message"] == "oops"


# ==========================================
# 3. ТЕСТЫ ХЕЛПЕРОВ
# ==========================================

def test_json_dumps_simple():
    """_json_dumps — простые значения."""
    assert _json_dumps({"a": 1}) == '{"a": 1}'
    assert _json_dumps("test") == '"test"'


def test_json_dumps_with_uuid():
    """_json_dumps — UUID → строка."""
    uid = uuid4()
    result = _json_dumps({"id": uid})
    assert str(uid) in result


def test_json_dumps_cyrillic():
    """_json_dumps — кириллица не экранируется."""
    result = _json_dumps({"name": "Тест"})
    assert "Тест" in result


def test_read_int_from_string():
    """_read_int из строки."""
    assert _read_int("720", 0) == 720
    assert _read_int('"720"', 0) == 720
    assert _read_int("'720'", 0) == 720


def test_read_int_from_number():
    """_read_int из числа."""
    assert _read_int(720, 0) == 720
    assert _read_int(720.5, 0) == 720


def test_read_int_invalid():
    """_read_int — невалидное значение возвращает default."""
    assert _read_int(None, 42) == 42
    assert _read_int("bad", 42) == 42


def test_percent_change():
    """_percent_change — базовая логика."""
    assert _percent_change(100, 150) == 50.0
    assert _percent_change(100, 50) == -50.0
    assert _percent_change(100, 100) == 0.0


def test_percent_change_zero_base():
    """_percent_change — base = 0."""
    assert _percent_change(0, 100) is None


# ==========================================
# 4. ТЕСТЫ МИГРАЦИИ
# ==========================================

def test_migration_add_16_exists():
    """Файл миграции add_16.sql существует."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_16.sql"
    )
    assert os.path.exists(path), "migrations/add_16.sql должен существовать"


def test_migration_add_16_has_table():
    """add_16.sql содержит CREATE TABLE whatif_scenario."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_16.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE TABLE IF NOT EXISTS whatif_scenario" in content
    assert "base_version_id" in content
    assert "result_version_id" in content
    assert "changes JSONB" in content


def test_migration_add_16_idempotent():
    """add_16.sql идемпотентна."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_16.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "IF NOT EXISTS" in content


def test_schema_init_has_whatif_table():
    """init_schema.sql содержит whatif_scenario."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "init_schema.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "whatif_scenario" in content
    assert "base_version_id" in content
    assert "changes JSONB" in content


def test_schema_init_version_3_0_0():
    """init_schema.sql содержит актуальную версию (3.0.0+)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "init_schema.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Версия может быть 3.0.0, 4.0.0, ... — проверяем наличие любой из них
    assert any(v in content for v in ["3.0.0", "v3.0.0", "4.0.0", "v4.0.0"]), (
        "init_schema.sql должен содержать актуальную версию (3.0.0+). "
        "Сейчас в схеме v4.0.0."
    )


# ==========================================
# 5. ТЕСТЫ API-РОУТЕРА
# ==========================================

def test_whatif_api_router_exists():
    """Роутер whatif создан с правильным префиксом."""
    from app.api.v1 import whatif as whatif_module
    assert whatif_module.router.prefix == "/api/v1/whatif"
    assert "What-if сценарии" in whatif_module.router.tags


def test_whatif_api_has_all_endpoints():
    """Все 4 базовых эндпоинта зарегистрированы."""
    from app.api.v1 import whatif as whatif_module
    paths = {route.path for route in whatif_module.router.routes}
    expected = {
        "/api/v1/whatif/scenarios",
        "/api/v1/whatif/scenarios/{scenario_id}",
        "/api/v1/whatif/scenarios/{scenario_id}/run",
        "/api/v1/whatif/scenarios/{scenario_id}/compare",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"


def test_whatif_api_create_is_post():
    """POST /scenarios."""
    from app.api.v1 import whatif as whatif_module
    route = next(
        r for r in whatif_module.router.routes
        if r.path == "/api/v1/whatif/scenarios"
    )
    assert "POST" in route.methods


def test_whatif_api_run_is_post():
    """POST /scenarios/{id}/run."""
    from app.api.v1 import whatif as whatif_module
    route = next(
        r for r in whatif_module.router.routes
        if r.path == "/api/v1/whatif/scenarios/{scenario_id}/run"
    )
    assert "POST" in route.methods


def test_whatif_api_checks_edit_role():
    """API проверяет роль для редактирования."""
    from app.api.v1 import whatif as whatif_module
    assert hasattr(whatif_module, "EDIT_ALLOWED_ROLES")
    assert whatif_module.EDIT_ALLOWED_ROLES == {"ADMIN", "PLANNER"}


def test_whatif_api_checks_run_role():
    """API проверяет роль для запуска."""
    from app.api.v1 import whatif as whatif_module
    assert hasattr(whatif_module, "RUN_ALLOWED_ROLES")
    assert whatif_module.RUN_ALLOWED_ROLES == {"ADMIN", "PLANNER"}


def test_whatif_api_has_build_compare_helper():
    """_build_compare_response — есть."""
    from app.api.v1 import whatif as whatif_module
    assert hasattr(whatif_module, "_build_compare_response")


def test_whatif_api_has_background_task():
    """
    Итерация 12 (async): есть фоновая функция _run_scenario_background.
    """
    from app.api.v1 import whatif as whatif_module
    assert hasattr(whatif_module, "_run_scenario_background"), (
        "API должен иметь _run_scenario_background для async-режима"
    )


# ==========================================
# 6. ТЕСТЫ ИНТЕГРАЦИИ (структурные)
# ==========================================

def test_main_includes_whatif_router():
    """main.py подключает whatif_router."""
    from app import main as main_module
    source = inspect.getsource(main_module)
    assert "whatif_router" in source
    assert "include_router(whatif_router)" in source


def test_saver_accepts_session():
    """ScheduleSaver.__init__ принимает session."""
    from app.scheduler.saver import ScheduleSaver
    sig = inspect.signature(ScheduleSaver.__init__)
    assert "session" in sig.parameters


def test_saver_has_owns_session_flag():
    """ScheduleSaver имеет _owns_session."""
    from app.scheduler.saver import ScheduleSaver
    source = inspect.getsource(ScheduleSaver.__init__)
    assert "_owns_session" in source


def test_saver_do_save_exists():
    """ScheduleSaver._do_save — есть."""
    from app.scheduler.saver import ScheduleSaver
    assert hasattr(ScheduleSaver, "_do_save")


def test_saver_do_save_has_deactivation():
    """_do_save содержит UPDATE schedule_version SET is_active = FALSE."""
    from app.scheduler.saver import ScheduleSaver
    source = inspect.getsource(ScheduleSaver._do_save)
    assert "UPDATE schedule_version" in source
    assert "SET is_active = FALSE" in source


def test_saver_do_save_conditional_commit():
    """
    _do_save делает commit только если _owns_session=True
    (для what-if — НЕ коммитит, коммитит вызывающий).
    """
    from app.scheduler.saver import ScheduleSaver
    source = inspect.getsource(ScheduleSaver._do_save)
    assert "_owns_session" in source, (
        "_do_save должен проверять _owns_session перед commit"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])