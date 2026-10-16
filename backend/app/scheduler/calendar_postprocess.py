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
остаётся в выходные (см. REACTOR_OP в сб/вс).

Итерация 21 (fix #hybrid):
  - ОТКАТ Итерации 20.
  - Возврат к последовательной постобработке (как в Итерации 18).
  - Правило:
      1. LINE_FILL — не сдвигается (Итерация 19).
      2. Остальные (REACTOR_OP, WASH, TANK_TRANSFER) — сдвигаются
         в ближайшее рабочее окно, если операция не влезает в
         текущее окно.
  - Цепочка партии МОЖЕТ РАЗРЫВАТЬСЯ между операциями: если
    операция не влезает, следующая ждёт следующей смены.
  - earliest_start = max(end(предков), orig_start + delta_предков).
  - Комментарий пишется каждой сдвинутой задаче.

Итерация 21 (fix #line-fill-nooverlap):
  - LINE_FILL по-прежнему НЕ переносится в рабочее окно
    (непрерывный слив по ТЗ), НО теперь ОБЯЗАН уважать
    занятые интервалы на своих единицах оборудования.
  - Причина: после сдвига предков (TANK_TRANSFER, REACTOR_OP)
    две LINE_FILL разных партий могли получить одинаковый
    earliest_start и пересечься на одной линии розлива
    (реальный инцидент: 118 мин наложения на Линии 1).
  - Реализация: LINE_FILL проходит через _find_free_slot(),
    как и все остальные задачи. Если свободного окна нет —
    fallback на earliest_start + WARNING в лог (лучше
    наложение в крайнем случае, чем сорванный план).
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
# Топологическая сортировка
# ==========================================

def _topological_sort(
        tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Топологическая сортировка задач по зависимостям."""
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

    for t in tasks:
        if t not in result:
            result.append(t)

    return result


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

    Итерация 21 (fix #hybrid):
      - LINE_FILL НЕ переносится в рабочее окно (непрерывный слив).
      - Остальные операции ищут ближайшее рабочее окно.
      - Цепочка может разрываться между операциями.
      - earliest_start = max(end(предков), orig_start + delta_предков).

    Итерация 21 (fix #line-fill-nooverlap):
      - LINE_FILL теперь УВАЖАЕТ занятые интервалы на своих
        единицах оборудования (см. _find_free_slot).
      - Если свободного окна нет — fallback на earliest_start
        + WARNING в лог.
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
    # Итерация 21: храним (start, end, parallel_group_id) для
    # корректного подсчёта overlaps (исключаем пары одной группы).
    occupied: Dict[str, List[Tuple[int, int, Optional[str]]]] = {}
    final_times: Dict[Tuple[str, str], Tuple[int, int]] = {}

    shift_delta: Dict[Tuple[str, str], int] = {}

    shifted_details: List[Dict[str, Any]] = []
    line_fill_skipped = 0

    def _find_free_slot(
            equipment_ids: List[str],
            duration: int,
            earliest_start: int,
            max_horizon: int,
            parallel_group_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Ищет ближайшее время >= earliest_start в рабочем окне,
        не пересекаясь с занятыми интервалами.

        Итерация 21: при проверке пересечения игнорируем пары
        одной parallel_group (они разрешены).
        """
        candidates: Set[int] = {earliest_start}
        for eq_id in equipment_ids:
            for (s, e, _pg) in occupied.get(eq_id, []):
                if e >= earliest_start:
                    candidates.add(e)

        for (ws, we) in working_windows:
            if we - ws >= duration and we >= earliest_start:
                candidates.add(max(ws, earliest_start))

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
                        # Игнорируем пары одной parallel_group
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

            return start

        return None

    def _occupy(
            equipment_ids: List[str],
            start: int,
            end: int,
            parallel_group_id: Optional[str] = None,
    ) -> None:
        """Регистрирует задачу как занятую с parallel_group_id."""
        for eq_id in equipment_ids:
            occupied.setdefault(eq_id, []).append(
                (start, end, parallel_group_id)
            )

    # ==========================================
    # Основной цикл — по задачам в топологическом порядке
    # ==========================================
    for task in tasks_sorted:
        batch_id = task.get("batch_id")
        op_id = task.get("op_id")
        if not batch_id or not op_id:
            continue
        key = (str(batch_id), str(op_id))

        orig_start_min = to_min(task.get("start"))
        orig_end_min = to_min(task.get("end"))
        duration = orig_end_min - orig_start_min

        if duration <= 0:
            continue

        equipment_ids: List[str] = []
        if task.get("equipment_id"):
            equipment_ids.append(str(task["equipment_id"]))
        if task.get("linked_equipment_id"):
            linked = str(task["linked_equipment_id"])
            if linked not in equipment_ids:
                equipment_ids.append(linked)

        # ==========================================
        # earliest_start = max(end(предков), orig_start + delta_предков)
        # ==========================================
        earliest_start = 0
        inherited_delta = 0

        for dep_op_id in (task.get("depends_on_op_ids") or []):
            dep_key = (str(batch_id), str(dep_op_id))

            if dep_key in final_times:
                _, dep_end = final_times[dep_key]
                earliest_start = max(earliest_start, dep_end)

            if dep_key in shift_delta:
                inherited_delta = max(inherited_delta, shift_delta[dep_key])

        chain_start = orig_start_min + inherited_delta
        earliest_start = max(earliest_start, chain_start)

        # ==========================================
        # LINE_FILL — не переносится в рабочее окно,
        # но УВАЖАЕТ занятые интервалы (Итерация 21, fix #line-fill-nooverlap).
        # ==========================================
        if _is_line_fill_task(task):
            # Итерация 21 (fix #line-fill-nooverlap):
            # Раньше здесь было new_start = earliest_start без
            # проверки occupied — из-за этого две LINE_FILL
            # разных партий могли оказаться на одной линии
            # розлива одновременно (реальный инцидент:
            # 118 мин наложения на Линии 1).
            #
            # Теперь ищем свободный слот. Если его нет —
            # fallback на earliest_start (лучше наложение в
            # крайнем случае, чем сорванный план), но с WARNING.
            new_start = _find_free_slot(
                equipment_ids=equipment_ids,
                duration=duration,
                earliest_start=earliest_start,
                max_horizon=horizon_minutes,
                parallel_group_id=task.get("parallel_group_id"),
            )

            if new_start is None:
                log_with_context(
                    logger, logging.WARNING,
                    f"[POSTPROCESS] LINE_FILL: нет свободного окна для "
                    f"batch={str(batch_id)[:8]} op={str(op_id)[:8]} "
                    f"eq={[e[:8] for e in equipment_ids]}, "
                    f"оставляем на earliest_start={earliest_start}",
                    stage="postprocess", org_id=str(t0),
                )
                new_start = earliest_start

            new_end = new_start + duration
            delta = new_start - orig_start_min
            shift_delta[key] = delta

            line_fill_skipped += 1

            if new_start != orig_start_min:
                old_start = task.get("start")
                old_end = task.get("end")

                shifted_details.append({
                    "batch_id": task["batch_id"],
                    "op_id": task["op_id"],
                    "operation_name": task.get("operation_name"),
                    "old_start": (
                        old_start.isoformat()
                        if hasattr(old_start, "isoformat") else str(old_start)
                    ),
                    "old_end": (
                        old_end.isoformat()
                        if hasattr(old_end, "isoformat") else str(old_end)
                    ),
                    "new_start": from_min(new_start).isoformat(),
                    "new_end": from_min(new_end).isoformat(),
                    "delta_minutes": delta,
                    "reason": "line_fill_shifted_to_free_slot",
                })

                task["start"] = from_min(new_start)
                task["end"] = from_min(new_end)

            _occupy(
                equipment_ids, new_start, new_end,
                task.get("parallel_group_id"),
            )
            final_times[key] = (new_start, new_end)
            continue

        # ==========================================
        # Обычная задача (REACTOR_OP, WASH, TANK_TRANSFER) —
        # ищем ближайшее рабочее окно (Итерация 21)
        # ==========================================
        new_start = _find_free_slot(
            equipment_ids=equipment_ids,
            duration=duration,
            earliest_start=earliest_start,
            max_horizon=horizon_minutes,
            parallel_group_id=task.get("parallel_group_id"),
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
            # Оставляем на исходном месте (fallback).
            _occupy(
                equipment_ids, orig_start_min, orig_end_min,
                task.get("parallel_group_id"),
            )
            final_times[key] = (orig_start_min, orig_end_min)
            shift_delta[key] = inherited_delta
            continue

        new_end = new_start + duration
        delta = new_start - orig_start_min
        shift_delta[key] = delta

        if new_start != orig_start_min:
            old_start = task.get("start")
            old_end = task.get("end")

            reason = _build_shift_reason(
                orig_start_min, new_start, working_windows,
            )
            comment = _make_shift_comment(
                old_start if isinstance(old_start, datetime) else None,
                from_min(new_start),
                reason,
            )

            shifted_details.append({
                "batch_id": task["batch_id"],
                "op_id": task["op_id"],
                "operation_name": task.get("operation_name"),
                "old_start": (
                    old_start.isoformat()
                    if hasattr(old_start, "isoformat") else str(old_start)
                ),
                "old_end": (
                    old_end.isoformat()
                    if hasattr(old_end, "isoformat") else str(old_end)
                ),
                "new_start": from_min(new_start).isoformat(),
                "new_end": from_min(new_end).isoformat(),
                "delta_minutes": delta,
                "reason": reason,
                "comment": comment,
            })

            task["start"] = from_min(new_start)
            task["end"] = from_min(new_end)
            task["comment"] = comment

        _occupy(
            equipment_ids, new_start, new_end,
            task.get("parallel_group_id"),
        )
        final_times[key] = (new_start, new_end)

    # ==========================================
    # Проверка результата
    # ==========================================
    # Итерация 21: overlaps считаются с исключением пар одной
    # parallel_group (разрешённая параллельность).
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
    for t in tasks_sorted:
        bid = str(t.get("batch_id"))
        oid = str(t.get("op_id"))
        index[(bid, oid)] = t

    for t in tasks_sorted:
        bid = str(t.get("batch_id"))
        oid = str(t.get("op_id"))
        my_start = to_min(t.get("start"))

        for dep_op_id in (t.get("depends_on_op_ids") or []):
            dep_key = (bid, str(dep_op_id))
            dep_task = index.get(dep_key)
            if dep_task is None:
                continue
            dep_end = to_min(dep_task.get("end"))
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
        "shifted_details": shifted_details[:20],
        "overlaps_after": overlaps_after,
        "dependency_violations": dep_violations,
        "skipped": False,
    }


def _build_shift_reason(
        old_start_min: int,
        new_start_min: int,
        working_windows: List[Tuple[int, int]],
) -> str:
    """Формирует человекочитаемую причину сдвига."""
    if not working_windows:
        return "нет рабочих окон"

    gap_min = new_start_min - old_start_min

    if gap_min >= 720:
        return "перенос на ближайший рабочий день (выходные/простой)"

    return "перенос на свободное рабочее окно"


def _make_shift_comment(
        orig_start_dt: Optional[datetime],
        new_start_dt: datetime,
        reason: str,
) -> str:
    """Формирует текст комментария для задачи."""
    orig = orig_start_dt.strftime("%d.%m %H:%M") if orig_start_dt else "?"
    new = new_start_dt.strftime("%d.%m %H:%M")
    return f"Перенос с {orig} на {new}: {reason}"