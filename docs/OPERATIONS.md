# Operations

Операции с базой данных, миграциями, бэкапами и мониторингом системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Все команды для БД](#все-команды-для-бд)
- [Применение миграций](#применение-миграций)
- [Бэкапы и восстановление](#бэкапы-и-восстановление)
- [Мониторинг](#мониторинг)
- [Проверка конкретных таблиц](#проверка-конкретных-таблиц)
- [Архивация версий планов (Итерация 13.21)](#архивация-версий-планов-итерация-1321)
- [Встроенная справка (Итерация 15.1)](#встроенная-справка-итерация-151)
- [Контекстные подсказки (Итерация 15.2)](#контекстные-подсказки-итерация-152)
- [Интерактивный туториал (Итерация 15.3)](#интерактивный-туториал-итерация-153)
- [FAQ (Итерация 15.4)](#faq-итерация-154)
- [Диагностика](#диагностика)

---

## Все команды для БД

### Проверить статус PostgreSQL

```bash
docker ps --filter "name=aps_postgres"
```

### Подключиться к БД

```bash
docker exec -it aps_postgres psql -U aps -d household
```

### Выйти из psql

```
\q
```

### Список таблиц

```bash
docker exec -i aps_postgres psql -U aps -d household -c "\dt"
```

### Список всех схем

```bash
docker exec -i aps_postgres psql -U aps -d household -c "\dn"
```

### Размер БД

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT pg_size_pretty(pg_database_size('household'));"
```

### Размер таблиц

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
"
```

### Активные соединения

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT pid, usename, application_name, state, query_start
FROM pg_stat_activity
WHERE datname = 'household'
ORDER BY query_start DESC;
"
```

### Убить зависший запрос

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT pg_terminate_backend(<pid>);"
```

---

## Применение миграций

### ⚠️ ВАЖНО

Применяйте SQL-файлы через `docker cp` + `psql -f`, а **не** через `Get-Content | docker exec` — иначе PowerShell испортит кириллицу.

### Правильный способ

```bash
docker cp backend/migrations/add_27_seed_1.sql aps_postgres:/tmp/add_27_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_27_seed_1.sql
```

### Неправильный способ (НЕ ИСПОЛЬЗОВАТЬ)

```bash
# ❌ PowerShell испортит кириллицу
Get-Content backend/migrations/add_27_seed_1.sql | docker exec -i aps_postgres psql -U aps -d household
```

### История миграций

| Файл | Итерация | Описание |
|------|----------|----------|
| `add_history_0_2.sql` | 0–2 | Базовая схема |
| `add_06.sql` | 6 | Пулы операторов |
| `add_06b.sql` | 6 | Дополнительные пулы |
| `add_07.sql` | 4 | Перепланирование |
| `add_08.sql` | 5 | Лаборатория |
| `fix_versions_hotfix.sql` | 5h | Деактивация старых версий |
| `add_09.sql` | 6 | Operator pool |
| `add_09b.sql` | 6 | Operator pool (продолжение) |
| `add_09c.sql` | 6 | Operator pool (продолжение) |
| `add_09d.sql` | 6 | Operator pool (продолжение) |
| `add_10.sql` | 7 | Охлаждение |
| `add_10b.sql` | 7 | `cooling_mode` |
| `add_11.sql` | 8 | Честный Знак |
| `add_12.sql` | 10 | `operation_name` |
| `add_13.sql` | 11 | `app_settings` |
| `add_14.sql` | 11 | `allow_weekend_work` |
| `add_15.sql` | 12 | Веса optimization |
| `add_16.sql` | 12 | `whatif_scenario` |
| `add_17.sql` | 13.1 | UNIQUE на `material_stock` |
| `add_18.sql` | 13.2 | Журнал `material_stock_log` |
| `add_19.sql` | 13.4 | TANK_2 |
| `add_20.sql` | 13.6 | `depends_on_task_ids` |
| `add_21.sql` | 13.14 | `plan_settings` |
| `add_22.sql` | 13.17 | Индексы для каскадного сдвига |
| `add_23.sql` | 13.21 | Архивация версий планов |
| `add_24.sql` | 15.1 | Таблица `help_article` |
| `add_24_seed_1.sql` | 15.1 | 3 статьи справки |
| `add_24_seed_2.sql` | 15.1 | 5 статей справки |
| `add_24_seed_3.sql` | 15.1 | 7 статей справки |
| `add_25.sql` | 15.2 | Таблица `help_hint` |
| `add_25_seed.sql` | 15.2 | 8 контекстных подсказок |
| `add_26_seed_1.sql` | 15.4 | FAQ: планирование (5 статей) |
| `add_26_seed_2.sql` | 15.4 | FAQ: гант, смены, what-if, ЧЗ (5 статей) |
| `add_26_seed_3.sql` | 15.4 | FAQ: лаборатория, advisor (5 статей) |
| **`add_27_seed_1.sql`** | **15.3** | **Туториал: статья `tutorial-interactive`** |
| `fix_shift_names.sql` | — | Исправление имён смен |
| `fix_work_time.sql` | — | Исправление work_start/end_time |

### Применить все миграции по порядку

```bash
$migrations = @(
    "add_06.sql", "add_06b.sql", "add_07.sql", "add_08.sql",
    "fix_versions_hotfix.sql",
    "add_09.sql", "add_09b.sql", "add_09c.sql", "add_09d.sql",
    "add_10.sql", "add_10b.sql", "add_11.sql", "add_12.sql",
    "add_13.sql", "add_14.sql", "add_15.sql", "add_16.sql",
    "add_17.sql", "add_18.sql", "add_19.sql", "add_20.sql",
    "add_21.sql", "add_22.sql", "add_23.sql",
    "add_24.sql", "add_24_seed_1.sql", "add_24_seed_2.sql", "add_24_seed_3.sql",
    "add_25.sql", "add_25_seed.sql",
    "add_26_seed_1.sql", "add_26_seed_2.sql", "add_26_seed_3.sql",
    "add_27_seed_1.sql",
    "fix_shift_names.sql", "fix_work_time.sql"
)

foreach ($m in $migrations) {
    Write-Host "Applying $m..."
    docker cp "backend/migrations/$m" "aps_postgres:/tmp/$m"
    docker exec -i aps_postgres psql -U aps -d household -f "/tmp/$m"
}
```

### Проверить, применена ли миграция

Например, для `add_23.sql` (архивация):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'schedule_version'
      AND column_name = 'is_archived'
);
"
```

Если `t` — применена. Если `f` — нет.

Для `add_24.sql` (справка):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'help_article'
);
"
```

Для `add_25.sql` (подсказки):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'help_hint'
);
"
```

Для `add_27_seed_1.sql` (туториал):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM help_article WHERE slug = 'tutorial-interactive'
);
"
```

### Пересоздать БД с нуля

```bash
docker exec aps_postgres psql -U aps -d household -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

**⚠️ Внимание:** это удалит все данные.

### Полная очистка (снести контейнер и БД)

```bash
docker rm -f aps_postgres
```

После этого — заново создать контейнер (см. [README.md](../README.md)).

---

## Бэкапы и восстановление

### Создать бэкап

```bash
docker exec aps_postgres pg_dump -U aps household > backup.sql
```

### Создать бэкап в custom-формате (сжатый)

```bash
docker exec aps_postgres pg_dump -U aps -Fc household > backup.dump
```

### Создать бэкап только схемы

```bash
docker exec aps_postgres pg_dump -U aps --schema-only household > schema.sql
```

### Создать бэкап только данных

```bash
docker exec aps_postgres pg_dump -U aps --data-only household > data.sql
```

### Восстановить из plain SQL

```bash
docker exec -i aps_postgres psql -U aps -d household < backup.sql
```

### Восстановить из custom-формата

```bash
docker cp backup.dump aps_postgres:/tmp/backup.dump
docker exec -i aps_postgres pg_restore -U aps -d household --clean --if-exists /tmp/backup.dump
```

### Восстановить в новую БД

```bash
docker exec aps_postgres psql -U aps -c "CREATE DATABASE household_restore;"
docker exec -i aps_postgres psql -U aps -d household_restore < backup.sql
```

### Автоматический бэкап (PowerShell)

```powershell
$date = Get-Date -Format "yyyy-MM-dd_HH-mm"
$backupDir = "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

docker exec aps_postgres pg_dump -U aps -Fc household > "$backupDir/household_$date.dump"

# Удалить бэкапы старше 30 дней
Get-ChildItem $backupDir -Filter "*.dump" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force

Write-Host "Backup created: $backupDir/household_$date.dump"
```

---

## Мониторинг

### Проверить статус backend

```bash
curl http://localhost:8000/docs
```

### Проверить статус frontend

```bash
curl http://localhost:5173
```

### Проверить логи backend

Backend логирует в stdout. Если запущен в терминале — смотрите вывод.

### Проверить логи PostgreSQL

```bash
docker logs aps_postgres --tail 100
```

### Следить за логами PostgreSQL в реальном времени

```bash
docker logs aps_postgres -f
```

### Проверить использование диска

```bash
docker exec aps_postgres df -h
```

### Проверить память

```bash
docker stats aps_postgres --no-stream
```

### Проверить долгие запросы

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 seconds'
ORDER BY duration DESC;
"
```

### Проверить размер БД

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    pg_size_pretty(pg_database_size('household')) AS db_size;
"
```

### Проверить количество задач в активной версии

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*)
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true;
"
```

---

## Проверка конкретных таблиц

### `schedule_version` (Итерации 4, 13.21)

**Полный список колонок:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'schedule_version'
ORDER BY ordinal_position;
"
```

**Общая статистика по версиям (Итерация 13.21):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    COUNT(*)                                             AS total_versions,
    COUNT(*) FILTER (WHERE is_active = TRUE)             AS active_versions,
    COUNT(*) FILTER (WHERE is_archived = TRUE)           AS archived_versions,
    COUNT(*) FILTER (WHERE is_archived = FALSE)          AS visible_versions,
    COUNT(*) FILTER (WHERE parent_version_id IS NOT NULL) AS with_parent
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001';
"
```

**Ожидаемый вывод после миграции add_23.sql:**

| total_versions | active_versions | archived_versions | visible_versions | with_parent |
|----------------|-----------------|-------------------|------------------|-------------|
| 55             | 1               | 54                | 1                | 5           |

**Все неархивные версии (то, что видит пользователь):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    id, name, is_active, parent_version_id, created_at
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND COALESCE(is_archived, FALSE) = FALSE
ORDER BY created_at DESC;
"
```

**Все версии с флагами (включая архивные):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.id,
    sv.name,
    sv.is_active,
    sv.is_archived,
    sv.parent_version_id,
    (SELECT COUNT(*) FROM whatif_scenario ws
     WHERE ws.base_version_id = sv.id OR ws.result_version_id = sv.id) AS in_whatif,
    (SELECT COUNT(*) FROM reschedule_log rl
     WHERE rl.from_version_id = sv.id OR rl.to_version_id = sv.id) AS in_log
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY sv.created_at DESC
LIMIT 20;
"
```

**Проверка иерархии (родитель → дети):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
WITH RECURSIVE tree AS (
    SELECT id, name, parent_version_id, 0 AS depth
    FROM schedule_version
    WHERE organization_id = '00000000-0000-0000-0000-000000000001'
      AND parent_version_id IS NULL
    UNION ALL
    SELECT sv.id, sv.name, sv.parent_version_id, t.depth + 1
    FROM schedule_version sv
    JOIN tree t ON sv.parent_version_id = t.id
)
SELECT
    REPEAT('  ', depth) || name AS tree_view,
    depth,
    id
FROM tree
ORDER BY depth, name;
"
```

---

### `app_settings` — настройка auto_archive_on_recalc (Итерация 13.21)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value, value_type, category, label
FROM app_settings
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'auto_archive_on_recalc';
"
```

**Ожидаемый вывод:**

| setting_key | setting_value | value_type | category | label |
|-------------|---------------|------------|----------|-------|
| `auto_archive_on_recalc` | `true` | `bool` | `planning` | Архивировать старую версию после пересчёта |

**Изменить через SQL (если нужно вручную):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE app_settings
SET setting_value = 'false'::jsonb, updated_at = NOW()
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND setting_key = 'auto_archive_on_recalc';
"
```

---

### `plan_settings` (Итерация 13.14)

**Структура:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'plan_settings'
ORDER BY ordinal_position;
"
```

**Триггер:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname, tgrelid::regclass AS on_table, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

**Настройки конкретного плана:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM plan_settings
WHERE schedule_version_id = (
    SELECT id FROM schedule_version WHERE is_active = true LIMIT 1
)
AND category = 'shifts'
ORDER BY setting_key;
"
```

**Количество plan_settings у активного плана:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM app_settings
     WHERE organization_id = '00000000-0000-0000-0000-000000000001') AS app_count,
    (SELECT COUNT(*) FROM plan_settings
     WHERE schedule_version_id = (
         SELECT id FROM schedule_version WHERE is_active = true LIMIT 1
     )) AS plan_count;
"
```

---

### `snapshot`-таблицы (Итерация 13.15)

**Снапшоты всех планов (последние 10):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    sv.is_active,
    sv.is_archived,
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment,
    (SELECT COUNT(*) FROM operation_snapshot WHERE version_id = sv.id) AS ops,
    (SELECT COUNT(*) FROM calendar_snapshot WHERE version_id = sv.id) AS cal,
    (SELECT COUNT(*) FROM plan_settings WHERE schedule_version_id = sv.id) AS settings
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY sv.created_at DESC
LIMIT 10;
"
```

**Планы без снапшотов (пустые):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.id,
    sv.name,
    sv.is_archived,
    sv.created_at
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = sv.id LIMIT 1
  )
ORDER BY sv.created_at DESC;
"
```

---

### `resource_pool` (Итерация 6)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT type, capacity FROM resource_pool ORDER BY type;
"
```

Ожидаемый вывод:

| type | capacity |
|------|----------|
| `BOILER` | 1 |
| `COOLING_ZONE` | 2 |
| `LAB` | 1 |
| `LINE_OPERATOR` | 2 |
| `MANUAL_OPERATOR` | 1 |
| `REACTOR_OPERATOR` | 3 |

---

### `shift` (Итерация 11)

**Смены на конкретную дату (МСК):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    name,
    starts_at AT TIME ZONE 'Europe/Moscow' AS starts_msk,
    ends_at AT TIME ZONE 'Europe/Moscow' AS ends_msk,
    is_working
FROM shift
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND (starts_at AT TIME ZONE 'Europe/Moscow')::date = '2026-09-01'
ORDER BY starts_at;
"
```

**Количество смен:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*), is_working FROM shift GROUP BY is_working;
"
```

---

### `scheduled_task` (Итерации 1–13.21)

**Распределение cooling_mode в активной версии:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT st.cooling_mode, COUNT(*)
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true
GROUP BY st.cooling_mode
ORDER BY st.cooling_mode NULLS LAST;
"
```

**Количество задач по типам:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT task_role, COUNT(*)
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true
GROUP BY task_role
ORDER BY COUNT(*) DESC;
"
```

**Закреплённые задачи:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*)
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true AND st.is_pinned = true;
"
```

---

### `batch` (Итерации 5, 8)

**Статистика ЧЗ:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT cz_status, COUNT(*)
FROM batch
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
GROUP BY cz_status
ORDER BY cz_status;
"
```

**Заблокированные партии:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, lab_status, lab_block_reason
FROM batch
WHERE is_lab_blocked = true;
"
```

---

### `whatif_scenario` (Итерация 12)

**Все сценарии:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, status, base_version_id, result_version_id, created_at
FROM whatif_scenario
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC;
"
```

**Сценарии, блокирующие архивацию (DRAFT/RUNNING):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT ws.id, ws.name, ws.status, ws.base_version_id
FROM whatif_scenario ws
WHERE ws.organization_id = '00000000-0000-0000-0000-000000000001'
  AND ws.status IN ('DRAFT', 'RUNNING');
"
```

**Какие версии используются в сценариях:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.id AS version_id,
    sv.name AS version_name,
    sv.is_archived,
    (SELECT COUNT(*) FROM whatif_scenario ws
     WHERE ws.base_version_id = sv.id AND ws.status IN ('DRAFT', 'RUNNING')) AS as_base_active,
    (SELECT COUNT(*) FROM whatif_scenario ws
     WHERE ws.result_version_id = sv.id AND ws.status IN ('DRAFT', 'RUNNING')) AS as_result_active
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY sv.created_at DESC
LIMIT 20;
"
```

**ВАЖНО:** если `as_base_active > 0` или `as_result_active > 0` — версия НЕ будет
архивирована при пересчёте с заменой (флаг `replace_blocked = true`).

---

### `audit` (Итерация 13.3)

**Количество событий в журналах-источниках:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT 'material_stock_log' AS source, COUNT(*) FROM material_stock_log
UNION ALL
SELECT 'reschedule_log', COUNT(*) FROM reschedule_log
UNION ALL
SELECT 'lab_analysis_log', COUNT(*) FROM lab_analysis_log
UNION ALL
SELECT 'cz_scan_log', COUNT(*) FROM cz_scan_log;
"
```

---

## Архивация версий планов (Итерация 13.21)

Раздел посвящён операциям с архивацией версий. Все команды — через docker.

### Проверка состояния архивации

**Общая сводка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    COUNT(*)                                             AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE)             AS active,
    COUNT(*) FILTER (WHERE is_archived = TRUE)           AS archived,
    COUNT(*) FILTER (WHERE is_archived = FALSE)          AS visible
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001';
"
```

### Разархивация через SQL (вручную)

Если нужно разархивировать версию напрямую в БД (например, через CLI):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = FALSE
WHERE id = '<version-uuid>'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

### Массовая архивация всех неактивных версий

Если нужно снова почистить список (например, после отключения
`auto_archive_on_recalc` накопились версии):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = TRUE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_active = FALSE
  AND is_archived = FALSE;
"
```

**Вывод покажет количество затронутых строк:**
```
UPDATE 12
```

### Массовая разархивация всех версий

Если нужно вернуть все архивные версии в список:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = FALSE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_archived = TRUE;
"
```

**Осторожно:** после этого в «Истории планов» может быть 50+ версий.

### Проверка: почему версия не архивируется

**Симптом:** пользователь нажимает «Пересчитать», ожидает архивацию,
но старая версия остаётся в списке.

**Причина:** версия используется в `whatif_scenario` со статусом
`DRAFT` или `RUNNING`.

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, status, base_version_id, result_version_id
FROM whatif_scenario
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND status IN ('DRAFT', 'RUNNING')
  AND (base_version_id = '<version-uuid>' OR result_version_id = '<version-uuid>');
"
```

**Решение:**
1. Открыть what-if сценарий и запустить его (переведёт в `DONE`).
2. Или удалить сценарий (`DELETE /api/v1/whatif/scenarios/{id}`).
3. Или разархивировать версию вручную (см. выше).

### Проверка индекса по архивным версиям

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'schedule_version'
  AND indexname = 'idx_schedule_version_archived';
"
```

**Ожидаемый вывод:**

```
indexname                        | indexdef
---------------------------------+-------------------------------------------
idx_schedule_version_archived    | CREATE INDEX idx_schedule_version_archived
                                 | ON public.schedule_version USING btree
                                 | (organization_id, created_at DESC)
                                 | WHERE (is_archived = false)
```

### Очистка старых архивных версий

Если архивных версий накопилось слишком много и они занимают место,
можно удалить самые старые (старше 90 дней):

```bash
# ⚠️ Сначала сделайте бэкап
docker exec aps_postgres pg_dump -U aps household > backup_before_cleanup.sql

# Удалить архивные старше 90 дней
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_archived = TRUE
  AND created_at < NOW() - INTERVAL '90 days';
"
```

**CASCADE** удалит `scheduled_task`, `plan_settings`, снапшоты,
`reschedule_log` записи с FK на эту версию.

**Осторожно:** это необратимо.

---

## Встроенная справка (Итерация 15.1)

### Проверить, что таблица создана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'help_article'
);
"
```

Ожидаемо: `t`.

### Количество статей по категориям

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT category, COUNT(*) AS cnt
FROM help_article
GROUP BY category
ORDER BY category;
"
```

**Ожидаемый вывод (после Итерации 15.4):**

| category | cnt |
|----------|-----|
| `cz` | 1 |
| `faq` | 15 |
| `gantt` | 4 |
| `getting-started` | 3 |
| `lab` | 1 |
| `planning` | 4 |
| `settings` | 1 |
| `shift` | 1 |
| `whatif` | 1 |

Всего: **31 статья** (15 базовых + 1 туториал + 15 FAQ).

### Список статей

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title, category, display_order
FROM help_article
ORDER BY category, display_order;
"
```

### Проверить триггер updated_at

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_help_article_updated_at';
"
```

### Проверить GIN-индекс по тегам

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'help_article' AND indexname = 'idx_help_article_tags';
"
```

### Добавить статью через SQL (вручную)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
INSERT INTO help_article
    (organization_id, slug, title, category, content_md, tags,
     display_order, is_published)
VALUES
    (NULL, 'my-new-article', 'Моя новая статья', 'getting-started',
     \$md\$# Заголовок

Текст статьи в markdown.\$md\$,
     '[\"тег1\", \"тег2\"]'::jsonb,
     100, TRUE)
ON CONFLICT (slug) DO NOTHING;
"
```

**⚠️ Внимание:** экранирование `$md$` в `-c` может быть проблематичным в PowerShell.
Лучше создавать отдельный `.sql`-файл и применять через `docker cp` + `psql -f`.

### Почистить `\r\n` в контенте статей

Если статьи добавлялись через PowerShell-пайп, в `content_md` могли попасть
символы `\r`. Не критично для рендера, но можно почистить:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE help_article
SET content_md = REPLACE(content_md, E'\r\n', E'\n')
WHERE content_md LIKE E'%\r%';
"
```

---

## Контекстные подсказки (Итерация 15.2)

### Проверить, что таблица создана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'help_hint'
);
"
```

Ожидаемо: `t`.

### Список подсказок

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT hint_key, title, article_slug, display_order
FROM help_hint
WHERE is_published = TRUE
ORDER BY display_order;
"
```

**Ожидаемо:** 8 подсказок.

### Проверить связь подсказок со статьями

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    h.hint_key,
    h.article_slug,
    CASE WHEN a.slug IS NULL THEN '❌ NOT FOUND' ELSE '✅ OK' END AS status
FROM help_hint h
LEFT JOIN help_article a ON a.slug = h.article_slug
WHERE h.article_slug IS NOT NULL
ORDER BY h.hint_key;
"
```

Все должны быть `✅ OK`.

### Проверить триггер updated_at

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_help_hint_updated_at';
"
```

### Проверить индексы

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT indexname FROM pg_indexes WHERE tablename = 'help_hint';
"
```

Ожидаемо: `idx_help_hint_published`, `idx_help_hint_org`.

---

## Интерактивный туториал (Итерация 15.3)

Туториал — **полностью на фронтенде**. Специальных таблиц в БД нет.

### Проверить, что статья туториала создана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title, category, is_published
FROM help_article
WHERE slug = 'tutorial-interactive';
"
```

**Ожидаемо:** 1 строка `tutorial-interactive`.

### Применить seed-миграцию туториала

```bash
docker cp backend/migrations/add_27_seed_1.sql aps_postgres:/tmp/add_27_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_27_seed_1.sql
```

**Идемпотентно** — повторное применение безопасно (`ON CONFLICT (slug) DO NOTHING`).

### Проверить, что категория getting-started содержит туториал

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title, display_order
FROM help_article
WHERE category = 'getting-started'
ORDER BY display_order;
"
```

**Ожидаемо:** 3 статьи (`intro-overview`, `intro-first-plan`, `tutorial-interactive`).

### Проверить через API

```bash
curl -s http://localhost:8000/api/v1/help/articles/tutorial-interactive \
  -H "Authorization: Bearer $TOKEN" | jq '.title'
```

**Ожидаемо:** `"Интерактивный туториал"`.

### Прогресс прохождения

Хранится в `localStorage` браузера:
- Ключ: `aps_tutorial_completed_<tour_id>`.
- Значение: `'true'`.

**Сбросить через консоль браузера (DevTools → Console):**

```javascript
localStorage.removeItem('aps_tutorial_completed_getting-started');
localStorage.removeItem('aps_tutorial_completed_gantt-basics');
localStorage.removeItem('aps_tutorial_completed_shift-management');
```

**Или сбросить весь localStorage (осторожно — удалит и токен):**

```javascript
localStorage.clear();
```

---

## FAQ (Итерация 15.4)

FAQ — это **категория** в существующей таблице `help_article`, поэтому
отдельных таблиц/индексов/триггеров **не создаётся**. Все проверки — через
`help_article` (см. раздел «Встроенная справка»).

### Проверить, что все 15 FAQ-статей на месте

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS faq_count
FROM help_article
WHERE category = 'faq';
"
```

**Ожидаемо:** `faq_count = 15`.

### Список FAQ-статей с заголовками

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title, display_order
FROM help_article
WHERE category = 'faq'
ORDER BY display_order;
"
```

**Ожидаемый вывод (15 строк):**

| slug | title |
|------|-------|
| `faq-plan-feasible-not-optimal` | План получился FEASIBLE, а не OPTIMAL — что делать? |
| `faq-task-not-movable` | Задача не двигается на Ганте |
| `faq-plan-is-empty` | План пуст (⚠) — что делать? |
| `faq-plan-settings-empty` | «Настройки плана не заполнены» при пересчёте |
| `faq-material-shortage` | Не хватает сырья — что делать? |
| `faq-move-pinned-task` | Закреплённая задача не двигается — как открепить? |
| `faq-old-version-not-archived` | Старая версия плана не архивируется |
| `faq-shift-mode-change` | После смены режима смен задачи потеряли привязку |
| `faq-whatif-running` | What-if сценарий завис в статусе RUNNING |
| `faq-cz-orphan-scan` | Скан ЧЗ попал в «сироты» — что делать? |
| `faq-lab-blocked-batch` | Партия заблокирована лабораторией — как разблокировать? |
| `faq-route-mismatch` | Advisor: ROUTE_MISMATCH — что это значит? |
| `faq-cooling-degradation` | Advisor: COOLING_DEGRADATION — что это значит? |
| `faq-cz-incomplete` | Advisor: CZ_INCOMPLETE — что это значит? |
| `faq-underload` | Advisor: UNDERLOAD — неполная загрузка реактора |

### Применить FAQ-миграции (если не применены)

```bash
docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker cp backend/migrations/add_26_seed_2.sql aps_postgres:/tmp/add_26_seed_2.sql
docker cp backend/migrations/add_26_seed_3.sql aps_postgres:/tmp/add_26_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_3.sql
```

**Идемпотентно** — повторное применение безопасно (`ON CONFLICT (slug) DO NOTHING`).

### Проверить ссылки из FAQ-статей на другие статьи

FAQ-статьи содержат внутренние ссылки `/help/{slug}`. Проверим, что все
они ведут на существующие статьи:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    slug AS faq_slug,
    LENGTH(content_md) AS content_length
FROM help_article
WHERE category = 'faq'
ORDER BY display_order;
"
```

Полная проверка ссылок — в тестах (`tests/test_help_faq.py`).

### Проверить, что FAQ-статьи глобальные (organization_id IS NULL)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS global_faq
FROM help_article
WHERE category = 'faq' AND organization_id IS NULL;
"
```

**Ожидаемо:** `global_faq = 15`.

### Проверить, что API возвращает категорию faq

```bash
curl -s http://localhost:8000/api/v1/help/categories \
  -H "Authorization: Bearer $TOKEN" | jq '.categories[] | select(.key=="faq")'
```

**Ожидаемо:**
```json
{
  "key": "faq",
  "label": "FAQ",
  "article_count": 15
}
```

---

## Диагностика

### Проверить активную версию плана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_active, is_archived, created_at
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC
LIMIT 5;
"
```

### Проверить, что только одна версия активна

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*)
FROM schedule_version
WHERE is_active = true
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

Должно быть `1`.

### Проверить пересечения задач

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT a.id, b.id, a.equipment_id
FROM scheduled_task a
JOIN scheduled_task b ON a.equipment_id = b.equipment_id AND a.id < b.id
WHERE a.schedule_version_id = b.schedule_version_id
  AND a.schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)
  AND a.start_at < b.end_at
  AND b.start_at < a.end_at;
"
```

Должно быть пусто.

### Проверить нарушения зависимостей

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*)
FROM scheduled_task
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)
  AND start_at < (
      SELECT MAX(end_at) FROM scheduled_task st2
      WHERE st2.id = ANY(depends_on_task_ids)
  );
"
```

### Проверить задачи без смены

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*)
FROM scheduled_task
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)
  AND shift_id IS NULL;
"
```

### Проверить plan_settings для активного плана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS settings_count
FROM plan_settings
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1);
"
```

Должно быть больше нуля.

### Сравнить app_settings и plan_settings

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM app_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001') AS app_count,
    (SELECT COUNT(*) FROM plan_settings WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)) AS plan_count;
"
```

### Проверить триггер copy_app_settings_to_plan

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

Ожидаемый вывод: `trg_copy_app_settings_to_plan | O` (`O` = enabled).

### Проверить, что миграции применены

**add_21.sql (plan_settings):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'plan_settings') AS has_table,
    EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_copy_app_settings_to_plan') AS has_trigger,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_plan_settings_version') AS has_index;
"
```

**add_23.sql (архивация):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name = 'schedule_version' AND column_name = 'is_archived') AS has_column,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_schedule_version_archived') AS has_index,
    EXISTS (SELECT 1 FROM app_settings WHERE setting_key = 'auto_archive_on_recalc') AS has_setting;
