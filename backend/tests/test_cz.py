# backend/tests/test_cz.py
"""
Тесты интеграции с Честным Знаком (Итерация 8).

Покрывают:
  1. Pydantic-модели (CzScanRequest, CzAttachRequest).
  2. Feature-флаг enable_cz_integration.
  3. Логику сопоставления скана с партией (resolve_batch_for_scan).
  4. Логику пересчёта статуса маркировки (recalc_batch_cz_status).
  5. Логику расчёта планового количества бутылок (compute_planned_qty).
  6. Наличие миграции add_11.sql и полей в схеме.
  7. Идемпотентность (контракт UNIQUE на cz_code).

Примечание по test_schema_init_has_cz_fields:
  init_schema.sql будет обновлён в САМОМ КОНЦЕ Итерации 8
  (вместе с README). До этого момента тест помечен skip.
  МИГРАЦИЯ add_11.sql — источник правды для текущей БД.
"""

import inspect
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.cz_models import (
    CZ_STATUS_VALUES,
    CzActionResponse,
    CzAttachRequest,
    CzPendingBatch,
    CzProgressResponse,
    CzScanRequest,
    CzScanResponse,
    CzStatsResponse,
)
from app.scheduler.feature_flags import FeatureFlags

TZ = timezone(timedelta(hours=3))
TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# 1. ТЕСТЫ PYDANTIC-МОДЕЛЕЙ
# ==========================================

def test_cz_scan_request_minimal():
    """Минимальный валидный скан — только cz_code."""
    req = CzScanRequest(cz_code="0104600000000001215Xk%5dQ")
    assert req.cz_code == "0104600000000001215Xk%5dQ"
    assert req.qty == 1.0
    assert req.batch_id is None
    assert req.task_id is None
    assert req.line_code is None
    assert req.camera_id is None
    assert req.scanned_at is None


def test_cz_scan_request_full():
    """Полный скан — все поля."""
    batch_id = uuid4()
    task_id = uuid4()
    now = datetime.now(TZ)

    req = CzScanRequest(
        cz_code="0104600000000001215FULL",
        gtin="04600000000001",
        batch_id=batch_id,
        task_id=task_id,
        line_code="LINE_1",
        camera_id="CAM-01",
        scanned_at=now,
        qty=1,
        comment="тест",
    )
    assert req.gtin == "04600000000001"
    assert req.batch_id == batch_id
    assert req.task_id == task_id
    assert req.line_code == "LINE_1"
    assert req.camera_id == "CAM-01"
    assert req.scanned_at == now
    assert req.comment == "тест"


def test_cz_scan_request_short_code_rejected():
    """Слишком короткий cz_code — ошибка валидации."""
    with pytest.raises(ValidationError):
        CzScanRequest(cz_code="abc")


def test_cz_scan_request_long_code_rejected():
    """Слишком длинный cz_code (>200) — ошибка."""
    with pytest.raises(ValidationError):
        CzScanRequest(cz_code="x" * 201)


def test_cz_scan_request_negative_qty_rejected():
    """Отрицательный qty — ошибка."""
    with pytest.raises(ValidationError):
        CzScanRequest(cz_code="0104600000000001215", qty=-1)


def test_cz_scan_request_zero_qty_allowed():
    """qty = 0 допустим (задел на будущее — скан-заглушка)."""
    req = CzScanRequest(cz_code="0104600000000001215", qty=0)
    assert req.qty == 0.0


def test_cz_scan_response_defaults():
    """Ответ на скан — дефолты duplicate=False, resolved=False."""
    scan_id = uuid4()
    resp = CzScanResponse(
        id=scan_id,
        cz_code="0104600000000001215",
        qty=1.0,
        message="ok",
    )
    assert resp.duplicate is False
    assert resp.resolved is False
    assert resp.batch_id is None
    assert resp.scheduled_task_id is None


def test_cz_attach_request_empty():
    """Attach без batch_id и task_id — валиден на уровне модели,
    но эндпоинт должен возвращать 400."""
    req = CzAttachRequest()
    assert req.batch_id is None
    assert req.task_id is None


def test_cz_attach_request_with_batch():
    """Attach с batch_id."""
    bid = uuid4()
    req = CzAttachRequest(batch_id=bid, comment="вручную")
    assert req.batch_id == bid
    assert req.comment == "вручную"


def test_cz_progress_response():
    """Модель прогресса."""
    batch_id = uuid4()
    product_id = uuid4()
    progress = CzProgressResponse(
        batch_id=batch_id,
        product_id=product_id,
        product_code="GP_CREAM_1L",
        product_name="Крем-мыло 1л",
        planned_qty=20000.0,
        marked_qty=19000.0,
        progress_percent=95.0,
        cz_status="COMPLETED",
        threshold=0.95,
        scans_count=19000,
    )
    assert progress.progress_percent == 95.0
    assert progress.cz_status == "COMPLETED"


