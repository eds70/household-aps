# backend/tests/test_calendar_postprocess_v2.py
from datetime import datetime, timedelta

from app.scheduler.calendar_postprocess import apply_calendar_postprocess


def _make_task(task_id, batch_id, op_id, start_dt, duration_min, eq_id, deps=None):
    """Хелпер для создания тестовой задачи."""
    end_dt = start_dt + timedelta(minutes=duration_min)
    return {
        "id": task_id,
        "batch_id": batch_id,
        "op_id": op_id,
        "operation_name": f"Op {op_id}",
        "start": start_dt,
        "end": end_dt,
        "duration_minutes": duration_min,
        "equipment_id": eq_id,
        "depends_on_task_ids": deps or [],
        "depends_on_op_ids": deps or [],
        "item_type": "task",
        "task_role": "LINE_FILL" if "fill" in op_id else "REACTOR_OP",
        "is_cooling_degraded": False,
        "parallel_group_id": None,
    }

def test_no_overlaps_after_postprocess():
    """
    Проверяет, что даже если на вход подать задачи с наложениями,
    постобработка разведет их так, чтобы overlaps_after == 0.
    """
    t0 = datetime(2026, 10, 12, 8, 0)  # Понедельник
    horizon = 30 * 24 * 60  # 30 дней

    # Одно рабочее окно в день: 08:00 - 16:00
    shifts = []
    for day in range(30):
        day_start = t0 + timedelta(days=day)
        # Пропускаем выходные (день 5 и 6)
        if day_start.weekday() in (5, 6):
            continue
        shifts.append({
            "starts_at": day_start,
            "ends_at": day_start + timedelta(hours=8),
            "is_working": True,
        })

    # Две задачи на одной линии, которые пересекаются на входе
    # Задача A: 10:00 - 14:00 (240 мин)
    # Задача B: 11:00 - 13:00 (120 мин)
    # Обе требуют LINE-1
    tasks = [
        _make_task("t1", "batch1", "fill_1", t0 + timedelta(hours=2), 240, "LINE-1"),
        _make_task("t2", "batch2", "fill_2", t0 + timedelta(hours=3), 120, "LINE-1"),
    ]

    result = apply_calendar_postprocess(
        tasks=tasks,
        calendar_events=[],
        shifts=shifts,
        t0=t0,
        horizon_minutes=horizon,
        allow_weekend_work=False,
        allow_interrupt_line_fill=True,
    )

    assert result["overlaps_after"] == 0, "Постобработка не должна оставлять наложений"

    # Задача B должна быть сдвинута после A
    t1_start = tasks[0]["start"]
    t1_end = tasks[0]["end"]
    t2_start = tasks[1]["start"]

    if t1_start < t2_start:
        assert t1_end <= t2_start, "Задачи не должны пересекаться"
    else:
        assert tasks[1]["end"] <= t1_start, "Задачи не должны пересекаться"

def test_dependency_restoration():
    """
    Проверяет, что третий проход восстанавливает зависимости.
    Если задача B зависит от A, но постобработка поставила B раньше A,
    она должна сдвинуть B.
    """
    t0 = datetime(2026, 10, 12, 8, 0)
    horizon = 30 * 24 * 60

    shifts = [{"starts_at": t0, "ends_at": t0 + timedelta(hours=8), "is_working": True}]

    # A: 08:00 - 10:00 (120 мин) на REACTOR-1
    # B: 09:00 - 11:00 (120 мин) на REACTOR-1, зависит от A
    tasks = [
        _make_task("t1", "batch1", "op_a", t0, 120, "REACTOR-1"),
        _make_task("t2", "batch1", "op_b", t0 + timedelta(hours=1), 120, "REACTOR-1", deps=["op_a"]),
    ]

    result = apply_calendar_postprocess(
        tasks=tasks,
        calendar_events=[],
        shifts=shifts,
        t0=t0,
        horizon_minutes=horizon,
        allow_weekend_work=False,
        allow_interrupt_line_fill=True,
    )

    assert result["overlaps_after"] == 0, "Не должно быть наложений"
    assert result["dependency_violations"] == 0, "Не должно быть нарушений зависимостей"

    a_end = tasks[0]["end"]
    b_start = tasks[1]["start"]
    assert a_end <= b_start, "Задача B должна начинаться после окончания A"

def test_shift_to_next_day():
    """
    Если задача не влезает в текущий день (окно 8 часов), она должна перенестись
    на следующий рабочий день.
    """
    t0 = datetime(2026, 10, 12, 8, 0)  # Пн
    horizon = 30 * 24 * 60

    # Делаем окна по 12 часов, чтобы 10-часовая задача влезла
    shifts = []
    for day in range(5):
        day_start = t0 + timedelta(days=day)
        shifts.append({"starts_at": day_start, "ends_at": day_start + timedelta(hours=12), "is_working": True})

    # Задача 1: 10 часов (600 мин) на LINE-1. Начинается в Пн.
    # Задача 2: 10 часов (600 мин) на LINE-1. Начинается тоже в Пн, но не влезает в остаток Пн.
    tasks = [
        _make_task("t1", "batch1", "fill_1", t0, 600, "LINE-1"),
        _make_task("t2", "batch2", "fill_2", t0 + timedelta(hours=1), 600, "LINE-1"),
    ]

    result = apply_calendar_postprocess(
        tasks=tasks,
        calendar_events=[],
        shifts=shifts,
        t0=t0,
        horizon_minutes=horizon,
        allow_weekend_work=False,
        allow_interrupt_line_fill=True,
    )

    # Первая задача должна остаться в Пн (08:00)
    assert tasks[0]["start"] == t0, "Первая задача должна остаться в Пн"

    # Вторая задача должна уехать на Вт (t0 + 1 день), т.к. в Пн остаток всего 2 часа (720 - 600)
    expected_start = t0 + timedelta(days=1)
    assert tasks[1]["start"] >= expected_start, "Вторая задача должна уехать на следующий день"