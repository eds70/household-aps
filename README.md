# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **1.4.0** (Итерации 0–3 завершены)

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

### Общие возможности
- ✅ JWT авторизация и ролевая модель (ADMIN, PLANNER, MASTER, LAB, VIEWER)
- ✅ Управление оборудованием, продуктами, материалами, рецептурами
- ✅ Технологические карты с формулами расчёта длительностей
- ✅ Автоматическое разбиение заказов на партии
- ✅ Диаграмма Ганта с интерактивным просмотром
- ✅ Экспорт плана в Excel
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

- **quickstart.ps1** — ⚡ Скрипт быстрого старта
- **README.md**
- **backend/**
  - **app/**
    - **api/v1/** — REST API endpoints
      - auth.py
      - equipment.py
      - products.py
      - materials.py
      - recipes.py
      - operations.py
      - orders.py
      - schedule.py
      - gantt.py
      - calendar.py
      - advisor.py (Итерация 2)
      - shift.py (Итерация 3)
      - shift_models.py (Итерация 3)
      - models.py
    - **auth/** — JWT + RBAC
    - **core/** — Конфигурация
    - **scheduler/** — Ядро планировщика
      - core.py — Оркестратор планирования
      - data_loader.py — Загрузка данных из БД
      - routing.py — Цепочки операций (Итерация 1)
      - materials.py — Потребность в сырье (Итерация 2)
      - advisor.py — Подсказки (Итерация 2)
      - feasibility.py — Оценка исполнимости (Итерация 2)
      - shifts.py — Смены (Итерация 3)
      - saver.py — Сохранение плана
      - feature_flags.py — Feature-флаги
      - logging_config.py — Structured logging
      - **duration/** — Стратегии длительностей
      - **constraints/** — Плагины ограничений
    - main.py
  - **migrations/** — История миграций
    - add_history_0_2.sql — Склейка Итераций 0–2
    - add_06.sql — Сменное планирование
    - add_06b.sql — Фикс снапшотов
    - fix_shift_names.sql — Фикс кириллицы
    - README.md — Описание миграций
  - .env
  - init_schema.sql — Полная схема БД (v1.4.0)
  - seed_demo.py — Python-скрипт демо-данных
  - seed_demo_data.sql — SQL-версия демо-данных (v1.4.0)
  - **scripts/**create_admin_user.py
  - requirements.txt
  - requirements-dev.txt
  - pyproject.toml
  - run_server.py
- **frontend/**
  - **src/**
    - **components/layout/** — MainLayout
    - **context/** — AuthContext, PlanContext
    - **pages/** — Login, Equipment, Products, Materials, Recipes, Operations, Orders, Schedule, Gantt, Shift
    - **services/**api.ts — Axios с интерсепторами
    - **types/** — TypeScript интерфейсы
    - App.tsx — Роутинг
    - main.tsx
  - package.json
  - vite.config.ts
- **README.md**

## 🚀 Быстрый старт

### Автоматический (рекомендуется)

Из корня проекта:

    .\quickstart.ps1

Скрипт делает всё:
1. Поднимает PostgreSQL в контейнере `aps_postgres`
2. Применяет `init_schema.sql` + `seed_demo_data.sql` (через `docker cp` + `psql -f`)
3. Создаёт `.venv` и ставит Python-зависимости
4. Создаёт администратора `admin@household.ru`
5. Устанавливает npm-зависимости

**Флаги:**
- `-SkipDb` — пропустить PostgreSQL
- `-SkipSeed` — пропустить схему и демо-данные
- `-SkipFrontend` — пропустить npm-зависимости
- `-Help` — справка

**Если PowerShell блокирует запуск скриптов:**

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

### Ручной (если нужен контроль)

#### Предварительные требования
- Python 3.12+
- Node.js 18+
- Docker

#### Шаг 1: Запуск PostgreSQL

    docker run --name aps_postgres -e POSTGRES_USER=aps -e POSTGRES_PASSWORD=aps_secret -e POSTGRES_DB=household -p 5432:5432 -d postgres:16

#### Шаг 2: Инициализация схемы и демо-данных

**⚠️ ВАЖНО:** применять SQL-файлы через `docker cp` + `psql -f`, а не через `Get-Content | docker exec` — иначе PowerShell испортит кириллицу в именах смен.

    # Копируем файлы в контейнер (сохраняет UTF-8)
    docker cp backend\init_schema.sql    aps_postgres:/tmp/init_schema.sql
    docker cp backend\seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql

    # Применяем
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

**Или через Python-скрипт:**

    cd backend
    python seed_demo.py

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

### Запуск в двух терминалах

**Терминал 1 — Backend:**

    cd backend
    .\.venv\Scripts\Activate.ps1
    python run_server.py

**Терминал 2 — Frontend:**

    cd frontend
    npm run dev

**Открыть:**
- Frontend: http://localhost:5173
- Swagger: http://localhost:8000/docs
- Логин: `admin@household.ru` / `admin123`

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
| enable_rescheduling | ❌ OFF | 4 |
| enable_lab_blocking | ❌ OFF | 5 |
| enable_operator_pools | ❌ OFF | 6 |
| enable_manual_station | ❌ OFF | 6 |
| enable_cooling_degradation | ❌ OFF | 7 |
| enable_cz_integration | ❌ OFF | 8 |

## 🧪 Тестирование

    cd backend
    pytest tests/ -v

**Текущее состояние:** 115 passed.

| Файл | Тестов | Что проверяет |
|------|--------|---------------|
| `test_tz_case.py` | 41 | Эталонный кейс ТЗ |
| `test_materials.py` | 11 | Расчёт потребности в сырье |
| `test_advisor.py` | 9 | Подсказки Advisor |
| `test_routing.py` | 11 | Цепочки операций |
| `test_shifts.py` | 16 | Смены и API смен |
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

    docker cp backend\migrations\add_07.sql aps_postgres:/tmp/add_07.sql
    docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_07.sql

### Остановить/запустить PostgreSQL

    docker stop aps_postgres
    docker start aps_postgres

### Полная очистка (снести контейнер и БД)

    docker rm -f aps_postgres

### Экспорт данных из БД

    docker exec aps_postgres pg_dump -U aps household > backup.sql

## ⚠️ Известные ограничения

1. **Слив на линию** добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает: NoOverlap не даёт им пересечься. Исправим в Итерации 4 (перепланирование).

2. **Материальные ограничения** — не жёсткие constraints в CP-SAT, а предупреждения Advisor. Для жёсткого учёта нужно добавить cumulative constraints (Итерация 9).

3. **График поставок** — все поставки считаются доступными (без учёта `expected_at` vs дата старта партии).

4. **Крем-мыло 5л (Р2)** имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Слив идёт DIRECT. Advisor подсвечивает это как ROUTE_MISMATCH.

5. **Кириллица в SQL-файлах:** применять через `docker cp` + `psql -f`, а не через `Get-Content | docker exec` (PowerShell портит UTF-8).

## 🗺️ Roadmap

| # | Итерация | Длит. | Приоритет | Статус |
|---|----------|-------|-----------|--------|
| 0 | Подготовка | 4 дня | 🔥 | ✅ |
| 1 | Цепочки рабочих центров | 2 нед | 🔥🔥🔥 | ✅ |
| 2 | Материальные ограничения и Advisor | 2 нед | 🔥🔥🔥 | ✅ |
| 3 | Сменное планирование и РМ мастера | 2 нед | 🔥🔥🔥 | ✅ |
| 4 | Перепланирование | 2 нед | 🔥🔥🔥 | 📋 Next |
| 5 | Лаборатория и блокировки | 1.5 нед | 🔥🔥 | ⏳ |
| 6 | Люди как ресурс | 2 нед | 🔥🔥 | ⏳ |
| 7 | Охлаждение с деградацией | 1.5 нед | 🔥 | ⏳ |
| 8 | ЧЗ и интеграции | 2 нед | 🔥 | ⏳ |
| 9 | Рефакторинг и качество | 2 нед | 🟡 | ⏳ |
| 10 | Multi-objective и what-if | 2 нед | 🟡 | ⏳ |

## 📄 Лицензия

Внутренний проект.

---

**Итерации 0, 1, 2, 3 завершены. Готовы к Итерации 4 — Перепланирование.**