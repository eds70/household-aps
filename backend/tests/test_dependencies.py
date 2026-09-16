# backend/tests/test_dependencies.py
"""
Тесты для FastAPI dependencies модуля авторизации.

ВАЖНО:
1. Тестовые эндпоинты называются с префиксом `_` (а не `test_`),
   чтобы pytest не принимал их за тестовые функции.
2. Поля `sub` и `org_id` в JWT должны быть валидными UUID —
   иначе `get_current_user_id` / `get_current_org_id` упадут.
"""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from uuid import UUID
from app.auth.security import create_access_token
from app.auth.dependencies import (
    get_current_user,
    get_current_org_id,
    get_current_user_id,
    require_admin,
    get_optional_user,
)

# ==========================================
# Тестовое FastAPI приложение
# ==========================================
app = FastAPI()


@app.get("/_user")
def _user_endpoint(user: dict = Depends(get_current_user)):
    return user


@app.get("/_org-id")
def _org_id_endpoint(org_id: UUID = Depends(get_current_org_id)):
    return {"org_id": str(org_id)}


@app.get("/_user-id")
def _user_id_endpoint(user_id: UUID = Depends(get_current_user_id)):
    return {"user_id": str(user_id)}


@app.get("/_admin")
def _admin_endpoint(user: dict = Depends(require_admin)):
    return {"message": "Admin access granted", "user": user}


@app.get("/_optional")
def _optional_endpoint(user: dict = Depends(get_optional_user)):
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}


client = TestClient(app)


# ==========================================
# ХЕЛПЕРЫ: валидные UUID для тестов
# ==========================================
# В проде `sub` — UUID пользователя, `org_id` — UUID организации.
# В тестах используем фиксированные валидные UUID.

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
TEST_ORG_ID = "00000000-0000-0000-0000-000000000001"


def _make_token(role: str = "ADMIN", email: str = "admin@test.com") -> str:
    """Создаёт валидный JWT с UUID-полями."""
    return create_access_token({
        "sub": TEST_USER_ID,
        "org_id": TEST_ORG_ID,
        "role": role,
        "email": email,
    })


# ==========================================
# ТЕСТЫ
# ==========================================

def test_get_current_user_valid_token():
    """Тест извлечения данных пользователя из валидного токена"""
    token = _make_token(role="ADMIN", email="admin@test.com")

    response = client.get(
        "/_user",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["org_id"] == TEST_ORG_ID
    assert data["role"] == "ADMIN"
    assert data["email"] == "admin@test.com"


def test_get_current_user_invalid_token():
    """Тест обработки невалидного токена"""
    response = client.get(
        "/_user",
        headers={"Authorization": "Bearer invalid.token.string"},
    )

    assert response.status_code == 401


def test_get_current_user_no_token():
    """Тест отсутствия токена (FastAPI HTTPBearer возвращает 401)"""
    response = client.get("/_user")

    assert response.status_code == 401


def test_get_org_id():
    """Тест получения ID организации"""
    token = _make_token()

    response = client.get(
        "/_org-id",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["org_id"] == TEST_ORG_ID


def test_get_user_id():
    """Тест получения ID пользователя"""
    token = _make_token()

    response = client.get(
        "/_user-id",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == TEST_USER_ID


def test_require_admin_success():
    """Тест успешной проверки роли администратора"""
    token = _make_token(role="ADMIN")

    response = client.get(
        "/_admin",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted"


def test_require_admin_forbidden():
    """Тест запрета доступа для не-администратора"""
    token = _make_token(role="VIEWER", email="viewer@test.com")

    response = client.get(
        "/_admin",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "ADMIN" in response.json()["detail"]


def test_optional_user_authenticated():
    """Тест опционального пользователя с токеном"""
    token = _make_token(role="VIEWER", email="viewer@test.com")

    response = client.get(
        "/_optional",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_optional_user_anonymous():
    """Тест опционального пользователя без токена"""
    response = client.get("/_optional")

    assert response.status_code == 200
    assert response.json()["authenticated"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])