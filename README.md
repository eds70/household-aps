# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **4.0.0** (Итерации 0–12 завершены)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-9.15+-F7931E)](https://developers.google.com/optimization)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

---

## ⚡ TL;DR — запуск за 60 секунд

Из корня проекта (household-aps):

```
.\quickstart.ps1
```

Скрипт сделает всё: поднимет PostgreSQL в Docker, применит схему и демо-данные, поставит Python/npm-зависимости, создаст админа.

После — в двух терминалах:

```
Терминал 1 (Backend):
cd backend; .\.venv\Scripts\Activate.ps1; python run_server.py

Терминал 2 (Frontend):
cd frontend; npm run dev
```

**Открыть:** http://localhost:5173
**Логин:** `admin@household.ru` / `admin123`

---

## 📋 Описание

APS (Advanced Planning and Scheduling) — полнофункциональная система оптимального планирования производства для химической промышленности (бытовая химия).

Строит расписание загрузки оборудования с учётом:
- **Технологических карт** и строгой последовательности операций
- **Цепочек рабочих центров** (реактор → накопительная ёмкость → линия розлива)
- **Освобождения реактора** только после полного слива жидкости
- **Двухресурсных операций** (слив занимает реактор+линию, перекачка — реактор+танк)
- **Матрицы замывки** (30/90 минут) между партиями разных ПФ
- **Календаря простоев** (выходные, плановые ремонты, аварии)
- **Ресурсных ограничений** (аппаратчики, операторы линий, операторы ручной станции, лаборанты, бойлер, зона охлаждения)
- **Остатков сырья** и графика поставок
- **Режимов смен** (`1x8`, `3x8`, `2x12`) с настраиваемыми интервалами
- **Лабораторных блокировок** (партия не участвует в планировании до одобрения)
- **Деградации охлаждения** (`fast`/`slow` при 2+ параллельных реакторах)
- **Маркировки Честного Знака** (приём сканов от камер ТС, прогресс по партии, Advisor-подсказки)
- **Мульти-тенантности** и **версионирования планов** (снапшоты справочников)
- **Централизованных настроек** (`app_settings` — единый источник правды)
- **Multi-objective оптимизации** (5 компонентов целевой функции с весами)
- **What-if сценариев** (сценарное планирование без изменения БД)

## 🎯 Ключевые возможности

### Итерация 0 — Фундамент
- ✅ Эталонный тест-кейс из ТЗ (Раздел 4)
- ✅ Централизованная конфигурация через `organization_settings`
- ✅ Feature-флаги для поэтапного внедрения
- ✅ Structured logging планировщика
- ✅ CI на GitHub Actions

### Итерация 1 — Цепочки рабочих центров
- ✅ Модуль `routing.py` — построение цепочек операций
- ✅ **Двухресурсные операции** (`linked_equipment_id`)
- ✅ Слив: `реактор → линия` (DIRECT) или `реактор → танк → линия` (VIA_TANK)
- ✅ Замыв реактора после слива (в конце цепочки)
- ✅ `NoOverlap` по каждому ресурсу отдельно
- ✅ Оптимизация setup-ограничений (270 вместо 9714)
- ✅ Корректный расчёт длительности слива (кг ПФ → бутылки → минуты)
- ✅ Makespan ~553 ч (было 1856 ч)

### Итерация 2 — Материальные ограничения и Advisor
- ✅ Модуль `materials.py` — расчёт потребности в сырье по всем партиям
- ✅ Модуль `advisor.py` — типы подсказок:
    - 🔴 **MATERIAL_SHORTAGE** — дефицит сырья
    - 🟡 **UNDERLOAD** — неполная загрузка реактора
    - 🔵 **ROUTE_MISMATCH** — VIA_TANK без танка
    - 🔵 **EQUIPMENT_GAP** — простои оборудования
    - 🔵 **COOLING_DEGRADATION** — охлаждение с замедлением (Итерация 7)
    - 🟡 **CZ_INCOMPLETE** — партия слита, но не промаркирована (Итерация 8)
- ✅ Модуль `feasibility.py` — оценка исполнимости плана
- ✅ API: `GET /api/v1/schedule/advice`, `POST /api/v1/schedule/feasibility`
- ✅ UI: панель Advisor с фильтрацией по severity
- ✅ **Обнаружение дефицита отдушки (150 кг) и соли (1500 кг)** — ключевые кейсы ТЗ

### Итерация 3 — Сменное планирование и РМ мастера
- ✅ Таблица `shift` — смены (одна в день, 08:00–20:00)
- ✅ Поля в `scheduled_task`: `shift_id`, `actual_qty`, `material_load_at`, `status`
- ✅ Модуль `shifts.py` — работа со сменами
- ✅ API `shift.py` — 5 эндпоинтов
- ✅ Frontend `ShiftPage.tsx` — **рабочее место мастера**:
    - Задания смены по рабочим центрам
    - **Переходящие** задачи из предыдущей смены
    - Отметка загрузки сырья в реактор
    - Внесение факта (start/end/qty/status)
- ✅ Пункт меню **«Мастер смены»**
- ✅ Все 282 задачи привязаны к сменам

### Итерация 4 — Перепланирование
- ✅ Модуль `rescheduler.py` — перепланирование с учётом изменений
- ✅ Типы изменений: `DELAY`, `BREAKDOWN`, `QTY_CHANGE`, `MANUAL`
- ✅ Закрепление задач (`is_pinned`) и заморозка до `frozen_before`
- ✅ Журнал перепланирований `reschedule_log`
- ✅ API `reschedule.py`:
    - `POST /api/v1/schedule/reschedule` — перепланировать
    - `GET /api/v1/schedule/compare` — сравнить две версии
    - `PUT /api/v1/schedule/task/{id}/pin` — закрепить/открепить задачу
- ✅ UI: диалог перепланирования в `SchedulePage.tsx`
- ✅ Сценарий «Аварийная остановка Р4 (25–28.09)»

### Итерация 5 — Лаборатория и блокировки
- ✅ Поля в `batch`: `is_lab_blocked`, `lab_status`, `lab_block_reason`, `lab_blocked_at`, `lab_blocked_by`
- ✅ Таблица `lab_analysis_log` — журнал всех проверок лаборатории
- ✅ Модуль `lab.py` — 7 эндпоинтов API:
    - `GET  /api/v1/lab/pending` — партии, ожидающие анализа / заблокированные
    - `GET  /api/v1/lab/batch/{id}` — статус партии по лаборатории
    - `GET  /api/v1/lab/batch/{id}/log` — журнал проверок
    - `POST /api/v1/lab/batch/{id}/block` — заблокировать партию
    - `POST /api/v1/lab/batch/{id}/unblock` — разблокировать
    - `POST /api/v1/lab/batch/{id}/approve` — одобрить после анализа
    - `POST /api/v1/lab/batch/{id}/request` — запросить анализ
- ✅ Планировщик **исключает заблокированные партии** из расписания (`core.py`, `rescheduler.py`)
- ✅ `build_routing(truncate_after_lab=True)` — обрезка цепочки после lab-операции
- ✅ UI `ShiftPage.tsx`: индикатор блокировки, кнопки блокировки/разблокировки, чипы `Ожидает лабу` / `Заблокировано` / `Одобрено`
- ✅ UI `GanttPage.tsx`: 🔒 красная рамка + фильтр «Только заблокированные» + Badge `Заблокировано: N`
- ✅ Роли `LAB`, `MASTER`, `ADMIN` имеют право блокировать партии

#### Hotfix Итерации 5 (устранены унаследованные баги)

- ✅ **Hotfix #1 — деактивация старых версий плана** (`saver.py`):
  при создании новой версии все старые деактивируются (`is_active = FALSE`).
  Иначе `shift.py` и `gantt.py` собирают задачи из всех версий → визуальное задвоение в 5–10 раз.
- ✅ **Hotfix #2 — фильтрация по `schedule_version_id`** (`shift.py`, `gantt.py`):
  добавлен параметр `version_id` (опциональный).
  Если не задан — берётся последняя активная версия (`is_active = TRUE`).
- ✅ **Hotfix #3 — таймзона в `by-date`** (`shift.py`):
  сравнение по UTC-дате: `(starts_at AT TIME ZONE 'UTC')::date = :shift_date`.
  Иначе naive datetime из Python не находит смену, если сессия asyncpg не в UTC.
- ✅ **Hotfix #4 — `is_lab_blocked` в Ганте** (`gantt.py`):
  добавлены `LEFT JOIN batch` и поля `is_lab_blocked`, `lab_status`, `lab_block_reason`.
  Без этого фильтр «Только заблокированные» всегда возвращал пустоту.
- ✅ **Миграция данных** `fix_versions_hotfix.sql` — деактивирует все старые версии, оставляя самую свежую.

### Итерация 6 — Люди как ресурс

- ✅ **4 пула операторов** в `resource_pool`:
    - `REACTOR_OPERATOR` — **3 аппаратчика** на 4 реактора (по ТЗ)
    - `LINE_OPERATOR` — **2 оператора** на 3 линии розлива
    - `MANUAL_OPERATOR` — **1 оператор** ручной станции (LINE_3)
    - `LAB` — **1 лаборант**
- ✅ **Колонка `scheduled_task.operator_pool`** — сохранение пула на уровне задачи
- ✅ **Колонка `resource_pool.updated_at`** — аудит изменений
- ✅ **UNIQUE-констрейнт** `resource_pool (organization_id, type)` — защита от дублей
- ✅ **`AddCumulative`** для каждого пула (жёсткое ограничение параллельности)
- ✅ **Модуль `plugins.py`** — `OperatorPoolConstraint` + `LabConstraint`:
    - `OperatorPoolConstraint` — для реакторных, линейных и ручных операторов
    - `LabConstraint` — для лабораторных анализов (capacity=1)
    - `CoolingZoneConstraint` — теперь берёт capacity из `resource_pool`
- ✅ **Модуль `routing.py`** — назначение пула для каждого шага:
    - реакторные операции → `REACTOR_OPERATOR`
    - лабораторные → `LAB`
    - `fill_*` на `FILLING_LINE` → `LINE_OPERATOR`
    - `fill_*` на `MANUAL_STATION` → `MANUAL_OPERATOR`
