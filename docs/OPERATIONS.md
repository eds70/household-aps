# Operations

Операции с базой данных, миграциями, бэкапами и мониторингом системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Все команды для БД](#все-команды-для-бд)
- [Применение миграций](#применение-миграций)
- [Бэкапы и восстановление](#бэкапы-и-восстановление)
- [Мониторинг](#мониторинг)
- [Проверка конкретных таблиц](#проверка-конкретных-таблиц)
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
docker cp backend/migrations/add_21.sql aps_postgres:/tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
```

### Неправильный способ (НЕ ИСПОЛЬЗОВАТЬ)

```bash
# ❌ PowerShell испортит кириллицу
Get-Content backend/migrations/add_21.sql | docker exec -i aps_postgres psql -U aps -d household
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
| `add_21.sql` | 13.14 | `plan_settings` |
| `fix_shift_names.sql` | — | Исправление имён смен |

### Применить все миграции по порядку

```bash
$migrations = @(
    "add_06.sql", "add_06b.sql", "add_07.sql", "add_08.sql",
    "fix_versions_hotfix.sql",
    "add_09.sql", "add_09b.sql", "add_09c.sql", "add_09d.sql",
    "add_10.sql", "add_10b.sql", "add_11.sql", "add_12.sql",
    "add_13.sql", "add_14.sql", "add_15.sql", "add_16.sql",
    "add_21.sql", "fix_shift_names.sql"
)

foreach ($m in $migrations) {
    Write-Host "Applying $m..."
    docker cp "backend/migrations/$m" "aps_postgres:/tmp/$m"
    docker exec -i aps_postgres psql -U aps -d household -f "/tmp/$m"
}
```

### Проверить, применена ли миграция

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

### `snapshot`-таблицы (Итерация 13.15)

**Снапшоты всех планов (последние 10):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    sv.is_active,
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
    sv.created_at
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = sv.id LIMIT 1
  )
ORDER BY sv.created_at DESC;
"
```

**Количество пустых планов:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS empty_plans
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = sv.id LIMIT 1
  );
"
```

### `app_settings` (Итерация 11)

**Настройки режима смен:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM app_settings
WHERE setting_key IN (
    'shift_mode', 'shift_intervals', 'shift_duration_hours', 'allow_weekend_work'
)
ORDER BY setting_key;
"
```

**Веса multi-objective:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM app_settings
WHERE category = 'optimization'
ORDER BY display_order;
"
```

**Настройки охлаждения:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM app_settings
WHERE setting_key IN (
    'enable_cooling_degradation',
    'cooling_degradation_factor',
    'cooling_zone_capacity'
);
"
```

**Настройки ЧЗ:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_key, setting_value
FROM app_settings
WHERE setting_key LIKE 'cz_%' OR setting_key = 'enable_cz_integration'
ORDER BY setting_key;
"
```

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

### `scheduled_task` (Итерации 1–13.14)

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

### `whatif_scenario` (Итерация 12)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, status, base_version_id, result_version_id, created_at
FROM whatif_scenario
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC;
"
```

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

## Диагностика

### Проверить активную версию плана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_active, created_at
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

### Проверить `plan_settings` для активного плана

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS settings_count
FROM plan_settings
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1);
"
```

Должно быть `32` (или больше, если добавлены новые настройки).

### Сравнить `app_settings` и `plan_settings`

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM app_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001') AS app_count,
    (SELECT COUNT(*) FROM plan_settings WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)) AS plan_count;
"
```

Должны совпадать.

### Проверить триггер `copy_app_settings_to_plan`

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

Ожидаемый вывод: `trg_copy_app_settings_to_plan | O` (`O` = enabled).

### Проверить содержимое `plan_settings` по категориям

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT category, COUNT(*)
FROM plan_settings
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1)
GROUP BY category
ORDER BY category;
"
```

Ожидаемые категории: `calendar`, `cooling`, `cz`, `features`, `lab`, `materials`, `optimization`, `planning`, `resources`, `shifts`.

### Проверить, что миграция `add_21.sql` применена

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'plan_settings') AS has_table,
    EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_copy_app_settings_to_plan') AS has_trigger,
    EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_plan_settings_version') AS has_index;
"
```

Все три должны быть `t`.

### Очистить старые планы (Итерация 13.15)

Если накопилось много планов, можно удалить всё кроме последнего:

```bash
docker exec aps_postgres pg_dump -U aps household > backup_before_cleanup.sql

docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND id NOT IN (
      SELECT id FROM schedule_version
      WHERE organization_id = '00000000-0000-0000-0000-000000000001'
      ORDER BY created_at DESC
      LIMIT 1
  );
"
```

**⚠️ Осторожно:** это удалит все снапшоты и задачи связанных планов (CASCADE).

### Удалить пустые планы (без снапшотов)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = schedule_version.id LIMIT 1
  );
"
```

Безопасно — удаляются только планы без снапшотов (они всё равно не открываются).

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.