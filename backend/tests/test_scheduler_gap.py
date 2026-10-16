# backend/tests/test_scheduler_gap.py
"""
Интеграционные тесты непрерывности плана (Итерация 18, fix #gap).

Проверяют, что после build_schedule:
  1. Операции одной партии идут непрерывно — между последовательными
     операциями нет разрывов больше max_gap_after_minutes.
  2. Параллельные операции (Перемешивание ∥ Охлаждение) имеют
     одинаковый planned_start.
  3. Операция после параллельной группы начинается не раньше, чем
     закончится самая длинная операция группы.

ВАЖНО: тесты используют рабочую БД из settings.DATABASE_URL.
Если активного плана нет — тесты пропускаются (pytest.skip).
"""

from typing import Dict, List, Tuple

import pytest

from app.core.config import settings
from app.scheduler.core import ProductionScheduler


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _build_graph(
        tasks: List[Dict],
) -> Tuple[Dict[Tuple[str, str], Dict], Dict[Tuple[str, str], List[Tuple[str, str]]]]:
    """
    Строит индекс задач и граф зависимостей.

    Returns:
        index: {(batch_id, op_id): task}
        deps:  {(batch_id, op_id): [(batch_id, dep_op_id), ...]}
    """
    index: Dict[Tuple[str, str], Dict] = {}
    for t in tasks:
        key = (str(t["batch_id"]), str(t["op_id"]))
        index[key] = t

    deps: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for t in tasks:
        key = (str(t["batch_id"]), str(t["op_id"]))
        dep_keys = []
        for dep_op_id in (t.get("depends_on_op_ids") or []):
            dep_key = (str(t["batch_id"]), str(dep_op_id))
            if dep_key in index:
                dep_keys.append(dep_key)
        deps[key] = dep_keys

    return index, deps


def _batch_ids(tasks: List[Dict]) -> List[str]:
    """Уникальные batch_id."""
    seen = set()
    result = []
    for t in tasks:
        bid = str(t["batch_id"])
        if bid not in seen:
            seen.add(bid)
            result.append(bid)
    return result


# ==========================================
# ТЕСТ 1: Непрерывность внутри партии
# ==========================================

def _check_continuity_for_batch(
        tasks: List[Dict],
        batch_id: str,
        max_allowed_gap_min: int = 1,
) -> List[Dict]:
    """
    Проверяет, что между последовательными операциями партии
    нет разрывов больше max_allowed_gap_min (по умолчанию 1 мин —
    допуск на округления).

    Возвращает список найденных разрывов (для диагностики).
    """
    index, deps = _build_graph(tasks)

    # Задачи только этой партии
    batch_tasks = [
        t for t in tasks if str(t["batch_id"]) == batch_id
    ]
    # Сортируем по start
    batch_tasks.sort(key=lambda t: t["start"])

    gaps = []
    for t in batch_tasks:
        key = (str(t["batch_id"]), str(t["op_id"]))
        my_start = t["start"]

        for dep_key in deps.get(key, []):
            dep_task = index.get(dep_key)
            if dep_task is None:
                continue
            dep_end = dep_task["end"]

            # Разрыв: start(текущей) − end(предшественника)
            gap_min = (my_start - dep_end).total_seconds() / 60

            # Проверяем только положительные разрывы (gap > 0)
            if gap_min > max_allowed_gap_min:
                gaps.append({
                    "batch_id": batch_id,
                    "op_id": key[1],
                    "op_name": t.get("operation_name"),
                    "dep_op_id": dep_key[1],
                    "dep_name": dep_task.get("operation_name"),
                    "my_start": my_start.isoformat(),
                    "dep_end": dep_end.isoformat(),
                    "gap_minutes": round(gap_min, 2),
                })

    return gaps


@pytest.mark.asyncio
async def test_no_gaps_between_sequential_ops():
    """
    Интеграционный: после build_schedule между последовательными
    операциями партии нет разрывов > 1 мин.

    Допускаем 1 мин на округления и потенциальный gap для
    операций с несколькими предками (но их сейчас нет).
    """
    scheduler = ProductionScheduler(
        horizon_hours=360,
        timeout_seconds=60,   # короткий таймаут для теста
        org_id=settings.DEFAULT_ORG_ID,
    )

    # Строим план, НЕ сохраняем в БД
    result = await scheduler.build_schedule()

    if "error" in result:
        pytest.skip(
            f"План не построен (status={result.get('status')}) — "
            f"пропускаем: {result.get('error')}"
        )

    tasks = result["tasks"]
    assert len(tasks) > 0, "Пустой план"

    batch_ids = _batch_ids(tasks)

    all_gaps = []
    for bid in batch_ids:
        gaps = _check_continuity_for_batch(
            tasks, bid, max_allowed_gap_min=1
        )
        all_gaps.extend(gaps)

    if all_gaps:
        # Формируем читаемый отчёт
        report_lines = [
            f"Найдено разрывов > 1 мин: {len(all_gaps)}",
        ]
        for g in all_gaps[:10]:   # первые 10
            report_lines.append(
                f"  batch={g['batch_id'][:8]} "
                f"op={g['op_name']} start={g['my_start']} "
                f"dep={g['dep_name']} end={g['dep_end']} "
                f"gap={g['gap_minutes']} мин"
            )
        pytest.fail("\n".join(report_lines))


# ==========================================
# ТЕСТ 2: Параллельные операции имеют одинаковый start
# ==========================================

