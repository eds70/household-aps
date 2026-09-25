# backend/tests/test_schedule_create_version.py
"""
Тесты создания версии плана (Итерация 13.15).

Проверяют:
  1. POST /api/v1/schedule/versions заполняет снапшоты.
  2. GET /api/v1/schedule/versions возвращает has_snapshot.
  3. Что старые планы без снапшотов имеют has_snapshot=false.

Тесты структурные + интеграционные.
"""

import inspect
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.api.v1 import schedule as schedule_module

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# 1. СТРУКТУРНЫЕ ТЕСТЫ
# ==========================================

def test_schedule_module_imports_snapshot():
    """schedule.py импортирует snapshot_all_catalogs."""
    src = inspect.getsource(schedule_module)
    assert "snapshot_all_catalogs" in src
    assert "from app.scheduler.snapshot import" in src


def test_create_schedule_version_calls_snapshot():
    """create_schedule_version вызывает snapshot_all_catalogs."""
    src = inspect.getsource(schedule_module.create_schedule_version)
    assert "snapshot_all_catalogs" in src
    assert "session=db" in src or "session = db" in src
    assert "org_id=org_id" in src
    assert "version_id=version_id" in src


def test_create_schedule_version_returns_has_snapshot():
    """Ответ create_schedule_version содержит has_snapshot=True."""
    src = inspect.getsource(schedule_module.create_schedule_version)
    assert '"has_snapshot": True' in src or "'has_snapshot': True" in src


def test_create_schedule_version_returns_snapshot_stats():
    """Ответ содержит snapshot_stats с данными по каждой таблице."""
    src = inspect.getsource(schedule_module.create_schedule_version)
    assert "snapshot_stats" in src


def test_get_versions_returns_has_snapshot():
    """get_schedule_versions селектит has_snapshot через EXISTS."""
    src = inspect.getsource(schedule_module.get_schedule_versions)
    assert "has_snapshot" in src
    assert "EXISTS" in src
    assert "equipment_snapshot" in src


def test_get_versions_has_has_snapshot_in_response():
    """В ответе get_schedule_versions есть ключ has_snapshot."""
    src = inspect.getsource(schedule_module.get_schedule_versions)
    assert '"has_snapshot"' in src or "'has_snapshot'" in src


# ==========================================
# 2. ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ==========================================

@pytest.mark.asyncio
async def test_create_version_fills_snapshots(async_session):
    """
    При вызове create_schedule_version (эмулируем через SQL)
    снапшоты заполняются.

    Полноценный HTTP-тест требует TestClient + JWT.
    Здесь проверяем на уровне БД: SQL из create_schedule_version
    + snapshot_all_catalogs.
    """
    from app.scheduler.snapshot import snapshot_all_catalogs

    version_id = uuid4()

    # Эмулируем то, что делает create_schedule_version:
    # 1. INSERT schedule_version
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active,
                 created_at, comment)
            VALUES
                (:id, :org_id, :name, :vtype, FALSE, NOW(), :comment)
        """),
        {
            "id": version_id,
            "org_id": TEST_ORG_ID,
            "name": "test-create-version",
            "vtype": "MONTHLY",
            "comment": "test",
        },
    )

    # 2. snapshot_all_catalogs
    stats = await snapshot_all_catalogs(
        session=async_session,
        org_id=TEST_ORG_ID,
        version_id=version_id,
    )
    await async_session.commit()

    try:
        # Проверка: снапшоты заполнены
        assert stats["equipment"] > 0
        assert stats["products"] > 0
        assert stats["operations"] > 0

        # Проверка: has_snapshot = true (через SQL-запрос из get_schedule_versions)
        result = await async_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM equipment_snapshot
                    WHERE version_id = :vid LIMIT 1
                ) AS has_snapshot
            """),
            {"vid": version_id},
        )
        assert result.fetchone().has_snapshot is True
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_get_versions_has_snapshot_true_after_create(async_session):
    """
    После создания плана + snapshot → has_snapshot=true.
    После удаления всех снапшотов → has_snapshot=false.
    """
    from app.scheduler.snapshot import snapshot_all_catalogs

    version_id = uuid4()
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'test-has-snapshot', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )

    # Заполняем снапшоты
    await snapshot_all_catalogs(async_session, TEST_ORG_ID, version_id)
    await async_session.commit()

    try:
        # Проверяем через запрос, аналогичный get_schedule_versions
        result = await async_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM equipment_snapshot
                    WHERE version_id = :vid LIMIT 1
                ) AS has_snapshot
            """),
            {"vid": version_id},
        )
        assert result.fetchone().has_snapshot is True

        # Удаляем все снапшоты (эмулируем «старый план»)
        await async_session.execute(
            text("DELETE FROM equipment_snapshot WHERE version_id = :vid"),
            {"vid": version_id},
        )
        await async_session.execute(
            text("DELETE FROM product_snapshot WHERE version_id = :vid"),
            {"vid": version_id},
        )
        await async_session.execute(
            text("DELETE FROM operation_snapshot WHERE version_id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()

        # Теперь has_snapshot должен быть false
        result2 = await async_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM equipment_snapshot
                    WHERE version_id = :vid LIMIT 1
                ) AS has_snapshot
            """),
            {"vid": version_id},
        )
        assert result2.fetchone().has_snapshot is False
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_create_version_triggers_plan_settings_copy(async_session):
    """
    При создании schedule_version триггер copy_app_settings_to_plan
    автоматически копирует app_settings в plan_settings.

    Итерация 13.14 / 13.15: это работает на уровне БД, не в Python.
    """
    version_id = uuid4()
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'test-trigger-plan-settings', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await async_session.commit()

    try:
        # Проверяем, что триггер сработал
        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM plan_settings
                WHERE schedule_version_id = :vid
            """),
            {"vid": version_id},
        )
        plan_settings_count = result.fetchone().cnt
        assert plan_settings_count > 0, (
            "Триггер copy_app_settings_to_plan не сработал — "
            "plan_settings пусты после создания schedule_version"
        )
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_create_version_has_both_snapshot_and_plan_settings(async_session):
    """
    При создании плана заполняются И снапшоты, И plan_settings.

    Это полная симуляция create_schedule_version.
    """
    from app.scheduler.snapshot import snapshot_all_catalogs

    version_id = uuid4()

    # Шаг 1: INSERT schedule_version (триггер сработает)
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'test-full-create', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )

    # Шаг 2: snapshot_all_catalogs
    await snapshot_all_catalogs(
        session=async_session,
        org_id=TEST_ORG_ID,
        version_id=version_id,
    )
    await async_session.commit()

    try:
        # Проверка снапшотов
        for table in ("equipment_snapshot", "product_snapshot",
                      "operation_snapshot", "calendar_snapshot"):
            result = await async_session.execute(
                text(f"SELECT COUNT(*) AS cnt FROM {table} WHERE version_id = :vid"),
                {"vid": version_id},
            )
            assert result.fetchone().cnt > 0, f"{table} пуста"

        # Проверка plan_settings (триггер)
        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM plan_settings
                WHERE schedule_version_id = :vid
            """),
            {"vid": version_id},
        )
        assert result.fetchone().cnt > 0, "plan_settings пусты"
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])