# 🏭 APS Production Scheduler

**Система автоматического планирования производства на базе OR-Tools CP-SAT**

Версия: **4.6.0** (Итерации 0–15.4 завершены)

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
- **Встроенной справки пользователя** (Итерация 15.1) — 15 markdown-статей в UI
- **Контекстных подсказок** (Итерация 15.2) — 8 всплывающих подсказок в UI
- **FAQ** (Итерация 15.4) — 15 статей «Симптом → Причина → Что делать»

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

**Встроенная справка** после запуска frontend: **http://localhost:5173/help**

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
| react-markdown | 9.x | Рендер markdown в UI |
| remark-gfm | 4.x | GFM-расширения (таблицы, чекбоксы) |

## 📁 Структура проекта

```
household-aps/
├── quickstart.ps1            # ⚡ Скрипт быстрого старта
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── backend/
│   ├── app/
│   │   ├── api/v1/           # REST API endpoints
│   │   │   ├── auth.py
│   │   │   ├── equipment.py
│   │   │   ├── products.py
│   │   │   ├── materials.py
│   │   │   ├── recipes.py
│   │   │   ├── operations.py
│   │   │   ├── orders.py
│   │   │   ├── schedule.py
│   │   │   ├── gantt.py
│   │   │   ├── calendar.py
│   │   │   ├── advisor.py
│   │   │   ├── shift.py
│   │   │   ├── reschedule.py
│   │   │   ├── lab.py
│   │   │   ├── personnel.py
│   │   │   ├── cz.py
│   │   │   ├── settings.py
│   │   │   ├── plan_settings.py
│   │   │   ├── whatif.py
│   │   │   ├── audit.py
│   │   │   ├── help.py
│   │   │   ├── help_models.py
│   │   │   ├── help_docs.py
│   │   │   └── models.py
│   │   ├── auth/
│   │   ├── core/
│   │   ├── scheduler/        # Ядро планировщика
│   │   │   ├── core.py
│   │   │   ├── data_loader.py
│   │   │   ├── routing.py
│   │   │   ├── materials.py
│   │   │   ├── advisor.py
│   │   │   ├── feasibility.py
│   │   │   ├── shifts.py
│   │   │   ├── rescheduler.py
│   │   │   ├── reschedule_cascade.py
│   │   │   ├── cz.py
│   │   │   ├── saver.py
│   │   │   ├── snapshot.py
│   │   │   ├── feature_flags.py
│   │   │   ├── settings.py
│   │   │   ├── settings_reader.py
│   │   │   ├── shift_regenerator.py
│   │   │   ├── calendar_postprocess.py
│   │   │   ├── optimization.py
│   │   │   ├── whatif.py
│   │   │   ├── logging_config.py
│   │   │   ├── duration/
│   │   │   └── constraints/plugins.py
│   │   └── main.py
│   ├── migrations/
│   │   ├── add_history_0_2.sql
│   │   ├── add_06.sql … add_16.sql
│   │   ├── add_21.sql          # plan_settings
│   │   ├── add_23.sql          # is_archived (13.21)
│   │   ├── add_24.sql          # help_article (15.1)
│   │   ├── add_24_seed_1.sql   # 3 статьи
│   │   ├── add_24_seed_2.sql   # 5 статей
│   │   ├── add_24_seed_3.sql   # 7 статей
│   │   ├── add_25.sql          # help_hint (15.2)
│   │   ├── add_25_seed.sql     # 8 подсказок
│   │   ├── add_26_seed_1.sql   # FAQ: планирование (5)
│   │   ├── add_26_seed_2.sql   # FAQ: гант, смены, what-if, ЧЗ (5)
│   │   ├── add_26_seed_3.sql   # FAQ: лаборатория, advisor (5)
│   │   ├── fix_versions_hotfix.sql
│   │   └── fix_shift_names.sql
│   ├── .env
│   ├── init_schema.sql
│   ├── seed_demo.py
│   ├── seed_demo_data.sql
│   ├── scripts/create_admin_user.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   └── run_server.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/DraggableDialog.tsx
│   │   │   ├── common/AppAgGrid.tsx
│   │   │   ├── layout/MainLayout.tsx
│   │   │   ├── help/
│   │   │   │   ├── HelpSidebar.tsx
│   │   │   │   ├── HelpArticleView.tsx
│   │   │   │   └── Hint.tsx
│   │   │   └── gantt/
│   │   │       ├── constants.ts
│   │   │       ├── types.ts
│   │   │       ├── DragTooltip.tsx
│   │   │       ├── GanttFiltersBar.tsx
│   │   │       ├── GanttFiltersPopover.tsx
│   │   │       ├── GanttTaskDialog.tsx
│   │   │       ├── GanttToolbar.tsx
│   │   │       ├── MoveValidationDialog.tsx
│   │   │       ├── RecalcProgressDialog.tsx
│   │   │       ├── RecalcSettingsDialog.tsx
│   │   │       └── TaskContextMenu.tsx
│   │   ├── context/
│   │   │   ├── AuthContext.tsx
│   │   │   ├── PlainContext.tsx
│   │   │   └── HelpHintsContext.tsx
│   │   ├── hooks/
│   │   │   ├── useCascadeMove.ts
│   │   │   ├── useDoubleClick.ts
│   │   │   ├── useDragTooltip.ts
│   │   │   ├── useExpandedGroups.ts
│   │   │   ├── useExpandedRoots.ts
│   │   │   ├── useGanttActions.ts
│   │   │   ├── useGanttData.ts
│   │   │   ├── useGanttDependencies.ts
│   │   │   ├── useGanttFilters.ts
│   │   │   ├── useGanttTimeline.ts
│   │   │   ├── useGanttViewport.ts
│   │   │   ├── useRecalculate.ts
│   │   │   └── useTaskResize.ts
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── EquipmentPage.tsx
│   │   │   ├── ProductsPage.tsx
│   │   │   ├── MaterialsPage.tsx
│   │   │   ├── RecipesPage.tsx
│   │   │   ├── OperationsPage.tsx
│   │   │   ├── OrdersPage.tsx
│   │   │   ├── SchedulePage.tsx
│   │   │   ├── GanttPage.tsx
│   │   │   ├── ShiftPage.tsx
│   │   │   ├── PersonnelPage.tsx
│   │   │   ├── CzPage.tsx
│   │   │   ├── WhatIfPage.tsx
│   │   │   ├── AuditPage.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   ├── PlanSettingsWizard.tsx
│   │   │   └── HelpPage.tsx
│   │   ├── services/api.ts
│   │   ├── theme/
│   │   │   ├── agGridLocale.ts
│   │   │   └── agGridTheme.ts
│   │   ├── types/index.ts
│   │   ├── utils/
│   │   │   ├── ganttBatchColors.ts
│   │   │   ├── ganttBrackets.ts
│   │   │   ├── ganttDowntimes.ts
│   │   │   ├── ganttGroups.ts
│   │   │   ├── ganttHelpers.ts
│   │   │   ├── ganttRenderItems.ts
│   │   │   ├── ganttSetups.ts
│   │   │   ├── ganttTimelineOptions.ts
│   │   │   └── ganttValidators.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── CONFIGURATION.md
│   ├── OPERATIONS.md
│   ├── TROUBLESHOOTING.md
│   ├── DEVELOPMENT.md
│   ├── ROADMAP.md
│   ├── adr/
│   │   ├── README.md
│   │   ├── 0001-use-ortools-cp-sat.md
│   │   ├── 0002-snapshot-tables-for-versioning.md
│   │   ├── 0003-plan-settings-per-plan.md
│   │   ├── 0004-whatif-two-transactions.md
│   │   └── 0005-help-system.md
│   └── requirements/ТЗ.txt
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
docker cp backend\migrations\add_24.sql aps_postgres:/tmp/add_24.sql
docker cp backend\migrations\add_24_seed_1.sql aps_postgres:/tmp/add_24_seed_1.sql
docker cp backend\migrations\add_24_seed_2.sql aps_postgres:/tmp/add_24_seed_2.sql
docker cp backend\migrations\add_24_seed_3.sql aps_postgres:/tmp/add_24_seed_3.sql
docker cp backend\migrations\add_25.sql aps_postgres:/tmp/add_25.sql
docker cp backend\migrations\add_25_seed.sql aps_postgres:/tmp/add_25_seed.sql
docker cp backend\migrations\add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker cp backend\migrations\add_26_seed_2.sql aps_postgres:/tmp/add_26_seed_2.sql
docker cp backend\migrations\add_26_seed_3.sql aps_postgres:/tmp/add_26_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_23.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_25.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_25_seed.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_3.sql
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

#### Шаг 5: Запуск Frontend
```
cd frontend
npm install
npm run dev
```

## 🧪 Тестирование

```bash
cd backend
..venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Текущее состояние:** **678 passed**, 0 warnings.

