# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **4.3.0** (Итерации 0–14.2 завершены)

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
Терминал 1 (Backend):
```
cd backend; ..venv\Scripts\Activate.ps1; python run_server.py
```

Терминал 2 (Frontend):
```
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
- **Настроек, привязанных к плану** (`plan_settings` — снапшот настроек для каждого плана)
- **Multi-objective оптимизации** (5 компонентов целевой функции с весами)
- **What-if сценариев** (сценарное планирование без изменения БД)
- **Архивации версий планов** (Итерация 13.21) — скрытие старых версий и иерархия
- **Редактирования плана прямо на Ганте** (Итерация 14.2) — переключатель `🔒/✏️` в тулбаре

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
  - `optimization` — веса multi-objective
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
- ✅ **7 эндпоинтов API `/api/v1/whatif`** (создать, список, один, обновить, удалить, запустить, сравнить)
- ✅ **Async запуск:**
  - `POST /run` возвращает `202 Accepted` сразу
  - Расчёт в `BackgroundTasks` (отдельная сессия БД)
  - Frontend polling через `GET /scenarios/{id}` каждые 3 сек
  - Статусы: `DRAFT` → `RUNNING` → `DONE`/`FAILED`
- ✅ **7 типов изменений:** `add_order`, `cancel_order`, `change_qty`, `change_due_date`, `shift_mode`, `resource_capacity`, `calendar_events` (add/remove)
- ✅ **UI `/whatif`** (`WhatIfPage.tsx`):
  - AgGrid со списком сценариев
  - Диалог создания/редактирования с JSON-редактором
  - 5 кнопок-шаблонов (Режим смен, +Заказ, +Capacity, Авария Р4, Полный пример)
  - Polling статуса `RUNNING` каждые 3 секунды
  - Диалог результата с таблицей метрик и Δ (зелёный = улучшение, красный = ухудшение)
  - Кнопка «Открыть план» → переход на `/gantt?version_id=...`
  - Кнопка удаления (🗑) для всех статусов кроме `RUNNING`
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

### Итерация 13.3 — Аудит

- ✅ Объединённый журнал событий для аудита действий пользователей.
- ✅ Единая точка входа для истории изменений планов, справочников, настроек.
- ✅ Объединение 4 источников:
  - `material_stock_log` — изменения остатков материалов
  - `reschedule_log` — перепланирования
  - `lab_analysis_log` — лабораторные блокировки
  - `cz_scan_log` — сканы Честного Знака
- ✅ API `/api/v1/audit`:
  - `GET /log` — объединённый журнал с фильтрами (источники, severity, даты, поиск)
  - `GET /stats` — счётчики по источникам за период
  - `GET /sources` — список доступных источников
- ✅ UI `AuditPage.tsx` — страница аудита с группировкой по дням.
- ✅ Фильтры синхронизируются с URL — можно делиться ссылкой.

**Примечание Итерации 13.16:** пункт «Аудит» временно скрыт из меню
(страница в разработке), роут `/audit` оставлен для отладки.

### Итерация 13.14 — Настройки, привязанные к плану

**Проблема:**
Глобальные настройки (`app_settings`) применяются ко **всем** планам одновременно. Если пользователь изменил `horizon_hours` с 720 на 1000 и пересчитал план — старые планы становятся «невалидными».

**Решение:**
Каждый план (`schedule_version`) хранит **свой снапшот** настроек в таблице `plan_settings`.

**Что сделано:**

**1. База данных (`add_21.sql`):**
- ✅ Таблица `plan_settings`.
- ✅ **Триггер `copy_app_settings_to_plan`:** копирует все `app_settings` в `plan_settings` нового плана при `INSERT INTO schedule_version`.
- ✅ Индексы: `idx_plan_settings_version`, `idx_plan_settings_org_category`.

**2. Backend:**
- ✅ `DataLoader(version_id=...)` — читает из `plan_settings`.
- ✅ `ProductionScheduler(version_id=...)` — прокидывает в `DataLoader`.
- ✅ `settings_reader.py` — 3 функции получили `version_id`.
- ✅ `rescheduler.py`, `whatif.py`.
- ✅ **API `/api/v1/plan-settings`** — 3 эндпоинта.
- ✅ **6 API-модулей** обновлены — все получили `version_id`.

**3. Frontend:**
- ✅ `planSettingsApi` в `api.ts`.
- ✅ `PlanSettingsWizard.tsx` — мастер настроек плана (9 шагов).
- ✅ `SchedulePage.tsx` — кнопка «Настройки плана» (⚙).

**4. Тесты:** +171, всего 492.

**5. Ключевые гарантии:**
- ✅ **Изоляция:** два плана имеют независимые настройки.
- ✅ **Воспроизводимость.**
- ✅ **Обратная совместимость.**

### Итерация 13.15 — Снапшоты при создании плана

**Проблема:**
При создании «пустого» плана через `POST /api/v1/schedule/versions` снапшоты справочников **не заполнялись**. UI показывал **пустые гриды**.

**Решение:**
- ✅ Новый модуль `backend/app/scheduler/snapshot.py`:
  - `snapshot_all_catalogs(session, org_id, version_id)`.
  - `snapshot_exists(session, version_id)`.
  - `_has_column(session, table, column)` — graceful-проверка схемы.
- ✅ API `schedule.py`: `POST /versions` вызывает `snapshot_all_catalogs`.
- ✅ `saver.py`: `_do_save` делегирует в `snapshot_all_catalogs`.
- ✅ Frontend: индикация ⚠ для планов без снапшотов.
- ✅ Тесты: +43, всего 535.

### Итерация 13.16 — Унификация диалогов и UI-полировка

- ✅ **Все 20 диалогов в 12 страницах** переведены на единый компонент `frontend/src/components/common/DraggableDialog.tsx`.
- ✅ Добавлен проп `centerOnOpen?: boolean`.
- ✅ Убран ~150 строк дублированного drag/resize-кода из `GanttPage.tsx`.
- ✅ **`CzPage.tsx`** — исправлен layout.
- ✅ **`MainLayout.tsx`** — пункт «Аудит» временно скрыт из меню.

### Итерация 13.17 — Каскадный сдвиг задач

- ✅ Новый модуль `backend/app/scheduler/reschedule_cascade.py`:
  - `apply_cascade()` — каскадный сдвиг BFS.
  - `validate_move()` — валидация.
  - `CascadeBlockedError`.
- ✅ Новые эндпоинты `PUT /schedule/task/{id}/move-cascade`, `PUT /schedule/task/{id}/resize`.
- ✅ Полный рефакторинг `GanttPage.tsx`: вынесены хуки и компоненты.
- ✅ Новые компоненты: `GanttToolbar`, `GanttFiltersBar`, `GanttFiltersPopover`, `GanttTaskDialog`, `TaskContextMenu`, `MoveValidationDialog`, `RecalcSettingsDialog`.
- ✅ Новые хуки: `useGanttActions`, `useGanttTimeline`, `useGanttViewport`, `useGanttDependencies`, `useGanttFilters`, `useExpandedGroups`, `useCascadeMove`, `useTaskResize`, `useDragTooltip`, `useRecalculate`.

### Итерация 13.18 — Улучшения Ганта

- ✅ Tooltip при resize и move: `DragTooltip` показывает тип операции, Δ, исходное время.
- ✅ `is_pinned` больше НЕ блокирует resize (только move).
- ✅ Визуальная индикация pinned: 📌, светлый синий фон, плотная рамка.
- ✅ Новый фильтр «Только закреплённые».

### Итерация 13.19 — Флаг planDirty

- ✅ Флаг `planDirty` в `PlanContext` (сохраняется в localStorage per-plan).
- ✅ `markPlanDirty()` вызывается при любых изменениях, влияющих на расчёт.
- ✅ Кнопка «Пересчитать» на Ганте активна только при `planDirty === true`.
- ✅ Сбрасывается при успешном пересчёте.

### Итерация 13.20 — Модальное окно прогресса пересчёта

**Проблема:**
Solver работает 30–120 секунд. Пользователь мог закрыть страницу, не понимая, что происходит.

**Решение:**
- ✅ Новый компонент `RecalcProgressDialog.tsx`:
  - Спиннер + иконка песочных часов.
  - Таймер «MM:SS» (тик каждую секунду).
  - Прогресс-бар до `timeout_seconds`.
  - Предупреждение «Не закрывайте страницу».
  - Блокировка Esc/backdrop.
- ✅ `GanttPage`: `RecalcOperation` type ('recalc' | 'force-recalc').
- ✅ Диалог показывается, пока solver работает.

### Итерация 13.21 — Архивирование версий планов

**Проблема:**
В «Истории планов» накапливалось много неактивных версий (55 за ~10 дней). Пользователь не понимал, какая версия актуальна.

**Решение:**

**1. База данных (миграция `add_23.sql`):**
- ✅ Колонка `schedule_version.is_archived BOOLEAN NOT NULL DEFAULT FALSE`.
- ✅ Partial-индекс `idx_schedule_version_archived`
  по `(organization_id, created_at DESC) WHERE is_archived = FALSE`.
- ✅ Настройка `app_settings.auto_archive_on_recalc` (bool, default=true).
- ✅ Одноразовая миграция: 54 старые неактивные версии → в архив.

**2. Backend:**
- ✅ `ScheduleSaver._archive_version(session, version_id)` — архивирует версию,
  если она не используется в `whatif_scenario` (статусы `DRAFT`, `RUNNING`).
- ✅ `ScheduleSaver._check_version_usage(session, version_id)` — проверка what-if.
- ✅ `save_schedule()` принимает `replace_version_id` в `schedule_data`.
- ✅ `RescheduleRequest.replace_version_id` (опциональное поле).
- ✅ `RescheduleResponse` + поля `replace_archived`, `replace_blocked`,
  `replace_blocked_reason`, `used_by_whatif`.
- ✅ `GET /versions?include_archived=true` — фильтр.
- ✅ Новый эндпоинт `PUT /versions/{id}/unarchive`.

**3. Frontend:**
- ✅ `PlanVersion.is_archived`, `PlanVersion.parent_version_id` в типах.
- ✅ `scheduleApi.unarchiveVersion(versionId)`.
- ✅ `PlainContext`:
  - `includeArchived`, `setIncludeArchived`, `unarchiveVersion`.
  - `loadVersions()` учитывает `includeArchived`.
- ✅ `useRecalculate` читает `auto_archive_on_recalc`.
- ✅ `SchedulePage`:
  - **Tree Data** для «Истории планов» (по `parent_version_id`).
  - Чекбокс «Показать архивные».
  - Кнопка «↩ Разархивировать» для архивных версий.
  - Иконка 📦 для архивных, чип «активный» для активного.
- ✅ `GanttPage`:
  - Снекбар после успешного пересчёта:
    - info — старая версия архивирована;
    - warning — не архивирована (используется в what-if).
  - `onRecalcSuccess` принимает `RescheduleResponse`.
- ✅ `PlanSettingsWizard` — чекбокс `auto_archive_on_recalc` на шаге «Основные».

**4. Тесты:** +28, всего 563.

**5. Ключевые гарантии:**
- ✅ **Архивация безопасна** — данные не удаляются, только скрываются.
- ✅ **What-if защищён** — версия не архивируется, если используется в сценариях.
- ✅ **Reschedule_log не блокирует** — ссылки на архивные версии валидны.
- ✅ **Разархивация возможна** через UI-кнопку или API.
- ✅ **Обратная совместимость.**

### Итерация 14.1 — Режимы отображения Ганта

**Проблема:**
Диаграмма Ганта отображала партии «плоско» — операции одной партии разбросаны по разным строкам (по оборудованию). Пользователь не видел партию как целое.

**Решение:**

- ✅ **Переключатель режима группировки** в тулбаре Ганта:
  - `'equipment'` — по оборудованию (по умолчанию).
  - `'batch'` — по партиям.
- ✅ **Фантомные скобки партий** — SVG-прямоугольники, охватывающие все операции одной партии. Рисуются поверх диаграммы.
- ✅ **Подсветка партии по клику** — при клике на скобку остальные задачи затемняются.
- ✅ **Детерминированные цвета партий** — хеш от `batch_id` → индекс в палитре.
- ✅ **Цвета по оборудованию** в режиме `'batch'` — каждая операция окрашена по своему оборудованию.
- ✅ **Чип с количеством партий** в тулбаре.
- ✅ Файлы:
  - `frontend/src/utils/ganttBatchColors.ts` — хеш → цвет, контрастный текст.
  - `frontend/src/utils/ganttBrackets.ts` — `buildBatchBrackets`, поиск скобки.
  - `frontend/src/components/gantt/constants.ts` — палитра, размеры, константы.
  - `useGanttTimeline.ts` — `drawBatchBrackets` в SVG.

### Итерация 14.2 — Редактирование плана прямо на Ганте

**Проблема:**
Если план был **открыт** (через кнопку 👁️ на странице «Планирование»), диаграмма Ганта переходила в режим **readonly** (`🔒 Просмотр`). Задачи **не перетаскивались**, длительность **не менялась**. Чтобы что-то поправить — приходилось закрывать план, терять контекст и пересчитывать заново.

Дополнительная проблема: в шапке `MainLayout` всегда горел `🔒`, даже когда пользователь **находился в режиме редактирования** — это путало.

**Решение:**

**1. Глобальный режим редактирования (Итерация 14.2):**
- ✅ Новый стейт `localEditMode` в `PlanContext`:
  - `false` — readonly (план открыт, но не редактируется).
  - `true` — редактирование разрешено.
- ✅ Синхронизация с `currentVersionId`:
  - план открыт → `localEditMode = false` (безопасный режим);
  - план закрыт → `localEditMode = true`.
- ✅ `isReadOnly = !localEditMode` в `GanttPage` — единый источник правды.

**2. Переключатель режима в тулбаре Ганта:**
- ✅ Компактный `ToggleButtonGroup` `🔒 / ✏️` (только иконки, текст в tooltip).
- ✅ Клик по `✏️` — переключение в редактирование.
- ✅ Клик по `🔒` — возврат в readonly.
- ✅ Активная кнопка — синяя (`#3498db`).

