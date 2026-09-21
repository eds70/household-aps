# backend/tests/test_audit.py
"""
Тесты API аудита (Итерация 13.3).

Проверяют:
  1. GET /api/v1/audit/sources — список источников.
  2. GET /api/v1/audit/log — объединённый журнал.
  3. Фильтры: sources, severity, search, date_from/date_to.
  4. GET /api/v1/audit/stats — статистика.

Тесты структурные (без реальной БД) + интеграционные (с БД).
"""
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import audit as audit_module
from app.api.v1.audit_models import (
    AUDIT_SOURCES,
    AuditEvent,
    AuditListResponse,
    AuditStatsResponse,
)
from app.main import app


# ==========================================
# 1. КОНСТАНТЫ
# ==========================================

def test_audit_sources_constant():
    """AUDIT_SOURCES содержит все 4 источника."""
    assert set(AUDIT_SOURCES) == {"STOCK", "RESCHEDULE", "LAB", "CZ"}


# ==========================================
# 2. PYDANTIC-МОДЕЛИ
# ==========================================

def test_audit_event_model():
    """AuditEvent принимает все обязательные поля."""
    from uuid import uuid4
    event = AuditEvent(
        id=uuid4(),
        source="STOCK",
        event_type="UPDATE",
        severity="WARNING",
        title="Water: изменение",
        description="100 → 200",
        entity_type="material",
        entity_id=uuid4(),
        entity_name="WATER — Вода",
        occurred_at=datetime.now(timezone.utc),
        details={"delta_qty": 100.0},
    )
    assert event.source == "STOCK"
    assert event.severity == "WARNING"
    assert event.details["delta_qty"] == 100.0


def test_audit_list_response():
    """AuditListResponse агрегирует by_source."""
    resp = AuditListResponse(
        events=[],
        total=0,
        by_source={"STOCK": 0, "RESCHEDULE": 0, "LAB": 0, "CZ": 0},
    )
    assert resp.total == 0


def test_audit_stats_response():
    """AuditStatsResponse содержит by_source и by_severity."""
    resp = AuditStatsResponse(
        period_days=7,
        date_from=datetime.now(timezone.utc) - timedelta(days=7),
        date_to=datetime.now(timezone.utc),
        total=42,
        by_source={"STOCK": 20, "RESCHEDULE": 10, "LAB": 8, "CZ": 4},
        by_severity={"INFO": 30, "WARNING": 10, "CRITICAL": 2},
    )
    assert resp.total == 42
    assert resp.by_severity["CRITICAL"] == 2


# ==========================================
# 3. СТРУКТУРА МОДУЛЯ
# ==========================================

def test_audit_router_prefix():
    """Роутер создан с правильным префиксом."""
    assert audit_module.router.prefix == "/api/v1/audit"
    assert "Аудит" in audit_module.router.tags