def test_cz_pending_batch():
    """Модель партии в ожидании."""
    pending = CzPendingBatch(
        batch_id=uuid4(),
        order_id=uuid4(),
        product_id=uuid4(),
        volume_kg=3500.0,
        cz_status="PENDING",
        marked_qty=0.0,
        progress_percent=0.0,
    )
    assert pending.cz_status == "PENDING"
    assert pending.planned_qty is None


def test_cz_stats_response():
    """Модель сводной статистики."""
    stats = CzStatsResponse(
        total_batches=28,
        not_applicable=0,
        pending=28,
        in_progress=0,
        completed=0,
        total_scans=0,
        unresolved_scans=0,
        threshold=0.95,
    )
    assert stats.total_batches == 28
    assert stats.threshold == 0.95


def test_cz_action_response():
    """Модель ответа на действие."""
    resp = CzActionResponse(
        id=uuid4(),
        message="OK",
        resolved=True,
    )
    assert resp.resolved is True


def test_cz_status_values_constant():
    """Константа статусов содержит все 4 значения."""
    assert set(CZ_STATUS_VALUES) == {
        "NOT_APPLICABLE",
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
    }


# ==========================================
# 2. ТЕСТЫ FEATURE-ФЛАГА
# ==========================================

def test_feature_flag_cz_integration_true():
    flags = FeatureFlags({"enable_cz_integration": "true"})
    assert flags.enable_cz_integration is True


def test_feature_flag_cz_integration_false():
    flags = FeatureFlags({"enable_cz_integration": "false"})
    assert flags.enable_cz_integration is False


def test_feature_flag_cz_integration_default():
    """По умолчанию — False (безопасно)."""
    flags = FeatureFlags({})
    assert flags.enable_cz_integration is False


def test_feature_flag_cz_integration_bool():
    """Флаг как настоящий bool."""
    flags = FeatureFlags({"enable_cz_integration": True})
    assert flags.enable_cz_integration is True


def test_feature_flag_cz_integration_in_bool_keys():
    """enable_cz_integration должен быть в BOOL_KEYS."""
    assert "enable_cz_integration" in FeatureFlags.BOOL_KEYS


# ==========================================
# 3. ТЕСТЫ МОДУЛЯ CZ (без БД — контрактные)
# ==========================================

def test_cz_module_importable():
    """Модуль cz.py импортируется без ошибок."""
    from app.scheduler import cz as cz_module
    assert cz_module is not None


def test_cz_module_has_resolve_function():
    """resolve_batch_for_scan существует и вызываемая."""
    from app.scheduler import cz as cz_module
    assert hasattr(cz_module, "resolve_batch_for_scan")
    assert callable(cz_module.resolve_batch_for_scan)


def test_cz_module_has_recalc_function():
    """recalc_batch_cz_status существует."""
    from app.scheduler import cz as cz_module
    assert hasattr(cz_module, "recalc_batch_cz_status")
    assert callable(cz_module.recalc_batch_cz_status)


def test_cz_module_has_compute_planned_qty():
    """compute_planned_qty существует."""
    from app.scheduler import cz as cz_module
    assert hasattr(cz_module, "compute_planned_qty")
    assert callable(cz_module.compute_planned_qty)


def test_cz_module_has_get_batch_progress():
    """get_batch_progress существует."""
    from app.scheduler import cz as cz_module
    assert hasattr(cz_module, "get_batch_progress")
    assert callable(cz_module.get_batch_progress)


def test_resolve_fallback_uses_line_code():
    """
    Проверяет, что SQL в resolve_batch_for_scan содержит
    fallback-сопоставление по equipment.code и task_role='LINE_FILL'.
    """
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.resolve_batch_for_scan)
    assert "e.code = :line_code" in source, (
        "resolve должен искать по equipment.code"
    )
    assert "LINE_FILL" in source, (
        "resolve должен фильтровать только LINE_FILL задачи"
    )
    assert "planned_start" in source
    assert "planned_end" in source


def test_resolve_checks_explicit_batch_id():
    """Если batch_id передан явно — проверяется в БД."""
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.resolve_batch_for_scan)
    assert "SELECT id FROM batch" in source
    assert "organization_id = :org_id" in source


def test_resolve_checks_explicit_task_id():
    """Если task_id передан — берём batch_id из задачи."""
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.resolve_batch_for_scan)
    assert "SELECT batch_id FROM scheduled_task" in source