**3. Синхронизация иконки в шапке приложения:**
- ✅ `MainLayout` берёт `localEditMode` из `usePlan()`.
- ✅ Условный рендер чипа:
  - `🔒 План от ...` (синий) — readonly.
  - `✏️ План от ...` (зелёный) — редактирование.
  - `✏️ Режим редактирования` (прозрачный) — план не открыт.

**4. Кнопка «Пересчитать» — доступна всегда:**
- ✅ В `<GanttToolbar>` рендерится, если передан `onRecalculate`.
- ✅ `GanttPage` передаёт `onRecalculate` **всегда**, если есть `currentVersionId` (не только в readonly).
- ✅ Активна только при `planDirty === true`.
- ✅ Tooltip объясняет, что нужно изменить справочники/задачи.

**5. Удалён дублирующий Chip с названием плана:**
- ✅ Название плана видно в шапке `MainLayout` — Chip в тулбаре Ганта был избыточен.
- ✅ Убраны неиспользуемые пропсы `isReadOnly`, `currentPlanName` из `GanttToolbarProps`.

**6. Фикс рендера скобок партий:**
- ✅ В `drawBatchBrackets` добавлена защита от отрицательной ширины:
  - `const w = Math.max(0, rawW)`.
  - `const h = Math.max(0, rawH)`.
  - Пропуск невалидных `rect`, если `w <= 0 || h <= 0`.