- ✅ **`core.py`** — передача `resource_pools` в плагины, `operator_pool` в задачи
- ✅ **`saver.py`** — сохранение `operator_pool` в `scheduled_task`
- ✅ **API `/api/v1/personnel`** — 4 эндпоинта:
    - `GET /pools` — список пулов с загрузкой
    - `GET /pools/{id}` — один пул
    - `PUT /pools/{id}` — редактирование capacity (ADMIN, PLANNER)
    - `GET /load` — краткая загрузка
- ✅ **Алгоритм `peak_concurrent`** — метод «заметающей прямой»:
    - Корректная обработка полуоткрытых интервалов `[start, end)`.
    - Задачи на стыке считаются последовательными (не пересекающимися).
- ✅ **UI страница «Персонал»**:
    - Таблица пулов: имя, тип, capacity, задачи, пик, загрузка (progress bar)
    - Редактирование capacity через диалог
    - Индикация перегрузки (peak > capacity — красным)
    - Режим просмотра для сохранённых версий
- ✅ **Feature-флаги** `enable_operator_pools`, `enable_manual_station`
- ✅ **Гибкость:** capacity можно менять через UI без правок кода

### Итерация 7 — Охлаждение с деградацией

**Логика по ТЗ:** если в зоне охлаждения (capacity = 2) охлаждается **1 реактор** — операция идёт в обычном режиме (`fast`); если **2+ реактора одновременно** — каждая операция замедляется в `×1.3` (`slow`).

**Реализация:**
- ✅ Миграция `add_10.sql` — feature-флаг + коэффициент
- ✅ Миграция `add_10b.sql` — колонка `scheduled_task.cooling_mode`
- ✅ Настройки в `organization_settings`:
    - `enable_cooling_degradation` = `true`
    - `cooling_degradation_factor` = `1.3`
    - `cooling_zone_capacity` = `2`
- ✅ `resource_pool.COOLING_ZONE` = capacity 2
- ✅ В `core.py` — модель деградации:
    - Для каждой cooling-задачи создаются два взаимоисключающих интервала: `fast_interval` (базовая длительность) и `slow_interval` (`base × 1.3`)
    - `chosen_end` = fast_end XOR slow_end в зависимости от `b_fast`/`b_slow`
    - **Ключевое:** `b_slow_i = 1 ⟺ ∃ j ≠ i: cooling_j пересекается с cooling_i` (через `overlap_ij` bool-переменные)
- ✅ В `plugins.py` — `CoolingDegradationConstraint`:
    - Ограничивает **общее** число одновременных охлаждений (`AddCumulative` с capacity из `resource_pool.COOLING_ZONE`)
    - **Не** делает `AddNoOverlap` на fast-интервалы (это была ошибка, исправлена)
- ✅ `scheduled_task.cooling_mode` сохраняется (`fast` | `slow` | `NULL`)
- ✅ API `/api/v1/gantt/` возвращает `cooling_mode` в каждой задаче
- ✅ Excel-экспорт содержит колонку «Режим охлаждения»
- ✅ API `/api/v1/shift/` возвращает `cooling_mode` в заданиях смены
- ✅ Advisor выдаёт `COOLING_DEGRADATION` (WARNING/INFO)
- ✅ UI `GanttPage.tsx`:
    - 🟠 оранжевая пунктирная рамка для `slow`-операций
    - Иконка `⏳` в задаче
    - Бейдж «ОХЛАЖДЕНИЕ ЗАМЕДЛЕНО (×1.3)» в тултипе
    - Легенда с «⏳ Замедленное охлаждение»
    - Чип статистики «⏳ Замедленное охлаждение: N»
    - Фильтр «Только замедленное охлаждение»
    - Чип «Показано: N / M» при активном фильтре
    - Кнопка «Сбросить фильтры»
- ✅ UI `ShiftPage.tsx`:
    - Чип «Замедленное охлаждение ×1.3» для `slow`
    - Чип «Охлаждение (норма)» для `fast`
    - Оранжевая подсветка карточки задачи при `slow`
    - Информационный Alert в диалоге внесения факта
- ✅ UI `PersonnelPage.tsx`: пул `COOLING_ZONE` (и `BOILER`) с иконками
- ✅ Тест-кейс ТЗ показал: **0 ложных `slow`** (раньше было 3)

#### Hotfix Итерации 7

- ✅ **Исправлена модель деградации в `core.py`**:
  раньше `b_slow` выбирался solver'ом произвольно (минимизация makespan ломала логику), из-за чего `slow` ставился даже для **последовательных** охлаждений. Теперь `b_slow` жёстко связан с фактическим пересечением интервалов — если охлаждения идут последовательно, всё корректно помечается `fast`.
- ✅ **`CoolingDegradationConstraint` больше не делает `AddNoOverlap(fast_intervals)`** — он был неверен, потому что fast-интервалы могут быть неактивны (`b_fast=0`), а slow-интервалы при этом не эксклюзивны.

### Итерация 8 — Честный Знак и интеграции

**Логика по ТЗ (п. 8):** факт готовой продукции должен попадать в систему автоматически при считывании кодов маркировки ЧЗ камерами технического зрения.

**Реализация:**

- ✅ **Миграция `add_11.sql`:**
    - Поля в `batch`: `cz_marked_qty`, `cz_last_scan_at`, `cz_status`
    - Таблица `cz_scan_log` — журнал всех сканирований ЧЗ
    - Feature-флаг `enable_cz_integration = true`
    - Настройки: `cz_completion_threshold`, `cz_api_key`, `enable_cz_auto_close`
- ✅ **Модуль `scheduler/cz.py`** — бизнес-логика:
    - `resolve_batch_for_scan()` — fallback-сопоставление скана с партией:
        - По `batch_id` (если камера знает)
        - По `task_id` (если камера знает)
        - По `line_code` + время (окно ±2 часа, только `LINE_FILL` задачи)
        - Иначе — скан «сирота» (`batch_id = NULL`)
    - `compute_planned_qty()` — расчёт ожидаемого количества бутылок
    - `recalc_batch_cz_status()` — пересчёт `cz_status` по порогу
    - `get_batch_progress()` — прогресс партии
- ✅ **API `/api/v1/cz`** — 7 эндпоинтов:
    - `POST   /scan` — приём скана от камеры (API-key в `X-CZ-Api-Key`)
    - `GET    /batch/{id}/progress` — прогресс маркировки партии
    - `GET    /pending` — партии в ожидании маркировки
    - `GET    /log` — журнал сканирований с фильтрами
    - `GET    /stats` — сводная статистика
    - `POST   /scan/{id}/attach` — ручное сопоставление «сироты» (ADMIN, PLANNER, MASTER)
    - `DELETE /scan/{id}` — удаление скана (только ADMIN)
- ✅ **Идемпотентность:** `UNIQUE (organization_id, cz_code)` + `ON CONFLICT DO NOTHING`.
  Повторный скан → `duplicate: true`, без двойного увеличения `cz_marked_qty`.
- ✅ **Порог завершения:** `cz_completion_threshold = 0.95` (настраивается).
  Статусы: `NOT_APPLICABLE` | `PENDING` | `IN_PROGRESS` | `COMPLETED`.
- ✅ **Advisor `CZ_INCOMPLETE`** (WARNING):
  Срабатывает, если задача `LINE_FILL` имеет `status = DONE`, но `batch.cz_status != COMPLETED`.
- ✅ **UI `CzPage.tsx`** — отдельная страница:
    - Сводка: партии по статусам, сканы, порог
    - Таблица партий с прогресс-барами
    - Журнал сканирований с фильтрами (линия, «только сироты»)
    - Диалог ручного сопоставления «сироты»
- ✅ **UI `ShiftPage.tsx`** — индикатор ЧЗ на задачах слива:
    - Прогресс-бар «X / Y (Z%)»
    - Чип статуса ЧЗ («ожидает», «в работе», «завершено»)
    - Кнопка **«ЧЗ»** в шапке для ручного обновления прогресса
- ✅ **UI `GanttPage.tsx`:**
    - Чип статистики «📷 Не промаркировано: N»
    - Фильтр «Только не промаркированные»
    - Иконка `📷` на задачах слива с незавершённой маркировкой
    - Синяя пунктирная рамка для таких задач
- ✅ **UI `MainLayout.tsx`:** пункт меню **«Честный Знак»**
- ✅ **API `/api/v1/gantt/`** расширен полями `task_role`, `cz_status`, `cz_marked_qty`.

### Итерация 9 — Рефакторинг, реальное перепланирование, drag-and-drop

**Реальное перепланирование (A3):**
- ✅ `rescheduler.py` больше не клонирует задачи — запускает `ProductionScheduler.build_schedule()` заново
- ✅ Изменения применяются к входным данным:
    - `BREAKDOWN` → `calendar_event`
    - `QTY_CHANGE` → `batch.volume_kg`
    - `DELAY` → сдвиг `planned_start` + `is_pinned = TRUE`
- ✅ Гибридная логика pinned:
    - `is_pinned = TRUE` → жёсткий constraint
    - `actual_start IS NOT NULL` → жёсткий constraint
    - `frozen_before` → только метаданные (не constraint)
- ✅ Fallback: если solver не нашёл решение с pinned — пробует без них
- ✅ Новая версия получает `parent_version_id = from_version_id`
- ✅ `frozen_before` корректно записывается в БД (UTC)
- ✅ 25 новых тестов в `test_rescheduler.py`

**Drag-and-Drop на диаграмме Ганта (C2):**
- ✅ Новый эндпоинт `PUT /api/v1/schedule/task/{id}/move`
- ✅ Валидация: длительность задачи не может меняться при перемещении
- ✅ Frontend `onMove` в `GanttPage.tsx` вызывает API и обновляет state
- ✅ UX-оптимизация:
    - Hover-курсор `grab` на задачах
    - Активное перетаскивание — `grabbing` + тень + снижение прозрачности
    - Пунктирная синяя рамка на выбранной задаче
    - `not-allowed` на downtime/setup (они не таскаются)
    - Отключён pan диаграммы (`moveable: false`) — устранена конкуренция за drag
