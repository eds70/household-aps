# APS Production Scheduler — Контекст чата (v4.10.2, Итерации 0–21)

## 0. Статус документа

- **Версия проекта:** 4.10.2 (patch от 2026-10-13).
- **Функциональная версия:** 4.10.0 (Итерации 17.1–17.4).
- **Последняя завершённая итерация по ROADMAP:** 20 — Календарные настройки и Тесты.
- **Дополнительно завершено:**
  - **Итерация 17.5 — Черновики** (план-контейнер + песочница).
  - **Итерация 21 (часть 1)** — UI-долг Advisor 2.0: бейдж 🧠 в тулбаре Ганта и чекбокс `allow_interrupt_line_fill`.
  - **Итерация 21.3 (часть)** — сохранение `advisor_note` в БД (минимальный набор проверок) — **В РАБОТЕ**.
  - **Итерация 21.3 (фокус на задаче/партии из «Истории сдвигов») — ОТЛОЖЕНА** (см. раздел «Известные баги / грабли»).
- **Тесты:** 789 passed, 0 skipped.

> **Правило ведения:** при завершении каждой итерации обновлять этот файл. При расхождении с README/ROADMAP — приоритет у README/ROADMAP (они публичные).

---

## 1. Главная концепция

### План = контейнер (Итерация 17.5, ✅ подтверждено)
Пользователь создаёт план один раз, нажимает «Построить» — результат **пишется в тот же план** (перезапись задач и снапшотов). Новых версий не появляется.

**Реализация:**
- `backend/app/scheduler/saver.py` — `ScheduleSaver(version_id=...)`. `_do_save` — ветки A (rewrite) и B (create). `_REWRITE_CLEANUP_TABLES` — 7 таблиц (`scheduled_task`, `equipment_snapshot`, `product_snapshot`, `operation_snapshot`, `calendar_snapshot`, `recipe_snapshot`, `recipe_item_snapshot`). `advisor_note` и `plan_settings` **не трогаются**.
- `backend/app/api/v1/schedule.py` — `ScheduleBuildRequest.version_id`. `POST /build` берёт `version_id` из body. `_prepare_rewrite` — снятие `is_active` с остальных, чистка, `is_active=TRUE`, `created_at=NOW()`.

### Черновик = песочница для правок (Итерация 17.5, ✅ подтверждено)

Кнопка ✏️ (в шапке `MainLayout`) открывает `PlanSettingsWizard` в режиме `asDraft=true`. Создаётся **черновик** (`is_draft = TRUE`, `parent_version_id = оригинал`). Пользователь редактирует задачи на Ганте, вносит факты в смене — не затрагивая оригинал. В шапке появляются **💾 (Утвердить)** и **✖ (Отменить)**.

**Реализация:**
- `backend/app/api/v1/schedule.py`:
  - `POST /versions/{id}/draft` — идемпотентный (`create_draft_from_version`). Если черновик уже есть — возвращает его. Копирует **только снапшоты** (5 таблиц + `recipe_item_snapshot`) и `plan_settings`. **`scheduled_task` не копируются.**
  - `POST /versions/{id}/commit` — `is_draft=FALSE`, `is_active=TRUE`, имя очищается от префикса `📝 Черновик: `, родитель архивируется.
  - `_copy_plan_settings` — все поля, кроме `default_value` (которого в `plan_settings` нет). `ON CONFLICT (schedule_version_id, setting_key) DO NOTHING`.
  - `GET /versions` — `include_drafts` (default `false`) скрывает черновики.
- `frontend/src/components/layout/MainLayout.tsx` — кнопки ✏️/💾/✖, `handleEditClick`, `handleCommitDraft`, `handleDiscardDraft`, `handleWizardSaved`.
- `frontend/src/pages/PlanSettingsWizard.tsx` — пропс `asDraft`, кнопка «Отменить» (outlined, справа, с разделителем), при `asDraft` вызывается `scheduleApi.createDraft`.

