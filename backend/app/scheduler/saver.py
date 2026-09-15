# backend/app/scheduler/saver.py
import asyncio
from datetime import datetime
from uuid import UUID, uuid4
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


class ScheduleSaver:
    def __init__(self, org_id: UUID):
        self.org_id = org_id
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        tasks = schedule_data["tasks"]
        async with self.async_session() as session:
            version_id = uuid4()
            plan_name = f"План от {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            # 1. Создаем версию плана
            await session.execute(
                text("""
                    INSERT INTO schedule_version (id, organization_id, name, version_type, is_active, created_at)
                    VALUES (:id, :org_id, :name, 'MONTHLY', TRUE, NOW())
                """),
                {"id": version_id, "org_id": self.org_id, "name": plan_name},
            )

            # 2. Делаем снимки текущих справочников (только для текущей организации)
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

            # 3. Сохраняем задачи расписания
            for task in tasks:
                await session.execute(
                    text("""
                        INSERT INTO scheduled_task (organization_id, schedule_version_id, batch_id, operation_template_id, equipment_id, planned_start, planned_end, is_pinned)
                        VALUES (:org_id, :version_id, :batch_id, :op_id, :eq_id, :start, :end, FALSE)
                    """),
                    {
                        "org_id": self.org_id,
                        "version_id": version_id,
                        "batch_id": task["batch_id"],
                        "op_id": task["op_id"],
                        "eq_id": task["equipment_id"],
                        "start": task["start"],
                        "end": task["end"],
                    },
                )

            await session.commit()
            return {"version_id": version_id, "name": plan_name, "tasks_saved": len(tasks)}