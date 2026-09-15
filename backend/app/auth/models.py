# backend/app/auth/models.py
"""
Pydantic-модели для модуля авторизации.

Определяют схемы запросов и ответов для эндпоинтов:
- POST /api/v1/auth/login
- GET /api/v1/auth/me
- POST /api/v1/auth/change-password
- POST /api/v1/auth/register (опционально)
"""

from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from uuid import UUID
from typing import Optional
from datetime import datetime


# ==========================================
# ЗАПРОСЫ (Request)
# ==========================================

class LoginRequest(BaseModel):
    """
    Запрос на авторизацию пользователя.

    Пример тела запроса:
    {
        "email": "admin@household.ru",
        "password": "admin123"
    }
    """
    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["admin@household.ru"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Пароль пользователя (от 6 до 128 символов)",
    )


class RegisterRequest(BaseModel):
    """
    Запрос на регистрацию нового пользователя.
    Опциональный эндпоинт — используется только при необходимости.
    """
    email: EmailStr = Field(
        ...,
        description="Email пользователя",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Пароль (минимум 8 символов)",
    )
    full_name: Optional[str] = Field(
        default=None,
        description="Полное имя пользователя (ФИО)",
        examples=["Иванов Иван Иванович"],
    )
    role: str = Field(
        default="VIEWER",
        description="Роль пользователя",
        examples=["ADMIN", "PLANNER", "MASTER", "LAB", "VIEWER"],
    )
    organization_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001"),
        description="ID организации, к которой привязывается пользователь",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Проверяем, что роль допустима"""
        allowed_roles = {"ADMIN", "PLANNER", "MASTER", "LAB", "VIEWER"}
        if v not in allowed_roles:
            raise ValueError(
                f"Недопустимая роль. Допустимые значения: {allowed_roles}"
            )
        return v


class ChangePasswordRequest(BaseModel):
    """
    Запрос на смену пароля текущего пользователя.
    """
    old_password: str = Field(
        ...,
        min_length=6,
        description="Текущий пароль",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Новый пароль (минимум 8 символов)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Проверяем сложность нового пароля"""
        if len(v) < 8:
            raise ValueError("Пароль должен содержать минимум 8 символов")
        if v.isdigit():
            raise ValueError("Пароль не может состоять только из цифр")
        return v


# ==========================================
# ОТВЕТЫ (Response)
# ==========================================

class TokenResponse(BaseModel):
    """
    Ответ при успешной авторизации.
    Содержит JWT токен и информацию о пользователе.
    """
    access_token: str = Field(
        ...,
        description="JWT токен доступа",
    )
    token_type: str = Field(
        default="bearer",
        description="Тип токена (всегда bearer)",
    )
    user_id: UUID = Field(
        ...,
        description="ID пользователя",
    )
    organization_id: UUID = Field(
        ...,
        description="ID организации пользователя",
    )
    role: str = Field(
        ...,
        description="Роль пользователя",
    )
    full_name: Optional[str] = Field(
        default=None,
        description="Полное имя пользователя",
    )


class TokenPayload(BaseModel):
    """
    Полезная нагрузка (payload) декодированного JWT токена.
    Используется внутри приложения, не возвращается клиенту.
    """
    sub: str = Field(
        ...,
        description="ID пользователя (стандартное поле JWT 'subject')",
    )
    org_id: str = Field(
        ...,
        description="ID организации",
    )
    role: str = Field(
        ...,
        description="Роль пользователя",
    )
    email: str = Field(
        ...,
        description="Email пользователя",
    )
    exp: Optional[int] = Field(
        default=None,
        description="Время истечения токена (Unix timestamp)",
    )


class UserResponse(BaseModel):
    """
    Информация о пользователе (для эндпоинта GET /me).
    """
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    organization_id: UUID
    is_active: bool
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """
    Список пользователей (для администратора).
    """
    users: list[UserResponse]
    total: int


class PasswordChangeResponse(BaseModel):
    """
    Ответ при успешной смене пароля.
    """
    message: str = Field(
        default="Пароль успешно изменен",
    )


class RegisterResponse(BaseModel):
    """
    Ответ при успешной регистрации.
    """
    user_id: UUID
    email: str
    message: str = Field(
        default="Пользователь успешно зарегистрирован",
    )


# ==========================================
# ОШИБКИ (Error)
# ==========================================

class ErrorResponse(BaseModel):
    """
    Универсальный формат ошибки.
    """
    detail: str
    error_code: Optional[str] = None


class AuthError(BaseModel):
    """
    Ошибка авторизации (401 Unauthorized).
    """
    detail: str = "Неверные учетные данные"
    error_code: str = "AUTH_FAILED"


class ForbiddenError(BaseModel):
    """
    Ошибка доступа (403 Forbidden).
    """
    detail: str = "Недостаточно прав"
    error_code: str = "FORBIDDEN"