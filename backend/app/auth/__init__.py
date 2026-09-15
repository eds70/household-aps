# backend/app/auth/__init__.py
"""
Пакет auth — модуль авторизации и аутентификации.

Содержит:
- security.py: утилиты для хеширования паролей и работы с JWT
- models.py: Pydantic-модели для запросов/ответов
- dependencies.py: FastAPI dependencies для извлечения данных из токена
"""

from .security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
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

from .dependencies import (
    get_current_user,
    get_current_org_id,
    get_current_user_id,
    require_admin,
    require_role,
    get_db_session,
    get_optional_user,
)

__all__ = [
    # Security utilities
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