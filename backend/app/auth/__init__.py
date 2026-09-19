# backend/app/auth/__init__.py
"""
Пакет auth — модуль авторизации и аутентификации.
"""

from .dependencies import (
    get_current_user,
    get_current_org_id,
    get_current_user_id,
    require_admin,
    require_role,
    get_db_session,
    get_optional_user,
)
from .models import (
    LoginRequest,
    RegisterRequest,
    ChangePasswordRequest,
    TokenResponse,
    TokenPayload,
    UserResponse,
    UserListResponse,
    PasswordChangeResponse,
    RegisterResponse,
    ErrorResponse,
    AuthError,
    ForbiddenError,
)
from .security import (
    # Async (для FastAPI-эндпоинтов)
    verify_password_async,
    get_password_hash_async,
    # Синхронные (для скриптов/тестов)
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
)

__all__ = [
    # Security utilities (async)
    "verify_password_async",
    "get_password_hash_async",
    # Security utilities (sync)
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "decode_token",
    # Request models
    "LoginRequest",
    "RegisterRequest",
    "ChangePasswordRequest",
    # Response models
    "TokenResponse",
    "TokenPayload",
    "UserResponse",
    "UserListResponse",
    "PasswordChangeResponse",
    "RegisterResponse",
    # Error models
    "ErrorResponse",
    "AuthError",
    "ForbiddenError",
    # Dependencies
    "get_current_user",
    "get_current_org_id",
    "get_current_user_id",
    "require_admin",
    "require_role",
    "get_db_session",
    "get_optional_user",
]