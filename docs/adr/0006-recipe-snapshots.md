# 0006. Recipe snapshots for versioning

**Дата:** 2026-10-12
**Статус:** Принято
**Контекст:** Итерация 17.2

---

## Контекст

Система APS Production Scheduler уже использует снапшоты для версионирования
справочников (см. [ADR 0002](0002-snapshot-tables-for-versioning.md)):
`equipment_snapshot`, `product_snapshot`, `operation_snapshot`,
`calendar_snapshot`. Каждая версия плана получает «слепок» справочников
на момент создания/расчёта.

Однако **рецептуры (`recipe`, `recipe_item`) в этот механизм не входили**.
Это приводило к проблеме: при открытии сохранённой версии плана список
рецептов всегда читался из **живых** таблиц. Если пользователь редактировал
рецепт **после** создания версии — история искажалась.

**Пример:**
1. Создали план на 01.10.2026.
2. В составе рецепта `PF_ANTISEPTIC` компонент `CHLORIDE` имел
   `qty_per_base = 5`.
3. 05.10.2026 пользователь изменил `qty_per_base` на `15`.
4. Открыли версию плана от 01.10.2026 → раздел «Рецептуры».
5. В составе отображается `CHLORIDE = 15` — **неверно**, потому что
   на момент расчёта плана было `5`.

**Требования:**
- Версия плана должна воспроизводиться: зная `version_id`, всегда
  можно получить тот же состав рецепта.
- Редактирование рецепта в текущем плане **не должно** влиять на
  сохранённые версии.
- Обратная совместимость: старые версии (до миграции) работают без падения,
  даже если рецепт в них недоступен.
- Снапшот рецепта **имутабелен**: ссылочные записи в живых таблицах могут
  быть удалены, но снапшот остаётся.
- Мульти-тенантность: снапшот привязан к `organization_id`.

---

## Решение

Создать **две снапшот-таблицы** по аналогии с `product_snapshot`:
- `recipe_snapshot` — снапшот шапок рецептов;
- `recipe_item_snapshot` — снапшот компонентов рецептов.

### Структура (миграция `add_29_recipe_snapshots.sql`)

```sql
CREATE TABLE IF NOT EXISTS recipe_snapshot (
    id              UUID           NOT NULL,
    organization_id UUID,
    product_id      UUID           NOT NULL,
    base_volume_kg  NUMERIC(10,2)  NOT NULL,
    comment         TEXT,
    version_id      UUID           NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_ver
    ON recipe_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_org_ver
    ON recipe_snapshot(organization_id, version_id);

CREATE TABLE IF NOT EXISTS recipe_item_snapshot (
    id           UUID           NOT NULL,
    recipe_id    UUID           NOT NULL,
    material_id  UUID           NOT NULL,
    qty_per_base NUMERIC(10,3)  NOT NULL,
    version_id   UUID           NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_ver
    ON recipe_item_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_recipe_ver
    ON recipe_item_snapshot(recipe_id, version_id);
```

### Ключевые архитектурные решения

**1. Составной PK `(id, version_id)`.**

Один и тот же рецепт может быть в снапшотах разных версий. PK составной —
как у `product_snapshot`.

**2. FK на `schedule_version` с `ON DELETE CASCADE`.**

При удалении версии снапшоты удаляются автоматически. Соответствует
паттерну `product_snapshot`.

**3. FK на `product` и `material` — отсутствуют.**

Это **сознательное** решение. Снапшот имутабелен:
- Если продукт/материал удалён в живых таблицах, снапшот должен
  остаться валидным.
- Если FK оставить с `ON DELETE CASCADE` — удаление продукта «снесёт»
  снапшот во всех версиях (потеря воспроизводимости).
- Если FK оставить без CASCADE — удаление продукта станет невозможным
  (каскадная блокировка).
- При чтении `product_name` / `material_name` подтягиваются через
  `LEFT JOIN` к живым таблицам. Если продукт удалён — `product_name = NULL`.

**Компромисс:** имя продукта/материала в снапшоте **не сохраняется**.
Это означает, что при переименовании материала в старой версии
отобразится **новое** имя. Для полного решения этой проблемы нужен
`material_snapshot` (отдельная задача на Итерацию 18+).

**4. Заполнение в `snapshot_all_catalogs`.**

Единая точка: `backend/app/scheduler/snapshot.py`. Вызывается из:
- `POST /api/v1/schedule/versions` — при создании пустого плана;
- `ScheduleSaver._do_save` — при сохранении рассчитанного плана.

