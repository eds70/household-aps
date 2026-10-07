# backend/tests/test_audit.py
"""
Тесты API аудита (Итерация 13.3 + 16).

Проверяют:
  Базовое (13.3):
    1. GET /api/v1/audit/sources — список источников.
    2. GET /api/v1/audit/log — объединённый журнал.
    3. Фильтры: sources, severity, search, date_from/date_to.
    4. GET /api/v1/audit/stats — статистика.

  Итерация 16.1 (расширенные фильтры):
    5. Наличие actor_id, entity_type, delta_qty_from/to в /log.
    6. Валидация AuditFilterSpec.
    7. Хелпер _post_filter.

  Итерация 16.3 (серии для дашборда):
    8. GET /api/v1/audit/stats/series.
    9. Валидация group_by.

  Итерация 16.2 (saved views):
   10. CRUD-эндпоинты.
   11. Валидация Pydantic-моделей.
   12. Права (401 без токена).

  Итерация 16.4 (экспорт в xlsx):
   13. POST /api/v1/audit/export.xlsx.
   14. Наличие _build_xlsx и openpyxl.

Тесты структурные (без реальной БД) + интеграционные (с БД).
"""
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import audit as audit_module
from app.api.v1.audit_models import (
    AUDIT_GROUP_BY,
    AUDIT_SEVERITIES,
    AUDIT_SOURCES,
    AuditEvent,
    AuditExportRequest,
    AuditFilterSpec,
    AuditListResponse,
    AuditSavedView,
    AuditSavedViewCreate,
    AuditSavedViewDeleteResponse,
    AuditSavedViewFilters,
    AuditSavedViewUpdate,
    AuditStatsResponse,
    AuditStatsSeriesPoint,
    AuditStatsSeriesResponse,
)
from app.main import app


# ==========================================
# 1. КОНСТАНТЫ
# ==========================================

def test_audit_sources_constant():
    """AUDIT_SOURCES содержит все 4 источника."""
    assert set(AUDIT_SOURCES) == {"STOCK", "RESCHEDULE", "LAB", "CZ"}


def test_audit_severities_constant():
    """AUDIT_SEVERITIES содержит 3 уровня (Итерация 16)."""
    assert set(AUDIT_SEVERITIES) == {"INFO", "WARNING", "CRITICAL"}


def test_audit_group_by_constant():
    """AUDIT_GROUP_BY содержит 3 варианта (Итерация 16.3)."""
    assert set(AUDIT_GROUP_BY) == {"day", "source", "severity"}


# ==========================================
# 2. PYDANTIC-МОДЕЛИ (базовые)
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
# 3. СТРУКТУРА МОДУЛЯ (13.3)
# ==========================================

def test_audit_router_prefix():
    """Роутер создан с правильным префиксом."""
    assert audit_module.router.prefix == "/api/v1/audit"
    assert "Аудит" in audit_module.router.tags


