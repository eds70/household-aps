-- ==========================================
-- SEED 26/2: СПРАВКА — FAQ (ГАНТ + СМЕНЫ)
-- ==========================================
-- 5 статей FAQ категории 'faq'.
-- Все — глобальные (organization_id = NULL).
--
-- Идемпотентна: ON CONFLICT (slug) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_article
(organization_id, slug, title, category, content_md, tags,
 display_order, is_published)
VALUES

-- ==========================================
-- 6. faq-move-pinned-task
-- ==========================================
(NULL,
 'faq-move-pinned-task',
 'Закреплённая задача не двигается — как открепить?',
 'faq',
 $md$# Закреплённая задача не двигается

**Категория:** FAQ

**Симптом:** На Ганте задача помечена **📌**, синяя рамка. Перетаскиваете — возвращается на место.

## Что значит «закреплена»

`is_pinned = TRUE` — задача **жёстко фиксирована** по времени. Solver не будет её двигать при пересчёте, и вручную перетащить нельзя.

**Важно:** длительность закреплённой задачи **менять можно** (тянуть за края). Запрещено только **перемещение**.

## Зачем это нужно

1. **Мастер смены** отметил задачу как начатую → она не должна «уезжать».
2. **Планировщик** вручную зафиксировал критичную задачу.
3. **Система** закрепила задачу после `DELAY` (сдвиг + `is_pinned = TRUE`).

## Как открепить

### Способ 1: Контекстное меню (быстро)

1. Правый клик на задаче.
2. Выбрать **«Открепить»**.
3. Иконка 📌 исчезнет.

### Способ 2: Через API

```bash
curl -X PUT http://localhost:8000/api/v1/schedule/task/{task_id}/pin \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_pinned": false}'
```

## Как найти все закреплённые

### Фильтр на Ганте

1. Тулбар → **🎛 Фильтры**.
2. Чекбокс **«📌 Только закреплённые»**.
3. Гант покажет только их.

### Через БД

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    st.id,
    st.operation_name,
    st.planned_start,
    st.planned_end,
    st.is_pinned
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = TRUE
  AND st.is_pinned = TRUE
ORDER BY st.planned_start;
"
```

## Массовое открепление

Если надо открепить все задачи сразу:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE scheduled_task
SET is_pinned = FALSE
WHERE schedule_version_id = (
    SELECT id FROM schedule_version
    WHERE organization_id = '00000000-0000-0000-0000-000000000001'
      AND is_active = TRUE
    LIMIT 1
);
"
```

**После этого — пересчитать план**, иначе solver не учтёт изменения.

## Связанные статьи

- [Редактирование задач на Ганте](/help/gantt-editing)
- [Пересчёт плана](/help/planning-recalculate)
- [Задача не двигается на Ганте](/help/faq-task-not-movable)$md$,
 '["faq", "гант", "pinned", "закреплена"]'::jsonb,
 60, TRUE),

-- ==========================================
-- 7. faq-old-version-not-archived
-- ==========================================
(NULL,
 'faq-old-version-not-archived',
 'Старая версия плана не архивируется',
 'faq',
 $md$# Старая версия не архивируется

**Категория:** FAQ

**Симптом:** Пересчитали план, ожидали, что старая версия уйдёт в архив — но она осталась в списке.

## Причины (по частоте)

### 1. Версия используется в what-if сценарии

**Самая частая причина.** Если старая версия является `base_version_id` или `result_version_id` сценария в статусе `DRAFT` или `RUNNING` — она **не архивируется**.

**Что делать:** после пересчёта в правом нижнем углу появляется снекбар **🟡 «Старая версия не архивирована»** со списком ID сценариев.

- Открыть **What-if** → запустить сценарий (перейдёт в `DONE`).
- Или удалить сценарий (только `DRAFT` или `FAILED`).
- Затем разархивировать вручную (см. ниже).

### 2. Настройка `auto_archive_on_recalc = false`

**Что делать:** проверить настройку:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'auto_archive_on_recalc';
"
```

Если `false` — включить:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE app_settings
SET setting_value = 'true'::jsonb, updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'auto_archive_on_recalc';
"
```

Или через `SettingsPage` → категория «Планирование» → чекбокс.

### 3. Миграция `add_23.sql` не применена

**Что делать:** проверить наличие колонки `is_archived`:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'schedule_version' AND column_name = 'is_archived'
);
"
```

Если `f` — применить миграцию:

```bash
docker cp backend/migrations/add_23.sql aps_postgres:/tmp/add_23.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_23.sql
```

## Разархивация вручную

Через UI:
1. Открыть **«Планирование»**.
2. Чекбокс **«Показать архивные»**.
3. Найти архивную версию (серая).
4. Кнопка **↩ Разархивировать**.

Через API:

```bash
curl -X PUT http://localhost:8000/api/v1/schedule/versions/{id}/unarchive \
  -H "Authorization: Bearer $TOKEN"
