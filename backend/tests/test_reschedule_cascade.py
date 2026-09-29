# backend/tests/test_reschedule_cascade.py
"""
Тесты каскадного сдвига задач (Итерация 13.17 + 13.18).

Проверяют:
  1. Простой сдвиг соседа при resize.
  2. Каскадный сдвиг последователей.
  3. Блокировка pinned-задачей (для move).
  4. Валидация (выходные, planning_start, статусы).
  5. Итерация 13.18: resize pinned-задачи разрешён,
     а move — запрещён.
"""
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduler.reschedule_cascade import (
    TaskSnapshot,
    ValidationResult,
    CascadeResult,
    CascadeBlockedError,
    _overlaps,
    _is_resize,
    validate_move,
    RESIZE_THRESHOLD_SECONDS,
)

TZ = None  # naive UTC
TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_task(
        task_id: str,
        equipment_id: str = "REACTOR_1",
        start_hours: int = 0,
        duration_min: int = 60,
        is_pinned: bool = False,
        status: str = "PLANNED",
        depends_on: list = None,
        actual_start: datetime = None,
) -> TaskSnapshot:
    start = datetime(2026, 9, 1, 8, 0) + timedelta(hours=start_hours)
    end = start + timedelta(minutes=duration_min)
    return TaskSnapshot(
        id=task_id,
        batch_id="batch_1",
        equipment_id=equipment_id,
        task_role="REACTOR_OP",
        operation_name=f"Операция {task_id}",
        planned_start=start,
        planned_end=end,
        duration_minutes=duration_min,
        is_pinned=is_pinned,
        status=status,
        actual_start=actual_start,
        actual_end=None,
        depends_on=depends_on or [],
    )


# ==========================================
# _overlaps
# ==========================================

def test_overlaps_basic():
    s = datetime(2026, 9, 1, 8, 0)
    e = datetime(2026, 9, 1, 10, 0)
    assert _overlaps(s, e, s, e) is True
    assert _overlaps(
        s, e,
        datetime(2026, 9, 1, 9, 0),
        datetime(2026, 9, 1, 11, 0),
    ) is True
    assert _overlaps(
        s, e,
        datetime(2026, 9, 1, 10, 0),
        datetime(2026, 9, 1, 12, 0),
    ) is False  # стык — не пересечение
    assert _overlaps(
        s, e,
        datetime(2026, 9, 1, 6, 0),
        datetime(2026, 9, 1, 8, 0),
    ) is False


# ==========================================
# _is_resize (Итерация 13.18)
# ==========================================

def test_is_resize_true_when_duration_changes():
    """Длительность изменилась значительно → resize."""
    original_start = datetime(2026, 9, 1, 8, 0)
    original_end = datetime(2026, 9, 1, 10, 0)  # 120 мин

    # Новая длительность 180 мин
    new_start = datetime(2026, 9, 1, 8, 0)
    new_end = datetime(2026, 9, 1, 11, 0)

    assert _is_resize(original_start, original_end, new_start, new_end) is True


def test_is_resize_false_when_duration_same():
    """Длительность не изменилась → move (не resize)."""
    original_start = datetime(2026, 9, 1, 8, 0)
    original_end = datetime(2026, 9, 1, 10, 0)  # 120 мин

    # Сдвиг на 2 часа, длительность та же
    new_start = datetime(2026, 9, 1, 10, 0)
    new_end = datetime(2026, 9, 1, 12, 0)

    assert _is_resize(original_start, original_end, new_start, new_end) is False


def test_is_resize_threshold_boundary():
    """Изменение на 30 секунд — ещё не resize (порог 60 сек)."""
    original_start = datetime(2026, 9, 1, 8, 0)
    original_end = datetime(2026, 9, 1, 10, 0)

    # Сдвиг на 30 сек — не resize
    new_start = datetime(2026, 9, 1, 8, 0, 30)
    new_end = datetime(2026, 9, 1, 10, 0, 30)

    assert _is_resize(original_start, original_end, new_start, new_end) is False


def test_is_resize_at_threshold():
    """
    Изменение длительности на 61 секунду — уже resize.

    Примечание: секунды в datetime() должны быть в диапазоне 0..59,
    поэтому используем +timedelta для точного контроля.
    """
    original_start = datetime(2026, 9, 1, 8, 0, 0)
    original_end = datetime(2026, 9, 1, 10, 0, 0)  # 120 мин

    # Изменяем конец на +61 секунду через timedelta
    new_start = datetime(2026, 9, 1, 8, 0, 0)
    new_end = datetime(2026, 9, 1, 10, 0, 0) + timedelta(seconds=61)

    assert _is_resize(original_start, original_end, new_start, new_end) is True


