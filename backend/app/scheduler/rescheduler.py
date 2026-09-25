# backend/app/scheduler/rescheduler.py
"""
Модуль перепланирования (Итерация 4).

Итерация 9 (A3): РЕАЛЬНЫЙ ПЕРЕСЧЁТ РАСПИСАНИЯ.

Раньше rescheduler.py просто клонировал задачи из старой версии
в новую, не пересчитывая расписание. Из-за этого DELAY/BREAKDOWN/
QTY_CHANGE не влияли на план, а поле parent_version_id у новых
версий оставалось NULL.

Теперь логика такая:
  1. Применяем изменения к ВХОДНЫМ ДАННЫМ:
     - BREAKDOWN → INSERT в calendar_event
     - QTY_CHANGE → UPDATE batch.volume_kg
     - DELAY → сдвиг planned_start/planned_end + is_pinned=TRUE
  2. Собираем pinned_tasks (гибридная логика, см. _build_pinned_tasks):
     - is_pinned = TRUE → жёсткий pinned
     - actual_start IS NOT NULL → жёсткий pinned
     - frozen_before → НЕ pinned (только метаданные версии)
  3. Вызываем ProductionScheduler.build_schedule(pinned_tasks=...)
  4. FALLBACK: если solver не нашёл решение с pinned — пробуем без pinned.
  5. Сохраняем результат через ScheduleSaver (он деактивирует старые версии).
  6. Присваиваем новой версии parent_version_id = from_version_id.
  7. Пишем запись в reschedule_log.

Итерация 13.14: ProductionScheduler получает version_id=from_version_id,
чтобы прочитать plan_settings исходного плана (а не глобальные app_settings).
Это гарантирует, что перепланирование использует ТЕ ЖЕ настройки,
с которыми план был построен.

Ключевые гарантии:
  - Явно помеченные is_pinned=TRUE не двигаются.
  - Начатые задачи (actual_start IS NOT NULL) не двигаются.
  - Заблокированные лабораторией партии исключаются из scheduler'а.
  - Все старые версии деактивируются (is_active=FALSE).
  - Если pinned конфликтуют — solver отработает без них с warning.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import UUID

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
    op_id: Optional[str]
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

    # ==========================================
    # ЗАГРУЗКА ДАННЫХ ИЗ БД
    # ==========================================

    async def _load_version(self, session, version_id: UUID) -> Optional[Dict]:
        """Загружает метаданные версии плана."""
        result = await session.execute(
            text("""
                SELECT id, name, version_type, frozen_before,
                       parent_version_id, created_at
                FROM schedule_version
                WHERE id = :version_id AND organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def _load_tasks(self, session, version_id: UUID) -> List[TaskSnapshot]:
        """
        Загружает задачи версии.

        Итерация 5: задачи заблокированных лабораторией партий
        (batch.is_lab_blocked = TRUE) исключаются из выборки — они
        не попадут в pinned и не будут участвовать в пересчёте.
        """
        result = await session.execute(
            text("""
                SELECT
                    st.id::text AS id,
                    st.batch_id::text AS batch_id,
                    st.task_role,
                    st.equipment_id::text AS equipment_id,
                    st.linked_equipment_id::text AS linked_equipment_id,
                    st.planned_start, st.planned_end,
                    st.actual_start, st.actual_end,
                    st.status,
                    COALESCE(st.is_pinned, FALSE) AS is_pinned
                FROM scheduled_task st
                LEFT JOIN batch b ON b.id = st.batch_id
                WHERE st.schedule_version_id = :version_id
                  AND st.organization_id = :org_id
                  AND COALESCE(b.is_lab_blocked, FALSE) = FALSE
                ORDER BY st.planned_start
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )
        return [
            TaskSnapshot(
                id=row.id,
                batch_id=row.batch_id,
                op_id=None,  # в БД нет отдельного op_id; полагаемся на task_role + equipment
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

    # ==========================================
    # ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ К ВХОДНЫМ ДАННЫМ
    # ==========================================

    async def _apply_breakdown(
            self,
            session,
            equipment_id: UUID,
            starts_at: datetime,
            ends_at: datetime,
            comment: str = "Аварийная остановка",
    ) -> None:
        """
        Добавляет BREAKDOWN в calendar_event.

        При следующем построении расписания solver учтёт этот интервал
        как запрет работы на оборудовании.
        """
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
        log_with_context(
            logger, logging.INFO,
            f"A3: добавлен BREAKDOWN для оборудования {str(equipment_id)[:8]}: "
            f"{starts_at} → {ends_at}",
            stage="reschedule", org_id=str(self.org_id),
        )

    async def _apply_qty_change(
            self,
            session,
            batch_ids: List[UUID],
            new_qty: Optional[float] = None,
            scale_factor: Optional[float] = None,
    ) -> None:
        """
        Изменяет объём партий.

        При следующем построении расписания пересчитаются:
          - длительность операций (через duration_formula)
          - количество сырья
        """
        if not batch_ids:
            return

        if new_qty is not None:
            await session.execute(
                text("""
                    UPDATE batch SET volume_kg = :new_qty
                    WHERE id = ANY(:batch_ids) AND organization_id = :org_id
                """),
                {"new_qty": new_qty, "batch_ids": batch_ids, "org_id": self.org_id},
            )
        elif scale_factor is not None:
            await session.execute(
                text("""
                    UPDATE batch SET volume_kg = volume_kg * :scale
                    WHERE id = ANY(:batch_ids) AND organization_id = :org_id
                """),
                {"scale": scale_factor, "batch_ids": batch_ids, "org_id": self.org_id},
            )

        log_with_context(
            logger, logging.INFO,
            f"A3: изменён объём {len(batch_ids)} партий: "
            f"new_qty={new_qty}, scale_factor={scale_factor}",
            stage="reschedule", org_id=str(self.org_id),
        )

    async def _apply_delay(
            self,
            session,
            delayed_task_id: UUID,
            delay_minutes: int,
    ) -> None:
        """
        Применяет задержку к задаче.

        Задача сдвигается на delay_minutes и помечается is_pinned=TRUE,
        чтобы при пересчёте solver не сдвинул её обратно.
        """
        await session.execute(
            text("""
                UPDATE scheduled_task
                SET planned_start = planned_start + (:delay || ' minutes')::interval,
                    planned_end = planned_end + (:delay || ' minutes')::interval,
                    is_pinned = TRUE
                WHERE id = :task_id AND organization_id = :org_id
            """),
            {
                "delay": delay_minutes,
                "task_id": delayed_task_id,
                "org_id": self.org_id,
            },
        )
        log_with_context(
            logger, logging.INFO,
            f"A3: задержка задачи {str(delayed_task_id)[:8]} на {delay_minutes} мин "
            f"(is_pinned=TRUE)",
            stage="reschedule", org_id=str(self.org_id),
        )

    # ==========================================
    # СБОР PINNED_TASKS (гибридная логика)
    # ==========================================

    def _build_pinned_tasks(
            self,
            tasks: List[TaskSnapshot],
            frozen_before: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        """
        Собирает список pinned-задач для ProductionScheduler.

        Итерация 9 (A3, гибридная логика):

        Pinned = задача, если выполняется ХОТЯ БЫ ОДНО условие:
          1. is_pinned = TRUE — пользователь явно заморозил.
          2. actual_start IS NOT NULL — задача уже начата (факт внесён).

        НЕ используется frozen_before для pinned:
          - frozen_before — семантический маркер "перепланируем с этой даты".
          - Он сохраняется как метаданные версии (schedule_version.frozen_before)
            и пишется в reschedule_log, но НЕ превращается в constraints.
          - Причина: попытка жёстко зафиксировать все задачи до frozen_before
            приводила к конфликтам setup-ограничений → "No feasible solution"
            (в тестовой БД было 171 задача до frozen_before).

        ВАЖНО: задачи заблокированных лабораторией партий уже исключены
        на этапе _load_tasks (JOIN batch + фильтр is_lab_blocked = FALSE).
        """
        pinned: List[Dict[str, Any]] = []

        for t in tasks:
            should_pin = False

            # 1. Явная заморозка пользователем
            if t.is_pinned:
                should_pin = True

            # 2. Задача уже начата (мастер внёс фактическое начало)
            if not should_pin and t.actual_start is not None:
                should_pin = True

            if should_pin:
                pinned.append({
                    "batch_id": str(t.batch_id) if t.batch_id else None,
                    "op_id": t.op_id,
                    "task_role": t.task_role,
                    "planned_start": t.planned_start,
                    "planned_end": t.planned_end,
                })

        log_with_context(
            logger, logging.INFO,
            f"A3: _build_pinned_tasks: pinned={len(pinned)} "
            f"(из {len(tasks)} задач; "
            f"is_pinned/started; frozen_before={frozen_before} игнорируется для pinned)",
            stage="reschedule", org_id=str(self.org_id),
        )

        return pinned

    # ==========================================
    # ОПРЕДЕЛЕНИЕ ЗАТРОНУТЫХ ПАРТИЙ
    # ==========================================

    def _find_affected_batch_ids(
            self,
            tasks: List[TaskSnapshot],
            changes: Dict[str, Any],
    ) -> set:
        """Определяет партии, затронутые изменением (для лога)."""
        affected: set = set()

        delayed_task_id = changes.get("delayed_task_id")
        if delayed_task_id:
            for t in tasks:
                if t.id == str(delayed_task_id):
                    if t.batch_id:
                        affected.add(t.batch_id)
                    break

        broken_equipment_id = changes.get("broken_equipment_id")
        if broken_equipment_id:
            for t in tasks:
                if (t.equipment_id == str(broken_equipment_id)
                        or t.linked_equipment_id == str(broken_equipment_id)):
                    if t.batch_id:
                        affected.add(t.batch_id)

        explicit_batch_ids = changes.get("affected_batch_ids")
        if explicit_batch_ids:
            for b in explicit_batch_ids:
                affected.add(str(b))

        return affected

    # ==========================================
    # ОСНОВНОЙ МЕТОД: RESCHEDULE
    # ==========================================

    async def reschedule(
            self,
            from_version_id: UUID,
            reason: str,
            changes: Dict[str, Any],
            frozen_before: Optional[datetime] = None,
            comment: Optional[str] = None,
    ) -> RescheduleResult:
        """
        Выполняет перепланирование с реальным пересчётом.

        Шаги:
          1. Загрузить исходную версию и её задачи.
          2. Применить изменения к входным данным.
          3. Собрать pinned_tasks.
          4. Запустить ProductionScheduler.build_schedule(pinned_tasks).
          5. FALLBACK: если solver не нашёл решение с pinned — пересчёт без них.
          6. Сохранить результат через ScheduleSaver.
          7. Присвоить parent_version_id новой версии.
          8. Записать в reschedule_log.

        Итерация 13.14: ProductionScheduler получает version_id=from_version_id,
        чтобы прочитать plan_settings исходного плана (а не глобальные
        app_settings). Это гарантирует, что перепланирование использует
        ТЕ ЖЕ настройки, с которыми план был построен.

        Args:
            from_version_id: Исходная версия.
            reason: DELAY | BREAKDOWN | QTY_CHANGE | MANUAL.
            changes: Параметры изменения.
            frozen_before: Заморозить задачи до этого момента (метаданные).
            comment: Комментарий к перепланированию.

        Returns:
            RescheduleResult с to_version_id — ID новой версии.
        """
        # Локальный импорт во избежание циклической зависимости
        from app.scheduler.core import ProductionScheduler
        from app.scheduler.saver import ScheduleSaver

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
                f"A3: ПЕРЕПЛАНИРОВАНИЕ START: from={str(from_version_id)[:8]}, "
                f"reason={reason}, frozen_before={frozen_before}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 2. Загружаем задачи исходной версии (для pinned и affected)
            from_tasks = await self._load_tasks(session, from_version_id)
            log_with_context(
                logger, logging.INFO,
                f"A3: загружено задач из исходной версии: {len(from_tasks)}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 3. Применяем изменения к входным данным
            if reason == RescheduleReason.BREAKDOWN:
                eq_id = changes.get("broken_equipment_id")
                start = changes.get("breakdown_start")
                end = changes.get("breakdown_end")
                if eq_id and start and end:
                    await self._apply_breakdown(
                        session,
                        UUID(str(eq_id)),
                        datetime.fromisoformat(str(start)) if isinstance(start, str) else start,
                        datetime.fromisoformat(str(end)) if isinstance(end, str) else end,
                        comment or "Аварийная остановка",
                        )

            elif reason == RescheduleReason.QTY_CHANGE:
                batch_ids_raw = changes.get("affected_batch_ids", [])
                batch_ids = [UUID(str(b)) for b in batch_ids_raw]
                await self._apply_qty_change(
                    session,
                    batch_ids,
                    new_qty=changes.get("new_qty"),
                    scale_factor=changes.get("scale_factor"),
                )

            elif reason == RescheduleReason.DELAY:
                delayed_task_id = changes.get("delayed_task_id")
                delay_minutes = changes.get("delay_minutes", 60)
                if delayed_task_id:
                    await self._apply_delay(
                        session,
                        UUID(str(delayed_task_id)),
                        delay_minutes,
                    )

            await session.commit()

            # 4. Собираем pinned_tasks
            pinned_tasks = self._build_pinned_tasks(from_tasks, frozen_before)
            log_with_context(
                logger, logging.INFO,
                f"A3: собрано pinned_tasks: {len(pinned_tasks)} "
                f"(frozen_before={frozen_before})",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 5. Запускаем ProductionScheduler с version_id=from_version_id
            #    (Итерация 13.14: настройки читаются из plan_settings плана)
            scheduler = ProductionScheduler(
                horizon_hours=2160,
                org_id=self.org_id,
                version_id=from_version_id,
            )
            schedule_result = await scheduler.build_schedule(
                pinned_tasks=pinned_tasks,
            )

            # 6. FALLBACK: если solver не нашёл решение с pinned —
            # пробуем без pinned. Лучше дать валидный план с предупреждением,
            # чем 500-ку.
            fallback_used = False
            if "error" in schedule_result and pinned_tasks:
                log_with_context(
                    logger, logging.WARNING,
                    f"A3: solver не нашёл решение с pinned "
                    f"({len(pinned_tasks)} задач). Пробуем БЕЗ pinned...",
                    stage="reschedule", org_id=str(self.org_id),
                )
                scheduler2 = ProductionScheduler(
                    horizon_hours=2160,
                    org_id=self.org_id,
                    version_id=from_version_id,
                )
                schedule_result = await scheduler2.build_schedule(
                    pinned_tasks=None,
                )
                if "error" not in schedule_result:
                    fallback_used = True
                    pinned_tasks = []  # для diff

            if "error" in schedule_result:
                log_with_context(
                    logger, logging.ERROR,
                    f"A3: пересчёт не удался даже без pinned: "
                    f"{schedule_result['error']}",
                    stage="reschedule", org_id=str(self.org_id),
                )
                return RescheduleResult(
                    status="error",
                    from_version_id=str(from_version_id),
                    to_version_id=None,
                    message=f"Пересчёт не удался: {schedule_result['error']}",
                )

            log_with_context(
                logger, logging.INFO,
                f"A3: пересчёт успешен, задач={schedule_result.get('total_tasks', 0)}, "
                f"makespan={schedule_result.get('makespan_minutes', 0):.0f} мин, "
                f"fallback_used={fallback_used}",
                stage="reschedule", org_id=str(self.org_id),
            )

            # 7. Сохраняем через ScheduleSaver
            # Saver САМ деактивирует старые версии (см. hotfix Итерации 5).
            saver = ScheduleSaver(org_id=self.org_id)
            save_stats = await saver.save_schedule(schedule_result)
            new_version_id = save_stats["version_id"]

            # 8. Обновляем метаданные новой версии:
            #    parent_version_id = from_version_id, frozen_before, comment.
            await session.execute(
                text("""
                    UPDATE schedule_version
                    SET parent_version_id = :parent_id,
                        frozen_before = :frozen_before,
                        comment = :comment
                    WHERE id = :new_version_id
                      AND organization_id = :org_id
                """),
                {
                    "parent_id": from_version_id,
                    "frozen_before": frozen_before,
                    "comment": comment or f"Перепланирование: {reason}",
                    "new_version_id": new_version_id,
                    "org_id": self.org_id,
                },
            )

            # 9. Пишем запись в reschedule_log
            affected_batch_ids = list(self._find_affected_batch_ids(from_tasks, changes))
            await session.execute(
                text("""
                    INSERT INTO reschedule_log
                    (organization_id, from_version_id, to_version_id, reason,
                     changes, affected_task_count, moved_task_count,
                     frozen_before, comment)
                    VALUES
                    (:org_id, :from_version_id, :to_version_id, :reason,
                     :changes, :affected_task_count, :moved_task_count,
                     :frozen_before, :comment)
                """),
                {
                    "org_id": self.org_id,
                    "from_version_id": from_version_id,
                    "to_version_id": new_version_id,
                    "reason": reason,
                    "changes": json.dumps(changes, default=str),
                    "affected_task_count": len(affected_batch_ids),
                    "moved_task_count": save_stats["tasks_saved"],
                    "frozen_before": frozen_before,
                    "comment": comment,
                },
            )

            await session.commit()

            log_with_context(
                logger, logging.INFO,
                f"A3: ПЕРЕПЛАНИРОВАНИЕ DONE: from={str(from_version_id)[:8]} → "
                f"to={str(new_version_id)[:8]}, tasks={save_stats['tasks_saved']}, "
                f"pinned={len(pinned_tasks)}, fallback={fallback_used}",
                stage="reschedule", org_id=str(self.org_id),
            )

            return RescheduleResult(
                status="success",
                from_version_id=str(from_version_id),
                to_version_id=str(new_version_id),
                affected_tasks=len(affected_batch_ids),
                moved_tasks=save_stats["tasks_saved"],
                frozen_tasks=len(pinned_tasks),
                message=(
                        f"Создана новая версия плана (пересчитано "
                        f"{save_stats['tasks_saved']} задач, pinned={len(pinned_tasks)}"
                        + (", fallback без pinned" if fallback_used else "")
                        + ")"
                ),
                diff={
                    "reason": reason,
                    "affected_batch_ids": affected_batch_ids,
                    "frozen_before": frozen_before.isoformat() if frozen_before else None,
                    "pinned_count": len(pinned_tasks),
                    "deactivated_versions": save_stats.get("deactivated_versions", 0),
                    "fallback_used": fallback_used,
                },
            )

    # ==========================================
    # СРАВНЕНИЕ ВЕРСИЙ
    # ==========================================

    async def compare_versions(
            self,
            v1_id: UUID,
            v2_id: UUID,
    ) -> Dict[str, Any]:
        """
        Сравнивает две версии плана.

        Возвращает:
          - moved: список задач, изменивших время
          - unchanged_count: сколько задач не изменилось
          - only_in_v1 / only_in_v2: задачи, которых нет в другой версии

        ВАЖНО (Итерация 9): после реального пересчёта задач в новой
        версии могут быть новые task_id (solver строит заново), поэтому
        only_in_v1 / only_in_v2 могут быть большими. Это ожидаемое
        поведение. Правильное сопоставление задач — по
        (batch_id, task_role, equipment_id) — задача Итерации 10.
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
                if (t1.planned_start != t2.planned_start
                        or t1.planned_end != t2.planned_end):
                    delta = (t2.planned_start - t1.planned_start).total_seconds() / 60
                    moved.append({
                        "task_id": task_id,
                        "batch_id": t1.batch_id,
                        "old_start": t1.planned_start.isoformat() if t1.planned_start else None,
                        "old_end": t1.planned_end.isoformat() if t1.planned_end else None,
                        "new_start": t2.planned_start.isoformat() if t2.planned_start else None,
                        "new_end": t2.planned_end.isoformat() if t2.planned_end else None,
                        "delta_minutes": int(delta),
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