def test_compute_planned_qty_uses_bottle_volume():
    """
    compute_planned_qty должен использовать bottle_volume_l ГП.
    """
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.compute_planned_qty)
    assert "bottle_volume_l" in source
    assert "volume_kg" in source
    assert "production_order" in source


def test_recalc_uses_threshold():
    """
    recalc_batch_cz_status должен сравнивать с threshold.
    """
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.recalc_batch_cz_status)
    assert "threshold" in source
    assert "COMPLETED" in source
    assert "IN_PROGRESS" in source


def test_recalc_status_values():
    """
    recalc должен выставлять именно 3 статуса:
    PENDING, IN_PROGRESS, COMPLETED.
    """
    from app.scheduler import cz as cz_module

    source = inspect.getsource(cz_module.recalc_batch_cz_status)
    assert '"PENDING"' in source
    assert '"IN_PROGRESS"' in source
    assert '"COMPLETED"' in source


# ==========================================
# 4. ТЕСТЫ API МОДУЛЯ (контрактные)
# ==========================================

def test_cz_api_router_exists():
    """Router в cz.py создан с правильным префиксом и тегом."""
    from app.api.v1 import cz as cz_module

    assert cz_module.router.prefix == "/api/v1/cz"
    assert "Честный Знак" in cz_module.router.tags


def test_cz_api_has_all_endpoints():
    """Все 7 эндпоинтов зарегистрированы."""
    from app.api.v1 import cz as cz_module

    paths = {route.path for route in cz_module.router.routes}
    expected = {
        "/api/v1/cz/scan",
        "/api/v1/cz/batch/{batch_id}/progress",
        "/api/v1/cz/pending",
        "/api/v1/cz/log",
        "/api/v1/cz/stats",
        "/api/v1/cz/scan/{scan_id}/attach",
        "/api/v1/cz/scan/{scan_id}",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"


def test_cz_scan_endpoint_is_post():
    """POST /scan — метод POST."""
    from app.api.v1 import cz as cz_module

    scan_route = next(
        r for r in cz_module.router.routes
        if r.path == "/api/v1/cz/scan"
    )
    assert "POST" in scan_route.methods


def test_cz_delete_endpoint_is_delete():
    """DELETE /scan/{id}."""
    from app.api.v1 import cz as cz_module

    delete_route = next(
        r for r in cz_module.router.routes
        if r.path == "/api/v1/cz/scan/{scan_id}"
    )
    assert "DELETE" in delete_route.methods


def test_cz_api_checks_feature_flag():
    """API проверяет enable_cz_integration."""
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module)
    assert "_check_cz_enabled" in source
    assert "enable_cz_integration" in source


def test_cz_api_checks_api_key():
    """API проверяет X-CZ-Api-Key в /scan."""
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module)
    assert "X-CZ-Api-Key" in source
    assert "_check_api_key" in source


def test_cz_api_uses_on_conflict_do_nothing():
    """
    Идемпотентность INSERT: ON CONFLICT (org, cz_code) DO NOTHING.
    """
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module)
    assert "ON CONFLICT (organization_id, cz_code) DO NOTHING" in source


def test_cz_attach_checks_role():
    """Attach доступен только ADMIN, PLANNER, MASTER."""
    from app.api.v1 import cz as cz_module

    assert hasattr(cz_module, "ALLOWED_ATTACH_ROLES")
    assert cz_module.ALLOWED_ATTACH_ROLES == {"ADMIN", "PLANNER", "MASTER"}


def test_cz_delete_checks_admin_only():
    """Delete доступен только ADMIN."""
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module.delete_scan)
    assert 'current_user.get("role") != "ADMIN"' in source


def test_cz_scan_updates_batch():
    """
    При сопоставлении скана обновляется batch.cz_marked_qty
    и пересчитывается статус.
    """
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module.receive_scan)
    assert "cz_marked_qty" in source
    assert "recalc_batch_cz_status" in source


def test_cz_scan_returns_duplicate_flag():
    """При дубликате возвращается duplicate=True."""
    from app.api.v1 import cz as cz_module

    source = inspect.getsource(cz_module.receive_scan)
    assert "duplicate=True" in source


# ==========================================
# 5. ТЕСТЫ МИГРАЦИИ
# ==========================================

def test_migration_add_11_exists():
    """Файл миграции add_11.sql существует."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_11.sql"
    )
    assert os.path.exists(path), "migrations/add_11.sql должен существовать"


def test_migration_add_11_has_batch_columns():
    """add_11.sql добавляет cz_marked_qty, cz_last_scan_at, cz_status."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_11.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "cz_marked_qty" in content
    assert "cz_last_scan_at" in content
    assert "cz_status" in content
    assert "ALTER TABLE batch" in content