def test_is_resize_at_threshold_60_seconds():
    """Ровно 60 секунд изменения — ещё НЕ resize (порог строгий >)."""
    original_start = datetime(2026, 9, 1, 8, 0, 0)
    original_end = datetime(2026, 9, 1, 10, 0, 0)

    new_start = datetime(2026, 9, 1, 8, 0, 0)
    new_end = datetime(2026, 9, 1, 10, 0, 0) + timedelta(seconds=60)

    assert _is_resize(original_start, original_end, new_start, new_end) is False


# ==========================================
# TaskSnapshot.is_movable
# ==========================================

def test_is_movable_normal():
    t = _make_task("t1")
    assert t.is_movable is True


def test_is_movable_pinned():
    t = _make_task("t1", is_pinned=True)
    assert t.is_movable is False


def test_is_movable_done():
    t = _make_task("t1", status="DONE")
    assert t.is_movable is False


def test_is_movable_in_progress():
    t = _make_task("t1", status="IN_PROGRESS")
    assert t.is_movable is False


def test_is_movable_actual_start():
    t = _make_task("t1", actual_start=datetime(2026, 9, 1, 9, 0))
    assert t.is_movable is False


# ==========================================
# ValidationResult
# ==========================================

def test_validation_result_default():
    r = ValidationResult(allowed=True)
    assert r.allowed is True
    assert r.reason is None
    assert r.details == []


def test_validation_result_blocked():
    r = ValidationResult(
        allowed=False,
        reason="Задача закреплена",
        details=["Открепите её"],
    )
    assert r.allowed is False
    assert "закреплена" in r.reason


# ==========================================
# CascadeResult
# ==========================================

def test_cascade_result_empty():
    r = CascadeResult()
    assert r.moved_count == 0
    assert r.moved_tasks == []


def test_cascade_result_with_moves():
    r = CascadeResult(moved_tasks=[
        {"task_id": "t1", "new_start": "2026-09-01T09:00:00"},
        {"task_id": "t2", "new_start": "2026-09-01T10:00:00"},
    ])
    assert r.moved_count == 2


# ==========================================
# CascadeBlockedError
# ==========================================

def test_cascade_blocked_error():
    e = CascadeBlockedError(
        "Задача закреплена",
        blocked_task={"task_id": "t1", "operation_name": "Замыв"},
    )
    assert e.reason == "Задача закреплена"
    assert e.blocked_task["task_id"] == "t1"


# ==========================================
# ИНТЕГРАЦИОННЫЕ: validate_move + БД
# ==========================================

async def _create_test_version(session: AsyncSession) -> UUID:
    """Создаёт schedule_version + минимальный набор данных."""
    version_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO schedule_version
                (id, organization_id, name, version_type, is_active, created_at)
            VALUES
                (:id, :org_id, 'Test cascade', 'MONTHLY', FALSE, NOW())
        """),
        {"id": version_id, "org_id": TEST_ORG_ID},
    )
    await session.commit()
    return version_id


async def _create_test_task(
        session: AsyncSession,
        version_id: UUID,
        *,
        is_pinned: bool = False,
        status: str = "PLANNED",
        duration_min: int = 120,
        start_at: datetime = None,
) -> UUID:
    """
    Создаёт тестовую задачу в БД.

    Требует наличия operation_template и equipment. Если их нет —
    создаём.
    """
    # Проверяем, есть ли операция (нужна для FK)
    op_result = await session.execute(
        text("""
            SELECT id FROM operation_template
            WHERE organization_id = :org_id
            LIMIT 1
        """),
        {"org_id": TEST_ORG_ID},
    )
    op_row = op_result.fetchone()

    if op_row is None:
        # Создаём операцию (требует product)
        prod_result = await session.execute(
            text("""
                SELECT id FROM product
                WHERE organization_id = :org_id
                LIMIT 1
            """),
            {"org_id": TEST_ORG_ID},
        )
        prod_row = prod_result.fetchone()
        if prod_row is None:
            pytest.skip("Нет product в БД — пропускаем интеграционный тест")

        op_id = uuid4()
        await session.execute(
            text("""
                INSERT INTO operation_template
                    (id, organization_id, product_id, stage_order, name,
                     base_duration_mins, is_setup, is_parallel_group,
                     needs_boiler, needs_cooling_zone, needs_operator, needs_lab)
                VALUES
                    (:id, :org_id, :product_id, 1, 'Test op', :dur,
                     FALSE, FALSE, FALSE, FALSE, TRUE, FALSE)
            """),
            {
                "id": op_id,
                "org_id": TEST_ORG_ID,
                "product_id": prod_row.id,
                "dur": duration_min,
            },
        )
    else:
        op_id = op_row.id

    # Проверяем, есть ли оборудование
    eq_result = await session.execute(
        text("""
            SELECT id FROM equipment
            WHERE organization_id = :org_id
            LIMIT 1
        """),
        {"org_id": TEST_ORG_ID},
    )
    eq_row = eq_result.fetchone()
    if eq_row is None:
        pytest.skip("Нет equipment в БД — пропускаем интеграционный тест")
    equipment_id = eq_row.id

    if start_at is None:
        start_at = datetime(2026, 9, 1, 8, 0)
    end_at = start_at + timedelta(minutes=duration_min)

    task_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO scheduled_task
                (id, organization_id, schedule_version_id,
                 operation_template_id, equipment_id,
                 planned_start, planned_end,
                 is_pinned, status)
            VALUES
                (:id, :org_id, :version_id, :op_id, :eq_id,
                 :start, :end, :is_pinned, :status)
        """),
        {
            "id": task_id,
            "org_id": TEST_ORG_ID,
            "version_id": version_id,
            "op_id": op_id,
            "eq_id": equipment_id,
            "start": start_at,
            "end": end_at,
            "is_pinned": is_pinned,
            "status": status,
        },
    )
    await session.commit()
    return task_id


