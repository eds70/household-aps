# backend/tests/test_plan_settings_integration.py
"""
Интеграционные тесты plan_settings (Итерация 13.14).

Требуют реальной PostgreSQL — триггеры, JSONB, ON CONFLICT
не работают в SQLite.

Проверяют:
  1. Триггер копирует app_settings при создании schedule_version.
  2. Upsert обновляет значения.
  3. Изоляция: два плана имеют независимые настройки.
  4. CASCADE DELETE: удаление плана удаляет настройки.
  5. DataLoader читает из plan_settings при version_id.
"""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

async def _create_test_version(
        session: AsyncSession,
        name: str = "Test Plan",
) -> UUID:
    """Создать тестовую schedule_version. Возвращает ID."""
    vid = uuid4()
    await session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, :name, 'MONTHLY', FALSE, NOW())
        """),
        {"id": vid, "org_id": TEST_ORG_ID, "name": name},
    )
    await session.commit()
    return vid


async def _cleanup_test_version(
        session: AsyncSession,
        version_id: UUID,
) -> None:
    """Удалить тестовую версию и её plan_settings (CASCADE)."""
    await session.execute(
        text("""
            DELETE FROM schedule_version
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": TEST_ORG_ID},
    )
    await session.commit()


async def _get_plan_setting(
        session: AsyncSession,
        version_id: UUID,
        key: str,
):
    """Получить значение plan_setting."""
    result = await session.execute(
        text("""
            SELECT setting_value FROM plan_settings
            WHERE schedule_version_id = :vid AND setting_key = :key
        """),
        {"vid": version_id, "key": key},
    )
    row = result.fetchone()
    return row.setting_value if row else None


async def _upsert_plan_setting(
        session: AsyncSession,
        version_id: UUID,
        key: str,
        value: str,
) -> None:
    """Прямой upsert plan_setting (эмуляция API)."""
    await session.execute(
        text("""
            INSERT INTO plan_settings
                (organization_id, schedule_version_id, setting_key,
                 setting_value, value_type, category, label)
            VALUES
                (:org_id, :vid, :key, CAST(:value AS jsonb),
                 'int', 'planning', 'Test')
            ON CONFLICT (schedule_version_id, setting_key) DO UPDATE
                SET setting_value = EXCLUDED.setting_value,
                    updated_at = NOW()
        """),
        {
            "org_id": TEST_ORG_ID,
            "vid": version_id,
            "key": key,
            "value": value,
        },
    )
    await session.commit()


# ==========================================
# 1. ТРИГГЕР
# ==========================================