"
```

Все три должны быть `t`.

**add_24.sql (справка):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'help_article') AS has_table,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_help_article_category') AS has_category_idx,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_help_article_tags') AS has_tags_idx,
    EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_help_article_updated_at') AS has_trigger,
    (SELECT COUNT(*) FROM help_article) AS article_count;
"
```

Все четыре `t`, `article_count` = 31.

**add_25.sql (подсказки):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'help_hint') AS has_table,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_help_hint_published') AS has_pub_idx,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_help_hint_org') AS has_org_idx,
    EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_help_hint_updated_at') AS has_trigger,
    (SELECT COUNT(*) FROM help_hint WHERE is_published = TRUE) AS hint_count;
"
```

Все четыре `t`, `hint_count` = 8.

**add_26_seed_1/2/3.sql (FAQ):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM help_article WHERE category = 'faq') AS faq_count,
    (SELECT COUNT(*) FROM help_article WHERE category = 'faq' AND organization_id IS NULL) AS global_faq,
    (SELECT COUNT(*) FROM help_article WHERE slug LIKE 'faq-%') AS faq_slug_count;
"
```

Ожидаемо: `faq_count = 15`, `global_faq = 15`, `faq_slug_count = 15`.

**add_27_seed_1.sql (туториал):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM help_article WHERE slug = 'tutorial-interactive') AS tutorial_count,
    (SELECT COUNT(*) FROM help_article WHERE category = 'getting-started') AS getting_started_count;