- ✅ При ошибке API задача возвращается на исходное место

**Рефакторинг (A1, B1, B2):**
- ✅ Удалён мёртвый код `PLUGIN_MANAGED_RESOURCE_TYPES`
- ✅ Единая функция `find_shift_id_for_time` в `shifts.py` — используется в `saver.py`
- ✅ Расширен `PERSONNEL_POOL_TYPES` — теперь UI показывает все 6 пулов
- ✅ `routing.py`: операции `needs_cooling_zone` и `needs_boiler` получают `operator_pool`
- ✅ `REACTOR_OPERATOR.capacity` исправлен на 3 (по ТЗ)

### Итерация 10 — Календарная постобработка и разбиение длинных задач

**Календарная постобработка (замена жёстких ограничений в CP-SAT):**
- ✅ Новый модуль `backend/app/scheduler/calendar_postprocess.py`
- ✅ Календарные ограничения **убраны из CP-SAT** — теперь постпроцессор сдвигает задачи в рабочие окна после solver'а
- ✅ Топологическая сортировка задач по зависимостям (`depends_on_op_ids`)
- ✅ Учёт `NoOverlap` при размещении — задачи на одном оборудовании не пересекаются
- ✅ Рабочие окна строятся из **смен** (`shift`) минус события календаря (WEEKEND)
- ✅ Сдвиг задач с выходных в рабочие окна
- ✅ **Результат:** `overlaps_after = 0`, `dependency_violations = 0`
- ✅ Makespan сохраняется в разумных пределах (не «улетает» на десятки дней вперёд)

**Разбиение длинных LINE_FILL на подзадачи:**
- ✅ Задачи `LINE_FILL` длиннее порога разбиваются на N равных подзадач
- ✅ Порог зависит от `shift_mode` (см. Итерацию 11):
    - `1x8` → max_part = 360 мин
    - `3x8` → max_part = 360 мин
    - `2x12` → max_part = 600 мин
- ✅ Подзадачи идут последовательно: `fill_X_part1 → fill_X_part2 → ...`
- ✅ Каждая подзадача привязана к своему `operation_name` с суффиксом `(часть i/N)`
- ✅ Каждая подзадача попадает в свою смену

**API `operation_name` в `scheduled_task`:**
- ✅ Миграция `add_12.sql` — колонка `scheduled_task.operation_name`
- ✅ Фактическое имя операции сохраняется (в т.ч. для динамических `fill_*` подзадач)
- ✅ `saver.py` записывает `operation_name` из routing

**Изменения в `models.py`:**
- ✅ `ScheduleBuildRequest.horizon_hours` по умолчанию: `720` (30 дней, было 2160)
- ✅ `ScheduleBuildRequest.timeout_seconds` по умолчанию: `600` (было 120)
- ✅ Обоснование: меньший горизонт ускоряет propagation, больший таймаут даёт solver'у время на OPTIMAL

**Advisor:**
- ✅ Новый тип подсказки `CZ_INCOMPLETE` (Итерация 8)
- ✅ `COOLING_DEGRADATION` теперь приоритетнее в сортировке

### Итерация 11 — Режимы смен, централизованные настройки, финальная полировка

**Шаг 4: Регенерация смен в БД**
- ✅ Новый модуль `backend/app/scheduler/shift_regenerator.py`
- ✅ `get_intervals_for_mode(mode)` — возвращает интервалы и длительность для режима:
    - `1x8` → `[{"start": "08:00", "end": "16:00"}]`, 8 часов
    - `3x8` → `[{"start": "00:00", "end": "08:00"}, {"start": "08:00", "end": "16:00"}, {"start": "16:00", "end": "00:00"}]`, 8 часов
    - `2x12` → `[{"start": "08:00", "end": "20:00"}, {"start": "20:00", "end": "08:00"}]`, 12 часов
- ✅ `regenerate_shifts(session, org_id, mode, date_from, date_to, reset_shift_ids=True)`:
    - Удаляет старые смены в диапазоне.
    - Создаёт новые смены по интервалам.
    - Выходные (сб, вс) — `is_working = FALSE`.
    - Сбрасывает `shift_id` в `scheduled_task` (старые UUID невалидны).
    - Диапазон по умолчанию: 90 дней от `2026-09-01`.
- ✅ Вызов из `POST /api/v1/settings/shift-mode` (только ADMIN)

**Шаг 5: Централизованные настройки через `app_settings`**
- ✅ Миграция `add_13.sql` — таблица `app_settings` с метаданными (тип, min/max, options, label, is_system)
- ✅ Перенос всех настроек из `organization_settings` в `app_settings`
- ✅ Новый модуль `backend/app/scheduler/settings_reader.py`:
    - `read_feature_flags(db, org_id)` — читает все `enable_*` флаги одним запросом
    - `read_setting(db, org_id, key, default)` — читает одну настройку
    - `read_settings_dict(db, org_id, keys)` — читает несколько настроек одним запросом
    - `read_float`, `read_str`, `read_bool` — утилиты приведения типов
- ✅ `data_loader.py`: `_load_org_settings` → `_load_app_settings` (читает из `app_settings`)
- ✅ Все API-модули (`advisor.py`, `lab.py`, `cz.py`, `personnel.py`, `reschedule.py`, `shift.py`) переведены на `settings_reader`
- ✅ Убрано дублирование SQL-запросов (~50 строк)
- ✅ Единый источник правды — таблица `app_settings`

**Шаг 6: Режимы смен и `allow_weekend_work`**
- ✅ `core.py` читает `shift_mode` и `allow_weekend_work` из `app_settings`
- ✅ `shift_mode` передаётся в `build_routing()` — влияет на разбиение длинных задач
- ✅ `allow_weekend_work` передаётся в `apply_calendar_postprocess()`:
    - `false` (по умолчанию) — постпроцессор сдвигает задачи с выходных
    - `true` — постпроцессор пропускается, задачи могут попадать на выходные
- ✅ Миграция `add_14.sql` — настройка `allow_weekend_work`
- ✅ `shift_regenerator.py` — пересоздаёт смены при смене режима
- ✅ `shift.py` (`by-date`): сравнение по МСК-дате (`AT TIME ZONE 'Europe/Moscow'`)
- ✅ UI `ShiftPage.tsx`: селектор смены дня (три смены для `3x8`)

**Шаг 7: UI-полировка и pan/zoom в Ганте**
- ✅ `SettingsPage.tsx` — страница настроек с группировкой по категориям:
    - `planning` — планирование
    - `shifts` — режим смен
    - `cooling` — охлаждение
    - `calendar` — календарь (`allow_weekend_work`)
    - `lab` — лаборатория
    - `materials` — материалы
    - `cz` — Честный Знак
    - `resources` — персонал
    - `features` — feature-флаги
- ✅ `SchedulePage.tsx` — читает `horizon_hours` и `timeout_seconds` из `app_settings`:
    - При загрузке: `settingsApi.getCategory('planning')`
    - При построении плана: сохраняет параметры перед расчётом
    - Кнопка «Сохранить настройки» для явного сохранения
    - Чип «Из настроек» — индикатор, что значения загружены из БД
- ✅ `ShiftPage.tsx` — фикс UX мастера смены:
    - **Фиксированная шапка** (заголовок, селектор смены, кнопки) — `flexShrink: 0`
    - **Скроллируемый список задач** — `flexGrow: 1, minHeight: 0, overflow: auto`
    - Шапка больше не «уезжает» вверх при большом количестве задач
- ✅ `PlainContext.tsx` — **фикс цикла ре-рендера**:
    - `useCallback` для `loadVersions`, `setPlan`, `createPlan`, `deletePlan`
    - Стабильные ссылки на функции → `useEffect` в потребителях не перезапускается
    - `loadVersions` вызывается **только после аутентификации** (`isAuthenticated && !isLoading`)
    - Устранена ошибка `401 Unauthorized` при первом заходе на `/login`
    - Advisor больше не «дёргается» (бесконечный цикл ре-рендера устранён)
- ✅ `GanttPage.tsx` — **pan + zoom + drag одновременно** (Механизм 3):
    - `moveable: true` — pan по пустому месту (перетаскивание диаграммы)
    - `zoomable: true` — zoom колёсиком мыши (без Ctrl)
    - `editable.updateTime` как **функция** `(item) => boolean`:
        - `true` для реальных задач — их можно таскать
        - `false` для setup и downtime — не таскаются, pan диаграммы
    - Убран `moveable: false` (Итерация 9) — pan снова включён
    - Текст-подсказка внизу: «Клик по пустому месту + drag = панорамирование • Клик по задаче + drag = перемещение • Колесо = зум»
- ✅ `index.css` — курсоры для разных зон диаграммы:
    - `.vis-panel.vis-center/left/right` → `grab` (pan)
    - `.vis-item.vis-range` (реальные задачи) → `grab`
    - `.vis-item.item-downtime` / `.item-setup` → `not-allowed`
    - `.gantt-readonly .vis-item.vis-range` → `default`
    - `:active` → `grabbing` для активного pan или drag

**Итоги Итерации 11:**
- ✅ 268 тестов зелёные (`pytest tests/ -v`)
- ✅ UI: мастер смены, Гант, настройки — работают
- ✅ Solver: OPTIMAL за ~78 секунд
- ✅ Makespan: 12526 мин (~8.7 дня)
- ✅ 0 overlaps, 0 нарушений зависимостей (постпроцессор)

### Итерация 12 — Multi-objective и what-if сценарии

**A. Multi-objective оптимизация:**
- ✅ Новый модуль `backend/app/scheduler/optimization.py`:
    - `OptimizationWeights` — dataclass с 5 весами `[0, 1]`
    - `from_settings()` — читает из `app_settings`
    - `validate()` — проверка корректности
    - `to_int()` — приведение к fixed-point (`PRECISION = 10000`)
    - `build_multi_objective()` — строит взвешенную сумму с нормализацией
    - 4 аккумулятора: `setup_sum`, `underload_sum`, `cooling_slow_count`, `tardiness_sum`