**⚠️ Критический нюанс: черновик пустой до build.**
`create_draft_from_version` копирует **только снапшоты** и `plan_settings` — **без `scheduled_task`**. Задачи появляются после «Создать черновик и построить» / «Сохранить и построить» → `scheduleApi.build({ version_id: draftId })` → `ScheduleSaver(version_id=draftId)` → ветка A (rewrite). Если нужен «клон с задачами» — использовать `POST /versions` с `parent_version_id` (создаёт обычный план-клон со снапшотами, но тоже **без задач**) + build.

**Правила:**
- ❌ Не открывать `PlanSettingsWizard` из ✏️ как обычно — только с `asDraft=true`.
- ❌ Не создавать «черновик от черновика» (`build` в черновик → 400).
- ❌ Не удалять черновик сразу после создания.
- ❌ Не ожидать, что черновик сразу содержит задачи — их там нет до build.

### ⚠️ Глобальные справочники vs Данные плана

**Глобальные справочники** — редактируются **всегда**, независимо от плана. Изменения в них **не** привязаны к черновику. Чтобы изменения попали в план, нужно **пересчитать** план (обновятся снапшоты).

| Сущность | Таблица | Привязка к плану |
|---|---|---|
| **Продукты** | `product` | Глобальная. Снапшот `product_snapshot`. |
| **Оборудование** | `equipment` | Глобальная. Снапшот `equipment_snapshot`. |
| **Материалы** | `material`, `material_stock` | Глобальная. **Не привязана к плану вообще.** |
| **Тех. карты** | `operation_template` | Глобальная. Снапшот `operation_snapshot`. |
| **Рецепты** | `recipe`, `recipe_item` | Глобальная. Снапшоты `recipe_snapshot`, `recipe_item_snapshot` (Итерация 17.2). |
| **Календарь** | `calendar_event` | Глобальная. Снапшот `calendar_snapshot`. |
| **Персонал** | `resource_pool` | Глобальная. |
| **Заказы** | `production_order` | Глобальная. |
| **Сканы ЧЗ** | `cz_scan_log` | Глобальная. |

**UI-правила для глобальных справочников:**
- Кнопка «Добавить», редактирование ячеек, «Удалить» — **всегда активны**.
- Если открыт план (активный или черновик) — показывать баннер «Вы редактируете глобальный справочник. Чтобы изменения попали в план, нажмите „Построить план“».
- **НЕ использовать** `isReadOnly = currentVersionId !== null`.
- **НЕ блокировать** редактирование на основе `localEditMode`.

### ⚠️ Отмена унификации vis-timeline (Итерация 62 — историческое решение)
Попытка вынести `vis-timeline` в общий `BaseTimeline` и перевести на него `GanttPage` **отменена и откачена**. Причины:
1. `GanttPage` имеет сложную логику зависимостей (SVG), батчей, мини-карты и синхронизации скролла.
2. Конфликт React и `vis-timeline` при SVG-оверлее → `insertBefore` и белый экран.
3. Перевод требует переписывания `useGanttTimeline` и `useGanttDependencies` — высокий риск регресса.

**Текущее состояние:**
- `GanttPage` работает на **своей старой архитектуре** (`useGanttTimeline` + `containerRef`).
- `EquipmentPage` переведён на `BaseTimeline` (там нет связей).
- Связи в `GanttPage` — через самописный `useGanttDependencies` (математический hover, ортогональные линии).
- **НЕ ПЫТАТЬСЯ** снова объединять `GanttPage` и `BaseTimeline` без острой необходимости.

### Оборудование (EquipmentPage) — особенности
- Справочник и ремонты (`calendar_event`) — **глобальные**. Загружаются без `version_id`.
- **Drag & Drop ремонтов** — самописный (`pointerdown`/`pointermove`/`pointerup` на `window`), встроенный `editable` у `vis-timeline` отключён.
- Контейнер таймлайна скрыт (`visibility: hidden`) до `redraw()` + 150 мс — иначе «нулевые размеры».
- Плашка «Сейчас идёт / Через N дней» в карточке ремонта.

**Данные плана** — привязаны к `schedule_version`, редактируются **только в черновике**:

| Сущность | Таблица | Редактирование |
|---|---|---|
| **Задачи плана** | `scheduled_task` | ✅ Только в черновике (через `localEditMode`). |
| **Настройки плана** | `plan_settings` | ✅ Через `PlanSettingsWizard`. |