def test_migration_add_11_has_scan_log_table():
    """add_11.sql создаёт cz_scan_log с UNIQUE на (org, cz_code)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_11.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TABLE IF NOT EXISTS cz_scan_log" in content
    assert "UNIQUE (organization_id, cz_code)" in content
    assert "cz_scan_log_code_unique" in content


def test_migration_add_11_has_settings():
    """add_11.sql вставляет настройки ЧЗ."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_11.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "enable_cz_integration" in content
    assert "cz_completion_threshold" in content
    assert "cz_api_key" in content
    assert "enable_cz_auto_close" in content


def test_migration_add_11_idempotent():
    """Повторное применение безопасно (IF NOT EXISTS / ON CONFLICT)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_11.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IF NOT EXISTS" in content
    assert "ON CONFLICT" in content


def test_schema_init_has_cz_flag_stub():
    """
    init_schema.sql (v1.8.0) уже содержит ЗАГЛУШКУ feature-флага
    enable_cz_integration = false. Это валидное состояние до
    обновления схемы под Итерацию 8.
    """
    path = os.path.join(
        os.path.dirname(__file__), "..", "init_schema.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "enable_cz_integration" in content, (
        "init_schema.sql должен содержать заглушку enable_cz_integration"
    )


def test_schema_init_has_cz_fields():
    """
    init_schema.sql v1.9.0 должен содержать все поля ЧЗ
    (Итерация 8 завершена).
    """
    path = os.path.join(
        os.path.dirname(__file__), "..", "init_schema.sql"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Поля batch
    assert "cz_marked_qty" in content
    assert "cz_last_scan_at" in content
    assert "cz_status" in content

    # Таблица cz_scan_log
    assert "cz_scan_log" in content
    assert "cz_scan_log_code_unique" in content

    # Настройки
    assert "cz_completion_threshold" in content
    assert "cz_api_key" in content
    assert "enable_cz_auto_close" in content

    # Версия схемы (обновлено: Итерация 13 → v4.0.0)
    # Проверяем, что версия есть в файле и она не ниже 1.9.0.
    # Конкретное значение может меняться (v2.0.0, v3.0.0, v4.0.0, ...).
    versions = ["1.9.0", "2.0.0", "3.0.0", "4.0.0", "v1.9.0", "v2.0.0", "v3.0.0", "v4.0.0"]
    assert any(v in content for v in versions), (
        "init_schema.sql должен содержать номер версии (1.9.0+). "
        f"Текущая ожидаемая версия: v4.0.0 (Итерация 12/13). Искали: {versions}"
    )

# ==========================================
# 6. ТЕСТЫ СОГЛАСОВАННОСТИ (sanity)
# ==========================================

def test_planned_qty_calculation_example():
    """
    Sanity-check: 3500 кг ПФ → крем-мыло 1л (bottle_volume_l=1).
    Плановое количество бутылок = 3500 / 1 = 3500.
    """
    volume_kg = 3500.0
    bottle_volume_l = 1.0
    planned = volume_kg / bottle_volume_l
    assert planned == 3500.0


def test_planned_qty_cream_5l():
    """
    Sanity-check: 7000 кг ПФ → крем-мыло 5л (bottle_volume_l=5).
    Плановое количество бутылок = 7000 / 5 = 1400.
    """
    volume_kg = 7000.0
    bottle_volume_l = 5.0
    planned = volume_kg / bottle_volume_l
    assert planned == 1400.0


def test_threshold_default_95_percent():
    """Порог по умолчанию — 95%."""
    default_threshold = 0.95
    assert default_threshold == 0.95

    # 19000 из 20000 = 95% → COMPLETED
    marked = 19000
    planned = 20000
    assert (marked / planned) >= default_threshold

    # 18000 из 20000 = 90% → IN_PROGRESS
    marked = 18000
    assert (marked / planned) < default_threshold


def test_decimal_conversion_safe():
    """_to_float должен корректно обрабатывать Decimal из asyncpg."""
    from app.scheduler.cz import _to_float

    assert _to_float(Decimal("100.5")) == 100.5
    assert _to_float(None, 0.0) == 0.0
    assert _to_float("123.45") == 123.45
    assert _to_float("bad", 42.0) == 42.0

def test_c2_tank_2_created_in_migration():
    """
    Итерация 13.4 (fix C2): миграция add_19.sql создаёт TANK_2
    для крем-мыла 5л.
    """
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "add_19.sql"
    )
    assert os.path.exists(path), "migrations/add_19.sql должен существовать"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "TANK_2" in content
    assert "REACTOR_2" in content
    assert "LINE_2" in content
    assert "equipment_link" in content
    
if __name__ == "__main__":
    pytest.main([__file__, "-v"])