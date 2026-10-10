# backend/tests/test_main.py
"""
Smoke-тесты конфигурации FastAPI-приложения.

Проверяют, что app из main.py правильно собран:
  - публичные эндпоинты (/, /health, /api/v1/license/info) доступны;
  - защищённые эндпоинты без лицензии → 403;
  - OPTIONS (CORS preflight) проходит через LicenseMiddleware;
  - lifespan выполняется и заполняет app.state.instance_id.

Все тесты — без БД, работают с реальным app из main.py.

ВАЖНО: авто-use фикстура `_disable_license_verification` из conftest.py
отключает LICENSE_VERIFY для всех тестов. Поэтому здесь мы локально
включаем проверку через monkeypatch и подкладываем в app.state
нужное состояние.
"""
from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


# ==========================================
# ФИКСТУРЫ
# ==========================================

@pytest.fixture
def restore_state() -> Generator[None, None, None]:
    """
    Сохраняет/восстанавливает app.state между тестами.

    app — модульный singleton, и тесты мутируют его state
    (license_info, license_error, instance_id). После теста
    возвращаем всё как было, чтобы не влиять на другие тесты.
    """
    saved = {
        "license_info": getattr(app.state, "license_info", None),
        "license_error": getattr(app.state, "license_error", None),
        "instance_id": getattr(app.state, "instance_id", None),
    }
    yield
    for key, value in saved.items():
        setattr(app.state, key, value)


@pytest.fixture
def client_with_license_disabled(
        monkeypatch: pytest.MonkeyPatch,
        restore_state: None,
) -> Generator[TestClient, None, None]:
    """
    TestClient с выключенной проверкой лицензии.

    Используется для тестов публичных эндпоинтов, которые
    не должны зависеть от лицензии вообще.
    """
    monkeypatch.setattr(settings, "LICENSE_VERIFY", False)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_with_license_enabled_no_key(
        monkeypatch: pytest.MonkeyPatch,
        restore_state: None,
) -> Generator[TestClient, None, None]:
    """
    TestClient с включённой проверкой и без валидной лицензии.

    Используется для тестов 403 на защищённых эндпоинтах.

    ВАЖНО: TestClient(app) вызывается с `with` — это триггерит
    lifespan, который попытается загрузить лицензию. С пустым
    app.state.license_info middleware вернёт 403 на защищённое.
    """
    monkeypatch.setattr(settings, "LICENSE_VERIFY", True)
    # Пропускаем проверку ключей — сразу ставим «нет лицензии».
    # lifespan выполнится и перезапишет app.state.license_info = None,
    # что нам и нужно.
    monkeypatch.setattr(settings, "LICENSE_KEY", None)

    with TestClient(app) as client:
        yield client


# ==========================================
# 1. ПРИЛОЖЕНИЕ СОБРАНО
# ==========================================

def test_app_metadata():
    """app имеет правильные title и version."""
    assert app.title == "APS Production Scheduler"
    assert app.version == "4.9.1"


def test_lifespan_attached():
    """
    lifespan подключён к app.

    Если кто-то случайно удалит `lifespan=lifespan` из FastAPI(...),
    этот тест упадёт — защищаемся от тихой деградации (приложение
    стартует, но лицензия не загружается).
    """
    assert app.router.lifespan_context is not None


# ==========================================
# 2. ПУБЛИЧНЫЕ ЭНДПОИНТЫ
# ==========================================

def test_health_returns_ok(client_with_license_disabled):
    """GET /health → 200, корректный JSON."""
    response = client_with_license_disabled.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "4.9.1"
    assert "timestamp" in data


def test_root_returns_ok(client_with_license_disabled):
    """GET / → 200, JSON с описанием API."""
    response = client_with_license_disabled.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "APS Production Scheduler API"
    assert data["version"] == "4.9.1"
    assert data["docs"] == "/docs"


def test_openapi_schema_available(client_with_license_disabled):
    """GET /openapi.json → 200, есть paths для основных роутеров."""
    response = client_with_license_disabled.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    # Проверяем, что основные роутеры подключены
    paths = data["paths"]
    assert "/health" in paths
    assert "/api/v1/license/info" in paths


def test_license_info_public_without_license(
        client_with_license_enabled_no_key,
):
    """
    GET /api/v1/license/info доступен даже без валидной лицензии.

    Это важно: UI должен показывать статус «лицензия недействительна»
    с причиной, а не получать 403.
    """
    response = client_with_license_enabled_no_key.get("/api/v1/license/info")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] is not None


# ==========================================
# 3. ЗАЩИЩЁННЫЕ ЭНДПОИНТЫ БЕЗ ЛИЦЕНЗИИ
# ==========================================

def test_protected_endpoint_returns_403_without_license(
        client_with_license_enabled_no_key,
):
    """
    GET /api/v1/equipment без лицензии → 403 LICENSE_INVALID.

    Проверяем, что middleware действительно блокирует защищённые пути.
    """
    response = client_with_license_enabled_no_key.get("/api/v1/equipment")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_INVALID"


# ==========================================
# 4. CORS PREFLIGHT ПРОХОДИТ ЧЕРЕЗ MIDDLEWARE
# ==========================================

def test_options_preflight_passes_through_license_middleware(
        client_with_license_enabled_no_key,
):
    """
    OPTIONS /api/v1/equipment без лицензии → 200, а не 403.

    Это регрессионный тест на баг, который мы починили:
    раньше LicenseMiddleware резал preflight OPTIONS, и браузер
    показывал «CORS policy blocked» вместо честного 403.

    Теперь OPTIONS всегда пропускается.
    """
    response = client_with_license_enabled_no_key.options(
        "/api/v1/equipment",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200


def test_options_preflight_returns_cors_headers(
        client_with_license_enabled_no_key,
):
    """
    OPTIONS preflight с разрешённого origin → CORS-заголовки в ответе.

    Проверяем, что CORSMiddleware зарегистрирован ДО LicenseMiddleware
    (порядок в Starlette — обратный порядку add_middleware).
    """
    response = client_with_license_enabled_no_key.options(
        "/api/v1/equipment",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


# ==========================================
# 5. LIFESPAN ЗАПОЛНЯЕТ STATE
# ==========================================

def test_lifespan_sets_instance_id(client_with_license_disabled):
    """
    После старта lifespan заполнил app.state.instance_id.

    TestClient(app) с `with` триггерит startup-lifespan. Это
    подтверждает, что _load_license_on_startup действительно
    вызывается, а не «тихо пропускается».
    """
    assert app.state.instance_id is not None
    assert isinstance(app.state.instance_id, str)
    assert len(app.state.instance_id) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])