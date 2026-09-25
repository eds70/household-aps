# Changelog

Все значимые изменения проекта APS Production Scheduler документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Заготовка для Итерации 14: встроенная справка пользователя.

### Changed

#### Frontend — Унификация диалогов через `DraggableDialog`

- **Все 20 диалогов в 12 страницах** переведены на единый компонент
  `frontend/src/components/common/DraggableDialog.tsx`.
- Убраны явные `<Dialog>` / `<DialogTitle>` / `<DialogContent>` /
  `<DialogActions>` — `DraggableDialog` сам оборачивает содержимое.
- Добавлен проп `centerOnOpen?: boolean` (по умолчанию `true`) — диалог
  открывается по центру экрана, а не по верхнему левому углу.
- Убран ~150 строк дублированного drag/resize-кода из `GanttPage.tsx`.

**Затронутые страницы:**

| Страница | Диалогов | Что унифицировано |
|----------|----------|-------------------|
| `EquipmentPage.tsx` | 2 | Добавить оборудование, Ремонт/простой |
| `ProductsPage.tsx` | 1 | Добавить продукт |
| `MaterialsPage.tsx` | 3 | Добавить материал, Импорт, Очистка журнала |
| `RecipesPage.tsx` | 2 | Добавить рецепт, Состав рецепта |
| `OperationsPage.tsx` | 1 | Добавить операцию |
| `OrdersPage.tsx` | 2 | Новый заказ, Авто-разбиение |
| `SchedulePage.tsx` | 1 | Перепланирование |
| `ShiftPage.tsx` | 3 | Внести факт, Заблокировать, Разблокировать |
| `CzPage.tsx` | 1 | Сопоставить скан |
| `WhatIfPage.tsx` | 2 | Создать сценарий, Результат |
| `SettingsPage.tsx` | 1 | Смена режима смен |
| `GanttPage.tsx` | 1 | Расширенный диалог задачи |

**Итого: 20 диалогов в 12 страницах.**

#### Frontend — Временное скрытие раздела «Аудит»

- Пункт «Аудит» убран из `MENU_ITEMS` в `MainLayout.tsx` — страница
  находится в разработке.
- Роут `/audit` **оставлен** — можно открыть по прямой ссылке для отладки.
- Файл `AuditPage.tsx` и API `/api/v1/audit/*` **не удалены** — вернутся,
  когда раздел будет готов.

#### Frontend — Исправление layout `CzPage.tsx`

- Заголовок страницы: `h4` → `h5` (в стиле остальных страниц).
- Иконка: 32px → 28px.
- Корневой `Box`: добавлен `gap: 2`.
- Сводка обёрнута в `Card` с тенью (как `MaterialsPage`, `ShiftPage`).
- Обе колонки (партии + журнал) — в отдельных `Card` с тенью.
- Подпись внизу — в `Card` с серым фоном, а не «висящий» текст.
- Устранено дублирование `key` в списке партий.

## [4.1.1] — 2026-09-25

Итерация 13.15 — исправление: пустые снапшоты у созданных, но не рассчитанных планов.

### Added

#### Итерация 13.15 — Снапшоты при создании плана

**Проблема:**
При создании «пустого» плана через `POST /api/v1/schedule/versions`
(например, из мастера `PlanSettingsWizard` в режиме create) снапшот-таблицы
справочников (`equipment_snapshot`, `product_snapshot`, `operation_snapshot`,
`calendar_snapshot`) **не заполнялись**. UI переключался в readonly-режим
и показывал **пустые гриды** на всех страницах справочников (продукты,
оборудование, техкарты, календарь).

**Решение:**

- **Новый модуль `backend/app/scheduler/snapshot.py`:**
    - `snapshot_all_catalogs(session, org_id, version_id)` — заполняет все
      4 снапшот-таблицы из актуальных справочников.
    - `snapshot_exists(session, version_id)` — проверяет, есть ли снапшоты.
    - `_has_column(session, table, column)` — graceful-проверка схемы
      (для совместимости со старыми БД без `operator_pool`).
    - Идемпотентен (`ON CONFLICT (id, version_id) DO NOTHING`).

- **API `schedule.py`:**
    - `POST /versions` вызывает `snapshot_all_catalogs` — при создании
      плана снапшоты заполняются сразу.
    - `GET /versions` возвращает поле `has_snapshot` — UI использует
      для индикации пустых планов.
    - Ответ `POST /versions` содержит `snapshot_stats` — статистика
      по каждой таблице.

- **`saver.py`:**
    - `_do_save` делегирует снапшоты в `snapshot_all_catalogs`.
    - Удалён inline SQL (4 INSERT'а) — теперь один вызов.
    - `save_stats` возвращает `snapshot_stats`.

- **Frontend `PlainContext.tsx`:**
    - `PlanVersion.has_snapshot?: boolean`.
    - `CurrentPlan.has_snapshot: boolean` (обязательное).
    - `setPlan(id, name, hasSnapshot?)` — третий опциональный параметр.
    - `currentPlanHasSnapshot` — новое поле в контексте.
    - `loadVersions()` синхронизирует `has_snapshot` из БД.

- **Frontend `SchedulePage.tsx`:**
    - `handleOpenPlan` передаёт `has_snapshot` в `setPlan`.
    - Список планов: иконка ⚠ рядом с планами без снапшотов.
    - Строки без снапшотов подсвечены жёлтым (`#fff8e1`).

- **Frontend `GanttPage.tsx`:**
    - Если у плана нет снапшотов — показывается предупреждение вместо
      диаграммы.
    - Кнопки «Перейти к планированию» и «Закрыть план».

- **Тесты (+43, всего 535):**
    - `test_snapshot.py` (18).
    - `test_schedule_create_version.py` (10).
    - `test_saver_uses_snapshot.py` (10).
    - Обновлён `test_plan_settings_models.py`: `test_update_request_requires_settings`
      → `test_update_request_no_args_is_valid` (устаревший тест, сломанный
      ещё до 13.15).

**Ключевые гарантии:**
- ✅ **Новые планы** сразу имеют снапшоты → справочники видны.
- ✅ **Старые планы** подсвечены ⚠, при открытии — предупреждение.
- ✅ **Единый источник правды** для снапшотов — модуль `snapshot.py`.
- ✅ **Обратная совместимость:** старые планы всё ещё открываются.

### Changed

- Версия проекта: `4.1.0` → `4.1.1`.
- `POST /api/v1/schedule/versions` теперь заполняет снапшоты.
- `GET /api/v1/schedule/versions` возвращает `has_snapshot`.
- `ScheduleSaver._do_save` делегирует снапшоты в `snapshot_all_catalogs`.
- `PlainContext` — новое поле `currentPlanHasSnapshot`.
- `SchedulePage` — визуальная индикация планов без снапшотов.
- `GanttPage` — предупреждение для пустых планов.

### Fixed

- **Проблема:** при создании «пустого» плана через `POST /schedule/versions`
  снапшоты справочников не заполнялись. UI показывал пустые гриды на
  всех страницах справочников (продукты, оборудование, техкарты, календарь).
- **Решение:** заполнение снапшотов при создании плана + индикация
  пустых планов в UI.
- **Тест `test_update_request_requires_settings`** (из Итерации 13.14) —
  переименован в `test_update_request_no_args_is_valid`. Причина: в
  Итерации 13.14.1 модель `PlanSettingsUpdateRequest` получила
  `default_factory=dict` для `settings`, поэтому запрос без аргументов
  стал валидным. Старый тест ожидал `ValidationError` и падал.

---

## [4.1.0] — 2026-09-25

Итерации 13.14 и 13.14.1.

### Added

#### Итерация 13.14 — Настройки, привязанные к плану (`plan_settings`)

- **БД: миграция `add_21.sql`.**
    - Таблица `plan_settings`:
        - `organization_id`, `schedule_version_id` — привязка к плану.
        - `setting_key`, `setting_value` (JSONB) — ключ-значение.
        - `value_type`, `category`, `label`, `description` — метаданные (снапшот).
        - `min_value`, `max_value`, `options`, `display_order`, `is_system`.
        - `UNIQUE (schedule_version_id, setting_key)` — защита от дублей.
        - `FOREIGN KEY ... ON DELETE CASCADE` — при удалении плана настройки удаляются.
    - Триггер `copy_app_settings_to_plan`:
        - `AFTER INSERT ON schedule_version` — автоматически копирует все `app_settings` в `plan_settings` нового плана.
        - Идемпотентен (`ON CONFLICT DO NOTHING`).
        - Работает на уровне БД — не нужен ни Python, ни API.
    - Индексы:
        - `idx_plan_settings_version` — по `schedule_version_id`.
        - `idx_plan_settings_org_category` — по `(organization_id, category)`.

- **Backend.**
    - `DataLoader(version_id=...)` — читает настройки из `plan_settings` этого плана. Если `version_id=None` или `plan_settings` пуст → fallback на `app_settings`.
    - `ProductionScheduler(version_id=...)` — принимает `version_id`, прокидывает в `DataLoader`.
    - `settings_reader.py` — 3 функции получили параметр `version_id`:
        - `read_feature_flags(db, org_id, version_id=None)`.
        - `read_setting(db, org_id, key, default, version_id=None)`.
        - `read_settings_dict(db, org_id, keys, version_id=None)`.
    - `rescheduler.py` — `version_id=from_version_id` в основном и fallback вызовах `ProductionScheduler`.
    - `whatif.py` — `version_id=base_version_id` при запуске сценария.
    - **API `/api/v1/plan-settings`** — 3 эндпоинта:
        - `GET    /version/{version_id}` — настройки плана + метаданные.
        - `PUT    /version/{version_id}` — массовое обновление (валидация через `validate_setting`).
        - `POST   /version/{version_id}/reset` — сброс к глобальным `app_settings`.
    - **6 API-модулей** обновлены — все получили опциональный `version_id`:
        - `advisor.py` — `?version_id=...` в `/advice`, `/feasibility`.
        - `lab.py` — 7 эндпоинтов с `version_id`.
        - `cz.py` — 7 эндпоинтов с `version_id`.
        - `personnel.py` — 4 эндпоинта с `version_id`.
        - `reschedule.py` — 3 эндпоинта с `version_id`.
        - `shift.py` — 5 эндпоинтов с `version_id`.

- **Frontend.**
    - `planSettingsApi` в `api.ts` — 3 метода (`getForVersion`, `updateForVersion`, `resetForVersion`).
    - `api.ts` — все API-модули получили опциональный `versionId?`.
    - `PlanSettingsWizard.tsx` — мастер настроек плана (9 шагов):
        1. Основные (`planning`).
        2. Режим смен (`shifts`).
        3. Календарь (`calendar`).
        4. Охлаждение (`cooling`).
        5. Ресурсы (`resources`).
        6. Материалы и лаборатория (`materials` + `lab`).
        7. Маршруты и функции (`features`).
        8. Честный Знак (`cz`).
        9. Оптимизация (`optimization`).
    - `SchedulePage.tsx` — кнопка «Настройки плана» (⚙) в действиях таблицы планов.
    - `MainLayout.tsx` — активный план на верхней плашке.
    - `SchedulePage.tsx` — усиленное визуальное выделение текущего плана.
    - Иконка «Открыть план» меняется на «Закрыть план» (✕) для текущего.

- **Тесты (+171, всего 492).**
    - `test_plan_settings_models.py` (8).
    - `test_plan_settings_api.py` (23).
    - `test_plan_settings_migration.py` (16).
    - `test_plan_settings_data_loader.py` (14).
    - `test_plan_settings_integration.py` (11).
    - `test_rescheduler_uses_plan_settings.py` (11).
    - `test_whatif_uses_plan_settings.py` (15).

#### Итерация 13.14.1 — Документация

- Обновлён `README.md` до версии 4.1.0.
- Добавлен раздел «Настройки, привязанные к плану» в «Ключевые сущности».
- Добавлены PowerShell-примеры для API `/plan-settings/*`.
- Добавлены команды проверки `plan_settings` и триггера.

### Changed

- Версия проекта: `4.0.0` → `4.1.0`.
- `ProductionScheduler` и `DataLoader` принимают `version_id`.
- Все API-эндпоинты, зависящие от настроек, получили опциональный `version_id`.
- `PlanContext.tsx` — активный план теперь отображается в верхней плашке.

### Fixed

- `PlanContext.tsx` — устранён цикл ре-рендера (стабильные ссылки через `useCallback`).
- `ShiftPage.tsx` — фиксированная шапка + скроллируемый список задач.
- `GanttPage.tsx` — восстановлен pan диаграммы (конфликт с drag устранён через `editable.updateTime` как функцию).

---

## [4.0.0] — 2026-09-24

Итерации 12 и 13.3.

### Added

#### Итерация 12 — Multi-objective и what-if сценарии

- **Multi-objective оптимизация.**
    - Новый модуль `backend/app/scheduler/optimization.py`:
        - `OptimizationWeights` — dataclass с 5 весами `[0, 1]`.
        - `from_settings()` — читает из `app_settings`.
        - `validate()` — проверка корректности.
        - `to_int()` — приведение к fixed-point (`PRECISION = 10000`).
        - `build_multi_objective()` — строит взвешенную сумму с нормализацией.
        - 4 аккумулятора: `setup_sum`, `underload_sum`, `cooling_slow_count`, `tardiness_sum`.
    - 5 компонентов целевой функции:
        - `makespan` — общее время (мин).
        - `setup` — сумма переналадок (мин).
        - `underload` — сумма недогрузки реакторов (кг).
        - `cooling_slow` — число замедленных охлаждений (шт).
        - `tardiness` — сумма просрочек `due_date` (мин).
    - Нормализация каждого компонента в `[0, PRECISION]` через `AddDivisionEquality`.
    - Обратная совместимость: если только `weight_makespan = 1.0`, остальные = 0 — работает как single-objective.
    - `SettingsPage.tsx` — новая категория «Оптимизация» с 5 слайдерами.
    - Миграция `add_15.sql` — 5 настроек в категории `optimization`.

- **What-if сценарии.**
    - Таблица `whatif_scenario` (миграция `add_16.sql`).
    - Новый модуль `backend/app/scheduler/whatif.py` — `WhatIfRunner`:
        - `create_scenario`, `get_scenario`, `list_scenarios`, `update_scenario`, `delete_scenario`.
        - `run_scenario` — запуск (async через BackgroundTasks).
        - `compare` — сравнение base vs result.
        - `_apply_changes` — оркестрация применения изменений.
        - `_apply_shift_mode`, `_apply_capacity_changes`, `_apply_order_changes`, `_apply_calendar_changes`.
        - `_compute_metrics` — 6 метрик для сравнения.
    - Архитектура 2 транзакций:
        - Транзакция №1 (rollback): применяем изменения + запускаем scheduler → откат.
        - Транзакция №2 (commit): сохраняем результат через `ScheduleSaver` → commit.
    - 7 эндпоинтов API `/api/v1/whatif` (создать, список, один, обновить, удалить, запустить, сравнить).
    - Async запуск: `POST /run` возвращает `202 Accepted` сразу, расчёт в `BackgroundTasks`.
    - 7 типов изменений: `add_order`, `cancel_order`, `change_qty`, `change_due_date`, `shift_mode`, `resource_capacity`, `calendar_events` (add/remove).
    - UI `/whatif` (`WhatIfPage.tsx`):
        - AgGrid со списком сценариев.
        - Диалог создания/редактирования с JSON-редактором.
        - 5 кнопок-шаблонов (Режим смен, +Заказ, +Capacity, Авария Р4, Полный пример).
        - Polling статуса `RUNNING` каждые 3 секунды.
        - Диалог результата с таблицей метрик и Δ.
        - Кнопка «Открыть план» → переход на `/gantt?version_id=...`.
        - Кнопка удаления (🗑) для всех статусов кроме `RUNNING`.
    - Rollback гарантирован: `shift_mode`, `capacity`, `orders`, `calendar_events` не меняются в БД после what-if.

- **Архитектурные патчи Итерации 12.**
    - `DataLoader` + `ProductionScheduler` принимают `session` извне.
    - `ScheduleSaver` принимает `session` (не делает commit при `_owns_session=False`).
    - `shift_regenerator` — `flush()` вместо `commit()` + `AT TIME ZONE 'Europe/Moscow'`.
    - `settings.py` — явный `commit()` после `regenerate_shifts`.
    - `whatif.py` — 2 транзакции без явного `begin()`.

- **Тесты.**
    - 45 новых тестов в `test_whatif.py`.
    - Всего 321 тестов зелёные.

#### Итерация 13.3 — Аудит (объединённый журнал событий)

- Объединённый журнал событий для аудита действий пользователей.
- Единая точка входа для истории изменений планов, справочников, настроек.
- 4 источника:
    - `material_stock_log` — изменения остатков материалов.
    - `reschedule_log` — перепланирования.
    - `lab_analysis_log` — лабораторные блокировки.
    - `cz_scan_log` — сканы Честного Знака.
- API `/api/v1/audit`:
    - `GET /log` — объединённый журнал с фильтрами.
    - `GET /stats` — счётчики по источникам за период.
    - `GET /sources` — список источников.
- UI `AuditPage.tsx` — страница аудита с группировкой по дням.
- Фильтры синхронизируются с URL.

### Changed

- Solver: OPTIMAL за 7–25 секунд (what-if).
- Версия проекта: `3.0.0` → `4.0.0`.

---

## [3.0.0]

Итерации 5–11.

### Added

#### Итерация 5 — Лаборатория и блокировки

- Поля в `batch`: `is_lab_blocked`, `lab_status`, `lab_block_reason`, `lab_blocked_at`, `lab_blocked_by`.
- Таблица `lab_analysis_log` — журнал всех проверок лаборатории.
- Модуль `lab.py` — 7 эндпоинтов API:
    - `GET  /api/v1/lab/pending`.
    - `GET  /api/v1/lab/batch/{id}`.
    - `GET  /api/v1/lab/batch/{id}/log`.
    - `POST /api/v1/lab/batch/{id}/block`.
    - `POST /api/v1/lab/batch/{id}/unblock`.
    - `POST /api/v1/lab/batch/{id}/approve`.
    - `POST /api/v1/lab/batch/{id}/request`.
- Планировщик исключает заблокированные партии из расписания.
- `build_routing(truncate_after_lab=True)` — обрезка цепочки после lab-операции.
- UI `ShiftPage.tsx`: индикатор блокировки, кнопки блокировки/разблокировки.
- UI `GanttPage.tsx`: 🔒 красная рамка + фильтр «Только заблокированные».
- Роли `LAB`, `MASTER`, `ADMIN` имеют право блокировать партии.

#### Hotfix Итерации 5

- **Hotfix #1 — деактивация старых версий плана** (`saver.py`): при создании новой версии все старые деактивируются (`is_active = FALSE`).
- **Hotfix #2 — фильтрация по `schedule_version_id`** (`shift.py`, `gantt.py`): добавлен параметр `version_id`.
- **Hotfix #3 — таймзона в `by-date`** (`shift.py`): сравнение по UTC-дате.
- **Hotfix #4 — `is_lab_blocked` в Ганте** (`gantt.py`): добавлены `LEFT JOIN batch` и поля `is_lab_blocked`, `lab_status`, `lab_block_reason`.
- Миграция данных `fix_versions_hotfix.sql` — деактивирует все старые версии.

#### Итерация 6 — Люди как ресурс

- 4 пула операторов в `resource_pool`:
    - `REACTOR_OPERATOR` — 3 аппаратчика на 4 реактора.
    - `LINE_OPERATOR` — 2 оператора на 3 линии розлива.
    - `MANUAL_OPERATOR` — 1 оператор ручной станции (LINE_3).
    - `LAB` — 1 лаборант.
- Колонка `scheduled_task.operator_pool`.
- Колонка `resource_pool.updated_at`.
- UNIQUE-констрейнт `resource_pool (organization_id, type)`.
- `AddCumulative` для каждого пула.
- Модуль `plugins.py` — `OperatorPoolConstraint` + `LabConstraint` + `CoolingZoneConstraint`.
- Модуль `routing.py` — назначение пула для каждого шага.
- API `/api/v1/personnel` — 4 эндпоинта.
- Алгоритм `peak_concurrent` — метод «заметающей прямой».
- UI страница «Персонал».
- Feature-флаги `enable_operator_pools`, `enable_manual_station`.

#### Итерация 7 — Охлаждение с деградацией

- Миграция `add_10.sql` — feature-флаг + коэффициент.
- Миграция `add_10b.sql` — колонка `scheduled_task.cooling_mode`.
- Настройки в `organization_settings`:
    - `enable_cooling_degradation` = `true`.
    - `cooling_degradation_factor` = `1.3`.
    - `cooling_zone_capacity` = `2`.
- Модель деградации в `core.py`:
    - Для каждой cooling-задачи создаются два взаимоисключающих интервала: `fast_interval` и `slow_interval`.
    - `b_slow_i = 1 ⟺ ∃ j ≠ i: cooling_j пересекается с cooling_i`.
- `CoolingDegradationConstraint` в `plugins.py`.
- `scheduled_task.cooling_mode` сохраняется (`fast` | `slow` | `NULL`).
- API `/api/v1/gantt/` возвращает `cooling_mode`.
- Excel-экспорт содержит колонку «Режим охлаждения».
- Advisor выдаёт `COOLING_DEGRADATION`.
- UI `GanttPage.tsx`: 🟠 оранжевая пунктирная рамка, иконка `⏳`, бейдж, легенда, чип статистики, фильтр.
- UI `ShiftPage.tsx`: чип «Замедленное охлаждение ×1.3», оранжевая подсветка.
- UI `PersonnelPage.tsx`: пул `COOLING_ZONE` (и `BOILER`).

#### Hotfix Итерации 7

- Исправлена модель деградации в `core.py`: `b_slow` жёстко связан с фактическим пересечением интервалов.
- `CoolingDegradationConstraint` больше не делает `AddNoOverlap(fast_intervals)`.

#### Итерация 8 — Честный Знак и интеграции

- Миграция `add_11.sql`:
    - Поля в `batch`: `cz_marked_qty`, `cz_last_scan_at`, `cz_status`.
    - Таблица `cz_scan_log`.
    - Feature-флаг `enable_cz_integration = true`.
    - Настройки: `cz_completion_threshold`, `cz_api_key`, `enable_cz_auto_close`.
- Модуль `scheduler/cz.py`:
    - `resolve_batch_for_scan()`.
    - `compute_planned_qty()`.
    - `recalc_batch_cz_status()`.
    - `get_batch_progress()`.
- API `/api/v1/cz` — 7 эндпоинтов.
- Идемпотентность: `UNIQUE (organization_id, cz_code)` + `ON CONFLICT DO NOTHING`.
- Порог завершения: `cz_completion_threshold = 0.95`.
- Advisor `CZ_INCOMPLETE` (WARNING).
- UI `CzPage.tsx` — отдельная страница.
- UI `ShiftPage.tsx` — индикатор ЧЗ на задачах слива.
- UI `GanttPage.tsx`: чип статистики, фильтр, иконка `📷`, синяя пунктирная рамка.
- UI `MainLayout.tsx`: пункт меню «Честный Знак».

#### Итерация 9 — Рефакторинг, реальное перепланирование, drag-and-drop

- `rescheduler.py` больше не клонирует задачи — запускает `ProductionScheduler.build_schedule()` заново.
- Изменения применяются к входным данным: `BREAKDOWN` → `calendar_event`, `QTY_CHANGE` → `batch.volume_kg`, `DELAY` → сдвиг `planned_start` + `is_pinned = TRUE`.
- Гибридная логика pinned.
- Fallback: если solver не нашёл решение с pinned — пробует без них.
- Новая версия получает `parent_version_id = from_version_id`.
- Новый эндпоинт `PUT /api/v1/schedule/task/{id}/move`.
- Drag-and-Drop на диаграмме Ганта.
- Удалён мёртвый код `PLUGIN_MANAGED_RESOURCE_TYPES`.
- Единая функция `find_shift_id_for_time` в `shifts.py`.
- `REACTOR_OPERATOR.capacity` исправлен на 3 (по ТЗ).

#### Итерация 10 — Календарная постобработка и разбиение длинных задач

- Новый модуль `backend/app/scheduler/calendar_postprocess.py`.
- Календарные ограничения убраны из CP-SAT — постпроцессор сдвигает задачи в рабочие окна.
- Топологическая сортировка задач по зависимостям.
- Учёт `NoOverlap` при размещении.
- Рабочие окна строятся из смен минус события календаря.
- Результат: `overlaps_after = 0`, `dependency_violations = 0`.
- Разбиение длинных `LINE_FILL` на подзадачи.
- Порог зависит от `shift_mode`: `1x8`/`3x8` → 360 мин, `2x12` → 600 мин.
- Миграция `add_12.sql` — колонка `scheduled_task.operation_name`.
- `ScheduleBuildRequest.horizon_hours` по умолчанию: `720`.
- `ScheduleBuildRequest.timeout_seconds` по умолчанию: `600`.

#### Итерация 11 — Режимы смен, централизованные настройки, финальная полировка

- Новый модуль `backend/app/scheduler/shift_regenerator.py`.
- `get_intervals_for_mode(mode)`.
- `regenerate_shifts(session, org_id, mode, date_from, date_to, reset_shift_ids=True)`.
- Вызов из `POST /api/v1/settings/shift-mode`.
- Миграция `add_13.sql` — таблица `app_settings`.
- Новый модуль `backend/app/scheduler/settings_reader.py`.
- `data_loader.py`: `_load_org_settings` → `_load_app_settings`.
- Все API-модули переведены на `settings_reader`.
- `core.py` читает `shift_mode` и `allow_weekend_work` из `app_settings`.
- Миграция `add_14.sql` — настройка `allow_weekend_work`.
- `shift.py` (`by-date`): сравнение по МСК-дате.
- UI `SettingsPage.tsx` — страница настроек с группировкой по категориям.
- UI `SchedulePage.tsx` — читает `horizon_hours` и `timeout_seconds` из `app_settings`.
- UI `ShiftPage.tsx` — фикс UX мастера смены.
- UI `PlainContext.tsx` — фикс цикла ре-рендера.
- UI `GanttPage.tsx` — pan + zoom + drag одновременно.
- UI `index.css` — курсоры для разных зон диаграммы.

### Changed

- Версия проекта: `2.0.0` → `3.0.0`.
- Solver: OPTIMAL за ~78 секунд.
- Makespan: 12526 мин (~8.7 дня).
- 268 тестов зелёные.

### Fixed

- Исправлена модель деградации охлаждения.
- Исправлены Hotfix #1–#4 Итерации 5.
- Устранён цикл ре-рендера в `PlainContext.tsx`.
- Восстановлен pan диаграммы Ганта.

---

## [2.0.0]

Итерации 2–4.

### Added

#### Итерация 2 — Материальные ограничения и Advisor

- Модуль `materials.py` — расчёт потребности в сырье по всем партиям.
- Модуль `advisor.py` — типы подсказок:
    - 🔴 `MATERIAL_SHORTAGE` — дефицит сырья.
    - 🟡 `UNDERLOAD` — неполная загрузка реактора.
    - 🔵 `ROUTE_MISMATCH` — VIA_TANK без танка.
    - 🔵 `EQUIPMENT_GAP` — простои оборудования.
- Модуль `feasibility.py` — оценка исполнимости плана.
- API: `GET /api/v1/schedule/advice`, `POST /api/v1/schedule/feasibility`.
- UI: панель Advisor с фильтрацией по severity.
- Обнаружение дефицита отдушки (150 кг) и соли (1500 кг).

#### Итерация 3 — Сменное планирование и РМ мастера

- Таблица `shift` — смены (одна в день, 08:00–20:00).
- Поля в `scheduled_task`: `shift_id`, `actual_qty`, `material_load_at`, `status`.
- Модуль `shifts.py` — работа со сменами.
- API `shift.py` — 5 эндпоинтов.
- Frontend `ShiftPage.tsx` — рабочее место мастера.
- Пункт меню «Мастер смены».
- Все 282 задачи привязаны к сменам.

#### Итерация 4 — Перепланирование

- Модуль `rescheduler.py` — перепланирование с учётом изменений.
- Типы изменений: `DELAY`, `BREAKDOWN`, `QTY_CHANGE`, `MANUAL`.
- Закрепление задач (`is_pinned`) и заморозка до `frozen_before`.
- Журнал перепланирований `reschedule_log`.
- API `reschedule.py`:
    - `POST /api/v1/schedule/reschedule`.
    - `GET /api/v1/schedule/compare`.
    - `PUT /api/v1/schedule/task/{id}/pin`.
- UI: диалог перепланирования в `SchedulePage.tsx`.
- Сценарий «Аварийная остановка Р4 (25–28.09)».

### Changed

- Версия проекта: `1.0.0` → `2.0.0`.

---

## [1.0.0]

Итерации 0–1.

### Added

#### Итерация 0 — Фундамент

- Эталонный тест-кейс из ТЗ (Раздел 4).
- Централизованная конфигурация через `organization_settings`.
- Feature-флаги для поэтапного внедрения.
- Structured logging планировщика.
- CI на GitHub Actions.

#### Итерация 1 — Цепочки рабочих центров

- Модуль `routing.py` — построение цепочек операций.
- Двухресурсные операции (`linked_equipment_id`).
- Слив: `реактор → линия` (DIRECT) или `реактор → танк → линия` (VIA_TANK).
- Замыв реактора после слива (в конце цепочки).
- `NoOverlap` по каждому ресурсу отдельно.
- Оптимизация setup-ограничений (270 вместо 9714).
- Корректный расчёт длительности слива (кг ПФ → бутылки → минуты).
- Makespan ~553 ч (было 1856 ч).

### Changed

- Первый релиз проекта.

---

## Типы изменений

- **Added** — новая функциональность.
- **Changed** — изменения в существующей функциональности.
- **Deprecated** — функциональность, которая будет удалена.
- **Removed** — удалённая функциональность.
- **Fixed** — исправления багов.
- **Security** — исправления уязвимостей.

---

## Ссылки

- [README.md](README.md) — основная документация.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура.
- [docs/ROADMAP.md](docs/ROADMAP.md) — план развития.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — руководство разработчика.
- [CONTRIBUTING.md](CONTRIBUTING.md) — как внести вклад.