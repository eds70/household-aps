# backend/tests/test_config.py
"""
Тесты для проверки загрузки конфигурации.
"""

import os
from app.core.config import settings


def test_settings_loaded():
    """Проверяем, что настройки загружены"""
    assert settings.DATABASE_URL is not None
    assert settings.SECRET_KEY is not None
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_allowed_origins_list():
    """Проверяем парсинг списка origins"""
    origins = settings.allowed_origins_list
    assert isinstance(origins, list)
    assert len(origins) > 0
    assert "http://localhost:5173" in origins


def test_default_org_id():
    """Проверяем, что DEFAULT_ORG_ID валидный UUID"""
    from uuid import UUID
    assert isinstance(settings.DEFAULT_ORG_ID, UUID)


if __name__ == "__main__":
    test_settings_loaded()
    test_allowed_origins_list()
    test_default_org_id()
    print("✅ Все тесты конфигурации пройдены!")