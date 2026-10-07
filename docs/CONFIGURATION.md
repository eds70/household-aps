# Configuration

Все настройки системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Обзор](#обзор)
- [app_settings](#app_settings)
- [plan_settings](#plan_settings)
- [.env](#env)
- [Docker-параметры](#docker-параметры)
- [Приоритеты](#приоритеты)
- [Валидация](#валидация)

---

## Обзор

Система использует **трёхуровневую** конфигурацию:

```
1. .env                          — переменные окружения (секреты, подключения)
2. app_settings                  — глобальные настройки (дефолт для всех планов)
3. plan_settings                 — снапшот настроек для конкретного плана
```

**Приоритет (от высшего к низшему):**
```
plan_settings  →  app_settings  →  .env  →  значения по умолчанию
```

**Чтение:** через модуль `backend/app/scheduler/settings_reader.py`:
- `read_setting(db, org_id, key, default, version_id=None)`.
- `read_settings_dict(db, org_id, keys, version_id=None)`.
- `read_feature_flags(db, org_id, version_id=None)`.

### Dev vs Prod (что где лежит)

| Контекст | Файл `.env` | Назначение |
|----------|-------------|------------|
| **Dev** (локально) | `backend/.env` | Backend запускается на хосте, БД — в Docker на `localhost:5432` |
| **Prod** (Docker) | `.env` в **корне** проекта | Все переменные пробрасываются в контейнеры через `docker-compose.prod.yml` |

В **Dev** переменные читает `backend/app/core/config.py` (файл `backend/.env`).
В **Prod** `backend/.env` **игнорируется** — переменные приходят из `environment:` в compose.

---

## app_settings

**Таблица `app_settings`** — глобальный источник правды. Содержит метаданные:
- `category` — для группировки в UI.
- `setting_key` — ключ.
- `setting_value` (JSONB) — значение.
- `value_type` — `int` | `float` | `bool` | `str` | `json` | `select`.
- `label`, `description` — для UI.
- `min_value`, `max_value`, `options` — валидация.
- `is_system` — запрет на редактирование через UI.

### Категория `planning` — Планирование

| Ключ | Тип | По умолчанию | Min | Max | Описание |
|------|-----|--------------|-----|-----|----------|
| `planning_start_date` | `str` | `2026-09-01` | — | — | Дата старта планирования |
| `horizon_hours` | `int` | `720` | `24` | `8760` | Горизонт планирования (ч) |
| `timeout_seconds` | `int` | `600` | `10` | `3600` | Таймаут solver (сек) |
| `max_fill_percent` | `float` | `0.70` | `0.1` | `1.0` | Макс. загрузка реактора |
| `auto_archive_on_recalc` | `bool` | `true` | — | — | **Итерация 13.21:** архивировать старую версию после пересчёта |

**Про `auto_archive_on_recalc`:**
- `true` (по умолчанию) — при пересчёте плана старая версия уходит
  в архив (скрывается из «Истории планов»).
- `false` — старая версия остаётся в списке как обычная.
- Управляется через `PlanSettingsWizard` (шаг «Основные») или
  через `PUT /api/v1/settings/auto_archive_on_recalc`.

### Категория `shifts` — Режим смен

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `shift_mode` | `select` | `2x12` | Режим смен: `1x8`, `3x8`, `2x12` |
| `shift_intervals` | `json` | `[{"start":"08:00","end":"20:00"},{"start":"20:00","end":"08:00"}]` | Интервалы смен (is_system) |
| `shift_duration_hours` | `int` | `12` | Длительность смены (is_system) |
| `work_start_time` | `str` | `08:00` | Начало рабочего дня |
| `work_end_time` | `str` | `20:00` | Конец рабочего дня |

**Режимы:**
- `1x8` → `[{"start": "08:00", "end": "16:00"}]`, 8 ч.
- `3x8` → `[{"start": "00:00", "end": "08:00"}, {"start": "08:00", "end": "16:00"}, {"start": "16:00", "end": "00:00"}]`, 8 ч.
- `2x12` → `[{"start": "08:00", "end": "20:00"}, {"start": "20:00", "end": "08:00"}]`, 12 ч.

### Категория `cooling` — Охлаждение

| Ключ | Тип | По умолчанию | Min | Max | Описание |
|------|-----|--------------|-----|-----|----------|
| `enable_cooling_degradation` | `bool` | `true` | — | — | Включить деградацию |
| `cooling_degradation_factor` | `float` | `1.3` | `1.0` | `3.0` | Коэффициент замедления |
| `cooling_zone_capacity` | `int` | `2` | `1` | `10` | Ёмкость зоны охлаждения |

### Категория `calendar` — Календарь

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `allow_weekend_work` | `bool` | `false` | Разрешить работу в выходные |
| `max_task_hours_for_calendar` | `float` | `12.0` | Макс. длительность задачи (ч) |
| `max_fill_part_hours` | `float` | `8.0` | Макс. длительность подзадачи LINE_FILL (ч) |

### Категория `lab` — Лаборатория

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `enable_lab_blocking` | `bool` | `true` | Включить лабораторные блокировки |

### Категория `materials` — Материалы

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `enable_material_constraints` | `bool` | `true` | Включить материальные ограничения |

### Категория `cz` — Честный Знак

| Ключ | Тип | По умолчанию | Min | Max | Описание |
|------|-----|--------------|-----|-----|----------|
| `enable_cz_integration` | `bool` | `true` | — | — | Включить ЧЗ |
| `cz_completion_threshold` | `float` | `0.95` | `0.1` | `1.0` | Порог завершения маркировки |
| `cz_api_key` | `str` | `dev-cz-api-key-change-in-production` | — | — | API-key для камер ЧЗ |
| `enable_cz_auto_close` | `bool` | `false` | — | — | Автозакрытие задачи слива |

> **Про `CZ_API_KEY`:** это НЕ ENV-переменная приложения.
> Ключ хранится в `app_settings.cz_api_key` (категория `cz`)
> и меняется через UI «Настройки → ЧЗ» или через
> `PUT /api/v1/settings/cz_api_key`.

### Категория `resources` — Персонал

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `enable_operator_pools` | `bool` | `true` | Включить пулы операторов |
| `enable_manual_station` | `bool` | `true` | Включить ручную станцию |

### Категория `features` — Feature-флаги

| Ключ | Тип | По умолчанию | Итерация | Описание |
|------|-----|--------------|----------|----------|
| `enable_tank_routing` | `bool` | `true` | 1 | Маршрутизация через танк |
| `enable_advisor` | `bool` | `true` | 2 | Advisor-подсказки |
| `enable_shift_planning` | `bool` | `true` | 3 | Сменное планирование |
| `enable_rescheduling` | `bool` | `true` | 4 | Перепланирование |

### Категория `optimization` — Оптимизация

| Ключ | Тип | По умолчанию | Min | Max | Описание |
|------|-----|--------------|-----|-----|----------|
| `weight_makespan` | `float` | `1.0` | `0.0` | `1.0` | Вес makespan |
| `weight_setup` | `float` | `0.0` | `0.0` | `1.0` | Вес переналадок |
| `weight_underload` | `float` | `0.0` | `0.0` | `1.0` | Вес недогрузки |
| `weight_cooling_slow` | `float` | `0.0` | `0.0` | `1.0` | Вес замедленного охлаждения |
| `weight_tardiness` | `float` | `0.0` | `0.0` | `1.0` | Вес просрочек |

**Примечание:** если `weight_makespan = 1.0`, а остальные = `0.0` — работает как single-objective.

---

## plan_settings

**Таблица `plan_settings`** — снапшот настроек для **конкретного плана**. Структура идентична `app_settings`, плюс колонка `schedule_version_id`.

### Логика

1. **При создании плана** (`INSERT INTO schedule_version`) триггер `copy_app_settings_to_plan` автоматически копирует все настройки из `app_settings` в `plan_settings` этого плана.
2. **Мастер настроек плана** (`PlanSettingsWizard.tsx`) позволяет переопределить значения для конкретного плана через `PUT /api/v1/plan-settings/version/{id}`.
3. **Планировщик** (`DataLoader`) читает настройки из `plan_settings`, если передан `version_id`. Если `version_id=None` или `plan_settings` пуст — fallback на `app_settings`.

### Категории, влияющие на план

| Категория | Ключи |
|-----------|-------|
| `planning` | `planning_start_date`, `horizon_hours`, `timeout_seconds`, `max_fill_percent`, `auto_archive_on_recalc` |
| `shifts` | `shift_mode`, `shift_intervals`, `shift_duration_hours`, `work_start_time`, `work_end_time` |
| `calendar` | `allow_weekend_work`, `max_task_hours_for_calendar`, `max_fill_part_hours` |
| `cooling` | `enable_cooling_degradation`, `cooling_degradation_factor`, `cooling_zone_capacity` |
| `resources` | `enable_operator_pools`, `enable_manual_station` |
| `materials` | `enable_material_constraints` |
| `lab` | `enable_lab_blocking` |
| `features` | `enable_tank_routing`, `enable_advisor`, `enable_shift_planning`, `enable_rescheduling` |
| `optimization` | `weight_makespan`, `weight_setup`, `weight_underload`, `weight_cooling_slow`, `weight_tardiness` |

### Мастер настроек плана — 9 шагов

1. Метаданные (только в create-режиме).
2. Основные (`planning`).
3. Режим смен (`shifts`).
4. Календарь (`calendar`).
5. Охлаждение (`cooling`).
6. Ресурсы (`resources`).
7. Материалы и лаборатория (`materials` + `lab`).
8. Маршруты и функции (`features`).
9. Честный Знак (`cz`).
10. Оптимизация (`optimization`).

### Права

Редактировать `plan_settings` может только `ADMIN` или `PLANNER`.

### Системные настройки

`shift_intervals`, `shift_duration_hours` — `is_system = true`, не редактируются через мастер. Управляются режимом смен (`shift_mode`).

### Связь с архивацией (Итерация 13.21)

`plan_settings` **не влияет** на архивацию версий. При архивации:
- `plan_settings` старой версии **сохраняются** (не удаляются).
- При разархивации — версия возвращается с теми же настройками.
- При пересчёте с заменой — у новой версии свои `plan_settings`
  (создаются через триггер), настройки старой остаются.

---

## .env

Переменные окружения читаются через `backend/app/core/config.py` (класс `Settings`,
`pydantic-settings`). Файл `.env` ищется в **директории запуска** приложения.

### Два контекста

| Контекст | Где лежит `.env` | Кто читает | Пример `DATABASE_URL` |
|----------|------------------|-----------|----------------------|
| **Dev** (локально) | `backend/.env` | `backend/app/core/config.py` | `postgresql+asyncpg://aps:aps_secret@localhost:5432/household` |
| **Prod** (Docker) | `.env` в корне | `docker-compose.prod.yml` → `environment:` | `postgresql+asyncpg://aps:...@postgres:5432/household` (генерируется в compose) |

**⚠️ Не коммитить ни один `.env`** — оба должны быть в `.gitignore`.

### Dev: `backend/.env` (пример)

```env
# Database
DATABASE_URL=postgresql+asyncpg://aps:aps_secret@localhost:5432/household

# JWT
SECRET_KEY=change-me-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:3000

# Application
APP_NAME=APS Production Scheduler
APP_VERSION=4.9.0
DEBUG=true
DEFAULT_ORG_ID=00000000-0000-0000-0000-000000000001
```

### Prod: `.env` в корне (пример)

```env
# PostgreSQL (для контейнера БД)
POSTGRES_USER=aps
POSTGRES_PASSWORD=change_me_strong_password_min_16_chars
POSTGRES_DB=household

# JWT
SECRET_KEY=change_me_openssl_rand_hex_32_...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS (домены/IP облака)
ALLOWED_ORIGINS=https://your-domain.com,http://your-server-ip

# Frontend (вшивается в бандл при сборке Vite, не читается backend'ом!)
# После изменения — пересобрать: docker compose -f docker-compose.prod.yml build frontend
VITE_API_URL=https://your-domain.com

# Организация
DEFAULT_ORG_ID=00000000-0000-0000-0000-000000000001

# Application
APP_NAME=APS Production Scheduler
APP_VERSION=4.9.0
DEBUG=false
```

**⚠️ Про `VITE_API_URL`:** вшивается в JS-бандл **при сборке frontend**. После изменения — **обязательно пересобрать** frontend:
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d
```

### Переменные

| Переменная | Обязательна (dev) | Обязательна (prod) | По умолчанию | Описание |
|------------|-------------------|--------------------|--------------|----------|
| `DATABASE_URL` | ✅ | ❌ (генерируется в compose) | `...@localhost:5432/household` | Строка подключения к PostgreSQL |
| `SECRET_KEY` | ✅ | ✅ | `your-super-secret-key-...` | Секрет для подписи JWT (мин. 32 символа) |
| `ALGORITHM` | ❌ | ❌ | `HS256` | Алгоритм JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | ❌ | `1440` | Время жизни токена (мин) |
| `ALLOWED_ORIGINS` | ❌ | ✅ | `http://localhost:5173,...` | CORS-источники через запятую |
| `DEFAULT_ORG_ID` | ❌ | ❌ | `00000000-...-0001` | ID организации по умолчанию |
| `APP_NAME` | ❌ | ❌ | `APS Production Scheduler` | Название приложения |
| `APP_VERSION` | ❌ | ❌ | `4.9.0` | Версия приложения |
| `DEBUG` | ❌ | ❌ | `false` | Режим отладки (в prod — `false`) |

> **Про `VITE_API_URL`:** это **не backend env-переменная**, а build-time
> переменная frontend. Читается Vite при сборке (`import.meta.env.VITE_API_URL`),
> не backend'ом. Описана отдельно — в разделе «Prod: `.env` в корне (пример)»
> и в [frontend/src/config.ts](../frontend/src/config.ts).

**Регистр имён полей важен:** `case_sensitive=True` в `SettingsConfigDict`.

**Сгенерировать `SECRET_KEY`:**
```bash
openssl rand -hex 32
```

**Сгенерировать `POSTGRES_PASSWORD`:**
```bash
openssl rand -base64 24
```

---

## Docker-параметры

### Dev: `docker/docker-compose.yml`

Только PostgreSQL. Порт пробрасывается на хост (`5432:5432`).

```bash
docker compose -f docker/docker-compose.yml up -d
```

| Параметр | Значение | Описание |
|----------|----------|----------|
| Образ | `postgres:17` | |
| `POSTGRES_USER` | `aps` | Пользователь БД |
| `POSTGRES_PASSWORD` | `aps_secret` | Пароль (dev — упрощённый) |
| `POSTGRES_DB` | `household` | Имя БД |
| Порт | `5432:5432` | Пробрасывается на хост |
| Volume | `pgdata` | Персистентные данные |

### Prod: `docker-compose.prod.yml`

4 сервиса: `postgres`, `backend`, `frontend`, `nginx` — все в Docker.
Описание сервисов (образы, порты, volumes, зависимости) — в
[docs/DOCKER.md](DOCKER.md).

```bash
docker compose -f docker-compose.prod.yml up -d
```

**Переменные для контейнера PostgreSQL** (читает сам образ `postgres:17`
при инициализации):

| Переменная | Обязательна | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `POSTGRES_USER` | ✅ | `aps` | Пользователь БД |
| `POSTGRES_PASSWORD` | ✅ | — | Пароль БД (мин. 16 символов) |
| `POSTGRES_DB` | ✅ | `household` | Имя БД |

> **Эти переменные — НЕ для backend'а.** Они пробрасываются в контейнер
> PostgreSQL через `environment:` в compose. Backend подключается к БД
> через `DATABASE_URL`, который **автоматически** генерируется в compose
> из этих трёх переменных с хостом `postgres` (имя сервиса).

**⚠️ Не пробрасывайте `5432:5432`** для `postgres` — иначе БД будет
доступна из интернета.

### Backend

| Параметр | Значение | Описание |
|----------|----------|----------|
| Порт | `8000` | Внутри контейнера |
| Host | `0.0.0.0` | Слушает все интерфейсы |
| Workers | `2` (prod), `1` (dev) | Uvicorn workers |
| Reload | `false` (prod), `true` (dev) | В prod — без файлового watcher |
| Timeout | `600` | Solver timeout (по умолчанию) |

### Frontend

| Параметр | Значение | Описание |
|----------|----------|----------|
| Порт (host) | ❌ не пробрасывается | Только через nginx |
| Порт (внутри) | `80` | nginx:alpine отдаёт статику |
| API URL | `VITE_API_URL` | Вшивается при сборке |

---

## Приоритеты

### Уровни настроек

```
┌─────────────────────────────────────────────────────────────┐
│                    Чтение настройки                         │
│                                                             │
│  read_setting(db, org_id, key, default, version_id)         │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Если version_id задан:                             │  │
│  │    SELECT setting_value FROM plan_settings            │  │
│  │    WHERE schedule_version_id = version_id             │  │
│  │      AND setting_key = key                            │  │
│  │    → если найдено, вернуть.                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓ не найдено                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. SELECT setting_value FROM app_settings             │  │
│  │    WHERE organization_id = org_id                     │  │
│  │      AND setting_key = key                            │  │
│  │    → если найдено, вернуть.                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓ не найдено                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 3. Вернуть default.                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Dev vs Prod (.env)

| Переменная | В Dev | В Prod |
|------------|-------|--------|
| `DATABASE_URL` | Из `backend/.env` (`localhost:5432`) | **Генерируется** в compose (`postgres:5432`) |
| `SECRET_KEY` | Из `backend/.env` (dev-значение) | Из `.env` в корне (**сильный**) |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Домен/IP облака |
| `VITE_API_URL` | Не задаётся (fallback `localhost:8000`) | Домен/IP облака |
| `DEBUG` | `true` | `false` |
| `APP_VERSION` | `4.9.0` | `4.9.0` |

**Важно:** в Docker `backend/.env` **не читается** — переменные пробрасываются через `environment:` в compose. Файл `backend/.env` в образ **не копируется** (исключён в `backend/.dockerignore`).

---

## Валидация

### На уровне БД

- `UNIQUE (schedule_version_id, setting_key)` — защита от дублей в `plan_settings`.
- `UNIQUE (organization_id, setting_key)` — защита от дублей в `app_settings`.
- `FOREIGN KEY ... ON DELETE CASCADE` — при удалении плана настройки удаляются.
- `CHECK (value_type IN ('int', 'float', 'bool', 'str', 'json', 'select'))`.

### На уровне API

`validate_setting` в `backend/app/scheduler/settings.py`:
- Проверка типа (`value_type`).
- Проверка диапазона (`min_value`, `max_value`).
- Проверка допустимых значений (`options` для `select`).

**Пример ошибки:**
```json
{
  "detail": "horizon_hours: значение 10000 больше максимума 8760"
}
```

### На уровне UI

- `SettingsPage.tsx` — группировка по категориям, слайдеры, чекбоксы.
- `PlanSettingsWizard.tsx` — 9 шагов, индикация изменённых полей.
- Системные настройки (`is_system`) — заблокированы с Tooltip.

---

## Примеры

### Изменить глобальную настройку

```bash
curl -X PUT http://localhost:8000/api/v1/settings/horizon_hours \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": 1440}'
```

### Изменить настройку конкретного плана

```bash
curl -X PUT http://localhost:8000/api/v1/plan-settings/version/$VERSION_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"settings": {"horizon_hours": 1440, "weight_makespan": 0.8}}'
```

### Сбросить настройки плана к глобальным

```bash
curl -X POST http://localhost:8000/api/v1/plan-settings/version/$VERSION_ID/reset \
  -H "Authorization: Bearer $TOKEN"
```

### Сменить режим смен

```bash
curl -X POST http://localhost:8000/api/v1/settings/shift-mode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "3x8"}'
```

**⚠️ Внимание:** при смене режима смен таблица `shift` пересоздаётся, `shift_id` в `scheduled_task` сбрасывается. Требуется пересчитать план.

### Отключить архивацию версий (Итерация 13.21)

```bash
curl -X PUT http://localhost:8000/api/v1/settings/auto_archive_on_recalc \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": false}'
```

**Эффект:** старая версия останется в списке как обычная после пересчёта.
Полезно, если нужно сохранять историю планов для сравнения.

### Разархивировать конкретную версию

```bash
curl -X PUT http://localhost:8000/api/v1/schedule/versions/$VERSION_ID/unarchive \
  -H "Authorization: Bearer $TOKEN"
```

**Проверка из БД:**
```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_archived, is_active
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC
LIMIT 10;
"
```

---

## Настройки, не относящиеся к app_settings

Некоторые параметры системы настраиваются **не через `app_settings`**,
а через контент в БД. Они не участвуют в приоритете `plan_settings` →
`app_settings`, но влияют на поведение UI.

### Справка (`help_article`) — Итерации 15.1, 15.4, 15.5

Контент статей справки и FAQ. Таблица `help_article`:
- `slug`, `title`, `category`, `content_md`, `tags`, `display_order`, `is_published`.

**Категории:** `getting-started`, `planning`, `gantt`, `shift`, `lab`,
`cz`, `whatif`, `settings`, **`faq`** (Итерация 15.4).

**Редактирование:**
- **Итерация 15.5:** через UI (роль ADMIN) — страница «Помощь».
- Альтернативно — через SQL или seed-миграции:
  ```
  docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
  docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
  ```

### Контекстные подсказки (`help_hint`) — Итерация 15.2

Короткие подсказки, привязанные к элементам UI. Таблица `help_hint`:
- `hint_key` (формат `<module>.<action>`), `title`, `body_md`, `article_slug`, `display_order`, `is_published`.

**8 стартовых подсказок:**
- `planning.recalc`, `planning.advisor`, `planning.plan_dirty`
- `gantt.edit_mode`, `gantt.brackets`
- `shift.lab_block`, `whatif.json`, `settings.system`

**Правки** — только через SQL или seed-миграции (`add_25_seed.sql`).
**Через UI редактирование подсказок не реализовано** (по состоянию на
Итерацию 15.5).

### Интерактивный туториал — Итерация 15.3

Конфигурация туров хранится **на фронтенде** в файле
`frontend/src/tutorial/tours.ts`. Не относится к `app_settings`.

**Прогресс прохождения** сохраняется в `localStorage` браузера:
- Ключ: `aps_tutorial_completed_<tour_id>`.
- Значение: `'true'`.
- Сброс — через UI (`HelpPage` → «Интерактивные туры» → «Пройти заново»).

**Статья `tutorial-interactive`** добавлена в `help_article` через
seed-миграцию `add_27_seed_1.sql` (категория `getting-started`).

**Дополнительных настроек** для туториала **не требуется**.

### Docker (prod) — Итерация 16.x

Для развёртывания в облаке добавлены:

- **`.env.example`** (корень) — шаблон prod-переменных.
- **`.env`** (корень) — реальные значения, не коммитится.
- **`docker-compose.prod.yml`** (корень) — 4 сервиса.
- **`backend/init_schema_v4.9.sql`** — полная схема v4.9.0.
- **`backend/init_schema_v4.9_seed.sql`** — seed-статьи справки.
- **`scripts/deploy_init.sh`** / **`.ps1`** — инициализация БД.

Подробно — в [DEPLOYMENT.md](DEPLOYMENT.md) и [DOCKER.md](DOCKER.md).

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание в облаке.
- [docs/DOCKER.md](DOCKER.md) — Docker: устройство и отладка.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.