def _check_parallel_start(
        tasks: List[Dict],
        tolerance_min: int = 1,
) -> List[Dict]:
    """
    Проверяет, что параллельные операции (одна группа) имеют
    одинаковый start (с допуском tolerance_min).

    Возвращает список несовпадений.
    """
    # Группируем по (batch_id, parallel_group_id)
    groups: Dict[Tuple[str, str], List[Dict]] = {}
    for t in tasks:
        pg = t.get("parallel_group_id")
        if not pg:
            continue
        key = (str(t["batch_id"]), str(pg))
        groups.setdefault(key, []).append(t)

    mismatches = []
    for key, ops in groups.items():
        if len(ops) < 2:
            continue

        starts = [t["start"] for t in ops]
        min_start = min(starts)
        max_start = max(starts)
        delta_min = (max_start - min_start).total_seconds() / 60

        if delta_min > tolerance_min:
            mismatches.append({
                "batch_id": key[0],
                "parallel_group": key[1],
                "starts": [s.isoformat() for s in starts],
                "max_delta_minutes": round(delta_min, 2),
                "op_names": [t.get("operation_name") for t in ops],
            })

    return mismatches


@pytest.mark.asyncio
async def test_parallel_ops_share_start():
    """
    Интеграционный: параллельные операции одной группы
    (например, Перемешивание ∥ Охлаждение) имеют одинаковый start.
    """
    scheduler = ProductionScheduler(
        horizon_hours=360,
        timeout_seconds=60,
        org_id=settings.DEFAULT_ORG_ID,
    )

    result = await scheduler.build_schedule()
    if "error" in result:
        pytest.skip(f"План не построен: {result.get('error')}")

    tasks = result["tasks"]
    mismatches = _check_parallel_start(tasks, tolerance_min=1)

    if mismatches:
        report = [f"Несовпадения start в параллельных группах: {len(mismatches)}"]
        for m in mismatches[:10]:
            report.append(
                f"  batch={m['batch_id'][:8]} group={m['parallel_group']} "
                f"delta={m['max_delta_minutes']} мин "
                f"ops={m['op_names']} starts={m['starts']}"
            )
        pytest.fail("\n".join(report))


# ==========================================
# ТЕСТ 3: Операция после группы начинается после max(end)
# ==========================================

def _check_after_group(
        tasks: List[Dict],
        tolerance_min: int = 1,
) -> List[Dict]:
    """
    Проверяет, что операция после параллельной группы начинается
    не раньше, чем max(end) операций группы.
    """
    # Индексируем задачи и их группы
    index: Dict[Tuple[str, str], Dict] = {}
    for t in tasks:
        key = (str(t["batch_id"]), str(t["op_id"]))
        index[key] = t

    violations = []
    for t in tasks:
        dep_ids = t.get("depends_on_op_ids") or []
        if not dep_ids:
            continue

        bid = str(t["batch_id"])
        my_start = t["start"]

        # Находим всех предков; смотрим, есть ли среди них операции группы
        group_ends = []
        for dep_id in dep_ids:
            dep_key = (bid, str(dep_id))
            dep_task = index.get(dep_key)
            if dep_task is None:
                continue
            if dep_task.get("parallel_group_id"):
                group_ends.append(
                    (dep_task.get("operation_name"), dep_task["end"])
                )

        if not group_ends:
            continue

        max_end = max(e for _, e in group_ends)
        delta_min = (my_start - max_end).total_seconds() / 60

        # my_start должен быть >= max_end (по ТЗ). Допускаем tolerance.
        if delta_min < -tolerance_min:
            violations.append({
                "batch_id": bid,
                "op_name": t.get("operation_name"),
                "my_start": my_start.isoformat(),
                "max_group_end": max_end.isoformat(),
                "delta_minutes": round(delta_min, 2),
                "group_ops": group_ends,
            })

    return violations


@pytest.mark.asyncio
async def test_op_after_group_starts_after_group_end():
    """
    Интеграционный: операция после параллельной группы (например,
    Лаб.анализ после Перемешивание ∥ Охлаждение) начинается
    не раньше max(end) операций группы.
    """
    scheduler = ProductionScheduler(
        horizon_hours=360,
        timeout_seconds=60,
        org_id=settings.DEFAULT_ORG_ID,
    )

    result = await scheduler.build_schedule()
    if "error" in result:
        pytest.skip(f"План не построен: {result.get('error')}")

    tasks = result["tasks"]
    violations = _check_after_group(tasks, tolerance_min=1)

    if violations:
        report = [f"Нарушений «после группы»: {len(violations)}"]
        for v in violations[:10]:
            report.append(
                f"  batch={v['batch_id'][:8]} "
                f"op={v['op_name']} start={v['my_start']} "
                f"max_group_end={v['max_group_end']} "
                f"delta={v['delta_minutes']} мин"
            )
        pytest.fail("\n".join(report))


# ==========================================
# ТЕСТ 4: План сходится и сохраняется
# ==========================================

@pytest.mark.asyncio
async def test_build_schedule_returns_feasible_plan():
    """
    Интеграционный smoke-тест: build_schedule возвращает
    осмысленный результат (не error, есть задачи).
    """
    scheduler = ProductionScheduler(
        horizon_hours=360,
        timeout_seconds=60,
        org_id=settings.DEFAULT_ORG_ID,
    )

    result = await scheduler.build_schedule()

    assert "error" not in result, (
        f"build_schedule вернул ошибку: {result.get('error')} "
        f"(status={result.get('status')})"
    )
    assert result.get("status") == "success"
    assert result["total_tasks"] > 0
    assert result["makespan_minutes"] > 0

    # Все задачи имеют start/end и они осмысленны
    for t in result["tasks"]:
        assert t["start"] < t["end"], (
            f"Задача {t['op_id']}: start >= end"
        )
        assert (t["end"] - t["start"]).total_seconds() > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])