- ✅ 5 компонентов целевой функции:
    - `makespan` — общее время (мин)
    - `setup` — сумма переналадок (мин)
    - `underload` — сумма недогрузки реакторов (кг)
    - `cooling_slow` — число замедленных охлаждений (шт)
    - `tardiness` — сумма просрочек `due_date` (мин)
- ✅ Нормализация каждого компонента в `[0, PRECISION]` через `AddDivisionEquality`:
    - `makespan` / `horizon_minutes`
    - `setup_sum` / `horizon_minutes`
    - `underload_sum` / `total_max_fill_kg`
    - `cooling_slow` / `total_cooling_count`
    - `tardiness_sum` / `(num_batches * horizon_minutes)`
- ✅ **Обратная совместимость:** если только `weight_makespan = 1.0`, остальные = 0 — работает как single-objective
- ✅ `SettingsPage.tsx` — новая категория «Оптимизация» с 5 слайдерами
- ✅ Миграция `add_15.sql` — 5 настроек в категории `optimization`

**B. What-if сценарии:**
- ✅ Таблица `whatif_scenario` (миграция `add_16.sql`)
- ✅ Новый модуль `backend/app/scheduler/whatif.py` — `WhatIfRunner`:
    - `create_scenario`, `get_scenario`, `list_scenarios`, `update_scenario`, `delete_scenario`
    - `run_scenario` — запуск (async через BackgroundTasks)
    - `compare` — сравнение base vs result
    - `_apply_changes` — оркестрация применения изменений
    - `_apply_shift_mode`, `_apply_capacity_changes`, `_apply_order_changes`, `_apply_calendar_changes`
    - `_compute_metrics` — 6 метрик для сравнения
- ✅ **Архитектура 2 транзакций:**
    - Транзакция №1 (rollback): применяем изменения + запускаем scheduler → откат
    - Транзакция №2 (commit): сохраняем результат через `ScheduleSaver` → commit
- ✅ **7 эндпоинтов API `/api/v1/whatif`:**
    - `POST   /scenarios` — создать
    - `GET    /scenarios` — список
    - `GET    /scenarios/{id}` — один
    - `PUT    /scenarios/{id}` — обновить (DRAFT)
    - `DELETE /scenarios/{id}` — удалить (кроме RUNNING)
    - `POST   /scenarios/{id}/run` — запустить (async, 202 Accepted)
    - `GET    /scenarios/{id}/compare` — сравнить
- ✅ **Async запуск:**
    - `POST /run` возвращает `202 Accepted` сразу
    - Расчёт в `BackgroundTasks` (отдельная сессия БД)
    - Frontend polling через `GET /scenarios/{id}` каждые 3 сек
    - Статусы: `DRAFT` → `RUNNING` → `DONE`/`FAILED`
- ✅ **7 типов изменений:**
    - `add_order` — добавить заказ
    - `cancel_order` — отменить заказ
    - `change_qty` — изменить объём
    - `change_due_date` — изменить due_date
    - `shift_mode` — режим смен
    - `resource_capacity` — capacity пулов
    - `calendar_events` (add/remove) — события календаря
- ✅ **UI `/whatif`** (`WhatIfPage.tsx`):
    - AgGrid со списком сценариев
    - Диалог создания/редактирования с JSON-редактором
    - 5 кнопок-шаблонов (Режим смен, +Заказ, +Capacity, Авария Р4, Полный пример)
    - Polling статуса `RUNNING` каждые 3 секунды
    - Диалог результата с таблицей метрик и Δ (зелёный = улучшение, красный = ухудшение)
    - Кнопка «Открыть план» → переход на `/gantt?version_id=...`
    - Кнопка удаления (🗑) для всех статусов кроме `RUNNING`
    - Tooltip: «план останется в истории» для `DONE` сценариев
- ✅ **Rollback гарантирован:** `shift_mode`, `capacity`, `orders`, `calendar_events` **не меняются** в БД после what-if

**Архитектурные патчи Итерации 12:**
- ✅ `DataLoader` + `ProductionScheduler` принимают `session` извне (для what-if — видят незакоммиченные изменения)
- ✅ `ScheduleSaver` принимает `session` (не делает commit при `_owns_session=False`)
- ✅ `shift_regenerator` — `flush()` вместо `commit()` + `AT TIME ZONE 'Europe/Moscow'` вместо `'UTC'`
- ✅ `settings.py` — явный `commit()` после `regenerate_shifts`
- ✅ `whatif.py` — 2 транзакции без явного `begin()` (SQLAlchemy async автоматически начинает)

**Итоги Итерации 12:**
- ✅ 321 тестов зелёные (`pytest tests/ -v`)
- ✅ What-if работает end-to-end (UI + backend)
- ✅ Rollback 100% надёжен
- ✅ Solver: OPTIMAL за 7–25 секунд
- ✅ 45 новых тестов в `test_whatif.py`

## 🛠️ Стек технологий

### Backend
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| Python | 3.12+ | Язык программирования |
| FastAPI | 0.141+ | REST API фреймворк |
| OR-Tools | 9.15+ | CP-SAT solver для оптимизации |
| Uvicorn | 0.52+ | ASGI сервер |
| SQLAlchemy | 2.0+ | Async ORM |
| asyncpg | 0.31+ | Async драйвер PostgreSQL |
| Pydantic | 2.13+ | Валидация данных |
| python-jose / bcrypt | latest | JWT авторизация |

### База данных
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| PostgreSQL | 16+ | Реляционная СУБД (Docker) |
| Docker | 24+ | Контейнеризация |

### Frontend
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| React | 19.x | UI фреймворк |
| TypeScript | ~6.0 | Типизация |
| Vite | 8.x | Сборщик |
| MUI (Material-UI) | 9.4 | UI компоненты |
| AG Grid Community | 36.1 | Таблицы с inline-редактированием |
| vis-timeline | 8.5 | Интерактивная диаграмма Ганта |
| axios | 1.20 | HTTP-клиент с интерсепторами |
## 📁 Структура проекта

```
household-aps/
├── quickstart.ps1                         # ⚡ Скрипт быстрого старта
├── README.md
├── backend/
│   ├── app/
│   │   ├── api/v1/                        # REST API endpoints
│   │   │   ├── auth.py
│   │   │   ├── equipment.py
│   │   │   ├── products.py
│   │   │   ├── materials.py
│   │   │   ├── recipes.py
│   │   │   ├── operations.py
│   │   │   ├── orders.py
│   │   │   ├── schedule.py
│   │   │   ├── gantt.py                   # Итерация 1, 5, 7, 8 + hotfix
│   │   │   ├── calendar.py
│   │   │   ├── advisor.py                 # Итерация 2, 7, 8 + Шаг 5
│   │   │   ├── shift.py                   # Итерация 3, 5, 7, 11 + hotfix
│   │   │   ├── shift_models.py
│   │   │   ├── reschedule.py              # Итерация 4, 9 + Шаг 5
│   │   │   ├── reschedule_models.py
│   │   │   ├── lab.py                     # Итерация 5 + Шаг 5
│   │   │   ├── lab_models.py
│   │   │   ├── personnel.py               # Итерация 6 + Шаг 5
│   │   │   ├── personnel_models.py
│   │   │   ├── cz.py                      # Итерация 8 + Шаг 5
│   │   │   ├── cz_models.py
│   │   │   ├── settings.py                # Итерация 11 (Шаг 4, 6)
│   │   │   ├── whatif.py                  # Итерация 12
│   │   │   ├── whatif_models.py           # Итерация 12
│   │   │   └── models.py
│   │   ├── auth/                          # JWT + RBAC
│   │   ├── core/                          # Конфигурация
│   │   ├── scheduler/                     # Ядро планировщика
│   │   │   ├── core.py                    # Итерация 5, 6, 7, 11, 12 + hotfix
│   │   │   ├── data_loader.py             # Итерация 5, 6, 11, 12
│   │   │   ├── routing.py                 # Итерация 1, 5, 6, 10, 11
│   │   │   ├── materials.py               # Итерация 2
│   │   │   ├── advisor.py                 # Итерация 2, 7, 8
│   │   │   ├── feasibility.py             # Итерация 2
│   │   │   ├── shifts.py                  # Итерация 3
│   │   │   ├── rescheduler.py             # Итерация 4, 5, 9
│   │   │   ├── cz.py                      # Итерация 8
│   │   │   ├── saver.py                   # Итерация 5, 6, 7, 12
│   │   │   ├── feature_flags.py           # Итерация 6, 7, 8, 11
│   │   │   ├── settings.py                # Итерация 11, 12
│   │   │   ├── settings_reader.py         # Итерация 11 (Шаг 5) — НОВЫЙ
│   │   │   ├── shift_regenerator.py       # Итерация 11 (Шаг 4), 12 — НОВЫЙ
│   │   │   ├── calendar_postprocess.py    # Итерация 10 — НОВЫЙ
│   │   │   ├── optimization.py            # Итерация 12 — НОВЫЙ
│   │   │   ├── whatif.py                  # Итерация 12 — НОВЫЙ
│   │   │   ├── logging_config.py
│   │   │   ├── duration/                  # Стратегии длительностей
│   │   │   └── constraints/
│   │   │       └── plugins.py             # Итерация 1, 6, 7 + hotfix
│   │   └── main.py
│   ├── migrations/                        # История миграций
│   │   ├── add_history_0_2.sql
│   │   ├── add_06.sql
│   │   ├── add_06b.sql
│   │   ├── add_07.sql                     # Итерация 4
│   │   ├── add_08.sql                     # Итерация 5
│   │   ├── fix_versions_hotfix.sql        # hotfix Итерации 5
│   │   ├── add_09.sql                     # Итерация 6
│   │   ├── add_09b.sql                    # Итерация 6
│   │   ├── add_09c.sql                    # Итерация 6
│   │   ├── add_09d.sql                    # Итерация 6
│   │   ├── add_10.sql                     # Итерация 7
│   │   ├── add_10b.sql                    # Итерация 7
│   │   ├── add_11.sql                     # Итерация 8
│   │   ├── add_12.sql                     # Итерация 10 (operation_name)
│   │   ├── add_13.sql                     # Итерация 11 (app_settings)
│   │   ├── add_14.sql                     # Итерация 11 (allow_weekend_work)
│   │   ├── add_15.sql                     # Итерация 12 (optimization веса)
│   │   ├── add_16.sql                     # Итерация 12 (whatif_scenario)
│   │   └── fix_shift_names.sql
│   ├── .env
│   ├── init_schema.sql                    # v3.0.0
│   ├── seed_demo.py
│   ├── seed_demo_data.sql
│   ├── scripts/create_admin_user.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   └── run_server.py
├── frontend/
│   ├── src/
│   │   ├── components/layout/             # MainLayout
│   │   ├── context/                       # AuthContext, PlanContext
│   │   ├── hooks/                         # useDoubleClick
│   │   ├── pages/                         # Login, Equipment, ..., WhatIfPage
│   │   ├── services/api.ts
│   │   ├── types/index.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 🚀 Быстрый старт

### Автоматический (рекомендуется)

Из корня проекта:

```
.\quickstart.ps1
```

**Флаги:**
- `-SkipDb` — пропустить PostgreSQL
- `-SkipSeed` — пропустить схему и демо-данные
- `-SkipFrontend` — пропустить npm-зависимости
- `-Help` — справка

**Если PowerShell блокирует запуск скриптов:**

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Ручной

#### Предварительные требования
- Python 3.12+
- Node.js 18+
- Docker

#### Шаг 1: Запуск PostgreSQL

```
docker run --name aps_postgres -e POSTGRES_USER=aps -e POSTGRES_PASSWORD=aps_secret -e POSTGRES_DB=household -p 5432:5432 -d postgres:16
```

#### Шаг 2: Инициализация схемы и демо-данных

**⚠️ ВАЖНО:** применять SQL-файлы через `docker cp` + `psql -f`, а не через `Get-Content | docker exec` — иначе PowerShell испортит кириллицу.

```
docker cp backend\init_schema.sql    aps_postgres:/tmp/init_schema.sql
docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

