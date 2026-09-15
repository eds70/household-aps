# backend/tests/test_auth_models.py
"""
Тесты для Pydantic-моделей авторизации.
Проверяют валидацию входных данных.
"""

import pytest
from uuid import UUID
from pydantic import ValidationError
from app.auth.models import (
    LoginRequest,
    RegisterRequest,
    ChangePasswordRequest,
    TokenPayload,
)


def test_login_request_valid():
    """Тест валидного запроса на вход"""
    request = LoginRequest(
        email="admin@household.ru",
        password="admin123",
    )
    assert request.email == "admin@household.ru"
    assert request.password == "admin123"


def test_login_request_invalid_email():
    """Тест невалидного email"""
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="admin123")


def test_login_request_short_password():
    """Тест слишком короткого пароля"""
    with pytest.raises(ValidationError):
        LoginRequest(email="admin@household.ru", password="12345")


def test_register_request_valid():
    """Тест валидной регистрации"""
    request = RegisterRequest(
        email="newuser@household.ru",
        password="securepassword",
        full_name="Иванов Иван",
        role="PLANNER",
    )
    assert request.role == "PLANNER"
    assert request.full_name == "Иванов Иван"


def test_register_request_invalid_role():
    """Тест недопустимой роли"""
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(
            email="newuser@household.ru",
            password="securepassword",
            role="SUPERADMIN",  # Недопустимая роль
        )
    assert "Недопустимая роль" in str(exc_info.value)


def test_register_request_short_password():
    """Тест короткого пароля при регистрации"""
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="newuser@household.ru",
            password="short",  # Менее 8 символов
        )


def test_change_password_request_valid():
    """Тест валидной смены пароля"""
    request = ChangePasswordRequest(
        old_password="oldpassword",
        new_password="newsecurepassword",
    )
    assert request.old_password == "oldpassword"
    assert request.new_password == "newsecurepassword"


def test_change_password_numeric_only():
    """Тест пароля только из цифр"""
    with pytest.raises(ValidationError) as exc_info:
        ChangePasswordRequest(
            old_password="oldpassword",
            new_password="12345678",
        )
    assert "только из цифр" in str(exc_info.value)


def test_token_payload():
    """Тест payload JWT токена"""
    payload = TokenPayload(
        sub="user-uuid-here",
        org_id="org-uuid-here",
        role="ADMIN",
        email="admin@household.ru",
        exp=1700000000,
    )
    assert payload.sub == "user-uuid-here"
    assert payload.role == "ADMIN"
    assert payload.exp == 1700000000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])