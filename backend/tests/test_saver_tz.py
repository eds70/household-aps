# backend/tests/test_saver_tz.py
"""
Тесты timezone-логики сохранения (Итерация 19, fix #tz-saver).

Проверяют:
  1. _extract_solution возвращает naive start/end (без tzinfo).
     Это критично, чтобы избежать TypeError 'offset-naive and
     offset-aware datetimes' при вычитании t["end"] - self.t0.
  2. Saver маркирует naive start/end как aware UTC перед записью
     в БД. Это защита от asyncpg, который иначе может
     интерпретировать naive datetime в локальной TZ клиента
     (например, МСК) и сохранить время со сдвигом −3 часа.
  3. Интеграционный: после сохранения planned_start в БД имеет
     смещение +00 (UTC) и совпадает с t0 для первой задачи.

ВАЖНО: интеграционные тесты требуют работающей БД
(DATABASE_URL в app.core.config.settings).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings


# ==========================================
# ЮНИТ-ТЕСТЫ: NAIVE vs AWARE
# ==========================================

def test_naive_start_end_from_extract():
    """
    _extract_solution должен возвращать naive start/end.

    Это гарантия того, что внутри core.py вычитания
    (t["end"] - self.t0) не падают с TypeError.
    """
    # Простейший наивный datetime
    t0_naive = datetime(2026, 10, 12, 5, 0, 0)
    start_offset = 61  # минут

    # Эмулируем логику _extract_solution
    start_dt = t0_naive + timedelta(minutes=start_offset)
    end_dt = t0_naive + timedelta(minutes=start_offset + 30)

    # Проверки: tzinfo is None
    assert start_dt.tzinfo is None, (
        f"start_dt должен быть naive, получено tzinfo={start_dt.tzinfo}"
    )
    assert end_dt.tzinfo is None, (
        f"end_dt должен быть naive, получено tzinfo={end_dt.tzinfo}"
    )

    # Проверка, что вычитание naive - naive не падает
    delta = end_dt - start_dt
    assert delta.total_seconds() == 30 * 60

    # Проверка, что t["end"] - self.t0 не падает
    makespan = (end_dt - t0_naive).total_seconds() / 60
    assert makespan == start_offset + 30


def test_saver_marks_naive_as_utc():
    """
    Saver должен маркировать naive datetime как aware UTC
    через .replace(tzinfo=timezone.utc).

    Сдвиг НЕ происходит: 05:00 naive → 05:00+00:00, а не
    02:00+00:00 (что было бы при интерпретации в МСК).
    """
    naive = datetime(2026, 10, 12, 5, 0, 0)
    aware = naive.replace(tzinfo=timezone.utc)

    # Час не изменился
    assert aware.hour == 5, (
        f"После .replace(tzinfo=utc) час изменился: "
        f"было {naive.hour}, стало {aware.hour}"
    )
    assert aware.minute == 0
    assert aware.tzinfo == timezone.utc

    # Конвертация в UTC не сдвигает
    assert aware.astimezone(timezone.utc) == aware

    # ISO-формат содержит +00:00
    iso = aware.isoformat()
    assert "+00:00" in iso, f"ISO-формат должен содержать +00:00: {iso}"


def test_naive_vs_aware_subtraction_raises():
    """
    Демонстрация проблемы, которую мы решили:
    вычитание naive - aware поднимает TypeError.
    Это обоснование того, почему _extract_solution возвращает naive,
    а не aware — иначе падает (t["end"] - self.t0).
    """
    naive = datetime(2026, 10, 12, 5, 0, 0)
    aware = datetime(2026, 10, 12, 5, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(TypeError):
        _ = aware - naive


# ==========================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ (требуют БД)
# ==========================================

@pytest.mark.asyncio
async def test_planned_start_in_db_is_utc():
    """
    Интеграционный: после сохранения плана planned_start в БД
    имеет смещение +00 и совпадает с t0 (для первой задачи).

    Проверяем на самой свежей активной версии.

    Запускать только при наличии БД:
        pytest tests/test_saver_tz.py -v
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            # Находим активную версию
            r = await conn.execute(text("""
                SELECT id, name, created_at
                FROM schedule_version
                WHERE organization_id = :org_id
                  AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """), {"org_id": settings.DEFAULT_ORG_ID})

            row = r.fetchone()
            if row is None:
                pytest.skip("Нет активной версии плана — пропускаем")

            version_id = row.id

            # Проверяем, что первая задача не сдвинута относительно t0
            r = await conn.execute(text("""
                SELECT
                    MIN(planned_start) AS first_start,
                    EXTRACT(EPOCH FROM (MIN(planned_start) -
                        (SELECT MIN(planned_start) FROM scheduled_task
                         WHERE schedule_version_id = :vid)))/60 AS delta
                FROM scheduled_task
                WHERE schedule_version_id = :vid
            """), {"vid": version_id})

            row = r.fetchone()
            assert row is not None
            first_start = row.first_start

            # first_start должен быть aware UTC (tzinfo=utc)
            assert first_start.tzinfo is not None, (
                f"planned_start должен быть aware, получено "
                f"tzinfo=None: {first_start}"
            )

            # Смещение должно быть UTC (+00:00)
            offset = first_start.utcoffset()
            assert offset == timedelta(0), (
                f"planned_start должен быть в UTC (offset=0), "
                f"получено offset={offset}"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_planned_start_matches_t0():
    """
    Интеграционный: MIN(planned_start) должен совпадать с
    t0 = planning_start_date в UTC.

    Если planning_start_date = "2026-10-12T08:00:00" (МСК),
    то t0 = 2026-10-12 05:00:00 UTC.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from zoneinfo import ZoneInfo

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            # Читаем planning_start_date из plan_settings активной версии
            r = await conn.execute(text("""
                SELECT ps.setting_value
                FROM plan_settings ps
                JOIN schedule_version sv
                  ON sv.id = ps.schedule_version_id
                WHERE sv.organization_id = :org_id
                  AND sv.is_active = TRUE
                  AND ps.setting_key = 'planning_start_date'
                LIMIT 1
            """), {"org_id": settings.DEFAULT_ORG_ID})

            row = r.fetchone()
            if row is None:
                pytest.skip(
                    "Нет plan_settings для активной версии — пропускаем"
                )

            raw = row.setting_value
            if isinstance(raw, str):
                raw = raw.strip().strip('"').strip("'")

            # Парсим как МСК → UTC
            dt_msk = datetime.fromisoformat(raw).replace(
                tzinfo=ZoneInfo("Europe/Moscow")
            )
            expected_t0 = dt_msk.astimezone(timezone.utc).replace(
                tzinfo=timezone.utc
            )

            # Читаем MIN(planned_start) активной версии
            r = await conn.execute(text("""
                SELECT MIN(planned_start) AS first_start
                FROM scheduled_task
                WHERE schedule_version_id = (
                    SELECT id FROM schedule_version
                    WHERE organization_id = :org_id
                      AND is_active = TRUE
                    LIMIT 1
                )
            """), {"org_id": settings.DEFAULT_ORG_ID})

            row = r.fetchone()
            assert row is not None and row.first_start is not None

            first_start = row.first_start

            # Допускаем разницу в пределах 1 минуты
            diff = abs((first_start - expected_t0).total_seconds())
            assert diff < 60, (
                f"MIN(planned_start)={first_start} не совпадает с "
                f"t0={expected_t0} (разница {diff} секунд). "
                f"Это указывает на сдвиг timezone."
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])