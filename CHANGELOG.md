# Changelog

Все значимые изменения проекта APS Production Scheduler документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added

#### Итерация 17.5 — Черновики (план-контейнер + песочница)

**Подтверждено по коду** (верификация 2026-10-25):
- `backend/app/scheduler/saver.py` — `ScheduleSaver(version_id=...)`,
  `_do_save` с ветками A (rewrite) и B (create),
  `_REWRITE_CLEANUP_TABLES` (7 таблиц), `_prepare_rewrite`.
- `backend/app/api/v1/schedule.py` — `create_draft_from_version`
  (идемпотентный), `commit_draft` (переименование + архивация родителя),
  `_copy_plan_settings` (все поля, кроме `default_value`;
  `ON CONFLICT DO NOTHING`). `ScheduleBuildRequest.version_id`,
  `build_schedule` берёт `version_id` из body.
- `frontend/src/components/layout/MainLayout.tsx` — кнопки ✏️ (для
  обычного плана), 💾/✖ (для черновика), `handleCommitDraft`,
  `handleDiscardDraft`, `handleWizardSaved`.
- `frontend/src/pages/PlanSettingsWizard.tsx` — пропс `asDraft`,
  кнопка «Отменить» (outlined, справа, с разделителем),
  при `asDraft` вызывается `scheduleApi.createDraft`.

**Поведение:**
- **План = контейнер.** `POST /build` с `version_id` перезаписывает
  существующий план (удаляет старые задачи и снапшоты, заливает новые,
  ставит `is_active=TRUE`). `advisor_note` и `plan_settings`
  **не трогаются**.
- **Черновик = песочница.** ✏️ в шапке `MainLayout` открывает
  `PlanSettingsWizard` с `asDraft=true` → `createDraft(parentId)`.
  Черновик создаётся **без `scheduled_task`** (копируются только
  снапшоты + `plan_settings`). Задачи появляются после
  «Создать черновик и построить» / «Сохранить и построить» →
  `scheduleApi.build({ version_id: draftId })` →
  `ScheduleSaver(version_id=draftId)` → ветка A (rewrite).
- **Утверждение.** 💾 → `POST /versions/{id}/commit`:
  `is_draft=FALSE`, `is_active=TRUE`, имя очищается от префикса
  `📝 Черновик: `, родитель архивируется (`is_archived=TRUE`).
- **Отмена.** ✖ → `DELETE /versions/{id}` → возврат к родителю
  (если есть) или `clearPlan()`.

**Ограничения:**
- Черновик **пустой до build** — задачи не копируются из родителя.
  Если нужен «клон с задачами» — использовать `POST /versions` с
  `parent_version_id` (создаёт обычный план-клон со снапшотами, но
  тоже без задач) + build.
- «Черновик от черновика» запрещён (`build` в черновик → 400).
- Скрыты из `GET /versions` по умолчанию (`include_drafts=false`).

### Changed

- **`CHAT_CONTEXT.md`** — синхронизирован с фактическим состоянием
  проекта (v4.10.2, Итерации 0–20 + 17.5). Пометка «требует
  верификации» снята с трека «Черновики» — подтверждено по коду.
  Добавлен нюанс «черновик пустой до build».
- **`docs/ROADMAP.md`** — трек C переименован в «Итерация 17.5 —
  Черновики», статус ✅. Добавлена в таблицу итераций.
- **`README.md`** — раздел «Известные ограничения»: пункт про
  черновики переписан (снята пометка «требует верификации»,
  добавлен нюанс «пустой до build»). Roadmap-таблица: трек C → 17.5 ✅.

---

## [4.10.2] — 2026-10-13

Patch-релиз: исправление бага в API Честного Знака, найденного
при интеграции с камерами технического зрения.

### Fixed

#### `POST /api/v1/cz/scan` требовал JWT — камера не могла отправить скан

- **`backend/app/api/v1/cz.py`** — из `receive_scan` убран
  `Depends(get_current_org_id)`. `org_id` берётся из
  `settings.DEFAULT_ORG_ID`.
  - **Симптом:** камера технического зрения отправляет скан на
    `POST /api/v1/cz/scan` с заголовком `X-CZ-Api-Key`, но получает
    `401 {"detail":"Not authenticated"}`. Ошибка возникает **до**
    проверки API-ключа (`_check_api_key`) — на этапе аутентификации.
  - **Причина:** `receive_scan` был объявлен с
    `org_id: UUID = Depends(get_current_org_id)`. Внутри
    `get_current_org_id` → `get_current_user`, который требует
    валидный JWT (`Authorization: Bearer <token>`). То есть эндпоинт
    фактически требовал **и** JWT, **и** API-ключ. Но камера — это
    не пользователь, у неё нет логина и JWT.
  - **Противоречие документации:** `docs/API.md` утверждает, что
    `POST /cz/scan` — **публичный** (только `X-CZ-Api-Key`, без JWT):
    «Все эндпоинты, кроме login и POST /cz/scan, требуют
    `Authorization: Bearer`». Код не соответствовал доке.
  - **Fix:** убран `Depends(get_current_org_id)` из `receive_scan`.
    `org_id` берётся из `settings.DEFAULT_ORG_ID`
    (`00000000-0000-0000-0000-000000000001`). Аутентификация —
    **только** через `X-CZ-Api-Key`.
  - **Совместимость:** UI-кнопка «Тестовый скан» (`api.ts`)
    продолжает работать — axios подставляет JWT автоматически, но
    теперь это не требуется. Реальные камеры (без JWT) теперь
    могут отправлять сканы.
  - **Мульти-тенантность (на будущее):** сейчас `org_id` жёстко
    `DEFAULT_ORG_ID`. Если понадобится **несколько организаций**,
    нужно привязать API-ключ к организации
    (`app_settings.cz_api_key_org_id`). Задача добавлена в
    `docs/BACKLOG.md` как **5.8**.

**Что НЕ изменилось:**
- Остальные эндпоинты `/cz/*` (`/pending`, `/log`, `/stats`,
  `/batch/{id}/progress`, `/scan/{id}/attach`, `/scan/{id}`)
  по-прежнему требуют JWT — они предназначены для UI.
- Модели `CzScanRequest`, `CzScanResponse` — без изменений.
- Схема БД — миграции нет.

### Changed

- **`docs/TROUBLESHOOTING.md`** — добавлен пункт **156**
  «POST /cz/scan требует JWT — камера не может отправить скан»
  (Симптом → Причина → Решение → Проверка).
  - Новая секция `## Честный Знак (17.5)` перед старой секцией
    `## Честный Знак`.
  - Раздел «Диагностика» перенумерован: **156 → 157**, **157 → 158**,
    **158 → 159** (непрерывная нумерация).

- **`docs/BACKLOG.md`** — добавлена задача **5.8**
  «Мульти-тенантный ЧЗ-API» (1 день, 🟢):
  - Привязка API-ключа к организации через
    `app_settings.cz_api_key_org_id`.
  - Актуально, если камеры ЧЗ будут слать сканы от имени
    нескольких организаций.

### Notes

- Версия `4.10.2` — **patch-релиз**, обратная совместимость
  с `4.10.1` сохранена.
- Все правки — **не меняют функциональность**, только устраняют
  архитектурный баг.

### Проверено end-to-end

1. **`Invoke-RestMethod` без JWT**, только `X-CZ-Api-Key` →
   `200 OK`.
2. Скан `TEST_NOJWT_004` записан в `cz_scan_log`,
   `organization_id = DEFAULT_ORG_ID`.
3. `resolve_batch_for_scan` автоматически сопоставил скан
   с партией `5d09850d-...` и задачей `6a9f7613-...`.
4. `batch.cz_marked_qty = 1`, `cz_status = IN_PROGRESS`,
   `cz_last_scan_at = 2026-10-13 08:18:20 UTC`.

### Migration

Обновление для тех, кто уже развернул `4.10.x`:

```bash
# 1. Получить изменения
git pull
# или вручную применить backend/app/api/v1/cz.py,
#   docs/TROUBLESHOOTING.md, docs/BACKLOG.md

# 2. Пересобрать backend (в Docker)
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend

# Или в dev (IntelliJ): Stop → Run

# 3. Проверить фикс — скан без JWT:
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT cz_code, line_code, camera_id, organization_id
FROM cz_scan_log
WHERE cz_code LIKE 'TEST_NOJWT%'
ORDER BY scanned_at DESC;
"

# Ожидаемо: строка с organization_id = DEFAULT_ORG_ID.

# 4. Проверить, что остальные /cz/* требуют JWT:
curl.exe -s "http://localhost:8000/api/v1/cz/pending"
# Ожидаемо: 401 {"detail":"Not authenticated"}
```

**Для новых развёртываний** — просто использовать обновлённый код.

---

## [4.10.1] — 2026-10-13

Patch-релиз: исправление бага, найденного при тестировании
автоматического разбиения заказов на партии.

### Fixed

