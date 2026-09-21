# backend/tests/conftest.py
"""
Общие фикстуры для тестов APS Scheduler.

- async_session: реальная PostgreSQL (или её отсутствие)
- skip_if_no_db: пропускает integration-тесты, если БД недоступна
"""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from app.core.config import settings


# ==========================================
# Событийный цикл (pytest-asyncio)
# ==========================================
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ==========================================
# Проверка доступности БД
# ==========================================
async def _db_available() -> bool:
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def db_available() -> bool:
    return await _db_available()


@pytest_asyncio.fixture
async def async_session(db_available) -> AsyncGenerator[AsyncSession, None]:
    """
    Сессия к тестовой БД.

    Если БД недоступна — тест будет пропущен через skip_if_no_db.
    """
    if not db_available:
        pytest.skip("PostgreSQL недоступен — пропускаем integration-тест")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    from sqlalchemy.orm import sessionmaker
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def skip_if_no_db(db_available):
    """Использовать как зависимость для integration-тестов."""
    if not db_available:
        pytest.skip("PostgreSQL недоступен — пропускаем integration-тест")
    return True