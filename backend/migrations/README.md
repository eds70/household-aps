# Миграции БД — APS Production Scheduler

Каталог содержит **историю изменений схемы БД** после базового релиза `v1.0.0`.

Все миграции **идемпотентны** — повторное применение безопасно (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `CREATE OR REPLACE`).

---

## ⚠️ Как применять

**Правильный способ** (через `docker cp` + `psql -f`):

```bash
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
```

**❌ НЕ использовать** `Get-Content | docker exec` — PowerShell испортит кириллицу.

---

## Список миграций

| Файл | Итерация | Что делает |
|------|----------|------------|
| `add_history_0_2.sql` | 0–2 | Склейка add_01..add_05: `organization_settings`, feature-флаги, `product.route_type`, `equipment.code`, 28 партий, включение материальных ограничений |
| `add_06.sql` | 3 | Сменное планирование: таблица `shift`, поля `shift_id`/`actual_qty`/`material_load_at`/`status` в `scheduled_task`, 30 смен на сентябрь 2026 |
| `add_06b.sql` | 3 | Снапшот-таблицы: колонки `code`, `route_type`, `operator_pool` |
| `add_07.sql` | 4 | Перепланирование: `schedule_version.frozen_before`, `schedule_version.parent_version_id`, таблица `reschedule_log` |
| `fix_versions_hotfix.sql` | 5h | Hotfix: деактивация старых версий плана (оставляем только последнюю `is_active = TRUE`) |
| `add_08.sql` | 5 | Лаборатория: поля `is_lab_blocked`/`lab_status`/`lab_block_reason`/`lab_blocked_at`/`lab_blocked_by` в `batch`, таблица `lab_analysis_log` |
| `add_09.sql` | 6 | Пулы операторов: `REACTOR_OPERATOR`, `LINE_OPERATOR`, `MANUAL_OPERATOR`, feature-флаги |
| `add_09b.sql` | 6 | Базовые пулы: `COOLING_ZONE`, `BOILER`, `LAB` |
| `add_09c.sql` | 6 | Колонка `resource_pool.updated_at` |
| `add_09d.sql` | 6 | Колонка `scheduled_task.operator_pool` |
| `add_10.sql` | 7 | Охлаждение: feature-флаг `enable_cooling_degradation`, `cooling_degradation_factor = 1.3` |
| `add_10b.sql` | 7 | Колонка `scheduled_task.cooling_mode` (`fast`/`slow`/`NULL`) |
| `add_11.sql` | 8 | Честный Знак: поля `cz_marked_qty`/`cz_last_scan_at`/`cz_status` в `batch`, таблица `cz_scan_log`, настройки ЧЗ |
| `add_12.sql` | 10 | Колонка `scheduled_task.operation_name` (фактическое имя операции) |
| `add_13.sql` | 11 | Централизованные настройки: таблица `app_settings`, перенос из `organization_settings` |
| `add_14.sql` | 11 | Настройка `allow_weekend_work` (работа в выходные) |
| `add_15.sql` | 12 | Веса multi-objective: `weight_makespan`, `weight_setup`, `weight_underload`, `weight_cooling_slow`, `weight_tardiness` |
| `add_16.sql` | 12 | What-if сценарии: таблица `whatif_scenario` |
| `add_17.sql` | 13.1 | UNIQUE-констрейнт `material_stock (organization_id, material_id)` |
| `add_18.sql` | 13.2 | Журнал остатков: таблица `material_stock_log`, триггер `log_material_stock_change()` |
| `add_19.sql` | 13.4 | TANK_2 для крем-мыла 5л (связи Р2 → TANK_2 → LINE_2) |
| `add_20.sql` | 13.6 | Колонка `scheduled_task.depends_on_task_ids` (связи между задачами на Ганте) |
| `add_21.sql` | 13.14 | Таблица `plan_settings` (снапшот настроек для плана), триггер `copy_app_settings_to_plan` |
| `add_22.sql` | 13.17 | Индексы для каскадного сдвига: `idx_scheduled_task_equipment_time`, `idx_scheduled_task_version_deps` |
| `add_23.sql` | 13.21 | Архивация версий планов: колонка `schedule_version.is_archived`, partial-индекс `idx_schedule_version_archived`, настройка `auto_archive_on_recalc`, одноразовая миграция неактивных версий в архив |
| `add_24.sql` | 15.1 | Встроенная справка: таблица `help_article` (slug, title, category, content_md, tags JSONB, display_order, is_published), индексы `idx_help_article_category`, `idx_help_article_tags` (GIN), триггер `trg_help_article_updated_at` |
| `add_24_seed_1.sql` | 15.1 | 3 статьи справки: `intro-overview`, `intro-first-plan`, `planning-build-plan` |
| `add_24_seed_2.sql` | 15.1 | 5 статей справки: `planning-history`, `planning-recalculate`, `planning-advisor`, `gantt-overview`, `gantt-editing` |
| `add_24_seed_3.sql` | 15.1 | 7 статей справки: `gantt-grouping`, `gantt-filters`, `shift-overview`, `lab-blocks`, `cz-overview`, `whatif-overview`, `settings-app-vs-plan` |
| `add_25.sql` | 15.2 | Контекстные подсказки: таблица `help_hint` (hint_key UNIQUE, title, body_md, article_slug, display_order, is_published), индексы `idx_help_hint_published`, `idx_help_hint_org`, триггер `trg_help_hint_updated_at` |
| `add_25_seed.sql` | 15.2 | 8 подсказок: `planning.recalc`, `planning.advisor`, `planning.plan_dirty`, `gantt.edit_mode`, `gantt.brackets`, `shift.lab_block`, `whatif.json`, `settings.system` |
| `add_26_seed_1.sql` | 15.4 | FAQ: планирование (5 статей): `faq-plan-feasible-not-optimal`, `faq-task-not-movable`, `faq-plan-is-empty`, `faq-plan-settings-empty`, `faq-material-shortage` |
| `add_26_seed_2.sql` | 15.4 | FAQ: гант, смены, what-if, ЧЗ (5 статей): `faq-move-pinned-task`, `faq-old-version-not-archived`, `faq-shift-mode-change`, `faq-whatif-running`, `faq-cz-orphan-scan` |
| `add_26_seed_3.sql` | 15.4 | FAQ: лаборатория, advisor (5 статей): `faq-lab-blocked-batch`, `faq-route-mismatch`, `faq-cooling-degradation`, `faq-cz-incomplete`, `faq-underload` |
| `add_27_seed_1.sql` | 15.3 | Туториал: статья `tutorial-interactive` в категории `getting-started` |
| `fix_shift_names.sql` | — | Hotfix: пересоздание смен с корректными именами (кириллица) |
| `fix_work_time.sql` | — | Hotfix: исправление `work_start_time` / `work_end_time` в `app_settings` |

