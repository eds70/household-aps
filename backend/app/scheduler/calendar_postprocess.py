# backend/app/scheduler/calendar_postprocess.py
"""
Постобработка календаря.

Итерация 10 (fix #13): вместо жёстких календарных ограничений в CP-SAT.
Итерация 10 (fix #14): учёт зависимостей и NoOverlap.
Итерация 11 (Шаг 6): рабочие окна строятся из СМЕН (shift),
а не из WEEKEND-событий. Это позволяет учитывать режимы 1x8/3x8/2x12.

Плюс новый флаг allow_weekend_work:
  - false (по умолчанию): постпроцессор сдвигает задачи с выходных.
  - true: постпроцессор возвращает пустой результат (нечего сдвигать).

Алгоритм:
  1. Строим рабочие окна = рабочие смены минус события календаря.
  2. Топологически сортируем задачи по зависимостям (depends_on_op_ids).
  3. Для каждой задачи в порядке:
     a. earliest_start = max(end всех зависимостей, 0).
     b. Находим ближайшее рабочее окно >= earliest_start, где
        задача не пересекается с уже размещёнными задачами
        на том же оборудовании.
     c. Ставим задачу в это окно.
  4. Возвращаем статистику.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# Построение рабочих окон из смен
# ==========================================

def _build_working_windows_from_shifts(
        shifts: List[Dict],
        calendar_events: List[Dict],
        t0: datetime,
        horizon_minutes: int,
        allow_weekend_work: bool = False,
) -> List[Tuple[int, int]]:
    """
    Строит рабочие окна из РАБОЧИХ смен.

    Если allow_weekend_work = True — возвращает [0, horizon]
    (нет ограничений — задачи могут быть где угодно).

    Логика:
      1. Собираем интервалы рабочих смен (is_working=TRUE).
      2. Вычитаем события календаря (WEEKEND, REPAIR).
      3. Инвертируем = рабочие окна.
    """
    if allow_weekend_work:
        # Выходные разрешены — нет ограничений
        return [(0, horizon_minutes)]

    t0_naive = t0 if t0.tzinfo is None else t0.replace(tzinfo=None)

    def _to_min(dt: datetime) -> int:
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return max(0, int((dt - t0_naive).total_seconds() / 60))

    # ==========================================
    # 1. Интервалы рабочих смен
    # ==========================================
    shift_intervals: List[Tuple[int, int]] = []
    for s in shifts:
        if not s.get("is_working"):
            continue

        starts_at = s.get("starts_at")
        ends_at = s.get("ends_at")
        if starts_at is None or ends_at is None:
            continue

        start_min = _to_min(starts_at)
        end_min = _to_min(ends_at)

        if end_min > start_min and start_min < horizon_minutes:
            shift_intervals.append(
                (start_min, min(end_min, horizon_minutes))
            )

    # Fallback: если смен нет — [0, horizon]
    if not shift_intervals:
        log_with_context(
            logger, logging.WARNING,
            "[POSTPROCESS] Смены не найдены — fallback на [0, horizon]",
            stage="postprocess", org_id=str(t0),
        )
        return [(0, horizon_minutes)]

    # ==========================================
    # 2. Занятые интервалы (общие события: WEEKEND)
    # ==========================================
    busy_intervals: List[Tuple[int, int]] = []
    for event in calendar_events:
        eq_id = event.get("equipment_id")
        if eq_id is not None:
            continue  # ремонт оборудования не влияет на общий календарь

        starts_at = event.get("starts_at")
        ends_at = event.get("ends_at")
        if starts_at is None or ends_at is None:
            continue

        start_min = _to_min(starts_at)
        end_min = _to_min(ends_at)

        if end_min > start_min:
            busy_intervals.append(
                (max(0, start_min), min(horizon_minutes, end_min))
            )

    # ==========================================
    # 3. Рабочие окна = shift_intervals \ busy_intervals
    # ==========================================
    working: List[Tuple[int, int]] = []
    for (ws, we) in shift_intervals:
        overlapping = [
            (max(ws, bs), min(we, be))
            for (bs, be) in busy_intervals
            if bs < we and be > ws
        ]
        overlapping.sort()

        cursor = ws
        for (bs, be) in overlapping:
            if bs > cursor:
                working.append((cursor, bs))
            cursor = max(cursor, be)
        if cursor < we:
            working.append((cursor, we))

    # Объединяем смежные окна
    working.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in working:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    return merged


# ==========================================
# Топологическая сортировка
# ==========================================

def _topological_sort(
        tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Топологическая сортировка задач по зависимостям.

    Задача зависит от других через `depends_on_op_ids`.
    Ключ задачи: (batch_id, op_id).

    Возвращает список задач в порядке, где predecessors идут раньше.
    """
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for t in tasks:
        batch_id = t.get("batch_id")
        op_id = t.get("op_id")
        if not batch_id or not op_id:
            continue
        key = (str(batch_id), str(op_id))
        index[key] = t

    deps: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for t in tasks:
        batch_id = t.get("batch_id")
        op_id = t.get("op_id")
        if not batch_id or not op_id:
            continue
        key = (str(batch_id), str(op_id))
        dep_op_ids = t.get("depends_on_op_ids", []) or []
        dep_keys = [(str(batch_id), str(dep_id)) for dep_id in dep_op_ids]
        deps[key] = [dk for dk in dep_keys if dk in index]

    visited: Set[Tuple[str, str]] = set()
    in_stack: Set[Tuple[str, str]] = set()
    result: List[Dict[str, Any]] = []

    def visit(key: Tuple[str, str]) -> None:
        if key in visited or key in in_stack:
            return
        in_stack.add(key)
        for dep_key in deps.get(key, []):
            visit(dep_key)
        in_stack.discard(key)
        visited.add(key)
        result.append(index[key])

    for t in tasks:
        batch_id = t.get("batch_id")
        op_id = t.get("op_id")
        if not batch_id or not op_id:
            continue
        visit((str(batch_id), str(op_id)))

    # На случай, если какие-то задачи не попали (без batch_id) —
    # добавляем их в конец
    for t in tasks:
        if t not in result:
            result.append(t)

    return result


