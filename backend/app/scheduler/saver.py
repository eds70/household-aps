# backend/app/scheduler/saver.py
"""
Сохранение результатов планирования в БД.

Итерация 1:
- Сохраняет linked_equipment_id и task_role (если колонки существуют)
- Совместим со старой схемой (проверяет наличие колонок)
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID, uuid4
from typing import Dict, Any
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
        """Проверяет, существует ли колонка в таблице (для обратной совместимости)."""
        result = await session.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
            """),
            {"table": table, "column": column},
        )
        return result.fetchone() is not None

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

            # 2. Снапшоты справочников
            await session.execute(
                text("""
                    INSERT INTO equipment_snapshot (id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active, version_id)
                    SELECT id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active, :version_id FROM equipment
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            await session.execute(
                text("""
                    INSERT INTO product_snapshot (id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, version_id)
                    SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, :version_id FROM product
                    WHERE organization_id = :org_id
                """),
                {"version_id": version_id, "org_id": self.org_id},
            )

            await session.execute(
                text("""
                    INSERT INTO operation_snapshot (id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, comment, version_id)
                    SELECT id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, comment, :version_id FROM operation_template
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

            # 3. Проверяем наличие колонок для связанных задач
            has_linked = await self._has_column(session, "scheduled_task", "linked_equipment_id")
            has_role = await self._has_column(session, "scheduled_task", "task_role")

            # 4. Сохраняем задачи
            for task in tasks:
                op_id = task["op_id"]
                # Если op_id — синтетический (fill_XXX), не пытаемся вставить его как UUID
                is_real_op = not str(op_id).startswith("fill_")

                # Для операций, которых нет в operation_template, используем
                # первую попавшуюся реальную операцию партии как заглушку
                # (в будущем — заведём виртуальные operation_template для слива)
                if not is_real_op:
                    # Ищем любую реальную операцию этой партии
                    fallback_op_id = None
                    for t in tasks:
                        if (t["batch_id"] == task["batch_id"]
                                and not str(t["op_id"]).startswith("fill_")):
                            fallback_op_id = t["op_id"]
                            break
                    if fallback_op_id is None:
                        log_with_context(
                            logger, logging.WARNING,
                            f"Пропускаю задачу {op_id} партии {task['batch_id'][:8]}: "
                            f"нет реальной operation_template",
                            stage="save", org_id=str(self.org_id),
                        )
                        continue
                    op_id_for_db = fallback_op_id
                else:
                    op_id_for_db = op_id

                if has_linked and has_role:
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
                    # Старая схема — без linked_equipment_id и task_role
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
            return {
                "version_id": version_id,
                "name": plan_name,
                "tasks_saved": len(tasks),
            }