#### Шаг 3: Создание администратора

```
cd backend
python -m scripts.create_admin_user
```

#### Шаг 4: Запуск Backend

```
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python run_server.py
```

*Swagger UI: http://localhost:8000/docs*

#### Шаг 5: Запуск Frontend

```
cd frontend
npm install
npm run dev
```

*Приложение: http://localhost:5173*
*Демо-доступ: `admin@household.ru` / `admin123`*

## 📚 Документация API

После запуска backend: **http://localhost:8000/docs**

### Основные эндпоинты

**Авторизация:**
- `POST /api/v1/auth/login` — вход
- `GET /api/v1/auth/me` — профиль

**Справочники:**
- `GET/POST/PUT/DELETE /api/v1/equipment` — оборудование
- `GET/POST/PUT/DELETE /api/v1/products` — продукты
- `GET/POST/PUT/DELETE /api/v1/materials` — материалы
- `GET/POST/PUT/DELETE /api/v1/recipes` — рецептуры
- `GET/POST/PUT/DELETE /api/v1/operations` — техкарты
- `GET/POST/PUT/DELETE /api/v1/orders` — заказы
- `GET/POST/PUT/DELETE /api/v1/calendar` — календарь простоев

**Планирование:**
- `POST /api/v1/schedule/build` — построить план
- `GET /api/v1/schedule/versions` — список версий
- `POST /api/v1/schedule/versions` — создать версию
- `DELETE /api/v1/schedule/versions/{id}` — удалить

**Advisor (Итерация 2 + Итерация 7 + Итерация 8):**
- `GET /api/v1/schedule/advice` — подсказки (включая COOLING_DEGRADATION, CZ_INCOMPLETE)
- `POST /api/v1/schedule/feasibility` — оценка исполнимости

**Сменное планирование (Итерация 3 + Итерация 7 + Итерация 11):**
- `GET /api/v1/shift/list` — список смен
- `GET /api/v1/shift/by-date/{date}` — **список смен** на дату (для `3x8` — 3 смены)
- `GET /api/v1/shift/{shift_id}/tasks` — задания смены (с `cooling_mode`)
- `GET /api/v1/shift/{shift_id}/carryover` — переходящие задания
- `POST /api/v1/shift/task/{task_id}/fact` — внести факт

**Перепланирование (Итерация 4 + Итерация 9):**
- `POST /api/v1/schedule/reschedule` — перепланировать
- `GET /api/v1/schedule/compare` — сравнить две версии
- `PUT /api/v1/schedule/task/{id}/pin` — закрепить/открепить
- `PUT /api/v1/schedule/task/{id}/move` — переместить задачу (drag-and-drop)

**Лаборатория (Итерация 5):**
- `GET /api/v1/lab/pending` — партии, ожидающие анализа
- `GET /api/v1/lab/batch/{id}` — статус партии
- `GET /api/v1/lab/batch/{id}/log` — журнал проверок
- `POST /api/v1/lab/batch/{id}/block` — заблокировать
- `POST /api/v1/lab/batch/{id}/unblock` — разблокировать
- `POST /api/v1/lab/batch/{id}/approve` — одобрить
- `POST /api/v1/lab/batch/{id}/request` — запросить анализ

**Персонал (Итерация 6):**
- `GET /api/v1/personnel/pools` — список пулов с загрузкой
- `GET /api/v1/personnel/pools/{id}` — один пул
- `PUT /api/v1/personnel/pools/{id}` — редактировать capacity (ADMIN, PLANNER)
- `GET /api/v1/personnel/load` — краткая загрузка

**Честный Знак (Итерация 8):**
- `POST   /api/v1/cz/scan` — приём скана от камеры (API-key в `X-CZ-Api-Key`)
- `GET    /api/v1/cz/batch/{id}/progress` — прогресс маркировки партии
- `GET    /api/v1/cz/pending` — партии в ожидании маркировки
- `GET    /api/v1/cz/log` — журнал сканирований с фильтрами
- `GET    /api/v1/cz/stats` — сводная статистика
- `POST   /api/v1/cz/scan/{id}/attach` — ручное сопоставление «сироты» (MASTER+)
- `DELETE /api/v1/cz/scan/{id}` — удаление скана (ADMIN)

**Настройки (Итерация 11):**
- `GET    /api/v1/settings/schema` — реестр настроек (метаданные)
- `GET    /api/v1/settings/categories` — список категорий
- `GET    /api/v1/settings/` — все настройки
- `GET    /api/v1/settings/category/{cat}` — настройки категории
- `PUT    /api/v1/settings/` — массовое обновление
- `PUT    /api/v1/settings/{key}` — обновление одной
- `POST   /api/v1/settings/shift-mode` — смена режима смен (ADMIN) + пересоздание смен

**What-if сценарии (Итерация 12):**
- `POST   /api/v1/whatif/scenarios` — создать сценарий
- `GET    /api/v1/whatif/scenarios` — список сценариев
- `GET    /api/v1/whatif/scenarios/{id}` — один сценарий
- `PUT    /api/v1/whatif/scenarios/{id}` — обновить (DRAFT)
- `DELETE /api/v1/whatif/scenarios/{id}` — удалить (DRAFT/FAILED/DONE)
- `POST   /api/v1/whatif/scenarios/{id}/run` — запустить расчёт (async, 202)
- `GET    /api/v1/whatif/scenarios/{id}/compare` — сравнить с базовым

**Гант:**
- `GET /api/v1/gantt/` — данные диаграммы (с `cooling_mode`, `cz_status`, `cz_marked_qty`)
- `GET /api/v1/gantt/export` — экспорт в Excel (с колонкой «Режим охлаждения»)
## 🧩 Ключевые сущности

### Оборудование
- **REACTOR** — реакторы (5000–10000 кг)
- **TANK** — накопительные ёмкости
- **FILLING_LINE** — линии розлива
- **MANUAL_STATION** — ручные станции
- **BOILER** — бойлер (2000 кг)

Все оборудование идентифицируется по полю **`code`**.

### Пулы операторов (Итерация 6)

| Пул | Capacity | Обслуживает |
|-----|----------|-------------|
| `REACTOR_OPERATOR` | 3 | 4 реактора |
| `LINE_OPERATOR` | 2 | 3 линии розлива |
| `MANUAL_OPERATOR` | 1 | LINE_3 (ручная станция) |
| `LAB` | 1 | Лабораторные анализы |
| `COOLING_ZONE` | 2 | Зона охлаждения (Итерация 7) |
| `BOILER` | 1 | Бойлер |

**Логика:** планировщик **физически не может** запланировать 4 реактора одновременно — только 3. `AddCumulative` запрещает это.

### Режимы смен (Итерация 11)

Настраиваются через `shift_mode` в `app_settings`. Значения:

| Режим | Интервалы | Длительность смены | Смен в день |
|-------|-----------|-------------------|-------------|
| `1x8` | `08:00–16:00` | 8 ч | 1 |
| `3x8` | `00:00–08:00`, `08:00–16:00`, `16:00–00:00` | 8 ч | 3 |
| `2x12` | `08:00–20:00`, `20:00–08:00` | 12 ч | 2 |

**Логика:**
- `shift_intervals` хранится в `app_settings` как JSON-массив.
- `shift_duration_hours` — целое число.
- При смене `shift_mode` через `POST /api/v1/settings/shift-mode` — таблица `shift` **пересоздаётся** (`shift_regenerator.py`).
- `shift_id` в `scheduled_task` сбрасывается (старые UUID невалидны).
- Требуется пересчитать план.

**Влияние на разбиение длинных LINE_FILL:**
- `1x8`, `3x8` → max_part = 360 мин
- `2x12` → max_part = 600 мин

### Режимы охлаждения (Итерация 7)

| Режим | Когда | Длительность | Иконка |
|-------|-------|--------------|--------|
| `fast` | 1 реактор охлаждается | base | ❄️ |
| `slow` | 2+ реактора одновременно | base × 1.3 | ⏳ |
| `null` | Операция не является охлаждением | — | — |

**Модель в `core.py`:** `b_slow_i = 1 ⟺ ∃ j: cooling_j пересекается с cooling_i`. Если охлаждения последовательны — все `fast`.

### Лабораторные блокировки (Итерация 5)

**Статусы партии:**

