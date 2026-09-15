# backend/app/core/config.py
"""
Центральная конфигурация приложения APS Production Scheduler.

Использует pydantic-settings для автоматической загрузки переменных
окружения из файла .env с валидацией типов и значениями по умолчанию.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List
from uuid import UUID


class Settings(BaseSettings):
    """
    Глобальные настройки приложения.

    Все поля автоматически загружаются из переменных окружения
    или из файла .env в корневой директории backend/.
    """

    # ==========================================
    # База данных PostgreSQL
    # ==========================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://aps:aps_secret@localhost:5432/household",
        description="Строка подключения к PostgreSQL",
    )

    # ==========================================
    # JWT авторизация
    # ==========================================
    SECRET_KEY: str = Field(
        default="your-super-secret-key-change-in-production-min-32-chars",
        description="Секретный ключ для подписи JWT токенов (минимум 32 символа)",
    )

    ALGORITHM: str = Field(
        default="HS256",
        description="Алгоритм шифрования JWT",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="Время жизни access-токена в минутах (по умолчанию 24 часа)",
    )

    # ==========================================
    # Организация по умолчанию (для демо)
    # ==========================================
    DEFAULT_ORG_ID: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001"),
        description="ID организации по умолчанию для демо-данных",
    )

    # ==========================================
    # CORS — разрешённые источники
    # ==========================================
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Список разрешённых URL фронтенда через запятую",
    )

    # ==========================================
    # Общие настройки приложения
    # ==========================================
    APP_NAME: str = Field(
        default="APS Production Scheduler",
        description="Название приложения",
    )

    APP_VERSION: str = Field(
        default="1.2.0",
        description="Версия приложения",
    )

    DEBUG: bool = Field(
        default=False,
        description="Режим отладки (включает подробные логи)",
    )

    # ==========================================
    # Валидация полей
    # ==========================================
    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key_length(cls, v: str) -> str:
        """Проверяем, что SECRET_KEY достаточно длинный для безопасности"""
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY должен содержать минимум 32 символа. "
                "Сгенерируйте случайный ключ: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        return v

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        """Проверяем, что алгоритм поддерживается библиотекой python-jose"""
        supported = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if v not in supported:
            raise ValueError(f"Неподдерживаемый алгоритм JWT. Допустимые: {supported}")
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_token_expiration(cls, v: int) -> int:
        """Проверяем, что время жизни токена положительное"""
        if v <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES должно быть положительным числом")
        return v

    # ==========================================
    # Вычисляемые свойства
    # ==========================================
    @property
    def allowed_origins_list(self) -> List[str]:
        """
        Возвращает список разрешённых origins.
        Разбивает строку ALLOWED_ORIGINS по запятым и удаляет пробелы.
        """
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Определяет, запущено ли приложение в production (не DEBUG и ключ изменён)"""
        return not self.DEBUG and "your-super-secret-key" not in self.SECRET_KEY

    # ==========================================
    # Конфигурация Pydantic Settings (V2 синтаксис)
    # ==========================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Игнорировать неизвестные переменные в .env
    )


# ==========================================
# Глобальный экземпляр настроек
# ==========================================
# Создаётся один раз при импорте модуля.
# Все компоненты приложения импортируют и используют этот экземпляр.
settings = Settings()