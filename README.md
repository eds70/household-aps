Держите **полный `README.md`** одним сообщением.

---

**Путь:** `README.md` (корень проекта)

```markdown
# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **1.6.1** (Итерации 0–5 + hotfix завершены)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-9.15+-F7931E)](https://developers.google.com/optimization)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

---

## ⚡ TL;DR — запуск за 60 секунд

Из корня проекта (household-aps):

    .\quickstart.ps1

Скрипт сделает всё: поднимет PostgreSQL в Docker, применит схему и демо-данные, поставит Python/npm-зависимости, создаст админа.

После — в двух терминалах:

    Терминал 1 (Backend):
    cd backend; .\.venv\Scripts\Activate.ps1; python run_server.py

    Терминал 2 (Frontend):
    cd frontend; npm run dev

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
- **Ресурсных ограничений** (аппаратчики, бойлер, зона охлаждения, лаборатория)
- **Остатков сырья** и графика поставок
- **Сменного планирования** (одна смена в день, 08:00–20:00)
- **Лабораторных блокировок** (партия не участвует в планировании до одобрения)
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
- ✅ Модуль `advisor.py` — 4 типа подсказок:
  - 🔴 **MATERIAL_SHORTAGE** — дефицит сырья
  - 🟡 **UNDERLOAD** — неполная загрузка реактора
  - 🔵 **ROUTE_MISMATCH** — VIA_TANK без танка
  - 🔵 **EQUIPMENT_GAP** — простои оборудования
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

#### Hotfix Итерации 5

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

### Общие возможности
- ✅ JWT авторизация и ролевая модель (ADMIN, PLANNER, MASTER, LAB, VIEWER)
- ✅ Управление оборудованием, продуктами, материалами, рецептурами
- ✅ Технологические карты с формулами расчёта длительностей
- ✅ Автоматическое разбиение заказов на партии
- ✅ Диаграмма Ганта с интерактивным просмотром
- ✅ Экспорт плана в Excel (с колонками «Заблокировано» и «Причина»)
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
│   │   │   ├── gantt.py                   # Итерация 1, 5 + hotfix #4
│   │   │   ├── calendar.py
│   │   │   ├── advisor.py                 # Итерация 2
│   │   │   ├── shift.py                   # Итерация 3, 5 + hotfix #2, #3
│   │   │   ├── shift_models.py            # Итерация 3, 5
│   │   │   ├── reschedule.py              # Итерация 4
│   │   │   ├── reschedule_models.py       # Итерация 4
│   │   │   ├── lab.py                     # Итерация 5
│   │   │   ├── lab_models.py              # Итерация 5
│   │   │   └── models.py                  # Итерация 2, 5 + hotfix #4
│   │   ├── auth/                          # JWT + RBAC
│   │   ├── core/                          # Конфигурация
│   │   ├── scheduler/                     # Ядро планировщика
│   │   │   ├── core.py                    # Итерация 5 (пропуск заблокированных)
│   │   │   ├── data_loader.py             # Итерация 5
│   │   │   ├── routing.py                 # Итерация 1, 5
│   │   │   ├── materials.py               # Итерация 2
│   │   │   ├── advisor.py                 # Итерация 2
│   │   │   ├── feasibility.py             # Итерация 2
│   │   │   ├── shifts.py                  # Итерация 3
│   │   │   ├── rescheduler.py             # Итерация 4, 5
│   │   │   ├── saver.py                   # hotfix #1
│   │   │   ├── feature_flags.py
│   │   │   └── logging_config.py
│   │   └── main.py
│   ├── migrations/                        # История миграций
│   │   ├── add_history_0_2.sql
│   │   ├── add_06.sql
│   │   ├── add_06b.sql
│   │   ├── add_07.sql
│   │   ├── add_08.sql                     # Итерация 5
│   │   ├── fix_versions_hotfix.sql        # hotfix #1
│   │   ├── fix_shift_names.sql
│   │   └── README.md
│   ├── .env
│   ├── init_schema.sql                    # v1.6.1
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
│   │   ├── pages/                         # Login, Equipment, ..., Shift
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

    .\quickstart.ps1

**Флаги:**
- `-SkipDb` — пропустить PostgreSQL
- `-SkipSeed` — пропустить схему и демо-данные
- `-SkipFrontend` — пропустить npm-зависимости
- `-Help` — справка

**Если PowerShell блокирует запуск скриптов:**

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

### Ручной

#### Предварительные требования
- Python 3.12+
- Node.js 18+
- Docker

#### Шаг 1: Запуск PostgreSQL

    docker run --name aps_postgres -e POSTGRES_USER=aps -e POSTGRES_PASSWORD=aps_secret -e POSTGRES_DB=household -p 5432:5432 -d postgres:16

#### Шаг 2: Инициализация схемы и демо-данных

**⚠️ ВАЖНО:** применять SQL-файлы через `docker cp` + `psql -f`, а не через `Get-Content | docker exec` — иначе PowerShell испортит кириллицу.

    docker cp backend\init_schema.sql    aps_postgres:/tmp/init_schema.sql
    docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

#### Шаг 3: Создание администратора

    cd backend
    python -m scripts.create_admin_user

#### Шаг 4: Запуск Backend

    cd backend
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt
    python run_server.py

*Swagger UI: http://localhost:8000/docs*

#### Шаг 5: Запуск Frontend

    cd frontend
    npm install
    npm run dev

*Приложение: http://localhost:5173*  
*Демо-доступ: `admin@household.ru` / `admin123`*

## 📚 Документация API

После запуска backend: **http://localhost:8000/docs**

Защищённые эндпоинты требуют `Authorization: Bearer <token>`.

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

**Advisor (Итерация 2):**
- `GET /api/v1/schedule/advice` — подсказки
- `POST /api/v1/schedule/feasibility` — оценка исполнимости

**Сменное планирование (Итерация 3):**
- `GET /api/v1/shift/list` — список смен
- `GET /api/v1/shift/by-date/{date}` — смена на дату
- `GET /api/v1/shift/{shift_id}/tasks` — задания смены
- `GET /api/v1/shift/{shift_id}/carryover` — переходящие задания
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

**Гант:**
- `GET /api/v1/gantt/` — данные диаграммы
- `GET /api/v1/gantt/export` — экспорт в Excel

## 🧩 Ключевые сущности

### Оборудование
- **REACTOR** — реакторы (5000–10000 кг)
- **TANK** — накопительные ёмкости (буфер между реактором и линией)
- **FILLING_LINE** — линии розлива
- **MANUAL_STATION** — ручные станции
- **BOILER** — бойлер (нагрев воды, 2000 кг)

Все оборудование идентифицируется по полю **`code`** (REACTOR_1, TANK_1, LINE_1, BOILER).

### Цепочки рабочих центров (Итерация 1)

**DIRECT:** реактор → линия

    REACTOR_1 → LINE_1

**VIA_TANK:** реактор → накопительная ёмкость → линия

    REACTOR_1 → TANK_1 → LINE_1

**Особенности:**
- Операции слива занимают **два ресурса** одновременно
- Реактор освобождается **только после полного слива**
- Замыв реактора стартует после слива и занимает реактор (NoOverlap)

### Продукция
- **PF** (полуфабрикат) — `route_type`: DIRECT | VIA_TANK
- **GP** (готовая продукция) — привязана к ПФ через `parent_pf_id`

### Смены (Итерация 3)

- **Одна смена в день:** 08:00–20:00 (12 часов).
- **Выходные** (сб, вс) — смены создаются, `is_working = false`.
- Задачи автоматически привязываются к смене по `planned_start` (с fallback на ближайшую).
- **Переходящие** задачи — не завершённые в предыдущей смене.

### Лабораторные блокировки (Итерация 5)

**Статусы партии (`batch.lab_status`):**

| Статус | Описание |
|--------|----------|
| `NOT_REQUIRED` | Партия не требует лабораторного анализа |
| `PENDING_LAB` | Ожидает анализа (лаборант должен проверить) |
| `APPROVED` | Одобрено лабораторией |
| `BLOCKED` | Заблокировано лабораторией (не участвует в планировании) |

**Логика:**
1. После завершения операции `needs_lab=true` партия становится `PENDING_LAB`.
2. Лаборант (или мастер) может **заблокировать** партию (`POST .../block`) — она получает `is_lab_blocked=true` и `lab_status=BLOCKED`.
3. **Планировщик исключает заблокированные партии** из построения цепочек операций.
4. Разблокировка (`POST .../unblock`) возвращает партию в планирование с `lab_status=APPROVED`.

**Журнал:** все действия записываются в `lab_analysis_log` (кто, когда, почему).

**Права:** блокировать/разблокировать могут роли `LAB`, `MASTER`, `ADMIN`.

### Advisor (Итерация 2)

| Код | Severity | Описание |
|-----|----------|----------|
| MATERIAL_SHORTAGE | CRITICAL / WARNING | Дефицит сырья или малый запас |
| UNDERLOAD | INFO | Неполная загрузка реактора |
| ROUTE_MISMATCH | INFO | VIA_TANK без танка |
| EQUIPMENT_GAP | INFO | Простой оборудования > 8 ч |

### Feature-флаги

| Флаг | Статус | Итерация |
|------|--------|----------|
| enable_tank_routing | ✅ ON | 1 |
| enable_advisor | ✅ ON | 2 |
| enable_material_constraints | ✅ ON | 2 |
| enable_shift_planning | ✅ ON | 3 |
| enable_rescheduling | ✅ ON | 4 |
| enable_lab_blocking | ✅ ON | 5 |
| enable_operator_pools | ❌ OFF | 6 |
| enable_manual_station | ❌ OFF | 6 |
| enable_cooling_degradation | ❌ OFF | 7 |
| enable_cz_integration | ❌ OFF | 8 |

## 🧪 Тестирование

    cd backend
    pytest tests/ -v

**Текущее состояние:** 170 passed.

| Файл | Тестов | Что проверяет |
|------|--------|---------------|
| `test_tz_case.py` | 41 | Эталонный кейс ТЗ |
| `test_materials.py` | 11 | Расчёт потребности в сырье |
| `test_advisor.py` | 9 | Подсказки Advisor |
| `test_routing.py` | 15 | Цепочки операций + truncate после лабы |
| `test_shifts.py` | 16 | Смены и API смен |
| `test_rescheduler.py` | 18 | Перепланирование + фильтрация блокировок |
| `test_lab.py` | 24 | Лабораторные блокировки |
| `test_versions.py` | 4 | Hotfix: деактивация версий |
| `test_dependencies.py` | 9 | FastAPI dependencies |
| `test_auth_models.py` | 9 | Pydantic-модели авторизации |
| `test_security.py` | 5 | JWT и bcrypt |
| `test_config.py` | 3 | Конфигурация |

## 🔧 Полезные команды

### Проверить статус PostgreSQL

    docker ps --filter "name=aps_postgres"

### Подключиться к БД

    docker exec -it aps_postgres psql -U aps -d household

### Пересоздать БД с нуля

    docker exec aps_postgres psql -U aps -d household -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    docker cp backend\init_schema.sql    aps_postgres:/tmp/init_schema.sql
    docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

### Применить SQL-миграцию (правильный способ)

    docker cp backend\migrations\add_08.sql aps_postgres:/tmp/add_08.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_08.sql

### Очистить кэш Python (если изменения не подхватываются)

    cd backend
    Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

### Полная очистка (снести контейнер и БД)

    docker rm -f aps_postgres

### Экспорт данных из БД

    docker exec aps_postgres pg_dump -U aps household > backup.sql

## ⚠️ Известные ограничения

1. **Слив на линию** добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает: NoOverlap не даёт им пересечься. Исправим в Итерации 9 (рефакторинг).

2. **Материальные ограничения** — не жёсткие constraints в CP-SAT, а предупреждения Advisor. Для жёсткого учёта нужно добавить cumulative constraints.

3. **График поставок** — все поставки считаются доступными (без учёта `expected_at` vs дата старта партии).

4. **Крем-мыло 5л (Р2)** имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Слив идёт DIRECT. Advisor подсвечивает это как ROUTE_MISMATCH.

5. **Лабораторные блокировки:** при блокировке партии нужно вручную запустить перепланирование (`POST /api/v1/schedule/reschedule`) — автоматическое перепланирование запланировано на Итерацию 9.

## 🐛 Troubleshooting

### 1. FastAPI 0.139+: `_IncludedRouter` в `app.routes`

**Симптом:** скрипт проверки `getattr(r, 'path', None)` возвращает `None` для всех `include_router(...)` — кажется, что роутеры не подключены.

**Причина:** в FastAPI ≥ 0.139 `app.routes` содержит `_IncludedRouter` — обёртки с атрибутом `.prefix`, а не `.path`.

**Решение:** проверять через `app.openapi()['paths']`:

```python
from app.main import app
paths = sorted(app.openapi()['paths'].keys())
print([p for p in paths if '/shift' in p])
```

### 2. Кэш Python (`__pycache__`) на Windows

**Симптом:** после правки `main.py` изменений не видно, даже после перезапуска uvicorn.

**Причина:** на Windows mtime `.pyc` иногда совпадает с mtime `.py`, и Python не перекомпилирует.

**Решение:** удалить `__pycache__` **в проекте** (не в venv!):

    cd backend
    Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Или запустить с флагом `-B`:

    python -B run_server.py

### 3. Кэш браузера — Swagger/UI показывает старое

**Симптом:** в Swagger нет нового раздела, или UI показывает старые данные, хотя backend возвращает корректный JSON.

**Решение:**
1. Открыть в **режиме инкогнито** (Ctrl+Shift+N).
2. Или **Ctrl+Shift+Delete** → очистить кэш.
3. В крайнем случае — **перезагрузить компьютер** (сбрасывает Service Workers).

### 4. Таймзона naive datetime в asyncpg

**Симптом:** `GET /api/v1/shift/by-date/2026-09-01` возвращает 404, хотя смена есть в БД.

**Причина:** Python передаёт `datetime.combine(...)` как **naive datetime**. PostgreSQL сравнивает `timestamptz >= timestamp` через таймзону **сессии asyncpg**, которая может отличаться от UTC.

**Решение:** сравнивать по **UTC-дате**:

```sql
WHERE (starts_at AT TIME ZONE 'UTC')::date = :shift_date
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
| 6 | Люди как ресурс | 2 нед | 🔥🔥 | 📋 Next |
| 7 | Охлаждение с деградацией | 1.5 нед | 🔥 | ⏳ |
| 8 | ЧЗ и интеграции | 2 нед | 🔥 | ⏳ |
| 9 | Рефакторинг и качество | 2 нед | 🟡 | ⏳ |
| 10 | Multi-objective и what-if | 2 нед | 🟡 | ⏳ |

## 📄 Лицензия

Внутренний проект.

---

**Итерации 0, 1, 2, 3, 4, 5 завершены. Hotfix Итерации 5 — деактивация версий + таймзона + Gantt.**

**Готовы к Итерации 6 — Люди как ресурс.**
```