- ✅ Устранена ошибка `<rect> attribute width: A negative value is not valid` при zoom/pan.

**7. `useGanttTimeline` учитывает `localEditMode`:**
- ✅ `editable.updateTime: localEditMode` — включает/выключает drag.
- ✅ `attachNativeDragListeners` использует `if (!localEditMode) return`.
- ✅ `localEditMode` добавлен в зависимости `useCallback`.

**8. `GanttPage` — ре-рендер Timeline при смене режима:**
- ✅ `localEditMode` добавлен в `key` внутри `useEffect`, который вызывает `renderTimeline`.
- ✅ `localEditMode` добавлен в зависимости `useEffect`.
- ✅ Отдельный `useEffect` для принудительного ре-рендера при смене `localEditMode` / `groupByMode` / `showBatchBrackets` / `highlightedBatchId`.

**Затронутые файлы:**
- `frontend/src/context/PlainContext.tsx` — глобальный `localEditMode`.
- `frontend/src/components/layout/MainLayout.tsx` — условная иконка.
- `frontend/src/components/gantt/GanttToolbar.tsx` — компактный переключатель, удалены устаревшие пропсы.
- `frontend/src/pages/GanttPage.tsx` — берёт `localEditMode` из контекста, `onRecalculate` всегда.
- `frontend/src/hooks/useGanttTimeline.ts` — `editable.updateTime: localEditMode`, защита от отрицательной ширины.

