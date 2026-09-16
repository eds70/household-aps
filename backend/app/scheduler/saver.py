# backend/app/scheduler/saver.py
"""
Сохранение результатов планирования в БД.

Итерация 3 (доработка):
- _find_shift_for_time имеет fallback: если задача вне окна смены,
  привязываем к ближайшей смене (по abs-разнице со starts_at).
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID, uuid4
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from .logging_config import setup_scheduler_logging, log_with_context


logger = setup_scheduler_logging(level=logging.INFO)


class ScheduleSaver:
    def __init__(self, org_id: UUID):
        self.org_id = org_id
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def _has_column(self, session, table: str, column: str) -> bool:
        result = await session.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
            """),
            {"table": table, "column": column},
        )
        return result.fetchone() is not None

    async def _load_shifts(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id, starts_at, ends_at FROM shift
                WHERE organization_id = :org_id
                ORDER BY starts_at
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    def _to_naive(self, dt: datetime) -> datetime:
        """Убирает tzinfo для сравнения."""
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

    def _find_shift_for_time(self, shifts: List[Dict], dt: datetime) -> Optional[str]:
        """
        Определяет shift_id по времени начала задачи.

        Алгоритм:
          1. Если dt попадает в окно [starts_at, ends_at] — берём эту смену.
          2. Иначе — берём смену с ближайшим starts_at (по abs-разнице).
             Это позволяет привязать ночные задачи к вечерней или утренней смене.
        """
        if not shifts:
            return None

        dt_naive = self._to_naive(dt)

        # Шаг 1: точное попадание в окно смены
        for shift in shifts:
            start = self._to_naive(shift["starts_at"])
            end = self._to_naive(shift["ends_at"])
            if start <= dt_naive <= end:
                return str(shift["id"])

        # Шаг 2: fallback — ближайшая смена по starts_at
        closest_shift = None
        closest_diff = None

        for shift in shifts:
            start = self._to_naive(shift["starts_at"])
            diff = abs((dt_naive - start).total_seconds())
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest_shift = shift

        if closest_shift is not None:
            return str(closest_shift["id"])

        return None

    async def save_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        tasks = schedule_data["tasks"]
        async with self.async_session() as session:
            version_id = uuid4()
            plan_name = f"План от {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            # 1. Версия плана
            await session.execute(
                text("""
                    INSERT INTO schedule_version (id, organization_id, name, version_type, is_active, created_at)
                    VALUES (:id, :org_id, :name, 'MONTHLY', TRUE, NOW())
                """),
                {"id": version_id, "org_id": self.org_id, "name": plan_name},
            )

            # 2. Снапшоты
            await session.execute(
                text("""
                    INSERT INTO equipment_snapshot (id, organization_id, code, name, type, volume_kg, speed_coeff, mixer_type, is_active, version_id)
                    SELECT id, organization_id, code, name, type, volume_kg, speed_coeff, mixer_type, is_active, :version_id FROM equipment
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            await session.execute(
                text("""
                    INSERT INTO product_snapshot (id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type, version_id)
                    SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type, :version_id FROM product
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            await session.execute(
                text("""
                    INSERT INTO operation_snapshot (id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, operator_pool, comment, version_id)
                    SELECT id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, operator_pool, comment, :version_id FROM operation_template
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            await session.execute(
                text("""
                    INSERT INTO calendar_snapshot (id, organization_id, equipment_id, event_type, starts_at, ends_at, comment, version_id)
                    SELECT id, organization_id, equipment_id, event_type, starts_at, ends_at, comment, :version_id FROM calendar_event
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            # 3. Проверяем колонки
            has_linked = await self._has_column(session, "scheduled_task", "linked_equipment_id")
            has_role = await self._has_column(session, "scheduled_task", "task_role")
            has_shift = await self._has_column(session, "scheduled_task", "shift_id")
            has_status = await self._has_column(session, "scheduled_task", "status")

            # Загружаем смены
            shifts = await self._load_shifts(session) if has_shift else []
            log_with_context(
                logger, logging.INFO,
                f"Загружено смен для привязки: {len(shifts)}",
                stage="save", org_id=str(self.org_id),
            )

            # 4. Сохраняем задачи
            shift_matched = 0
            shift_fallback = 0
            shift_none = 0

            for task in tasks:
                op_id = task["op_id"]
                is_real_op = not str(op_id).startswith("fill_")

                if not is_real_op:
                    fallback_op_id = None
                    for t in tasks:
                        if (t["batch_id"] == task["batch_id"]
                                and not str(t["op_id"]).startswith("fill_")):
                            fallback_op_id = t["op_id"]
                            break
                    if fallback_op_id is None:
                        continue
                    op_id_for_db = fallback_op_id
                else:
                    op_id_for_db = op_id

                shift_id = None
                if has_shift:
                    shift_id = self._find_shift_for_time(shifts, task["start"])
                    if shift_id:
                        shift_matched += 1
                    else:
                        shift_none += 1

                if has_linked and has_role and has_shift and has_status:
                    await session.execute(
                        text("""
                            INSERT INTO scheduled_task
                            (organization_id, schedule_version_id, batch_id,
                             operation_template_id, equipment_id, linked_equipment_id,
                             planned_start, planned_end, task_role, shift_id, status, is_pinned)
                            VALUES (:org_id, :version_id, :batch_id, :op_id, :eq_id,
                                    :linked_eq_id, :start, :end, :role, :shift_id, 'PLANNED', FALSE)
                        """),
                        {
                            "org_id": self.org_id,
                            "version_id": version_id,
                            "batch_id": task["batch_id"],
                            "op_id": op_id_for_db,
                            "eq_id": task["equipment_id"],
                            "linked_eq_id": task.get("linked_equipment_id"),
                            "start": task["start"],
                            "end": task["end"],
                            "role": task.get("role"),
                            "shift_id": shift_id,
                        },
                    )
                elif has_linked and has_role:
                    await session.execute(
                        text("""
                            INSERT INTO scheduled_task
                            (organization_id, schedule_version_id, batch_id,
                             operation_template_id, equipment_id, linked_equipment_id,
                             planned_start, planned_end, task_role, is_pinned)
                            VALUES (:org_id, :version_id, :batch_id, :op_id, :eq_id,
                                    :linked_eq_id, :start, :end, :role, FALSE)
                        """),
                        {
                            "org_id": self.org_id,
                            "version_id": version_id,
                            "batch_id": task["batch_id"],
                            "op_id": op_id_for_db,
                            "eq_id": task["equipment_id"],
                            "linked_eq_id": task.get("linked_equipment_id"),
                            "start": task["start"],
                            "end": task["end"],
                            "role": task.get("role"),
                        },
                    )
                else:
                    await session.execute(
                        text("""
                            INSERT INTO scheduled_task
                            (organization_id, schedule_version_id, batch_id,
                             operation_template_id, equipment_id,
                             planned_start, planned_end, is_pinned)
                            VALUES (:org_id, :version_id, :batch_id, :op_id, :eq_id,
                                    :start, :end, FALSE)
                        """),
                        {
                            "org_id": self.org_id,
                            "version_id": version_id,
                            "batch_id": task["batch_id"],
                            "op_id": op_id_for_db,
                            "eq_id": task["equipment_id"],
                            "start": task["start"],
                            "end": task["end"],
                        },
                    )

            await session.commit()

            log_with_context(
                logger, logging.INFO,
                f"Привязка к сменам: matched={shift_matched}, "
                f"fallback={shift_fallback}, none={shift_none}",
                stage="save", org_id=str(self.org_id),
            )

            return {
                "version_id": version_id,
                "name": plan_name,
                "tasks_saved": len(tasks),
            }