**UI-правила для данных плана:**
- `GanttPage` — drag, resize, pin, move: `isReadOnly = !localEditMode`.
- `ShiftPage` — внесение факта, блокировка лабой: `isReadOnly = !localEditMode`.
- `SchedulePage` — «Построить план», «Пересохранить» доступны всегда.

### Клонирование плана (через мастер)
`PlanSettingsWizard(mode="create", baseVersionId=...)` — создаёт обычный план-клон (не черновик) с настройками и снапшотами родителя. Реализация: `POST /versions` с `parent_version_id` → копируются снапшоты (5 таблиц + `recipe_item_snapshot`) + `plan_settings`. **Задачи не копируются** — нужен build.

---

## 2. Завершённые итерации (по ROADMAP)

### Базовые (0–11)
CP-SAT, цепочки РЦ, материальные ограничения + Advisor, сменное планирование, перепланирование, лаборатория, люди-ресурсы, охлаждение с деградацией, ЧЗ, календарная постобработка, режимы смен, `app_settings`.

### 12–16
- **12** — multi-objective, what-if.
- **13.3** — аудит (4 источника).
- **13.14** — `plan_settings`.
- **13.15** — снапшоты при создании плана.
- **13.16** — `DraggableDialog`.
- **13.17** — каскадный сдвиг задач.
- **13.18** — улучшения Ганта (`is_pinned`).
- **13.19** — флаг `planDirty`.
- **13.20** — `RecalcProgressDialog`.
- **13.21** — архивация версий (`is_archived`, `auto_archive_on_recalc`).
- **14.1** — режимы отображения Ганта (`groupByMode`).
- **14.2** — редактирование на Ганте (`localEditMode`).
- **15.1** — встроенная справка (15 статей).
- **15.2** — контекстные подсказки (`help_hint`, 8 шт).
- **15.3** — туториал (`react-joyride`, 3 тура).
- **15.4** — FAQ (15 статей, всего 31).
- **15.5** — CRUD статей справки в UI (ADMIN).
- **15.6** — `collect_project.py`, `AI_WORKFLOW.md`.
- **15.7** — `check_docs.py`.
- **16** — аудит 2.0 (фильтры, дашборд, saved views, Excel).

### 17.1–17.5
- **17.1** — inline-edit рецептур.
- **17.2** — версионирование рецептур (`recipe_snapshot`, `recipe_item_snapshot`, миграция `add_29`).
- **17.3** — `planning_start_date` в UI.
- **17.4** — копирование UUID версии плана из UI.
- **17.5 — Черновики (план-контейнер + песочница)** ✅
  - `saver.py` — `version_id`, `_do_save` (ветки A/B), `_REWRITE_CLEANUP_TABLES` (7 таблиц), `_prepare_rewrite`.
  - `schedule.py` — `ScheduleBuildRequest.version_id`, `create_draft_from_version` (идемпотентный, копирует только снапшоты + `plan_settings`), `commit_draft`, `_copy_plan_settings`, `include_drafts`.
  - `MainLayout.tsx` — ✏️/💾/✖, `handleCommitDraft`, `handleDiscardDraft`, `handleWizardSaved`.
  - `PlanSettingsWizard.tsx` — `asDraft`, кнопка «Отменить».
  - **Черновик пустой до build** — задачи появляются только после `build({ version_id: draftId })`.

### 18 — Advisor 2.0
- `advisor_note` (миграция `add_31`), `schedule_version.has_advisor_notes`.
- `GET /schedule/advice` читает `postprocess_result` из БД.
- Новые проверки: `OVER_HORIZON`, `SHIFTED_TASKS`, `SKIPPED_BATCHES`, `OVERLAPS_AFTER`.
- `GET /schedule/advisor-notes`.
- UI: иконка 🧠 в «Истории планов», модалка «История сдвигов» (AG Grid).
- `routing.py`: валидация `equipment_capability`.
- `data_loader.py` + `calendar_postprocess.py`: `allow_interrupt_line_fill` (бэкенд).

### 19 — Оптимизация заказов и Архивация
- `POST /api/v1/orders/{id}/auto-split-optimized` — `greedy_makespan` (защита от дублей 409).
- UI: кнопка «Оптимально распределить» в `OrdersPage.tsx`.
- UI: «Архивировать» / «Очистить архив» в `SchedulePage.tsx`.
- `PUT /api/v1/schedule/versions/{id}/archive`.

