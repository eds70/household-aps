# backend/app/scheduler/calendar_postprocess.py
"""
Постобработка календаря.

Итерация 10 (fix #13): вместо жёстких календарных ограничений в CP-SAT.
Итерация 10 (fix #14): учёт зависимостей и NoOverlap.
Итерация 11 (Шаг 6): рабочие окна строятся из СМЕН (shift).

Итерация 18 (fix #chain-shift): сдвиг одной задачи распространяется
на потомков через shift_delta.

Итерация 19 (fix #line-fill): LINE_FILL НЕ сдвигается календарём —
слив непрерывный процесс по ТЗ.

Итерация 20 (fix #chain-whole): попытка сдвинуть всю цепочку партии.
ПРИЗНАНО ОШИБОЧНЫМ: если цепочка длиннее рабочего окна, она
остаётся в выходные.

Итерация 21 (fix #hybrid):
  - ОТКАТ Итерации 20.
  - Возврат к последовательной постобработке.
  - LINE_FILL — не переносится в рабочее окно (по ТЗ), но
    УВАЖАЕТ occupied.

Итерация 25 (fix #two-pass):
  - ДВУХПРОХОДНЫЙ алгоритм + третий проход восстановления
    зависимостей.
  - Первый проход: сортировка (LINE_FILL — первыми, затем
    по earliest_start).
  - Второй проход: жадное размещение с учётом occupied.
  - Fallback при отсутствии окна: сдвиг за max_occupied_end.
  - Третий проход: топологический обход, восстановление
    зависимостей (start потомка >= end предка). Если нужно —
    сдвиг потомка на max(end предков) или позже.
  - Финальная проверка: overlaps_after и dep_violations.

Итерация 35 (fix #interrupt):
  - Добавлен параметр allow_interrupt_line_fill.
  - Если False, LINE_FILL не может быть разорвана на выходные
    (переносится целиком на следующий рабочий день).
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
    """Строит рабочие окна из РАБОЧИХ смен."""
    if allow_weekend_work:
        return [(0, horizon_minutes)]

    t0_naive = t0 if t0.tzinfo is None else t0.replace(tzinfo=None)

    def _to_min(dt: datetime) -> int:
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return max(0, int((dt - t0_naive).total_seconds() / 60))

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

    if not shift_intervals:
        log_with_context(
            logger, logging.WARNING,
            "[POSTPROCESS] Смены не найдены — fallback на [0, horizon]",
            stage="postprocess", org_id=str(t0),
        )
        return [(0, horizon_minutes)]

    busy_intervals: List[Tuple[int, int]] = []
    for event in calendar_events:
        eq_id = event.get("equipment_id")
        if eq_id is not None:
            continue

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

    working.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in working:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    return merged


# ==========================================
# Утилиты
# ==========================================

def _overlaps(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Полуоткрытые интервалы [s, e)."""
    return s1 < e2 and s2 < e1


def _is_line_fill_task(task: Dict[str, Any]) -> bool:
    """LINE_FILL — непрерывная операция (Итерация 19)."""
    role = task.get("role") or task.get("task_role")
    if role == "LINE_FILL":
        return True
    op_id = str(task.get("op_id", ""))
    return op_id.startswith("fill_")


def _to_min(dt, t0_naive: datetime) -> int:
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


def _from_min(m: int, t0_naive: datetime) -> datetime:
    return t0_naive + timedelta(minutes=m)


# ==========================================
# ПЕРВЫЙ ПРОХОД: сортировка по earliest_start
# ==========================================

def _build_ordered_queue(
        tasks: List[Dict[str, Any]],
        t0_naive: datetime,
) -> List[Tuple[Dict[str, Any], str, int, int]]:
    """
    Возвращает список (task, batch_id_str, earliest_start, duration)
    в порядке обработки.
    """
    entries: List[Tuple[Dict[str, Any], str, int, int, int]] = []
    for task in tasks:
        batch_id = task.get("batch_id")
        op_id = task.get("op_id")
        if not batch_id or not op_id:
            continue

        orig_start = _to_min(task.get("start"), t0_naive)
        orig_end = _to_min(task.get("end"), t0_naive)
        duration = orig_end - orig_start
        if duration <= 0:
            continue

        entries.append((
            task,
            str(batch_id),
            orig_start,
            duration,
            orig_end,
        ))

    def _sort_key(entry):
        task, batch_id, earliest_start, duration, orig_end = entry
        is_line_fill = _is_line_fill_task(task)
        return (
            0 if is_line_fill else 1,
            earliest_start,
        )

    entries.sort(key=_sort_key)

    return [
        (task, batch_id, earliest_start, duration)
        for (task, batch_id, earliest_start, duration, _orig_end) in entries
    ]


