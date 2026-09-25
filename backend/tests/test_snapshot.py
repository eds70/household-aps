# backend/tests/test_snapshot.py
"""
Тесты модуля snapshot (Итерация 13.15).

Проверяют:
  1. Что модуль snapshot.py экспортирует нужные функции.
  2. Что snapshot_all_catalogs имеет правильную сигнатуру.
  3. Что _has_column корректно работает.
  4. Интеграция: при создании плана снапшоты заполняются.

Тесты структурные + интеграционные (с БД).
"""

import inspect
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.scheduler import snapshot as snapshot_module
from app.scheduler.snapshot import (
    snapshot_all_catalogs,
    snapshot_exists,
    _has_column,
)

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


# ==========================================
# 1. СТРУКТУРНЫЕ ТЕСТЫ
# ==========================================

def test_module_exports_snapshot_all_catalogs():
    """snapshot_all_catalogs существует и вызываема."""
    assert hasattr(snapshot_module, "snapshot_all_catalogs")
    assert callable(snapshot_module.snapshot_all_catalogs)


def test_module_exports_snapshot_exists():
    """snapshot_exists существует."""
    assert hasattr(snapshot_module, "snapshot_exists")


def test_module_exports_has_column():
    """_has_column существует."""
    assert hasattr(snapshot_module, "_has_column")


def test_snapshot_all_catalogs_signature():
    """snapshot_all_catalogs принимает (session, org_id, version_id)."""
    sig = inspect.signature(snapshot_all_catalogs)
    params = list(sig.parameters.keys())

    assert "session" in params
    assert "org_id" in params
    assert "version_id" in params


def test_snapshot_all_catalogs_is_async():
    """snapshot_all_catalogs — async-функция."""
    assert inspect.iscoroutinefunction(snapshot_all_catalogs)


def test_snapshot_exists_is_async():
    """snapshot_exists — async-функция."""
    assert inspect.iscoroutinefunction(snapshot_exists)


def test_snapshot_all_catalogs_uses_on_conflict():
    """Исходник содержит ON CONFLICT DO NOTHING — идемпотентность."""
    src = inspect.getsource(snapshot_all_catalogs)
    assert "ON CONFLICT" in src
    assert "DO NOTHING" in src


def test_snapshot_all_catalogs_covers_all_four_snapshots():
    """Заполняет все 4 снапшот-таблицы."""
    src = inspect.getsource(snapshot_all_catalogs)
    assert "equipment_snapshot" in src
    assert "product_snapshot" in src
    assert "operation_snapshot" in src
    assert "calendar_snapshot" in src


def test_snapshot_all_catalogs_has_operator_pool_fallback():
    """Есть graceful-обработка отсутствия operator_pool."""
    src = inspect.getsource(snapshot_all_catalogs)
    assert "_has_column" in src
    assert "operator_pool" in src


def test_snapshot_all_catalogs_returns_stats_dict():
    """Возвращает dict со статистикой по каждой таблице."""
    src = inspect.getsource(snapshot_all_catalogs)
    assert '"equipment"' in src or "'equipment'" in src
    assert '"products"' in src or "'products'" in src
    assert '"operations"' in src or "'operations'" in src
    assert '"calendar_events"' in src or "'calendar_events'" in src


# ==========================================
# 2. ИНТЕГРАЦИОННЫЕ ТЕСТЫ (с БД)
# ==========================================