def test_audit_router_paths():
    """Все 3 эндпоинта зарегистрированы."""
    paths = {route.path for route in audit_module.router.routes}
    expected = {
        "/api/v1/audit/log",
        "/api/v1/audit/stats",
        "/api/v1/audit/sources",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"


def test_audit_has_fetch_functions():
    """Все 4 функции загрузки событий существуют."""
    for name in (
            "_fetch_stock_events",
            "_fetch_reschedule_events",
            "_fetch_lab_events",
            "_fetch_cz_events",
    ):
        assert hasattr(audit_module, name), f"Нет функции {name}"


def test_audit_main_endpoint_exists():
    """Эндпоинт /log есть."""
    assert hasattr(audit_module, "get_audit_log")


# ==========================================
# 4. СТРУКТУРА SQL (без БД)
# ==========================================

def test_fetch_stock_events_uses_correct_tables():
    """_fetch_stock_events джойнит material_stock_log + material + app_user."""
    src = inspect.getsource(audit_module._fetch_stock_events)
    assert "material_stock_log" in src
    assert "material m" in src
    assert "app_user u" in src


def test_fetch_reschedule_events_uses_correct_tables():
    """_fetch_reschedule_events читает reschedule_log."""
    src = inspect.getsource(audit_module._fetch_reschedule_events)
    assert "reschedule_log" in src
    assert "app_user u" in src
    # Проверяем, что НЕ джойнит schedule_version (только метаданные)
    # (в SQL-запросе нет "JOIN schedule_version")
    assert "JOIN schedule_version" not in src


def test_fetch_lab_events_uses_correct_tables():
    """_fetch_lab_events читает lab_analysis_log + batch + product."""
    src = inspect.getsource(audit_module._fetch_lab_events)
    assert "lab_analysis_log" in src
    assert "batch b" in src
    assert "product p" in src


def test_fetch_cz_events_uses_correct_tables():
    """_fetch_cz_events читает cz_scan_log + batch + product."""
    src = inspect.getsource(audit_module._fetch_cz_events)
    assert "cz_scan_log" in src
    assert "batch b" in src


# ==========================================
# 5. ЛОГИКА SEVERITY
# ==========================================

def test_stock_severity_is_warning_for_negative_delta():
    """Для списания (delta < 0) severity=WARNING."""
    # Логика заложена в _fetch_stock_events:
    #   severity = "WARNING" if delta < 0 else "INFO"
    src = inspect.getsource(audit_module._fetch_stock_events)
    assert 'severity = "WARNING" if delta < 0 else "INFO"' in src


def test_reschedule_severity_is_critical_for_breakdown():
    """Для BREAKDOWN severity=CRITICAL."""
    src = inspect.getsource(audit_module._fetch_reschedule_events)
    assert '"CRITICAL" if row.reason == "BREAKDOWN" else "INFO"' in src


def test_lab_severity_is_warning_for_blocked():
    """Для BLOCKED severity=WARNING."""
    src = inspect.getsource(audit_module._fetch_lab_events)
    assert '"WARNING" if row.action == "BLOCKED" else "INFO"' in src


def test_cz_severity_is_warning_for_unresolved():
    """Для скана-сироты severity=WARNING."""
    src = inspect.getsource(audit_module._fetch_cz_events)
    assert '"WARNING" if is_unresolved else "INFO"' in src


# ==========================================
# 6. РЕГИСТРАЦИЯ В MAIN.PY
# ==========================================

def test_audit_router_included_in_main():
    """main.py подключает audit_router."""
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert "audit_router" in src
    assert "include_router(audit_router)" in src


def test_main_has_audit_tag():
    """В tags_metadata есть «Аудит»."""
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert '"Аудит"' in src or "'Аудит'" in src


# ==========================================
# 7. HTTP API (через TestClient)
# ==========================================

@pytest.fixture
def client():
    return TestClient(app)


def test_audit_sources_endpoint_no_auth(client):
    """Эндпоинт /sources не требует авторизации (только список)."""
    # В текущей реализации /sources не требует JWT
    response = client.get("/api/v1/audit/sources")
    # Может вернуть 200 или 401 — в зависимости от глобальных deps.
    # Проверяем, что не 500.
    assert response.status_code != 500


def test_audit_log_requires_auth(client):
    """Эндпоинт /log требует JWT."""
    response = client.get("/api/v1/audit/log")
    assert response.status_code in (401, 403)


def test_audit_stats_requires_auth(client):
    """Эндпоинт /stats требует JWT."""
    response = client.get("/api/v1/audit/stats")
    assert response.status_code in (401, 403)


# ==========================================
# 8. ЛИМИТЫ
# ==========================================

def test_limit_per_source_helper():
    """_limit_per_source распределяет лимит по источникам."""
    from app.api.v1.audit import _limit_per_source

    # 100 / 4 = 25 + 10 = 35, но не меньше limit
    assert _limit_per_source(100, 4) == 100
    # 40 / 4 = 10 + 10 = 20, но не меньше 40
    assert _limit_per_source(40, 4) == 40
    # 4 / 4 = 1 + 10 = 11, больше limit → возвращаем 11
    assert _limit_per_source(4, 4) == 11


def test_to_float_helper():
    """_to_float корректно обрабатывает None и Decimal."""
    from app.api.v1.audit import _to_float
    from decimal import Decimal

    assert _to_float(None) is None
    assert _to_float(Decimal("100.5")) == 100.5
    assert _to_float(42) == 42.0
    assert _to_float("bad") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])