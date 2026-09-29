# backend/app/scheduler/reschedule_cascade.py
"""
Каскадный сдвиг задач при ручных правках на Ганте (Итерация 13.17).

Детерминированный алгоритм (не solver):
  1. Пользователь тянет задачу (move) или меняет её длительность (resize).
  2. Изменение применяется к целевой задаче.
  3. Каскад:
     a. Соседи на том же оборудовании сдвигаются, чтобы не пересекаться.
     b. Последователи (depends_on_task_ids) сдвигаются, чтобы начинаться
        после предшественника.
     c. Каскад рекурсивный (BFS) с ограничениями MAX_CASCADE_DEPTH
        и MAX_CASCADE_TASKS.

Гарантии:
  - NoOverlap на оборудовании после каскада.
  - Зависимости соблюдены (start >= end предшественника).
  - Pinned / DONE / IN_PROGRESS / actual_start — не двигаются,
    при конфликте бросается CascadeBlockedError.

Итерация 13.18:
  - is_pinned больше НЕ блокирует resize (изменение длительности).
  - is_pinned блокирует ТОЛЬКО move (перемещение без изменения длительности).
  - Это позволяет пользователю корректировать длительность закреплённой
    задачи, не открепляя её.
Итерация 13.18 (fix #4):
  - Все datetime приводятся к naive-UTC через _to_naive_utc.
  - Это устраняет TypeError: can't compare offset-naive and offset-aware
    при сортировке задач на одном оборудовании.
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)

# Защита от бесконечной рекурсии
MAX_CASCADE_DEPTH = 200
MAX_CASCADE_TASKS = 500

# Порог определения resize (сек). Если длительность изменилась больше,
# чем на этот порог — это resize, иначе — move.
RESIZE_THRESHOLD_SECONDS = 60


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ: NORMALIZE DATETIME
# ==========================================

def _to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Приводит datetime к naive-UTC.

    Если dt имеет timezone — конвертирует в UTC и убирает tzinfo.
    Если dt уже naive — возвращает как есть (предполагаем UTC).
    Если dt is None — возвращает None.

    Нужно, чтобы избежать TypeError при сравнении/сортировке
    aware и naive datetime (см. баг Итерации 13.18).

    Args:
        dt: datetime с timezone или без, или None.

    Returns:
        datetime без tzinfo в UTC, или None.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ==========================================
# ТИПЫ
# ==========================================

@dataclass
class TaskSnapshot:
    """Снимок задачи для каскадного сдвига."""
    id: str
    batch_id: Optional[str]
    equipment_id: str
    task_role: Optional[str]
    operation_name: str
    planned_start: datetime
    planned_end: datetime
    duration_minutes: int
    is_pinned: bool
    status: str
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    depends_on: List[str] = field(default_factory=list)

    @property
    def is_movable(self) -> bool:
        """Можно ли двигать эту задачу."""
        if self.is_pinned:
            return False
        if self.status in ("DONE", "IN_PROGRESS", "CANCELLED"):
            return False
        if self.actual_start is not None:
            return False
        if self.actual_end is not None:
            return False
        return True


@dataclass
class CascadeResult:
    """Результат каскадного сдвига."""
    moved_tasks: List[dict] = field(default_factory=list)
    blocked_tasks: List[dict] = field(default_factory=list)
    depth_reached: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def moved_count(self) -> int:
        return len(self.moved_tasks)


class CascadeBlockedError(Exception):
    """Каскад заблокирован (pinned/DONE/IN_PROGRESS задача мешает)."""

    def __init__(self, reason: str, blocked_task: Optional[dict] = None):
        super().__init__(reason)
        self.reason = reason
        self.blocked_task = blocked_task or {}


@dataclass
class ValidationResult:
    """Результат валидации перемещения."""
    allowed: bool
    reason: Optional[str] = None
    details: List[str] = field(default_factory=list)


# ==========================================
# ЗАГРУЗКА ЗАДАЧ
# ==========================================

async def _load_tasks(
        session: AsyncSession,
        org_id: UUID,
        version_id: UUID,
) -> Dict[str, TaskSnapshot]:
    """
    Загружает все задачи версии в память.

    Итерация 13.18 (fix #4): все datetime приводятся к naive-UTC
    через _to_naive_utc. Это устраняет TypeError при сортировке.
    """
    result = await session.execute(
        text("""
            SELECT
                st.id::text AS id,
                st.batch_id::text AS batch_id,
                st.equipment_id::text AS equipment_id,
                st.task_role,
                COALESCE(st.operation_name, ot.name, 'Операция') AS operation_name,
                st.planned_start,
                st.planned_end,
                COALESCE(st.is_pinned, FALSE) AS is_pinned,
                COALESCE(st.status, 'PLANNED') AS status,
                st.actual_start,
                st.actual_end,
                COALESCE(st.depends_on_task_ids, '[]'::jsonb) AS depends_on
            FROM scheduled_task st
            LEFT JOIN operation_template ot ON ot.id = st.operation_template_id
            WHERE st.schedule_version_id = :version_id
              AND st.organization_id = :org_id
        """),
        {"version_id": version_id, "org_id": org_id},
    )

    tasks: Dict[str, TaskSnapshot] = {}
    for row in result.fetchall():
        # Парсим depends_on_task_ids (JSONB → list)
        deps_raw = row.depends_on
        if isinstance(deps_raw, str):
            import json
            try:
                deps_raw = json.loads(deps_raw)
            except (ValueError, TypeError):
                deps_raw = []
        if not isinstance(deps_raw, list):
            deps_raw = []

        # Итерация 13.18 (fix #4): нормализуем все datetime к naive-UTC.
        planned_start_naive = _to_naive_utc(row.planned_start)
        planned_end_naive = _to_naive_utc(row.planned_end)

        duration = int(
            (planned_end_naive - planned_start_naive).total_seconds() / 60
        )

        tasks[row.id] = TaskSnapshot(
            id=row.id,
            batch_id=row.batch_id,
            equipment_id=row.equipment_id,
            task_role=row.task_role,
            operation_name=row.operation_name,
            planned_start=planned_start_naive,
            planned_end=planned_end_naive,
            duration_minutes=duration,
            is_pinned=bool(row.is_pinned),
            status=row.status,
            actual_start=_to_naive_utc(row.actual_start),
            actual_end=_to_naive_utc(row.actual_end),
            depends_on=[str(d) for d in deps_raw],
        )

    return tasks


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ
# ==========================================

def _overlaps(
        s1: datetime, e1: datetime,
        s2: datetime, e2: datetime,
) -> bool:
    """Полуоткрытые интервалы [s, e). Стык не пересечение."""
    return s1 < e2 and s2 < e1


def _is_resize(
        original_start: datetime,
        original_end: datetime,
        new_start: datetime,
        new_end: datetime,
) -> bool:
    """
    Определяет, является ли изменение resize (изменением длительности)
    или move (перемещением без изменения длительности).

    Returns:
        True  — resize (длительность изменилась больше порога).
        False — move (длительность та же).
    """
    original_duration = (original_end - original_start).total_seconds()
    new_duration = (new_end - new_start).total_seconds()
    return abs(new_duration - original_duration) > RESIZE_THRESHOLD_SECONDS


# ==========================================
# ОСНОВНОЙ АЛГОРИТМ
# ==========================================

async def apply_cascade(
        session: AsyncSession,
        org_id: UUID,
        version_id: UUID,
        changed_task_id: UUID,
        new_start: datetime,
        new_end: datetime,
        allow_weekend_work: bool = False,
) -> CascadeResult:
    """
    Применяет каскадный сдвиг.

    Итерация 13.18 (fix #4): входные new_start/new_end нормализуются
    к naive-UTC в начале функции.

    Returns:
        CascadeResult со списком сдвинутых задач.

    Raises:
        CascadeBlockedError: если каскад заблокирован pinned-задачей.
    """
    changed_id_str = str(changed_task_id)

    # Итерация 13.18 (fix #4): нормализуем входные времена.
    new_start = _to_naive_utc(new_start)
    new_end = _to_naive_utc(new_end)

    # 1. Загружаем все задачи версии
    tasks = await _load_tasks(session, org_id, version_id)

    if changed_id_str not in tasks:
        raise CascadeBlockedError(f"Задача {changed_id_str} не найдена")

    # 2. Применяем изменение к целевой задаче
    changed_task = tasks[changed_id_str]
    changed_task.planned_start = new_start
    changed_task.planned_end = new_end
    changed_task.duration_minutes = int(
        (new_end - new_start).total_seconds() / 60
    )

    log_with_context(
        logger, logging.INFO,
        f"[cascade] START: task={changed_id_str[:8]}, "
        f"new_start={new_start.isoformat()}, new_end={new_end.isoformat()}",
        stage="cascade", org_id=str(org_id),
    )

    # 3. Индексы: по оборудованию, последователи
    by_equipment: Dict[str, List[TaskSnapshot]] = {}
    for t in tasks.values():
        by_equipment.setdefault(t.equipment_id, []).append(t)

    successors: Dict[str, List[str]] = {}
    for t in tasks.values():
        for dep_id in t.depends_on:
            successors.setdefault(dep_id, []).append(t.id)

    # 4. Каскад через BFS
    queue = deque([changed_id_str])
    processed: Set[str] = set()
    moved: List[dict] = []
    blocked: List[dict] = []

    while queue:
        current_id = queue.popleft()
        if current_id in processed:
            continue
        if len(processed) > MAX_CASCADE_TASKS:
            log_with_context(
                logger, logging.WARNING,
                f"[cascade] Достигнут лимит задач: {MAX_CASCADE_TASKS}",
                stage="cascade", org_id=str(org_id),
            )
            break

        processed.add(current_id)
        current = tasks.get(current_id)
        if current is None:
            continue

        # 4a. Последователи: должны начинаться после current
        for succ_id in successors.get(current_id, []):
            succ = tasks.get(succ_id)
            if succ is None:
                continue

            if not succ.is_movable:
                if succ.planned_start < current.planned_end:
                    blocked.append({
                        "task_id": succ.id,
                        "operation_name": succ.operation_name,
                        "reason": (
                            f"Зависимая задача «{succ.operation_name}» "
                            f"не может быть сдвинута"
                        ),
                    })
                    raise CascadeBlockedError(
                        f"Зависимая задача «{succ.operation_name}» "
                        f"закреплена или уже начата. "
                        f"Открепите её или отмените изменение.",
                        blocked_task={
                            "task_id": succ.id,
                            "operation_name": succ.operation_name,
                            "status": succ.status,
                        },
                    )
                continue

            if succ.planned_start < current.planned_end:
                delta = current.planned_end - succ.planned_start
                succ.planned_start = current.planned_end
                succ.planned_end = succ.planned_end + delta
                queue.append(succ_id)

        # 4b. Соседи на том же оборудовании: не должны пересекаться
        equipment_tasks = by_equipment.get(current.equipment_id, [])
        equipment_tasks_sorted = sorted(
            equipment_tasks, key=lambda t: t.planned_start,
        )

        for task in equipment_tasks_sorted:
            if task.id == current_id:
                continue
            if not _overlaps(
                    task.planned_start, task.planned_end,
                    current.planned_start, current.planned_end,
            ):
                continue

            if task.planned_start >= current.planned_start:
                # task идёт после current — сдвигаем task вправо
                if not task.is_movable:
                    blocked.append({
                        "task_id": task.id,
                        "operation_name": task.operation_name,
                        "reason": (
                            f"Соседняя задача «{task.operation_name}» "
                            f"не может быть сдвинута"
                        ),
                    })
                    raise CascadeBlockedError(
                        f"Соседняя задача «{task.operation_name}» "
                        f"закреплена или уже начата. "
                        f"Открепите её или отмените изменение.",
                        blocked_task={
                            "task_id": task.id,
                            "operation_name": task.operation_name,
                            "status": task.status,
                        },
                    )

                delta = current.planned_end - task.planned_start
                if delta.total_seconds() > 0:
                    task.planned_start = current.planned_end
                    task.planned_end = task.planned_end + delta
                    queue.append(task.id)
            else:
                # task до current, но пересекается — сдвигаем task влево
                # (или current вправо, если task нельзя двигать)
                if not task.is_movable:
                    current.planned_start = task.planned_end
                    current.planned_end = current.planned_start + timedelta(
                        minutes=current.duration_minutes
                    )
                    queue.append(current_id)
                else:
                    task.planned_end = current.planned_start
                    task.planned_start = task.planned_end - timedelta(
                        minutes=task.duration_minutes
                    )
                    queue.append(task.id)

        # 4c. Записываем изменение
        if current_id != changed_id_str:
            moved.append({
                "task_id": current.id,
                "operation_name": current.operation_name,
                "equipment_id": current.equipment_id,
                "new_start": current.planned_start.isoformat(),
                "new_end": current.planned_end.isoformat(),
            })

    # 5. Сохраняем изменения
    for task in tasks.values():
        if task.id == changed_id_str or any(
                m["task_id"] == task.id for m in moved
        ):
            await session.execute(
                text("""
                    UPDATE scheduled_task
                    SET planned_start = :start,
                        planned_end = :end
                    WHERE id = :task_id
                """),
                {
                    "task_id": task.id,
                    "start": task.planned_start,
                    "end": task.planned_end,
                },
            )

    result = CascadeResult(
        moved_tasks=moved,
        blocked_tasks=blocked,
        depth_reached=len(processed),
    )

    log_with_context(
        logger, logging.INFO,
        f"[cascade] DONE: moved={len(moved)}, processed={len(processed)}",
        stage="cascade", org_id=str(org_id),
    )

    return result


# ==========================================
# ВАЛИДАЦИЯ
# ==========================================

async def validate_move(
        session: AsyncSession,
        org_id: UUID,
        version_id: UUID,
        task_id: UUID,
        new_start: datetime,
        new_end: datetime,
        planning_start: Optional[datetime] = None,
        allow_weekend_work: bool = False,
) -> ValidationResult:
    """
    Валидирует перемещение/изменение длительности задачи.

    Итерация 13.18:
      - is_pinned блокирует ТОЛЬКО move (перемещение без изменения длительности).
      - is_pinned НЕ блокирует resize (изменение длительности).

    Итерация 13.18 (fix #4): входные new_start/new_end нормализуются
    к naive-UTC в начале функции.
    """

    # Итерация 13.18 (fix #4): нормализуем входные времена.
    new_start = _to_naive_utc(new_start)
    new_end = _to_naive_utc(new_end)
    planning_start = _to_naive_utc(planning_start)

    # 1. Времена
    if new_end <= new_start:
        return ValidationResult(
            allowed=False,
            reason="Некорректные времена",
            details=["Конец должен быть позже начала."],
        )

    duration_min = int((new_end - new_start).total_seconds() / 60)
    if duration_min < 5:
        return ValidationResult(
            allowed=False,
            reason="Слишком короткая задача",
            details=["Минимум 5 минут."],
        )
    if duration_min > 24 * 60:
        return ValidationResult(
            allowed=False,
            reason="Слишком длинная задача",
            details=["Максимум 24 часа."],
        )

    # 2. planning_start
    if planning_start is not None and new_start < planning_start:
        return ValidationResult(
            allowed=False,
            reason="Задача раньше начала плана",
            details=[
                f"Начало плана: {planning_start.strftime('%d.%m.%Y %H:%M')}",
                f"Новое начало: {new_start.strftime('%d.%m.%Y %H:%M')}",
            ],
        )

    # 3. Выходные
    if not allow_weekend_work:
        if new_start.weekday() >= 5 or new_end.weekday() >= 5:
            return ValidationResult(
                allowed=False,
                reason="Задача попадает на выходной день",
                details=[
                    "В настройках плана запрещена работа в выходные.",
                    "Изменить можно в мастере настроек плана (allow_weekend_work).",
                ],
            )

    # 4. Задача двигаема?
    result = await session.execute(
        text("""
            SELECT
                st.id::text AS id,
                COALESCE(st.is_pinned, FALSE) AS is_pinned,
                COALESCE(st.status, 'PLANNED') AS status,
                st.actual_start,
                st.actual_end,
                st.planned_start,
                st.planned_end
            FROM scheduled_task st
            WHERE st.id = :task_id
              AND st.organization_id = :org_id
        """),
        {"task_id": task_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        return ValidationResult(allowed=False, reason="Задача не найдена")

    # Нормализуем original planned_start/planned_end
    original_start = _to_naive_utc(row.planned_start)
    original_end = _to_naive_utc(row.planned_end)

    # Итерация 13.18: определяем, resize это или move
    is_resize = _is_resize(
        original_start=original_start,
        original_end=original_end,
        new_start=new_start,
        new_end=new_end,
    )

    # 4.1. is_pinned блокирует ТОЛЬКО move (не resize)
    if row.is_pinned and not is_resize:
        return ValidationResult(
            allowed=False,
            reason="Задача закреплена (is_pinned)",
            details=[
                "Перемещение закреплённой задачи запрещено.",
                "Открепите задачу в контекстном меню.",
                "Изменение длительности закреплённой задачи разрешено.",
            ],
        )

    # 4.2. DONE/IN_PROGRESS блокируют любые изменения
    if row.status in ("DONE", "IN_PROGRESS"):
        return ValidationResult(
            allowed=False,
            reason=f"Задача в статусе {row.status}",
            details=["Нельзя сдвигать завершённые или начатые задачи."],
        )

    # 4.3. actual_start блокирует любые изменения
    if row.actual_start is not None:
        return ValidationResult(
            allowed=False,
            reason="Задача уже начата",
            details=["Нельзя сдвигать задачи с внесённым фактом."],
        )

    return ValidationResult(allowed=True)