| Статус | Описание |
|--------|----------|
| `NOT_REQUIRED` | Партия не требует анализа |
| `PENDING_LAB` | Ожидает анализа |
| `APPROVED` | Одобрено |
| `BLOCKED` | Заблокировано (не в плане) |

**Логика:**
1. После операции `needs_lab=true` партия → `PENDING_LAB`.
2. Блокировка → `is_lab_blocked=true`, `lab_status=BLOCKED`.
3. Планировщик **исключает заблокированные** из расписания.
4. Разблокировка → `APPROVED`.

**Права:** `LAB`, `MASTER`, `ADMIN`.

### Маркировка Честного Знака (Итерация 8)

**Статусы маркировки:**

| Статус | Описание |
|--------|----------|
| `NOT_APPLICABLE` | Партия не требует маркировки |
| `PENDING` | 0 сканов |
| `IN_PROGRESS` | 0 < marked / planned < threshold |
| `COMPLETED` | marked / planned ≥ threshold |

**Поток данных:**
1. Камера ТС сканирует код ЧЗ → `POST /api/v1/cz/scan` с заголовком `X-CZ-Api-Key`.
2. Backend идемпотентно вставляет скан в `cz_scan_log` (UNIQUE на `cz_code`).
3. **Fallback-сопоставление** с партией:
- По `batch_id` (если камера знает).
- По `task_id` (если камера знает).
- По `line_code` + время (`LINE_FILL` задача в окне ±2 часа).
- Иначе — скан «сирота» (`batch_id = NULL`).
4. Если партия найдена — увеличиваем `batch.cz_marked_qty`, обновляем `cz_status`.
5. Advisor выдаёт **`CZ_INCOMPLETE`** (WARNING), если задача слива закрыта, а маркировка не завершена.

**Права:** `MASTER`/`PLANNER`/`ADMIN` — ручное сопоставление сирот; `ADMIN` — удаление скана.

### Централизованные настройки (Итерация 11)

**Таблица `app_settings`** — единый источник правды. Содержит метаданные:
- `category` — для группировки в UI
- `setting_key` — ключ
- `setting_value` — JSONB-значение
- `value_type` — `int` | `float` | `bool` | `str` | `json` | `select`
- `label`, `description` — для UI
- `min_value`, `max_value`, `options` — валидация
- `is_system` — запрет на редактирование через UI

**Чтение:** через модуль `settings_reader.py`:
- `read_feature_flags(db, org_id)` — все `enable_*` флаги одним запросом
- `read_setting(db, org_id, key, default)` — одна настройка
- `read_settings_dict(db, org_id, keys)` — несколько настроек

**Категории:**

| Категория | Label | Что содержит |
|-----------|-------|--------------|
| `planning` | Планирование | `planning_start_date`, `horizon_hours`, `timeout_seconds`, `max_fill_percent` |
| `shifts` | Режим смен | `shift_mode`, `shift_intervals`, `shift_duration_hours`, `work_start_time`, `work_end_time` |
| `cooling` | Охлаждение | `enable_cooling_degradation`, `cooling_degradation_factor`, `cooling_zone_capacity` |
| `calendar` | Календарь | `max_task_hours_for_calendar`, `max_fill_part_hours`, `allow_weekend_work` |
| `lab` | Лаборатория | `enable_lab_blocking` |
| `materials` | Материалы | `enable_material_constraints` |
| `cz` | Честный Знак | `enable_cz_integration`, `cz_completion_threshold`, `cz_api_key`, `enable_cz_auto_close` |
| `resources` | Персонал | `enable_operator_pools`, `enable_manual_station` |
| `features` | Feature-флаги | `enable_tank_routing`, `enable_shift_planning`, `enable_rescheduling`, `enable_advisor` |
| `optimization` | Оптимизация | `weight_makespan`, `weight_setup`, `weight_underload`, `weight_cooling_slow`, `weight_tardiness` |

### Multi-objective оптимизация (Итерация 12)

**Модуль `backend/app/scheduler/optimization.py`.**

**5 компонентов целевой функции:**

| Компонент | Что измеряет | Нормализация |
|-----------|--------------|--------------|
| `makespan` | Общее время плана (мин) | `makespan / horizon_minutes` |
| `setup` | Сумма переналадок (мин) | `setup_sum / horizon_minutes` |
| `underload` | Сумма недогрузки реакторов (кг) | `underload_sum / total_max_fill_kg` |
| `cooling_slow` | Число замедленных охлаждений (шт) | `cooling_slow / total_cooling_count` |
| `tardiness` | Сумма просрочек due_date (мин) | `tardiness_sum / (num_batches * horizon_minutes)` |

**Веса в `[0, 1]`:**
- `0.0` — компонент отключён.
- `1.0` — максимальный приоритет.
- Все веса суммируются в целевую функцию: `w1*norm1 + w2*norm2 + ...`

**Fixed-point для CP-SAT:**
- `PRECISION = 10000` (4 знака после запятой).
- Каждый компонент нормируется в `[0, PRECISION]` через `AddDivisionEquality`.

**По умолчанию:** `weight_makespan = 1.0`, остальные = 0 — работает как single-objective.

### What-if сценарии (Итерация 12)

**Таблица `whatif_scenario`:**

| Поле | Описание |
|------|----------|
| `id`, `organization_id` | Идентификация |
| `name`, `comment` | Метаданные |
| `base_version_id` | Базовый план |
| `result_version_id` | Результат (новая `schedule_version`) |
| `changes` JSONB | Изменения (orders, shift_mode, resource_capacity, calendar_events) |
| `status` | `DRAFT` \| `RUNNING` \| `DONE` \| `FAILED` |
| `created_at`, `updated_at`, `created_by` | Аудит |

**Формат `changes`:**

```json
{
  "orders": [
    {"action": "add_order", "product_code": "GP_CREAM_1L", "target_qty": 25000, "due_date": "..."},
    {"action": "cancel_order", "order_id": "uuid"},
    {"action": "change_qty", "order_id": "uuid", "new_qty": 30000},
    {"action": "change_due_date", "order_id": "uuid", "new_due_date": "..."}
  ],
  "shift_mode": "3x8",
  "resource_capacity": {"REACTOR_OPERATOR": 4, "LINE_OPERATOR": 3},
  "calendar_events": [
    {"action": "add", "event_type": "BREAKDOWN", "equipment_code": "REACTOR_4",
     "starts_at": "...", "ends_at": "...", "comment": "..."}
  ]
}
```

**Архитектура 2 транзакций:**
1. **Транзакция №1 (rollback):** применить изменения → запустить scheduler → получить результат в памяти → rollback (изменения исчезают).
2. **Транзакция №2 (commit):** сохранить результат через `ScheduleSaver` → обновить статус → commit.

**Ключевая особенность:** `DataLoader` и `ScheduleSaver` принимают `session` извне, чтобы видеть незакоммиченные изменения из транзакции №1.

**Что гарантируется:**
- ✅ Основная БД **не меняется** после what-if.
- ✅ Результат — **отдельная `schedule_version`** в истории планов.
- ✅ Удаление сценария **не удаляет** план.

### Feature-флаги

Читаются через `settings_reader.read_feature_flags()` из `app_settings`.

| Флаг | Статус | Итерация |
|------|--------|----------|
| enable_tank_routing | ✅ ON | 1 |
| enable_advisor | ✅ ON | 2 |
| enable_material_constraints | ✅ ON | 2 |
| enable_shift_planning | ✅ ON | 3 |
| enable_rescheduling | ✅ ON | 4 |
| enable_lab_blocking | ✅ ON | 5 |
| enable_operator_pools | ✅ ON | 6 |
| enable_manual_station | ✅ ON | 6 |
| enable_cooling_degradation | ✅ ON | 7 |
| enable_cz_integration | ✅ ON | 8 |

### Параметры организации (app_settings)

| Ключ | Значение | Категория | Назначение |
|------|----------|-----------|------------|
| `planning_start_date` | `2026-09-01T08:00:00` | planning | Дата старта планирования (МСК) |
| `horizon_hours` | `720` | planning | Горизонт планирования (30 дней) |
| `timeout_seconds` | `600` | planning | Таймаут solver (сек) |
| `max_fill_percent` | `0.70` | planning | Максимальная загрузка реактора |
| `shift_mode` | `"2x12"` | shifts | Режим смен |
| `shift_intervals` | JSON | shifts | Интервалы смен (системный) |
| `shift_duration_hours` | `12` | shifts | Длительность смены (системный) |
| `work_start_time` | `"08:00"` | shifts | Начало рабочего дня |
| `work_end_time` | `"20:00"` | shifts | Конец рабочего дня |
| `allow_weekend_work` | `false` | calendar | Разрешить работу в выходные |
| `cooling_degradation_factor` | `1.3` | cooling | Коэффициент замедления охлаждения |
| `cooling_zone_capacity` | `2` | cooling | Максимум реакторов в зоне охлаждения |
| `cz_completion_threshold` | `0.95` | cz | Порог завершения маркировки партии |
| `cz_api_key` | `"dev-cz-api-key-change-in-production"` | cz | API-ключ для вебхука ЧЗ |
| `enable_cz_auto_close` | `false` | cz | Автозакрытие задачи слива при завершении ЧЗ |
| `weight_makespan` | `1.0` | optimization | Вес makespan |
| `weight_setup` | `0.0` | optimization | Вес переналадок |
| `weight_underload` | `0.0` | optimization | Вес недогрузки реакторов |
| `weight_cooling_slow` | `0.0` | optimization | Вес замедленного охлаждения |
| `weight_tardiness` | `0.0` | optimization | Вес просрочек due_date |

## 🧪 Тестирование