**Тесты:** 563 passed (0 failed). Итерация не добавила новых тестов — фича покрыта UI-тестами и ручной проверкой.

**Ключевые гарантии:**
- ✅ **Редактирование без закрытия плана** — переключатель в один клик.
- ✅ **Единый источник правды** — `localEditMode` в `PlanContext`.
- ✅ **Синхронизация UI** — шапка и тулбар показывают одно состояние.
- ✅ **Безопасность** — при открытии плана по умолчанию readonly.
- ✅ **Кнопка «Пересчитать»** доступна в обоих режимах.
- ✅ **Фикс рендера** — скобки партий больше не ломают SVG.

---

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
├── quickstart.ps1 # ⚡ Скрипт быстрого старта
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── backend/
│ ├── app/
│ │ ├── api/v1/ # REST API endpoints
│ │ │ ├── auth.py
│ │ │ ├── equipment.py
│ │ │ ├── products.py
│ │ │ ├── materials.py
│ │ │ ├── recipes.py
│ │ │ ├── operations.py
│ │ │ ├── orders.py
│ │ │ ├── schedule.py
│ │ │ ├── gantt.py
│ │ │ ├── calendar.py
│ │ │ ├── advisor.py
│ │ │ ├── shift.py
│ │ │ ├── reschedule.py
│ │ │ ├── lab.py
│ │ │ ├── personnel.py
│ │ │ ├── cz.py
│ │ │ ├── settings.py
│ │ │ ├── plan_settings.py
│ │ │ ├── whatif.py
│ │ │ └── audit.py
│ │ ├── auth/
│ │ ├── core/
│ │ ├── scheduler/ # Ядро планировщика
│ │ │ ├── core.py
│ │ │ ├── data_loader.py
│ │ │ ├── routing.py
│ │ │ ├── materials.py
│ │ │ ├── advisor.py
│ │ │ ├── feasibility.py
│ │ │ ├── shifts.py
│ │ │ ├── rescheduler.py
│ │ │ ├── reschedule_cascade.py
│ │ │ ├── cz.py
│ │ │ ├── saver.py
│ │ │ ├── snapshot.py
│ │ │ ├── feature_flags.py
│ │ │ ├── settings.py
│ │ │ ├── settings_reader.py
│ │ │ ├── shift_regenerator.py
│ │ │ ├── calendar_postprocess.py
│ │ │ ├── optimization.py
│ │ │ ├── whatif.py
│ │ │ ├── logging_config.py
│ │ │ ├── duration/
│ │ │ └── constraints/plugins.py
│ │ └── main.py
│ ├── migrations/
│ │ ├── add_history_0_2.sql
│ │ ├── add_06.sql … add_16.sql
│ │ ├── add_21.sql       # plan_settings
│ │ ├── add_23.sql       # is_archived (13.21)
│ │ ├── fix_versions_hotfix.sql
│ │ └── fix_shift_names.sql
│ ├── .env
│ ├── init_schema.sql
│ ├── seed_demo.py
│ ├── seed_demo_data.sql
│ ├── scripts/create_admin_user.py
│ ├── requirements.txt
│ ├── requirements-dev.txt
│ ├── pyproject.toml
│ └── run_server.py
├── frontend/
│ ├── src/
│ │ ├── components/
│ │ │ ├── common/DraggableDialog.tsx
│ │ │ ├── common/AppAgGrid.tsx
│ │ │ ├── layout/MainLayout.tsx
│ │ │ └── gantt/
│ │ │ ├── constants.ts
│ │ │ ├── types.ts
│ │ │ ├── DragTooltip.tsx
│ │ │ ├── GanttFiltersBar.tsx
│ │ │ ├── GanttFiltersPopover.tsx
│ │ │ ├── GanttTaskDialog.tsx
│ │ │ ├── GanttToolbar.tsx
│ │ │ ├── MoveValidationDialog.tsx
│ │ │ ├── RecalcProgressDialog.tsx
│ │ │ ├── RecalcSettingsDialog.tsx
│ │ │ └── TaskContextMenu.tsx
│ │ ├── context/
│ │ │ ├── AuthContext.tsx
│ │ │ └── PlainContext.tsx
│ │ ├── hooks/
│ │ │ ├── useCascadeMove.ts
│ │ │ ├── useDoubleClick.ts
│ │ │ ├── useDragTooltip.ts
│ │ │ ├── useExpandedGroups.ts
│ │ │ ├── useExpandedRoots.ts
│ │ │ ├── useGanttActions.ts
│ │ │ ├── useGanttData.ts
│ │ │ ├── useGanttDependencies.ts
│ │ │ ├── useGanttFilters.ts
│ │ │ ├── useGanttTimeline.ts
│ │ │ ├── useGanttViewport.ts
│ │ │ ├── useRecalculate.ts
│ │ │ └── useTaskResize.ts
│ │ ├── pages/
│ │ │ ├── LoginPage.tsx
│ │ │ ├── EquipmentPage.tsx
│ │ │ ├── ProductsPage.tsx
│ │ │ ├── MaterialsPage.tsx
│ │ │ ├── RecipesPage.tsx
│ │ │ ├── OperationsPage.tsx
│ │ │ ├── OrdersPage.tsx
│ │ │ ├── SchedulePage.tsx
│ │ │ ├── GanttPage.tsx
│ │ │ ├── ShiftPage.tsx
│ │ │ ├── PersonnelPage.tsx
│ │ │ ├── CzPage.tsx
│ │ │ ├── WhatIfPage.tsx
│ │ │ ├── AuditPage.tsx
│ │ │ ├── SettingsPage.tsx
│ │ │ └── PlanSettingsWizard.tsx
│ │ ├── services/api.ts
│ │ ├── theme/
│ │ │ ├── agGridLocale.ts
│ │ │ └── agGridTheme.ts
│ │ ├── types/index.ts
│ │ ├── utils/
│ │ │ ├── ganttBatchColors.ts
│ │ │ ├── ganttBrackets.ts
│ │ │ ├── ganttDowntimes.ts
│ │ │ ├── ganttGroups.ts
│ │ │ ├── ganttHelpers.ts
│ │ │ ├── ganttRenderItems.ts
│ │ │ ├── ganttSetups.ts
│ │ │ ├── ganttTimelineOptions.ts
│ │ │ └── ganttValidators.ts
│ │ ├── App.tsx
│ │ ├── main.tsx
│ │ └── index.css
│ ├── package.json
│ └── vite.config.ts
├── docs/
│ ├── ARCHITECTURE.md
│ ├── API.md
│ ├── CONFIGURATION.md
│ ├── OPERATIONS.md
│ ├── TROUBLESHOOTING.md
│ ├── DEVELOPMENT.md
│ ├── ROADMAP.md
│ ├── adr/
│ │ ├── README.md
│ │ ├── 0001-use-ortools-cp-sat.md
│ │ ├── 0002-snapshot-tables-for-versioning.md
│ │ ├── 0003-plan-settings-per-plan.md
│ │ └── 0004-whatif-two-transactions.md
│ └── requirements/ТЗ.txt
└── tools/prompts/
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
docker cp backend\init_schema.sql aps_postgres:/tmp/init_schema.sql
docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

