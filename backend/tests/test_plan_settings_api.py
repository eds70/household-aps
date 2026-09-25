# backend/tests/test_plan_settings_api.py
"""
Тесты API мастера настроек плана (Итерация 13.14).

Проверяют СТРУКТУРУ модуля и контракты эндпоинтов.
Не работают с БД — используют TestClient только для проверки
кодов ответов (401, 404, 405 и т.п.).

Примечание: FastAPI оборачивает функции-роутеры декоратором @router.get(...),
поэтому inspect.getsource(module.get_plan_settings) НЕ работает — нужно
читать исходник МОДУЛЯ через inspect.getsource(module).
"""
import inspect
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import plan_settings as ps_module
from app.main import app

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def client():
    return TestClient(app)


# ==========================================
# 1. РОУТЕР
# ==========================================

def test_router_prefix():
    """Роутер создан с правильным префиксом."""
    assert ps_module.router.prefix == "/api/v1/plan-settings"
    assert "Настройки плана" in ps_module.router.tags


def test_router_has_three_endpoints():
    """Все 3 эндпоинта зарегистрированы."""
    paths = {route.path for route in ps_module.router.routes}
    expected = {
        "/api/v1/plan-settings/version/{version_id}",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"

    methods_by_path = {}
    for route in ps_module.router.routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods)

    get_put = methods_by_path.get(
        "/api/v1/plan-settings/version/{version_id}", set()
    )
    assert "GET" in get_put, "GET /version/{id} должен быть"
    assert "PUT" in get_put, "PUT /version/{id} должен быть"

    reset_path = "/api/v1/plan-settings/version/{version_id}/reset"
    assert reset_path in methods_by_path, "POST /version/{id}/reset должен быть"
    assert "POST" in methods_by_path[reset_path]


def test_router_has_edit_roles_constant():
    """EDIT_ALLOWED_ROLES = {ADMIN, PLANNER}."""
    assert hasattr(ps_module, "EDIT_ALLOWED_ROLES")
    assert ps_module.EDIT_ALLOWED_ROLES == {"ADMIN", "PLANNER"}


# ==========================================
# 2. ФУНКЦИИ МОДУЛЯ
# ==========================================

def test_module_has_check_edit_role():
    """_check_edit_role существует и вызываема."""
    assert hasattr(ps_module, "_check_edit_role")
    assert callable(ps_module._check_edit_role)


def test_module_has_assert_version_exists():
    """_assert_version_exists существует."""
    assert hasattr(ps_module, "_assert_version_exists")


def test_check_edit_role_allows_admin():
    """_check_edit_role не бросает для ADMIN."""
    ps_module._check_edit_role({"role": "ADMIN"})


def test_check_edit_role_allows_planner():
    """_check_edit_role не бросает для PLANNER."""
    ps_module._check_edit_role({"role": "PLANNER"})


def test_check_edit_role_rejects_viewer():
    """_check_edit_role бросает 403 для VIEWER."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        ps_module._check_edit_role({"role": "VIEWER"})
    assert exc_info.value.status_code == 403


def test_check_edit_role_rejects_master():
    """MASTER не может редактировать настройки плана."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        ps_module._check_edit_role({"role": "MASTER"})


def test_check_edit_role_rejects_no_role():
    """Без роли — 403."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        ps_module._check_edit_role({})


# ==========================================
# 3. СТРУКТУРНЫЕ ПРОВЕРКИ ИСХОДНИКА
# ==========================================

def test_source_uses_plan_settings_table():
    """Модуль работает с таблицей plan_settings, а не app_settings."""
    src = inspect.getsource(ps_module)
    assert "plan_settings" in src, "Должна использоваться таблица plan_settings"
    assert "schedule_version_id" in src, "Должна быть привязка к schedule_version"


def test_source_uses_validate_setting():
    """Валидация значений — через validate_setting из settings.py."""
    src = inspect.getsource(ps_module)
    assert "validate_setting" in src, (
        "PUT должен использовать validate_setting из settings.py"
    )


def test_source_uses_upsert():
    """Массовое обновление использует ON CONFLICT DO UPDATE."""
    src = inspect.getsource(ps_module)
    assert "ON CONFLICT" in src
    assert "DO UPDATE" in src


def test_source_reset_deletes_then_inserts():
    """Reset сначала удаляет, потом копирует из app_settings."""
    src = inspect.getsource(ps_module.reset_plan_settings)
    assert "DELETE FROM plan_settings" in src
    assert "INSERT INTO plan_settings" in src
    assert "FROM app_settings" in src


def test_source_validates_system_flag():
    """Системные настройки не обновляются."""
    src = inspect.getsource(ps_module.update_plan_settings)
    assert "is_system" in src, "Должна быть проверка is_system"


def test_source_rolls_back_on_validation_error():
    """При ошибке валидации — rollback."""
    src = inspect.getsource(ps_module.update_plan_settings)
    assert "rollback" in src, "Должен быть rollback при ошибке валидации"


# ==========================================
# 4. HTTP-КОНТРАКТЫ (без авторизации)
# ==========================================

def test_get_requires_auth(client):
    """GET /version/{id} требует JWT."""
    response = client.get(
        f"/api/v1/plan-settings/version/{uuid4()}"
    )
    assert response.status_code in (401, 403)


def test_put_requires_auth(client):
    """PUT /version/{id} требует JWT."""
    response = client.put(
        f"/api/v1/plan-settings/version/{uuid4()}",
        json={"settings": {}},
    )
    assert response.status_code in (401, 403)


def test_reset_requires_auth(client):
    """POST /reset требует JWT."""
    response = client.post(
        f"/api/v1/plan-settings/version/{uuid4()}/reset"
    )
    assert response.status_code in (401, 403)


def test_get_invalid_uuid(client):
    """Невалидный UUID в URL — 422."""
    response = client.get("/api/v1/plan-settings/version/not-a-uuid")
    assert response.status_code in (401, 403, 422)


# ==========================================
# 5. РЕГИСТРАЦИЯ В MAIN
# ==========================================

def test_main_includes_plan_settings_router():
    """main.py подключает plan_settings_router."""
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert "plan_settings_router" in src
    assert "include_router(plan_settings_router)" in src


def test_main_has_plan_settings_tag():
    """В tags_metadata есть "Настройки плана"."""
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert '"Настройки плана"' in src or "'Настройки плана'" in src


# ==========================================
# 6. SANITY: РОЛЬ ЛОГИКИ
# ==========================================

def test_edit_roles_dont_include_master_or_lab():
    """MASTER/LAB/VIEWER не могут править настройки плана."""
    for role in ("MASTER", "LAB", "VIEWER"):
        assert role not in ps_module.EDIT_ALLOWED_ROLES, (
            f"{role} не должен иметь права на редактирование"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])