```

## Как найти причину автоматически

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.id,
    sv.name,
    sv.is_archived,
    (SELECT COUNT(*) FROM whatif_scenario ws
     WHERE (ws.base_version_id = sv.id OR ws.result_version_id = sv.id)
       AND ws.status IN ('DRAFT', 'RUNNING')) AS blocks_archive
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY sv.created_at DESC
LIMIT 10;
"
```

Если `blocks_archive > 0` — версия **не будет** архивирована.

## Связанные статьи

- [История планов](/help/planning-history)
- [What-if сценарии](/help/whatif-overview)
- [app_settings vs plan_settings](/help/settings-app-vs-plan)$md$,
 '["faq", "архив", "версия", "what-if"]'::jsonb,
 70, TRUE),

-- ==========================================
-- 8. faq-shift-mode-change
-- ==========================================
(NULL,
 'faq-shift-mode-change',
 'После смены режима смен задачи потеряли привязку',
 'faq',
 $md$# После смены режима смен задачи потеряли привязку

**Категория:** FAQ

**Симптом:** Переключили режим смен (`1x8` ↔ `3x8` ↔ `2x12`) на странице «Настройки». В **Мастере смены** — пустой список. В задачах `shift_id = NULL`.

## Причина — by design

При смене режима:
1. Старые смены **удаляются** из таблицы `shift`.
2. Создаются **новые** смены по новому режиму.
3. У всех задач `shift_id` **сбрасывается** в `NULL` — старые UUID невалидны.

Это происходит **автоматически** при смене режима. Об этом сообщает диалог-предупреждение.

## Что делать

**Пересчитать план.** После пересчёта задачи получат новые `shift_id`.

### Через UI

1. Открыть план на Ганте.
2. В тулбаре нажать **🔄 «Пересчитать»**.
3. Дождаться завершения (30–120 сек).
4. Открыть **Мастер смены** → задачи привязались к новым сменам.

### Через API

```bash
curl -X POST http://localhost:8000/api/v1/schedule/reschedule \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "from_version_id": "<VERSION_ID>",
    "reason": "MANUAL",
    "changes": {},
    "comment": "Пересчёт после смены режима смен"
  }'
```

## Проверка

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    COUNT(st.id) AS total_tasks,
    COUNT(st.shift_id) AS tasks_with_shift,
    COUNT(st.id) - COUNT(st.shift_id) AS tasks_without_shift
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
  AND sv.is_active = TRUE
GROUP BY sv.id, sv.name;
"
```

Если `tasks_without_shift > 0` — план не пересчитан после смены режима.

## Как избежать

**Планируйте смену режима в начале цикла** — например, перед созданием нового месячного плана. Тогда пересчёт займёт минимум времени, а не будет «вклиниваться» в активный план.

## Связанные статьи

- [Мастер смены](/help/shift-overview)
- [Пересчёт плана](/help/planning-recalculate)
- [app_settings vs plan_settings](/help/settings-app-vs-plan)$md$,
 '["faq", "смены", "shift_mode", "пересчёт"]'::jsonb,
 80, TRUE),

-- ==========================================
-- 9. faq-whatif-running
-- ==========================================
(NULL,
 'faq-whatif-running',
 'What-if сценарий завис в статусе RUNNING',
 'faq',
 $md$# What-if сценарий завис в RUNNING

**Категория:** FAQ

**Симптом:** What-if сценарий не завершается. Статус `RUNNING` держится часами. В UI — бесконечный спиннер.

## Причины

### 1. Solver реально работает

What-if расчёт занимает **7–25 секунд** (быстрее, чем обычный пересчёт). Но если сценарий сложный (`shift_mode = "3x8"` + `add_order` + capacity) — до **120 секунд**.

**Что делать:** подождать.

### 2. Timeout solver

Solver упирается в `timeout_seconds` (по умолчанию 600 сек = 10 минут). После этого вернёт `FEASIBLE` или `FAILED`.

**Что делать:** подождать 10 минут.

### 3. BackgroundTask упал

Скрипт фоновой задачи `_run_scenario_background` мог вылететь с ошибкой (например, `UndefinedColumnError`).

**Что делать:** проверить логи backend:

```bash
# Если backend запущен в терминале — смотреть вывод.
# Если в Docker:
docker logs <backend_container_name> --tail 100 | grep -i whatif
```

Искать:
- `[BG] Ошибка what-if ...` — фатальная ошибка.
- `[BG] what-if ...: завершён` — успех.

### 4. Backend перезагрузился

Если backend был перезапущен во время расчёта — BackgroundTask «потерялся», но статус в БД остался `RUNNING`.

**Что делать:** принудительно завершить сценарий:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE whatif_scenario
SET status = 'FAILED',
    comment = COALESCE(comment, '') || '\nЗавис в RUNNING — сброшено вручную',
    updated_at = NOW()
WHERE id = '<SCENARIO_ID>'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

После этого можно удалить сценарий и создать заново.

## Нельзя удалить сценарий в RUNNING

API возвращает `400` при попытке удалить `RUNNING` сценарий. Это защита от потери данных.

**Что делать:** дождаться завершения или сбросить статус вручную (см. выше).

## Как ускорить расчёт

- Уменьшить `timeout_seconds` через `POST /run` (тело: `{"timeout_seconds": 300}`).
- Убрать лишние изменения из сценария.
- Использовать `horizon_hours = 720`.

## Связанные статьи

- [What-if сценарии](/help/whatif-overview)
- [План получился FEASIBLE, а не OPTIMAL](/help/faq-plan-feasible-not-optimal)$md$,
 '["faq", "what-if", "running", "завис"]'::jsonb,
 90, TRUE),

-- ==========================================
-- 10. faq-cz-orphan-scan
-- ==========================================
(NULL,
 'faq-cz-orphan-scan',
 'Скан ЧЗ попал в «сироты» — что делать?',
 'faq',
 $md$# Скан ЧЗ попал в «сироты»

**Категория:** FAQ

**Симптом:** На странице **«Честный Знак»** в журнале сканов — записи с чипом **🔗 «Сирота»** (`batch_id = NULL`). Скан не привязан к партии.

## Почему так происходит

Камера ТС шлёт скан на `POST /api/v1/cz/scan` с полями `cz_code`, `line_code`, `scanned_at`. Система пытается сопоставить скан с партией по **труём правилам**:

1. **Явно передан `batch_id`** — используем его.
2. **Передан `task_id`** — берём `batch_id` из задачи.
3. **Fallback по `line_code` + `scanned_at`** (±2 часа) — ищем активную задачу `LINE_FILL` на этой линии.

Если ни один способ не сработал — скан остаётся «сиротой».

## Причины

### 1. Камера не передала `line_code`

Без `line_code` fallback не может найти партию.

**Что делать:** настроить камеру на передачу `line_code` в запросе.

### 2. Скан вне окна ±2 часа

Камера шлёт `scanned_at`, отличное от `planned_start` задачи `LINE_FILL` более чем на 2 часа. Возможно, бутылку отсканировали **до начала** или **после окончания** смены.

**Что делать:** вручную привязать (см. ниже).

### 3. Партия не запланирована

Скан пришёл, а соответствующей задачи `LINE_FILL` нет в БД (план не построен или не пересчитан).

**Что делать:** построить/пересчитать план, потом привязать.

## Как привязать вручную

### Через UI

1. Открыть **«Честный Знак»**.
2. В журнале найти скан-сироту (чип «Сирота»).
3. Кликнуть иконку **❓** (Сопоставить).
4. Ввести **UUID партии** (`batch_id`).
5. Нажать **«Сопоставить»**.

После этого:
- `batch_id` заполнен.
- `batch.cz_marked_qty` увеличится на 1.
- `batch.cz_status` пересчитается.
- Скан исчезнет из списка «сирот».

### Через API

```bash
curl -X POST http://localhost:8000/api/v1/cz/scan/{scan_id}/attach \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"batch_id": "<BATCH_UUID>", "comment": "Ручное сопоставление"}'
```

## Как найти UUID партии

На странице **«Заказы»** → развернуть заказ → скопировать ID партии.

Или через БД:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    b.id,
    p.code AS product_code,
    b.volume_kg,
    b.cz_status,
    b.cz_marked_qty
FROM batch b
JOIN product p ON p.id = b.product_id
WHERE b.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY b.id
LIMIT 20;
"
```

## Профилактика

- Убедиться, что камеры передают `line_code` и `camera_id`.
- Проверить, что время на камере **синхронизировано** с сервером (NTP).
- Окно ±2 часа можно расширить в коде `resolve_batch_for_scan` (не через настройки).

## Связанные статьи

- [Честный Знак](/help/cz-overview)
- [Скан ЧЗ не привязывается к партии](/help/cz-overview)$md$,
 '["faq", "честный знак", "cz", "сирота", "скан"]'::jsonb,
 100, TRUE)

    ON CONFLICT (slug) DO NOTHING;

COMMIT;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT COUNT(*) AS seeded
FROM help_article
WHERE slug IN (
               'faq-move-pinned-task',
               'faq-old-version-not-archived',
               'faq-shift-mode-change',
               'faq-whatif-running',
               'faq-cz-orphan-scan'
    );
-- Ожидаемо: 5