# backend/app/scheduler/core.py
"""
Ядро планировщика на OR-Tools CP-SAT.

Итерация 1: build_routing с gp_product.
Итерация 5: пропуск заблокированных партий.
Итерация 6: operator_pool + resource_pools в плагины.
Итерация 7: дискретизация охлаждения (fast/slow) для деградации.
Итерация 7 (fix #1): связывание b_slow с пересечением cooling-интервалов.
Итерация 7 (fix #2): overlap_ij вычисляется через fast_end, а не через
                     chosen_end. Иначе циклическая зависимость:
                     chosen_end ← b_slow ← overlap ← chosen_end.
Итерация 7 (fix #3): fast_end и slow_end жёстко связаны с start + duration
                     явным Add(...). Иначе при отсутствии минимизации
                     (или при поиске FEASIBLE вместо OPTIMAL)
                     solver может выбрать произвольные end, из-за чего
                     overlap всегда = 1, и все cooling-задачи становятся slow.
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

# Итерация 7: типы ресурсов, для которых НЕ создаём NoOverlap
# (обрабатываются плагинами отдельно).
PLUGIN_MANAGED_RESOURCE_TYPES = {"COOLING_ZONE"}


class ProductionScheduler:
    def __init__(self, horizon_hours: int = 2160, org_id: UUID = None):
        self.horizon_minutes = horizon_hours * 60
        self.org_id = org_id
        self.data_loader = DataLoader(org_id=org_id)
        self.tasks: Dict[Tuple[str, str], Dict] = {}
        self.t0: Optional[datetime] = None
        self.flags: Optional[FeatureFlags] = None
        self.skipped_batches: List[Dict[str, Any]] = []
        # Итерация 7
        self.cooling_degradation_factor: float = 1.3

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
        """Проверяет, заблокирована ли партия лабораторией."""
        if not self.flags or not self.flags.enable_lab_blocking:
            return False
        return bool(batch.get("is_lab_blocked", False))

    def _resolve_cooling_degradation_factor(self, org_settings: Dict[str, Any]) -> float:
        """Читает cooling_degradation_factor из настроек."""
        raw = org_settings.get("cooling_degradation_factor")
        if raw is None:
            return 1.3
        try:
            if isinstance(raw, str):
                return float(raw.strip().strip('"').strip("'"))
            return float(raw)
        except (ValueError, TypeError):
            return 1.3

    def _apply_cooling_degradation_model(
            self,
            model: cp_model.CpModel,
            cooling_tasks: List[Dict],
    ) -> None:
        """
        Итерация 7 (fix #2): корректная модель деградации охлаждения.

        Логика по ТЗ:
          - 1 реактор охлаждается  → fast (base duration).
          - 2+ реактора охлаждаются → каждый slow (base × factor).

        КРИТИЧНО: overlap_ij определяется через `fast_end` (фиксированную
        длительность), а НЕ через `chosen_end`. Иначе возникает
        циклическая зависимость:
            chosen_end зависит от b_slow,
            b_slow зависит от overlap,
            overlap зависит от chosen_end.
        Solver находит фиктивное решение, где все задачи slow,
        даже если они последовательны.

        Модель:
          Для каждой cooling-задачи i:
            b_slow_i = 1  ⟺  ∃ j ≠ i: cooling_j пересекается с cooling_i
            b_fast_i = 1  ⟺  не существует такого j
            b_fast_i + b_slow_i == 1  (уже задано при создании задачи)
        """
        if not cooling_tasks:
            return

        n = len(cooling_tasks)
        log_with_context(
            logger, logging.INFO,
            f"Итерация 7 (fix): применяем модель деградации для {n} cooling-задач",
            stage="build", org_id=str(self.org_id),
        )

        # ==========================================
        # Вычисляем "fast end" для каждой задачи.
        #
        # Если у задачи сохранён fast_end (мы добавили его в self.tasks),
        # используем его. Если нет — создаём переменную
        # fast_end = start + duration (fallback для тестов).
        # ==========================================

        for i, ti in enumerate(cooling_tasks):
            # Получаем "fast end" как fixed end для сравнения
            ti_fast_end = ti.get("fast_end")

            if ti_fast_end is None:
                duration_i = ti.get("duration", 0)
                ti_fast_end = model.NewIntVar(
                    0, self.horizon_minutes,
                    f"fast_end_fallback_i_{i}"
                )
                model.Add(ti_fast_end == ti["start"] + duration_i)

            overlaps = []

            for j, tj in enumerate(cooling_tasks):
                if i == j:
                    continue

                tj_fast_start = tj["start"]
                tj_fast_end_fixed = tj.get("fast_end")

                if tj_fast_end_fixed is None:
                    duration_j = tj.get("duration", 0)
                    tj_fast_end_fixed = model.NewIntVar(
                        0, self.horizon_minutes,
                        f"fast_end_fallback_j_{j}"
                    )
                    model.Add(tj_fast_end_fixed == tj["start"] + duration_j)

                # overlap_ij = (tj.start < ti.fast_end) AND (ti.start < tj.fast_end)
                # Используем fast_end для ОБЕИХ задач — это фиксированные
                # значения, не зависящие от b_fast / b_slow.
                overlap_ij = model.NewBoolVar(f"ov_cool_{i}_{j}")

                # tj.start < ti.fast_end
                b1 = model.NewBoolVar(f"b1_{i}_{j}")
                model.Add(tj_fast_start < ti_fast_end).OnlyEnforceIf(b1)
                model.Add(tj_fast_start >= ti_fast_end).OnlyEnforceIf(b1.Not())

                # ti.start < tj.fast_end
                b2 = model.NewBoolVar(f"b2_{i}_{j}")
                model.Add(ti["start"] < tj_fast_end_fixed).OnlyEnforceIf(b2)
                model.Add(ti["start"] >= tj_fast_end_fixed).OnlyEnforceIf(b2.Not())

                # overlap_ij = b1 AND b2
                model.AddBoolAnd([b1, b2]).OnlyEnforceIf(overlap_ij)
                model.AddBoolOr([b1.Not(), b2.Not()]).OnlyEnforceIf(overlap_ij.Not())

                overlaps.append(overlap_ij)

            if not overlaps:
                # Единственная cooling-задача — всегда fast
                model.Add(ti["b_fast"] == 1)
                continue

            # b_slow_i >= overlap_ij для каждого j
            for ov in overlaps:
                model.Add(ti["b_slow"] >= ov)

            # b_slow_i <= sum(overlaps):
            # если все overlaps = 0, то b_slow_i = 0
            model.Add(ti["b_slow"] <= sum(overlaps))

    async def build_schedule(
            self,
            pinned_tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Строит расписание.

        Итерация 9 (A3): добавлен параметр pinned_tasks — список задач,
        которые должны быть ЖЁСТКО зафиксированы на своих planned_start
        и planned_end (если задан). Используется при перепланировании.

        Каждый элемент pinned_tasks — dict:
          {
            "batch_id": str,
            "op_id": str | None,
            "task_role": str | None,
            "planned_start": datetime | str,
            "planned_end": datetime | str | None,
          }
        """
        log_with_context(
            logger, logging.INFO,
            f"Начало построения плана "
            f"(pinned_tasks={len(pinned_tasks) if pinned_tasks else 0})",
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
        resource_pools = data.get("resource_pools", [])

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

        # Итерация 7: коэффициент деградации
        self.cooling_degradation_factor = self._resolve_cooling_degradation_factor(org_settings)
        log_with_context(
            logger, logging.INFO,
            f"Cooling degradation: enable={self.flags.enable_cooling_degradation}, "
            f"factor={self.cooling_degradation_factor}",
            stage="init", org_id=str(self.org_id),
        )

        log_with_context(
            logger, logging.INFO,
            f"Загружено: партий={len(batches)}, оборудования={len(equipment_map)}, "
            f"связей={len(equipment_links)}, ГП={len(gp_products)}, "
            f"событий календаря={len(calendar_events)}",
            stage="load", org_id=str(self.org_id),
        )

        pool_types = [p.get("type") for p in resource_pools]
        log_with_context(
            logger, logging.INFO,
            f"Загружено пулов ресурсов: {len(resource_pools)} ({pool_types})",
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

        self.skipped_batches = []

        for batch in batches:
            batch_id = str(batch["id"])
            product_id = str(batch["product_id"])
            equipment_id = str(batch["assigned_equipment_id"])

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
                f"роли={summary['roles']}, длительность={summary['total_duration']} мин, "
                f"пулы={summary.get('operator_pools', [])}",
                stage="routing", org_id=str(self.org_id),
            )

        if self.skipped_batches:
            log_with_context(
                logger, logging.WARNING,
                f"Пропущено заблокированных партий: {len(self.skipped_batches)}",
                stage="routing", org_id=str(self.org_id),
            )

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

        # ==========================================
        # СОЗДАНИЕ ПЕРЕМЕННЫХ
        # ==========================================
        # Итерация 7: для cooling-операций создаём fast/slow интервалы,
        # если feature-флаг enable_cooling_degradation включён.

        cooling_count = 0
        for batch_id, steps in routing_steps.items():
            for step in steps:
                key = (batch_id, step.op_id)
                needs_cooling = step.op.get("needs_cooling_zone", False)
                use_degradation = (
                        self.flags.enable_cooling_degradation and needs_cooling
                )

                start_var = model.NewIntVar(0, self.horizon_minutes, f"start_{batch_id}_{step.op_id}")

                if use_degradation:
                    # === Итерация 7: fast/slow ===
                    slow_duration = int(step.duration * self.cooling_degradation_factor)
                    if slow_duration < step.duration:
                        slow_duration = step.duration

                    b_fast = model.NewBoolVar(f"b_fast_{batch_id}_{step.op_id}")
                    b_slow = model.NewBoolVar(f"b_slow_{batch_id}_{step.op_id}")
                    model.Add(b_fast + b_slow == 1)

                    fast_end = model.NewIntVar(0, self.horizon_minutes, f"fast_end_{batch_id}_{step.op_id}")
                    slow_end = model.NewIntVar(0, self.horizon_minutes, f"slow_end_{batch_id}_{step.op_id}")

                    fast_interval = model.NewOptionalIntervalVar(
                        start_var, step.duration, fast_end,
                        b_fast, f"fast_interval_{batch_id}_{step.op_id}",
                    )
                    slow_interval = model.NewOptionalIntervalVar(
                        start_var, slow_duration, slow_end,
                        b_slow, f"slow_interval_{batch_id}_{step.op_id}",
                    )

                    # Итерация 7 (fix #3): ЯВНАЯ связь end = start + duration.
                    # NewOptionalIntervalVar формально задаёт эту связь, но без
                    # явного Add(...) solver может выбрать произвольное fast_end
                    # при отсутствии минимизации (например, при поиске FEASIBLE
                    # вместо OPTIMAL, или в unit-тестах).
                    model.Add(fast_end == start_var + step.duration)
                    model.Add(slow_end == start_var + slow_duration)

                    # chosen_end — «реальная» длительность
                    chosen_end = model.NewIntVar(0, self.horizon_minutes, f"chosen_end_{batch_id}_{step.op_id}")
                    model.Add(chosen_end == fast_end).OnlyEnforceIf(b_fast)
                    model.Add(chosen_end == slow_end).OnlyEnforceIf(b_slow)

                    # interval — общий интервал для NoOverlap по реактору.
                    # Используем chosen_end как конец, чтобы NoOverlap
                    # учитывал реальную (возможно, увеличенную) длительность.
                    interval = model.NewIntervalVar(
                        start_var, step.duration, chosen_end,
                        f"interval_{batch_id}_{step.op_id}",
                    )

                    self.tasks[key] = {
                        "interval": interval,
                        "start": start_var,
                        "end": chosen_end,
                        "fast_interval": fast_interval,
                        "slow_interval": slow_interval,
                        "fast_end": fast_end,           # ← Итерация 7 (fix #2)
                        "b_fast": b_fast,
                        "b_slow": b_slow,
                        "chosen_end": chosen_end,
                        "duration": step.duration,
                        "slow_duration": slow_duration,
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
                        "needs_cooling": needs_cooling,
                        "needs_operator": step.op.get("needs_operator", False),
                        "operator_pool": step.operator_pool,
                        "is_cooling_degraded": True,
                    }
                    cooling_count += 1
                else:
                    # === Обычная логика ===
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
                        "needs_cooling": needs_cooling,
                        "needs_operator": step.op.get("needs_operator", False),
                        "operator_pool": step.operator_pool,
                        "is_cooling_degraded": False,
                    }

        if cooling_count > 0:
            log_with_context(
                logger, logging.INFO,
                f"Итерация 7: создано {cooling_count} задач с деградацией охлаждения",
                stage="build", org_id=str(self.org_id),
            )

        # ==========================================
        # A3 (Итерация 9): ПРИМЕНЕНИЕ PINNED CONSTRAINTS
        # ==========================================
        # Жёстко фиксируем pinned-задачи на их planned_start.
        # Делается ПОСЛЕ создания всех self.tasks, ДО применения
        # остальных ограничений и минимизации makespan.
        if pinned_tasks:
            self._apply_pinned_constraints(model, pinned_tasks)

        # ==========================================
        # ИТЕРАЦИЯ 7 (FIX): МОДЕЛЬ ДЕГРАДАЦИИ ОХЛАЖДЕНИЯ
        # ==========================================

        # ==========================================
        # ИТЕРАЦИЯ 7 (FIX): МОДЕЛЬ ДЕГРАДАЦИИ ОХЛАЖДЕНИЯ
        # ==========================================
        # Собираем все cooling-задачи и связываем b_slow с фактическим
        # пересечением fast-интервалов. Это делается ДО применения
        # плагинов, т.к. плагины добавляют только общее ограничение capacity.
        if self.flags.enable_cooling_degradation and cooling_count > 0:
            cooling_tasks = [
                t for t in self.tasks.values() if t.get("is_cooling_degraded")
            ]
            self._apply_cooling_degradation_model(model, cooling_tasks)

        # Зависимости (используем task["end"], который равен chosen_end для cooling)
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

        # NoOverlap — исключаем cooling_zone (обрабатывается плагином)
        intervals_by_equipment: Dict[str, List] = {}
        for key, task in self.tasks.items():
            primary = task["primary_equipment_id"]
            secondary = task["secondary_equipment_id"]
            if primary:
                intervals_by_equipment.setdefault(primary, []).append(task["interval"])
            if secondary:
                intervals_by_equipment.setdefault(secondary, []).append(task["interval"])

        # Определяем ID cooling_zone оборудования (если есть)
        cooling_zone_ids = set()
        for eq_id, eq in equipment_map.items():
            if eq.get("type") == "COOLING_ZONE":
                cooling_zone_ids.add(str(eq_id))

        nooverlap_count = 0
        for eq_id, intervals in intervals_by_equipment.items():
            if eq_id in cooling_zone_ids:
                # Пропускаем — за это отвечает CoolingDegradationConstraint
                continue
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)
                nooverlap_count += 1

        log_with_context(
            logger, logging.INFO,
            f"NoOverlap по {nooverlap_count} ресурсам",
            stage="build", org_id=str(self.org_id),
        )

        # Setup-ограничения (используют task["start"] и task["end"])
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

        # Календарь (использует task["start"] и task["end"])
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
                "operator_pool": task.get("operator_pool"),
                "fast_interval": task.get("fast_interval"),
                "slow_interval": task.get("slow_interval"),
                "b_fast": task.get("b_fast"),
                "b_slow": task.get("b_slow"),
            }

        for plugin in CONSTRAINT_PLUGINS:
            try:
                plugin.apply(model, plugin_tasks, resource_pools=resource_pools)
            except TypeError:
                plugin.apply(model, plugin_tasks)

        log_with_context(
            logger, logging.INFO,
            f"Применено плагинов: {len(CONSTRAINT_PLUGINS)}, "
            f"пулов ресурсов: {len(resource_pools)}",
            stage="build", org_id=str(self.org_id),
        )

        # Целевая функция (использует task["end"] = chosen_end для cooling)
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

    def _apply_pinned_constraints(
            self,
            model: cp_model.CpModel,
            pinned_tasks: List[Dict[str, Any]],
    ) -> None:
        """
        Итерация 9 (A3): жёстко фиксирует pinned-задачи
        на их planned_start (и planned_end, если задан).

        Как ищет задачу в модели:
          1. По (batch_id, op_id) — если op_id задан.
          2. Иначе по (batch_id, task_role) — первое совпадение.

        Побочный эффект:
          Задачи, зависящие от pinned (через depends_on_op_ids),
          тоже сдвинутся — это правильно.

        Если pinned-задача не найдена (партия заблокирована
        лабораторией или отсутствует), она пропускается
        с WARNING в лог.
        """
        if not pinned_tasks:
            return

        applied_count = 0
        skipped_count = 0

        # Индексы для быстрого поиска задач
        by_batch_op: Dict[Tuple[str, str], Dict] = {}
        by_batch_role: Dict[Tuple[str, str], Dict] = {}

        for key, task in self.tasks.items():
            batch_id = task.get("batch_id")
            op_id = task.get("op_id")
            role = task.get("role")
            if batch_id and op_id:
                by_batch_op[(str(batch_id), str(op_id))] = task
            if batch_id and role:
                rkey = (str(batch_id), str(role))
                if rkey not in by_batch_role:
                    by_batch_role[rkey] = task

        for pinned in pinned_tasks:
            batch_id = str(pinned.get("batch_id") or "")
            op_id = str(pinned.get("op_id") or "")
            task_role = str(pinned.get("task_role") or "")
            planned_start = pinned.get("planned_start")
            planned_end = pinned.get("planned_end")

            # Ищем задачу
            task = None
            if batch_id and op_id:
                task = by_batch_op.get((batch_id, op_id))
            if task is None and batch_id and task_role:
                task = by_batch_role.get((batch_id, task_role))

            if task is None:
                skipped_count += 1
                log_with_context(
                    logger, logging.WARNING,
                    f"A3: pinned-задача не найдена в модели: "
                    f"batch={batch_id[:8] if batch_id else '?'}, "
                    f"op_id={op_id[:8] if op_id else '?'}, "
                    f"role={task_role}",
                    stage="pinned", org_id=str(self.org_id),
                )
                continue

            if planned_start is None:
                skipped_count += 1
                continue

            # Приводим start к минутам от t0
            start_minutes = self._coerce_to_minutes(planned_start)
            if start_minutes is None:
                skipped_count += 1
                continue

            # Фиксируем start
            model.Add(task["start"] == start_minutes)

            # Фиксируем end, если задан
            if planned_end is not None:
                end_minutes = self._coerce_to_minutes(planned_end)
                if end_minutes is not None:
                    model.Add(task["end"] == end_minutes)

            applied_count += 1

        log_with_context(
            logger, logging.INFO,
            f"A3: применено pinned-constraints: {applied_count}, "
            f"пропущено: {skipped_count}",
            stage="pinned", org_id=str(self.org_id),
        )

    def _coerce_to_minutes(self, value: Any) -> Optional[int]:
        """
        Приводит значение (datetime | str) к минутам от self.t0.
        Возвращает None, если преобразование невозможно.
        """
        if isinstance(value, datetime):
            return self._datetime_to_minutes(value)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return self._datetime_to_minutes(dt)
            except (ValueError, TypeError):
                return None
        return None


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

            # Итерация 7: для cooling — определить режим
            cooling_mode = None
            if task.get("is_cooling_degraded"):
                b_fast_var = task.get("b_fast")
                if b_fast_var is not None:
                    b_fast_val = solver.Value(b_fast_var)
                    cooling_mode = "fast" if b_fast_val == 1 else "slow"

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
                "operator_pool": task.get("operator_pool"),
                "cooling_mode": cooling_mode,
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