Подробнее о тестировании — в [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#запуск-тестов).

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
docker cp backend\migrations\add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
```

### Проверить статьи справки по категориям (Итерация 15.1 + 15.4)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT category, COUNT(*) AS cnt FROM help_article GROUP BY category ORDER BY category;"
```

**Ожидаемо:** 9 категорий, **30 статей** (включая 15 FAQ).

### Проверить FAQ-статьи (Итерация 15.4)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT slug, title FROM help_article WHERE category = 'faq' ORDER BY display_order;"
```

**Ожидаемо:** 15 статей с префиксом `faq-`.

### Проверить контекстные подсказки (Итерация 15.2)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT hint_key, title, article_slug FROM help_hint WHERE is_published = TRUE ORDER BY display_order;"
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

### Проверить связь подсказок со статьями (Итерация 15.2)
```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT h.hint_key, h.article_slug, CASE WHEN a.slug IS NULL THEN '❌ NOT FOUND' ELSE '✅ OK' END AS status FROM help_hint h LEFT JOIN help_article a ON a.slug = h.article_slug WHERE h.article_slug IS NOT NULL ORDER BY h.hint_key;"
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
- **Справка (15.1):** поиск неполнотекстовый (`ILIKE`), для 100+ статей — миграция на `tsvector`.
- **Справка (15.1):** нет редактирования статей через UI. Правки — через SQL или seed-миграции.
- **Подсказки (15.2):** нет редактирования через UI. Правки — через SQL или seed-миграции.
- **Подсказки (15.2):** обновление кэша только при перезагрузке страницы.
- **FAQ (15.4):** 15 статей покрывают топ-15 проблем. Дополнения — через seed-миграции.

## 🐛 Troubleshooting

Краткий список — в [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). А также встроенный FAQ в UI: **http://localhost:5173/help/faq-plan-feasible-not-optimal**.

Частые проблемы:
- **`UndefinedColumnError`** → не применена миграция (см. таблицу в TROUBLESHOOTING).
- **`usePlan must be used within PlanProvider`** → очистить `node_modules\.vite`.
- **Advisor «дёргается»** → `useCallback` в `PlainContext.tsx`.
- **План пуст (⚠)** → снапшоты не заполнены, пересоздать план.
- **Старая версия не архивируется** → используется в what-if сценарии, снекбар покажет детали.
- **Задачи не перетаскиваются на Ганте (14.2)** → проверьте, что режим `✏️ Редактирование`, а не `🔒 Просмотр`.
- **Справка не открывается (15.1)** → проверить, что применены миграции `add_24.sql` и seed-файлы.
- **Подсказки не показываются (15.2)** → проверить, что применены миграции `add_25.sql` и `add_25_seed.sql`, а также перезагрузить страницу (Ctrl+F5).
- **Popover подсказки пустой (15.2)** → проверить `body_md` в `help_hint` для нужного `hint_key`.
- **«Читать подробнее» ведёт на 404 (15.2)** → проверить связь `help_hint.article_slug` ↔ `help_article.slug`.
- **FAQ-статьи не появились (15.4)** → проверить, что применены миграции `add_26_seed_1/2/3.sql`.
- **FAQ-категория не отображается (15.4)** → перезапустить backend после правки `help.py`.

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
| 14.2 | Редактирование плана прямо на Ганте | 3 дня | 🔥🔥 | ✅ |
| 15.1 | Встроенная справка пользователя | 3 дня | 🟡 | ✅ |
| 15.2 | Контекстные подсказки | 2 дня | 🟡 | ✅ |
| 15.3 | Интерактивный туториал | 2 дня | 🟡 | ⏳ |
| **15.4** | **FAQ + расширение базы знаний** | **2 дня** | **🟡** | **✅** |
| 15.5 | Редактирование статей в UI | 3 дня | 🟢 | ⏳ |

Полный Roadmap — в [docs/ROADMAP.md](docs/ROADMAP.md).

## 📄 Лицензия

Внутренний проект.

---

Итерации 0–15.4 завершены. Следующая — Итерация 15.3: Интерактивный туториал (⏳).