# backend/app/auth/security.py
"""
Утилиты для работы с паролями и JWT токенами.

Итерация 9 (fix):
  - Убран passlib (конфликтовал с bcrypt>=4.1 и подвешивал первый вызов).
  - bcrypt.checkpw и bcrypt.hashpw вынесены в ThreadPoolExecutor,
    чтобы не блокировать event loop FastAPI.
  - Async-версии verify_password_async / get_password_hash_async
    используются в async-эндпоинтах (login, change-password).
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger("app.auth.security")


# ==========================================
# Пул потоков для bcrypt
# ==========================================
# bcrypt — CPU-интенсивный и синхронный. Если вызвать его напрямую
# в async-функции — блокируется event loop, и все остальные запросы
# ждут. Поэтому выносим в отдельный ThreadPoolExecutor.
#
# max_workers=4 — с запасом на параллельные логины.
_BCRYPT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bcrypt")


# ==========================================
# Синхронные реализации (для скриптов и тестов)
# ==========================================

def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    """Синхронная проверка пароля. Вызывается ТОЛЬКО из отдельного потока."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _get_password_hash_sync(password: str) -> str:
    """Синхронное хеширование пароля. Вызывается ТОЛЬКО из отдельного потока."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


# ==========================================
# Async-обёртки (используются в FastAPI-эндпоинтах)
# ==========================================

async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """
    Асинхронная проверка пароля.
    Не блокирует event loop — bcrypt работает в отдельном потоке.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _BCRYPT_EXECUTOR,
        _verify_password_sync,
        plain_password,
        hashed_password,
    )


async def get_password_hash_async(password: str) -> str:
    """
    Асинхронное хеширование пароля.
    Не блокирует event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _BCRYPT_EXECUTOR,
        _get_password_hash_sync,
        password,
    )


# ==========================================
# Синхронные публичные функции (для скриптов, тестов)
# ==========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Синхронная проверка пароля.
    НЕ использовать в async-эндпоинтах — блокирует event loop!
    """
    return _verify_password_sync(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Синхронное хеширование пароля.
    НЕ использовать в async-эндпоинтах — блокирует event loop!
    """
    return _get_password_hash_sync(password)


# ==========================================
# JWT
# ==========================================

def create_access_token(
        data: dict,
        expires_delta: Optional[timedelta] = None,
) -> str:
    """Создание JWT токена доступа."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


def decode_token(token: str) -> dict:
    """Декодирование и валидация JWT токена."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )