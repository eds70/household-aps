# APS Production Scheduler — Контекст чата (Итерация 61.5)

## 1. Главная концепция (РЕАЛИЗОВАНО И ПРОТЕСТИРОВАНО)

### План = контейнер
Пользователь создаёт план один раз, нажимает «Построить» — результат **пишется в тот же план** (перезапись задач и снапшотов). Новых версий не появляется.

### Черновик = песочница для правок
Кнопка ✏️ (в шапке `MainLayout`) открывает `PlanSettingsWizard` в режиме `asDraft=true`. Создаётся **черновик** (`is_draft = TRUE`, `parent_version_id = оригинал`). Пользователь редактирует задачи на Ганте, вносит факты в смене — не затрагивая оригинал. В шапке появляются **💾 (Утвердить)** и **✖ (Отменить)**.

**Правила:**
- ❌ Не открывать `PlanSettingsWizard` из ✏️ как обычно — только с `asDraft=true`.
- ❌ Не создавать «черновик от черновика».
- ❌ Не удалять черновик сразу после создания.

### ⚠️ КРИТИЧНО: Глобальные справочники vs Данные плана

**Глобальные справочники** — редактируются **всегда**, независимо от плана. Изменения в них **не** привязаны к черновику. Чтобы изменения попали в план, нужно **пересчитать** план (обновятся снапшоты).

| Сущность | Таблица | Привязка к плану |
|---|---|---|
| **Продукты** | `product` | Глобальная. Снапшот `product_snapshot` — только для чтения Ганта. |
| **Оборудование** | `equipment` | Глобальная. Снапшот `equipment_snapshot`. |
| **Материалы** | `material`, `material_stock` | Глобальная. **Не привязана к плану вообще**. |
| **Тех. карты** | `operation_template` | Глобальная. Снапшот `operation_snapshot`. |
| **Рецепты** | `recipe`, `recipe_item` | Глобальная. Снапшот `recipe_snapshot`. |
| **Календарь** | `calendar_event` | Глобальная. Снапшот `calendar_snapshot`. |
| **Персонал** | `resource_pool` | Глобальная. |
| **Заказы** | `production_order` | Глобальная. |
| **Сканы ЧЗ** | `cz_scan_log` | Глобальная. |

**UI-правила для глобальных справочников:**
- Кнопка «Добавить», редактирование ячеек, «Удалить» — **всегда активны**.
- Если открыт план (активный или черновик) — показывать баннер «Вы редактируете глобальный справочник. Чтобы изменения попали в план, нажмите „Построить план“».
- **НЕ использовать** `isReadOnly = currentVersionId !== null`.
- **НЕ блокировать** редактирование на основе `localEditMode`.
- **Асинхронность загрузки:** Справочники всегда грузятся глобально (без `version_id`), кроме страниц, которые явно работают со снапшотами.

### Оборудование (EquipmentPage) — Особенности
- Справочник и ремонты (`calendar_event`) — **глобальные**. Загружаются без `version_id`.
- **Drag & Drop ремонтов** реализован самописно (как в Ганте) через `pointerdown`/`pointermove`/`pointerup` на `window`, чтобы избежать багов `vis-timeline` в React.
- Встроенный `editable` у `vis-timeline` **отключен** (`editable: false`, `moveable: false`).
- Контейнер таймлайна скрыт (`visibility: hidden`), пока не отработает таймер 150мс и `redraw()`, чтобы избежать «нулевых размеров» при инициализации.
- В карточке ремонта выводится плашка «Сейчас идёт / Через N дней» (ближайшие события).

**Данные плана** — привязаны к `schedule_version`, редактируются **только в черновике**:

| Сущность | Таблица | Редактирование |
|---|---|---|
| **Задачи плана** | `scheduled_task` | ✅ Только в черновике (через `localEditMode`). |
| **Настройки плана** | `plan_settings` | ✅ Через `PlanSettingsWizard`. |

**UI-правила для данных плана:**
- `GanttPage` — drag, resize, pin, move задач: `isReadOnly = !localEditMode`.
- `ShiftPage` — внесение факта, блокировка лабой: `isReadOnly = !localEditMode`.
- `SchedulePage` — настройки: кнопки «Построить план», «Пересохранить» доступны всегда.

### Клонирование плана (через мастер)
`PlanSettingsWizard(mode="create", baseVersionId=...)` — создаёт обычный план-клон (не черновик) с настройками и снапшотами родителя.

## 2. Завершённые правки

### Backend
| Файл | Что сделано |
|---|---|
| `saver.py` | `__init__(version_id)`. `_do_save`: ветка A (перезапись) и B (создание). `_REWRITE_CLEANUP_TABLES` — 7 таблиц. |
| `models.py` | `ScheduleBuildRequest.version_id`. |
| `schedule.py` | `build_schedule` берёт `version_id` из body. `_copy_plan_settings` (все поля, **кроме `default_value`**; `ON CONFLICT DO NOTHING`). `create_schedule_version` — `parent_version_id`. `create_draft_from_version` — идемпотентный. `commit_draft` — переименовывает, делает активным, архивирует родителя. |

### Frontend (обновлено)
| Файл | Что сделано |
|---|---|
| `api.ts` | `scheduleApi.build` — `version_id`. `scheduleApi.createVersion` — `parent_version_id`. `scheduleApi.createDraft(versionId)`. Экспорт `api` (дефолт) для `MainLayout`. |
| `PlanSettingsWizard.tsx` | Пропс `asDraft`. Кнопка «Отменить» (outlined, справа). При `asDraft` создаёт черновик. |
| `MainLayout.tsx` | Кнопка ✏️ в шапке (для обычного плана) → `PlanSettingsWizard` (asDraft=true). Кнопки 💾/✖ (для черновика). `ConfirmDialog` с правильными `confirmText`/`cancelText`. Исправлена логика `handleWizardSaved` (прямой запрос версий вместо устаревшего стейта). |
| `SchedulePage.tsx` | Кнопки ✏️/💾/✖ **убраны** (переехали в `MainLayout`). `handleSaveSettings` сохраняет в `plan_settings`. `handleWizardSaved` не навигейтит на Гант. |
| `ConfirmDialog.tsx` | Иконка зависит от severity. `cancelText` по умолчанию «Закрыть», `confirmText` — «Подтвердить». |
| `ProductsPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, `editable: true` всегда, баннер про глобальный справочник. `loadProducts` без `version_id`. |
| `OperationsPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, баннер, `loadData` без `version_id`. |
| `RecipesPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, баннер. |
| `PersonnelPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, баннер. |
| `MaterialsPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, баннер. `loadMaterials` без `version_id`. |
| `EquipmentPage.tsx` | **✅ Глобальный справочник**: убран `isReadOnly`, баннер. **Таймлайн ремонтов оживлён** (самописный Drag&Drop как в Ганте, блокировка скролла холста, автоскролл к текущей дате). `loadEquipment` и `loadRepairs` — без `version_id`. |
| `CzPage.tsx` | ✅ `isReadOnly = currentVersionId !== null` (сканы ЧЗ — только просмотр без плана). Оставить как есть. |
| `OrdersPage.tsx` | ✅ Не привязан к плану. Оставить как есть. |
| `SettingsPage.tsx` | ✅ Глобальные настройки. Оставить как есть. |
| `ShiftPage.tsx` | ✅ Использует `localEditMode` (через `markPlanDirty`). Оставить как есть. |
| `GanttPage.tsx` | ✅ Использует `localEditMode`. Оставить как есть. |

## 3. Что нужно сделать дальше (Итерация 62)

1. **Тестирование полного цикла**: создание плана → правка справочника → пересчёт → проверка снапшота.
2. **Очистка мусорных черновиков** (SQL скрипты).
3. Разработка новых фич (согласно Roadmap).

## 4. Что присылать в новый чат

### Обязательно
1. **Этот файл** (`CHAT_CONTEXT.md`).
2. `frontend/src/pages/EquipmentPage.tsx` (эталон работы с глобальным справочником и таймлайном).
3. `frontend/src/pages/ProductsPage.tsx` (эталон простого глобального справочника).
4. `frontend/src/components/layout/MainLayout.tsx` (если продолжается работа над шапкой и черновиками).

## 5. Известные баги / грабли

- **CORS** при 500 — смотреть лог в IDEA.
- **`plan_settings` не содержит `default_value`** (только `app_settings`).
- **`ON CONFLICT DO NOTHING`** в `_copy_plan_settings` не перезаписывает существующие настройки черновика.
- **Черновики не удаляются** после commit (в `handleCommitDraft` `setPlan` меняет `is_draft` на `false`, но запись остаётся как обычный план). Это нормально — так задумано.
- **`vis-timeline` в `Allotment`**: при инициализации в контейнере с нулевой высотой ломаются обработчики мыши. Решение: инициализировать со скрытым контейнером (`visibility: hidden`) и задержкой 150мс, затем `redraw()` и `visibility: visible`. Для Drag использовать `pointerdown` на `window` с `e.stopPropagation()`.

## 6. Ключевые решения (не забыть)

- `plan_settings` — **источник истины** для `timeout_seconds`, `horizon_hours`, `planning_start_date`.
- `handleBuildSchedule` **не перезаписывает** `plan_settings` перед `build`.
- `PlanSettingsWizard` при `alsoBuild` передаёт `timeout_seconds` в `scheduleApi.build`.
- Перезапись (`build`): чистятся 7 таблиц. Не трогаем `advisor_note` и `plan_settings`.
- **Черновик = песочница для задач и настроек плана.**
- **Справочники (Products, Operations, Recipes, Personnel, Materials, Equipment) — ГЛОБАЛЬНЫЕ.** Редактируются всегда. Изменения в план попадают только после пересчёта.
- **Кнопки ✏️ / 💾 / ✖ — в шапке `MainLayout`**, не на `SchedulePage`.
- **`SchedulePage`** — только «Новый план», «Построить», «Сохранить настройки», «Перейти на Гант».
- **`ProductsPage`** — эталон простого глобального справочника.
- **`EquipmentPage`** — эталон глобального справочника с самописным Drag&Drop таймлайном ремонтов.