#### Шаг 2b (только при апгрейде существующей БД): применить миграции
```
docker cp backend\migrations\add_21.sql aps_postgres:/tmp/add_21.sql
docker cp backend\migrations\add_23.sql aps_postgres:/tmp/add_23.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_23.sql
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
..venv\Scripts\Activate.ps1
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

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Архитектура системы |
| [docs/API.md](docs/API.md) | REST API endpoints |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Все настройки |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Операции с БД |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Решение проблем |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Руководство разработчика |
| [docs/ROADMAP.md](docs/ROADMAP.md) | План развития |
| [docs/adr/](docs/adr/) | Архитектурные решения |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Как внести вклад |

**Swagger UI** после запуска backend: **http://localhost:8000/docs**

## 🧪 Тестирование

```
cd backend
..venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Текущее состояние:** **563 passed**, 13 warnings.

Основные тестовые файлы:

| Файл | Тестов | Что проверяет |
|------|--------|---------------|
| `test_tz_case.py` | 41 | Эталонный кейс ТЗ |
| `test_materials.py` | 11 | Расчёт потребности в сырье |
| `test_advisor.py` | 17 | Подсказки Advisor |
| `test_routing.py` | 15 | Цепочки операций |
| `test_shifts.py` | 16 | Смены и API |
| `test_rescheduler.py` | 18 | Перепланирование |
| `test_lab.py` | 24 | Лабораторные блокировки |
| `test_personnel.py` | 15 | Люди как ресурс |
| `test_cooling_degradation.py` | 19 | Охлаждение с деградацией |
| `test_cz.py` | 52 | Честный Знак |
| `test_whatif.py` | 45 | What-if сценарии |
| `test_plan_settings_*.py` | 78 | plan_settings |
| `test_audit.py` | 33 | Аудит |
| `test_snapshot.py` | 18 | Модуль snapshot |
| **`test_schedule_versions_archive.py`** | **28** | **Архивация версий (13.21)** |

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
docker cp backend\init_schema.sql aps_postgres:/tmp/init_schema.sql
docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