@pytest.mark.asyncio
async def test_trigger_copies_app_settings_on_create(async_session):
    """При создании version триггер копирует app_settings в plan_settings."""
    vid = await _create_test_version(async_session, "Trigger Test")

    try:
        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM plan_settings
                WHERE schedule_version_id = :vid
            """),
            {"vid": vid},
        )
        count = result.fetchone().cnt
        assert count > 0, "Триггер должен был скопировать app_settings"

        result = await async_session.execute(
            text("""
                SELECT setting_value FROM plan_settings
                WHERE schedule_version_id = :vid
                  AND setting_key = 'horizon_hours'
            """),
            {"vid": vid},
        )
        row = result.fetchone()
        assert row is not None, "horizon_hours должен быть скопирован"
    finally:
        await _cleanup_test_version(async_session, vid)


@pytest.mark.asyncio
async def test_trigger_does_not_duplicate(async_session):
    """Повторное применение триггера идемпотентно."""
    vid = await _create_test_version(async_session, "Idempotent Test")

    try:
        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM plan_settings
                WHERE schedule_version_id = :vid
            """),
            {"vid": vid},
        )
        count_before = result.fetchone().cnt

        await async_session.execute(
            text("""
                INSERT INTO plan_settings
                    (organization_id, schedule_version_id, setting_key,
                     setting_value, value_type, category, label)
                SELECT
                    :org_id, :vid, s.setting_key, s.setting_value,
                    s.value_type, s.category, s.label
                FROM app_settings s
                WHERE s.organization_id = :org_id
                ON CONFLICT (schedule_version_id, setting_key) DO NOTHING
            """),
            {"org_id": TEST_ORG_ID, "vid": vid},
        )
        await async_session.commit()

        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM plan_settings
                WHERE schedule_version_id = :vid
            """),
            {"vid": vid},
        )
        count_after = result.fetchone().cnt
        assert count_after == count_before, (
            "Повторный запуск не должен создавать дубли"
        )
    finally:
        await _cleanup_test_version(async_session, vid)


# ==========================================
# 2. UPSERT
# ==========================================

@pytest.mark.asyncio
async def test_plan_setting_upsert_updates_value(async_session):
    """UPDATE по (version_id, key) обновляет значение."""
    vid = await _create_test_version(async_session, "Upsert Test")

    try:
        await _upsert_plan_setting(async_session, vid, "horizon_hours", "800")
        value = await _get_plan_setting(async_session, vid, "horizon_hours")
        assert value == 800

        await _upsert_plan_setting(async_session, vid, "horizon_hours", "1200")
        value = await _get_plan_setting(async_session, vid, "horizon_hours")
        assert value == 1200
    finally:
        await _cleanup_test_version(async_session, vid)


# ==========================================
# 3. ИЗОЛЯЦИЯ ПЛАНОВ
# ==========================================

@pytest.mark.asyncio
async def test_two_plans_have_isolated_settings(async_session):
    """Два плана имеют независимые настройки."""
    vid_a = await _create_test_version(async_session, "Plan A")
    vid_b = await _create_test_version(async_session, "Plan B")

    try:
        a_val = await _get_plan_setting(async_session, vid_a, "horizon_hours")
        b_val = await _get_plan_setting(async_session, vid_b, "horizon_hours")
        assert a_val == b_val, "Оба плана должны иметь одинаковые начальные настройки"

        await _upsert_plan_setting(async_session, vid_a, "horizon_hours", "2000")

        a_new = await _get_plan_setting(async_session, vid_a, "horizon_hours")
        b_new = await _get_plan_setting(async_session, vid_b, "horizon_hours")

        assert a_new == 2000, "A должен был обновиться"
        assert b_new != 2000, "B не должен меняться"
    finally:
        await _cleanup_test_version(async_session, vid_a)
        await _cleanup_test_version(async_session, vid_b)


# ==========================================
# 4. UNIQUE CONSTRAINT
# ==========================================

@pytest.mark.asyncio
async def test_unique_constraint_on_duplicate_insert(async_session):
    """UNIQUE (version_id, setting_key) — дубликат падает."""
    vid = await _create_test_version(async_session, "Unique Test")

    try:
        await async_session.execute(
            text("""
                INSERT INTO plan_settings
                    (organization_id, schedule_version_id, setting_key,
                     setting_value, value_type, category, label)
                VALUES
                    (:org_id, :vid, 'test_unique', '100'::jsonb,
                     'int', 'planning', 'Test')
            """),
            {"org_id": TEST_ORG_ID, "vid": vid},
        )
        await async_session.commit()

        with pytest.raises(Exception):
            await async_session.execute(
                text("""
                    INSERT INTO plan_settings
                        (organization_id, schedule_version_id, setting_key,
                         setting_value, value_type, category, label)
                    VALUES
                        (:org_id, :vid, 'test_unique', '200'::jsonb,
                         'int', 'planning', 'Test')
                """),
                {"org_id": TEST_ORG_ID, "vid": vid},
            )
            await async_session.commit()

        await async_session.rollback()
    finally:
        await _cleanup_test_version(async_session, vid)


# ==========================================
# 5. CASCADE DELETE
# ==========================================

@pytest.mark.asyncio
async def test_plan_settings_cascade_on_version_delete(async_session):
    """При удалении schedule_version — plan_settings удаляются CASCADE."""
    vid = await _create_test_version(async_session, "Cascade Test")

    result = await async_session.execute(
        text("""
            SELECT COUNT(*) AS cnt FROM plan_settings
            WHERE schedule_version_id = :vid
        """),
        {"vid": vid},
    )
    assert result.fetchone().cnt > 0

    await _cleanup_test_version(async_session, vid)

    result = await async_session.execute(
        text("""
            SELECT COUNT(*) AS cnt FROM plan_settings
            WHERE schedule_version_id = :vid
        """),
        {"vid": vid},
    )
    assert result.fetchone().cnt == 0, "plan_settings должны удалиться CASCADE"


# ==========================================
# 6. DATA LOADER
# ==========================================

@pytest.mark.asyncio
async def test_data_loader_reads_from_plan_settings(async_session):
    """DataLoader читает plan_settings при version_id."""
    from app.scheduler.data_loader import DataLoader

    vid = await _create_test_version(async_session, "DataLoader Test")

    try:
        await _upsert_plan_setting(async_session, vid, "horizon_hours", "999")

        loader = DataLoader(
            org_id=TEST_ORG_ID,
            session=async_session,
            version_id=vid,
        )

        result = await loader._load_app_settings(async_session)
        assert result.get("horizon_hours") == 999, (
            f"DataLoader должен читать из plan_settings, "
            f"получено: {result.get('horizon_hours')}"
        )
    finally:
        await _cleanup_test_version(async_session, vid)


@pytest.mark.asyncio
async def test_data_loader_without_version_uses_app_settings(async_session):
    """DataLoader без version_id читает app_settings."""
    from app.scheduler.data_loader import DataLoader

    loader = DataLoader(
        org_id=TEST_ORG_ID,
        session=async_session,
        version_id=None,
    )

    result = await loader._load_app_settings(async_session)
    assert "horizon_hours" in result


# ==========================================
# 7. СХЕМА
# ==========================================

@pytest.mark.asyncio
async def test_plan_settings_table_exists(async_session):
    """Таблица plan_settings существует."""
    result = await async_session.execute(
        text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'plan_settings'
        """)
    )
    assert result.fetchone() is not None


@pytest.mark.asyncio
async def test_trigger_exists(async_session):
    """Триггер trg_copy_app_settings_to_plan зарегистрирован."""
    result = await async_session.execute(
        text("""
            SELECT tgname FROM pg_trigger
            WHERE tgname = 'trg_copy_app_settings_to_plan'
        """)
    )
    assert result.fetchone() is not None


@pytest.mark.asyncio
async def test_indexes_exist(async_session):
    """Оба индекса существуют."""
    result = await async_session.execute(
        text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'plan_settings'
        """)
    )
    indexes = {row.indexname for row in result.fetchall()}
    assert "idx_plan_settings_version" in indexes
    assert "idx_plan_settings_org_category" in indexes