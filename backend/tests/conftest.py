# backend/tests/conftest.py
"""
Общие фикстуры для тестов APS Scheduler.

Итерация 15.5: используется httpx.AsyncClient + ASGITransport
с override get_db_session, чтобы избежать конфликта event loop
между pytest-asyncio, asyncpg и FastAPI.
"""
# ==========================================
# ФИКС КИРИЛЛИЦЫ НА WINDOWS — ДО ВСЕХ ИМПОРТОВ
# ==========================================
import io
import os
import sys

if sys.platform == "win32":
    # Кодовая страница консоли → UTF-8
    os.system("chcp 65001 > nul")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, io.UnsupportedOperation):
            try:
                buffer = stream.buffer  # type: ignore[attr-defined]
                new_stream = io.TextIOWrapper(
                    buffer,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                )
                setattr(sys, stream_name, new_stream)
            except (AttributeError, ValueError):
                pass


# ==========================================
# ОБЫЧНЫЕ ИМПОРТЫ
# ==========================================
import socket
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.main import app
from app.auth.dependencies import get_db_session


# ==========================================
# ПРОВЕРКА ДОСТУПНОСТИ POSTGRESQL (sync!)
# ==========================================
def _db_available_sync() -> bool:
    """
    Проверяет доступность PostgreSQL через обычный TCP-сокет.

    ВАЖНО: sync-функция. Это позволяет использовать её
    как session-scoped фикстуру без конфликта с pytest-asyncio.
    """
    try:
        # DATABASE_URL вида:
        # postgresql+asyncpg://aps:aps_secret@localhost:5432/household
        url = settings.DATABASE_URL
        # Отрезаем схему и креды
        # после '@' идёт 'host:port/db'
        host_part = url.split("@", 1)[-1]
        host_port = host_part.split("/", 1)[0]
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            host, port = host_port, 5432

        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (OSError, ValueError, IndexError):
        return False


@pytest.fixture(scope="session")
def db_available() -> bool:
    """
    Session-scoped, синхронная фикстура.

    Возвращает True, если PostgreSQL доступен по TCP.
    Не поднимает event loop — не конфликтует с pytest-asyncio.
    """
    return _db_available_sync()


@pytest.fixture
def skip_if_no_db(db_available):
    """Хелпер для integration-тестов."""
    if not db_available:
        pytest.skip("PostgreSQL недоступен — пропускаем integration-тест")
    return True


# ==========================================
# СЕССИЯ К БД (для интеграционных тестов,
# которым нужен прямой доступ к БД)
# ==========================================
@pytest_asyncio.fixture
async def async_session(
        db_available,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async-сессия для тестов, которые хотят работать с БД напрямую.

    Создаёт свежий engine на каждый тест, чтобы не тащить
    привязку к закрытому event loop между тестами.
    """
    if not db_available:
        pytest.skip("PostgreSQL недоступен — пропускаем integration-тест")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with maker() as session:
        yield session

    await engine.dispose()


# ==========================================
# ASYNC CLIENT ПОВЕРХ ASGITRANSPORT
# ==========================================
@pytest_asyncio.fixture
async def async_client(
        db_available,
) -> AsyncGenerator[AsyncClient, None]:
    """
    httpx.AsyncClient поверх ASGITransport(FastAPI app).

    Ключевая идея: создаём свежий engine ЗДЕСЬ и подменяем
    get_db_session так, чтобы FastAPI использовал ТОТ ЖЕ engine,
    что и тест. Это устраняет конфликт event loop между
    pytest-asyncio, asyncpg и ASGITransport.
    """
    if not db_available:
        pytest.skip("PostgreSQL недоступен — пропускаем integration-тест")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with maker() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db_session] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
            transport=transport,
            base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()