# ==========================================
# Пересечение интервалов
# ==========================================

def _overlaps(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Полуоткрытые интервалы [s, e). Задачи на стыке не пересекаются."""
    return s1 < e2 and s2 < e1


# ==========================================
# Основная функция
# ==========================================

def apply_calendar_postprocess(
        tasks: List[Dict[str, Any]],
        calendar_events: List[Dict],
        shifts: List[Dict],
        t0: datetime,
        horizon_minutes: int,
        allow_weekend_work: bool = False,
) -> Dict[str, Any]:
    """
    Сдвигает задачи в рабочие окна с учётом зависимостей и NoOverlap.

    Если allow_weekend_work = True — постпроцессор пропускается.

    Args:
        tasks: список задач (мутируется).
        calendar_events: события календаря (выходные, ремонты).
        shifts: список смен из таблицы shift.
        t0: начало планирования.
        horizon_minutes: горизонт.
        allow_weekend_work: разрешена ли работа в выходные.

    Returns:
        Статистика.
    """
    if not tasks:
        return {
            "total_tasks": 0,
            "shifted_tasks": 0,
            "shifted_details": [],
            "overlaps_after": 0,
            "dependency_violations": 0,
            "skipped": True,
            "reason": "no_tasks",
        }

    # ==========================================
    # Если работа в выходные разрешена — пропускаем постобработку
    # ==========================================
    if allow_weekend_work:
        log_with_context(
            logger, logging.INFO,
            "[POSTPROCESS] allow_weekend_work=true — постобработка пропущена",
            stage="postprocess", org_id=str(t0),
        )
        return {
            "total_tasks": len(tasks),
            "shifted_tasks": 0,
            "shifted_details": [],
            "overlaps_after": 0,
            "dependency_violations": 0,
            "skipped": True,
            "reason": "allow_weekend_work",
        }

    # ==========================================
    # Строим рабочие окна из смен
    # ==========================================
    working_windows = _build_working_windows_from_shifts(
        shifts=shifts,
        calendar_events=calendar_events,
        t0=t0,
        horizon_minutes=horizon_minutes,
        allow_weekend_work=False,
    )

    log_with_context(
        logger, logging.INFO,
        f"[POSTPROCESS] Рабочих окон: {len(working_windows)}. "
        f"Первые 3: {working_windows[:3]}",
        stage="postprocess", org_id=str(t0),
    )

    # ==========================================
    # Топологическая сортировка
    # ==========================================
    tasks_sorted = _topological_sort(tasks)

    log_with_context(
        logger, logging.INFO,
        f"[POSTPROCESS] Топологическая сортировка: {len(tasks_sorted)} задач",
        stage="postprocess", org_id=str(t0),
    )

    t0_naive = t0 if t0.tzinfo is None else t0.replace(tzinfo=None)

    def to_min(dt) -> int:
        if dt is None:
            return 0
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return 0
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return max(0, int((dt - t0_naive).total_seconds() / 60))

    def from_min(m: int) -> datetime:
        return t0_naive + timedelta(minutes=m)

    # ==========================================
    # Состояние: занятые интервалы по оборудованию
    # ==========================================
    occupied: Dict[str, List[Tuple[int, int]]] = {}
    final_times: Dict[Tuple[str, str], Tuple[int, int]] = {}

    shifted_details: List[Dict[str, Any]] = []

    def _find_free_slot(
            equipment_ids: List[str],
            duration: int,
            earliest_start: int,
            max_horizon: int,
    ) -> Optional[int]:
        """Ищет ближайшее время >= earliest_start для размещения задачи."""
        # Кандидаты: earliest_start + концы всех занятых задач
        candidates: Set[int] = {earliest_start}
        for eq_id in equipment_ids:
            for (s, e) in occupied.get(eq_id, []):
                if e >= earliest_start:
                    candidates.add(e)

        # Кандидаты: начала рабочих окон (>= earliest_start)
        for (ws, we) in working_windows:
            if we - ws >= duration and we >= earliest_start:
                candidates.add(max(ws, earliest_start))

        for start in sorted(candidates):
            if start < earliest_start:
                continue

            end = start + duration
            if end > max_horizon:
                continue

            # Проверка 1: попадает в рабочее окно?
            in_working = False
            for (ws, we) in working_windows:
                if start >= ws and end <= we:
                    in_working = True
                    break
            if not in_working:
                continue

            # Проверка 2: не пересекается с занятыми?
            conflict = False
            for eq_id in equipment_ids:
                for (os_, oe) in occupied.get(eq_id, []):
                    if _overlaps(start, end, os_, oe):
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                continue

            return start

        return None

    def _occupy(equipment_ids: List[str], start: int, end: int) -> None:
        """Регистрирует задачу как занятую на указанных оборудованиях."""
        for eq_id in equipment_ids:
            occupied.setdefault(eq_id, []).append((start, end))

    # ==========================================
    # Основной цикл
    # ==========================================
    for task in tasks_sorted:
        start_min = to_min(task.get("start"))
        end_min = to_min(task.get("end"))
        duration = end_min - start_min

        if duration <= 0:
            continue

        # Оборудования задачи
        equipment_ids: List[str] = []
        if task.get("equipment_id"):
            equipment_ids.append(str(task["equipment_id"]))
        if task.get("linked_equipment_id"):
            linked = str(task["linked_equipment_id"])
            if linked not in equipment_ids:
                equipment_ids.append(linked)

        # ==========================================
        # Earliest start с учётом зависимостей
        # ==========================================
        earliest_start = 0
        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (str(task["batch_id"]), str(dep_op_id))
            if dep_key in final_times:
                _, dep_end = final_times[dep_key]
                earliest_start = max(earliest_start, dep_end)

        # ==========================================
        # Ищем свободное место
        # ==========================================
        new_start = _find_free_slot(
            equipment_ids=equipment_ids,
            duration=duration,
            earliest_start=earliest_start,
            max_horizon=horizon_minutes,
        )

        if new_start is None:
            log_with_context(
                logger, logging.WARNING,
                f"[POSTPROCESS] НЕ найдено окно для задачи "
                f"batch={str(task.get('batch_id', ''))[:8]} "
                f"op={str(task.get('op_id', ''))[:8]} "
                f"duration={duration} earliest={earliest_start}",
                stage="postprocess", org_id=str(t0),
            )
            _occupy(equipment_ids, start_min, end_min)
            final_times[(str(task["batch_id"]), str(task["op_id"]))] = (
                start_min, end_min
            )
            continue

        new_end = new_start + duration

        # ==========================================
        # Сдвиг (если нужно)
        # ==========================================
        if new_start != start_min:
            old_start = task.get("start")
            old_end = task.get("end")

            shifted_details.append({
                "batch_id": task["batch_id"],
                "op_id": task["op_id"],
                "operation_name": task.get("operation_name"),
                "old_start": old_start.isoformat() if hasattr(old_start, "isoformat") else str(old_start),
                "old_end": old_end.isoformat() if hasattr(old_end, "isoformat") else str(old_end),
                "new_start": from_min(new_start).isoformat(),
                "new_end": from_min(new_end).isoformat(),
                "delta_minutes": new_start - start_min,
            })

            task["start"] = from_min(new_start)
            task["end"] = from_min(new_end)

        # ==========================================
        # Регистрируем
        # ==========================================
        _occupy(equipment_ids, new_start, new_end)
        final_times[(str(task["batch_id"]), str(task["op_id"]))] = (
            new_start, new_end
        )

    # ==========================================
    # Проверка результата
    # ==========================================
    overlaps_after = 0
    for eq_id, intervals in occupied.items():
        sorted_i = sorted(intervals)
        for i in range(len(sorted_i) - 1):
            if _overlaps(
                    sorted_i[i][0], sorted_i[i][1],
                    sorted_i[i + 1][0], sorted_i[i + 1][1],
            ):
                overlaps_after += 1

    dep_violations = 0
    for task in tasks_sorted:
        batch_id = task.get("batch_id")
        op_id = task.get("op_id")
        if not batch_id or not op_id:
            continue
        key = (str(batch_id), str(op_id))
        if key not in final_times:
            continue
        my_start, _ = final_times[key]

        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (str(batch_id), str(dep_op_id))
            if dep_key in final_times:
                _, dep_end = final_times[dep_key]
                if my_start < dep_end:
                    dep_violations += 1

    log_with_context(
        logger, logging.INFO,
        f"[POSTPROCESS] Сдвинуто: {len(shifted_details)} из {len(tasks)}. "
        f"Остаточные overlaps: {overlaps_after}, "
        f"нарушений зависимостей: {dep_violations}",
        stage="postprocess", org_id=str(t0),
    )

    return {
        "total_tasks": len(tasks),
        "shifted_tasks": len(shifted_details),
        "shifted_details": shifted_details[:20],
        "overlaps_after": overlaps_after,
        "dependency_violations": dep_violations,
        "skipped": False,
    }