# backend/tests/test_dependencies.py
"""
Тесты для FastAPI dependencies модуля авторизации.
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


@app.get("/test-user")
def test_user_endpoint(user: dict = Depends(get_current_user)):
    return user


@app.get("/test-org-id")
def test_org_id_endpoint(org_id: UUID = Depends(get_current_org_id)):
    return {"org_id": str(org_id)}


@app.get("/test-user-id")
def test_user_id_endpoint(user_id: UUID = Depends(get_current_user_id)):
    return {"user_id": str(user_id)}


@app.get("/test-admin")
def test_admin_endpoint(user: dict = Depends(require_admin)):
    return {"message": "Admin access granted", "user": user}


@app.get("/test-optional")
def test_optional_endpoint(user: dict = Depends(get_optional_user)):
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}


client = TestClient(app)


# ==========================================
# Тесты (синхронные, так как TestClient блокирующий)
# ==========================================

def test_get_current_user_valid_token():
    """Тест извлечения данных пользователя из валидного токена"""
    token_data = {
        "sub": "user-123",
        "org_id": "org-456",
        "role": "ADMIN",
        "email": "admin@test.com",
    }
    token = create_access_token(token_data)

    response = client.get(
        "/test-user",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-123"
    assert data["org_id"] == "org-456"
    assert data["role"] == "ADMIN"


def test_get_current_user_invalid_token():
    """Тест обработки невалидного токена"""
    response = client.get(
        "/test-user",
        headers={"Authorization": "Bearer invalid.token.string"}
    )

    assert response.status_code == 401


def test_get_current_user_no_token():
    """Тест отсутствия токена (FastAPI HTTPBearer возвращает 401)"""
    response = client.get("/test-user")

    # ✅ Исправлено: ожидаем 401, а не 403
    assert response.status_code == 401


def test_get_org_id():
    """Тест получения ID организации"""
    token_data = {
        "sub": "user-123",
        "org_id": "00000000-0000-0000-0000-000000000001",
        "role": "ADMIN",
        "email": "admin@test.com",
    }
    token = create_access_token(token_data)

    response = client.get(
        "/test-org-id",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["org_id"] == "00000000-0000-0000-0000-000000000001"


def test_require_admin_success():
    """Тест успешной проверки роли администратора"""
    token_data = {
        "sub": "user-123",
        "org_id": "org-456",
        "role": "ADMIN",
        "email": "admin@test.com",
    }
    token = create_access_token(token_data)

    response = client.get(
        "/test-admin",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted"


def test_require_admin_forbidden():
    """Тест запрета доступа для не-администратора"""
    token_data = {
        "sub": "user-123",
        "org_id": "org-456",
        "role": "VIEWER",  # Не ADMIN
        "email": "viewer@test.com",
    }
    token = create_access_token(token_data)

    response = client.get(
        "/test-admin",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "ADMIN" in response.json()["detail"]


def test_optional_user_authenticated():
    """Тест опционального пользователя с токеном"""
    token_data = {
        "sub": "user-123",
        "org_id": "org-456",
        "role": "VIEWER",
        "email": "viewer@test.com",
    }
    token = create_access_token(token_data)

    response = client.get(
        "/test-optional",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_optional_user_anonymous():
    """Тест опционального пользователя без токена"""
    response = client.get("/test-optional")

    assert response.status_code == 200
    assert response.json()["authenticated"] is False