```
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Текущее состояние:** 321 passed, 12 warnings.

| Файл | Тестов | Что проверяет |
|------|--------|---------------|
| `test_tz_case.py` | 41 | Эталонный кейс ТЗ |
| `test_materials.py` | 11 | Расчёт потребности в сырье |
| `test_advisor.py` | 17 | Подсказки Advisor (включая CZ_INCOMPLETE) |
| `test_routing.py` | 15 | Цепочки операций + разбиение LINE_FILL (Итерация 11) |
| `test_shifts.py` | 16 | Смены и API смен |
| `test_rescheduler.py` | 18 | Перепланирование + фильтрация блокировок |
| `test_lab.py` | 24 | Лабораторные блокировки + разбиение |
| `test_personnel.py` | 15 | Люди как ресурс (Итерация 6) |
| `test_cooling_degradation.py` | 19 | Охлаждение с деградацией (Итерация 7 + hotfix) |
| `test_cz.py` | 52 | Честный Знак (Итерация 8) |
| `test_whatif.py` | 45 | What-if сценарии (Итерация 12) |
| `test_versions.py` | 4 | Hotfix: деактивация версий |
| `test_dependencies.py` | 9 | FastAPI dependencies |
| `test_auth_models.py` | 9 | Pydantic-модели авторизации |
| `test_security.py` | 5 | JWT и bcrypt |
| `test_config.py` | 3 | Конфигурация |

**Warnings** (не критично):
- `StarletteDeprecationWarning` — `httpx` с `starlette.testclient` устарел.
- `DeprecationWarning` — `anyio.abc.BlockingPortal` alias устарел.
- `PydanticDeprecatedSince20` — `class Config` вместо `ConfigDict` в некоторых моделях.

## 🔧 Полезные команды

### Проверить статус PostgreSQL

```
docker ps --filter "name=aps_postgres"
```

### Подключиться к БД

```
docker exec -it aps_postgres psql -U aps -d household
```

### Пересоздать БД с нуля

```
docker exec aps_postgres psql -U aps -d household -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker cp backend\init_schema.sql    aps_postgres:/tmp/init_schema.sql
docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

### Применить SQL-миграцию (правильный способ)

```
docker cp backend\migrations\add_16.sql aps_postgres:/tmp/add_16.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_16.sql
```

### Очистить кэш Python

```
cd backend
Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

### Полная очистка (снести контейнер и БД)

```
docker rm -f aps_postgres
```

### Экспорт данных из БД

```
docker exec aps_postgres pg_dump -U aps household > backup.sql
```

### Проверить настройки режима смен (Итерация 11)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('shift_mode', 'shift_intervals', 'shift_duration_hours', 'allow_weekend_work') ORDER BY setting_key;"
```

### Проверить веса multi-objective (Итерация 12)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE category = 'optimization' ORDER BY display_order;"
```

### Проверить смены на конкретную дату (МСК)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT name, starts_at AT TIME ZONE 'Europe/Moscow' AS starts_msk, ends_at AT TIME ZONE 'Europe/Moscow' AS ends_msk, is_working FROM shift WHERE organization_id = '00000000-0000-0000-0000-000000000001' AND (starts_at AT TIME ZONE 'Europe/Moscow')::date = '2026-09-01' ORDER BY starts_at;"
```

### Проверить настройки охлаждения (Итерация 7)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('enable_cooling_degradation', 'cooling_degradation_factor', 'cooling_zone_capacity');"
```

### Проверить настройки ЧЗ (Итерация 8)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key LIKE 'cz_%' OR setting_key = 'enable_cz_integration' ORDER BY setting_key;"
```

### Проверить пулы ресурсов

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT type, capacity FROM resource_pool ORDER BY type;"
```

### Проверить what-if сценарии (Итерация 12)

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT id, name, status, base_version_id, result_version_id, created_at FROM whatif_scenario WHERE organization_id = '00000000-0000-0000-0000-000000000001' ORDER BY created_at DESC;"
```

### Посмотреть распределение cooling_mode в активной версии

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT st.cooling_mode, COUNT(*) FROM scheduled_task st JOIN schedule_version sv ON sv.id = st.schedule_version_id WHERE sv.is_active = true GROUP BY st.cooling_mode ORDER BY st.cooling_mode NULLS LAST;"
```

### Посмотреть статистику ЧЗ по партиям

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT cz_status, COUNT(*) FROM batch WHERE organization_id = '00000000-0000-0000-0000-000000000001' GROUP BY cz_status ORDER BY cz_status;"
```

### Отправить тестовый скан ЧЗ (PowerShell)

```powershell
# Сначала получите JWT
$body = '{"email": "admin@household.ru", "password": "admin123"}'
$token = (Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -Body $body -ContentType "application/json").access_token

# Отправить скан
$scanBody = @{
    cz_code = "0104600000000001215TEST0000000001"
    gtin = "04600000000001"
    line_code = "LINE_1"
    camera_id = "CAM-01"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/cz/scan" `
    -Method Post `
    -Body $scanBody `
    -ContentType "application/json" `
    -Headers @{
        Authorization = "Bearer $token"
        "X-CZ-Api-Key" = "dev-cz-api-key-change-in-production"
    } | ConvertTo-Json
```

### Создать what-if сценарий через API (PowerShell)

```powershell
$body = '{"email": "admin@household.ru", "password": "admin123"}'
$token = (Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -Body $body -ContentType "application/json").access_token

# Получить активную версию
$versions = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/schedule/versions" -Headers @{Authorization="Bearer $token"}
$activeVer = ($versions | Where-Object { $_.is_active })[0].id

# Создать сценарий
$scenarioBody = @{
    name = "Test +20% cream"
    base_version_id = $activeVer
    changes = @{
        shift_mode = "3x8"
        resource_capacity = @{
            REACTOR_OPERATOR = 5
        }
    }
} | ConvertTo-Json -Depth 5

$scenario = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/whatif/scenarios" `
    -Method Post `
    -Body $scenarioBody `
    -ContentType "application/json" `
    -Headers @{Authorization="Bearer $token"}

Write-Host "Создан сценарий: $($scenario.id)"

# Запустить расчёт
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/whatif/scenarios/$($scenario.id)/run" `
    -Method Post `
    -Body '{}' `
    -ContentType "application/json" `
    -Headers @{Authorization="Bearer $token"}

# Проверить статус (подождать 30 сек)
Start-Sleep -Seconds 30
$status = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/whatif/scenarios/$($scenario.id)" -Headers @{Authorization="Bearer $token"}
Write-Host "Статус: $($status.status)"

# Сравнить
$compare = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/whatif/scenarios/$($scenario.id)/compare" -Headers @{Authorization="Bearer $token"}
$compare | ConvertTo-Json -Depth 5
```
## ⚠️ Известные ограничения

1. **Слив на линию** добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает: NoOverlap не даёт им пересечься.

2. **Материальные ограничения** — предупреждения Advisor, не жёсткие constraints в CP-SAT.

3. **График поставок** — все поставки считаются доступными (без учёта `expected_at` vs дата старта партии).

4. **Крем-мыло 5л (Р2)** имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Advisor подсвечивает это как ROUTE_MISMATCH.

5. **Лабораторные блокировки:** после блокировки партии нужно **вручную запустить перепланирование** (`POST /api/v1/schedule/reschedule`) — автоматическое не реализовано.

6. **Персонал:** на Итерации 6 нет HR-подсистемы (нет ФИО, смен, отпусков). Только пулы с capacity.

7. **Solver:** при большом горизонте и множестве `AddCumulative` + модель деградации охлаждения (O(N²) bool-переменных) solver может не успеть найти OPTIMAL за отведённое время — выдаёт FEASIBLE. На тестовом кейсе ТЗ — OPTIMAL за 7–25 сек.

8. **Деградация охлаждения (Итерация 7)** активна, но в тестовом кейсе ТЗ `slow` не появляется — узкие места в других ресурсах (линии, аппаратчики, единственный tank). Чтобы увидеть `slow` в UI — уменьшите `cooling_degradation_factor` до 1.05 или разгрузите Line 1.

9. **ЧЗ (Итерация 8):** формат данных от камер — **гибкий JSON** с опциональными `batch_id`/`task_id`/`line_code`. Реальный формат камер ТС будет уточнён; текущая модель — задел на будущее.

10. **ЧЗ:** `enable_cz_auto_close = false` — закрытие задачи слива при завершении маркировки отключено. Включается через `app_settings`.

11. **ЧЗ:** ручное сопоставление сироты требует ввода UUID партии — UI подсказки/автоподбора по продукту не реализовано.

12. **Режимы смен (Итерация 11):** при смене `shift_mode` через `/api/v1/settings/shift-mode` **все задачи теряют привязку к сменам** (`shift_id = NULL`). Требуется пересчитать план.

13. **Разбиение LINE_FILL (Итерация 10):** длинные задачи (например, слив 7000 кг крем-мыла 5л = 7000 минут) разбиваются на **много подзадач** (для `3x8` — до 20 частей). Это увеличивает общее число задач в плане.

14. **Pan + drag на Ганте:** setup и downtime не таскаются (только pan). Это by design — они генерируются автоматически и не должны менять положение вручную.

15. **What-if (Итерация 12):** при удалении сценария со статусом `DONE` **план остаётся** в истории (это by design). `result_version_id` — отдельная `schedule_version`.

16. **Multi-objective:** если все веса = 0 (кроме `makespan`), работает как single-objective. Это **дефолтное** поведение для обратной совместимости.

17. **What-if `RUNNING`:** нельзя удалить сценарий во время расчёта. Дождитесь `DONE`/`FAILED`.

18. **What-if `changes`:** формат JSON не строго типизирован на уровне Pydantic — валидация в `WhatIfRunner._apply_changes`. Ошибки в JSON возвращают `FAILED` с текстом в комментарии.

## 🐛 Troubleshooting

### 1. FastAPI 0.139+: `_IncludedRouter` в `app.routes`

**Симптом:** скрипт проверки `getattr(r, 'path', None)` возвращает `None` для всех `include_router(...)`.

**Решение:** проверять через `app.openapi()['paths']`:

```python
from app.main import app
paths = sorted(app.openapi()['paths'].keys())
print([p for p in paths if '/shift' in p])
```

### 2. Кэш Python (`__pycache__`) на Windows

**Симптом:** после правки `main.py` изменений не видно.

**Решение:** удалить `__pycache__` в проекте:

```
cd backend
Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

### 3. Кэш браузера — Swagger/UI показывает старое

**Решение:**
1. Открыть в **режиме инкогнито** (Ctrl+Shift+N).
2. Или **Ctrl+Shift+Delete** → очистить кэш.
3. В крайнем случае — **перезагрузить компьютер**.

### 4. Таймзона naive datetime в asyncpg

**Симптом:** `GET /api/v1/shift/by-date/2026-09-01` возвращает 404.

**Решение:** сравнение по **МСК-дате** (Итерация 11):

```sql
WHERE (starts_at AT TIME ZONE 'Europe/Moscow')::date = :shift_date
```

### 5. `UndefinedColumnError: column "updated_at" does not exist`

**Симптом:** `GET /api/v1/personnel/pools` возвращает 500.

**Причина:** не применена миграция `add_09c.sql`.

**Решение:**

```
docker cp backend\migrations\add_09c.sql aps_postgres:/tmp/add_09c.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09c.sql
```

### 6. `UndefinedColumnError: column "operator_pool" does not exist`

**Симптом:** `GET /api/v1/personnel/pools` возвращает 500.

**Причина:** не применена миграция `add_09d.sql`.

**Решение:**

```
docker cp backend\migrations\add_09d.sql aps_postgres:/tmp/add_09d.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09d.sql
```

### 7. `UndefinedColumnError: column "cooling_mode" does not exist`

**Симптом:** `GET /api/v1/gantt/` возвращает 500.

**Причина:** не применена миграция `add_10b.sql` (Итерация 7).

**Решение:**

```
docker cp backend\migrations\add_10b.sql aps_postgres:/tmp/add_10b.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_10b.sql
```

### 8. Все охлаждения помечены `slow`, хотя идут последовательно

**Симптом:** на диаграмме Ганта много оранжевых пунктирных задач с иконкой ⏳, но по времени они не пересекаются.

**Причина:** не применён hotfix Итерации 7 (модель `b_slow ⟺ пересечение` не активна).

**Решение:** убедиться, что в `core.py` вызывается `_apply_cooling_degradation_model`, а в `plugins.py` убран `AddNoOverlap(fast_intervals)` из `CoolingDegradationConstraint`.

### 9. `UndefinedColumnError: column "cz_status" does not exist`

**Симптом:** `GET /api/v1/cz/stats` возвращает 500.

**Причина:** не применена миграция `add_11.sql` (Итерация 8).

**Решение:**

```
docker cp backend\migrations\add_11.sql aps_postgres:/tmp/add_11.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_11.sql
```

### 10. `401 Unauthorized` при отправке скана ЧЗ

**Симптом:** `POST /api/v1/cz/scan` возвращает 401.

**Причина:** неверный или отсутствующий заголовок `X-CZ-Api-Key`.

**Решение:**

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_value FROM app_settings WHERE setting_key = 'cz_api_key';"
```

Значение по умолчанию: `dev-cz-api-key-change-in-production`.

### 11. `400 Интеграция с ЧЗ отключена`

**Симптом:** эндпоинт `/api/v1/cz/*` возвращает 400.

**Причина:** `enable_cz_integration = false` в `app_settings`.

**Решение:**

```
docker exec -i aps_postgres psql -U aps -d household -c "UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'enable_cz_integration';"
```

### 12. Скан ЧЗ не сопоставляется с партией («сирота»)

**Симптом:** `POST /api/v1/cz/scan` возвращает `resolved: false`.

**Возможные причины:**
1. Камера не передала `batch_id`/`task_id`, а `line_code` не совпадает с `equipment.code`.
2. Нет активной `LINE_FILL` задачи в окне ±2 часа от `scanned_at`.

**Решение:** проверить журнал сканов на странице **«Честный Знак»** → фильтр «Только сироты». Сопоставить вручную.

### 13. `app_settings` пустой (нет настроек)

**Симптом:** `GET /api/v1/settings/` возвращает пустой объект.

**Причина:** не применена миграция `add_13.sql` (Итерация 11).

**Решение:**

```
docker cp backend\migrations\add_13.sql aps_postgres:/tmp/add_13.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_13.sql
```

### 14. `UndefinedColumnError: column "operation_name" does not exist`

**Симптом:** `GET /api/v1/gantt/` возвращает 500.

**Причина:** не применена миграция `add_12.sql` (Итерация 10).

**Решение:**

```
docker cp backend\migrations\add_12.sql aps_postgres:/tmp/add_12.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_12.sql
```

### 15. `allow_weekend_work` отсутствует в настройках

**Симптом:** в UI настройки «Работа в выходные» нет.

**Причина:** не применена миграция `add_14.sql` (Итерация 11).

**Решение:**

```
docker cp backend\migrations\add_14.sql aps_postgres:/tmp/add_14.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_14.sql
```

### 16. `usePlan must be used within PlanProvider` (frontend)

**Симптом:** ошибка в консоли на `/schedule` или `/whatif`.

**Причина:** HMR сохранил старый модуль `PlainContext.tsx`.

**Решение:**
1. Проверить `App.tsx` — порядок: `AuthProvider > PlanProvider > BrowserRouter > AppRoutes`.
2. Перезапустить Vite с очисткой кэша:
   ```powershell
   cd frontend
   # Ctrl+C
   Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue
   npm run dev
   ```
3. Жёсткая перезагрузка (Ctrl+Shift+R).

### 17. Advisor «дёргается» (бесконечный ре-рендер)

**Симптом:** панель Advisor мигает.

**Причина:** `loadVersions` из `PlainContext` не обёрнут в `useCallback`.

**Решение:** в `PlainContext.tsx` обернуть `loadVersions`, `setPlan`, `createPlan`, `deletePlan` в `useCallback`. Вызывать `loadVersions` только после аутентификации.

### 18. What-if: `InvalidRequestError: A transaction is already begun on this Session`

**Симптом:** при запуске what-if — ошибка фазы 1.

**Причина:** двойной `await session.begin()` в `whatif.py`.

**Решение:** убрать явные `session.begin()` — SQLAlchemy async начинает транзакцию автоматически при первом `execute()`. См. патч `whatif.py` (Итерация 12, fix #2).

### 19. What-if: `InvalidRequestError: Can't operate on closed transaction`

**Симптом:** при сохранении результата what-if — ошибка фазы 2.

**Причина:** `ScheduleSaver` делает `commit()` или работает с закрытой транзакцией.

**Решение:** `ScheduleSaver(session=self.session)` — не коммитит при `_owns_session=False`. Коммит делает `WhatIfRunner` в конце.

### 20. What-if: изменения не применяются к solver'у

**Симптом:** `makespan` не меняется после what-if. В логах `shift_mode=2x12` вместо `3x8`.

**Причина:** `DataLoader` использует **свой engine** — отдельное соединение, не видит незакоммиченные данные.

**Решение:** `ProductionScheduler(..., session=self.session)` — передавать сессию из WhatIfRunner. См. патч `data_loader.py` + `core.py` + `whatif.py` (Итерация 12).

### 21. What-if: смены дублируются (4 смены на 01.09.2026 вместо 2)

**Симптом:** в БД 184 смены вместо 182. Ночные смены `00:00–08:00` не удаляются.

**Причина:** `shift_regenerator.py` использует `AT TIME ZONE 'UTC'` в DELETE. Ночные смены (`00:00 МСК` = `21:00 UTC` предыдущего дня) не попадают в диапазон.

**Решение:** заменить на `AT TIME ZONE 'Europe/Moscow'` в DELETE. См. патч `shift_regenerator.py` (Итерация 12).

### 22. What-if: `start_end` смены не сохраняются при вызове API `/shift-mode`

**Симптом:** API возвращает `200 OK`, но смены в БД не изменились.

**Причина:** `regenerate_shifts` делает `flush()` вместо `commit()` (для what-if). В `settings.py` не делается явный `commit()`.

**Решение:** добавить `await db.commit()` после `regenerate_shifts` в `settings.py`. См. патч `settings.py` (Итерация 12).

### 23. What-if: сценарий `DONE`, но кнопка удаления 🗑 отсутствует

**Симптом:** нельзя удалить успешно посчитанный сценарий.

**Причина:** backend запрещает `DELETE` для `DONE`.

**Решение:** разрешить `DELETE` для `DRAFT`, `FAILED`, `DONE` (кроме `RUNNING`). Frontend — показывать 🗑 для всех статусов кроме `RUNNING`. См. патч `whatif.py` + `WhatIfPage.tsx` (Итерация 12, fix #3).

## 🗺️ Roadmap

| # | Итерация | Длит. | Приоритет | Статус |
|---|----------|-------|-----------|--------|
| 0 | Подготовка | 4 дня | 🔥 | ✅ |
| 1 | Цепочки рабочих центров | 2 нед | 🔥🔥🔥 | ✅ |
| 2 | Материальные ограничения и Advisor | 2 нед | 🔥🔥🔥 | ✅ |
| 3 | Сменное планирование и РМ мастера | 2 нед | 🔥🔥🔥 | ✅ |
| 4 | Перепланирование | 2 нед | 🔥🔥🔥 | ✅ |
| 5 | Лаборатория и блокировки | 1.5 нед | 🔥🔥 | ✅ |
| 5h | Hotfix: версии + tz + Gantt | 2 дня | 🔥🔥🔥 | ✅ |
| 6 | Люди как ресурс | 2 нед | 🔥🔥 | ✅ |
| 7 | Охлаждение с деградацией | 1.5 нед | 🔥 | ✅ |
| 7h | Hotfix: модель деградации охлаждения | 2 дня | 🔥🔥🔥 | ✅ |
| 8 | ЧЗ и интеграции | 2 нед | 🔥 | ✅ |
| 9 | Рефакторинг, A3 (реальный пересчет), C2 (drag-and-drop) | 2 нед | 🟡 | ✅ |
| 10 | Календарная постобработка, разбиение длинных задач | 2 нед | 🟡 | ✅ |
| 11 | Режимы смен, `app_settings`, pan/zoom в Ганте | 2 нед | 🟡 | ✅ |
| 12 | Multi-objective и what-if сценарии | 2 нед | 🟡 | ✅ |
| 13 | Встроенная справка пользователя | 1 нед | 🟡 | ⏳ |

## 📄 Лицензия

Внутренний проект.

---

**Итерации 0, 1, 2, 3, 4, 5, 5h, 6, 7, 7h, 8, 9, 10, 11, 12 завершены.**

**Следующая — Итерация 13: Встроенная справка пользователя (⏳).**