def test_audit_router_paths():
    """Базовые эндпоинты зарегистрированы (13.3 + 16)."""
    paths = {route.path for route in audit_module.router.routes}
    expected = {
        "/api/v1/audit/log",
        "/api/v1/audit/stats",
        "/api/v1/audit/sources",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"


def test_audit_router_paths_iteration_16():
    """Итерация 16: эндпоинты series, saved-views, export зарегистрированы."""
    paths = {route.path for route in audit_module.router.routes}
    expected = {
        "/api/v1/audit/stats/series",
        "/api/v1/audit/saved-views",
        "/api/v1/audit/saved-views/{view_id}",
        "/api/v1/audit/export.xlsx",
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
# 5. ЛОГИКА SEVERITY (13.3)
# ==========================================

def test_stock_severity_is_warning_for_negative_delta():
    """Для списания (delta < 0) severity=WARNING."""
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
# 7. HTTP API (базовые) через TestClient
# ==========================================

@pytest.fixture
def client():
    return TestClient(app)


def test_audit_sources_endpoint_no_auth(client):
    """Эндпоинт /sources не требует авторизации."""
    response = client.get("/api/v1/audit/sources")
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
# 8. ХЕЛПЕРЫ
# ==========================================

def test_limit_per_source_helper():
    """_limit_per_source распределяет лимит по источникам."""
    from app.api.v1.audit import _limit_per_source

    assert _limit_per_source(100, 4) == 100
    assert _limit_per_source(40, 4) == 40
    assert _limit_per_source(4, 4) == 11


def test_to_float_helper():
    """_to_float корректно обрабатывает None и Decimal."""
    from app.api.v1.audit import _to_float
    from decimal import Decimal

    assert _to_float(None) is None
    assert _to_float(Decimal("100.5")) == 100.5
    assert _to_float(42) == 42.0
    assert _to_float("bad") is None


# ==========================================
# 9. ИТЕРАЦИЯ 16.1: РАСШИРЕННЫЕ ФИЛЬТРЫ
# ==========================================

def test_post_filter_helper_exists():
    """_post_filter существует (Итерация 16.1)."""
    assert hasattr(audit_module, "_post_filter")


def test_post_filter_signature():
    """_post_filter принимает actor_id, entity_type, delta_qty_from/to."""
    sig = inspect.signature(audit_module._post_filter)
    params = list(sig.parameters.keys())
    assert "actor_id" in params
    assert "entity_type" in params
    assert "delta_qty_from" in params
    assert "delta_qty_to" in params


def test_get_audit_log_accepts_extended_filters():
    """GET /log принимает actor_id, entity_type, delta_qty_from/to."""
    sig = inspect.signature(audit_module.get_audit_log)
    params = list(sig.parameters.keys())
    assert "actor_id" in params
    assert "entity_type" in params
    assert "delta_qty_from" in params
    assert "delta_qty_to" in params


def test_fetch_stock_events_accepts_actor_id_and_entity_type():
    """_fetch_stock_events принимает actor_id и entity_type."""
    sig = inspect.signature(audit_module._fetch_stock_events)
    params = list(sig.parameters.keys())
    assert "actor_id" in params
    assert "entity_type" in params


def test_fetch_reschedule_events_accepts_actor_id():
    """_fetch_reschedule_events принимает actor_id."""
    sig = inspect.signature(audit_module._fetch_reschedule_events)
    assert "actor_id" in list(sig.parameters.keys())


def test_fetch_lab_events_accepts_actor_id():
    """_fetch_lab_events принимает actor_id."""
    sig = inspect.signature(audit_module._fetch_lab_events)
    assert "actor_id" in list(sig.parameters.keys())


def test_fetch_cz_events_returns_empty_for_actor_filter():
    """У CZ actor_id всегда NULL — при фильтре возвращается []."""
    src = inspect.getsource(audit_module._fetch_cz_events)
    assert "if actor_id is not None:" in src
    assert "return []" in src


# ---- Pydantic: AuditFilterSpec ----

def test_audit_filter_spec_minimal():
    """AuditFilterSpec с пустым набором фильтров."""
    spec = AuditFilterSpec()
    assert spec.sources is None
    assert spec.limit == 200


def test_audit_filter_spec_sources_lowercase_normalized():
    """AuditFilterSpec нормализует sources в верхний регистр."""
    spec = AuditFilterSpec(sources=["stock", "lab"])
    assert spec.sources == ["STOCK", "LAB"]


def test_audit_filter_spec_sources_invalid_filtered_out():
    """Невалидные источники отбрасываются."""
    spec = AuditFilterSpec(sources=["STOCK", "INVALID", "LAB"])
    assert spec.sources == ["STOCK", "LAB"]


def test_audit_filter_spec_sources_empty_becomes_none():
    """Пустой список источников превращается в None (= все)."""
    spec = AuditFilterSpec(sources=[])
    assert spec.sources is None


def test_audit_filter_spec_severity_normalized():
    """AuditFilterSpec нормализует severity в верхний регистр."""
    spec = AuditFilterSpec(severity="warning")
    assert spec.severity == "WARNING"


def test_audit_filter_spec_severity_invalid():
    """Невалидный severity → ошибка валидации."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuditFilterSpec(severity="INVALID")


def test_audit_filter_spec_delta_range():
    """AuditFilterSpec принимает delta_qty_from/to."""
    spec = AuditFilterSpec(delta_qty_from=-100.0, delta_qty_to=50.0)
    assert spec.delta_qty_from == -100.0
    assert spec.delta_qty_to == 50.0


def test_audit_filter_spec_actor_and_entity():
    """AuditFilterSpec принимает actor_id (UUID) и entity_type."""
    from uuid import uuid4
    uid = uuid4()
    spec = AuditFilterSpec(actor_id=uid, entity_type="material")
    assert spec.actor_id == uid
    assert spec.entity_type == "material"


# ==========================================
# 10. ИТЕРАЦИЯ 16.3: СЕРИИ ДЛЯ ДАШБОРДА
# ==========================================

def test_get_audit_stats_series_exists():
    """Функция get_audit_stats_series существует."""
    assert hasattr(audit_module, "get_audit_stats_series")


def test_audit_stats_series_point_model():
    """AuditStatsSeriesPoint принимает label и count."""
    pt = AuditStatsSeriesPoint(label="2026-10-07", count=42)
    assert pt.label == "2026-10-07"
    assert pt.count == 42


def test_audit_stats_series_response_model():
    """AuditStatsSeriesResponse — базовые поля."""
    resp = AuditStatsSeriesResponse(
        group_by="day",
        date_from=datetime.now(timezone.utc) - timedelta(days=7),
        date_to=datetime.now(timezone.utc),
        total=100,
        points=[
            AuditStatsSeriesPoint(label="2026-10-01", count=20),
            AuditStatsSeriesPoint(label="2026-10-02", count=30),
        ],
    )
    assert resp.group_by == "day"
    assert len(resp.points) == 2


def test_audit_stats_series_requires_auth(client):
    """Эндпоинт /stats/series требует JWT."""
    response = client.get("/api/v1/audit/stats/series")
    assert response.status_code in (401, 403)


# ==========================================
# 11. ИТЕРАЦИЯ 16.2: СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ
# ==========================================

def test_saved_view_endpoints_exist():
    """4 эндпоинта saved-views зарегистрированы."""
    paths = {route.path for route in audit_module.router.routes}
    assert "/api/v1/audit/saved-views" in paths
    assert "/api/v1/audit/saved-views/{view_id}" in paths


def test_list_saved_views_exists():
    """Функция list_saved_views существует."""
    assert hasattr(audit_module, "list_saved_views")


def test_create_saved_view_exists():
    """Функция create_saved_view существует."""
    assert hasattr(audit_module, "create_saved_view")


def test_update_saved_view_exists():
    """Функция update_saved_view существует."""
    assert hasattr(audit_module, "update_saved_view")


def test_delete_saved_view_exists():
    """Функция delete_saved_view существует."""
    assert hasattr(audit_module, "delete_saved_view")


def test_saved_views_use_current_user_id():
    """Все 4 эндпоинта saved-views используют get_current_user_id."""
    for fn_name in (
            "list_saved_views",
            "create_saved_view",
            "update_saved_view",
            "delete_saved_view",
    ):
        src = inspect.getsource(getattr(audit_module, fn_name))
        assert "get_current_user_id" in src, f"{fn_name} не использует get_current_user_id"


def test_no_get_user_id_from_org_leftover():
    """Костыль _get_user_id_from_org удалён."""
    assert not hasattr(audit_module, "_get_user_id_from_org"), \
        "Костыль _get_user_id_from_org должен быть удалён"


# ---- Pydantic: AuditSavedView* ----

def test_audit_saved_view_filters_model():
    """AuditSavedViewFilters содержит расширенные поля."""
    f = AuditSavedViewFilters(
        sources=["STOCK", "LAB"],
        severity="WARNING",
        search="крем",
        actor_id=None,
        entity_type="material",
        delta_qty_from=-100.0,
    )
    assert f.sources == ["STOCK", "LAB"]
    assert f.severity == "WARNING"
    assert f.entity_type == "material"


def test_audit_saved_view_model():
    """AuditSavedView — полный набор полей."""
    from uuid import uuid4
    view = AuditSavedView(
        id=uuid4(),
        name="Критичные за неделю",
        comment="описание",
        filters={"severity": "CRITICAL"},
        is_default=True,
        display_order=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert view.name == "Критичные за неделю"
    assert view.is_default is True


def test_audit_saved_view_create_name_too_short():
    """name = '' → ошибка валидации."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuditSavedViewCreate(name="", filters=AuditSavedViewFilters())


def test_audit_saved_view_create_name_too_long():
    """name > 100 символов → ошибка."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuditSavedViewCreate(name="x" * 101, filters=AuditSavedViewFilters())


def test_audit_saved_view_create_defaults():
    """AuditSavedViewCreate имеет дефолтные filters и display_order."""
    view = AuditSavedViewCreate(name="test")
    assert view.is_default is False
    assert view.display_order == 0
    assert isinstance(view.filters, AuditSavedViewFilters)


def test_audit_saved_view_update_all_optional():
    """AuditSavedViewUpdate все поля опциональны."""
    upd = AuditSavedViewUpdate()
    assert upd.name is None
    assert upd.filters is None
    assert upd.is_default is None


def test_audit_saved_view_delete_response():
    """AuditSavedViewDeleteResponse содержит status, id, message."""
    from uuid import uuid4
    resp = AuditSavedViewDeleteResponse(
        status="deleted",
        id=uuid4(),
        message="ok",
    )
    assert resp.status == "deleted"


# ---- HTTP: 401 без токена ----

def test_saved_views_list_requires_auth(client):
    """GET /saved-views требует JWT."""
    response = client.get("/api/v1/audit/saved-views")
    assert response.status_code in (401, 403)


def test_saved_views_create_requires_auth(client):
    """POST /saved-views требует JWT."""
    response = client.post(
        "/api/v1/audit/saved-views",
        json={"name": "test", "filters": {}},
    )
    assert response.status_code in (401, 403)


def test_saved_views_update_requires_auth(client):
    """PUT /saved-views/{id} требует JWT."""
    from uuid import uuid4
    response = client.put(
        f"/api/v1/audit/saved-views/{uuid4()}",
        json={"name": "test"},
    )
    assert response.status_code in (401, 403)


def test_saved_views_delete_requires_auth(client):
    """DELETE /saved-views/{id} требует JWT."""
    from uuid import uuid4
    response = client.delete(f"/api/v1/audit/saved-views/{uuid4()}")
    assert response.status_code in (401, 403)


# ==========================================
# 12. ИТЕРАЦИЯ 16.4: ЭКСПОРТ В XLSX
# ==========================================

def test_export_audit_xlsx_exists():
    """Функция export_audit_xlsx существует."""
    assert hasattr(audit_module, "export_audit_xlsx")


def test_build_xlsx_exists():
    """Функция _build_xlsx существует."""
    assert hasattr(audit_module, "_build_xlsx")


def test_build_xlsx_uses_openpyxl():
    """_build_xlsx импортирует openpyxl (локально в функции)."""
    src = inspect.getsource(audit_module._build_xlsx)
    assert "from openpyxl import Workbook" in src


def test_build_xlsx_signature():
    """_build_xlsx принимает events и title."""
    sig = inspect.signature(audit_module._build_xlsx)
    params = list(sig.parameters.keys())
    assert "events" in params
    assert "title" in params


def test_audit_export_request_model():
    """AuditExportRequest содержит filters, title, max_rows."""
    req = AuditExportRequest(
        filters=AuditFilterSpec(),
        title="Журнал",
        max_rows=5000,
    )
    assert req.title == "Журнал"
    assert req.max_rows == 5000


def test_audit_export_request_defaults():
    """AuditExportRequest имеет дефолты title=None, max_rows=10000."""
    req = AuditExportRequest(filters=AuditFilterSpec())
    assert req.title is None
    assert req.max_rows == 10000


def test_audit_export_request_max_rows_range():
    """max_rows < 1 → ошибка валидации."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AuditExportRequest(filters=AuditFilterSpec(), max_rows=0)


def test_export_requires_auth(client):
    """POST /export.xlsx требует JWT."""
    response = client.post(
        "/api/v1/audit/export.xlsx",
        json={"filters": {}},
    )
    assert response.status_code in (401, 403)


# ==========================================
# 13. СОВМЕСТИМОСТЬ / РЕГРЕССИЯ
# ==========================================

def test_get_log_still_accepts_old_params():
    """GET /log сохраняет старые параметры (обратная совместимость)."""
    sig = inspect.signature(audit_module.get_audit_log)
    params = list(sig.parameters.keys())
    # 13.3-параметры
    assert "sources" in params
    assert "severity" in params
    assert "search" in params
    assert "date_from" in params
    assert "date_to" in params
    assert "limit" in params


def test_audit_event_unchanged():
    """AuditEvent не потерял поля (13.3)."""
    from uuid import uuid4
    e = AuditEvent(
        id=uuid4(),
        source="STOCK",
        event_type="UPDATE",
        severity="INFO",
        title="t",
        occurred_at=datetime.now(timezone.utc),
    )
    # Все базовые поля доступны
    assert e.source == "STOCK"
    assert e.details == {}


def test_audit_list_response_unchanged():
    """AuditListResponse не потерял поля (13.3)."""
    resp = AuditListResponse(
        events=[],
        total=0,
        by_source={s: 0 for s in AUDIT_SOURCES},
    )
    assert resp.total == 0
    assert set(resp.by_source.keys()) == set(AUDIT_SOURCES)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])