---

## Когда применять

### Сценарий 1: Пустая БД (новая установка)

Применяйте **только** `init_schema.sql` + `seed_demo_data.sql`. Все миграции `add_06.sql`...`add_27_seed_1.sql` **уже включены** в актуальный `init_schema.sql` (v4.0.0).

```bash
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

### Сценарий 2: Апгрейд существующей БД (v1.x → v4.x)

Применяйте миграции по порядку:

```bash
$migrations = @(
    "add_history_0_2.sql",
    "add_06.sql", "add_06b.sql",
    "add_07.sql",
    "fix_versions_hotfix.sql",
    "add_08.sql",
    "add_09.sql", "add_09b.sql", "add_09c.sql", "add_09d.sql",
    "add_10.sql", "add_10b.sql",
    "add_11.sql",
    "add_12.sql",
    "add_13.sql",
    "add_14.sql",
    "add_15.sql",
    "add_16.sql",
    "add_17.sql",
    "add_18.sql",
    "add_19.sql",
    "add_20.sql",
    "add_21.sql",
    "add_22.sql",
    "add_23.sql",
    "add_24.sql", "add_24_seed_1.sql", "add_24_seed_2.sql", "add_24_seed_3.sql",
    "add_25.sql", "add_25_seed.sql",
    "add_26_seed_1.sql", "add_26_seed_2.sql", "add_26_seed_3.sql",
    "add_27_seed_1.sql",
    "fix_shift_names.sql",
    "fix_work_time.sql"
)

foreach ($m in $migrations) {
    Write-Host "Applying $m..."
    docker cp "backend/migrations/$m" "aps_postgres:/tmp/$m"
    docker exec -i aps_postgres psql -U aps -d household -f "/tmp/$m"
}
```

### Сценарий 3: Проверить, применена ли миграция

Например, для `add_21.sql` (plan_settings):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'plan_settings'
);
"
```

Если `t` — применена. Если `f` — нет.

**Для справки (15.1):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM help_article;
"
```

Ожидаемо: **31** (15 базовых + 1 туториал + 15 FAQ).

**Для подсказок (15.2):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM help_hint;
"
```

Ожидаемо: **8**.

**Для FAQ (15.4):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM help_article WHERE category = 'faq';
"
```

Ожидаемо: **15**.

**Для туториала (15.3):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM help_article WHERE slug = 'tutorial-interactive';
"
```

Ожидаемо: **1**.

