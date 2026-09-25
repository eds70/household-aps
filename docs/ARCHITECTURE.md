# Architecture

Архитектура системы **APS Production Scheduler** — оптимальное планирование производства на базе OR-Tools CP-SAT.

---

## 📋 Содержание

- [Общая схема](#общая-схема)
- [Доменные сущности](#доменные-сущности)
- [Алгоритм планирования](#алгоритм-планирования)
- [Деградация охлаждения](#деградация-охлаждения)
- [Multi-objective](#multi-objective)
- [Снапшоты](#снапшоты)
- [Мульти-тенантность и RBAC](#мульти-тенантность-и-rbac)
- [Версионирование планов](#версионирование-планов)
- [Известные ограничения](#известные-ограничения)

---

## Общая схема

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React 19)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Schedule │ │  Gantt   │ │  Shift   │ │  WhatIf  │ │ Settings │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       │            │            │            │            │         │
│       └────────────┴────────────┴────────────┴────────────┘         │
│                              │ axios + JWT                          │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                         Backend (FastAPI)                           │
│  ┌───────────────────────────┴───────────────────────────────────┐  │
│  │                     API Layer (api/v1/)                       │  │
│  │  auth │ equipment │ orders │ schedule │ gantt │ shift │ ...   │  │
│  │  advisor │ lab │ cz │ personnel │ settings │ plan-settings    │  │
│  │  whatif │ reschedule │ calendar │ audit                       │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────┴───────────────────────────────────┐  │
│  │                    Scheduler Core (scheduler/)                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │  │
│  │  │ DataLoader   │→ │ Production   │→ │ ScheduleSaver│        │  │
│  │  │              │  │ Scheduler    │  │              │        │  │
│  │  └──────────────┘  └──────┬───────┘  └──────┬───────┘        │  │
│  │                           │                 │                │  │
│  │  ┌────────────────────────┼─────────────────┼────────────┐   │  │
│  │  │ routing │ materials │ advisor │ feasibility │ shifts  │   │  │
│  │  │ rescheduler │ cz │ optimization │ whatif             │   │  │
│  │  │ calendar_postprocess │ shift_regenerator            │   │  │
│  │  │ settings_reader │ feature_flags │ snapshot.py       │   │  │
│  │  └────────────────────────┼─────────────────┼────────────┘   │  │
│  │                           │                 │                │  │
│  │  ┌────────────────────────┴─────────────────┴────────────┐   │  │
│  │  │              Constraints (constraints/)               │   │  │
│  │  │  OperatorPoolConstraint │ LabConstraint              │   │  │
│  │  │  CoolingDegradationConstraint │ ...                  │   │  │
│  │  └───────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────┴───────────────────────────────────┐  │
│  │              OR-Tools CP-SAT Solver (9.15+)                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                    PostgreSQL 16 (Docker)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │equipment │ │ products │ │ recipes  │ │ orders   │ │ calendar │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ batch    │ │ schedule │ │scheduled │ │ shift    │ │resource_ │  │
│  │          │ │ _version │ │ _task    │ │          │ │  pool    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │app_      │ │plan_     │ │whatif_   │ │cz_scan_  │ │lab_      │  │
│  │settings  │ │settings  │ │scenario  │ │log       │ │analysis_ │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │equipment_│ │ product_ │ │operation_│ │calendar_ │              │
│  │snapshot  │ │ snapshot │ │ snapshot │ │snapshot  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Доменные сущности

### Оборудование (`equipment`)

| Тип | Описание | Примеры |
|-----|----------|---------|
| `REACTOR` | Реакторы (5000–10000 кг) | Р1, Р2, Р3, Р4 |
| `TANK` | Накопительные ёмкости | Т1, Т2 |
| `FILLING_LINE` | Линии розлива | LINE_1, LINE_2, LINE_3 |
| `MANUAL_STATION` | Ручные станции | LINE_3 (ручная) |
| `BOILER` | Бойлер (2000 кг) | B1 |

Идентификация — по полю **`code`**.

### Продукция (`products`)

Готовая продукция (бутылки, канистры). Связана с рецептурами.

### Рецептуры (`recipes`)

Состав продукта: материалы, количества, операции.

### Техкарты (`operations`)

Последовательность операций для производства партии:
- Загрузка сырья в реактор.
- Нагрев / перемешивание.
- Охлаждение.
- Перекачка в танк (опционально).
- Слив на линию розлива.
- Замыв реактора.

Каждая операция имеет:
- `equipment_type` — тип оборудования.
- `duration_min` — базовая длительность.
- `needs_lab` — требуется ли лабораторный анализ.
- `needs_cooling_zone` — требуется ли зона охлаждения.
- `needs_boiler` — требуется ли бойлер.
- `linked_equipment_id` — для двухресурсных операций.

### Заказы (`orders`)

Заказы на производство продукции:
- `product_id` — что производить.
- `volume_kg` — объём партии.
- `due_date` — срок.
- `priority` — приоритет.

### Партии (`batch`)

Партия — единица производства. Связана с заказом, рецептурой, операциями.

Поля:
- `volume_kg` — объём.
- `is_lab_blocked`, `lab_status` — лабораторные блокировки.
- `cz_marked_qty`, `cz_status` — маркировка ЧЗ.

---

## Алгоритм планирования

### Общая схема

```
1. DataLoader.load()
   ├── Загрузка справочников (equipment, products, recipes, operations)
   ├── Загрузка заказов и партий
   ├── Загрузка календаря (простои, выходные)
   ├── Загрузка смен (shift)
   ├── Загрузка resource_pool (операторы, охлаждение, бойлер)
   ├── Загрузка app_settings / plan_settings
   └── Загрузка feature_flags

2. build_routing()
   ├── Для каждой партии — построение цепочки операций
   ├── Учёт двухресурсных операций (linked_equipment_id)
   ├── Обрезка после lab-операции (truncate_after_lab=True)
   ├── Разбиение длинных LINE_FILL на подзадачи
   └── Назначение operator_pool для каждого шага

3. ProductionScheduler.build_schedule()
   ├── Создание interval-переменных для каждой задачи
   ├── AddNoOverlap для каждого ресурса
   ├── AddCumulative для пулов операторов
   ├── Зависимости между операциями (precedence)
   ├── Двухресурсные операции (linked)
   ├── Деградация охлаждения (fast/slow)
   ├── Multi-objective функция цели
   └── Solver.Solve()

4. calendar_postprocess()
   ├── Топологическая сортировка задач
   ├── Сдвиг задач в рабочие окна (смены минус календарь)
   └── Проверка NoOverlap после сдвига

5. ScheduleSaver.save()
   ├── Деактивация старых версий (is_active = FALSE)
   ├── Создание новой schedule_version
   ├── Заполнение снапшотов (snapshot_all_catalogs)
   ├── Сохранение scheduled_task
   └── Привязка к сменам (shift_id)
```

### OR-Tools CP-SAT

**Переменные:**
- `start_i` — начало задачи i.
- `end_i` — конец задачи i.
- `interval_i` — интервал `[start_i, end_i)`.
- `b_fast_i`, `b_slow_i` — bool-переменные для охлаждения.
- `overlap_ij` — bool-переменные для пересечений.

**Ограничения:**
- `AddNoOverlap(intervals_on_resource)` — для каждого ресурса.
- `AddCumulative(intervals, demands, capacity)` — для пулов операторов.
- `Add(end_i <= start_j)` — для зависимостей.
- `Add(end_i == start_j)` — для двухресурсных операций.

**Целевая функция:**
- Single-objective: `Minimize(makespan)`.
- Multi-objective: взвешенная сумма 5 компонентов (см. [Multi-objective](#multi-objective)).

### Двухресурсные операции

Операция может занимать **два ресурса одновременно**:
- Слив: `реактор + линия` (DIRECT) или `реактор + танк + линия` (VIA_TANK).
- Перекачка: `реактор + танк`.

Реализация: `linked_equipment_id` в `operations`.

### Маршрутизация

`routing.py` строит цепочку операций для каждой партии:

```
DIRECT:    загрузка → нагрев → охлаждение → слив → замыв
VIA_TANK:  загрузка → нагрев → охлаждение → перекачка → слив → замыв
```

**Разбиение длинных LINE_FILL:**
- Порог зависит от `shift_mode`:
  - `1x8`, `3x8` → max_part = 360 мин.
  - `2x12` → max_part = 600 мин.
- Подзадачи идут последовательно: `fill_X_part1 → fill_X_part2 → ...`.

---

## Деградация охлаждения

**Логика по ТЗ:** если в зоне охлаждения (capacity = 2) охлаждается **1 реактор** — операция идёт в обычном режиме (`fast`); если **2+ реактора одновременно** — каждая операция замедляется в `×1.3` (`slow`).

**Модель в `core.py`:**

Для каждой cooling-задачи создаются два взаимоисключающих интервала:
- `fast_interval` — базовая длительность.
- `slow_interval` — `base × 1.3`.

`chosen_end` = fast_end XOR slow_end в зависимости от `b_fast`/`b_slow`.

**Ключевое:**
```
b_slow_i = 1 ⟺ ∃ j ≠ i: cooling_j пересекается с cooling_i
```

Через `overlap_ij` bool-переменные:
```
b_slow_i = 1 → ∀ j ≠ i: overlap_ij = 1
b_slow_i = 0 → ∀ j ≠ i: overlap_ij = 0
```

**`CoolingDegradationConstraint` в `plugins.py`:**
- Ограничивает **общее** число одновременных охлаждений (`AddCumulative` с capacity из `resource_pool.COOLING_ZONE`).
- **Не** делает `AddNoOverlap` на fast-интервалы (это была ошибка, исправлена в Hotfix Итерации 7).

**Результат:** если охлаждения последовательны — все `fast`. Если параллельны — все `slow`.

---

## Multi-objective

**Модуль `backend/app/scheduler/optimization.py`.**

### 5 компонентов целевой функции

| Компонент | Что измеряет | Нормализация |
|-----------|--------------|--------------|
| `makespan` | Общее время плана (мин) | `makespan / horizon_minutes` |
| `setup` | Сумма переналадок (мин) | `setup_sum / horizon_minutes` |
| `underload` | Сумма недогрузки реакторов (кг) | `underload_sum / total_max_fill_kg` |
| `cooling_slow` | Число замедленных охлаждений (шт) | `cooling_slow / total_cooling_count` |
| `tardiness` | Сумма просрочек due_date (мин) | `tardiness_sum / (num_batches * horizon_minutes)` |

### Веса

Веса в `[0, 1]` задаются в `app_settings` (или `plan_settings`):
- `weight_makespan = 1.0` (по умолчанию).
- Остальные = `0.0`.

### Реализация

```python
OptimizationWeights:
    - from_settings() — читает из app_settings.
    - validate() — проверка корректности.
    - to_int() — приведение к fixed-point (PRECISION = 10000).
    - build_multi_objective() — строит взвешенную сумму с нормализацией.
```

**Аккумуляторы:**
- `setup_sum`, `underload_sum`, `cooling_slow_count`, `tardiness_sum`.

**Нормализация** каждого компонента в `[0, PRECISION]` через `AddDivisionEquality`.

**Обратная совместимость:** если только `weight_makespan = 1.0`, остальные = 0 — работает как single-objective.

---

## Снапшоты

### Проблема

Глобальные настройки (`app_settings`) применяются ко **всем** планам одновременно. Если пользователь изменил `horizon_hours` с 720 на 1000 и пересчитал план — старые планы становятся «невалидными»:
- Нельзя воспроизвести их результат.
- Нельзя сравнить два плана, построенные с разными настройками.

### Решение: `plan_settings`

Каждый план (`schedule_version`) хранит **свой снапшот** настроек в таблице `plan_settings`.

**Структура:**
```
plan_settings:
    - organization_id, schedule_version_id — привязка.
    - setting_key, setting_value (JSONB) — ключ-значение.
    - value_type, category, label, description — метаданные (снапшот).
    - min_value, max_value, options, display_order, is_system.
    - UNIQUE (schedule_version_id, setting_key).
    - FOREIGN KEY ... ON DELETE CASCADE.
```

**Триггер `copy_app_settings_to_plan`:**
- `AFTER INSERT ON schedule_version` — автоматически копирует все `app_settings` в `plan_settings` нового плана.
- Идемпотентен (`ON CONFLICT DO NOTHING`).
- Работает на уровне БД — не нужен ни Python, ни API.

**Чтение:**
- `DataLoader(version_id=...)` — читает настройки из `plan_settings` этого плана.
- Если `version_id=None` или `plan_settings` пуст → fallback на `app_settings`.

**Что это даёт:**
- ✅ **Изоляция:** два плана имеют независимые настройки.
- ✅ **Воспроизводимость:** зная `plan_settings`, можно пересчитать ровно тот же результат.
- ✅ **Сравнимость:** можно корректно сравнивать два плана.
- ✅ **Обратная совместимость:** старые планы без `plan_settings` работают через `app_settings`.

**Подробнее:** см. [ADR 0003](adr/0003-plan-settings-per-plan.md).

### Снапшоты справочников (Итерация 13.15)

Помимо `plan_settings`, каждый план имеет **снапшоты справочников**:
- `equipment_snapshot`
- `product_snapshot`
- `operation_snapshot`
- `calendar_snapshot`

Эти таблицы содержат «слепок» справочников на момент создания/расчёта плана. При открытии плана в readonly-режиме UI читает данные **из снапшотов**, а не из живых справочников.

**Заполняются из двух мест:**

1. **При создании плана** (`POST /api/v1/schedule/versions`) — модуль `snapshot.py` вызывает `snapshot_all_catalogs`.
2. **При расчёте плана** (`POST /api/v1/schedule/build`) — `ScheduleSaver._do_save` делегирует в `snapshot_all_catalogs`.

**Проблема (исправлена в 13.15):**
До Итерации 13.15 снапшоты заполнялись **только** при расчёте плана. Если план создавался «пустым» (например, через мастер `PlanSettingsWizard`), снапшоты оставались пустыми, и UI показывал пустые гриды на всех страницах справочников.

**Решение:**
- Новый модуль `snapshot.py` с функцией `snapshot_all_catalogs`.
- `POST /schedule/versions` вызывает эту функцию сразу после создания плана.
- API возвращает `has_snapshot` — UI индицирует планы без снапшотов иконкой ⚠.
- `GanttPage` показывает предупреждение вместо диаграммы для пустого плана.

**Подробнее:** см. [ADR 0002](adr/0002-snapshot-tables-for-versioning.md).

---

## Мульти-тенантность и RBAC

### Мульти-тенантность

Все таблицы содержат `organization_id`. Все запросы фильтруются по `organization_id` текущего пользователя.

### Роли

| Роль | Права |
|------|-------|
| `ADMIN` | Полный доступ. Управление настройками, пользователями, миграциями. |
| `PLANNER` | Планирование, перепланирование, what-if, plan_settings. |
| `MASTER` | Мастер смены: факт, блокировка партий, ЧЗ. |
| `LAB` | Лаборатория: блокировка/разблокировка партий. |
| `VIEWER` | Только просмотр. |

### RBAC

Реализован через FastAPI dependencies:
```python
from app.auth.dependencies import require_role

@router.put("/settings/{key}")
async def update_setting(
    key: str,
    user: User = Depends(require_role("ADMIN", "PLANNER")),
):
    ...
```

---

## Версионирование планов

### `schedule_version`

Каждый план — отдельная версия:
- `id` — UUID.
- `organization_id` — организация.
- `is_active` — активная версия (только одна на организацию).
- `parent_version_id` — родительская версия (для перепланирования).
- `created_at`, `created_by` — метаданные.

### `scheduled_task`

Задачи плана:
- `id` — UUID.
- `schedule_version_id` — привязка к версии.
- `batch_id` — партия.
- `equipment_id` — оборудование.
- `operation_name` — имя операции.
- `start_at`, `end_at` — время.
- `shift_id` — привязка к смене.
- `operator_pool` — пул операторов.
- `cooling_mode` — `fast` | `slow` | `NULL`.
- `is_pinned` — закреплена ли задача.
- `status` — `PLANNED` | `IN_PROGRESS` | `DONE`.
- `depends_on_task_ids` — список UUID задач-предшественников (JSONB).

### Hotfix Итерации 5

- **Деактивация старых версий:** при создании новой версии все старые деактивируются (`is_active = FALSE`).
- **Фильтрация по `schedule_version_id`:** в `shift.py`, `gantt.py` добавлен параметр `version_id`.
- **Таймзона в `by-date`:** сравнение по МСК-дате.
- **`is_lab_blocked` в Ганте:** добавлены `LEFT JOIN batch` и поля `is_lab_blocked`, `lab_status`, `lab_block_reason`.

**Миграция данных** `fix_versions_hotfix.sql` — деактивирует все старые версии, оставляя самую свежую.

### Что происходит при создании плана

```
POST /api/v1/schedule/versions
    ↓
1. INSERT INTO schedule_version (name, version_type, comment)
    ↓
2. Триггер copy_app_settings_to_plan срабатывает автоматически:
   INSERT INTO plan_settings SELECT ... FROM app_settings
    ↓
3. snapshot_all_catalogs(session, org_id, version_id):
   INSERT INTO equipment_snapshot SELECT ... FROM equipment
   INSERT INTO product_snapshot SELECT ... FROM product
   INSERT INTO operation_snapshot SELECT ... FROM operation_template
   INSERT INTO calendar_snapshot SELECT ... FROM calendar_event
    ↓
4. Ответ: {id, name, has_snapshot: true, snapshot_stats: {...}}
```

План полностью готов к открытию в readonly-режиме: справочники читаются из снапшотов, настройки — из `plan_settings`.

### Что происходит при расчёте плана

```
POST /api/v1/schedule/build
    ↓
1. ProductionScheduler(org_id, version_id=None) — читает глобальные app_settings
    ↓
2. ScheduleSaver.save_schedule(result):
   ├── Деактивация старых версий (is_active = FALSE)
   ├── INSERT INTO schedule_version (is_active = TRUE)
   ├── snapshot_all_catalogs(...)
   └── INSERT INTO scheduled_task (...) для каждой задачи
```

---

## Известные ограничения

1. Слив на линию добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает.
2. Материальные ограничения — предупреждения Advisor, не жёсткие constraints в CP-SAT.
3. График поставок — все поставки считаются доступными.
4. Крем-мыло 5л (Р2) имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Advisor подсвечивает `ROUTE_MISMATCH`.
5. Лабораторные блокировки: после блокировки партии нужно вручную запустить перепланирование.
6. Персонал: нет HR-подсистемы (нет ФИО, смен, отпусков). Только пулы с capacity.
7. Solver: при большом горизонте может выдать `FEASIBLE` вместо `OPTIMAL`.
8. Деградация охлаждения активна, но в тестовом кейсе ТЗ `slow` не появляется (узкие места в других ресурсах).
9. ЧЗ: формат данных от камер — гибкий JSON с опциональными полями.
10. ЧЗ: `enable_cz_auto_close = false` — автозакрытие задачи слива отключено.
11. ЧЗ: ручное сопоставление сироты требует ввода UUID партии.
12. Режимы смен: при смене `shift_mode` все задачи теряют привязку к сменам.
13. Разбиение `LINE_FILL`: длинные задачи разбиваются на много подзадач.
14. Pan + drag на Ганте: setup и downtime не таскаются.
15. What-if: удаление DONE-сценария не удаляет результирующий план.
16. Multi-objective: если все веса = 0 (кроме makespan), работает как single-objective.
17. What-if RUNNING: нельзя удалить сценарий во время расчёта.
18. What-if changes: формат JSON не строго типизирован на уровне Pydantic.
19. `plan_settings` (13.14): существующие планы (созданные до миграции `add_21.sql`) не имеют `plan_settings` — работают через fallback на `app_settings`.
20. `plan_settings` (13.14): при изменении `app_settings` после создания плана, значения в `plan_settings` этого плана не обновляются — это by design (снапшот).
21. Мастер настроек плана (13.14): работает только с существующими планами.
22. Системные настройки (13.14): `shift_intervals`, `shift_duration_hours` — `is_system = true`, не редактируются через мастер.
23. **Снапшоты справочников (13.15):** старые планы (созданные до Итерации 13.15) могут иметь пустые снапшоты. Они помечены ⚠ в списке планов, при открытии показывают предупреждение. Пересоздайте план через мастер или удалите его.

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/API.md](API.md) — описание API.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.
- [docs/ROADMAP.md](ROADMAP.md) — план развития.
- [docs/adr/README.md](adr/README.md) — индекс ADR.