"
```

Ожидаемо: `tutorial_count = 1`, `getting_started_count = 3`.

### Полная диагностика системы

```bash
# 1. Статус PostgreSQL
docker ps --filter "name=aps_postgres"

# 2. Backend
curl http://localhost:8000/docs

# 3. Frontend
curl http://localhost:5173

# 4. Активная версия
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_active, is_archived FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC LIMIT 1;
"

# 5. Количество задач
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true;
"

# 6. plan_settings
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM plan_settings
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1);
"

# 7. Снапшоты
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment,
    (SELECT COUNT(*) FROM operation_snapshot WHERE version_id = sv.id) AS ops,
    (SELECT COUNT(*) FROM calendar_snapshot WHERE version_id = sv.id) AS cal
FROM schedule_version sv
WHERE sv.is_active = true LIMIT 1;
"

# 8. Архивные версии
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS archived FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_archived = TRUE;
"

# 9. Статьи справки
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS help_articles FROM help_article;
"

# 10. Контекстные подсказки
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS help_hints FROM help_hint WHERE is_published = TRUE;
"

# 11. FAQ-статьи
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS faq_articles FROM help_article WHERE category = 'faq';
"

# 12. Туториал
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS tutorial_articles FROM help_article WHERE slug = 'tutorial-interactive';
"
```

**Ожидаемые значения:**

| Проверка | Ожидание |
|----------|----------|
| `help_articles` | 31 |
| `help_hints` | 8 |
| `faq_articles` | 15 |
| `tutorial_articles` | 1 |
| `active` версия | 1 |
| `plan_settings` активного плана | >0 |

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.