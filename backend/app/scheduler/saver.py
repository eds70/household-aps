# backend/app/scheduler/saver.py
"""
Сохранение результатов планирования в БД.

Итерация 3: _find_shift_for_time имеет fallback.
Итерация 5 (hotfix): деактивация старых версий.
Итерация 6: сохранение operator_pool в scheduled_task.
Итерация 7: сохранение cooling_mode в scheduled_task.

Итерация 9 (fix #1):
  - Для LINE_FILL (динамические fill_*) equipment_id = линия (secondary),
    а linked_equipment_id = реактор/танк (primary).
    Раньше задача слива привязывалась к реактору, что физически неверно.
  - Добавлено сохранение operation_name — фактического имени операции.
    Для fill_* нет operation_template_id, поэтому имя бралось из fallback-
    шаблона (первая операция партии), что вводило в заблуждение.

Итерация 12 (what-if):
  - ScheduleSaver теперь принимает опциональную session.
    Это позволяет what-if сценариям использовать savepoint:
    сохранять новую версию плана внутри той же сессии,
    что и временные изменения (которые потом откатываются).
  - Если session не передана — создаём свою (обратная совместимость).
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from .logging_config import setup_scheduler_logging, log_with_context
from .shifts import find_shift_id_for_time

logger = setup_scheduler_logging(level=logging.INFO)


class ScheduleSaver:
    def __init__(
            self,
            org_id: UUID,
            session: Optional[AsyncSession] = None,
    ):
        """
        Итерация 12: опциональная session.

        Args:
            org_id: UUID организации.
            session: если передана — используем её (для what-if savepoint).
                     если None — создаём свою (обратная совместимость).
        """
        self.org_id = org_id

        if session is not None:
            # Итерация 12: используем переданную сессию.
            # В этом режиме НЕ создаём engine — сессия принадлежит вызывающему.
            self.async_session = session
            self.engine = None
            self._owns_session = False
        else:
            # Обратная совместимость: создаём свою сессию.
            self.engine = create_async_engine(
                settings.DATABASE_URL, echo=False
            )
            self._session_maker = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self.async_session = None  # создадим в save_schedule
            self._owns_session = True

    async def _has_column(self, session, table: str, column: str) -> bool:
        """Проверяет, существует ли колонка в таблице."""
        result = await session.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
            """),
            {"table": table, "column": column},
        )
        return result.fetchone() is not None

    async def _load_shifts(self, session) -> List[Dict]:
        """Загружает все смены организации."""
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
        """Приводит datetime к naive (без таймзоны)."""
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

    def _find_shift_for_time(
            self, shifts: List[Dict], dt: datetime
    ) -> Optional[str]:
        """
        Итерация 9 (B1): обёртка над shifts.find_shift_id_for_time.
        Единая логика для saver.py и rescheduler.py.
        """
        return find_shift_id_for_time(shifts, dt)

    async def save_schedule(
            self, schedule_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Сохраняет построенный план в БД.

        Итерация 12: если session передана в __init__ — используем её
        (для what-if savepoint). Иначе — создаём свою сессию
        (обратная совместимость).

        Args:
            schedule_data: результат ProductionScheduler.build_schedule():

        Returns:
            Статистика сохранения.
        """
        tasks = schedule_data["tasks"]

        # Итерация 12: определяем, использовать ли переданную сессию.
        if self._owns_session:
            # Создаём свою сессию (обратная совместимость).
            async with self._session_maker() as session:
                return await self._do_save(session, tasks)
        else:
            # Используем переданную сессию (what-if savepoint).
            # НЕ закрываем и НЕ коммитим — это делает вызывающий.
            return await self._do_save(self.async_session, tasks)

    async def _do_save(
            self,
            session: AsyncSession,
            tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Основная логика сохранения.

        Работает с переданной сессией. Коммит делает вызывающий
        (для what-if — savepoint откатится; для обычного режима —
        коммитим в конце).
        """
        version_id = uuid4()
        plan_name = f"План от {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # ==========================================
        # 1. Деактивация старых версий (hotfix Итерации 5)
        # ==========================================
        deactivate_result = await session.execute(
            text("""
                UPDATE schedule_version
                SET is_active = FALSE
                WHERE organization_id = :org_id AND is_active = TRUE
            """),
            {"org_id": self.org_id},
        )
        deactivated_count = deactivate_result.rowcount or 0
        if deactivated_count > 0:
            log_with_context(
                logger, logging.INFO,
                f"Деактивировано старых версий: {deactivated_count}",
                stage="save", org_id=str(self.org_id),
            )

        # ==========================================
        # 2. Создание новой версии плана
        # ==========================================
        await session.execute(
            text("""
                INSERT INTO schedule_version
                    (id, organization_id, name, version_type, is_active, created_at)
                VALUES
                    (:id, :org_id, :name, 'MONTHLY', TRUE, NOW())
            """),
            {"id": version_id, "org_id": self.org_id, "name": plan_name},
        )

        # ==========================================
        # 3. Снапшоты справочников
        # ==========================================
        await session.execute(
            text("""
                INSERT INTO equipment_snapshot
                    (id, organization_id, code, name, type, volume_kg,
                     speed_coeff, mixer_type, is_active, version_id)
                SELECT id, organization_id, code, name, type, volume_kg,
                       speed_coeff, mixer_type, is_active, :version_id
                FROM equipment
                WHERE organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )

        await session.execute(
            text("""
                INSERT INTO product_snapshot
                    (id, organization_id, code, name, type, viscosity_coeff,
                     requires_heating, bottle_volume_l, fill_speed_per_min,
                     parent_pf_id, route_type, version_id)
                SELECT id, organization_id, code, name, type, viscosity_coeff,
                       requires_heating, bottle_volume_l, fill_speed_per_min,
                       parent_pf_id, route_type, :version_id
                FROM product
                WHERE organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )

        await session.execute(
            text("""
                INSERT INTO operation_snapshot
                    (id, organization_id, product_id, stage_order, name,
                     base_duration_mins, is_setup, is_parallel_group,
                     parallel_group_id, needs_boiler, needs_cooling_zone,
                     needs_operator, needs_lab, duration_formula,
                     operator_pool, comment, version_id)
                SELECT id, organization_id, product_id, stage_order, name,
                       base_duration_mins, is_setup, is_parallel_group,
                       parallel_group_id, needs_boiler, needs_cooling_zone,
                       needs_operator, needs_lab, duration_formula,
                       operator_pool, comment, :version_id
                FROM operation_template
                WHERE organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )

        await session.execute(
            text("""
                INSERT INTO calendar_snapshot
                    (id, organization_id, equipment_id, event_type,
                     starts_at, ends_at, comment, version_id)
                SELECT id, organization_id, equipment_id, event_type,
                       starts_at, ends_at, comment, :version_id
                FROM calendar_event
                WHERE organization_id = :org_id
            """),
            {"version_id": version_id, "org_id": self.org_id},
        )

        # ==========================================
        # 4. Проверяем, какие колонки доступны в scheduled_task
        # ==========================================
        has_linked = await self._has_column(
            session, "scheduled_task", "linked_equipment_id"
        )
        has_role = await self._has_column(
            session, "scheduled_task", "task_role"
        )
        has_shift = await self._has_column(
            session, "scheduled_task", "shift_id"
        )
        has_status = await self._has_column(
            session, "scheduled_task", "status"
        )
        has_operator_pool = await self._has_column(
            session, "scheduled_task", "operator_pool"
        )
        has_cooling_mode = await self._has_column(
            session, "scheduled_task", "cooling_mode"
        )
        has_operation_name = await self._has_column(
            session, "scheduled_task", "operation_name"
        )

        shifts = await self._load_shifts(session) if has_shift else []
        log_with_context(
            logger, logging.INFO,
            f"Загружено смен для привязки: {len(shifts)}",
            stage="save", org_id=str(self.org_id),
        )

        # ==========================================
        # 5. Сохраняем задачи
        # ==========================================
        shift_matched = 0
        shift_none = 0
        cooling_fast_count = 0
        cooling_slow_count = 0
        line_fill_fixed = 0

        for task in tasks:
            op_id = task["op_id"]
            is_real_op = not str(op_id).startswith("fill_")

            # ==========================================
            # 5.1. Fallback operation_template_id для fill_*
            # ==========================================
            if not is_real_op:
                fallback_op_id = None
                for t in tasks:
                    if (
                            t["batch_id"] == task["batch_id"]
                            and not str(t["op_id"]).startswith("fill_")
                    ):
                        fallback_op_id = t["op_id"]
                        break
                if fallback_op_id is None:
                    log_with_context(
                        logger, logging.WARNING,
                        f"Пропущена задача {op_id}: нет fallback "
                        f"operation_template_id для партии "
                        f"{task['batch_id'][:8]}",
                        stage="save", org_id=str(self.org_id),
                    )
                    continue
                op_id_for_db = fallback_op_id
            else:
                op_id_for_db = op_id

            # ==========================================
            # 5.2. Привязка к смене
            # ==========================================
            shift_id = None
            if has_shift:
                shift_id = self._find_shift_for_time(shifts, task["start"])
                if shift_id:
                    shift_matched += 1
                else:
                    shift_none += 1

            # ==========================================
            # 5.3. Cooling mode (Итерация 7)
            # ==========================================
            cooling_mode = task.get("cooling_mode")
            if cooling_mode == "fast":
                cooling_fast_count += 1
            elif cooling_mode == "slow":
                cooling_slow_count += 1

            # ==========================================
            # 5.4. Итерация 9 (fix): правильная привязка LINE_FILL
            # ==========================================
            task_role = task.get("role")
            is_line_fill = (
                    task_role == "LINE_FILL"
                    or str(task.get("op_id", "")).startswith("fill_")
            )

            primary_eq = task.get("equipment_id")
            secondary_eq = task.get("linked_equipment_id")

            if is_line_fill and secondary_eq:
                eq_id_for_db = secondary_eq
                linked_eq_id_for_db = primary_eq
                line_fill_fixed += 1
            else:
                eq_id_for_db = primary_eq
                linked_eq_id_for_db = secondary_eq

            # ==========================================
            # 5.5. Формируем словарь для INSERT
            # ==========================================
            insert_data = {
                "org_id": self.org_id,
                "version_id": version_id,
                "batch_id": task["batch_id"],
                "op_id": op_id_for_db,
                "eq_id": eq_id_for_db,
                "linked_eq_id": linked_eq_id_for_db,
                "start": task["start"],
                "end": task["end"],
                "role": task_role,
                "shift_id": shift_id,
                "operator_pool": task.get("operator_pool"),
                "cooling_mode": cooling_mode,
                "operation_name": task.get("operation_name", "Операция"),
            }

            # ==========================================
            # 5.6. Собираем список колонок и значений
            # ==========================================
            columns = [
                "organization_id", "schedule_version_id", "batch_id",
                "operation_template_id", "equipment_id",
                "planned_start", "planned_end",
            ]
            values = [
                ":org_id", ":version_id", ":batch_id",
                ":op_id", ":eq_id",
                ":start", ":end",
            ]

            if has_linked:
                columns.append("linked_equipment_id")
                values.append(":linked_eq_id")
            if has_role:
                columns.append("task_role")
                values.append(":role")
            if has_shift:
                columns.append("shift_id")
                values.append(":shift_id")
            if has_status:
                columns.append("status")
                values.append("'PLANNED'")
            if has_operator_pool:
                columns.append("operator_pool")
                values.append(":operator_pool")
            if has_cooling_mode:
                columns.append("cooling_mode")
                values.append(":cooling_mode")
            if has_operation_name:
                columns.append("operation_name")
                values.append(":operation_name")

            columns.append("is_pinned")
            values.append("FALSE")

            query = text(f"""
                INSERT INTO scheduled_task ({', '.join(columns)})
                VALUES ({', '.join(values)})
            """)

            await session.execute(query, insert_data)

        # ==========================================
        # 6. Commit — ТОЛЬКО если saver владеет сессией
        # ==========================================
        # Итерация 12: если сессия передана извне (what-if),
        # НЕ коммитим — коммит/откат делает вызывающий.
        if self._owns_session:
            await session.commit()

        log_with_context(
            logger, logging.INFO,
            f"Сохранено задач: {len(tasks)}. "
            f"Привязка к сменам: matched={shift_matched}, none={shift_none}. "
            f"Cooling: fast={cooling_fast_count}, slow={cooling_slow_count}. "
            f"LINE_FILL перепривязано к линии: {line_fill_fixed}. "
            f"owns_session={self._owns_session}",
            stage="save", org_id=str(self.org_id),
        )

        return {
            "version_id": version_id,
            "name": plan_name,
            "tasks_saved": len(tasks),
            "deactivated_versions": deactivated_count,
            "cooling_fast": cooling_fast_count,
            "cooling_slow": cooling_slow_count,
            "line_fill_fixed": line_fill_fixed,
        }