### Применить SQL-миграцию (правильный способ)
```
docker cp backend\migrations\add_23.sql aps_postgres:/tmp/add_23.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_23.sql
```

### Проверить архивные версии (Итерация 13.21)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT COUNT(*) FILTER (WHERE is_archived = TRUE) AS archived, COUNT(*) FILTER (WHERE is_active = TRUE) AS active FROM schedule_version WHERE organization_id = '00000000-0000-0000-0000-000000000001';"
```

### Проверить настройку auto_archive_on_recalc (Итерация 13.21)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'auto_archive_on_recalc';"
```

### Проверить пулы ресурсов
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT type, capacity FROM resource_pool ORDER BY type;"
```

### Проверить настройки режима смен (Итерация 11)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('shift_mode', 'shift_intervals', 'shift_duration_hours', 'allow_weekend_work') ORDER BY setting_key;"
```

### Проверить снапшоты конкретного плана (Итерация 13.15)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT sv.name, (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products, (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment FROM schedule_version sv ORDER BY sv.created_at DESC LIMIT 5;"
```

## ⚠️ Известные ограничения

Полный список — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#известные-ограничения).

Ключевые:
- **Архивация (13.21):** версия НЕ архивируется, если используется в `whatif_scenario` со статусом `DRAFT` или `RUNNING`.
- **Снапшоты (13.15):** старые планы могут иметь пустые снапшоты — помечены ⚠.
- **Режимы смен:** при смене `shift_mode` все задачи теряют привязку к сменам.
- **What-if RUNNING:** нельзя удалить сценарий во время расчёта.
- **Multi-objective:** если все веса = 0 (кроме makespan), работает как single-objective.
- **Редактирование (14.2):** при открытии плана режим по умолчанию — readonly; для редактирования нужно кликнуть `✏️`.

## 🐛 Troubleshooting

Краткий список — в [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

Частые проблемы:
- **`UndefinedColumnError`** → не применена миграция (см. таблицу в TROUBLESHOOTING).
- **`usePlan must be used within PlanProvider`** → очистить `node_modules\.vite`.
- **Advisor «дёргается»** → `useCallback` в `PlainContext.tsx`.
- **План пуст (⚠)** → снапшоты не заполнены, пересоздать план.
- **Старая версия не архивируется** → используется в what-if сценарии, снекбар покажет детали.
- **Задачи не перетаскиваются на Ганте (14.2)** → проверьте, что режим `✏️ Редактирование`, а не `🔒 Просмотр`.

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
| 9 | Рефакторинг, A3, C2 | 2 нед | 🟡 | ✅ |
| 10 | Календарная постобработка | 2 нед | 🟡 | ✅ |
| 11 | Режимы смен, app_settings, pan/zoom | 2 нед | 🟡 | ✅ |
| 12 | Multi-objective и what-if | 2 нед | 🟡 | ✅ |
| 13.3 | Аудит | 1 нед | 🟡 | ✅ |
| 13.14 | plan_settings | 1 нед | 🟡 | ✅ |
| 13.15 | Снапшоты при создании плана | 2 дня | 🔥🔥 | ✅ |
| 13.16 | Унификация диалогов | 2 дня | 🟡 | ✅ |
| 13.17 | Каскадный сдвиг задач | 1 нед | 🟡 | ✅ |
| 13.18 | Улучшения Ганта | 3 дня | 🟡 | ✅ |
| 13.19 | Флаг planDirty | 2 дня | 🟡 | ✅ |
| 13.20 | Прогресс-диалог пересчёта | 1 день | 🔥🔥 | ✅ |
| 13.21 | Архивация версий планов | 3 дня | 🟡 | ✅ |
| 14.1 | Режимы отображения Ганта | 3 дня | 🟡 | ✅ |
| **14.2** | **Редактирование плана прямо на Ганте** | **3 дня** | **🔥🔥** | **✅** |
| 15 | Встроенная справка пользователя | 1 нед | 🟡 | ⏳ |

Полный Roadmap — в [docs/ROADMAP.md](docs/ROADMAP.md).

## 📄 Лицензия

Внутренний проект.

---

Итерации 0–14.2 завершены. Следующая — Итерация 15: Встроенная справка пользователя (⏳).