Код:
```python
# Блок 5: recipe → recipe_snapshot
INSERT INTO recipe_snapshot
    (id, organization_id, product_id, base_volume_kg, comment, version_id)
SELECT id, organization_id, product_id, base_volume_kg, comment, :version_id
FROM recipe
WHERE organization_id = :org_id
ON CONFLICT (id, version_id) DO NOTHING

# Блок 6: recipe_item → recipe_item_snapshot
INSERT INTO recipe_item_snapshot
    (id, recipe_id, material_id, qty_per_base, version_id)
SELECT ri.id, ri.recipe_id, ri.material_id, ri.qty_per_base, :version_id
FROM recipe_item ri
JOIN recipe r ON r.id = ri.recipe_id
WHERE r.organization_id = :org_id
ON CONFLICT (id, version_id) DO NOTHING
```

`ON CONFLICT (id, version_id) DO NOTHING` делает функцию идемпотентной —
повторный вызов безопасен.

**5. Чтение — через параметр `version_id`.**

`GET /api/v1/recipes/?version_id=<UUID>`:
- Если `version_id` задан → `recipe_snapshot` / `recipe_item_snapshot`.
- Если не задан → `recipe` / `recipe_item`.

Реализация — динамический выбор имени таблицы:
```python
if version_id:
    recipe_table = "recipe_snapshot"
    item_table = "recipe_item_snapshot"
    version_filter = "AND r.version_id = :version_id"
else:
    recipe_table = "recipe"
    item_table = "recipe_item"
    version_filter = ""
```

**6. Мутации — только с живыми таблицами.**

`POST`, `PUT`, `DELETE` в `recipes.py` работают только с
`recipe` / `recipe_item`. В режиме версии UI скрывает элементы
редактирования (`isReadOnly = true` в `RecipesPage.tsx`), поэтому
конфликта не возникает.

**7. Frontend передаёт `currentVersionId`.**

`RecipesPage.loadData` формирует `recipesParams = { params: { version_id: currentVersionId } }`,
если `currentVersionId` не `null`. `useEffect` уже зависит от
`currentVersionId` — при переключении версий список перезагружается.

---

## Последствия

### Положительные

- ✅ **Воспроизводимость** — зная `version_id`, всегда получаем тот же
  состав рецепта.
- ✅ **Имутабельность** — редактирование живого рецепта не влияет на
  уже сохранённые версии.
- ✅ **Мульти-тенантность** — снапшот содержит `organization_id`.
- ✅ **CASCADE DELETE** — при удалении версии снапшоты чистятся
  автоматически.
- ✅ **Обратная совместимость** — `GET /recipes/` без `version_id`
  работает как раньше.
- ✅ **Единый паттерн** — `snapshot_all_catalogs` расширен двумя блоками,
  никаких новых вызовов или сервисов.
- ✅ **Идемпотентность** — `ON CONFLICT (id, version_id) DO NOTHING`.
- ✅ **Простота UI** — `RecipesPage.tsx` уже знает о `currentVersionId`
  (используется для `isReadOnly`), нужна всего одна строка в `loadData`.

### Отрицательные

- ⚠️ **Материалы не версионируются.** `material_name` / `material_code` /
  `material_unit` подтягиваются через `LEFT JOIN material` — живые данные.
  Если материал переименован после снапшота, в старой версии отобразится
  **новое** имя. Решение — `material_snapshot` (отдельная задача).
- ⚠️ **Продукты не версионируются.** Аналогично: `product_name` /
  `product_code` через `LEFT JOIN product`.
- ⚠️ **Старые версии без снапшота.** Версии, созданные до применения
  миграции `add_29_recipe_snapshots.sql`, имеют **пустые** снапшоты
  рецептов. При открытии такой версии в разделе «Рецептуры» —
  **пустой список**. Нужна новая версия.
- ⚠️ **Нет backfill для старых версий.** Миграция не может восстановить
  состав рецепта на момент создания старой версии — данных просто нет.
- ⚠️ **Дублирование данных.** Каждая версия хранит полный состав рецептов.
  При большом количестве версий растёт объём БД.
- ⚠️ **Проверки целостности.** Так как FK на `product` / `material` убраны,
  БД не гарантирует, что `product_id` / `material_id` в снапшоте ссылаются
  на существующие записи. Это осознанный компромисс.

