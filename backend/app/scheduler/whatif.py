# backend/app/scheduler/whatif.py
"""
What-if сценарии для планировщика (Итерация 12).

Позволяет создавать альтернативные сценарии планирования без изменения
основной БД:
  1. Пользователь выбирает базовый план (schedule_version).
  2. Задаёт изменения (JSONB):
       - orders: [add_order, cancel_order, change_qty, change_due_date]
       - shift_mode: "1x8" | "3x8" | "2x12"
       - resource_capacity: {POOL_TYPE: int}
       - calendar_events: [add, remove]
  3. Запускает расчёт → создаётся новая schedule_version.
  4. Сравнивает с базовым планом.

Механизм (Итерация 12, fix):
  Используем 2 отдельные транзакции вместо savepoint
  (asyncpg + SQLAlchemy 2.0 не поддерживают savepoint так, как ожидалось).

  Транзакция №1 (rollback):
    - Применяем изменения к БД.
    - Запускаем ProductionScheduler (он читает из БД → видит изменения).
    - Получаем schedule_result в память.
    - Делаем rollback — изменения в БД откатываются.

  Транзакция №2 (commit):
    - Сохраняем schedule_result через ScheduleSaver
      (session передаётся извне, saver не делает commit).
    - Обновляем статус сценария и result_version_id.
    - Commit.

Итерация 13.14:
  ProductionScheduler получает version_id=base_version_id, чтобы
  прочитать plan_settings базового плана (а не глобальные app_settings).
  Это гарантирует, что what-if использует ТЕ ЖЕ настройки, с которыми
  был построен базовый план, — иначе сравнение метрик некорректно.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ИСКЛЮЧЕНИЕ ДЛЯ ROLLBACK (сохранено для обратной совместимости)
# ==========================================

class _RollbackSavepoint(Exception):
    """
    Оставлен для обратной совместимости с тестами.

    В текущей реализации (2 транзакции) не используется,
    но остаётся как публичный символ для тестов.
    """
    def __init__(self, payload: Any):
        super().__init__("Rollback savepoint")
        self.payload = payload


# ==========================================
# РЕЗУЛЬТАТ
# ==========================================

@dataclass
class WhatIfRunResult:
    """Результат запуска сценария."""
    status: str
    result_version_id: Optional[UUID] = None
    wall_time_seconds: Optional[float] = None
    message: str = ""
    error_message: Optional[str] = None
    metrics_base: Optional[Dict[str, Any]] = None
    metrics_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "result_version_id": (
                str(self.result_version_id) if self.result_version_id else None
            ),
            "wall_time_seconds": self.wall_time_seconds,
            "message": self.message,
            "error_message": self.error_message,
            "metrics_base": self.metrics_base,
            "metrics_result": self.metrics_result,
        }


# ==========================================
# ОСНОВНОЙ КЛАСС
# ==========================================

class WhatIfRunner:
    """
    Оркестратор what-if сценариев.

    Использование:
        runner = WhatIfRunner(org_id=..., session=...)
        scenario_id = await runner.create_scenario(
            name="+20% заказ",
            base_version_id=...,
            changes={...},
        )
        result = await runner.run_scenario(scenario_id)
        compare = await runner.compare(scenario_id)
    """

    def __init__(self, org_id: UUID, session: AsyncSession):
        self.org_id = org_id
        self.session = session

    # ==========================================
    # CRUD
    # ==========================================

    async def create_scenario(
            self,
            name: str,
            base_version_id: UUID,
            changes: Dict[str, Any],
            comment: Optional[str] = None,
            created_by: Optional[UUID] = None,
    ) -> UUID:
        """
        Создаёт сценарий. Возвращает ID.

        Проверяет, что base_version_id существует и принадлежит org.
        """
        check = await self.session.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE id = :vid AND organization_id = :org_id
            """),
            {"vid": base_version_id, "org_id": self.org_id},
        )
        if not check.fetchone():
            raise ValueError(
                f"Базовая версия {base_version_id} не найдена"
            )

        scenario_id = uuid4()
        await self.session.execute(
            text("""
                INSERT INTO whatif_scenario
                    (id, organization_id, name, comment, base_version_id,
                     changes, status, created_at, updated_at, created_by)
                VALUES
                    (:id, :org_id, :name, :comment, :base_version_id,
                     CAST(:changes AS jsonb), 'DRAFT', NOW(), NOW(), :created_by)
            """),
            {
                "id": scenario_id,
                "org_id": self.org_id,
                "name": name,
                "comment": comment,
                "base_version_id": base_version_id,
                "changes": _json_dumps(changes),
                "created_by": created_by,
            },
        )
        await self.session.commit()

        log_with_context(
            logger, logging.INFO,
            f"Создан what-if сценарий {str(scenario_id)[:8]} "
            f"'{name}' (base={str(base_version_id)[:8]})",
            stage="whatif_create", org_id=str(self.org_id),
        )

        return scenario_id

    async def get_scenario(
            self, scenario_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Возвращает сценарий или None."""
        result = await self.session.execute(
            text("""
                SELECT id, organization_id, name, comment, base_version_id,
                       result_version_id, changes, status,
                       created_at, updated_at, created_by
                FROM whatif_scenario
                WHERE id = :sid AND organization_id = :org_id
            """),
            {"sid": scenario_id, "org_id": self.org_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return _row_to_scenario(row)

    async def list_scenarios(
            self,
            status: Optional[str] = None,
            limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Список сценариев организации (свежие — первыми)."""
        where = ["organization_id = :org_id"]
        params: Dict[str, Any] = {"org_id": self.org_id, "limit": limit}

        if status:
            where.append("status = :status")
            params["status"] = status

        result = await self.session.execute(
            text(f"""
                SELECT id, name, comment, base_version_id, result_version_id,
                       status, created_at
                FROM whatif_scenario
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            params,
        )
        return [
            {
                "id": row.id,
                "name": row.name,
                "comment": row.comment,
                "base_version_id": row.base_version_id,
                "result_version_id": row.result_version_id,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in result.fetchall()
        ]

    async def update_scenario(
            self,
            scenario_id: UUID,
            name: Optional[str] = None,
            comment: Optional[str] = None,
            changes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Обновляет сценарий. Только в статусе DRAFT.
        Возвращает True, если обновлено.
        """
        check = await self.session.execute(
            text("""
                SELECT status FROM whatif_scenario
                WHERE id = :sid AND organization_id = :org_id
            """),
            {"sid": scenario_id, "org_id": self.org_id},
        )
        row = check.fetchone()
        if not row:
            return False
        if row.status != "DRAFT":
            raise ValueError(
                f"Сценарий в статусе {row.status} нельзя редактировать "
                f"(только DRAFT)"
            )

        updates = []
        params: Dict[str, Any] = {
            "sid": scenario_id,
            "org_id": self.org_id,
        }

        if name is not None:
            updates.append("name = :name")
            params["name"] = name
        if comment is not None:
            updates.append("comment = :comment")
            params["comment"] = comment
        if changes is not None:
            updates.append("changes = CAST(:changes AS jsonb)")
            params["changes"] = _json_dumps(changes)

        if not updates:
            return True

        updates.append("updated_at = NOW()")

        await self.session.execute(
            text(f"""
                UPDATE whatif_scenario
                SET {', '.join(updates)}
                WHERE id = :sid AND organization_id = :org_id
            """),
            params,
        )
        await self.session.commit()
        return True

    async def delete_scenario(self, scenario_id: UUID) -> bool:
        """
        Удаляет сценарий. Только в статусе DRAFT или FAILED.
        Возвращает True, если удалено.
        """
        check = await self.session.execute(
            text("""
                SELECT status FROM whatif_scenario
                WHERE id = :sid AND organization_id = :org_id
            """),
            {"sid": scenario_id, "org_id": self.org_id},
        )
        row = check.fetchone()
        if not row:
            return False
        # Итерация 12 (fix #3): разрешаем удаление и DONE.
        # result_version_id — это отдельная schedule_version,
        # она живёт в истории планов независимо от сценария.
        if row.status == "RUNNING":
            raise ValueError(
                f"Нельзя удалить сценарий в статусе RUNNING — "
                f"дождитесь завершения расчёта"
            )

        await self.session.execute(
            text("""
                DELETE FROM whatif_scenario
                WHERE id = :sid AND organization_id = :org_id
            """),
            {"sid": scenario_id, "org_id": self.org_id},
        )
        await self.session.commit()
        return True

    # ==========================================
    # ЗАПУСК СЦЕНАРИЯ
    # ==========================================

    async def run_scenario(
            self,
            scenario_id: UUID,
            horizon_hours: Optional[int] = None,
            timeout_seconds: Optional[int] = None,
    ) -> WhatIfRunResult:
        """
        Запускает what-if сценарий.

        Итерация 12 (fix #2): убраны явные session.begin().
        В SQLAlchemy 2.0 async-сессия автоматически начинает транзакцию
        при первом execute(). Двойной begin() падает с InvalidRequestError.

        Итерация 13.14: ProductionScheduler получает version_id=base_version_id,
        чтобы прочитать plan_settings базового плана (а не глобальные
        app_settings). Это гарантирует, что сравнение base vs result
        использует одни и те же настройки.
        """
        import time

        log_with_context(
            logger, logging.INFO,
            f"Запуск what-if сценария {str(scenario_id)[:8]}",
            stage="whatif_run", org_id=str(self.org_id),
        )

        # --------------------------------------------------
        # 1. Загружаем сценарий
        # --------------------------------------------------
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return WhatIfRunResult(
                status="FAILED",
                error_message="Сценарий не найден",
            )

        if scenario["status"] not in ("DRAFT", "FAILED", "RUNNING"):
            return WhatIfRunResult(
                status="FAILED",
                error_message=(
                    f"Нельзя запустить сценарий в статусе {scenario['status']}"
                ),
            )

        base_version_id: UUID = scenario["base_version_id"]
        changes: Dict[str, Any] = scenario["changes"] or {}

        # --------------------------------------------------
        # 2. Ставим статус RUNNING (если ещё не RUNNING)
        # --------------------------------------------------
        if scenario["status"] != "RUNNING":
            try:
                await self.session.execute(
                    text("""
                        UPDATE whatif_scenario
                        SET status = 'RUNNING', updated_at = NOW()
                        WHERE id = :sid AND organization_id = :org_id
                    """),
                    {"sid": scenario_id, "org_id": self.org_id},
                )
                await self.session.commit()
            except Exception as e:
                log_with_context(
                    logger, logging.WARNING,
                    f"Не удалось поставить статус RUNNING для "
                    f"{str(scenario_id)[:8]}: {e}",
                    stage="whatif_run", org_id=str(self.org_id),
                )
                try:
                    await self.session.rollback()
                except Exception:
                    pass

        # --------------------------------------------------
        # 3. Транзакция №1: изменения + scheduler → rollback
        # --------------------------------------------------
        # Итерация 12 (fix #2): НЕ вызываем begin() явно.
        # SQLAlchemy async начинает транзакцию автоматически при execute().
        wall_time_start = time.time()
        result_version_id: Optional[UUID] = None
        error_message: Optional[str] = None
        metrics_base: Optional[Dict[str, Any]] = None
        metrics_result: Optional[Dict[str, Any]] = None
        schedule_result: Optional[Dict[str, Any]] = None

        try:
            # Метрики базового плана (автоматически begin).
            metrics_base = await self._compute_metrics(base_version_id)

            # Применяем изменения.
            await self._apply_changes(changes)

            # Определяем horizon/timeout.
            if horizon_hours is None or timeout_seconds is None:
                settings_row = await self.session.execute(
                    text("""
                        SELECT setting_key, setting_value
                        FROM app_settings
                        WHERE organization_id = :org_id
                          AND setting_key IN ('horizon_hours', 'timeout_seconds')
                    """),
                    {"org_id": self.org_id},
                )
                settings = {
                    row.setting_key: row.setting_value
                    for row in settings_row.fetchall()
                }
                if horizon_hours is None:
                    horizon_hours = _read_int(
                        settings.get("horizon_hours"), 720
                    )
                if timeout_seconds is None:
                    timeout_seconds = _read_int(
                        settings.get("timeout_seconds"), 600
                    )

            log_with_context(
                logger, logging.INFO,
                f"[Phase 1] scheduler: horizon={horizon_hours}ч, "
                f"timeout={timeout_seconds}с, base_version={str(base_version_id)[:8]}",
                stage="whatif_run", org_id=str(self.org_id),
            )

            # Запускаем scheduler.
            from .core import ProductionScheduler

            # Итерация 12 (fix): передаём self.session, чтобы
            # DataLoader использовал ту же сессию и видел
            # незакоммиченные изменения из транзакции №1.
            # Итерация 13.14: передаём version_id=base_version_id,
            # чтобы прочитать plan_settings базового плана.
            scheduler = ProductionScheduler(
                horizon_hours=horizon_hours,
                timeout_seconds=timeout_seconds,
                org_id=self.org_id,
                session=self.session,
                version_id=base_version_id,   # ← НОВОЕ (Итерация 13.14)
            )
            schedule_result = await scheduler.build_schedule()

            if "error" in schedule_result:
                error_message = schedule_result["error"]

            # Откатываем транзакцию №1 — изменения в БД отменяются.
            # schedule_result остаётся в памяти.
            await self.session.rollback()

            log_with_context(
                logger, logging.INFO,
                f"[Phase 1] завершён: error={error_message}, "
                f"tasks={len(schedule_result.get('tasks', [])) if schedule_result else 0}",
                stage="whatif_run", org_id=str(self.org_id),
            )

        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            log_with_context(
                logger, logging.ERROR,
                f"Ошибка фазы 1 what-if {str(scenario_id)[:8]}: "
                f"{error_message}",
                stage="whatif_run", org_id=str(self.org_id),
            )
            try:
                await self.session.rollback()
            except Exception:
                pass

        # --------------------------------------------------
        # 4. Транзакция №2: сохраняем результат (только при успехе)
        # --------------------------------------------------
        # Итерация 12 (fix #2): НЕ вызываем begin() явно.
        if not error_message and schedule_result is not None:
            try:
                from .saver import ScheduleSaver

                saver = ScheduleSaver(
                    org_id=self.org_id,
                    session=self.session,
                )
                save_stats = await saver.save_schedule(schedule_result)
                result_version_id = save_stats["version_id"]

                # Метрики результирующего плана.
                metrics_result = await self._compute_metrics(
                    result_version_id
                )

                # Обновляем статус сценария.
                await self.session.execute(
                    text("""
                        UPDATE whatif_scenario
                        SET status = 'DONE',
                            result_version_id = :result_vid,
                            updated_at = NOW()
                        WHERE id = :sid AND organization_id = :org_id
                    """),
                    {
                        "sid": scenario_id,
                        "org_id": self.org_id,
                        "result_vid": result_version_id,
                    },
                )

                # Commit транзакции №2.
                await self.session.commit()

                log_with_context(
                    logger, logging.INFO,
                    f"[Phase 2] сохранено: version="
                    f"{str(result_version_id)[:8]}, "
                    f"tasks={save_stats['tasks_saved']}",
                    stage="whatif_run", org_id=str(self.org_id),
                )

            except Exception as e:
                error_message = f"{type(e).__name__}: {str(e)}"
                log_with_context(
                    logger, logging.ERROR,
                    f"Ошибка фазы 2 what-if {str(scenario_id)[:8]}: "
                    f"{error_message}",
                    stage="whatif_run", org_id=str(self.org_id),
                )
                try:
                    await self.session.rollback()
                except Exception:
                    pass

        wall_time = time.time() - wall_time_start

        # --------------------------------------------------
        # 5. Обработка ошибки
        # --------------------------------------------------
        if error_message or result_version_id is None:
            final_status = "FAILED"
            final_message = error_message or "Не удалось построить план"

            try:
                await self.session.execute(
                    text("""
                        UPDATE whatif_scenario
                        SET status = 'FAILED',
                            comment = COALESCE(comment, '') || :err,
                            updated_at = NOW()
                        WHERE id = :sid AND organization_id = :org_id
                    """),
                    {
                        "sid": scenario_id,
                        "org_id": self.org_id,
                        "err": f"\n[run error] {final_message[:500]}",
                    },
                )
                await self.session.commit()
            except Exception as e:
                log_with_context(
                    logger, logging.ERROR,
                    f"Не удалось записать ошибку в сценарий "
                    f"{str(scenario_id)[:8]}: {e}",
                    stage="whatif_run", org_id=str(self.org_id),
                )
                try:
                    await self.session.rollback()
                except Exception:
                    pass

            return WhatIfRunResult(
                status="FAILED",
                error_message=final_message,
                wall_time_seconds=round(wall_time, 2),
                metrics_base=metrics_base,
            )

        # --------------------------------------------------
        # 6. Успех
        # --------------------------------------------------
        log_with_context(
            logger, logging.INFO,
            f"What-if {str(scenario_id)[:8]} завершён: "
            f"result_version={str(result_version_id)[:8]}, "
            f"wall_time={wall_time:.2f}s",
            stage="whatif_run", org_id=str(self.org_id),
        )

        return WhatIfRunResult(
            status="DONE",
            result_version_id=result_version_id,
            wall_time_seconds=round(wall_time, 2),
            message="План построен",
            metrics_base=metrics_base,
            metrics_result=metrics_result,
        )

    # ==========================================
    # СРАВНЕНИЕ
    # ==========================================

    async def compare(
            self, scenario_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Сравнивает базовый и результирующий планы.
        Возвращает dict с метриками base, result и delta.
        """
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return None

        base_version_id = scenario["base_version_id"]
        result_version_id = scenario["result_version_id"]

        base_metrics = await self._compute_metrics(base_version_id)
        result_metrics = None
        if result_version_id:
            result_metrics = await self._compute_metrics(result_version_id)

        delta: Dict[str, Any] = {}
        if result_metrics:
            delta = {
                "makespan_delta_minutes": (
                        result_metrics["makespan_minutes"]
                        - base_metrics["makespan_minutes"]
                ),
                "makespan_delta_percent": _percent_change(
                    base_metrics["makespan_minutes"],
                    result_metrics["makespan_minutes"],
                ),
                "total_tasks_delta": (
                        result_metrics["total_tasks"]
                        - base_metrics["total_tasks"]
                ),
                "blocked_tasks_delta": (
                        result_metrics["blocked_tasks"]
                        - base_metrics["blocked_tasks"]
                ),
                "cooling_slow_tasks_delta": (
                        result_metrics["cooling_slow_tasks"]
                        - base_metrics["cooling_slow_tasks"]
                ),
                "cz_incomplete_tasks_delta": (
                        result_metrics["cz_incomplete_tasks"]
                        - base_metrics["cz_incomplete_tasks"]
                ),
            }

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "scenario_status": scenario["status"],
            "base_version_id": base_version_id,
            "result_version_id": result_version_id,
            "base_metrics": base_metrics,
            "result_metrics": result_metrics,
            **delta,
        }

    # ==========================================
    # ВНУТРЕННИЕ: ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ
    # ==========================================

    async def _apply_changes(self, changes: Dict[str, Any]) -> None:
        """
        Применяет все изменения к БД (внутри транзакции №1).

        Порядок:
          1. shift_mode (пересоздаёт смены).
          2. resource_capacity.
          3. orders.
          4. calendar_events.
        """
        if not changes:
            return

        if "shift_mode" in changes:
            await self._apply_shift_mode(changes["shift_mode"])

        if "resource_capacity" in changes:
            await self._apply_capacity_changes(changes["resource_capacity"])

        if "orders" in changes and changes["orders"]:
            await self._apply_order_changes(changes["orders"])

        if "calendar_events" in changes and changes["calendar_events"]:
            await self._apply_calendar_changes(changes["calendar_events"])

    async def _apply_shift_mode(self, mode: str) -> None:
        """Меняет shift_mode + пересоздаёт смены."""
        if mode not in ("1x8", "3x8", "2x12"):
            raise ValueError(f"Недопустимый shift_mode: {mode}")

        from .shift_regenerator import regenerate_shifts

        log_with_context(
            logger, logging.INFO,
            f"What-if: применяем shift_mode={mode}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

        await self.session.execute(
            text("""
                UPDATE app_settings
                SET setting_value = CAST(:value AS jsonb),
                    updated_at = NOW()
                WHERE organization_id = :org_id
                  AND setting_key = 'shift_mode'
            """),
            {"org_id": self.org_id, "value": _json_dumps(mode)},
        )

        await regenerate_shifts(
            session=self.session,
            org_id=self.org_id,
            mode=mode,
            reset_shift_ids=True,
        )

    async def _apply_capacity_changes(
            self, capacity: Dict[str, Any]
    ) -> None:
        """Меняет capacity пулов."""
        if not isinstance(capacity, dict):
            raise ValueError("resource_capacity должен быть объектом")

        log_with_context(
            logger, logging.INFO,
            f"What-if: применяем capacity={capacity}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

        for pool_type, new_capacity in capacity.items():
            try:
                cap_int = int(new_capacity)
            except (ValueError, TypeError):
                raise ValueError(
                    f"capacity для {pool_type} должно быть числом"
                )
            if cap_int < 0:
                raise ValueError(
                    f"capacity для {pool_type} не может быть отрицательным"
                )

            await self.session.execute(
                text("""
                    UPDATE resource_pool
                    SET capacity = :cap, updated_at = NOW()
                    WHERE organization_id = :org_id AND type = :ptype
                """),
                {
                    "org_id": self.org_id,
                    "ptype": pool_type,
                    "cap": cap_int,
                },
            )

    async def _apply_order_changes(
            self, orders: List[Dict[str, Any]]
    ) -> None:
        """Применяет изменения заказов."""
        for item in orders:
            action = item.get("action")
            if action == "add_order":
                await self._apply_add_order(item)
            elif action == "cancel_order":
                await self._apply_cancel_order(item)
            elif action == "change_qty":
                await self._apply_change_qty(item)
            elif action == "change_due_date":
                await self._apply_change_due_date(item)
            else:
                raise ValueError(f"Неизвестное действие order: {action}")

    async def _apply_add_order(self, item: Dict[str, Any]) -> None:
        product_code = item.get("product_code")
        target_qty = item.get("target_qty")
        due_date = item.get("due_date")
        priority = int(item.get("priority", 5))

        if not product_code or not target_qty or not due_date:
            raise ValueError(
                "add_order требует product_code, target_qty, due_date"
            )

        result = await self.session.execute(
            text("""
                SELECT id FROM product
                WHERE organization_id = :org_id AND code = :code
            """),
            {"org_id": self.org_id, "code": product_code},
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Продукт {product_code} не найден")

        product_id = row.id

        if isinstance(due_date, str):
            due_date_dt = datetime.fromisoformat(
                due_date.replace("Z", "+00:00")
            )
        elif isinstance(due_date, datetime):
            due_date_dt = due_date
        else:
            raise ValueError(f"Некорректный due_date: {due_date}")

        new_id = uuid4()
        await self.session.execute(
            text("""
                INSERT INTO production_order
                    (id, organization_id, product_id, target_qty, due_date,
                     priority, status, created_at)
                VALUES
                    (:id, :org_id, :product_id, :target_qty, :due_date,
                     :priority, 'PLANNED', NOW())
            """),
            {
                "id": new_id,
                "org_id": self.org_id,
                "product_id": product_id,
                "target_qty": float(target_qty),
                "due_date": due_date_dt,
                "priority": priority,
            },
        )

        log_with_context(
            logger, logging.INFO,
            f"What-if: добавлен заказ {product_code} "
            f"qty={target_qty} due={due_date}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

    async def _apply_cancel_order(self, item: Dict[str, Any]) -> None:
        order_id = item.get("order_id")
        if not order_id:
            raise ValueError("cancel_order требует order_id")

        check = await self.session.execute(
            text("""
                SELECT id FROM production_order
                WHERE id = :oid AND organization_id = :org_id
            """),
            {"oid": order_id, "org_id": self.org_id},
        )
        if not check.fetchone():
            raise ValueError(f"Заказ {order_id} не найден")

        await self.session.execute(
            text("""
                DELETE FROM production_order
                WHERE id = :oid AND organization_id = :org_id
            """),
            {"oid": order_id, "org_id": self.org_id},
        )

        log_with_context(
            logger, logging.INFO,
            f"What-if: отменён заказ {str(order_id)[:8]}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

    async def _apply_change_qty(self, item: Dict[str, Any]) -> None:
        order_id = item.get("order_id")
        new_qty = item.get("new_qty")
        if not order_id or new_qty is None:
            raise ValueError("change_qty требует order_id и new_qty")

        await self.session.execute(
            text("""
                UPDATE production_order
                SET target_qty = :qty
                WHERE id = :oid AND organization_id = :org_id
            """),
            {
                "oid": order_id,
                "org_id": self.org_id,
                "qty": float(new_qty),
            },
        )

        log_with_context(
            logger, logging.INFO,
            f"What-if: заказ {str(order_id)[:8]} → qty={new_qty}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

    async def _apply_change_due_date(self, item: Dict[str, Any]) -> None:
        order_id = item.get("order_id")
        new_due_date = item.get("new_due_date")
        if not order_id or not new_due_date:
            raise ValueError(
                "change_due_date требует order_id и new_due_date"
            )

        if isinstance(new_due_date, str):
            due_dt = datetime.fromisoformat(
                new_due_date.replace("Z", "+00:00")
            )
        elif isinstance(new_due_date, datetime):
            due_dt = new_due_date
        else:
            raise ValueError(f"Некорректный new_due_date: {new_due_date}")

        await self.session.execute(
            text("""
                UPDATE production_order
                SET due_date = :due
                WHERE id = :oid AND organization_id = :org_id
            """),
            {"oid": order_id, "org_id": self.org_id, "due": due_dt},
        )

    async def _apply_calendar_changes(
            self, events: List[Dict[str, Any]]
    ) -> None:
        for item in events:
            action = item.get("action")
            if action == "add":
                await self._apply_add_calendar_event(item)
            elif action == "remove":
                await self._apply_remove_calendar_event(item)
            else:
                raise ValueError(f"Неизвестное действие calendar: {action}")

    async def _apply_add_calendar_event(self, item: Dict[str, Any]) -> None:
        event_type = item.get("event_type")
        starts_at = item.get("starts_at")
        ends_at = item.get("ends_at")
        equipment_code = item.get("equipment_code")
        comment = item.get("comment")

        if not event_type or not starts_at or not ends_at:
            raise ValueError(
                "add calendar требует event_type, starts_at, ends_at"
            )

        equipment_id = None
        if equipment_code:
            result = await self.session.execute(
                text("""
                    SELECT id FROM equipment
                    WHERE organization_id = :org_id AND code = :code
                """),
                {"org_id": self.org_id, "code": equipment_code},
            )
            row = result.fetchone()
            if not row:
                raise ValueError(f"Оборудование {equipment_code} не найдено")
            equipment_id = row.id

        start_dt = (
            datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
            if isinstance(starts_at, str)
            else starts_at
        )
        end_dt = (
            datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            if isinstance(ends_at, str)
            else ends_at
        )

        new_id = uuid4()
        await self.session.execute(
            text("""
                INSERT INTO calendar_event
                    (id, organization_id, equipment_id, event_type,
                     starts_at, ends_at, comment)
                VALUES
                    (:id, :org_id, :eq_id, :etype, :start, :end, :comment)
            """),
            {
                "id": new_id,
                "org_id": self.org_id,
                "eq_id": equipment_id,
                "etype": event_type,
                "start": start_dt,
                "end": end_dt,
                "comment": comment,
            },
        )

        log_with_context(
            logger, logging.INFO,
            f"What-if: добавлено событие {event_type} "
            f"({equipment_code or 'all'}) {start_dt} → {end_dt}",
            stage="whatif_apply", org_id=str(self.org_id),
        )

    async def _apply_remove_calendar_event(
            self, item: Dict[str, Any]
    ) -> None:
        event_id = item.get("event_id")
        if not event_id:
            raise ValueError("remove calendar требует event_id")

        await self.session.execute(
            text("""
                DELETE FROM calendar_event
                WHERE id = :eid AND organization_id = :org_id
            """),
            {"eid": event_id, "org_id": self.org_id},
        )

    # ==========================================
    # ВНУТРЕННИЕ: МЕТРИКИ
    # ==========================================

    async def _compute_metrics(
            self, version_id: UUID
    ) -> Dict[str, Any]:
        """Считает метрики для schedule_version."""
        result = await self.session.execute(
            text("""
                SELECT
                    COALESCE(
                        EXTRACT(EPOCH FROM (MAX(st.planned_end) - MIN(st.planned_start))) / 60,
                        0
                    )::float AS makespan_minutes,
                    COUNT(*)::int AS total_tasks,
                    COUNT(*) FILTER (WHERE b.is_lab_blocked = TRUE)::int AS blocked_tasks,
                    COUNT(*) FILTER (WHERE st.cooling_mode = 'slow')::int AS cooling_slow_tasks,
                    COUNT(*) FILTER (
                        WHERE st.task_role = 'LINE_FILL'
                          AND st.status = 'DONE'
                          AND b.cz_status IS NOT NULL
                          AND b.cz_status != 'COMPLETED'
                    )::int AS cz_incomplete_tasks
                FROM scheduled_task st
                LEFT JOIN batch b ON b.id = st.batch_id
                WHERE st.schedule_version_id = :vid
                  AND st.organization_id = :org_id
            """),
            {"vid": version_id, "org_id": self.org_id},
        )
        row = result.fetchone()

        makespan_min = float(row.makespan_minutes or 0.0)

        return {
            "makespan_minutes": makespan_min,
            "makespan_hours": round(makespan_min / 60.0, 2),
            "total_tasks": int(row.total_tasks or 0),
            "blocked_tasks": int(row.blocked_tasks or 0),
            "cooling_slow_tasks": int(row.cooling_slow_tasks or 0),
            "cz_incomplete_tasks": int(row.cz_incomplete_tasks or 0),
        }


# ==========================================
# УТИЛИТЫ
# ==========================================

def _json_dumps(value: Any) -> str:
    """Сериализует значение в JSON-строку."""
    import json
    return json.dumps(value, default=str, ensure_ascii=False)


def _read_int(raw: Any, default: int) -> int:
    """Читает int из JSONB-значения."""
    if raw is None:
        return default
    try:
        if isinstance(raw, str):
            return int(raw.strip().strip('"').strip("'"))
        return int(raw)
    except (ValueError, TypeError):
        return default


def _percent_change(base: float, result: float) -> Optional[float]:
    """Процент изменения (result - base) / base * 100."""
    if base == 0:
        return None
    return round((result - base) / base * 100.0, 2)


def _row_to_scenario(row) -> Dict[str, Any]:
    """Преобразует SQL-row в dict (для API)."""
    import json
    changes = row.changes
    if isinstance(changes, str):
        try:
            changes = json.loads(changes)
        except (ValueError, TypeError):
            changes = {}

    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "name": row.name,
        "comment": row.comment,
        "base_version_id": row.base_version_id,
        "result_version_id": row.result_version_id,
        "changes": changes or {},
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": getattr(row, "updated_at", None),
        "created_by": getattr(row, "created_by", None),
    }