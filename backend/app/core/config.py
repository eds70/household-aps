# backend/app/core/config.py
"""
Центральная конфигурация приложения APS Production Scheduler.

Использует pydantic-settings для автоматической загрузки переменных
окружения из файла .env с валидацией типов и значениями по умолчанию.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ==========================================
# ХЕЛПЕРЫ ДЛЯ PEM-КЛЮЧЕЙ
# ==========================================

_PEM_BEGIN_MARKERS = ("-----BEGIN PUBLIC KEY-----", "-----BEGIN RSA PUBLIC KEY-----")
_PEM_END_MARKERS = ("-----END PUBLIC KEY-----", "-----END RSA PUBLIC KEY-----")


def normalize_pem(value: str) -> str:
    """
    Приводит PEM-ключ к каноничному виду: реальные переводы строк,
    без пробелов вокруг строк, корректные BEGIN/END-маркеры.

    Принимает три формата:
      1. Многострочный с реальными \\n (как в .env в кавычках).
      2. Однострочный с литеральными \\n (частый случай при копипасте
         из Python-кода или из переменной окружения).
      3. Смешанный — где-то реальные, где-то литеральные.

    Все три приводятся к формату (1).

    Args:
        value: сырая строка из .env или из тестов.

    Returns:
        Каноничный PEM с реальными переводами строк.

    Raises:
        ValueError: если строка не похожа на PEM.
    """
    if not value or not value.strip():
        raise ValueError("PEM-ключ пустой")

    # Шаг 1: заменяем литеральные "\n" на реальные переносы.
    # Это покрывает случай "-----BEGIN...\nMIIB...\n-----END..."
    # из однострочного .env.
    text = value.replace("\\n", "\n")

    # Шаг 2: убираем пробелы и табы вокруг строк, но НЕ внутри base64.
    lines = [line.strip() for line in text.splitlines()]

    # Шаг 3: убираем пустые строки (могут появиться при копипасте).
    lines = [line for line in lines if line]

    if len(lines) < 3:
        raise ValueError(
            "PEM-ключ слишком короткий: ожидаются BEGIN, тело (base64), END."
        )

    # Шаг 4: проверяем BEGIN/END-маркеры.
    first, last = lines[0], lines[-1]
    if not any(first.startswith(m) for m in _PEM_BEGIN_MARKERS):
        raise ValueError(
            f"PEM-ключ должен начинаться с одного из: "
            f"{', '.join(_PEM_BEGIN_MARKERS)}. Получено: {first[:60]!r}"
        )
    if not any(last.startswith(m) for m in _PEM_END_MARKERS):
        raise ValueError(
            f"PEM-ключ должен заканчиваться одним из: "
            f"{', '.join(_PEM_END_MARKERS)}. Получено: {last[:60]!r}"
        )

    # Шаг 5: склеиваем. Каждая строка — отдельная.
    return "\n".join(lines) + "\n"


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
    # JWT авторизация (для пользовательских токенов)
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
        default="4.9.1",
        description="Версия приложения",
    )

    DEBUG: bool = Field(
        default=False,
        description="Режим отладки (включает подробные логи)",
    )

    # ==========================================
    # Лицензирование (Уровни 1 + 2)
    # ==========================================
    #
    # Схема:
    #   LICENSE_VERIFY      — включена ли проверка (false только для dev).
    #   LICENSE_KEY         — JWT-лицензия, выданная вендором.
    #   LICENSE_PUBLIC_KEY  — ПУБЛИЧНЫЙ ключ вендора (RS256/ES256).
    #                         Задаётся на проде. Клиент не может
    #                         подписать лицензию этим ключом.
    #   LICENSE_MASTER_SECRET — МАСТЕР-СЕКРЕТ (HS256). Задаётся
    #                         только для локальной разработки:
    #                         клиент получает тот же ключ, что и
    #                         подпись, и технически может выпустить
    #                         себе лицензию. На проде — не задавать.
    #
    # Приоритет: если задан LICENSE_PUBLIC_KEY, используется он
    # (RS256). Иначе, если задан LICENSE_MASTER_SECRET — HS256.
    # Если заданы оба — RS256 выигрывает, мастер-секрет игнорируется.

    LICENSE_KEY: Optional[str] = Field(
        default=None,
        description=(
            "JWT-ключ лицензии. Получается у вендора. "
            "Если задан и LICENSE_VERIFY=true — backend проверяет его "
            "при старте: подпись, срок, привязку к серверу. "
            "Генерируется через scripts/generate_license.py."
        ),
    )

    LICENSE_VERIFY: bool = Field(
        default=True,
        description=(
            "Проверять лицензию при старте backend. "
            "Отключать (false) только для локальной разработки или тестов."
        ),
    )

    LICENSE_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description=(
            "Публичный ключ вендора для проверки подписи (RS256/ES256). "
            "PEM-формат. Используется в продакшене. Клиент, зная этот "
            "ключ, может только ПРОВЕРИТЬ лицензию, но не подписать. "
            ""
            "Как вставить в .env:"
            "  Вариант 1 (одна строка с литеральными \\n):"
            "    LICENSE_PUBLIC_KEY=\"-----BEGIN PUBLIC KEY-----\\nMIIB...\\n-----END PUBLIC KEY-----\""
            "  Вариант 2 (многострочный, в двойных кавычках):"
            "    LICENSE_PUBLIC_KEY=\"-----BEGIN PUBLIC KEY-----"
            "    MIIB..."
            "    -----END PUBLIC KEY-----\""
            "  Валидатор normalize_pem() принимает оба и приводит"
            "  к каноничному PEM с реальными переносами."
        ),
    )

    LICENSE_MASTER_SECRET: Optional[str] = Field(
        default=None,
        description=(
            "Мастер-секрет (HS256) — тот же ключ, что использовался "
            "при генерации лицензии через scripts/generate_license.py. "
            "⚠️  В production НЕ задаётся: подпись проверяется публичным "
            "ключом (LICENSE_PUBLIC_KEY) в RS256/ES256-режиме. "
            "Задавать только для локальной разработки и тестов."
        ),
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
        supported = {
            "HS256", "HS384", "HS512",
            "RS256", "RS384", "RS512",
            "ES256", "ES384", "ES512",
        }
        if v not in supported:
            raise ValueError(f"Неподдерживаемый алгоритм JWT. Допустимые: {sorted(supported)}")
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_token_expiration(cls, v: int) -> int:
        """Проверяем, что время жизни токена положительное"""
        if v <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES должно быть положительным числом")
        return v

    @field_validator("LICENSE_KEY")
    @classmethod
    def validate_license_key_format(cls, v: Optional[str]) -> Optional[str]:
        """
        Если LICENSE_KEY задан — проверить базовый формат JWT
        (3 сегмента, разделённых точками). Полная проверка подписи
        происходит при старте приложения (см. main.py).
        """
        if v is None:
            return None

        v = v.strip()
        if not v:
            return None

        # JWT имеет формат: header.payload.signature
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError(
                "LICENSE_KEY должен быть в формате JWT (3 сегмента, "
                "разделённых точками). Проверьте, что вы скопировали "
                "ключ полностью, без обрезаний и лишних пробелов."
            )

        return v

    @field_validator("LICENSE_PUBLIC_KEY")
    @classmethod
    def validate_public_key(cls, v: Optional[str]) -> Optional[str]:
        """
        Если LICENSE_PUBLIC_KEY задан — нормализуем PEM-формат:
        заменяем литеральные '\\n' на реальные переносы, убираем
        пустые строки и пробелы вокруг строк, проверяем BEGIN/END.

        Позволяет класть ключ в .env как одной строкой с '\\n',
        так и многострочно в кавычках — результат одинаковый.
        """
        if v is None:
            return None

        v = v.strip()
        if not v:
            return None

        return normalize_pem(v)

    @field_validator("LICENSE_MASTER_SECRET")
    @classmethod
    def validate_master_secret_length(cls, v: Optional[str]) -> Optional[str]:
        """
        Если LICENSE_MASTER_SECRET задан — минимум 32 символа.
        Это HS256-секрет, короче нельзя (безопасность HMAC).
        """
        if v is None:
            return None

        v = v.strip()
        if not v:
            return None

        if len(v) < 32:
            raise ValueError(
                f"LICENSE_MASTER_SECRET слишком короткий ({len(v)} символов). "
                f"Минимум 32. Обычно это 64 hex-символа, сгенерированные "
                f"командой `init-master-key`."
            )

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

    @property
    def license_configured(self) -> bool:
        """
        Возвращает True, если LICENSE_KEY задан и LICENSE_VERIFY включён.

        Используется в main.py для условной логики:
          - если False → лицензия не проверяется, работаем в «открытом режиме»;
          - если True → лицензия обязательна, при невалидной — 403.
        """
        return self.LICENSE_VERIFY and bool(self.LICENSE_KEY)

    @property
    def license_verify_mode(self) -> Optional[str]:
        """
        Возвращает алгоритм, которым будет проверяться лицензия:
          - 'RS256' — если задан LICENSE_PUBLIC_KEY (прод);
          - 'HS256' — если задан только LICENSE_MASTER_SECRET (dev);
          - None — если ни один не задан (лицензию проверить нельзя).

        Приоритет — как в main.py: публичный ключ важнее мастер-секрета.
        """
        if self.LICENSE_PUBLIC_KEY:
            return "RS256"
        if self.LICENSE_MASTER_SECRET:
            return "HS256"
        return None

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