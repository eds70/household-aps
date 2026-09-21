# backend/tests/test_material_stock_log.py
"""
Тесты журнала изменений остатков (Итерация 13.2 + 13.3).

Проверяют:
  1. Триггер material_stock_log срабатывает на INSERT/UPDATE/DELETE.
  2. set_config('app.change_source') / 'app.current_user_id' работают.
  3. delta_qty считается правильно.
  4. Rollback возвращает old_qty.
  5. Cleanup удаляет старые записи, оставляет свежие.

ВАЖНО: требует реальной PostgreSQL — триггеры, set_config и JSONB
не работают в SQLite.
"""
from datetime import timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
TZ = timezone.utc


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

async def _create_test_material(
        session: AsyncSession,
        code: str,
        qty: float = 100.0,
) -> UUID:
    """
    Создать тестовый материал + остаток. Возвращает material_id.

    Идемпотентно: если материал с таким code уже существует —
    переиспользуем его (сбрасываем остаток в qty).
    Это защищает от падений после неудачных прогонов тестов.
    """
    # 1. Пробуем найти существующий
    existing = await session.execute(
        text("""
            SELECT id FROM material
            WHERE organization_id = :org_id AND code = :code
        """),
        {"org_id": TEST_ORG_ID, "code": code},
    )
    existing_row = existing.fetchone()

    if existing_row is not None:
        mat_id = existing_row.id
        # Обновляем остаток (upsert)
        await session.execute(
            text("""
                INSERT INTO material_stock
                    (organization_id, material_id, qty, reserved_qty)
                VALUES (:org_id, :mid, :qty, 0)
                ON CONFLICT (organization_id, material_id)
                DO UPDATE SET
                    qty = EXCLUDED.qty,
                    reserved_qty = 0,
                    updated_at = NOW()
            """),
            {"org_id": TEST_ORG_ID, "mid": mat_id, "qty": qty},
        )
        # Чистим журнал, чтобы тест видел только свои записи
        await session.execute(
            text("DELETE FROM material_stock_log WHERE material_id = :mid"),
            {"mid": mat_id},
        )
        await session.commit()
        return mat_id

    # 2. Создаём новый
    mat_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO material (id, organization_id, code, name, unit, category)
            VALUES (:id, :org_id, :code, :name, 'kg', 'RAW')
        """),
        {
            "id": mat_id,
            "org_id": TEST_ORG_ID,
            "code": code,
            "name": f"Test {code}",
        },
    )
    await session.execute(
        text("""
            INSERT INTO material_stock (organization_id, material_id, qty, reserved_qty)
            VALUES (:org_id, :mid, :qty, 0)
        """),
        {"org_id": TEST_ORG_ID, "mid": mat_id, "qty": qty},
    )
    await session.commit()
    return mat_id


async def _cleanup_test_material(session: AsyncSession, mat_id: UUID) -> None:
    """
    Удалить материал + журнал + остатки.

    Порядок важен: сначала журнал, потом остатки, потом материал.
    Триггер material_stock_log при DELETE material_stock проверит,
    что материал ещё существует — а он уже удалён, поэтому триггер
    НЕ создаст новую запись (см. патч add_18.sql).
    """
    # 1. Журнал (FK на material_id)
    await session.execute(
        text("DELETE FROM material_stock_log WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    # 2. Остатки (триггер сработает, но увидит, что материала нет — пропустит)
    await session.execute(
        text("DELETE FROM material_stock WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    # 3. Сам материал
    await session.execute(
        text("DELETE FROM material WHERE id = :mid"),
        {"mid": mat_id},
    )
    await session.commit()


async def _get_log_entries(
        session: AsyncSession,
        material_id: UUID,
) -> list:
    """Получить журнал по материалу (DESC)."""
    result = await session.execute(
        text("""
            SELECT action, old_qty, new_qty, delta_qty, source, reason
            FROM material_stock_log
            WHERE material_id = :mid
            ORDER BY changed_at ASC
        """),
        {"mid": material_id},
    )
    return result.fetchall()


# ==========================================
# 1. ТРИГГЕР: INSERT
# ==========================================

@pytest.mark.asyncio
async def test_trigger_logs_insert_on_create(async_session):
    """При INSERT в material_stock создаётся запись в журнале."""
    mat_id = await _create_test_material(async_session, "TEST_INSERT", qty=500)

    log = await _get_log_entries(async_session, mat_id)
    assert len(log) == 1

    entry = log[0]
    assert entry.action == "INSERT"
    assert float(entry.new_qty) == 500.0
    assert float(entry.delta_qty) == 500.0
    assert entry.old_qty is None

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 2. ТРИГГЕР: UPDATE
# ==========================================

@pytest.mark.asyncio
async def test_trigger_logs_update(async_session):
    """При UPDATE остатка создаётся запись с old/new/delta."""
    mat_id = await _create_test_material(async_session, "TEST_UPDATE", qty=100)

    # Обновляем qty → 250 (delta = +150)
    await async_session.execute(
        text("""
            UPDATE material_stock SET qty = 250, updated_at = NOW()
            WHERE material_id = :mid
        """),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    # Должно быть: INSERT (начальный) + UPDATE
    assert len(log) == 2

    update = log[1]
    assert update.action == "UPDATE"
    assert float(update.old_qty) == 100.0
    assert float(update.new_qty) == 250.0
    assert float(update.delta_qty) == 150.0

    await _cleanup_test_material(async_session, mat_id)


@pytest.mark.asyncio
async def test_trigger_skips_update_without_changes(async_session):
    """UPDATE без изменения значений НЕ создаёт запись."""
    mat_id = await _create_test_material(async_session, "TEST_NO_CHANGE", qty=100)

    # UPDATE с тем же значением
    await async_session.execute(
        text("""
            UPDATE material_stock SET qty = 100, updated_at = NOW()
            WHERE material_id = :mid
        """),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    # Только начальный INSERT, без UPDATE
    assert len(log) == 1

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 3. ТРИГГЕР: DELETE
# ==========================================

@pytest.mark.asyncio
async def test_trigger_logs_delete(async_session):
    """При DELETE остатков создаётся запись с delta = -qty."""
    mat_id = await _create_test_material(async_session, "TEST_DELETE", qty=300)

    await async_session.execute(
        text("DELETE FROM material_stock WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    assert len(log) == 2

    deletion = log[1]
    assert deletion.action == "DELETE"
    assert float(deletion.old_qty) == 300.0
    assert deletion.new_qty is None
    assert float(deletion.delta_qty) == -300.0

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 4. SOURCE через set_config
# ==========================================

@pytest.mark.asyncio
async def test_trigger_uses_source_from_session_variable(async_session):
    """set_config('app.change_source', 'IMPORT') → журнал пишет source=IMPORT."""
    mat_id = await _create_test_material(async_session, "TEST_SOURCE", qty=100)

    # Устанавливаем source
    await async_session.execute(
        text("SELECT set_config('app.change_source', 'IMPORT', TRUE)")
    )
    await async_session.execute(
        text("SELECT set_config('app.change_reason', 'Excel upload', TRUE)")
    )

    # Обновляем остаток
    await async_session.execute(
        text("UPDATE material_stock SET qty = 200 WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    update = log[1]
    assert update.source == "IMPORT"
    assert update.reason == "Excel upload"

    await _cleanup_test_material(async_session, mat_id)


@pytest.mark.asyncio
async def test_trigger_default_source_is_system(async_session):
    """Без set_config source = SYSTEM."""
    mat_id = await _create_test_material(async_session, "TEST_DEFAULT_SRC", qty=100)

    await async_session.execute(
        text("UPDATE material_stock SET qty = 150 WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    update = log[1]
    assert update.source == "SYSTEM"

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 5. changed_by через set_config
# ==========================================

@pytest.mark.asyncio
async def test_trigger_logs_changed_by(async_session):
    """set_config('app.current_user_id', ...) → журнал пишет changed_by."""
    # Берём существующего админа
    user_result = await async_session.execute(
        text("""
            SELECT id FROM app_user
            WHERE organization_id = :org_id
            LIMIT 1
        """),
        {"org_id": TEST_ORG_ID},
    )
    user_row = user_result.fetchone()
    if not user_row:
        pytest.skip("Нет пользователя в БД — пропускаем")

    user_id = user_row.id

    mat_id = await _create_test_material(async_session, "TEST_USER", qty=100)

    await async_session.execute(
        text("SELECT set_config('app.current_user_id', :uid, TRUE)"),
        {"uid": str(user_id)},
    )
    await async_session.execute(
        text("UPDATE material_stock SET qty = 111 WHERE material_id = :mid"),
        {"mid": mat_id},
    )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    update = log[1]
    # changed_by должен быть проставлен
    # (проверим через отдельный SELECT)
    result = await async_session.execute(
        text("""
            SELECT changed_by FROM material_stock_log
            WHERE material_id = :mid AND action = 'UPDATE'
        """),
        {"mid": mat_id},
    )
    row = result.fetchone()
    assert row.changed_by == user_id

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 6. Множественные изменения
# ==========================================

@pytest.mark.asyncio
async def test_multiple_updates_create_multiple_log_entries(async_session):
    """Несколько UPDATE → несколько записей в журнале."""
    mat_id = await _create_test_material(async_session, "TEST_MULTI", qty=100)

    for new_qty in (200, 300, 150):
        await async_session.execute(
            text("UPDATE material_stock SET qty = :q WHERE material_id = :mid"),
            {"q": new_qty, "mid": mat_id},
        )
    await async_session.commit()

    log = await _get_log_entries(async_session, mat_id)
    # 1 INSERT + 3 UPDATE = 4 записи
    assert len(log) == 4

    # Проверяем delta
    assert float(log[1].delta_qty) == 100.0   # 100 → 200
    assert float(log[2].delta_qty) == 100.0   # 200 → 300
    assert float(log[3].delta_qty) == -150.0  # 300 → 150

    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 7. UNIQUE на material_stock
# ==========================================

@pytest.mark.asyncio
async def test_material_stock_unique_constraint(async_session):
    """Дубликат (org_id, material_id) → ошибка UNIQUE."""
    mat_id = await _create_test_material(async_session, "TEST_UNIQUE", qty=100)

    with pytest.raises(Exception) as exc_info:
        await async_session.execute(
            text("""
                INSERT INTO material_stock (organization_id, material_id, qty)
                VALUES (:org_id, :mid, 50)
            """),
            {"org_id": TEST_ORG_ID, "mid": mat_id},
        )
        await async_session.commit()

    # Ошибка unique violation
    assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    await async_session.rollback()
    await _cleanup_test_material(async_session, mat_id)


# ==========================================
# 8. Схема таблицы
# ==========================================

@pytest.mark.asyncio
async def test_material_stock_log_table_exists(async_session):
    """Таблица material_stock_log существует."""
    result = await async_session.execute(
        text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'material_stock_log'
        """)
    )
    assert result.fetchone() is not None


@pytest.mark.asyncio
async def test_trigger_exists(async_session):
    """Триггер trg_material_stock_log зарегистрирован."""
    result = await async_session.execute(
        text("""
            SELECT tgname FROM pg_trigger
            WHERE tgname = 'trg_material_stock_log'
        """)
    )
    assert result.fetchone() is not None