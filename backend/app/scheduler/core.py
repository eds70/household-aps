# backend/app/scheduler/core.py
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from uuid import UUID
from ortools.sat.python import cp_model
from .data_loader import DataLoader
from .duration.strategies import get_strategy, DurationContext
from .constraints.plugins import CONSTRAINT_PLUGINS
from .saver import ScheduleSaver


class ProductionScheduler:
    def __init__(self, horizon_hours: int = 2160, org_id: UUID = None):
        self.horizon_minutes = horizon_hours * 60
        self.org_id = org_id
        self.data_loader = DataLoader(org_id=org_id)
        self.tasks: Dict[Tuple[str, str], Dict] = {}
        self.t0 = datetime(2026, 9, 1, 8, 0, 0)

    def _calculate_duration(self, operation: Dict, batch: Dict, equipment: Dict, product: Dict) -> int:
        formula = operation.get("duration_formula") or operation["name"].lower()
        try:
            strategy = get_strategy(formula)
            ctx = DurationContext(operation, batch, equipment, product)
            return strategy.calculate(ctx)
        except ValueError:
            return operation["base_duration_mins"]

    def _datetime_to_minutes(self, dt: datetime) -> int:
        """Преобразует datetime в минуты от t0"""
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        t0_naive = self.t0.replace(tzinfo=None)
        delta = dt - t0_naive
        return max(0, int(delta.total_seconds() / 60))

    async def build_schedule(self) -> Dict[str, Any]:
        print("📊 Загрузка данных из БД...")
        data = await self.data_loader.load_all()
        batches = data["batches"]
        equipment_map = data["equipment"]
        products_map = data["products"]
        ops_map = data["operation_templates"]
        setup_matrix = data["setup_matrix"]
        calendar_events = data["calendar_events"]

        print(f" Загружено {len(batches)} партий")
        print(f"️  Загружено {len(equipment_map)} единиц оборудования")
        print(f"📅 Загружено {len(calendar_events)} событий календаря")

        total_ops = sum(len(ops_map.get(str(b["product_id"]), [])) for b in batches)
        print(f"🔢 Всего операций: {total_ops}")

        # Преобразуем события календаря в минуты
        calendar_minutes = []
        for event in calendar_events:
            start_dt = event["starts_at"]
            end_dt = event["ends_at"]
            start_min = self._datetime_to_minutes(start_dt)
            end_min = self._datetime_to_minutes(end_dt)
            calendar_minutes.append({
                "equipment_id": str(event.get("equipment_id", "")) if event.get("equipment_id") else None,
                "event_type": event["event_type"],
                "start": start_min,
                "end": end_min,
            })

        print(f"⏱️  Календарь в минутах: {len(calendar_minutes)} периодов")

        model = cp_model.CpModel()

        print(" Создание переменных...")
        for batch in batches:
            batch_id = str(batch["id"])
            product_id = str(batch["product_id"])
            equipment_id = str(batch["assigned_equipment_id"])

            product = products_map.get(product_id, {})
            equipment = equipment_map.get(equipment_id, {})
            operations = ops_map.get(product_id, [])

            for op in operations:
                op_id = str(op["id"])
                task_key = (batch_id, op_id)
                duration = self._calculate_duration(op, batch, equipment, product)

                start_var = model.NewIntVar(0, self.horizon_minutes, f"start_{batch_id}_{op_id}")
                end_var = model.NewIntVar(0, self.horizon_minutes, f"end_{batch_id}_{op_id}")
                interval = model.NewIntervalVar(start_var, duration, end_var, f"interval_{batch_id}_{op_id}")

                self.tasks[task_key] = {
                    "interval": interval,
                    "start": start_var,
                    "end": end_var,
                    "batch_id": batch_id,
                    "op_id": op_id,
                    "equipment_id": equipment_id,
                    "product_id": product_id,
                    "needs_boiler": op.get("needs_boiler", False),
                    "needs_cooling": op.get("needs_cooling_zone", False),
                    "needs_operator": op.get("needs_operator", False),
                    "duration": duration,
                    "op": op,
                }

        print(" Добавление ограничений последовательности...")
        seq_constraints_count = 0
        for batch in batches:
            batch_id = str(batch["id"])
            product_id = str(batch["product_id"])
            operations = ops_map.get(product_id, [])

            for i in range(len(operations) - 1):
                curr_op = operations[i]
                next_op = operations[i + 1]
                curr_key = (batch_id, str(curr_op["id"]))
                next_key = (batch_id, str(next_op["id"]))

                if curr_op.get("parallel_group_id") != next_op.get("parallel_group_id"):
                    model.Add(self.tasks[next_key]["start"] >= self.tasks[curr_key]["end"])
                    seq_constraints_count += 1

        print(f"   ✅ Добавлено {seq_constraints_count} ограничений последовательности")

        print("🚫 Добавление NoOverlap и Setup Times...")
        by_equipment: Dict[str, List[Dict]] = {}
        for task_key, task_data in self.tasks.items():
            eq_id = task_data["equipment_id"]
            if eq_id not in by_equipment:
                by_equipment[eq_id] = []
            by_equipment[eq_id].append(task_data)

        nooverlap_count = 0
        setup_constraints_count = 0
        for eq_id, tasks_list in by_equipment.items():
            k = len(tasks_list)
            intervals = [t["interval"] for t in tasks_list]
            model.AddNoOverlap(intervals)
            nooverlap_count += 1

            for i in range(k):
                for j in range(i + 1, k):
                    task_i = tasks_list[i]
                    task_j = tasks_list[j]

                    if task_i["batch_id"] == task_j["batch_id"]:
                        continue

                    prod_i = task_i["product_id"]
                    prod_j = task_j["product_id"]
                    setup_ij = setup_matrix.get((prod_i, prod_j), 90)
                    setup_ji = setup_matrix.get((prod_j, prod_i), 90)

                    i_before_j = model.NewBoolVar(
                        f"eq_{eq_id}_batch_{task_i['batch_id'][:8]}_before_{task_j['batch_id'][:8]}"
                    )
                    model.Add(task_j["start"] >= task_i["end"] + setup_ij).OnlyEnforceIf(i_before_j)
                    model.Add(task_i["start"] >= task_j["end"] + setup_ji).OnlyEnforceIf(i_before_j.Not())
                    setup_constraints_count += 1

        print(f"   ✅ Добавлено {nooverlap_count} NoOverlap и {setup_constraints_count} Setup Time ограничений")

        print("📅 Добавление ограничений календаря простоев...")
        calendar_constraints_count = 0
        for cal_event in calendar_minutes:
            eq_id = cal_event["equipment_id"]
            start_min = cal_event["start"]
            end_min = cal_event["end"]

            affected_tasks = []
            if eq_id:
                for task_key, task_data in self.tasks.items():
                    if task_data["equipment_id"] == eq_id:
                        affected_tasks.append(task_data)
            else:
                affected_tasks = list(self.tasks.values())

            for task_data in affected_tasks:
                ends_before = model.NewBoolVar(
                    f"cal_{task_data['batch_id'][:8]}_{task_data['op_id'][:8]}_before_{start_min}"
                )
                model.Add(task_data["end"] <= start_min).OnlyEnforceIf(ends_before)
                model.Add(task_data["start"] >= end_min).OnlyEnforceIf(ends_before.Not())
                calendar_constraints_count += 1

        print(f"   ✅ Добавлено {calendar_constraints_count} ограничений календаря")

        print("🛡️  Применение плагинов ограничений...")
        for plugin in CONSTRAINT_PLUGINS:
            plugin.apply(model, self.tasks)

        print("🎯 Установка целевой функции (минимизация makespan)...")
        makespan = model.NewIntVar(0, self.horizon_minutes, "makespan")
        for task_data in self.tasks.values():
            model.Add(makespan >= task_data["end"])
        model.Minimize(makespan)

        print(" Запуск solver (OR-Tools CP-SAT)...")
        print(f"   ⏱️  Таймаут: 120 секунд")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"✅ Решение найдено! Статус: {solver.StatusName(status)}")
            return self._extract_solution(solver, equipment_map, products_map, batches)
        else:
            print(f"❌ Решение не найдено. Статус: {solver.StatusName(status)}")
            return {"error": "No feasible solution found", "status": solver.StatusName(status)}

    def _extract_solution(self, solver, equipment_map, products_map, batches) -> Dict:
        """Извлекает решение из solver с названиями сущностей"""
        schedule = []
        for task_key, task_data in self.tasks.items():
            batch_id, op_id = task_key
            start = solver.Value(task_data["start"])
            end = solver.Value(task_data["end"])
            start_dt = self.t0 + timedelta(minutes=start)
            end_dt = self.t0 + timedelta(minutes=end)

            equipment_info = equipment_map.get(task_data["equipment_id"], {})
            product_info = products_map.get(task_data["product_id"], {})
            batch_info = next((b for b in batches if str(b["id"]) == batch_id), {})

            schedule.append({
                "batch_id": batch_id,
                "batch_name": f"Партия {batch_info.get('product_name', 'Unknown')}",
                "op_id": op_id,
                "equipment_id": task_data["equipment_id"],
                "equipment_name": equipment_info.get("name", "Unknown"),
                "product_id": task_data["product_id"],
                "product_name": product_info.get("name", "Unknown"),
                "product_code": product_info.get("code", "Unknown"),
                "start": start_dt,
                "end": end_dt,
                "duration": end - start,
                "operation_name": task_data["op"]["name"],
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
        print(f"❌ Ошибка: {result['error']}")
        return

    print(f"\n🎉 План построен успешно!")
    print(f"📊 Всего задач: {result['total_tasks']}")
    print(f"️  Makespan: {result['makespan_minutes']:.0f} минут ({result['makespan_minutes']/60:.1f} часов)")

    print(f"\n📋 Первые 15 задач:")
    for i, task in enumerate(result["tasks"][:15]):
        print(f"  {i+1:2d}. [{task['operation_name']:<25}] на {task['equipment_name']} "
              f"с {task['start'].strftime('%m-%d %H:%M')} по {task['end'].strftime('%H:%M')} "
              f"({task['duration']} мин)")

    print("\n" + "="*60)
    print("💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ В БД")
    print("="*60)
    saver = ScheduleSaver(org_id=settings.DEFAULT_ORG_ID)
    save_stats = await saver.save_schedule(result)
    print(f"\n✅ ВСЕ ДАННЫЕ СОХРАНЕНЫ!")
    print(f"   - Задач в БД: {save_stats['tasks_saved']}")
    print(f"   - Версия плана: {save_stats['version_id']}")


if __name__ == "__main__":
    asyncio.run(main())