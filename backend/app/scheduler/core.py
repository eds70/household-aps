# backend/app/scheduler/core.py
"""
Ядро планировщика на OR-Tools CP-SAT.

Итерация 1 (исправление 2):
- В build_routing передаётся gp_product (ГП) для корректного расчёта
  длительности слива (бутылки / скорость).

Итерация 5:
- Пропуск заблокированных партий (is_lab_blocked = TRUE) при построении
  цепочек операций.
- Логирование пропущенных партий.
- Возврат списка исключённых партий в результате.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from uuid import UUID

from ortools.sat.python import cp_model

from .constraints.plugins import CONSTRAINT_PLUGINS
from .data_loader import DataLoader
from .duration.strategies import get_strategy, DurationContext
from .feature_flags import FeatureFlags
from .logging_config import setup_scheduler_logging, log_with_context
from .routing import build_routing, RoutingStep, TaskRole, RouteType, get_routing_summary
from .saver import ScheduleSaver

logger = setup_scheduler_logging(level=logging.INFO)


class ProductionScheduler:
    def __init__(self, horizon_hours: int = 2160, org_id: UUID = None):
        self.horizon_minutes = horizon_hours * 60
        self.org_id = org_id
        self.data_loader = DataLoader(org_id=org_id)
        self.tasks: Dict[Tuple[str, str], Dict] = {}
        self.t0: Optional[datetime] = None
        self.flags: Optional[FeatureFlags] = None
        self.skipped_batches: List[Dict[str, Any]] = []

    def _calculate_duration(
            self,
            operation: Dict,
            batch: Dict,
            equipment: Dict,
            product: Dict,
    ) -> int:
        formula = operation.get("duration_formula") or operation.get("name", "").lower()
        try:
            strategy = get_strategy(formula)
            ctx = DurationContext(operation, batch, equipment, product)
            return strategy.calculate(ctx)
        except ValueError:
            return operation.get("base_duration_mins", 0)

    def _datetime_to_minutes(self, dt: datetime) -> int:
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        t0_naive = self.t0.replace(tzinfo=None)
        delta = dt - t0_naive
        return max(0, int(delta.total_seconds() / 60))

    def _resolve_t0(self, org_settings: Dict[str, Any]) -> datetime:
        raw = org_settings.get("planning_start_date")
        if raw is not None:
            try:
                if isinstance(raw, str):
                    cleaned = raw.strip().strip('"').strip("'")
                    return datetime.fromisoformat(cleaned)
                return datetime.fromisoformat(str(raw).strip().strip('"'))
            except (ValueError, TypeError) as e:
                log_with_context(
                    logger, logging.WARNING,
                    f"Не удалось распарсить planning_start_date='{raw}': {e}. "
                    f"Использую fallback 2026-09-01 08:00:00",
                    stage="init", org_id=str(self.org_id),
                )
        return datetime(2026, 9, 1, 8, 0, 0)

    def _is_batch_blocked(self, batch: Dict) -> bool:
        """
        Проверяет, заблокирована ли партия лабораторией.

        Итерация 5.
        """
        if not self.flags or not self.flags.enable_lab_blocking:
            return False
        return bool(batch.get("is_lab_blocked", False))

    async def build_schedule(self) -> Dict[str, Any]:
        log_with_context(
            logger, logging.INFO,
            "Начало построения плана",
            stage="start", org_id=str(self.org_id),
        )

        data = await self.data_loader.load_all()
        batches = data["batches"]
        equipment_map = data["equipment"]
        products_map = data["products"]
        ops_map = data["operation_templates"]
        setup_matrix = data["setup_matrix"]
        calendar_events = data["calendar_events"]
        equipment_links = data.get("equipment_links", [])
        org_settings = data.get("org_settings", {})
        gp_products = data.get("gp_products", {})

        self.flags = FeatureFlags(org_settings)
        log_with_context(
            logger, logging.INFO,
            f"Feature-флаги: {self.flags}",
            stage="init", org_id=str(self.org_id),
        )

        self.t0 = self._resolve_t0(org_settings)
        log_with_context(
            logger, logging.INFO,
            f"t0 = {self.t0.isoformat()}",
            stage="init", org_id=str(self.org_id),
        )

        log_with_context(
            logger, logging.INFO,
            f"Загружено: партий={len(batches)}, оборудования={len(equipment_map)}, "
            f"связей={len(equipment_links)}, ГП={len(gp_products)}, "
            f"событий календаря={len(calendar_events)}",
            stage="load", org_id=str(self.org_id),
        )

        calendar_minutes = []
        for event in calendar_events:
            start_min = self._datetime_to_minutes(event["starts_at"])
            end_min = self._datetime_to_minutes(event["ends_at"])
            calendar_minutes.append({
                "equipment_id": str(event.get("equipment_id", "")) if event.get("equipment_id") else None,
                "event_type": event["event_type"],
                "start": start_min,
                "end": end_min,
            })

        model = cp_model.CpModel()

        log_with_context(
            logger, logging.INFO,
            "Построение цепочек операций...",
            stage="routing", org_id=str(self.org_id),
        )

        routing_steps: Dict[str, List[RoutingStep]] = {}
        use_tank_routing = self.flags.enable_tank_routing

        # Итерация 5: сбрасываем список пропущенных партий
        self.skipped_batches = []

        for batch in batches:
            batch_id = str(batch["id"])
            product_id = str(batch["product_id"])
            equipment_id = str(batch["assigned_equipment_id"])

            # === Итерация 5: пропуск заблокированных партий ===
            if self._is_batch_blocked(batch):
                skip_info = {
                    "batch_id": batch_id,
                    "product_id": product_id,
                    "equipment_id": equipment_id,
                    "reason": batch.get("lab_block_reason") or "Заблокировано лабораторией",
                    "lab_status": batch.get("lab_status", "BLOCKED"),
                }
                self.skipped_batches.append(skip_info)
                log_with_context(
                    logger, logging.WARNING,
                    f"Партия {batch_id[:8]} (ПФ={product_id[:8]}) ПРОПУЩЕНА: "
                    f"{skip_info['reason']}",
                    stage="routing", org_id=str(self.org_id),
                )
                continue
            # === /Итерация 5 ===

            gp_product_id = batch.get("gp_product_id")
            gp_product = gp_products.get(str(gp_product_id)) if gp_product_id else None

            product = products_map.get(product_id, {})
            reactor = equipment_map.get(equipment_id, {})
            operations = ops_map.get(product_id, [])

            if not use_tank_routing:
                product = {**product, "route_type": RouteType.DIRECT}
                equipment_links_for_routing = []
            else:
                equipment_links_for_routing = equipment_links

            steps = build_routing(
                batch=batch,
                product=product,
                reactor=reactor,
                operations=operations,
                equipment_map=equipment_map,
                equipment_links=equipment_links_for_routing,
                products_map=products_map,
                calc_duration=self._calculate_duration,
                gp_product=gp_product,
            )

            routing_steps[batch_id] = steps

            summary = get_routing_summary(steps)
            log_with_context(
                logger, logging.DEBUG,
                f"Партия {batch_id[:8]}: {summary['total_steps']} шагов, "
                f"роли={summary['roles']}, длительность={summary['total_duration']} мин",
                stage="routing", org_id=str(self.org_id),
            )

        if self.skipped_batches:
            log_with_context(
                logger, logging.WARNING,
                f"Пропущено заблокированных партий: {len(self.skipped_batches)}",
                stage="routing", org_id=str(self.org_id),
            )

        # Если все партии заблокированы — вернуть пустой результат
        if not routing_steps:
            log_with_context(
                logger, logging.WARNING,
                "Все партии заблокированы или отсутствуют — план пуст",
                stage="solve", org_id=str(self.org_id),
            )
            return {
                "status": "success",
                "tasks": [],
                "makespan_minutes": 0,
                "total_tasks": 0,
                "skipped_batches": self.skipped_batches,
                "message": "Нет доступных партий для планирования",
            }

        # Переменные
        for batch_id, steps in routing_steps.items():
            for step in steps:
                key = (batch_id, step.op_id)
                start_var = model.NewIntVar(0, self.horizon_minutes, f"start_{batch_id}_{step.op_id}")
                end_var = model.NewIntVar(0, self.horizon_minutes, f"end_{batch_id}_{step.op_id}")
                interval = model.NewIntervalVar(
                    start_var, step.duration, end_var, f"interval_{batch_id}_{step.op_id}"
                )

                self.tasks[key] = {
                    "interval": interval,
                    "start": start_var,
                    "end": end_var,
                    "duration": step.duration,
                    "batch_id": batch_id,
                    "op_id": step.op_id,
                    "role": step.role,
                    "primary_equipment_id": step.primary_equipment_id,
                    "secondary_equipment_id": step.secondary_equipment_id,
                    "op": step.op,
                    "depends_on_op_ids": step.depends_on_op_ids,
                    "is_parallel_with": step.is_parallel_with,
                    "is_first_in_batch": step.is_first_in_batch,
                    "is_last_in_batch": step.is_last_in_batch,
                    "needs_boiler": step.op.get("needs_boiler", False),
                    "needs_cooling": step.op.get("needs_cooling_zone", False),
                    "needs_operator": step.op.get("needs_operator", False),
                }

        # Зависимости
        deps_count = 0
        for batch_id, steps in routing_steps.items():
            for step in steps:
                key = (batch_id, step.op_id)
                for dep_op_id in step.depends_on_op_ids:
                    dep_key = (batch_id, dep_op_id)
                    if dep_key in self.tasks:
                        model.Add(self.tasks[key]["start"] >= self.tasks[dep_key]["end"])
                        deps_count += 1

        log_with_context(
            logger, logging.INFO,
            f"Ограничений зависимостей: {deps_count}",
            stage="build", org_id=str(self.org_id),
        )

        # NoOverlap
        intervals_by_equipment: Dict[str, List] = {}
        for key, task in self.tasks.items():
            primary = task["primary_equipment_id"]
            secondary = task["secondary_equipment_id"]
            if primary:
                intervals_by_equipment.setdefault(primary, []).append(task["interval"])
            if secondary:
                intervals_by_equipment.setdefault(secondary, []).append(task["interval"])

        nooverlap_count = 0
        for eq_id, intervals in intervals_by_equipment.items():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)
                nooverlap_count += 1

        log_with_context(
            logger, logging.INFO,
            f"NoOverlap по {nooverlap_count} ресурсам",
            stage="build", org_id=str(self.org_id),
        )

        # Setup-ограничения
        setup_count = 0
        last_by_reactor: Dict[str, List[Dict]] = {}
        first_by_reactor: Dict[str, List[Dict]] = {}

        for key, task in self.tasks.items():
            if task["role"] not in (TaskRole.REACTOR_OP, TaskRole.WASH):
                continue
            reactor_id = task["primary_equipment_id"]
            if not reactor_id:
                continue

            if task["is_last_in_batch"]:
                last_by_reactor.setdefault(reactor_id, []).append(task)
            if task["is_first_in_batch"]:
                first_by_reactor.setdefault(reactor_id, []).append(task)

        for reactor_id, last_tasks in last_by_reactor.items():
            first_tasks = first_by_reactor.get(reactor_id, [])
            for last_task in last_tasks:
                for first_task in first_tasks:
                    if last_task["batch_id"] == first_task["batch_id"]:
                        continue

                    last_prod = self._get_product_code_for_batch(last_task["batch_id"], routing_steps)
                    first_prod = self._get_product_code_for_batch(first_task["batch_id"], routing_steps)

                    default_setup = 30 if last_prod == first_prod else 90
                    setup_ij = setup_matrix.get((last_prod, first_prod), default_setup)
                    setup_ji = setup_matrix.get((first_prod, last_prod), default_setup)

                    i_before_j = model.NewBoolVar(
                        f"setup_{reactor_id[:8]}_{last_task['batch_id'][:8]}_before_{first_task['batch_id'][:8]}"
                    )
                    model.Add(
                        first_task["start"] >= last_task["end"] + setup_ij
                    ).OnlyEnforceIf(i_before_j)

                    j_before_i = model.NewBoolVar(
                        f"setup_{reactor_id[:8]}_{first_task['batch_id'][:8]}_before_{last_task['batch_id'][:8]}"
                    )
                    model.Add(
                        last_task["start"] >= first_task["end"] + setup_ji
                    ).OnlyEnforceIf(j_before_i)

                    model.Add(i_before_j + j_before_i == 1)
                    setup_count += 1

        log_with_context(
            logger, logging.INFO,
            f"Setup-ограничений: {setup_count}",
            stage="build", org_id=str(self.org_id),
        )

        # Календарь
        calendar_count = 0
        for cal_event in calendar_minutes:
            eq_id = cal_event["equipment_id"]
            start_min = cal_event["start"]
            end_min = cal_event["end"]

            affected = []
            for key, task in self.tasks.items():
                if eq_id is None:
                    affected.append(task)
                elif task["primary_equipment_id"] == eq_id or task["secondary_equipment_id"] == eq_id:
                    affected.append(task)

            for task in affected:
                ends_before = model.NewBoolVar(
                    f"cal_{task['batch_id'][:8]}_{task['op_id'][:8]}_before_{start_min}"
                )
                model.Add(task["end"] <= start_min).OnlyEnforceIf(ends_before)
                model.Add(task["start"] >= end_min).OnlyEnforceIf(ends_before.Not())
                calendar_count += 1

        log_with_context(
            logger, logging.INFO,
            f"Календарных ограничений: {calendar_count}",
            stage="build", org_id=str(self.org_id),
        )

        # Плагины
        plugin_tasks = {}
        for key, task in self.tasks.items():
            plugin_tasks[key] = {
                "interval": task["interval"],
                "needs_boiler": task["needs_boiler"],
                "needs_cooling": task["needs_cooling"],
                "needs_operator": task["needs_operator"],
            }
        for plugin in CONSTRAINT_PLUGINS:
            plugin.apply(model, plugin_tasks)

        log_with_context(
            logger, logging.INFO,
            f"Применено плагинов: {len(CONSTRAINT_PLUGINS)}",
            stage="build", org_id=str(self.org_id),
        )

        # Целевая функция
        makespan = model.NewIntVar(0, self.horizon_minutes, "makespan")
        for task in self.tasks.values():
            model.Add(makespan >= task["end"])
        model.Minimize(makespan)

        # Solver
        log_with_context(
            logger, logging.INFO,
            "Запуск OR-Tools CP-SAT solver (timeout=120s)...",
            stage="solve", org_id=str(self.org_id),
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            log_with_context(
                logger, logging.INFO,
                f"Решение найдено: status={solver.StatusName(status)}, "
                f"wall_time={solver.WallTime():.2f}s, "
                f"objective={solver.ObjectiveValue():.0f} мин",
                stage="solve", org_id=str(self.org_id),
            )
            result = self._extract_solution(
                solver, equipment_map, products_map, batches, routing_steps
            )
            result["skipped_batches"] = self.skipped_batches
            return result
        else:
            log_with_context(
                logger, logging.ERROR,
                f"Решение НЕ найдено: status={solver.StatusName(status)}",
                stage="solve", org_id=str(self.org_id),
            )
            return {
                "error": "No feasible solution found",
                "status": solver.StatusName(status),
                "skipped_batches": self.skipped_batches,
            }

    def _get_product_code_for_batch(
            self,
            batch_id: str,
            routing_steps: Dict[str, List[RoutingStep]],
    ) -> str:
        steps = routing_steps.get(batch_id, [])
        if steps:
            return steps[0].op.get("product_id", "")
        return ""

    def _extract_solution(
            self,
            solver,
            equipment_map: Dict[str, Dict],
            products_map: Dict[str, Dict],
            batches: List[Dict],
            routing_steps: Dict[str, List[RoutingStep]],
    ) -> Dict:
        batch_by_id = {str(b["id"]): b for b in batches}

        schedule = []
        for key, task in self.tasks.items():
            batch_id, op_id = key
            start = solver.Value(task["start"])
            end = solver.Value(task["end"])
            start_dt = self.t0 + timedelta(minutes=start)
            end_dt = self.t0 + timedelta(minutes=end)

            primary_info = equipment_map.get(task["primary_equipment_id"], {})
            secondary_info = (
                equipment_map.get(task["secondary_equipment_id"], {})
                if task["secondary_equipment_id"] else {}
            )
            batch_info = batch_by_id.get(batch_id, {})
            product_id = str(batch_info.get("product_id", ""))
            product_info = products_map.get(product_id, {})

            schedule.append({
                "batch_id": batch_id,
                "batch_name": f"Партия {batch_info.get('product_name', 'Unknown')}",
                "op_id": op_id,
                "role": task["role"],
                "equipment_id": task["primary_equipment_id"],
                "equipment_name": primary_info.get("name", "Unknown"),
                "linked_equipment_id": task["secondary_equipment_id"],
                "linked_equipment_name": secondary_info.get("name") if secondary_info else None,
                "product_id": product_id,
                "product_name": product_info.get("name", "Unknown"),
                "product_code": product_info.get("code", "Unknown"),
                "start": start_dt,
                "end": end_dt,
                "duration": end - start,
                "operation_name": task["op"].get("name", "Операция"),
            })

        schedule.sort(key=lambda x: x["start"])
        makespan_mins = max((t["end"] - self.t0).total_seconds() / 60 for t in schedule) if schedule else 0

        return {
            "status": "success",
            "tasks": schedule,
            "makespan_minutes": makespan_mins,
            "total_tasks": len(schedule),
        }


async def main():
    from app.core.config import settings

    scheduler = ProductionScheduler(
        horizon_hours=2160,
        org_id=settings.DEFAULT_ORG_ID,
    )
    result = await scheduler.build_schedule()
    if "error" in result:
        log_with_context(
            logger, logging.ERROR,
            f"Ошибка: {result['error']}",
            stage="finish", org_id=str(settings.DEFAULT_ORG_ID),
        )
        return

    log_with_context(
        logger, logging.INFO,
        f"План построен: задач={result['total_tasks']}, "
        f"makespan={result['makespan_minutes']:.0f} мин "
        f"({result['makespan_minutes']/60:.1f} ч), "
        f"пропущено={len(result.get('skipped_batches', []))}",
        stage="finish", org_id=str(settings.DEFAULT_ORG_ID),
    )

    saver = ScheduleSaver(org_id=settings.DEFAULT_ORG_ID)
    save_stats = await saver.save_schedule(result)
    log_with_context(
        logger, logging.INFO,
        f"Сохранено в БД: задач={save_stats['tasks_saved']}, "
        f"version_id={save_stats['version_id']}",
        stage="save", org_id=str(settings.DEFAULT_ORG_ID),
    )


if __name__ == "__main__":
    asyncio.run(main())