#### Партии ГП-заказов привязывались к ГП вместо родительского ПФ

- **`backend/app/api/v1/orders.py`** — при создании партии продукт
  берётся из заказа через `COALESCE(parent_pf_id, product_id)`.
  - **Симптом:** после «Разбить» заказа на ГП партии создавались
    с `batch.product_id = <ГП>`. При пересчёте плана эти партии
    **молча выпадали** из расписания. Пользователь видел, что
    заказ есть, партии есть, но на Ганте их нет.
  - **Причина:** `auto_split_order` и `create_batch` использовали
    `order.product_id` (это `type='GP'`). `operation_template`
    заведены только на ПФ (`type='PF'`), поэтому
    `build_routing()` в `routing.py:357` возвращал `[]`
    (см. ниже — второе исправление).
  - **Пример:** заказ `TEST_E` (ГП, `parent_pf_id = TEST_1`) →
    партии ссылались на `TEST_E` (0 операций) вместо `TEST_1`
    (3 операции). Партии не попадали в план.
  - **Fix:** добавлен helper `_resolve_batch_product_id()`,
    который берёт `COALESCE(product.parent_pf_id, product.id)`
    из заказа. Для ПФ-заказов работает как раньше
    (возвращает сам ПФ), для ГП-заказов — родительский ПФ.
    Используется в `auto_split_order` и `create_batch`.