### 20 — Календарные настройки и Тесты
- `test_calendar_postprocess_v2.py` (3 теста: наложения, зависимости, сдвиг).
- `_find_free_slot` — фикс для задач, не влезающих в окно.
- Чекбокс `allow_interrupt_line_fill` в `PlanSettingsWizard` (Итерация 20/21).

### 21 (часть 1) — UI-долг Advisor 2.0
- **21.1** — Чекбокс `allow_interrupt_line_fill` в `PlanSettingsWizard` (работает автоматически из `settings.py`).
- **21.2** — Бейдж 🧠 в тулбаре Ганта (`GanttToolbar.tsx` + `advisorApi.getAdvice` в `GanttPage.tsx`).
- **21.3 (ОТЛОЖЕНО)** — Клик по строке в «Истории сдвигов» → переход на Гант с зумом и подсветкой. **Не работает** (см. «Известные баги / грабли»). Код убран из `GanttPage.tsx`.

### ⚠️ Итерация 21.3 (fix advisor_note) — В РАБОТЕ
**Проблема:** таблица `advisor_note` пуста, хотя в `advisor.py` есть проверки. «История сдвигов» показывает пустой грид (пагинация «20 из 276» есть, но данных нет).

**Решение (минимальное):** сохранять `advisor_note` только для тех проверок, которые зависят от `result` и `postprocess_result`:
- `SHIFTED_TASKS` (из `result.calendar_postprocess.shifted_details`)
- `OVER_HORIZON` (из `result.tasks`)
- `SKIPPED_BATCHES` (из `result.skipped_batches`)
- `OVERLAPS_AFTER` (из `result.calendar_postprocess`)

**Что НЕ сохраняем (пока):** `MATERIAL_SHORTAGE`, `UNDERLOAD`, `COOLING_DEGRADATION`, `CZ_INCOMPLETE`, `EQUIPMENT_GAP`, `ROUTE_MISMATCH` — их можно добавить позже, но для этого нужен `DataLoader` и полные данные (batches, products, equipment, recipes, materials). Это отдельная задача.

**Реализация:** в `build_schedule` (после `save_schedule`) добавить блок `try/except`:
1. Вызвать `check_over_horizon(result)`, `check_shifted_tasks(postprocess_result)`, `check_skipped_batches(skipped_batches)`, `check_overlaps_after(postprocess_result)`.
2. `DELETE FROM advisor_note WHERE schedule_version_id = :vid`.
3. `INSERT` новые заметки.
4. `commit` (или `rollback` при ошибке).

### Patch-релизы
- **4.10.1** — партии ГП-заказов привязываются к родительскому ПФ (`_resolve_batch_product_id`, `COALESCE(parent_pf_id, product_id)`). `BatchCreate` без `product_id`. WARNING в `routing.py` при пустых операциях.
- **4.10.2** — `POST /cz/scan` без JWT (убран `Depends(get_current_org_id)`), `org_id = DEFAULT_ORG_ID`. Мульти-тенантность ЧЗ — BACKLOG 5.8.

---

## 3. Что нужно сделать дальше

### Итерация 21 (часть 2) — 21.4: Префикс партии и разделители подзадач на Ганте (⏳)
- В имени задачи показывать `[5ce3] Слив...` (первые 4 символа от `batch_id`).
- Для задач с `(часть N/M)` — визуальные разделители (частично уже есть через `border-right: 2px dashed`).
- **Файлы:** `frontend/src/utils/ganttRenderItems.ts`.

### Итерация 21.3 (fix advisor_note) — В РАБОТЕ
**Цель:** заполнить `advisor_note` минимальным набором проверок (SHIFTED_TASKS, OVER_HORIZON, SKIPPED_BATCHES, OVERLAPS_AFTER). См. раздел 21.3 выше.

**Файл:** `backend/app/api/v1/schedule.py` (функция `build_schedule`).

**Проверка:**
```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT schedule_version_id, code, created_at FROM advisor_note ORDER BY created_at DESC LIMIT 10;"