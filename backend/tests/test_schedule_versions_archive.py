# backend/tests/test_schedule_versions_archive.py
"""
Тесты архивации версий планов (Итерация 13.21).

Проверяют:
  1. Pydantic-модели (RescheduleRequest, RescheduleResponse,
     UnarchiveVersionResponse) — 4 теста.
  2. Настройку auto_archive_on_recalc — 3 теста.
  3. Структурные тесты saver.py — 7 тестов.
  4. Структурные тесты API — 7 тестов.
  5. Миграцию add_23.sql — 7 тестов.
  6. Sanity — 2 теста.

Все тесты БЫСТРЫЕ, БЕЗ БД (структурные + Pydantic).
Интеграционные тесты (с реальной БД) — отдельным файлом.
"""

import inspect
import os
from uuid import UUID, uuid4

import pytest

from app.api.v1 import schedule as schedule_module
from app.api.v1.reschedule_models import (
    RescheduleRequest,
    RescheduleResponse,
    UnarchiveVersionResponse,
)
from app.scheduler import rescheduler as rescheduler_module
from app.scheduler import saver as saver_module

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# 1. PYDANTIC-МОДЕЛИ (4 теста)
# ==========================================

def test_reschedule_request_accepts_replace_version_id():
    """RescheduleRequest принимает replace_version_id (Итерация 13.21)."""
    from_id = uuid4()
    replace_id = uuid4()

    req = RescheduleRequest(
        from_version_id=from_id,
        reason="MANUAL",
        changes={},
        replace_version_id=replace_id,
    )

    assert req.replace_version_id == replace_id
    assert req.from_version_id == from_id


def test_reschedule_request_replace_version_id_optional():
    """replace_version_id опционален (по умолчанию None)."""
    req = RescheduleRequest(
        from_version_id=uuid4(),
        reason="MANUAL",
        changes={},
    )

    assert req.replace_version_id is None


def test_reschedule_response_has_archive_fields():
    """RescheduleResponse содержит все поля архивации."""
    resp = RescheduleResponse(
        status="success",
        to_version_id=str(uuid4()),
        replace_archived=True,
        replace_blocked=False,
        replace_blocked_reason=None,
        used_by_whatif=[],
    )

    assert resp.replace_archived is True
    assert resp.replace_blocked is False
    assert resp.replace_blocked_reason is None
    assert resp.used_by_whatif == []


def test_unarchive_version_response_model():
    """UnarchiveVersionResponse корректно валидирует поля."""
    vid = uuid4()
    resp = UnarchiveVersionResponse(
        status="success",
        version_id=str(vid),
        name="Test Plan",
        is_archived=False,
        is_active=False,
        message="Разархивирована",
    )

    assert resp.status == "success"
    assert resp.version_id == str(vid)
    assert resp.is_archived is False
    assert resp.is_active is False


# ==========================================
# 2. НАСТРОЙКА auto_archive_on_recalc (3 теста)
# ==========================================

def test_auto_archive_setting_exists_in_registry():
    """Настройка auto_archive_on_recalc есть в SETTINGS_REGISTRY."""
    from app.scheduler.settings import _SETTINGS_BY_KEY

    assert "auto_archive_on_recalc" in _SETTINGS_BY_KEY
    spec = _SETTINGS_BY_KEY["auto_archive_on_recalc"]

    assert spec.value_type == "bool"
    assert spec.default is True
    assert spec.category == "planning"


def test_auto_archive_setting_not_system():
    """Настройка НЕ системная — можно менять через UI."""
    from app.scheduler.settings import _SETTINGS_BY_KEY

    spec = _SETTINGS_BY_KEY["auto_archive_on_recalc"]
    assert spec.is_system is False


def test_auto_archive_setting_validation():
    """validate_setting корректно обрабатывает значение."""
    from app.scheduler.settings import validate_setting

    assert validate_setting("auto_archive_on_recalc", True) is True
    assert validate_setting("auto_archive_on_recalc", False) is False
    assert validate_setting("auto_archive_on_recalc", "true") is True
    assert validate_setting("auto_archive_on_recalc", "false") is False
    assert validate_setting("auto_archive_on_recalc", 1) is True
    assert validate_setting("auto_archive_on_recalc", 0) is False


# ==========================================
# 3. СТРУКТУРНЫЕ ТЕСТЫ saver.py (7 тестов)
# ==========================================

def test_saver_has_archive_version_method():
    """ScheduleSaver имеет метод _archive_version."""
    assert hasattr(saver_module.ScheduleSaver, "_archive_version")
    assert callable(saver_module.ScheduleSaver._archive_version)


def test_saver_has_check_version_usage_method():
    """ScheduleSaver имеет метод _check_version_usage."""
    assert hasattr(saver_module.ScheduleSaver, "_check_version_usage")
    assert callable(saver_module.ScheduleSaver._check_version_usage)


def test_saver_archive_version_checks_whatif():
    """_archive_version проверяет whatif_scenario перед архивацией."""
    src = inspect.getsource(saver_module.ScheduleSaver._archive_version)
    assert "whatif_scenario" in src or "_check_version_usage" in src
    assert "replace_blocked" in src


def test_saver_check_usage_queries_whatif():
    """_check_version_usage делает SELECT из whatif_scenario."""
    src = inspect.getsource(saver_module.ScheduleSaver._check_version_usage)
    assert "whatif_scenario" in src
    assert "DRAFT" in src
    assert "RUNNING" in src


