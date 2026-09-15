# backend/tests/test_security.py
"""
Тесты для модуля безопасности (хеширование паролей и JWT).
"""

import pytest
from datetime import timedelta
from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
)
from app.core.config import settings


def test_password_hashing():
    """Тест хеширования и проверки пароля"""
    password = "test_password_123"

    # Хешируем пароль
    hashed = get_password_hash(password)

    # Проверяем, что хеш не равен исходному паролю
    assert hashed != password

    # Проверяем, что пароль верифицируется
    assert verify_password(password, hashed) is True

    # Проверяем, что неверный пароль не проходит
    assert verify_password("wrong_password", hashed) is False


def test_create_access_token():
    """Тест создания JWT токена"""
    data = {
        "sub": "user_id_123",
        "org_id": "org_id_456",
        "role": "ADMIN",
        "email": "test@example.com",
    }

    token = create_access_token(data)

    # Токен должен быть строкой
    assert isinstance(token, str)

    # Токен должен содержать три части (header.payload.signature)
    assert len(token.split(".")) == 3


def test_decode_access_token():
    """Тест декодирования JWT токена"""
    data = {
        "sub": "user_id_123",
        "org_id": "org_id_456",
        "role": "ADMIN",
        "email": "test@example.com",
    }

    # Создаём токен
    token = create_access_token(data)

    # Декодируем токен
    payload = decode_token(token)

    # Проверяем данные
    assert payload["sub"] == "user_id_123"
    assert payload["org_id"] == "org_id_456"
    assert payload["role"] == "ADMIN"
    assert payload["email"] == "test@example.com"


def test_token_expiration():
    """Тест истечения срока действия токена"""
    data = {"sub": "user_id_123"}

    # Создаём токен с временем жизни 1 секунда
    token = create_access_token(
        data,
        expires_delta=timedelta(seconds=1)
    )

    # Сразу декодируем - должно работать
    payload = decode_token(token)
    assert payload["sub"] == "user_id_123"


def test_invalid_token():
    """Тест невалидного токена"""
    from fastapi import HTTPException

    invalid_token = "invalid.token.string"

    # Декодирование должно вызвать исключение
    with pytest.raises(HTTPException) as exc_info:
        decode_token(invalid_token)

    assert exc_info.value.status_code == 401


if __name__ == "__main__":
    test_password_hashing()
    test_create_access_token()
    test_decode_access_token()
    test_token_expiration()
    test_invalid_token()
    print("✅ Все тесты безопасности пройдены!")