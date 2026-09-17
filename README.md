# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **1.8.0** (Итерации 0–7 завершены)

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
- **Сменного планирования** (одна смена в день, 08:00–20:00)
- **Лабораторных блокировок** (партия не участвует в планировании до одобрения)
- **Деградации охлаждения** (`fast`/`slow` при 2+ параллельных реакторах)
- **Мульти-тенантности** и **версионирования планов** (снапшоты справочников)

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

### Общие возможности
- ✅ JWT авторизация и ролевая модель (ADMIN, PLANNER, MASTER, LAB, VIEWER)
- ✅ Управление оборудованием, продуктами, материалами, рецептурами
- ✅ Технологические карты с формулами расчёта длительностей
- ✅ Автоматическое разбиение заказов на партии
- ✅ Диаграмма Ганта с интерактивным просмотром
- ✅ Экспорт плана в Excel (с колонками «Заблокировано», «Причина», «Режим охлаждения»)
- ✅ Версионирование планов через снапшоты

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
│   │   │   ├── gantt.py                   # Итерация 1, 5, 7 + hotfix
│   │   │   ├── calendar.py
│   │   │   ├── advisor.py                 # Итерация 2, 7
│   │   │   ├── shift.py                   # Итерация 3, 5, 7 + hotfix
│   │   │   ├── shift_models.py
│   │   │   ├── reschedule.py              # Итерация 4
│   │   │   ├── reschedule_models.py
│   │   │   ├── lab.py                     # Итерация 5
│   │   │   ├── lab_models.py
│   │   │   ├── personnel.py               # Итерация 6
│   │   │   ├── personnel_models.py        # Итерация 6
│   │   │   └── models.py
│   │   ├── auth/                          # JWT + RBAC
│   │   ├── core/                          # Конфигурация
│   │   ├── scheduler/                     # Ядро планировщика
│   │   │   ├── core.py                    # Итерация 5, 6, 7 + hotfix
│   │   │   ├── data_loader.py             # Итерация 5, 6
│   │   │   ├── routing.py                 # Итерация 1, 5, 6
│   │   │   ├── materials.py               # Итерация 2
│   │   │   ├── advisor.py                 # Итерация 2, 7
│   │   │   ├── feasibility.py             # Итерация 2
│   │   │   ├── shifts.py                  # Итерация 3
│   │   │   ├── rescheduler.py             # Итерация 4, 5
│   │   │   ├── saver.py                   # hotfix Итерации 5, 6, 7
│   │   │   ├── feature_flags.py           # Итерация 6, 7
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
│   │   └── fix_shift_names.sql
│   ├── .env
│   ├── init_schema.sql                    # v1.8.0
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
│   │   ├── pages/                         # Login, Equipment, ..., Personnel
│   │   ├── services/api.ts
│   │   ├── types/index.ts
│   │   ├── App.tsx
│   │   └── main.tsx
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

**Advisor (Итерация 2 + Итерация 7):**
- `GET /api/v1/schedule/advice` — подсказки (включая COOLING_DEGRADATION)
- `POST /api/v1/schedule/feasibility` — оценка исполнимости

**Сменное планирование (Итерация 3 + Итерация 7):**
- `GET /api/v1/shift/list` — список смен
- `GET /api/v1/shift/by-date/{date}` — смена на дату
- `GET /api/v1/shift/{shift_id}/tasks` — задания смены (с `cooling_mode`)
- `GET /api/v1/shift/{shift_id}/carryover` — переходящие задания (с `cooling_mode`)
- `POST /api/v1/shift/task/{task_id}/fact` — внести факт

**Перепланирование (Итерация 4):**
- `POST /api/v1/schedule/reschedule` — перепланировать
- `GET /api/v1/schedule/compare` — сравнить две версии
- `PUT /api/v1/schedule/task/{id}/pin` — закрепить/открепить

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

**Гант:**
- `GET /api/v1/gantt/` — данные диаграммы (с `cooling_mode`)
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

### Feature-флаги

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
| enable_cz_integration | ❌ OFF | 8 |

### Параметры организации (Итерация 7)

| Ключ | Значение | Назначение |
|------|----------|------------|
| `cooling_degradation_factor` | `1.3` | Коэффициент замедления охлаждения |
| `cooling_zone_capacity` | `2` | Максимум реакторов в зоне охлаждения |
| `max_fill_percent` | `0.70` | Максимальная загрузка реактора |
| `planning_start_date` | `2026-09-01T08:00:00` | Дата старта планирования |

## 🧪 Тестирование

```
cd backend
pytest tests/ -v
```

**Текущее состояние:** 204 passed.