- **`backend/app/api/v1/material_models.py`** — `BatchCreate`
  больше не принимает `product_id`.
  - **Симптом:** UI передавал `product_id = order.product_id` (ГП),
    и backend сохранял его в `batch.product_id`. Это источник
    бага выше.
  - **Причина:** продукт партии определяется заказом и не должен
    задаваться клиентом. Иначе клиент может ошибиться
    (что и произошло).
  - **Fix:** поле `product_id` удалено из `BatchCreate`. `BatchResponse`
    сохраняет `product_id` (вычисленный backend'ом) — для чтения.
  - **Совместимость:** `OrdersPage.tsx` не передаёт `product_id`
    (использует только `autoSplit(orderId, equipmentId, maxFill)`),
    поэтому UI правок не требует. Старые кастомные клиенты,
    передающие `product_id`, получат `422 Unprocessable Entity`.

- **`backend/app/scheduler/routing.py`** — при отсутствии
  `operation_template` пишется WARNING в лог.
  - **Симптом:** партии с продуктом без операций **молча
    выпадали** из плана. Не было ни ошибки, ни предупреждения —
    пользователь не понимал, почему заказ не планируется.
  - **Причина:** `if not operations: return []` без логирования.
  - **Fix:** добавлен `log_with_context(WARNING, ...)` с
    `batch_id`, `product_code`, `product_type`. Теперь такие
    случаи видны в логах backend:
    ```
    [routing] Пропущена партия <uuid>: у продукта TEST_E
    (type=GP) нет operation_template. Партия выпадет из плана.
    ```
  - **Дополнительно:** docstring `build_routing` дополнен
    блоком `Итерация 17.5 (fix #silent-skip)`.

**Что НЕ изменилось:**
- `frontend/src/pages/OrdersPage.tsx` — не требует правок.
- Схема БД — миграции нет (это fix на уровне кода).

### Notes

- Версия `4.10.1` — **patch-релиз**, обратная совместимость
  с `4.10.0` сохранена.
- Все правки — **не меняют функциональность**, только
  устраняют баг.

### Проверено end-to-end

1. Создан ПФ `TEST_1` (3 операции: `water_loading`, `mixing`, `washing`).
2. Создан ГП `TEST_E` с `parent_pf_id = TEST_1`.
3. Заказ на `TEST_E` → «Разбить» →
   `batch.product_id = TEST_1` (PF), а не `TEST_E` (GP).
4. Пересчёт → 4 задачи в плане:
- `Загрузка сырья (вода)` — `REACTOR_OP` на `REACTOR_1`
- `Перемешивание` — `REACTOR_OP` на `REACTOR_1`
- `Слив на линию розлива` — `LINE_FILL` на `LINE_1`
- `Промывка реактора` — `WASH` на `REACTOR_1`

### Migration

Обновление для тех, кто уже развернул `4.10.0`:

```bash
# 1. Получить изменения
git pull
# или rsync, или вручную применить 3 файла

# 2. Пересобрать backend (в Docker)
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend

# Или в dev (IntelliJ): Stop → Run

# 3. Проверить, что фикс работает:
#    - Создать/открыть ГП-заказ.
#    - «Разбить» на партии.
#    - Проверить batch.product_id:

docker exec -i aps_postgres psql -U aps -d household -c "
SELECT b.id AS batch_id, b.volume_kg,
       p.code AS batch_product, p.type AS batch_type
FROM batch b
JOIN product p ON p.id = b.product_id
WHERE b.order_id = (
    SELECT id FROM production_order
    WHERE product_id = (SELECT id FROM product WHERE code = 'TEST_E')
    ORDER BY created_at DESC LIMIT 1
);
"

# Ожидаемо: batch_product = TEST_1 (PF), НЕ TEST_E (GP).

# 4. Пересчитать план:
#    - «Планирование» → «Построить план»
#    - Проверить, что партии появились в расписании.

# 5. Проверить логи — не должно быть WARNING:
docker compose -f docker-compose.prod.yml logs backend --tail 200 | grep routing
# Ожидаемо: пусто.
```

**Для существующих партий с ГП:** если в БД уже есть партии,
созданные до этого фикса, они всё ещё ссылаются на ГП и не будут
планироваться. Разово исправить:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE batch b
SET product_id = p.parent_pf_id
FROM product p
WHERE b.product_id = p.id
  AND p.type = 'GP'
  AND p.parent_pf_id IS NOT NULL;
"
```

Затем — пересчитать план.

---

## [4.10.0] — 2026-10-12

Итерации 17.1–17.4 — Редактирование и версионирование рецептур,
дата начала планирования, копирование UUID версии плана.

### Added

#### Итерация 17.1 — Inline-edit рецептур в UI

**Проблема:**
Модуль «Рецептуры» позволял только создать рецепт (с пустым составом)
и удалить его. Не было:
- редактирования базовых полей (`base_volume_kg`, `comment`);
- редактирования состава (добавить/удалить/изменить количество);
- режима просмотра (readonly) для сохранённых версий плана.

Пользователю приходилось удалять рецепт и создавать заново — теряя
историю и ID.

**Решение:**

**1. Backend (`recipes.py`):**
- ✅ `PUT /api/v1/recipes/{recipe_id}/items/{item_id}` — новый эндпоинт
  для inline-edit `qty_per_base` компонента.
- ✅ `POST /api/v1/recipes/{recipe_id}/items` переведён на **JSON body**
  (`RecipeItemCreate`) — было через query-параметры.
- ✅ Во все item-endpoint'ы добавлена проверка принадлежности рецепта
  организации.

**2. Frontend (`RecipesPage.tsx`):**
- ✅ Inline-edit колонок `base_volume_kg` и `comment` в основной
  таблице → `PUT /api/v1/recipes/{id}`.
- ✅ Диалог состава переделан на редактируемый AG Grid:
  - inline-edit `qty_per_base`;
  - кнопки удаления компонентов;
  - форма добавления материала (селект + кол-во).
- ✅ Режим просмотра: `isReadOnly` через `currentVersionId`, баннер
  «Режим просмотра», скрытие всех элементов редактирования.
- ✅ `markPlanDirty()` вызывается на все изменения.

**3. Frontend (`api.ts`):**
- ✅ `recipesApi.addItem` переведён на JSON body.
- ✅ Добавлен `recipesApi.updateItem(recipeId, itemId, materialId, qty)`.

**Fixed:**

- **`RecipesPage.tsx` — селект «Продукт (ПФ)» использовал материалы
  вместо продуктов.**
  - **Симптом:** создание рецепта через UI → `500 Internal Server Error`,
    в логах — `ForeignKeyViolationError: insert or update on table "recipe"
    violates foreign key constraint "recipe_product_id_fkey"`.
  - **Причина:** в селект подставлялись `materials.filter(category === 'RAW')`,
    их `id` уходил в `recipe.product_id`. FK `recipe.product_id → product.id`
    падал, потому что это разные UUID.
  - **Последствие:** рецепты через UI было невозможно создать; они
    существовали только из seed-миграции.
  - **Fix:** селект использует `productsApi.getAll()` (с учётом
    `currentVersionId`), фильтр `type === 'PF'`. Плюс добавлена валидация
    `formData.product_id !== ''` перед POST.

#### Итерация 17.2 — Версионирование рецептур (снапшоты)

**Проблема:**
Рецептуры не версионировались. При открытии сохранённой версии плана
всегда читались **актуальные** данные из `recipe` / `recipe_item`. Если
пользователь менял рецепт после создания версии, история искажалась —
старые планы «ссылались» на новые составы.

**Решение:**

**1. Миграция `add_29_recipe_snapshots.sql`:**
- ✅ Таблица `recipe_snapshot`:
  - составной PK `(id, version_id)`;
  - FK `version_id → schedule_version(id) ON DELETE CASCADE`;
  - индексы `idx_recipe_snap_ver`, `idx_recipe_snap_org_ver`.
- ✅ Таблица `recipe_item_snapshot`:
  - составной PK `(id, version_id)`;
  - FK `version_id → schedule_version(id) ON DELETE CASCADE`;
  - индексы `idx_recipe_item_snap_ver`, `idx_recipe_item_snap_recipe_ver`.
- ✅ **Важно:** FK на `product` и `material` в снапшотах убраны —
  снапшот имутабелен, а ссылочные записи могут быть удалены в живой БД.

**2. `snapshot.py` — расширение `snapshot_all_catalogs`:**
- ✅ Блок 5: `INSERT INTO recipe_snapshot SELECT ... FROM recipe`.
- ✅ Блок 6: `INSERT INTO recipe_item_snapshot SELECT ... FROM recipe_item
  JOIN recipe ON recipe.organization_id = :org_id`.
- ✅ `stats` теперь содержит `recipes` и `recipe_items`.
- ✅ `ON CONFLICT (id, version_id) DO NOTHING` — идемпотентно.

**3. `recipes.py` — чтение с учётом версии:**
- ✅ `GET /api/v1/recipes/?version_id=<UUID>` — новый параметр.
- ✅ Если `version_id` задан — чтение из `recipe_snapshot` и
  `recipe_item_snapshot`. Иначе — из живых `recipe` / `recipe_item`.
- ✅ Все мутации (`POST`, `PUT`, `DELETE`) — только с живыми таблицами.

**4. Frontend (`RecipesPage.tsx`):**
- ✅ `loadData` передаёт `currentVersionId` в `GET /recipes/`.

**5. Frontend (`api.ts`):**
- ✅ `recipesApi.getAll(productId?, versionId?)` — второй параметр.

**Ключевые гарантии:**

- ✅ **Имутабельность** — снапшот не обновляется при изменении
  живого рецепта (by design).
- ✅ **Обратная совместимость** — `GET /recipes/` без `version_id`
  работает как раньше.
- ✅ **CASCADE DELETE** — при удалении версии снапшоты удаляются
  автоматически.
- ✅ **Мульти-тенантность** — снапшот содержит `organization_id`.

**Проверено:**
- Создание версии → `recipe_snapshot` содержит 4 рецепта / 14 компонентов
  (для тестовой версии `b85988cf-...`).
- Просмотр версии → данные из снапшота (`CHLORIDE=5`).
- Редактирование в текущем плане (`CHLORIDE=15`) не влияет на версию.

#### Итерация 17.3 — Дата начала планирования в UI

**Проблема:**
Настройка `planning_start_date` существовала в backend
(`settings.py::SETTINGS_REGISTRY`, читается `data_loader.py`,
используется `core.py::_resolve_t0`), но её можно было изменить только
через раздел «Настройки». В панели «Параметры расчёта» на странице
«Планирование» поля не было.

**Решение:**

**`SchedulePage.tsx`:**
- ✅ Новый стейт `planningStartDate` (`YYYY-MM-DD` для `input[type=date]`).
- ✅ `loadPlanningSettings` читает `planning_start_date` из `app_settings`,
  обрезает до `YYYY-MM-DD`.
- ✅ `savePlanningSettings` дополняет до `YYYY-MM-DDTHH:mm:ss`
  (`T08:00:00` — начало первой смены по МСК, как в
  `core.py::_resolve_t0`) и сохраняет в `app_settings`.
- ✅ Поле `TextField type="date"` добавлено в панель между «Таймаут solver»
  и «Построить план».
- ✅ Выравнивание: обёртка кнопки `height: 40`, `alignItems: flex-start`
  у контейнера — чтобы поле/кнопка/hint стояли на одной линии и
  helper-тексты не сдвигали элементы.

**Почему `T08:00:00`:** `core.py::_resolve_t0` парсит значение как
`Europe/Moscow`. Без времени получилось бы `00:00:00 МСК` → `21:00 UTC`
предыдущего дня. С `T08:00:00` — `05:00 UTC`, совпадает с дефолтом
`2026-09-01 05:00:00 UTC`.

#### Итерация 17.4 — Копирование UUID версии плана из UI

**Проблема:**
Чтобы получить `id` версии плана (для SQL-запросов, отладки,
передачи в API), приходилось лезть в БД через `psql`. Это неудобно
и требует доступа к серверу.

**Решение:**

**`SchedulePage.tsx` — `renderNameCell`:**
- ✅ Имя плана обёрнуто в `Tooltip` с UUID версии и подсказкой
  «Кликните, чтобы скопировать».
- ✅ Клик по имени копирует UUID в буфер обмена
  (`navigator.clipboard.writeText`).
- ✅ Fallback для http-контекста — `document.execCommand('copy')`.
- ✅ Обратная связь через существующий Alert `success`:
  «ID плана скопирован: `<UUID>`» (авто-скрытие через 2.5 сек).

### Changed

- Версия проекта: `4.9.1` → `4.10.0` (функциональная итерация).
- `backend/app/api/v1/recipes.py` — добавлен `PUT /{id}/items/{item_id}`,
  `POST /{id}/items` переведён на JSON body, добавлен параметр `version_id`
  в `GET /`.
- `backend/app/scheduler/snapshot.py` — `snapshot_all_catalogs` расширен
  блоками 5 и 6 (рецепты), `stats` содержит `recipes` и `recipe_items`.
- `backend/migrations/add_29_recipe_snapshots.sql` — **новый файл**.
- `frontend/src/services/api.ts` — `recipesApi.addItem` (JSON body),
  `recipesApi.updateItem` (новый метод), `recipesApi.getAll` (второй
  параметр `versionId`).
- `frontend/src/pages/RecipesPage.tsx` — inline-edit, редактируемый
  диалог состава, режим просмотра, `markPlanDirty`, фикс селекта
  «Продукт (ПФ)», передача `version_id`.
- `frontend/src/pages/SchedulePage.tsx` — поле «Дата начала
  планирования», копирование UUID по клику на имя плана, выравнивание
  панели «Параметры расчёта».

### Fixed

- **Создание рецепта через UI падало с 500 (FK violation).**
  - **Симптом:** `POST /api/v1/recipes/` → `500 Internal Server Error`,
    в логах — `ForeignKeyViolationError: recipe_product_id_fkey`.
  - **Причина:** в `RecipesPage.tsx` селект «Продукт (ПФ)» использовал
    `materials.filter(category === 'RAW')`. `material.id` ≠ `product.id`.
  - **Fix:** селект использует `productsApi.getAll()` (фильтр
    `type === 'PF'`). См. Итерацию 17.1.
- **`POST /api/v1/recipes/{id}/items` не работал из UI.**
  - **Причина:** endpoint принимал `material_id` и `qty_per_base` как
    query-параметры, что не соответствует inline-edit паттерну.
  - **Fix:** переведён на JSON body. См. Итерацию 17.1.
- **Дата начала планирования не отражалась в UI.**
  - **Причина:** настройка `planning_start_date` существовала в
    `app_settings`, но не отображалась в панели «Параметры расчёта».
  - **Fix:** добавлено поле `type="date"` в `SchedulePage.tsx`.
    См. Итерацию 17.3.
- **UUID версии плана было сложно получить.**
  - **Fix:** клик по имени плана копирует UUID в буфер.
    См. Итерацию 17.4.

### Notes

- Версия `4.10.0` — **функциональная итерация**, обратная совместимость
  с `4.9.x` сохранена.
- Тесты: **789 passed, 0 skipped** — новых тестов не добавлено
  (изменения проверены вручную через UI и SQL).
- `saver.py` менять не потребовалось — вызывающая сторона
  `snapshot_all_catalogs` уже расширена.

### Migration

Для тех, кто уже развернул `4.9.x`:

```bash
# 1. Применить миграцию для снапшотов рецептур
docker cp backend/migrations/add_29_recipe_snapshots.sql aps_postgres:/tmp/add_29.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_29.sql

# 2. Проверить, что таблицы созданы
docker exec -i aps_postgres psql -U aps -d household -c "\d recipe_snapshot"
docker exec -i aps_postgres psql -U aps -d household -c "\d recipe_item_snapshot"

# 3. Перезапустить backend (или пересобрать, если в Docker)
docker compose -f docker-compose.prod.yml restart backend
# Или в IntelliJ — Stop → Run

# 4. Создать новую версию плана (снапшоты рецептов заполнятся автоматически)
#    Через UI: «Планирование» → «Новый план» → «Создать»

# 5. Проверить, что снапшот рецептов заполнен
docker exec -i aps_postgres psql -U aps -d household -c "SELECT version_id, COUNT(*) AS recipes FROM recipe_snapshot GROUP BY version_id ORDER BY version_id DESC LIMIT 5;"

# 6. Пересобрать frontend (из-за правок в RecipesPage.tsx, SchedulePage.tsx, api.ts)
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Важно для старых версий планов:** снапшоты рецептов для версий,
созданных **до** применения миграции `add_29_recipe_snapshots.sql`,
**пусты**. При открытии такой версии раздел «Рецептуры» покажет пустой
список. Для получения снапшота рецептов нужно **создать новую версию**
плана (через UI или `POST /api/v1/schedule/versions`).

Для новых развёртываний — применить миграцию `add_29_recipe_snapshots.sql`
вместе с остальными (см. [docs/OPERATIONS.md](docs/OPERATIONS.md)).

---

## [4.9.1] — 2026-10-09

Patch-релиз: исправления, найденные при развёртывании в изолированной VM (VirtualBox + Ubuntu 22.04 + Docker).

### Fixed

#### Инфраструктура развёртывания

- **`backend/seed_demo_data.sql`** — добавлено пропущенное объявление `v_tank2 UUID;` в `DECLARE`-блоке.
  - **Симптом:** при применении `seed_demo_data.sql` через `psql -f` — ошибка `ERROR: "v_tank2" is not a known variable` (строка 142).
  - **Причина:** переменная `v_tank2` использовалась в теле PL/pgSQL-блока (строки 166, 168, 193, 194), но не была объявлена рядом с `v_tank1`.
  - **Последствие:** демо-данные не применялись, БД оставалась пустой.
  - **Fix:** добавлена строка `v_tank2 UUID;` после `v_tank1 UUID;` в `DECLARE`.

- **`nginx/nginx.conf`** — во всех активных `proxy_set_header Host` заменено `$host` на `$http_host`.
  - **Симптом:** `GET /api/v1/equipment` → `307 Temporary Redirect` с `location: http://localhost/api/v1/equipment/` (**без порта**).
  - **Причина:** `$host` в nginx не содержит порт, а `$http_host` — содержит. При reverse-proxy на нестандартном порту (8080 → 80) это ломает 307 redirect.
  - **Последствие:** frontend не мог загрузить данные — браузер шёл на `http://localhost/...` (порт 80), где ничего нет.
  - **Fix:** замена 6 активных вхождений `$host` → `$http_host` (строки 117, 136, 145, 154, 166, 178).

- **`backend/.dockerignore`** — создан (отсутствовал в проекте).
  - **Симптом:** при сборке backend-образа в него попадали `.env`, `.venv`, `__pycache__`, `.git`, `tests/`.
  - **Последствие:** образ раздувался (~+200 MB), `.env` с секретами попадал в image.
  - **Fix:** создан полный `.dockerignore` с исключениями для секретов, кэша, тестов, IDE.

- **`frontend/src/config.ts`** — добавлена защита от плейсхолдеров в `VITE_API_URL`.
  - **Симптом:** после сборки frontend стучался на `http://your-server-ip/api/v1/...` → `net::ERR_NAME_NOT_RESOLVED`.
  - **Причина:** пользователь забыл заменить `VITE_API_URL=http://your-server-ip` в `.env` на реальный адрес; Vite вшил плейсхолдер в бандл.
  - **Последствие:** UI открывался, но логин не работал; все API-запросы падали.
  - **Fix:** добавлена проверка `isValidApiUrl()` — если значение содержит `your-server-ip` / `your-domain.com` или не начинается с `http(s)://`, используется fallback `http://localhost:8080`. Плюс — DEV-предупреждение в консоль.
  - **Дополнительно:** добавлены экспорты `APP_NAME` (для `document.title`), `API_TIMEOUT_MS` (для axios).

- **`docker-compose.prod.yml`** — удалена устаревшая директива `version: '3.9'`.
  - **Симптом:** при `docker compose config` — warning `the attribute 'version' is obsolete, it will be ignored`.
  - **Причина:** в Docker Compose v2+ атрибут `version` устарел.
  - **Fix:** строка удалена.

### Changed

- **`docs/DEPLOYMENT.md`** — усилена инструкция по развёртыванию:
  - **Новый Шаг 6.1** — «Проверка критичных переменных» с командами:
    - `grep -c "change_me" .env` → ожидается `0`;
    - `grep -E "your-server-ip|your-domain\.com" .env` → ожидается пусто;
    - Проверка, что `VITE_API_URL` вшит правильно в бандл.
  - **Troubleshooting** — добавлены 2 пункта:
    - Frontend стучится на `your-server-ip`;
    - Оборудование не грузится (307 redirect без порта).
  - **Чек-лист** — 3 новых проверки для `VITE_API_URL` и `ALLOWED_ORIGINS`.

- **`docs/TROUBLESHOOTING.md`** — добавлены 2 пункта в раздел «Docker / облако»:
  - **147.** Frontend стучится на `your-server-ip` (`ERR_NAME_NOT_RESOLVED`).
  - **148.** Оборудование не грузится, 307 redirect без порта.
  - Старые пункты 147–148 (Диагностика) перенумерованы в 151–152.

### Notes

- Версия `4.9.1` — **patch-релиз**, обратная совместимость с `4.9.0` сохранена.
- Все правки — **не меняют функциональность**, только устраняют проблемы развёртывания.
- Версия в `README.md`, `docs/ROADMAP.md`, `backend/app/main.py` — **осталась 4.9.0** (patch-релизы не влияют на фичи).

### Migration

Для тех, кто уже развернул `4.9.0`:

```bash
# 1. Применить фиксы в рабочей копии проекта (git pull или вручную)

# 2. Пересобрать frontend (из-за правок в config.ts)
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend

# 3. Перезапустить nginx (из-за правок в nginx.conf)
docker compose -f docker-compose.prod.yml restart nginx

# 4. Перезапустить backend (из-за правок в nginx)
docker compose -f docker-compose.prod.yml restart backend
```

Для новых развёртываний — просто использовать обновлённые файлы.

---

## [4.9.0] — 2026-10-07

Итерация 16 — Расширенный аудит и отчёты.

### Added

#### Итерация 16 — Расширенный аудит и отчёты

**Проблема:**
Страница «Аудит» (Итерация 13.3) собирала события из 4 журналов
(`material_stock_log`, `reschedule_log`, `lab_analysis_log`,
`cz_scan_log`) и показывала их списком с базовыми фильтрами.
Но:
- пункт меню был **скрыт** в UI (Итерация 13.16 — «страница в разработке»),
- фильтров не хватало для реального анализа (нет `actor_id`,
  `entity_type`, диапазона `delta_qty`),
- не было дашборда — только список,
- нельзя было сохранить часто используемые представления,
- нельзя было выгрузить результат в Excel.

**Решение:**

**1. Возврат аудита в UI (16.0):**
- ✅ `frontend/src/App.tsx` — роут `/audit` снова зарегистрирован.
- ✅ `frontend/src/components/layout/MainLayout.tsx` — пункт меню «Аудит»
  раскомментирован, добавлена иконка `History`.
- ✅ Backend был подключён всегда — потребовалась только правка фронта.

**2. Расширенные фильтры (16.1):**
- ✅ 4 новых query-параметра в `GET /api/v1/audit/log`:
  - `actor_id` — фильтр по автору события (UUID);
  - `entity_type` — тип сущности: `material | batch | schedule_version`;
  - `delta_qty_from` / `delta_qty_to` — диапазон изменения количества
    (только для STOCK-событий).
- ✅ SQL-фильтры `actor_id`/`entity_type` добавлены в `_fetch_*_events`
  (для STOCK/RESCHEDULE/LAB; CZ — всегда пусто при `actor_id`, т.к.
  камера не является пользователем).
- ✅ Пост-фильтр `_post_filter` применяет `delta_qty` к STOCK-событиям
  и отбрасывает события без этого поля.
- ✅ Новая Pydantic-модель `AuditFilterSpec` — единый формат для
  GET-запросов, POST-экспорта и сохранённых представлений.

**3. Сохранённые представления (16.2):**
- ✅ Миграция `add_28.sql` — таблица `audit_saved_view`:
  - `id`, `organization_id`, `user_id`, `name`, `comment`, `filters` (JSONB),
    `is_default`, `display_order`, `created_at`, `updated_at`;
  - UNIQUE `(organization_id, user_id, name)`;
  - partial-index по `is_default = TRUE`;
  - триггер автообновления `updated_at`.
- ✅ 4 эндпоинта:
  - `GET    /api/v1/audit/saved-views` — список моих представлений;
  - `POST   /api/v1/audit/saved-views` — создать;
  - `PUT    /api/v1/audit/saved-views/{id}` — обновить;
  - `DELETE /api/v1/audit/saved-views/{id}` — удалить.
- ✅ Все 4 защищены `Depends(get_current_user_id)` — представления per-user.
- ✅ При установке `is_default = TRUE` с других представлений пользователя
  флаг снимается автоматически (в одной транзакции).
- ✅ UI: чипы представлений над фильтрами; клик — загрузить, крестик — удалить,
  двойной клик — переключить «по умолчанию» (★).

**4. Дашборд с графиками (16.3):**
- ✅ Новый эндпоинт `GET /api/v1/audit/stats/series`:
  - `group_by=day` — точки по дням (с заполнением пропущенных нулями);
  - `group_by=source` — точки по источникам;
  - `group_by=severity` — точки по уровням важности.
- ✅ Frontend: библиотека `recharts@^2.15.0`.
- ✅ 3 графика в сворачиваемой карточке:
  - Line chart «События по дням»;
  - Bar chart «По источникам»;
  - Bar chart «По важности».
- ✅ Нулевые категории в bar-charts скрыты (нет визуального «шума»).
- ✅ Дашборд сворачивается кнопкой `▲/▼`, состояние в `localStorage`
  (ключ `aps_audit_dashboard_open`).
- ✅ При свёрнутом дашборде в заголовке показывается компактная сводка
  `RESCHEDULE: 2 · Инфо: 2`.

**5. Экспорт в Excel (16.4):**
- ✅ Новый эндпоинт `POST /api/v1/audit/export.xlsx`.
- ✅ Генерация на backend через `openpyxl` (добавлен в `requirements.txt`).
- ✅ Заголовки: `Время | Источник | Важность | Тип | Заголовок | Описание |
  Сущность | Автор | Детали`.
- ✅ Фильтры те же, что у `/log` (`AuditFilterSpec`).
- ✅ Параметр `max_rows` (default 10 000) — защита от гигантских выгрузок.
- ✅ StreamingResponse с `Content-Disposition: attachment`.
- ✅ Frontend: кнопка «Экспорт в Excel» рядом с «Обновить».

**6. UX-полировка страницы «Аудит» (16.5):**
- ✅ Дашборд вынесен в сворачиваемую карточку — экономия до 400px
  вертикали при свёрнутом виде.
- ✅ Фильтры сжаты в одну карточку с двумя рядами (базовые + расширенные),
  `flexShrink: 0` — не «уезжают» на маленьких экранах.
- ✅ Пресеты дат (`День/Неделя/Месяц`) + «Сбросить» сгруппированы справа.
- ✅ Графики уменьшены до 140px по высоте, читаемы и на 1366×768.
- ✅ Скроллбар списка событий корректно растягивается (`minHeight: 0` на
  всех flex-обёртках).
- ✅ Все фильтры синхронизируются с URL (шаринг ссылок, history back/forward).

**7. Тесты:**
- ✅ `test_audit.py` — **+35** новых структурных тестов (расширенные
  фильтры, saved views CRUD, series, экспорт, права, регрессия).
- ✅ `test_audit_models.py` — **+27** новых тестов Pydantic-моделей
  (`AuditFilterSpec`, `AuditSavedView*`, `AuditStatsSeriesResponse`,
  `AuditExportRequest`).
- ✅ Существующие 17 + 9 тестов не сломаны.
- ✅ **Итого: 789 passed, 0 skipped** (все интеграционные тесты
  прогнаны на реальной PostgreSQL после применения `add_28.sql`).

**Ключевые гарантии:**
- ✅ **Обратная совместимость** — `GET /log`, `GET /stats`, `GET /sources`
  работают как раньше, старые query-параметры сохранены.
- ✅ **Per-user изоляция** — представления не пересекаются между
  пользователями, даже в одной организации.
- ✅ **Открытый формат** — экспорт в xlsx читается Excel, LibreOffice, pandas.
- ✅ **Мульти-тенантность** — все эндпоинты привязаны к `organization_id`.
- ✅ **Идемпотентные миграции** — `add_28.sql` можно применять повторно.

### Changed

- Версия проекта: `4.8.0` → `4.9.0`.
- `backend/app/main.py` — `FastAPI(version="4.9.0")`, `health` возвращает
  `APP_VERSION` из константы.
- `backend/app/api/v1/audit.py` — расширены `_fetch_*_events`, добавлены
  `_post_filter`, `_collect_events`, `_json_dumps`, `_build_xlsx`,
  `export_audit_xlsx`, `get_audit_stats_series`, 4 эндпоинта saved-views.
- `backend/app/api/v1/audit_models.py` — 8 новых моделей.
- `backend/requirements.txt` — добавлен `openpyxl>=3.1.0`.
- `frontend/package.json` — добавлен `recharts@^2.15.0`.
- `frontend/src/App.tsx` — роут `/audit`.
- `frontend/src/components/layout/MainLayout.tsx` — пункт меню «Аудит».
- `frontend/src/services/api.ts` — `auditApi` расширен 8 методами.
- `frontend/src/types/index.ts` — 9 новых типов.
- `frontend/src/pages/AuditPage.tsx` — полный рефакторинг UI.

### Fixed

- **Аудит снова доступен в UI** (Итерация 13.16 временно скрыла пункт
  меню). Теперь страница открывается из бокового меню.
- **Дашборд и фильтры не «уезжают» на экранах 1366×768** — исправлено
  через `flexShrink: 0` и `minHeight: 0` на промежуточных flex-контейнерах.
- **Скроллбар списка событий** — корректно растягивается до низа окна.
- **Дублирование нулевых категорий в bar-charts** — устранено.

---

## [4.8.0] — 2026-10-06

Итерация 15.5 — Редактирование статей справки в UI.

### Added

#### Итерация 15.5 — Редактирование статей справки в UI

**Проблема:**
Итерации 15.1–15.4 создали полноценную справку: markdown-статьи,
контекстные подсказки, интерактивные туры, FAQ. Но для добавления
или правки статьи требовалось писать SQL-миграцию и применять её
вручную через `docker cp` + `psql -f`. Это неудобно для контент-
менеджеров и администраторов: даже исправить опечатку — целая
операция.

**Решение:**
Добавлены CRUD-эндпоинты на бэкенде и полноценный редактор на
фронтенде. Редактирование доступно роли **ADMIN** через страницу
«Помощь».

**1. Backend (`help.py` + `help_models.py`):**
- ✅ 3 новых эндпоинта:
  - `POST   /api/v1/help/articles` — создать статью.
  - `PUT    /api/v1/help/articles/{slug}` — обновить.
  - `DELETE /api/v1/help/articles/{slug}` — удалить.
- ✅ Все три защищены `Depends(require_admin)` (роль ADMIN).
- ✅ `HelpArticleCreate`, `HelpArticleUpdate`, `HelpArticleDeleteResponse`
  вынесены в `help_models.py` (единый источник Pydantic-моделей).
- ✅ Автогенерация slug из title: `_slugify()` с транслитерацией
  RU → EN (`Первый план за 5 минут` → `pervyy-plan-za-5-minut`).
- ✅ Проверка уникальности slug: `_check_slug_conflict()` — включая
  режим исключения для update (тот же slug не считается конфликтом).
- ✅ Авто-`display_order`: если не задан — `max + 10` в категории
  (`_next_display_order()`).
- ✅ Валидация категории по `CATEGORY_LABELS` (9 категорий).
- ✅ Теги сериализуются в JSONB.
- ✅ Статья привязывается к организации (`organization_id = org_id`),
  изоляция по мульти-тенантности.
- ✅ Физическое удаление (`DELETE`). Для скрытия — `is_published = false`.

**2. Frontend (React):**
- ✅ Новый компонент `HelpArticleEditor.tsx`:
  - Форма создания/редактирования на базе `DraggableDialog`.
  - Две вкладки: «Редактор» (поля + textarea markdown) и
    «Предпросмотр» (рендер через `HelpArticleView`).
  - Поля: title, slug (опционально), category (селект),
    content_md (markdown), tags (строка через запятую с парсингом
    в чипы), display_order, is_published.
  - Валидация обязательных полей на клиенте.
  - Кнопка «Удалить» — только в режиме `edit`, с `window.confirm`.
- ✅ Доработка `HelpPage.tsx`:
  - Кнопка **«Новая статья»** в шапке — видна только `ADMIN`.
  - Кнопка **«Редактировать»** (иконка карандаша) над статьёй —
    видна только `ADMIN`.
  - Состояние `editorOpen`, `editorMode`, `editorArticle`,
    `editorError`.
  - Обработчики `handleOpenCreate`, `handleOpenEdit`,
    `handleSaveArticle`, `handleDeleteArticle`.
  - Авторедирект на новый slug после смены slug в редакторе.
  - Перезагрузка списка категорий после CRUD-операции.
- ✅ `helpApi` в `api.ts` — 3 новых метода:
  - `createArticle(payload)`, `updateArticle(slug, payload)`,
    `deleteArticle(slug)`.
- ✅ Типы в `types/index.ts`: `HelpArticleCreate`,
  `HelpArticleUpdate`, `HelpArticleDeleteResponse`.

**3. Тесты (+54):**

- ✅ `test_help.py` — **+37** структурных тестов:
  - Pydantic-модели CRUD (9).
  - Хелпер `_slugify` (8).
  - Роутер: наличие эндпоинтов и async-обработчиков (5).
  - Проверка `require_admin` (3).
  - Структурные проверки CRUD (8).
  - HTTP-контракты 401/403 без токена (3).
  - Sanity: идемпотентность slug (1).
- ✅ `test_help_crud_integration.py` — **+17** интеграционных тестов
  (требуют реальной PostgreSQL):
  - POST /articles: успех, авто-slug, авто-display_order,
    конфликт slug, неизвестная категория (5).
  - PUT /articles/{slug}: успех, частичное, смена slug, конфликт,
    404, неизвестная категория (6).
  - DELETE /articles/{slug}: успех, 404 (2).
  - Права: PLANNER/MASTER/VIEWER → 403 (4 — create×3, update, delete).
  - Изоляция по организации: 404 для чужой org (1).
  - Sanity cleanup (1).

**Ключевые гарантии:**
- ✅ **Редактирование без SQL** — правки через UI.
- ✅ **Только ADMIN** — остальные роли получают 403.
- ✅ **Авто-slug** — не нужно придумывать руками.
- ✅ **Предпросмотр** — видно результат до сохранения.
- ✅ **Мульти-тенантность** — статьи изолированы по организации.
- ✅ **Обратная совместимость** — существующие 15+15+1 статей
  из seed-миграций не затронуты.
- ✅ **Идемпотентность** — повторное создание с тем же slug → 409
  (не 500).

### Changed

- Версия проекта: `4.7.0` → `4.8.0`.
- `backend/app/api/v1/help.py` — 3 новых эндпоинта, хелпер `_slugify`,
  `_check_slug_conflict`, `_next_display_order`. Модели CRUD вынесены
  в `help_models.py`.
- `backend/app/api/v1/help_models.py` — добавлены `HelpArticleCreate`,
  `HelpArticleUpdate`, `HelpArticleDeleteResponse`.
- `frontend/src/services/api.ts` — `helpApi.createArticle`,
  `helpApi.updateArticle`, `helpApi.deleteArticle`.
- `frontend/src/types/index.ts` — 3 новых типа для CRUD.
- `frontend/src/pages/HelpPage.tsx` — кнопки «Новая статья» и
  «Редактировать» (только ADMIN), интеграция `HelpArticleEditor`.
- `frontend/src/components/help/HelpArticleEditor.tsx` — **новый
  компонент** (форма + предпросмотр).

---

## [4.7.0] — 2026-10-04

Итерация 15.3 — Интерактивный туториал.

### Added

#### Итерация 15.3 — Интерактивный туториал

**Проблема:**
Даже с встроенной справкой (Итерация 15.1) и FAQ (Итерация 15.4)
пользователю сложно освоить систему без наглядной демонстрации. Новый
сотрудник не знает, с чего начать и какие шаги предпринять для
построения первого плана.

**Решение:**
Создан интерактивный пошаговый туториал, который «ведёт» пользователя
по ключевым сценариям работы в системе.

**1. Инфраструктура туров (Frontend):**
- ✅ Установлена библиотека `react-joyride` для создания туров.
- ✅ Создан `frontend/src/tutorial/tours.ts` с конфигурацией шагов для
  нескольких туров:
  - `getting-started` — первый план за 5 минут (11 шагов).
  - `gantt-basics` — основы работы с диаграммой Ганта (7 шагов).
  - `shift-management` — работа мастера смены (8 шагов).
- ✅ Создан `frontend/src/tutorial/types.ts` с типами `Tour` и
  `TutorialContextType`.
- ✅ Создан `frontend/src/context/TutorialContext.tsx` для управления
  состоянием активного тура.
- ✅ Создан компонент `TutorialProvider` для глобального доступа к логике
  туров.

**2. Интеграция в UI:**
- ✅ В `MainLayout.tsx` добавлена кнопка «Помощь» (иконка `?`) в шапке
  с выпадающим меню, содержащим:
  - пункт «Открыть справку» (переход на `/help`);
  - список интерактивных туров с возможностью запуска.
- ✅ На странице `HelpPage.tsx` добавлен блок «Интерактивные туры» с
  карточками для запуска каждого тура.
- ✅ Ключевые элементы интерфейса (кнопки, поля, панели) получили
  `data-tour-id` для привязки шагов:
  - `sidebar`, `menu-equipment`, `menu-products`, `menu-orders`,
    `menu-schedule` (главное меню);
  - `build-plan-button`, `advisor-panel`, `plans-history`,
    `open-gantt-button` (страница «Планирование»);
  - `gantt-toolbar`, `gantt-edit-toggle`, `gantt-recalc-button`,
    `gantt-timeline` (диаграмма Ганта);
  - `shift-date-picker`, `shift-selector`, `shift-tasks-list`,
    `task-material-load`, `task-complete`, `task-lab-assign`
    (рабочее место мастера).
- ✅ В `App.tsx` добавлен глобальный `TutorialProvider` и компонент
  `TutorialRunner`, который рендерит `<Joyride/>` поверх всего приложения.

**3. Логика туториала:**
- ✅ Прогресс прохождения тура сохраняется в `localStorage`
  (`aps_tutorial_completed_<tour_id>`).
- ✅ Реализован сброс прогресса (кнопка «Пройти заново»).
- ✅ Возможность пропустить тур (кнопка «Пропустить» на любом шаге).
- ✅ Поддержка навигации: «Назад», «Далее», «Завершить».
- ✅ Синхронизация состояния `activeTour` + `currentStepIndex` через
  `TutorialContext`.
- ✅ Локализация react-joyride на русский язык.

**4. Статья в справке (Backend):**
- ✅ Seed-миграция `add_27_seed_1.sql` добавляет статью
  `tutorial-interactive` в категорию `getting-started`.
- ✅ Статья содержит ссылки на все доступные туры.

**5. Тесты (+18, всего 738):**
- ✅ `frontend/src/context/__tests__/TutorialContext.test.tsx` (13):
  - Инициализация (2).
  - `startTour`, `stopTour` (3).
  - Навигация по шагам: `nextStep`, `prevStep`, `goToStep` (5).
  - Сохранение в localStorage (3).
- ✅ `frontend/src/tutorial/__tests__/tours.test.ts` (18):
  - Корректность структуры туров (4).
  - Валидность `target`, `content`, `placement` (3).
  - Опции шагов (3).
  - `getTourById` (3).
  - Проверки конкретных туров (5).

**Ключевые гарантии:**
- ✅ **Пошаговое обучение** — пользователь видит, куда нажимать.
- ✅ **Сохранение прогресса** — тур не показывается повторно.
- ✅ **Сброс** — можно пройти заново в любой момент.
- ✅ **Обратная совместимость** — если тур не настроен, UI работает как раньше.
- ✅ **Локализация** — все кнопки и подсказки на русском.

### Changed

- Версия проекта: `4.6.0` → `4.7.0`.
- `App.tsx` — обёрнут в `TutorialProvider`, добавлен `TutorialRunner`.
- `MainLayout.tsx` — добавлена кнопка «Помощь» с меню туров, `data-tour-id`
  на sidebar и пункты меню.
- `HelpPage.tsx` — добавлен блок «Интерактивные туры» на главной странице.
- `SchedulePage.tsx` — добавлены `data-tour-id` на ключевые элементы.
- `GanttPage.tsx` — добавлены `data-tour-id` на контейнер диаграммы.
- `GanttToolbar.tsx` — добавлены `data-tour-id` на тулбар, переключатель
  режима и кнопку «Пересчитать».
- `ShiftPage.tsx` — добавлены `data-tour-id` на поля выбора смены,
  задания и иконки действий.
- `README.md` — обновлён список фич и Roadmap.
- `docs/ROADMAP.md` — Итерация 15.3 отмечена как ✅.
- `docs/DEVELOPMENT.md` — добавлен раздел «Как добавить интерактивный тур».

---

## [4.6.0] — 2026-10-04

Итерация 15.4 — FAQ и расширение базы знаний.

### Added

#### Итерация 15.4 — FAQ и расширение базы знаний

**Проблема:**
Встроенная справка (Итерация 15.1) содержит 15 статей, покрывающих
базовые сценарии. Но пользователи часто сталкиваются с **типовыми
проблемами** (Advisor-подсказки, зависший What-if, «сироты» ЧЗ,
задача не двигается), и не всегда понимают, что делать. Техническая
`TROUBLESHOOTING.md` — для разработчиков.

**Решение:**
Новая категория **FAQ** в справке с 15 статьями, построенными по
принципу **Симптом → Причина → Что делать**.

**1. Категория FAQ (Backend):**
- ✅ В `help.py`:
  - `CATEGORY_LABELS["faq"] = "FAQ"`.
  - `CATEGORY_ORDER` — `faq` добавлена последней.
- ✅ Frontend не меняется — `HelpPage` подхватывает новую категорию
  автоматически.

**2. Seed-миграции (15 статей в 3 файлах):**

**`add_26_seed_1.sql` — Планирование (5 статей):**
- ✅ `faq-plan-feasible-not-optimal` — План FEASIBLE vs OPTIMAL.
- ✅ `faq-task-not-movable` — Задача не двигается на Ганте.
- ✅ `faq-plan-is-empty` — План пуст (⚠).
- ✅ `faq-plan-settings-empty` — «Настройки плана не заполнены».
- ✅ `faq-material-shortage` — Не хватает сырья.

**`add_26_seed_2.sql` — Гант, смены, what-if, ЧЗ (5 статей):**
- ✅ `faq-move-pinned-task` — Закреплённая задача не двигается.
- ✅ `faq-old-version-not-archived` — Старая версия не архивируется.
- ✅ `faq-shift-mode-change` — После смены режима смен задачи
  потеряли привязку.
- ✅ `faq-whatif-running` — What-if завис в RUNNING.
- ✅ `faq-cz-orphan-scan` — Скан ЧЗ попал в «сироты».

**`add_26_seed_3.sql` — Лаборатория и Advisor (5 статей):**
- ✅ `faq-lab-blocked-batch` — Партия заблокирована лабораторией.
- ✅ `faq-route-mismatch` — Advisor: ROUTE_MISMATCH.
- ✅ `faq-cooling-degradation` — Advisor: COOLING_DEGRADATION.
- ✅ `faq-cz-incomplete` — Advisor: CZ_INCOMPLETE.
- ✅ `faq-underload` — Advisor: UNDERLOAD.

**3. Единый формат статьи:**
- ✅ **Категория** — FAQ.
- ✅ **Симптом** — что видит пользователь.
- ✅ **Причина** — почему так происходит.
- ✅ **Что делать** — варианты решения (по приоритету).
- ✅ **Проверка** — SQL-запросы для диагностики.
- ✅ **Связанные статьи** — ссылки на 2-3 других статьи.

**4. Тесты (+24, всего 678):**
- ✅ `test_help_faq.py` (24):
  - Категория FAQ в `help.py` (5).
  - Файлы миграций (3).
  - Содержимое seed-файлов (4).
  - 15 FAQ-статей (5).
  - Ссылки на статьи (3).
  - API структурные (3).
  - Sanity (2).

**Ключевые гарантии:**
- ✅ **15 статей** покрывают топ-15 проблем пользователей.
- ✅ **Единый формат** — Симптом → Причина → Что делать.
- ✅ **SQL-запросы** для диагностики в каждой статье.
- ✅ **Ссылки на статьи** — перекрёстная навигация.
- ✅ **Идемпотентность** — `ON CONFLICT (slug) DO NOTHING`.
- ✅ **Обратная совместимость** — API `/categories` возвращает `faq`
  как обычную категорию.

### Changed

- Версия проекта: `4.5.0` → `4.6.0`.
- `help.py` — `CATEGORY_LABELS` + `CATEGORY_ORDER` содержат `faq`.
- Total категорий справки: **8 → 9**.
- Total статей справки: **15 → 30**.

---

## [4.5.0] — 2026-10-02

Итерация 15.2 — контекстные подсказки.

### Added

#### Итерация 15.2 — Контекстные подсказки

**Проблема:**
Даже с встроенной справкой (Итерация 15.1) пользователь не всегда знает,
что делает конкретная кнопка или флаг. Приходится уходить в раздел «Помощь»,
искать статью, читать её — теряя контекст.

**Решение:**

**1. База данных (миграция `add_25.sql`):**
- ✅ Таблица `help_hint`:
  - `hint_key` (UNIQUE) — идентификатор вида `planning.recalc`.
  - `title`, `body_md` (TEXT) — заголовок и короткое markdown-тело.
  - `article_slug` (nullable) — ссылка на полную статью справки.
  - `display_order`, `is_published`.
  - `organization_id` (nullable — глобальные подсказки).
- ✅ Триггер `help_hint_set_updated_at`.
- ✅ Индексы: `idx_help_hint_published`, `idx_help_hint_org`.

**2. Seed-миграция (`add_25_seed.sql`):**
- ✅ 8 стартовых подсказок:
  - `planning.recalc`, `planning.advisor`, `planning.plan_dirty`
  - `gantt.edit_mode`, `gantt.brackets`
  - `shift.lab_block`
  - `whatif.json`
  - `settings.system`
- ✅ Все привязаны к статьям справки из `add_24_seed_*`.
- ✅ Идемпотентна (`ON CONFLICT (hint_key) DO NOTHING`).

**3. Backend:**
- ✅ Модуль `help_models.py` — новые Pydantic-модели:
  - `HelpHint`, `HelpHintsResponse`.
- ✅ Модуль `help.py` — новый эндпоинт:
  - `GET /api/v1/help/hints` — возвращает словарь `{hint_key: HelpHint}`.

**4. Frontend:**
- ✅ `HelpHintsContext.tsx` — глобальный кэш подсказок:
  - Загрузка один раз при монтировании приложения.
  - Методы `getHint()`, `useHint()`.
  - Тихий fail: если запрос упал — подсказки не блокируют UI.
- ✅ `Hint.tsx` — компонент иконки `?` с Popover:
  - Иконка `HelpOutlineIcon` 14/18px.
  - Markdown-рендер (react-markdown + remark-gfm).
  - Кнопка «Читать подробнее» — переход на `/help/{slug}`.
  - Возвращает `null`, если подсказки нет.
- ✅ `App.tsx` — провайдер `HelpHintsProvider` обёрнут вокруг `BrowserRouter`.
- ✅ `types/index.ts` — типы `HelpHint`, `HelpHintsResponse`.
- ✅ `api.ts` — `helpApi.getHints()`.
- ✅ Интеграция в 5 страниц (8 подсказок):
  - `SchedulePage.tsx`: planning.recalc, planning.advisor, planning.plan_dirty.
  - `GanttPage.tsx`: gantt.edit_mode, gantt.brackets.
  - `ShiftPage.tsx`: shift.lab_block.
  - `WhatIfPage.tsx`: whatif.json.
  - `PlanSettingsWizard.tsx`: settings.system.

**5. Тесты (+27, всего 654):**
- ✅ `test_help_hints.py` (27):
  - Pydantic-модели (8).
  - Эндпоинт `/hints` (5).
  - Миграция `add_25.sql` (7).
  - Seed-файл (3).
  - Sanity (4).

**Ключевые гарантии:**
- ✅ **Не уходя со страницы** — подсказка открывается в Popover.
- ✅ **Короткий текст** — 2-3 предложения, чтобы не отвлекать.
- ✅ **Ссылка на статью** — для тех, кому нужно подробнее.
- ✅ **Обратная совместимость** — если подсказки нет в БД, `<Hint/>` рендерит null.
- ✅ **Кэширование** — 1 запрос при загрузке приложения на все подсказки.
- ✅ **Не критично** — ошибка загрузки подсказок не ломает UI.

### Fixed

- **Итерация 15.2 (fix):** контекстные подсказки не отображались в нескольких
  местах UI.
  - `frontend/src/pages/SchedulePage.tsx` — добавлены 3 подсказки:
    `planning.recalc`, `planning.advisor`, `planning.plan_dirty`.
  - `frontend/src/components/gantt/GanttToolbar.tsx` — добавлена подсказка
    `planning.recalc` рядом с кнопкой «Пересчитать» (🔄).

### Changed

- Версия проекта: `4.4.0` → `4.5.0`.
- `help_models.py` — добавлены модели `HelpHint`, `HelpHintsResponse`.
- `help.py` — добавлен эндпоинт `GET /hints`.
- `App.tsx` — обёрнут в `HelpHintsProvider`.
- `types/index.ts` — типы для подсказок.
- `api.ts` — метод `helpApi.getHints()`.
- 5 страниц получили встроенные `<Hint/>`.

---

## [4.4.0] — 2026-10-02

Итерация 15.1 — встроенная справка пользователя.

### Added

#### Итерация 15.1 — Встроенная справка пользователя

**Проблема:**
Пользователь, впервые открывший систему, не понимает, что делать.
Документация — в `docs/*.md`, но она для разработчиков. Нужна
встроенная справка прямо в UI.

**Решение:**

**1. База данных (миграция `add_24.sql`):**
- ✅ Таблица `help_article`:
  - `slug` (UNIQUE) — идентификатор для URL.
  - `title`, `category`, `content_md` (TEXT).
  - `tags` (JSONB-массив).
  - `display_order`, `is_published`.
  - `organization_id` (nullable — глобальные статьи).
- ✅ Триггер `help_article_set_updated_at`.
- ✅ Индексы: `idx_help_article_category`, `idx_help_article_tags` (GIN).

**2. Seed-миграции (`add_24_seed_1/2/3.sql`):**
- ✅ 15 стартовых статей в 8 категориях.
- ✅ Категории: `getting-started` (2), `planning` (4), `gantt` (4),
  `shift` (1), `lab` (1), `cz` (1), `whatif` (1), `settings` (1).
- ✅ Идемпотентны (`ON CONFLICT (slug) DO NOTHING`).
- ✅ Markdown в dollar-quoted strings (`$md$...$md$`).

**3. Backend:**
- ✅ Модуль `help_models.py` — Pydantic-модели:
  - `HelpArticleListItem`, `HelpArticleResponse`.
  - `HelpCategoriesResponse`, `HelpCategoryResponse`.
  - `HelpArticlesListResponse`.
  - `HelpSearchHit`, `HelpSearchResponse`.
- ✅ Модуль `help.py` — 4 эндпоинта:
  - `GET /api/v1/help/articles` — список статей (с фильтром по категории).
  - `GET /api/v1/help/articles/{slug}` — одна статья.
  - `GET /api/v1/help/categories` — список категорий с количеством.
  - `GET /api/v1/help/search?q=...` — поиск по title / content / tags.
- ✅ Модуль `help_docs.py` — отдача `docs/*.md`:
  - `GET /api/v1/help/docs/{filename}`.
  - Защита от path traversal (`/`, `\`, `..`).
  - Ограничение размера 1 МБ.
  - Только `.md`.
- ✅ Подключение в `main.py`:
  - `from app.api.v1.help import router as help_router`
  - `from app.api.v1.help_docs import router as help_docs_router`
  - `{"name": "Справка"}` в `tags_metadata`.
  - `app.include_router(help_router)`
  - `app.include_router(help_docs_router)`

**4. Frontend:**
- ✅ `npm install react-markdown@^9.0.1 remark-gfm@^4.0.0`.
- ✅ `helpApi` в `api.ts` — 5 методов:
  - `listArticles(category?)`, `getArticle(slug)`, `listCategories()`,
    `search(q, limit)`, `getDocFile(filename)`.
- ✅ Типы `HelpArticle`, `HelpArticleListItem`, `HelpCategory`,
  `HelpCategoriesResponse`, `HelpArticlesListResponse`,
  `HelpSearchHit`, `HelpSearchResponse`, `HelpDocFileResponse`.
- ✅ `HelpSidebar.tsx` — левая панель:
  - Поиск с debounce 300 мс.
  - Категории в аккордеонах.
  - При активном поиске — список найденных статей с сниппетами.
- ✅ `HelpArticleView.tsx` — markdown-рендер:
  - `react-markdown` + `remark-gfm`.
  - Кастомные компоненты для таблиц, кода, цитат.
  - Внутренние ссылки `/help/slug` перехватываются и открывают
    статьи внутри приложения.
- ✅ `HelpPage.tsx` — страница:
  - Двухпанельный layout через `Allotment`.
  - Роуты `/help` (редирект на `/help/intro-overview`) и `/help/:slug`.
- ✅ `MainLayout.tsx` — пункт меню «Помощь» с иконкой `HelpOutlined`.
- ✅ `App.tsx` — 2 роута для `/help` и `/help/:slug`.

**5. Тесты (+36, всего 601 → 627 после 15.2):**
- ✅ `test_help.py` (36):
  - Pydantic-модели (7).
  - Константы категорий (3).
  - Хелперы `_parse_tags`, `_make_snippet` (8).
  - Структура модулей (4).
  - Безопасность `help_docs` (3).
  - Миграция `add_24.sql` (6).
  - Seed-файлы (3).
  - Регистрация в `main.py` (2).

**6. ADR:**
- ✅ `docs/adr/0005-help-system.md` — обоснование выбора
  markdown-статей в PostgreSQL.

**Ключевые гарантии:**
- ✅ **15 статей** покрывают 80% сценариев.
- ✅ **Поиск** работает по title, content, tags.
- ✅ **Markdown-рендер** с таблицами и кодом.
- ✅ **Внутренние ссылки** — переход между статьями.
- ✅ **Отдача `docs/*.md`** — техническая документация.
- ✅ **Обратная совместимость** — read-only эндпоинты.

### Changed

- Версия проекта: `4.3.0` → `4.4.0`.
- `main.py` — подключены `help_router`, `help_docs_router`.
- `MainLayout.tsx` — пункт меню «Помощь».
- `App.tsx` — роуты `/help`, `/help/:slug`.
- `api.ts` — модуль `helpApi` (5 методов).
- `types/index.ts` — 8 новых типов для справки.

---

## [4.3.0] — 2026-10-02

Итерация 14.2 — редактирование плана прямо на Ганте.

### Added

#### Итерация 14.2 — Редактирование плана прямо на Ганте

**Проблема:**
Если план был **открыт** (через кнопку 👁️ на странице «Планирование»),
диаграмма Ганта переходила в режим **readonly** (`🔒 Просмотр`).
Задачи **не перетаскивались**, длительность **не менялась**. Чтобы
что-то поправить — приходилось закрывать план, терять контекст и
пересчитывать заново.

**Решение:**

**1. Глобальный режим редактирования:**
- ✅ Новый стейт `localEditMode` в `PlanContext`:
  - `false` — readonly.
  - `true` — редактирование разрешено.
- ✅ Синхронизация с `currentVersionId`.
- ✅ `isReadOnly = !localEditMode` в `GanttPage`.

**2. Переключатель режима в тулбаре Ганта:**
- ✅ Компактный `ToggleButtonGroup` `🔒 / ✏️`.
- ✅ Активная кнопка — синяя (`#3498db`).

**3. Синхронизация иконки в шапке приложения:**
- ✅ `MainLayout` берёт `localEditMode` из `usePlan()`.
- ✅ Условный рендер чипа (🔒/✏️).

**4. Кнопка «Пересчитать» — доступна всегда:**
- ✅ Рендерится, если передан `onRecalculate`.
- ✅ Активна только при `planDirty === true`.

**5. Удалён дублирующий Chip с названием плана.**

**6. Фикс рендера скобок партий** — защита от отрицательной ширины.

**7. `useGanttTimeline` учитывает `localEditMode`.**

**8. `GanttPage` — ре-рендер Timeline при смене режима.**

### Changed

- Версия проекта: `4.2.0` → `4.3.0`.

### Fixed

- **Проблема:** при открытии плана задачи не перетаскивались.
- **Решение:** глобальный `localEditMode` + переключатель в тулбаре.
- **Проблема:** `<rect> attribute width: A negative value is not valid`.
- **Решение:** защита от отрицательной ширины в `drawBatchBrackets`.

---

## [4.2.0] — 2026-09-29

Итерация 13.21 — архивация версий планов.

### Added

- Поле `schedule_version.is_archived`.
- Partial-индекс `idx_schedule_version_archived`.
- Настройка `auto_archive_on_recalc`.
- `ScheduleSaver._archive_version`, `_check_version_usage`.
- `RescheduleRequest.replace_version_id`.
- `PUT /api/v1/schedule/versions/{id}/unarchive`.
- UI: Tree Data в «Истории планов», чекбокс «Показать архивные».
- Снекбар после пересчёта в `GanttPage`.

**Тесты (+28, всего 563):** `test_schedule_versions_archive.py`.

---

## [4.1.2] — 2026-09-29

Итерация 13.20 — `RecalcProgressDialog`.

---

## [4.1.1] — 2026-09-25

Итерация 13.15 — снапшоты при создании плана.

### Added

- Модуль `snapshot.py` — `snapshot_all_catalogs`.
- `POST /versions` заполняет снапшоты.
- `has_snapshot` в ответах API.
- Индикация ⚠ в UI для планов без снапшотов.

**Тесты (+43, всего 535).**

---

## [4.1.0] — 2026-09-25

Итерации 13.14 и 13.14.1 — `plan_settings`.

### Added

- Таблица `plan_settings` (миграция `add_21.sql`).
- Триггер `copy_app_settings_to_plan`.
- `DataLoader(version_id=...)`, `ProductionScheduler(version_id=...)`.
- `settings_reader.py` — 3 функции с `version_id`.
- API `/api/v1/plan-settings` — 3 эндпоинта.
- `PlanSettingsWizard.tsx` — 9 шагов.

**Тесты (+171, всего 492).**

---

## [4.0.0] — 2026-09-24

Итерации 12 и 13.3.

### Added

- **Multi-objective** — модуль `optimization.py`, 5 компонентов.
- **What-if сценарии** — `whatif.py`, таблица `whatif_scenario`.
- **Аудит** — `/api/v1/audit`, `AuditPage.tsx`.

---

## [3.0.0]

Итерации 5–11.

### Added

- Лаборатория, люди как ресурс, охлаждение, ЧЗ, рефакторинг,
  календарная постобработка, режимы смен, `app_settings`.

---

## [2.0.0]

Итерации 2–4.

### Added

- Материальные ограничения и Advisor, сменное планирование,
  перепланирование.

---

## [1.0.0]

Итерации 0–1.

### Added

- Фундамент, цепочки рабочих центров.

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