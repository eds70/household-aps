# Operations

Операции с базой данных, миграциями, бэкапами и мониторингом системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Docker (production)](#docker-production)
- [Все команды для БД (dev)](#все-команды-для-бд-dev)
- [Применение миграций](#применение-миграций)
- [Бэкапы и восстановление](#бэкапы-и-восстановление)
- [Мониторинг](#мониторинг)
- [Проверка конкретных таблиц](#проверка-конкретных-таблиц)
- [Архивация версий планов (Итерация 13.21)](#архивация-версий-планов-итерация-1321)
- [Встроенная справка (Итерация 15.1)](#встроенная-справка-итерация-151)
- [Контекстные подсказки (Итерация 15.2)](#контекстные-подсказки-итерация-152)
- [Интерактивный туториал (Итерация 15.3)](#интерактивный-туториал-итерация-153)
- [FAQ (Итерация 15.4)](#faq-итерация-154)
- [Редактирование статей через UI (Итерация 15.5)](#редактирование-статей-через-ui-итерация-155)
- [Проверка prod-развёртывания](#проверка-prod-развёртывания)
- [Диагностика](#диагностика)

---

## Docker (production)

Всё взаимодействие с prod-развёртыванием — через `docker compose` с явным указанием файла `docker-compose.prod.yml`.

### Псевдоним для удобства

Все команды в этом разделе — из **корня проекта**. Чтобы не писать каждый раз `-f docker-compose.prod.yml`, можно завести псевдоним.

**Bash / Git Bash:**
```bash
alias dcp="docker compose -f docker-compose.prod.yml"
dcp ps
dcp logs backend
dcp exec postgres psql -U aps -d household
```

**PowerShell:**
```powershell
Set-Alias -Name dcp -Value "docker compose -f docker-compose.prod.yml"
# Или — через функцию (потому что алиасы в PS не работают с аргументами)
function dcp { docker compose -f docker-compose.prod.yml $args }
```

### Статус сервисов

```bash
docker compose -f docker-compose.prod.yml ps
```

**Ожидаемо:**
```
NAME            IMAGE                   STATUS
aps_postgres    postgres:17             Up (healthy)
aps_backend     <project>-backend       Up (healthy)
aps_frontend    <project>-frontend      Up
aps_nginx       nginx:alpine            Up
```

### Логи

```bash
# Все сервисы
docker compose -f docker-compose.prod.yml logs -f

# Только backend (последние 100 строк)
docker compose -f docker-compose.prod.yml logs backend --tail=100

# Только backend, фильтр по ошибкам
docker compose -f docker-compose.prod.yml logs backend | grep ERROR

# PostgreSQL
docker compose -f docker-compose.prod.yml logs postgres --tail=50

# nginx (access logs)
docker compose -f docker-compose.prod.yml logs nginx -f
```

### Подключение к БД (production)

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U aps -d household
```

**Замечание:** `exec` (не `exec -it`) работает и в скриптах, и в терминале. Если нужен интерактивный psql — добавьте `-it`:
```bash
docker compose -f docker-compose.prod.yml exec -it postgres psql -U aps -d household
```

### Однократные SQL-запросы

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U aps -d household -c "SELECT COUNT(*) FROM help_article;"
```

Флаг `-T` отключает TTY (важно для скриптов и pipe).

### Применение SQL-файла (в Docker)

```bash
# 1. Скопировать файл в контейнер
docker compose -f docker-compose.prod.yml cp backend/init_schema_v4.9.sql postgres:/tmp/init_schema_v4.9.sql

# 2. Применить
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -f /tmp/init_schema_v4.9.sql
```

**⚠️ Кириллица:** только через `cp` + `psql -f`, **не** через pipe (`Get-Content | docker compose exec ...` — испортит UTF-8).

### Перезапуск сервисов

```bash
# Перезапустить backend
docker compose -f docker-compose.prod.yml restart backend

# Пересобрать backend (после правок кода)
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend

# Пересобрать frontend (после правок или изменения VITE_API_URL)
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend

# Перезагрузить nginx (после правки nginx/nginx.conf)
docker compose -f docker-compose.prod.yml restart nginx
```

### Остановка и запуск

```bash
# Остановить (БЕЗ удаления volumes — БД сохраняется)
docker compose -f docker-compose.prod.yml down

# Запустить
docker compose -f docker-compose.prod.yml up -d

# ⚠️ ПОЛНАЯ ОЧИСТКА: удалит БД!
# docker compose -f docker-compose.prod.yml down -v   # ❌ НЕ ДЕЛАТЬ БЕЗ БЭКАПА
```

### Обновление версии

```bash
cd household-aps

# 1. Бэкап БД (см. ниже)
~/backup_aps.sh

# 2. Получить изменения
git pull

# 3. Пересобрать образы
docker compose -f docker-compose.prod.yml build

# 4. Применить новые миграции (если есть)
docker compose -f docker-compose.prod.yml cp backend/migrations/add_29.sql postgres:/tmp/
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -f /tmp/add_29.sql

# 5. Перезапустить сервисы
docker compose -f docker-compose.prod.yml up -d

# 6. Проверить
docker compose -f docker-compose.prod.yml ps
curl http://your-server-ip/health
```

### Мониторинг ресурсов

```bash
# Использование CPU/RAM контейнерами
docker stats

# Свободное место на диске
df -h

# Размер Docker-данных
docker system df
```

### Полная первичная инициализация (production)

```bash
# Скрипт делает всё: схема + seed-статьи + демо-данные + админ
./scripts/deploy_init.sh       # Linux / Git Bash
.\scripts\deploy_init.ps1      # Windows PowerShell
```

Что делает скрипт — см. [DEPLOYMENT.md](DEPLOYMENT.md), раздел «Шаг 8. Инициализация БД».

---

## Все команды для БД (dev)

**Dev-контекст:** PostgreSQL запущен через `docker/docker-compose.yml` (только БД) или через `docker run`. Backend и frontend — на хосте. Все команды — через `docker exec aps_postgres`.

> Для **production** (всё в Docker) — см. раздел [Docker (production)](#docker-production).

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

### Консолидированные файлы v4.9.0

Для **свежей установки** используйте:

| Файл | Что делает |
|------|-----------|
| `backend/init_schema_v4.9.sql` | **Полная схема** v4.9.0 (включая миграции 13.14–16.2) |
| `backend/init_schema_v4.9_seed.sql` | **31 статья справки** + **8 подсказок** |
| `backend/seed_demo_data.sql` | Демо-данные (оборудование, партии, заказы) |

Применяются в **этом порядке**:

```bash
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/init_schema_v4.9.sql
docker cp backend/init_schema_v4.9_seed.sql aps_postgres:/tmp/init_schema_v4.9_seed.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9_seed.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql
```

**Плюс:** одно развёртывание → полностью рабочая БД с 31 статьёй справки.
**Когда применять:** пустая БД, новая установка.

### Базовая схема + миграции (для апгрейда)

Если БД уже существует и развёрнута на версии до 4.0.0, используйте:

1. `backend/init_schema.sql` — базовая схема v4.0.0.
2. `backend/seed_demo_data.sql` — демо-данные.
3. **Все миграции** из `backend/migrations/` по порядку.

**Порядок миграций:**

| Файл | Итерация | Описание |
|------|----------|----------|
| `add_history_0_2.sql` | 0–2 | Базовая схема (уже в `init_schema.sql`) |
| `add_06.sql` | 3 | Сменное планирование |
| `add_06b.sql` | 3 | Снапшот-таблицы |
| `add_07.sql` | 4 | Перепланирование |
| `fix_versions_hotfix.sql` | 5h | Деактивация старых версий |
| `add_08.sql` | 5 | Лаборатория |
| `add_09.sql` | 6 | Пулы операторов |
| `add_09b.sql` | 6 | COOLING_ZONE, BOILER, LAB |
| `add_09c.sql` | 6 | `resource_pool.updated_at` |
| `add_09d.sql` | 6 | `scheduled_task.operator_pool` |
| `add_10.sql` | 7 | Охлаждение с деградацией |
| `add_10b.sql` | 7 | `scheduled_task.cooling_mode` |
| `add_11.sql` | 8 | Честный Знак |
| `add_12.sql` | 9 | `scheduled_task.operation_name` |
| `add_13.sql` | 11 | `app_settings` |
| `add_14.sql` | 11 | `allow_weekend_work` |
| `add_15.sql` | 12 | Веса multi-objective |
| `add_16.sql` | 12 | `whatif_scenario` |
| `add_17.sql` | 13.1 | UNIQUE на `material_stock` |
| `add_18.sql` | 13.2 | `material_stock_log` + триггер |
| `add_19.sql` | 13.4 | TANK_2 |
| `add_20.sql` | 13.6 | `depends_on_task_ids` |
| `add_21.sql` | 13.14 | `plan_settings` + триггер |
| `add_22.sql` | 13.17 | Индексы каскада |
| `add_23.sql` | 13.21 | Архивация версий |
| `add_24.sql` | 15.1 | `help_article` |
| `add_24_seed_1.sql` | 15.1 | 3 статьи справки |
| `add_24_seed_2.sql` | 15.1 | 5 статей справки |
| `add_24_seed_3.sql` | 15.1 | 7 статей справки |
| `add_25.sql` | 15.2 | `help_hint` |
| `add_25_seed.sql` | 15.2 | 8 контекстных подсказок |
| `add_26_seed_1.sql` | 15.4 | FAQ: планирование (5) |
| `add_26_seed_2.sql` | 15.4 | FAQ: гант, смены, what-if, ЧЗ (5) |
| `add_26_seed_3.sql` | 15.4 | FAQ: лаборатория, advisor (5) |
| `add_27_seed_1.sql` | 15.3 | Туториал (`tutorial-interactive`) |
| `add_28.sql` | 16.2 | `audit_saved_view` |
| `fix_shift_names.sql` | — | Пересоздание смен с корректной кириллицей |
| `fix_work_time.sql` | — | Исправление `work_start_time` / `work_end_time` |

### Правильный способ применения миграции

```bash
docker cp backend/migrations/add_28.sql aps_postgres:/tmp/add_28.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_28.sql
```

### Неправильный способ (НЕ ИСПОЛЬЗОВАТЬ)

```bash
# ❌ PowerShell испортит кириллицу
Get-Content backend/migrations/add_28.sql | docker exec -i aps_postgres psql -U aps -d household
```

### Применить все миграции по порядку (dev)

```powershell
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
    "add_27_seed_1.sql", "add_28.sql",
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

Для `add_28.sql` (аудит — сохранённые представления):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'audit_saved_view'
);
"
```

### Пересоздать БД с нуля (v4.9.0)

```bash
docker exec aps_postgres psql -U aps -d household -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/init_schema_v4.9.sql
docker cp backend/init_schema_v4.9_seed.sql aps_postgres:/tmp/init_schema_v4.9_seed.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9_seed.sql
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

### Создать бэкап (dev)

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

### Бэкап в Docker (production)

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U aps household | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Восстановление:**

```bash
gunzip -c backup_20261007_020000.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household
```

### Автоматический бэкап (dev, PowerShell)

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

### Автоматический бэкап (production, cron)

```bash
# ~/backup_aps.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/home/user/backups
mkdir -p $BACKUP_DIR

docker compose -f /home/user/household-aps/docker-compose.prod.yml exec -T postgres \
    pg_dump -U aps household | gzip > $BACKUP_DIR/household_$DATE.sql.gz

find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

**Cron:**
```bash
crontab -e
# Добавить:
0 2 * * * /home/user/backup_aps.sh
```

---

## Мониторинг

### Проверить статус backend (dev)

```bash
curl http://localhost:8000/docs
```

### Проверить статус frontend (dev)

```bash
curl http://localhost:5173
```

### Проверить статус prod

```bash
# Health endpoint
curl http://your-server-ip/health

# Ожидаемо:
# {"status":"healthy","version":"4.9.0","timestamp":"..."}
```

### Проверить логи backend

**Dev:** логи выводятся в терминал, где запущен `python run_server.py`.

**Prod:**
```bash
docker compose -f docker-compose.prod.yml logs -f backend --tail=100
```

### Проверить логи PostgreSQL (dev)

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

### `audit` (Итерация 13.3 + 16.2)

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

**Сохранённые представления аудита (Итерация 16.2):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, user_id, name, is_default, display_order, created_at
FROM audit_saved_view
ORDER BY display_order, name;
"
```

**Структура таблицы:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "\d audit_saved_view"
```

**Ожидаемо:** 10 колонок, 4 индекса, 1 триггер.

---

## Архивация версий планов (Итерация 13.21)

Раздел посвящён операциям с архивацией версий.

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

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = FALSE
WHERE id = '<version-uuid>'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

### Массовая архивация всех неактивных версий

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = TRUE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_active = FALSE
  AND is_archived = FALSE;
"
```

**Вывод покажет количество затронутых строк:** `UPDATE 12`.

### Массовая разархивация всех версий

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

### Очистка старых архивных версий

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
`reschedule_log` записи с FK на эту версию. **Осторожно:** это необратимо.

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

**⚠️ Лучше — через UI (Итерация 15.5) или через отдельный `.sql`-файл + `docker cp`.**

Для ad-hoc вставки через `-c`:

```bash
docker exec -i aps_postgres psql -U aps -d household << 'EOF'
INSERT INTO help_article
    (organization_id, slug, title, category, content_md, tags,
     display_order, is_published)
VALUES
    (NULL, 'my-new-article', 'Моя новая статья', 'getting-started',
     $md$# Заголовок

Текст статьи в markdown.$md$,
     '["тег1", "тег2"]'::jsonb,
     100, TRUE)
ON CONFLICT (slug) DO NOTHING;
EOF
```

### Почистить `\r\n` в контенте статей

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

**Идемпотентно** — повторное применение безопасно.

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

---

## FAQ (Итерация 15.4)

FAQ — это **категория** в существующей таблице `help_article`. Отдельных
таблиц/индексов/триггеров **не создаётся**.

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

### Применить FAQ-миграции (если не применены)

```bash
docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker cp backend/migrations/add_26_seed_2.sql aps_postgres:/tmp/add_26_seed_2.sql
docker cp backend/migrations/add_26_seed_3.sql aps_postgres:/tmp/add_26_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_3.sql
```

**Идемпотентно** — повторное применение безопасно.

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

## Редактирование статей через UI (Итерация 15.5)

### Правка статей справки через UI

С Итерации 15.5 статьи можно создавать/редактировать/удалять через UI
(роль **ADMIN**). SQL-миграции больше **не нужны** для правки контента.

**Через UI:**
1. Открыть страницу **«Помощь»** (`/help`).
2. Для новой статьи — кнопка **«Новая статья»** в шапке.
3. Для правки существующей — кнопка **«Редактировать»** (карандаш) над статьёй.
4. Форма с двумя вкладками: «Редактор» / «Предпросмотр».
5. Сохранить.

**Через API (альтернатива):**

```bash
# Создать статью
curl -X POST http://localhost:8000/api/v1/help/articles \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Моя статья",
    "slug": "my-article",
    "category": "planning",
    "content_md": "# Заголовок\n\nТекст.",
    "tags": ["тег1", "тег2"],
    "display_order": 100,
    "is_published": true
  }'

# Обновить статью
curl -X PUT http://localhost:8000/api/v1/help/articles/my-article \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Обновлённый заголовок", "is_published": false}'

# Удалить статью
curl -X DELETE http://localhost:8000/api/v1/help/articles/my-article \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Важно:**
- Правки идут в `help_article` **напрямую** (не через seed-миграции).
- Через UI редактируются **только статьи текущей организации**.
  Глобальные статьи (`organization_id IS NULL`) — через seed-миграции.
- **Мульти-тенантность:** ADMIN одной организации не может править статью другой.
- **Остальные роли** (PLANNER, MASTER, LAB, VIEWER) → `403`.

### Проверить, что статья создана через UI

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title, category, organization_id, updated_at
FROM help_article
WHERE slug = 'my-article';
"
```

Если `organization_id = '00000000-0000-0000-0000-000000000001'` — статья
создана через UI. Если `NULL` — через seed-миграцию.

### Массовые правки через SQL (когда UI недоступен)

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE help_article
SET content_md = REPLACE(content_md, 'старое', 'новое'),
    updated_at = NOW()
WHERE slug = 'planning-build-plan';
"
```

---

## Проверка prod-развёртывания

Быстрая проверка после деплоя в облако.

### 1. Контейнеры подняты

```bash
docker compose -f docker-compose.prod.yml ps
```

Ожидаемо: 4 сервиса `Up`. `postgres` и `backend` — `(healthy)`.

### 2. Health endpoint

```bash
curl http://your-server-ip/health
```

Ожидаемо:
```json
{"status":"healthy","version":"4.9.0","timestamp":"2026-10-07T..."}
```

**В PowerShell** — использовать `curl.exe` (не алиас `curl`).

### 3. Swagger UI

```bash
curl http://your-server-ip/docs
```

Ожидаемо: HTML Swagger.

### 4. Frontend отдаётся

```bash
curl http://your-server-ip/
```

Ожидаемо: HTML с `<div id="root">`.

### 5. SPA-fallback работает

```bash
curl -I http://your-server-ip/audit
```

Ожидаемо: `HTTP/1.1 200 OK`, `Content-Type: text/html`.

### 6. API-прокси работает

```bash
curl http://your-server-ip/api/v1/health
```

Ожидаемо: то же, что `/health` (если маршрут существует).

### 7. Статьи справки загружены

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "SELECT COUNT(*) FROM help_article;"
```

Ожидаемо: `31`.

### 8. Подсказки загружены

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "SELECT COUNT(*) FROM help_hint WHERE is_published = TRUE;"
```

Ожидаемо: `8`.

### 9. Админ существует

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "SELECT COUNT(*) FROM app_user WHERE role = 'ADMIN';"
```

Ожидаемо: `>= 1`.

### 10. Вход в UI

Откройте `http://your-server-ip/` в браузере.
Логин: `admin@household.ru` / `admin123`.
**Сразу смените пароль** (Настройки → Профиль → Сменить пароль).

---

## Диагностика

### Общая проверка системы (dev)

```bash
# PostgreSQL
docker ps --filter "name=aps_postgres"

# Backend
curl http://localhost:8000/docs

# Frontend
curl http://localhost:5173

# Активная версия
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_active, is_archived FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC LIMIT 1;
"

# Количество задач
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = true;
"

# plan_settings
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM plan_settings
WHERE schedule_version_id = (SELECT id FROM schedule_version WHERE is_active = true LIMIT 1);
"

# Снапшоты
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment,
    (SELECT COUNT(*) FROM operation_snapshot WHERE version_id = sv.id) AS ops,
    (SELECT COUNT(*) FROM calendar_snapshot WHERE version_id = sv.id) AS cal
FROM schedule_version sv
WHERE sv.is_active = true LIMIT 1;
"

# Статьи справки
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS help_articles FROM help_article;
"

# Контекстные подсказки
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS help_hints FROM help_hint WHERE is_published = TRUE;
"

# FAQ-статьи
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS faq_articles FROM help_article WHERE category = 'faq';
"

# Туториал
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS tutorial_articles FROM help_article WHERE slug = 'tutorial-interactive';
"

# Сохранённые представления аудита (Итерация 16.2)
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS saved_views FROM audit_saved_view;
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
| `saved_views` | >= 0 |

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание в облаке.
- [docs/DOCKER.md](DOCKER.md) — Docker: устройство и отладка.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.