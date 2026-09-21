# backend/tests/test_materials_stock.py
"""
Тесты остатков материалов (Итерация 13.1).

Проверяют:
  1. GET /materials/ возвращает stock_qty / reserved_qty.
  2. POST /materials/ создаёт материал с initial_qty.
  3. PUT /materials/{id}/stock — upsert.
  4. GET /materials/stock — список остатков.
"""
from uuid import UUID

import pytest
from sqlalchemy import text

from app.api.v1.material_models import (
    MaterialCreate,
    MaterialResponse,
    MaterialStockUpdate,
)

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# PYDANTIC-МОДЕЛИ
# ==========================================

def test_material_create_with_initial_qty():
    """MaterialCreate принимает initial_qty."""
    m = MaterialCreate(
        code="TEST",
        name="Test material",
        unit="kg",
        category="RAW",
        initial_qty=500.0,
        initial_reserved_qty=100.0,
    )
    assert m.initial_qty == 500.0
    assert m.initial_reserved_qty == 100.0


def test_material_create_without_initial_qty():
    """По умолчанию initial_qty=0."""
    m = MaterialCreate(code="X", name="Y", unit="kg", category="RAW")
    assert m.initial_qty == 0.0
    assert m.initial_reserved_qty == 0.0


def test_material_create_rejects_negative_initial_qty():
    """Negative initial_qty → ошибка."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MaterialCreate(
            code="X", name="Y", unit="kg", category="RAW",
            initial_qty=-10,
        )


def test_material_response_has_stock_fields():
    """MaterialResponse содержит stock_qty / reserved_qty."""
    fields = MaterialResponse.model_fields
    assert "stock_qty" in fields
    assert "reserved_qty" in fields


def test_material_stock_update_partial():
    """MaterialStockUpdate — все поля опциональны."""
    u = MaterialStockUpdate()
    assert u.qty is None
    assert u.reserved_qty is None


# ==========================================
# СТРУКТУРНЫЕ ТЕСТЫ SQL
# ==========================================

def test_get_all_materials_joins_stock():
    """GET /materials/ делает LEFT JOIN material_stock."""
    import inspect
    from app.api.v1 import materials as materials_module
    src = inspect.getsource(materials_module.get_all_materials)
    assert "material_stock" in src
    assert "LEFT JOIN" in src
    assert "stock_qty" in src or "COALESCE" in src


def test_create_material_inserts_stock():
    """POST /materials/ вставляет запись в material_stock."""
    import inspect
    from app.api.v1 import materials as materials_module
    src = inspect.getsource(materials_module.create_material)
    assert "material_stock" in src
    assert "initial_qty" in src or "initial_reserved" in src


def test_update_stock_uses_upsert():
    """PUT /stock использует ON CONFLICT DO NOTHING перед UPDATE."""
    import inspect
    from app.api.v1 import materials as materials_module
    src = inspect.getsource(materials_module.update_material_stock)
    assert "ON CONFLICT" in src
    assert "material_stock" in src


def test_update_stock_sets_log_context():
    """PUT /stock вызывает _set_log_context."""
    import inspect
    from app.api.v1 import materials as materials_module
    src = inspect.getsource(materials_module.update_material_stock)
    assert "_set_log_context" in src


# ==========================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ (нужна БД)
# ==========================================

@pytest.mark.asyncio
async def test_material_stock_unique_constraint_exists(async_session):
    """UNIQUE (organization_id, material_id) существует."""
    result = await async_session.execute(
        text("""
            SELECT conname FROM pg_constraint
            WHERE conname = 'material_stock_org_mat_unique'
        """)
    )
    assert result.fetchone() is not None


@pytest.mark.asyncio
async def test_material_stock_log_table_exists(async_session):
    """Таблица material_stock_log существует."""
    result = await async_session.execute(
        text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'material_stock_log'
        """)
    )
    assert result.fetchone() is not None


@pytest.mark.asyncio
async def test_set_log_context_function_exists(async_session):
    """Функция _set_log_context работает с set_config."""
    from app.api.v1.materials import _set_log_context

    # Не должно падать
    await _set_log_context(
        async_session,
        user_id=None,
        source="TEST",
        reason="unit test",
    )
    await async_session.rollback()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])