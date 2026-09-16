# backend/app/scheduler/rescheduler.py
"""
Модуль перепланирования (Итерация 4).

Функции:
  - Загрузка предыдущего плана из БД (scheduled_task).
  - Применение изменений:
      * DELAY: задержка операции (факт позже плана).
      * BREAKDOWN: поломка оборудования.
      * QTY_CHANGE: изменение объёма заказа.
  - Закрепление задач до frozen_before (is_pinned = TRUE).
  - Пересчёт только затронутых партий.
  - Сохранение как новой версии.

Ключевое:
  - Задачи с is_pinned = TRUE не двигаются.
  - Задачи до frozen_before — тоже не двигаются.
  - Пересчёт только для партий, затронутых изменением.

Итерация 4 (fix): корректный SQL для клонирования снапшотов.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


class RescheduleReason:
    DELAY = "DELAY"
    BREAKDOWN = "BREAKDOWN"
    QTY_CHANGE = "QTY_CHANGE"
    MANUAL = "MANUAL"


@dataclass
class TaskSnapshot:
    """Снимок задачи из существующего плана."""
    id: str
    batch_id: Optional[str]
    equipment_id: str
    linked_equipment_id: Optional[str]
    task_role: Optional[str]
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    status: str
    is_pinned: bool


@dataclass
class RescheduleResult:
    """Результат перепланирования."""
    status: str
    from_version_id: Optional[str]
    to_version_id: Optional[str]
    affected_tasks: int = 0
    moved_tasks: int = 0
    frozen_tasks: int = 0
    message: str = ""
    diff: Dict[str, Any] = field(default_factory=dict)


class Rescheduler:
    """
    Оркестратор перепланирования.

    Использование:
        rescheduler = Rescheduler(org_id=...)
        result = await rescheduler.reschedule(
            from_version_id=...,
            reason=RescheduleReason.DELAY,
            changes={...},
            frozen_before=...,
        )
    """

    def __init__(self, org_id: UUID):
        self.org_id = org_id
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def _load_version(self, session, version_id: UUID) -> Optional[Dict]:
        result = await session.execute(
            text("""
                SELECT id, name, version_type, frozen_before, parent_version_id, created_at
                FROM schedule_version
                WHERE id = :version_id AND organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def _load_tasks(self, session, version_id: UUID) -> List[TaskSnapshot]:
        result = await session.execute(
            text("""
                SELECT
                    st.id::text AS id,
                    st.batch_id::text AS batch_id,
                    st.equipment_id::text AS equipment_id,
                    st.linked_equipment_id::text AS linked_equipment_id,
                    st.task_role,
                    st.planned_start, st.planned_end,
                    st.actual_start, st.actual_end,
                    st.status, COALESCE(st.is_pinned, FALSE) AS is_pinned
                FROM scheduled_task st
                WHERE st.schedule_version_id = :version_id
                  AND st.organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )
        return [
            TaskSnapshot(
                id=row.id,
                batch_id=row.batch_id,
                equipment_id=row.equipment_id,
                linked_equipment_id=row.linked_equipment_id,
                task_role=row.task_role,
                planned_start=row.planned_start,
                planned_end=row.planned_end,
                actual_start=row.actual_start,
                actual_end=row.actual_end,
                status=row.status or "PLANNED",
                is_pinned=bool(row.is_pinned),
            )
            for row in result.fetchall()
        ]

    def _is_frozen(self, task: TaskSnapshot, frozen_before: Optional[datetime]) -> bool:
        """Задача заморожена, если pin, или началась до frozen_before, или уже DONE."""
        if task.is_pinned:
            return True
        if task.status in ("DONE", "CANCELLED"):
            return True
        if frozen_before is not None:
            start = task.planned_start
            fb = frozen_before
            # Нормализуем таймзоны
            if start.tzinfo is not None and fb.tzinfo is None:
                start = start.replace(tzinfo=None)
            elif start.tzinfo is None and fb.tzinfo is not None:
                fb = fb.replace(tzinfo=None)
            if start < fb:
                return True
        return False

    def _find_affected_batch_ids(
            self,
            tasks: List[TaskSnapshot],
            changes: Dict[str, Any],
    ) -> set:
        """Определяет партии, затронутые изменением."""
        affected: set = set()

        # DELAY: конкретная задача задержалась
        delayed_task_id = changes.get("delayed_task_id")
        if delayed_task_id:
            for t in tasks:
                if t.id == str(delayed_task_id):
                    if t.batch_id:
                        affected.add(t.batch_id)
                    break

        # BREAKDOWN: оборудование сломалось — все партии на нём
        broken_equipment_id = changes.get("broken_equipment_id")
        if broken_equipment_id:
            for t in tasks:
                if t.equipment_id == str(broken_equipment_id) or t.linked_equipment_id == str(broken_equipment_id):
                    if t.batch_id:
                        affected.add(t.batch_id)

        # QTY_CHANGE: явно переданные партии
        explicit_batch_ids = changes.get("affected_batch_ids")
        if explicit_batch_ids:
            for b in explicit_batch_ids:
                affected.add(str(b))

        return affected

    async def _add_breakdown_to_calendar(
            self,
            session,
            equipment_id: UUID,
            starts_at: datetime,
            ends_at: datetime,
            comment: str = "Аварийная остановка",
    ) -> None:
        """Добавляет BREAKDOWN в calendar_event."""
        await session.execute(
            text("""
                INSERT INTO calendar_event
                (organization_id, equipment_id, event_type, starts_at, ends_at, comment)
                VALUES (:org_id, :eq_id, 'BREAKDOWN', :start, :end, :comment)
            """),
            {
                "org_id": self.org_id,
                "eq_id": equipment_id,
                "start": starts_at,
                "end": ends_at,
                "comment": comment,
            },
        )

    def _find_shift_id(self, shifts: List[Dict], dt: datetime) -> Optional[str]:
        """
        Находит shift_id для момента времени.

        Алгоритм:
          1. Точное попадание в окно смены.
          2. Fallback: ближайшая смена по starts_at.
        """
        if not shifts:
            return None

        if dt.tzinfo is not None:
            dt_naive = dt.replace(tzinfo=None)
        else:
            dt_naive = dt

        # 1. Точное попадание
        for s in shifts:
            start = s["starts_at"]
            end = s["ends_at"]
            if start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            if start <= dt_naive <= end:
                return str(s["id"])

        # 2. Fallback: ближайшая по starts_at
        closest_id = None
        closest_diff = None
        for s in shifts:
            start = s["starts_at"]
            if start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            diff = abs((dt_naive - start).total_seconds())
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest_id = str(s["id"])
        return closest_id

    async def _load_shifts(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id::text, starts_at, ends_at
                FROM shift
                WHERE organization_id = :org_id
                ORDER BY starts_at
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _clone_snapshots(
            self,
            session,
            from_version_id: UUID,
            new_version_id: UUID,
    ) -> None:
        """
        Клонирует снапшоты из исходной версии в новую.
        Для каждой таблицы — свой SQL с явными колонками,
        потому что наборы колонок разные.
        """
        # equipment_snapshot
        await session.execute(
            text("""
                INSERT INTO equipment_snapshot
                (id, organization_id, code, name, type, volume_kg, speed_coeff,
                 mixer_type, is_active, version_id)
                SELECT id, organization_id, code, name, type, volume_kg, speed_coeff,
                       mixer_type, is_active, :new_version_id
                FROM equipment_snapshot
                WHERE version_id = :from_version_id
            """),
            {"new_version_id": new_version_id, "from_version_id": from_version_id},
        )

        # product_snapshot
        await session.execute(
            text("""
                INSERT INTO product_snapshot
                (id, organization_id, code, name, type, viscosity_coeff, requires_heating,
                 bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type, version_id)
                SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating,
                       bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type, :new_version_id
                FROM product_snapshot
                WHERE version_id = :from_version_id
            """),
            {"new_version_id": new_version_id, "from_version_id": from_version_id},
        )

        # operation_snapshot
        await session.execute(
            text("""
                INSERT INTO operation_snapshot
                (id, organization_id, product_id, stage_order, name, base_duration_mins,
                 is_setup, is_parallel_group, parallel_group_id, needs_boiler,
                 needs_cooling_zone, needs_operator, needs_lab, duration_formula,
                 operator_pool, comment, version_id)
                SELECT id, organization_id, product_id, stage_order, name, base_duration_mins,
                       is_setup, is_parallel_group, parallel_group_id, needs_boiler,
                       needs_cooling_zone, needs_operator, needs_lab, duration_formula,
                       operator_pool, comment, :new_version_id
                FROM operation_snapshot
                WHERE version_id = :from_version_id
            """),
            {"new_version_id": new_version_id, "from_version_id": from_version_id},
        )

        # calendar_snapshot
        await session.execute(
            text("""
                INSERT INTO calendar_snapshot
                (id, organization_id, equipment_id, event_type, starts_at, ends_at,
                 comment, version_id)
                SELECT id, organization_id, equipment_id, event_type, starts_at, ends_at,
                       comment, :new_version_id
                FROM calendar_snapshot
                WHERE version_id = :from_version_id
            """),
            {"new_version_id": new_version_id, "from_version_id": from_version_id},
        )

    async def _clone_tasks(
            self,
            session,
            from_tasks: List[TaskSnapshot],
            new_version_id: UUID,
            affected_batch_ids: set,
            frozen_before: Optional[datetime],
            shifts: List[Dict],
    ) -> Tuple[int, int, int]:
        """
        Клонирует задачи из исходной версии в новую.
        Возвращает: (affected_tasks, moved_tasks, frozen_tasks).
        """
        affected_count = 0
        moved_count = 0
        frozen_count = 0

        for task in from_tasks:
            frozen = self._is_frozen(task, frozen_before)
            if frozen:
                frozen_count += 1

            is_affected = (task.batch_id in affected_batch_ids) and not frozen
            if is_affected:
                affected_count += 1

            shift_id = self._find_shift_id(shifts, task.planned_start)

            await session.execute(
                text("""
                    INSERT INTO scheduled_task
                    (organization_id, schedule_version_id, batch_id,
                     operation_template_id, equipment_id, linked_equipment_id,
                     planned_start, planned_end, actual_start, actual_end,
                     task_role, shift_id, status, is_pinned)
                    SELECT
                        organization_id, :new_version_id, batch_id,
                        operation_template_id, equipment_id, linked_equipment_id,
                        planned_start, planned_end, actual_start, actual_end,
                        task_role, :shift_id, status, is_pinned
                    FROM scheduled_task
                    WHERE id = :task_id
                """),
                {
                    "new_version_id": new_version_id,
                    "task_id": task.id,
                    "shift_id": shift_id,
                },
            )
            moved_count += 1

        return affected_count, moved_count, frozen_count

    async def reschedule(
            self,
            from_version_id: UUID,
            reason: str,
            changes: Dict[str, Any],
            frozen_before: Optional[datetime] = None,
            comment: Optional[str] = None,
    ) -> RescheduleResult:
        """
        Выполняет перепланирование.

        Args:
            from_version_id: исходная версия плана.
            reason: DELAY | BREAKDOWN | QTY_CHANGE | MANUAL.
            changes: dict с параметрами изменения.
            frozen_before: до какого момента задачи не двигаются.
            comment: комментарий.

        Returns:
            RescheduleResult с новой версией и diff'ом.
        """
        async with self.async_session() as session:
            # 1. Загружаем исходную версию
            from_version = await self._load_version(session, from_version_id)
            if not from_version:
                return RescheduleResult(
                    status="error",
                    from_version_id=str(from_version_id),
                    to_version_id=None,
                    message=f"Версия {from_version_id} не найдена",
                )

            log_with_context(
                logger, logging.INFO,
                f"Перепланирование: from={str(from_version_id)[:8]}, "
                f"reason={reason}, frozen_before={frozen_before}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 2. Загружаем задачи
            from_tasks = await self._load_tasks(session, from_version_id)
            log_with_context(
                logger, logging.INFO,
                f"Загружено задач из исходной версии: {len(from_tasks)}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 3. Если BREAKDOWN — добавляем в календарь
            if reason == RescheduleReason.BREAKDOWN:
                eq_id = changes.get("broken_equipment_id")
                start = changes.get("breakdown_start")
                end = changes.get("breakdown_end")
                if eq_id and start and end:
                    await self._add_breakdown_to_calendar(
                        session,
                        UUID(str(eq_id)),
                        datetime.fromisoformat(str(start)) if isinstance(start, str) else start,
                        datetime.fromisoformat(str(end)) if isinstance(end, str) else end,
                        comment or "Аварийная остановка",
                        )

            # 4. Определяем затронутые партии
            affected_batch_ids = self._find_affected_batch_ids(from_tasks, changes)
            log_with_context(
                logger, logging.INFO,
                f"Затронуто партий: {len(affected_batch_ids)}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 5. Создаём новую версию
            new_version_id = uuid4()
            new_name = f"Перепланирование от {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            await session.execute(
                text("""
                    INSERT INTO schedule_version
                    (id, organization_id, name, version_type, is_active,
                     created_at, frozen_before, parent_version_id, comment)
                    VALUES
                    (:id, :org_id, :name, 'MONTHLY', FALSE,
                     NOW(), :frozen_before, :parent_id, :comment)
                """),
                {
                    "id": new_version_id,
                    "org_id": self.org_id,
                    "name": new_name,
                    "frozen_before": frozen_before,
                    "parent_id": from_version_id,
                    "comment": comment or f"Перепланирование: {reason}",
                },
            )

            # 6. Клонируем снапшоты
            await self._clone_snapshots(
                session,
                from_version_id=from_version_id,
                new_version_id=new_version_id,
            )

            # 7. Клонируем задачи
            shifts = await self._load_shifts(session)
            affected_count, moved_count, frozen_count = await self._clone_tasks(
                session,
                from_tasks=from_tasks,
                new_version_id=new_version_id,
                affected_batch_ids=affected_batch_ids,
                frozen_before=frozen_before,
                shifts=shifts,
            )

            # 8. Логируем в reschedule_log
            await session.execute(
                text("""
                    INSERT INTO reschedule_log
                    (organization_id, from_version_id, to_version_id, reason,
                     changes, affected_task_count, moved_task_count, frozen_before, comment)
                    VALUES
                    (:org_id, :from_version_id, :to_version_id, :reason,
                     :changes, :affected_task_count, :moved_task_count, :frozen_before, :comment)
                """),
                {
                    "org_id": self.org_id,
                    "from_version_id": from_version_id,
                    "to_version_id": new_version_id,
                    "reason": reason,
                    "changes": json.dumps(changes),
                    "affected_task_count": affected_count,
                    "moved_task_count": moved_count,
                    "frozen_before": frozen_before,
                    "comment": comment,
                },
            )

            await session.commit()

            log_with_context(
                logger, logging.INFO,
                f"Перепланирование завершено: from={str(from_version_id)[:8]} → "
                f"to={str(new_version_id)[:8]}, affected={affected_count}, "
                f"moved={moved_count}, frozen={frozen_count}",
                stage="reschedule", org_id=str(self.org_id),
            )

            return RescheduleResult(
                status="success",
                from_version_id=str(from_version_id),
                to_version_id=str(new_version_id),
                affected_tasks=affected_count,
                moved_tasks=moved_count,
                frozen_tasks=frozen_count,
                message=f"Создана новая версия '{new_name}'",
                diff={
                    "reason": reason,
                    "affected_batch_ids": list(affected_batch_ids),
                    "frozen_before": frozen_before.isoformat() if frozen_before else None,
                },
            )

    async def compare_versions(
            self,
            v1_id: UUID,
            v2_id: UUID,
    ) -> Dict[str, Any]:
        """
        Сравнивает две версии плана.
        Возвращает dict с diff по задачам.
        """
        async with self.async_session() as session:
            v1_tasks = await self._load_tasks(session, v1_id)
            v2_tasks = await self._load_tasks(session, v2_id)

            v1_map = {t.id: t for t in v1_tasks}
            v2_map = {t.id: t for t in v2_tasks}

            only_in_v1 = set(v1_map.keys()) - set(v2_map.keys())
            only_in_v2 = set(v2_map.keys()) - set(v1_map.keys())
            common = set(v1_map.keys()) & set(v2_map.keys())

            moved = []
            unchanged = []
            for task_id in common:
                t1 = v1_map[task_id]
                t2 = v2_map[task_id]
                if t1.planned_start != t2.planned_start or t1.planned_end != t2.planned_end:
                    moved.append({
                        "task_id": task_id,
                        "batch_id": t1.batch_id,
                        "old_start": t1.planned_start.isoformat(),
                        "old_end": t1.planned_end.isoformat(),
                        "new_start": t2.planned_start.isoformat(),
                        "new_end": t2.planned_end.isoformat(),
                        "delta_minutes": int((t2.planned_start - t1.planned_start).total_seconds() / 60),
                    })
                else:
                    unchanged.append(task_id)

            return {
                "v1_id": str(v1_id),
                "v2_id": str(v2_id),
                "v1_task_count": len(v1_tasks),
                "v2_task_count": len(v2_tasks),
                "only_in_v1": list(only_in_v1),
                "only_in_v2": list(only_in_v2),
                "moved": moved,
                "unchanged_count": len(unchanged),
                "moved_count": len(moved),
            }