def test_saver_do_save_returns_archive_fields():
    """_do_save возвращает поля архивации в результате."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "replace_archived" in src
    assert "replace_blocked" in src
    assert "replace_blocked_reason" in src
    assert "used_by_whatif" in src


def test_saver_do_save_sets_is_archived_false_for_new_version():
    """_do_save создаёт новую версию с is_archived = FALSE."""
    src = inspect.getsource(saver_module.ScheduleSaver._do_save)
    assert "is_archived" in src


def test_saver_archive_sets_is_active_false():
    """_archive_version выставляет is_active = FALSE."""
    src = inspect.getsource(saver_module.ScheduleSaver._archive_version)
    assert "is_active = FALSE" in src or "is_active=FALSE" in src


# ==========================================
# 4. СТРУКТУРНЫЕ ТЕСТЫ API (7 тестов)
# ==========================================

def test_schedule_module_has_unarchive_endpoint():
    """schedule.py содержит эндпоинт unarchive_schedule_version."""
    assert hasattr(schedule_module, "unarchive_schedule_version")
    assert callable(schedule_module.unarchive_schedule_version)


def test_unarchive_endpoint_is_put():
    """Эндпоинт unarchive зарегистрирован как PUT."""
    paths = {route.path for route in schedule_module.router.routes}
    unarchive_path = "/api/v1/schedule/versions/{version_id}/unarchive"
    assert unarchive_path in paths, f"Не найден {unarchive_path}"

    route = next(
        r for r in schedule_module.router.routes
        if r.path == unarchive_path
    )
    assert "PUT" in route.methods


def test_get_versions_accepts_include_archived():
    """get_schedule_versions принимает include_archived с дефолтом False."""
    sig = inspect.signature(schedule_module.get_schedule_versions)
    assert "include_archived" in sig.parameters

    param = sig.parameters["include_archived"]
    default = param.default

    # FastAPI оборачивает default в объект Query(...).
    # У него есть атрибут .default с фактическим значением.
    if hasattr(default, "default"):
        actual_default = default.default
    else:
        actual_default = default

    assert actual_default is False, (
        f"Ожидался default=False, получено: {actual_default!r}"
    )


def test_get_versions_filters_archived():
    """get_schedule_versions фильтрует архивные при include_archived=False."""
    src = inspect.getsource(schedule_module.get_schedule_versions)
    assert "is_archived" in src
    assert "include_archived" in src


def test_get_versions_returns_is_archived():
    """get_schedule_versions возвращает is_archived в ответе."""
    src = inspect.getsource(schedule_module.get_schedule_versions)
    assert '"is_archived"' in src or "'is_archived'" in src


def test_get_versions_returns_parent_version_id():
    """get_schedule_versions возвращает parent_version_id."""
    src = inspect.getsource(schedule_module.get_schedule_versions)
    assert "parent_version_id" in src


def test_unarchive_endpoint_checks_column():
    """unarchive проверяет наличие колонки is_archived."""
    src = inspect.getsource(schedule_module.unarchive_schedule_version)
    assert "is_archived" in src
    assert "add_23.sql" in src or "add_23" in src


# ==========================================
# 5. МИГРАЦИЯ add_23.sql (7 тестов)
# ==========================================

MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_23.sql"
)


def test_migration_add_23_exists():
    """Файл миграции add_23.sql существует."""
    assert os.path.exists(MIGRATION_PATH), (
        "migrations/add_23.sql должен существовать (Итерация 13.21)"
    )


def test_migration_adds_is_archived_column():
    """Миграция добавляет колонку is_archived."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "is_archived" in content
    assert "BOOLEAN" in content
    assert "DEFAULT FALSE" in content
    assert "NOT NULL" in content


def test_migration_creates_partial_index():
    """Миграция создаёт partial-индекс idx_schedule_version_archived."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "idx_schedule_version_archived" in content
    assert "WHERE is_archived = FALSE" in content


def test_migration_inserts_setting():
    """Миграция вставляет настройку auto_archive_on_recalc."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "auto_archive_on_recalc" in content
    assert "'true'::jsonb" in content or "true" in content
    assert "'planning'" in content or "planning" in content


def test_migration_is_idempotent():
    """Миграция идемпотентна (IF NOT EXISTS, ON CONFLICT)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IF NOT EXISTS" in content
    assert "ON CONFLICT" in content


def test_migration_wrapped_in_transaction():
    """Миграция обёрнута в BEGIN/COMMIT."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "BEGIN;" in content
    assert "COMMIT;" in content


def test_migration_migrates_inactive_versions():
    """Миграция архивирует неактивные версии (одноразово)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "is_active = FALSE" in content
    assert "is_archived = TRUE" in content or "SET is_archived = TRUE" in content


# ==========================================
# 6. SANITY (2 теста)
# ==========================================

def test_rescheduler_has_replace_version_id_param():
    """Rescheduler.reschedule принимает replace_version_id."""
    sig = inspect.signature(rescheduler_module.Rescheduler.reschedule)
    assert "replace_version_id" in sig.parameters
    param = sig.parameters["replace_version_id"]
    assert param.default is None


def test_rescheduler_passes_replace_to_saver():
    """Rescheduler пробрасывает replace_version_id в saver."""
    src = inspect.getsource(rescheduler_module.Rescheduler.reschedule)
    assert "replace_version_id" in src
    assert "schedule_result[\"replace_version_id\"]" in src or \
           "schedule_result['replace_version_id']" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])