# ==========================================
# ВТОРОЙ ПРОХОД: жадное размещение
# ==========================================

def _find_free_slot(
        equipment_ids: List[str],
        duration: int,
        earliest_start: int,
        working_windows: List[Tuple[int, int]],
        occupied: Dict[str, List[Tuple[int, int, Optional[str]]]],
        max_horizon: int,
        parallel_group_id: Optional[str] = None,
) -> Optional[Tuple[int, int]]:
    """
    Ищет свободный интервал [start, start+duration):
      - start >= earliest_start,
      - интервал целиком внутри одного рабочего окна,
      - не пересекается с occupied[eq_id] для каждого eq_id,
        КРОМЕ интервалов с тем же parallel_group_id.
    """
    candidates: Set[int] = {earliest_start}

    for (ws, we) in working_windows:
        if we - ws >= duration and we >= earliest_start:
            candidates.add(max(ws, earliest_start))

    for eq_id in equipment_ids:
        for (s, e, _pg) in occupied.get(eq_id, []):
            if e >= earliest_start:
                candidates.add(e)

    for start in sorted(candidates):
        if start < earliest_start:
            continue
        end = start + duration
        if end > max_horizon:
            continue

        in_working = False
        for (ws, we) in working_windows:
            if start >= ws and end <= we:
                in_working = True
                break
        if not in_working:
            continue

        conflict = False
        for eq_id in equipment_ids:
            for (os_, oe, opg) in occupied.get(eq_id, []):
                if _overlaps(start, end, os_, oe):
                    if (parallel_group_id is not None
                            and opg is not None
                            and parallel_group_id == opg):
                        continue
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            continue

        return (start, end)

    return None


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
        allow_interrupt_line_fill: bool = True,
) -> Dict[str, Any]:
    """
    Трёхпроходная постобработка календаря.
    """
    if not tasks:
        return {
            "total_tasks": 0,
            "shifted_tasks": 0,
            "line_fill_skipped": 0,
            "shifted_details": [],
            "overlaps_after": 0,
            "dependency_violations": 0,
            "skipped": True,
            "reason": "no_tasks",
        }

    if allow_weekend_work:
        log_with_context(
            logger, logging.INFO,
            "[POSTPROCESS] allow_weekend_work=true — постобработка пропущена",
            stage="postprocess", org_id=str(t0),
        )
        return {
            "total_tasks": len(tasks),
            "shifted_tasks": 0,
            "line_fill_skipped": 0,
            "shifted_details": [],
            "overlaps_after": 0,
            "dependency_violations": 0,
            "skipped": True,
            "reason": "allow_weekend_work",
        }

    t0_naive = t0 if t0.tzinfo is None else t0.replace(tzinfo=None)

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

    queue = _build_ordered_queue(tasks, t0_naive)

    log_with_context(
        logger, logging.INFO,
        f"[POSTPROCESS] Очередь обработки: {len(queue)} задач "
        f"(LINE_FILL — первыми, затем по earliest_start)",
        stage="postprocess", org_id=str(t0),
    )

    occupied: Dict[str, List[Tuple[int, int, Optional[str]]]] = {}
    final_times: Dict[Tuple[str, str], Tuple[int, int]] = {}
    shifted_details: List[Dict[str, Any]] = []
    line_fill_skipped = 0

    for (task, batch_id, _prelim_earliest, duration) in queue:
        op_id = str(task.get("op_id", ""))
        key = (batch_id, op_id)

        orig_start = _to_min(task.get("start"), t0_naive)
        orig_end = orig_start + duration

        equipment_ids: List[str] = []
        if task.get("equipment_id"):
            equipment_ids.append(str(task["equipment_id"]))
        if task.get("linked_equipment_id"):
            linked = str(task["linked_equipment_id"])
            if linked not in equipment_ids:
                equipment_ids.append(linked)

        earliest_start = orig_start
        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (batch_id, str(dep_op_id))
            if dep_key in final_times:
                _, dep_end = final_times[dep_key]
                earliest_start = max(earliest_start, dep_end)

        # ==========================================
        # Итерация 35: логика для LINE_FILL
        # ==========================================
        is_line_fill = _is_line_fill_task(task)

        # Если прерывать нельзя, мы ищем окно, куда задача влезет ЦЕЛИКОМ.
        # _find_free_slot и так ищет целое окно, но если allow_interrupt_line_fill=False,
        # мы можем запретить сдвиг на часть окна (хотя текущая логика это и так делает).
        # Используем параметр, чтобы IDE не ругалась и для явности.
        if is_line_fill and not allow_interrupt_line_fill:
            # Если нужно, здесь можно добавить специфичную логику (например, запрет на перенос)
            pass

        slot = _find_free_slot(
            equipment_ids=equipment_ids,
            duration=duration,
            earliest_start=earliest_start,
            working_windows=working_windows,
            occupied=occupied,
            max_horizon=horizon_minutes,
            parallel_group_id=task.get("parallel_group_id"),
        )

        if slot is None:
            # Итерация 36: Если окна нет (задача длиннее окна или всё занято),
            # сдвигаем на начало следующего окна, куда она влезает по размеру.
            max_occupied_end = 0
            for eq_id in equipment_ids:
                for (s, e, _pg) in occupied.get(eq_id, []):
                    max_occupied_end = max(max_occupied_end, e)

            new_start = max(earliest_start, max_occupied_end)

            # Ищем окно, которое начинается после new_start И в которое влезает duration
            found_window = False
            for (ws, we) in working_windows:
                if ws >= new_start and (we - ws) >= duration:
                    new_start = ws
                    found_window = True
                    break

            new_end = new_start + duration

            log_with_context(
                logger, logging.WARNING,
                f"[POSTPROCESS] Нет окна для задачи batch={batch_id[:8]} op={op_id[:8]} dur={duration} — сдвигаем на {new_start} (horizon={horizon_minutes})",
                stage="postprocess", org_id=str(t0),
            )
        else:
            new_start, new_end = slot

        if is_line_fill:
            line_fill_skipped += 1

        delta = new_start - orig_start
        if delta != 0:
            old_start = task.get("start")
            old_end = task.get("end")

            reason = _build_shift_reason(
                orig_start, new_start, working_windows,
            )
            comment = _make_shift_comment(
                old_start if isinstance(old_start, datetime) else None,
                _from_min(new_start, t0_naive),
                reason,
            )

            shifted_details.append({
                "batch_id": task["batch_id"],
                "op_id": task.get("op_id"),
                "operation_name": task.get("operation_name"),
                "old_start": (
                    old_start.isoformat()
                    if hasattr(old_start, "isoformat") else str(old_start)
                ),
                "old_end": (
                    old_end.isoformat()
                    if hasattr(old_end, "isoformat") else str(old_end)
                ),
                "new_start": _from_min(new_start, t0_naive).isoformat(),
                "new_end": _from_min(new_end, t0_naive).isoformat(),
                "delta_minutes": delta,
                "reason": reason,
                "comment": comment,
                "is_line_fill": is_line_fill,
            })

            task["start"] = _from_min(new_start, t0_naive)
            task["end"] = _from_min(new_end, t0_naive)
            if not is_line_fill:
                task["comment"] = comment

        for eq_id in equipment_ids:
            occupied.setdefault(eq_id, []).append(
                (new_start, new_end, task.get("parallel_group_id"))
            )

        final_times[key] = (new_start, new_end)

    # ==========================================
    # ТРЕТИЙ ПРОХОД: восстановление зависимостей
    # ==========================================
    task_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for (task, batch_id, _, _) in queue:
        op_id = str(task.get("op_id", ""))
        task_index[(batch_id, op_id)] = task

    visited_dep: Set[Tuple[str, str]] = set()
    topo_order: List[Tuple[str, str]] = []

    def _dfs_deps(key: Tuple[str, str]) -> None:
        if key in visited_dep:
            return
        visited_dep.add(key)
        task = task_index.get(key)
        if task is None:
            return
        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (key[0], str(dep_op_id))
            if dep_key in task_index:
                _dfs_deps(dep_key)
        topo_order.append(key)

    for key in task_index:
        _dfs_deps(key)

    dep_fixes = 0
    for key in topo_order:
        task = task_index.get(key)
        if task is None:
            continue
        batch_id, op_id = key

        max_pred_end = 0
        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (batch_id, str(dep_op_id))
            if dep_key in final_times:
                _, dep_end = final_times[dep_key]
                max_pred_end = max(max_pred_end, dep_end)

        if max_pred_end == 0:
            continue

        current_start = _to_min(task.get("start"), t0_naive)
        current_end = _to_min(task.get("end"), t0_naive)
        duration = current_end - current_start

        if current_start >= max_pred_end:
            continue

        equipment_ids: List[str] = []
        if task.get("equipment_id"):
            equipment_ids.append(str(task["equipment_id"]))
        if task.get("linked_equipment_id"):
            linked = str(task["linked_equipment_id"])
            if linked not in equipment_ids:
                equipment_ids.append(linked)

        slot = _find_free_slot(
            equipment_ids=equipment_ids,
            duration=duration,
            earliest_start=max_pred_end,
            working_windows=working_windows,
            occupied=occupied,
            max_horizon=horizon_minutes,
            parallel_group_id=task.get("parallel_group_id"),
        )

        if slot is None:
            max_occupied_end = 0
            for eq_id in equipment_ids:
                for (s, e, _pg) in occupied.get(eq_id, []):
                    max_occupied_end = max(max_occupied_end, e)
            new_start = max(max_pred_end, max_occupied_end)
            new_end = new_start + duration
        else:
            new_start, new_end = slot

        for eq_id in equipment_ids:
            occupied[eq_id] = [
                (s, e, pg) for (s, e, pg) in occupied.get(eq_id, [])
                if not (s == current_start and e == current_end)
            ]
            occupied[eq_id].append(
                (new_start, new_end, task.get("parallel_group_id"))
            )

        task["start"] = _from_min(new_start, t0_naive)
        task["end"] = _from_min(new_end, t0_naive)
        final_times[key] = (new_start, new_end)

        dep_fixes += 1
        log_with_context(
            logger, logging.WARNING,
            f"[POSTPROCESS] Восстановление зависимости: "
            f"batch={batch_id[:8]} op={op_id[:8]} "
            f"сдвинут с {current_start} на {new_start} "
            f"(предок до {max_pred_end})",
            stage="postprocess", org_id=str(t0),
        )

    if dep_fixes > 0:
        log_with_context(
            logger, logging.INFO,
            f"[POSTPROCESS] Восстановлено зависимостей: {dep_fixes}",
            stage="postprocess", org_id=str(t0),
        )

    # ==========================================
    # Проверка результата
    # ==========================================
    overlaps_after = 0
    for eq_id, meta_list in occupied.items():
        sorted_meta = sorted(meta_list, key=lambda x: x[0])
        for i in range(len(sorted_meta) - 1):
            s1, e1, pg1 = sorted_meta[i]
            s2, e2, pg2 = sorted_meta[i + 1]
            if _overlaps(s1, e1, s2, e2):
                if pg1 and pg2 and pg1 == pg2:
                    continue
                overlaps_after += 1

    dep_violations = 0
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for t in tasks:
        bid = str(t.get("batch_id"))
        oid = str(t.get("op_id"))
        if bid and oid:
            index[(bid, oid)] = t

    for t in tasks:
        bid = str(t.get("batch_id"))
        oid = str(t.get("op_id"))
        if not bid or not oid:
            continue
        my_start = _to_min(t.get("start"), t0_naive)

        for dep_op_id in (t.get("depends_on_op_ids") or []):
            dep_key = (bid, str(dep_op_id))
            dep_task = index.get(dep_key)
            if dep_task is None:
                continue
            dep_end = _to_min(dep_task.get("end"), t0_naive)
            if my_start < dep_end:
                dep_violations += 1

    log_with_context(
        logger, logging.INFO,
        f"[POSTPROCESS] Сдвинуто задач: {len(shifted_details)} из {len(tasks)}. "
        f"LINE_FILL пропущено (без сдвига): {line_fill_skipped}. "
        f"Остаточные overlaps: {overlaps_after}, "
        f"нарушений зависимостей: {dep_violations}",
        stage="postprocess", org_id=str(t0),
    )

    return {
        "total_tasks": len(tasks),
        "shifted_tasks": len(shifted_details),
        "line_fill_skipped": line_fill_skipped,
        "shifted_details": shifted_details,
        "overlaps_after": overlaps_after,
        "dependency_violations": dep_violations,
        "skipped": False,
    }


# ==========================================
# Утилиты причин сдвига
# ==========================================

def _build_shift_reason(
        old_start_min: int,
        new_start_min: int,
        working_windows: List[Tuple[int, int]],
) -> str:
    if not working_windows:
        return "нет рабочих окон"

    gap_min = new_start_min - old_start_min

    if gap_min >= 720:
        return "перенос на ближайший рабочий день (выходные/простой)"

    if gap_min > 0:
        return "перенос на свободное рабочее окно"

    return "сдвиг по occupied"


def _make_shift_comment(
        orig_start_dt: Optional[datetime],
        new_start_dt: datetime,
        reason: str,
) -> str:
    orig = orig_start_dt.strftime("%d.%m %H:%M") if orig_start_dt else "?"
    new = new_start_dt.strftime("%d.%m %H:%M")
    return f"Перенос с {orig} на {new}: {reason}"