@pytest.mark.asyncio
async def test_snapshot_creates_all_four_tables_data(async_session):
    """snapshot_all_catalogs заполняет 4 таблицы для новой версии."""
    version_id = uuid4()

    # Создаём schedule_version (триггер plan_settings сработает сам)
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'Test Snapshot', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await async_session.commit()

    try:
        # Вызываем snapshot
        stats = await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
        )
        await async_session.commit()

        # Проверяем, что все 4 таблицы заполнены
        for table, key in [
            ("equipment_snapshot", "equipment"),
            ("product_snapshot", "products"),
            ("operation_snapshot", "operations"),
            ("calendar_snapshot", "calendar_events"),
        ]:
            result = await async_session.execute(
                text(f"SELECT COUNT(*) AS cnt FROM {table} WHERE version_id = :vid"),
                {"vid": version_id},
            )
            count = result.fetchone().cnt
            assert count > 0, f"{table} пуста (stats['{key}']={stats[key]})"
    finally:
        # Удаляем version (CASCADE удалит снапшоты)
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_snapshot_idempotent(async_session):
    """Повторный вызов snapshot_all_catalogs не создаёт дубликатов."""
    version_id = uuid4()
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'Test Idempotent', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await async_session.commit()

    try:
        # Первый вызов
        stats1 = await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
        )
        await async_session.commit()

        # Второй вызов
        stats2 = await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
        )
        await async_session.commit()

        # Второй вызов не должен ничего вставить
        assert stats2["equipment"] == 0
        assert stats2["products"] == 0
        assert stats2["operations"] == 0
        assert stats2["calendar_events"] == 0

        # Но первый вызов что-то вставил
        assert stats1["equipment"] > 0
        assert stats1["products"] > 0
        assert stats1["operations"] > 0
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_snapshot_exists_returns_true_after_snapshot(async_session):
    """snapshot_exists() → True после заполнения."""
    version_id = uuid4()
    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'Test Exists', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await async_session.commit()

    try:
        # До — пусто
        exists_before = await snapshot_exists(async_session, version_id)
        assert exists_before is False, "До snapshot_exists должен вернуть False"

        # Заполняем
        await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
        )
        await async_session.commit()

        # После — есть
        exists_after = await snapshot_exists(async_session, version_id)
        assert exists_after is True, "После snapshot_exists должен вернуть True"
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_snapshot_all_catalogs_filters_by_org(async_session):
    """snapshot_all_catalogs копирует только данные своей организации."""
    other_org_id = uuid4()
    version_id = uuid4()

    await async_session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'Test Org Filter', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await async_session.commit()

    try:
        stats = await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
        )
        await async_session.commit()

        # Проверяем, что в снапшотах только записи TEST_ORG_ID
        result = await async_session.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM equipment_snapshot
                WHERE version_id = :vid AND organization_id != :org_id
            """),
            {"vid": version_id, "org_id": TEST_ORG_ID},
        )
        other_org_count = result.fetchone().cnt
        assert other_org_count == 0, (
            f"В снапшотах найдены записи чужой организации: {other_org_count}"
        )

        assert stats["equipment"] > 0
    finally:
        await async_session.execute(
            text("DELETE FROM schedule_version WHERE id = :vid"),
            {"vid": version_id},
        )
        await async_session.commit()


@pytest.mark.asyncio
async def test_has_column_detects_existing(async_session):
    """_has_column находит существующую колонку."""
    exists = await _has_column(async_session, "equipment", "code")
    assert exists is True


@pytest.mark.asyncio
async def test_has_column_returns_false_for_missing(async_session):
    """_has_column не находит несуществующую колонку."""
    exists = await _has_column(async_session, "equipment", "nonexistent_column_xyz")
    assert exists is False


@pytest.mark.asyncio
async def test_has_column_detects_operator_pool(async_session):
    """_has_column находит operator_pool в operation_template."""
    exists = await _has_column(async_session, "operation_template", "operator_pool")
    assert exists is True, (
        "Колонка operation_template.operator_pool должна существовать "
        "(миграция add_09.sql)"
    )


@pytest.mark.asyncio
async def test_snapshot_does_not_touch_existing_versions(async_session):
    """
    Заполнение снапшотов для версии A не влияет на версию B.

    Создаём две версии, заполняем только первую, проверяем что
    у второй снапшотов нет.
    """
    version_a = uuid4()
    version_b = uuid4()

    for vid, name in [(version_a, "A"), (version_b, "B")]:
        await async_session.execute(
            text("""
                INSERT INTO schedule_version
                    (id, organization_id, name, version_type, is_active, created_at)
                VALUES
                    (:id, :org_id, :name, 'MONTHLY', FALSE, NOW())
            """),
            {"id": vid, "org_id": TEST_ORG_ID, "name": f"Test Isolation {name}"},
        )
    await async_session.commit()

    try:
        # Заполняем только A
        await snapshot_all_catalogs(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_a,
        )
        await async_session.commit()

        # A — есть
        exists_a = await snapshot_exists(async_session, version_a)
        assert exists_a is True

        # B — пусто
        exists_b = await snapshot_exists(async_session, version_b)
        assert exists_b is False, (
            "Заполнение снапшотов для версии A не должно влиять на версию B"
        )
    finally:
        for vid in (version_a, version_b):
            await async_session.execute(
                text("DELETE FROM schedule_version WHERE id = :vid"),
                {"vid": vid},
            )
        await async_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])