**Для архивации (13.21):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'schedule_version' AND column_name = 'is_archived'
);
"
```

Ожидаемо: `t`.

---

## Что в какой миграции — краткий справочник

### Итерация 3 — Сменное планирование

- `add_06.sql` — таблица `shift`, поля в `scheduled_task`, 30 смен.
- `add_06b.sql` — снапшот-таблицы (equipment/product/operation).

### Итерация 4 — Перепланирование

- `add_07.sql` — `frozen_before`, `parent_version_id`, `reschedule_log`.

### Итерация 5 — Лаборатория

- `add_08.sql` — `batch.is_lab_blocked`, `batch.lab_status`, `lab_analysis_log`.
- `fix_versions_hotfix.sql` — деактивация старых версий.

### Итерация 6 — Люди как ресурс

- `add_09.sql` — пулы операторов.
- `add_09b.sql` — COOLING_ZONE / BOILER / LAB.
- `add_09c.sql` — `resource_pool.updated_at`.
- `add_09d.sql` — `scheduled_task.operator_pool`.

### Итерация 7 — Охлаждение

- `add_10.sql` — feature-флаг + коэффициент.
- `add_10b.sql` — `scheduled_task.cooling_mode`.

### Итерация 8 — Честный Знак

- `add_11.sql` — `batch.cz_*`, `cz_scan_log`, настройки ЧЗ.

### Итерация 10 — operation_name

- `add_12.sql` — `scheduled_task.operation_name`.

### Итерация 11 — Централизованные настройки

- `add_13.sql` — `app_settings`.
- `add_14.sql` — `allow_weekend_work`.

### Итерация 12 — Multi-objective и what-if

- `add_15.sql` — веса optimization.
- `add_16.sql` — `whatif_scenario`.

### Итерация 13.x

- `add_17.sql` — UNIQUE на `material_stock`.
- `add_18.sql` — журнал `material_stock_log`.
- `add_19.sql` — TANK_2.
- `add_20.sql` — `depends_on_task_ids`.
- `add_21.sql` — `plan_settings`.
- `add_22.sql` — индексы для каскадного сдвига (13.17).
- `add_23.sql` — архивация версий планов (13.21).

### Итерации 15.1–15.5 — Встроенная справка

- `add_24.sql` — таблица `help_article` (15.1).
- `add_24_seed_1/2/3.sql` — 15 статей справки (15.1).
- `add_25.sql` — таблица `help_hint` (15.2).
- `add_25_seed.sql` — 8 контекстных подсказок (15.2).
- `add_26_seed_1/2/3.sql` — 15 FAQ-статей (15.4).
- `add_27_seed_1.sql` — статья `tutorial-interactive` (15.3).

**Примечание:** Итерация 15.5 (редактирование статей через UI) **не
требует новых миграций** — использует существующую таблицу
`help_article` (из 15.1). CRUD-эндпоинты работают с ней на уровне API.

### Hotfix-миграции

- `fix_versions_hotfix.sql` — деактивация старых версий.
- `fix_shift_names.sql` — исправление кириллицы в именах смен.
- `fix_work_time.sql` — исправление `work_start_time` / `work_end_time`.

---

## Правила создания новой миграции

1. **Имя файла:** `add_NN.sql` (следующий номер) или `fix_<описание>.sql`.
2. **Обернуть в транзакцию:**

```sql
-- Итерация N: описание
BEGIN;

-- ... SQL ...

COMMIT;
```

3. **Сделать идемпотентной:**

```sql
CREATE TABLE IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;
INSERT INTO ... ON CONFLICT DO NOTHING;
```

4. **Применить:**

```bash
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
```

5. **Добавить тест:** `tests/test_<модуль>_migration.py`.

6. **Обновить этот README** (добавить строку в таблицу «Список миграций»).

7. **Обновить `CHANGELOG.md`** (секция `[Unreleased]`).

### Особенности seed-миграций справки (15.x)

Seed-миграции (`add_24_seed_*`, `add_25_seed`, `add_26_seed_*`,
`add_27_seed_1`) **не создают таблиц** — они только наполняют
существующие `help_article` / `help_hint`.

**Правила:**

- **Кириллица** — использовать dollar-quoted strings: `$md$...$md$`.
- **Только через `docker cp` + `psql -f`** — иначе PowerShell испортит
  кириллицу в `$md$...$md$`.
- **Идемпотентность** — `ON CONFLICT (slug) DO NOTHING` (или
  `ON CONFLICT (hint_key) DO NOTHING`).
- **Глобальные статьи** — `organization_id = NULL`.
- **Проверка после применения** — `SELECT COUNT(*) FROM help_article;`.

**Альтернатива для статей:** с Итерации 15.5 статьи можно создавать
и редактировать **через UI** (роль ADMIN) — без SQL-миграций. Seed-
миграции остаются для глобальных статей и для первоначального
наполнения БД.

---

## Ссылки

- [../../README.md](../../README.md) — основная документация проекта.
- [../init_schema.sql](../init_schema.sql) — актуальная схема БД (v4.0.0).
- [../seed_demo_data.sql](../seed_demo_data.sql) — демо-данные.
- [../../docs/OPERATIONS.md](../../docs/OPERATIONS.md) — операции с БД.
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — архитектура.
- [../../docs/DEVELOPMENT.md](../../docs/DEVELOPMENT.md) — руководство разработчика.