### Альтернативы

#### 1. JSONB-снапшот в `schedule_version`

**Идея:** добавить колонку `recipes_snapshot JSONB` в `schedule_version`.

**Плюсы:**
- Нет отдельных таблиц.
- Просто.

**Минусы:**
- ❌ **Нет валидации** на уровне БД (нет FK, нет NOT NULL).
- ❌ **Сложные запросы** — для чтения конкретного рецепта нужно
  разбирать JSONB в приложении.
- ❌ **Нет индексов** на отдельные поля (например, `product_id`).
- ❌ **Не масштабируется** — при 100 рецептах JSONB станет многомегабайтным.
- ❌ **Противоречит существующему паттерну** — `product_snapshot` и другие
  сделаны реляционными.

**Почему отклонён:** нет валидации, сложные запросы, не соответствует
уже принятому паттерну.

---

#### 2. Версионирование через `valid_from` / `valid_to` в живых таблицах

**Идея:** добавить колонки `valid_from TIMESTAMPTZ`, `valid_to TIMESTAMPTZ`
в `recipe` и `recipe_item`. Каждое изменение создаёт новую строку с новым
интервалом валидности.

**Плюсы:**
- Единый источник правды.
- Нет дублирования структуры.

**Минусы:**
- ❌ **Усложняет все запросы**: `WHERE valid_from <= :ts AND (valid_to IS NULL OR valid_to > :ts)`.
- ❌ **Усложняет планировщик**: `data_loader.py` должен передавать
  нужную дату в каждый запрос.
- ❌ **Проблемы с FK**: `recipe_item.recipe_id → recipe.id` — при версионировании
  `recipe.id` меняется, а `recipe_item` ссылается на старую версию. Нужны
  составные ключи или переработка схемы.
- ❌ **Проблемы с производительностью**: индексы на временные интервалы менее
  эффективны, чем на `(id, version_id)`.
- ❌ **Сложность UI**: нужно показывать историю изменений.

**Почему отклонён:** сложность, несовместимость с текущей схемой.

---

#### 3. Отдельная БД для каждой версии

**Идея:** каждая версия плана — отдельная БД со своими рецептами.

**Плюсы:**
- Полная изоляция.

**Минусы:**
- ❌ **Огромная сложность** — управление соединениями, миграциями.
- ❌ **Не масштабируется** — 100 версий = 100 БД.
- ❌ **Проблемы с бэкапами** — нужно бэкапить каждую БД.
- ❌ **Несовместимо с мульти-тенантностью**.

**Почему отклонён:** избыточно, не масштабируется.

---

#### 4. Отдельные схемы PostgreSQL

**Идея:** каждая версия плана — отдельная схема (`schema`) в PostgreSQL.

**Плюсы:**
- Изоляция.
- Rollback через `DROP SCHEMA`.

**Минусы:**
- ❌ **DDL в транзакции** — не работает стабильно с async SQLAlchemy.
- ❌ **Проблемы с внешними ключами** между схемами.
- ❌ **Сложность миграций** — нужно дублировать схему N раз.
- ❌ **Не масштабируется** — 100 версий = 100 схем.

**Почему отклонён:** DDL в транзакции, сложность.

---

#### 5. Soft-delete + audit log

**Идея:** не удалять старые версии рецептов, а помечать `is_deleted = TRUE`.
Логировать изменения в audit log.

**Плюсы:**
- Нет дублирования структуры.
- Полная история.

**Минусы:**
- ❌ **Сложность запросов** — везде учитывать `is_deleted`.
- ❌ **Не решает проблему полностью** — при изменении `qty_per_base` старая
  строка не сохраняется, если не логировать каждое поле.
- ❌ **Раздувание таблиц** — каждая версия рецепта = новая строка.
- ❌ **Несовместимо с существующим паттерном снапшотов**.

**Почему отклонён:** сложность, не решает воспроизводимость полностью.

---

## Ссылки

- [ADR 0002: Snapshot tables for versioning](0002-snapshot-tables-for-versioning.md)
- [ADR 0003: Plan settings per plan](0003-plan-settings-per-plan.md)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — раздел «Версионирование рецептур».
- [docs/API.md](../API.md) — раздел «Рецептуры (расширение)».
- [docs/OPERATIONS.md](../OPERATIONS.md) — раздел «Снапшоты рецептур».
- [README.md](../../README.md) — основная документация.