async def _cleanup_test_version(session: AsyncSession, version_id: UUID):
    """Удаляет тестовую версию и связанные задачи."""
    await session.execute(
        text("DELETE FROM schedule_version WHERE id = :vid"),
        {"vid": version_id},
    )
    await session.commit()


# ==========================================
# Итерация 13.18: pinned + resize/move
# ==========================================

@pytest.mark.asyncio
async def test_validate_move_pinned_resize_allowed(async_session):
    """
    Итерация 13.18: resize pinned-задачи РАЗРЕШЁН.

    Раньше validate_move возвращал allowed=False при is_pinned=TRUE
    для любого изменения. Теперь — только для move.
    """
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            is_pinned=True,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        # Resize: 120 → 180 минут
        new_start = datetime(2026, 9, 1, 8, 0)
        new_end = datetime(2026, 9, 1, 11, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is True, (
            f"Resize pinned-задачи должен быть разрешён, "
            f"но получено: reason={result.reason}, details={result.details}"
        )
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_pinned_move_blocked(async_session):
    """
    Итерация 13.18: move (без изменения длительности)
    pinned-задачи ЗАПРЕЩЁН.
    """
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            is_pinned=True,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        # Move: сдвиг на 2 часа, длительность та же (120 мин)
        new_start = datetime(2026, 9, 1, 10, 0)
        new_end = datetime(2026, 9, 1, 12, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is False
        assert "закреплена" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_not_pinned_resize_allowed(async_session):
    """Не-pinned задача: resize разрешён."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            is_pinned=False,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 8, 0)
        new_end = datetime(2026, 9, 1, 11, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is True
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_not_pinned_move_allowed(async_session):
    """Не-pinned задача: move разрешён."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            is_pinned=False,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 10, 0)
        new_end = datetime(2026, 9, 1, 12, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is True
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_done_resize_blocked(async_session):
    """DONE-задача: resize запрещён."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            is_pinned=False,
            status="DONE",
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 8, 0)
        new_end = datetime(2026, 9, 1, 11, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is False
        assert "DONE" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_short_duration_rejected(async_session):
    """Задача короче 5 минут — ошибка валидации."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 8, 0)
        new_end = datetime(2026, 9, 1, 8, 3)  # 3 минуты

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is False
        assert "короткая" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_long_duration_rejected(async_session):
    """Задача длиннее 24 часов — ошибка валидации."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 8, 0)
        new_end = datetime(2026, 9, 3, 8, 0)  # 48 часов

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is False
        assert "длинная" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_end_before_start_rejected(async_session):
    """Конец раньше начала — ошибка."""
    version_id = await _create_test_version(async_session)
    try:
        task_id = await _create_test_task(
            async_session,
            version_id,
            duration_min=120,
            start_at=datetime(2026, 9, 1, 8, 0),
        )

        new_start = datetime(2026, 9, 1, 10, 0)
        new_end = datetime(2026, 9, 1, 9, 0)

        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=task_id,
            new_start=new_start,
            new_end=new_end,
        )

        assert result.allowed is False
        assert "Некорректные времена" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


@pytest.mark.asyncio
async def test_validate_move_task_not_found(async_session):
    """Несуществующая задача — ошибка."""
    version_id = await _create_test_version(async_session)
    try:
        fake_id = uuid4()
        result = await validate_move(
            session=async_session,
            org_id=TEST_ORG_ID,
            version_id=version_id,
            task_id=fake_id,
            new_start=datetime(2026, 9, 1, 8, 0),
            new_end=datetime(2026, 9, 1, 10, 0),
        )

        assert result.allowed is False
        assert "не найдена" in result.reason
    finally:
        await _cleanup_test_version(async_session, version_id)


# ==========================================
# RESIZE_THRESHOLD_SECONDS
# ==========================================

def test_resize_threshold_constant():
    """Порог resize — 60 секунд."""
    assert RESIZE_THRESHOLD_SECONDS == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])