| Файл | Тестов | Что проверяет |
|------|--------|---------------|
| `test_tz_case.py` | 41 | Эталонный кейс ТЗ |
| `test_materials.py` | 11 | Расчёт потребности в сырье |
| `test_advisor.py` | 9 | Подсказки Advisor |
| `test_routing.py` | 15 | Цепочки операций + truncate после лабы |
| `test_shifts.py` | 16 | Смены и API смен |
| `test_rescheduler.py` | 18 | Перепланирование + фильтрация блокировок |
| `test_lab.py` | 24 | Лабораторные блокировки |
| `test_personnel.py` | 15 | Люди как ресурс (Итерация 6) |
| `test_cooling_degradation.py` | 19 | Охлаждение с деградацией (Итерация 7 + hotfix) |
| `test_versions.py` | 4 | Hotfix: деактивация версий |
| `test_dependencies.py` | 9 | FastAPI dependencies |
| `test_auth_models.py` | 9 | Pydantic-модели авторизации |
| `test_security.py` | 5 | JWT и bcrypt |
| `test_config.py` | 3 | Конфигурация |

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
docker cp backend\migrations\add_10.sql aps_postgres:/tmp/add_10.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_10.sql
```

### Очистить кэш Python (если изменения не подхватываются)

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

### Проверить настройки Итерации 7

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM organization_settings WHERE setting_key IN ('enable_cooling_degradation', 'cooling_degradation_factor', 'cooling_zone_capacity');"
```

### Проверить пулы ресурсов

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT type, capacity FROM resource_pool ORDER BY type;"
```

### Посмотреть распределение cooling_mode в активной версии

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT st.cooling_mode, COUNT(*) FROM scheduled_task st JOIN schedule_version sv ON sv.id = st.schedule_version_id WHERE sv.is_active = true GROUP BY st.cooling_mode ORDER BY st.cooling_mode NULLS LAST;"
```

## ⚠️ Известные ограничения

1. **Слив на линию** добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает: NoOverlap не даёт им пересечься.

2. **Материальные ограничения** — предупреждения Advisor, не жёсткие constraints в CP-SAT.

3. **График поставок** — все поставки считаются доступными (без учёта `expected_at` vs дата старта партии).

4. **Крем-мыло 5л (Р2)** имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Advisor подсвечивает это как ROUTE_MISMATCH.

5. **Лабораторные блокировки:** после блокировки партии нужно вручную запустить перепланирование (`POST /api/v1/schedule/reschedule`) — автоматическое запланировано на Итерацию 9.

6. **Персонал:** на Итерации 6 нет HR-подсистемы (нет ФИО, смен, отпусков). Только пулы с capacity.

7. **Solver:** с `AddCumulative` и моделью деградации охлаждения (O(N²) bool-переменных) solver может не успеть найти OPTIMAL за 120 секунд — выдаёт FEASIBLE. Увеличение таймаута или `num_search_workers` — Итерация 9.

8. **Деградация охлаждения (Итерация 7)** активна, но в тестовом кейсе ТЗ `slow` не появляется — узкие места в других ресурсах (линии, аппаратчики, единственный tank). Чтобы увидеть `slow` в UI — уменьшите `cooling_degradation_factor` до 1.05 или разгрузите Line 1.

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

**Решение:** сравнивать по **UTC-дате**:

```sql
WHERE (starts_at AT TIME ZONE 'UTC')::date = :shift_date
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

**Причина:** не применён hotfix Итерации 7 (модель `b_slow ⟺ пересечение` не активна). Используется старая модель из `plugins.py`, где `AddNoOverlap(fast_intervals)` конфликтует с `AddCumulative`.

**Решение:** убедиться, что в `core.py` вызывается `_apply_cooling_degradation_model`, а в `plugins.py` убран `AddNoOverlap(fast_intervals)` из `CoolingDegradationConstraint`. Проверить логи backend:

```
[scheduler] [INFO] [stage=build] Итерация 7 (fix): применяем модель деградации для N cooling-задач
```

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
| 8 | ЧЗ и интеграции | 2 нед | 🔥 | 📋 Next |
| 9 | Рефакторинг и качество | 2 нед | 🟡 | ⏳ |
| 10 | Multi-objective и what-if | 2 нед | 🟡 | ⏳ |

## 📄 Лицензия

Внутренний проект.

---

**Итерации 0, 1, 2, 3, 4, 5, 5h, 6, 7, 7h завершены.**

**Итерация 7 hotfix — модель деградации охлаждения.**

**Готовы к Итерации 8 — ЧЗ и интеграции.**