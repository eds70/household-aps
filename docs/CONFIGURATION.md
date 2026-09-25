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
| `max_fill_percent` | `float` | `0.95` | `0.5` | `1.0` | Макс. загрузка реактора |

### Категория `shifts` — Режим смен

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `shift_mode` | `select` | `1x8` | Режим смен: `1x8`, `3x8`, `2x12` |
| `shift_intervals` | `json` | `[{"start":"08:00","end":"16:00"}]` | Интервалы смен (is_system) |
| `shift_duration_hours` | `int` | `8` | Длительность смены (is_system) |
| `work_start_time` | `str` | `08:00` | Начало рабочего дня |
| `work_end_time` | `str` | `16:00` | Конец рабочего дня |

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
| `max_task_hours_for_calendar` | `int` | `24` | Макс. длительность задачи (ч) |
| `max_fill_part_hours` | `int` | `6` | Макс. длительность подзадачи LINE_FILL (ч) |
| `allow_weekend_work` | `bool` | `false` | Разрешить работу в выходные |

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
| `cz_completion_threshold` | `float` | `0.95` | `0.5` | `1.0` | Порог завершения маркировки |
| `cz_api_key` | `str` | `dev-cz-api-key-change-in-production` | — | — | API-key для камер |
| `enable_cz_auto_close` | `bool` | `false` | — | — | Автозакрытие задачи слива |

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

1. **При создании плана** (`INSERT INTO schedule_version`) триггер `copy_app_settings_to_plan` автоматически копирует все 32 настройки из `app_settings` в `plan_settings` этого плана.
2. **Мастер настроек плана** (`PlanSettingsWizard.tsx`) позволяет переопределить значения для конкретного плана через `PUT /api/v1/plan-settings/version/{id}`.
3. **Планировщик** (`DataLoader`) читает настройки из `plan_settings`, если передан `version_id`. Если `version_id=None` или `plan_settings` пуст — fallback на `app_settings`.

### Категории, влияющие на план (23 из 32)

| Категория | Ключи |
|-----------|-------|
| `planning` | `planning_start_date`, `horizon_hours`, `timeout_seconds`, `max_fill_percent` |
| `shifts` | `shift_mode`, `shift_intervals`, `shift_duration_hours`, `work_start_time`, `work_end_time` |
| `calendar` | `allow_weekend_work`, `max_task_hours_for_calendar`, `max_fill_part_hours` |
| `cooling` | `enable_cooling_degradation`, `cooling_degradation_factor`, `cooling_zone_capacity` |
| `resources` | `enable_operator_pools`, `enable_manual_station` |
| `materials` | `enable_material_constraints` |
| `lab` | `enable_lab_blocking` |
| `features` | `enable_tank_routing`, `enable_advisor`, `enable_shift_planning`, `enable_rescheduling` |
| `optimization` | `weight_makespan`, `weight_setup`, `weight_underload`, `weight_cooling_slow`, `weight_tardiness` |

### Мастер настроек плана — 9 шагов

1. Основные (`planning`).
2. Режим смен (`shifts`).
3. Календарь (`calendar`).
4. Охлаждение (`cooling`).
5. Ресурсы (`resources`).
6. Материалы и лаборатория (`materials` + `lab`).
7. Маршруты и функции (`features`).
8. Честный Знак (`cz`).
9. Оптимизация (`optimization`).

### Права

Редактировать `plan_settings` может только `ADMIN` или `PLANNER`.

### Системные настройки

`shift_intervals`, `shift_duration_hours` — `is_system = true`, не редактируются через мастер. Управляются режимом смен (`shift_mode`).

---

## .env

**Файл `backend/.env`** — переменные окружения.

### Пример

```env
# Database
DATABASE_URL=postgresql+asyncpg://aps:aps_secret@localhost:5432/household

# JWT
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=60

# CZ
CZ_API_KEY=dev-cz-api-key-change-in-production

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Переменные

| Переменная | Обязательна | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `DATABASE_URL` | ✅ | — | Строка подключения к PostgreSQL |
| `JWT_SECRET` | ✅ | — | Секрет для подписи JWT |
| `JWT_ALGORITHM` | ❌ | `HS256` | Алгоритм JWT |
| `JWT_EXPIRES_MINUTES` | ❌ | `60` | Время жизни токена (мин) |
| `CZ_API_KEY` | ❌ | `dev-cz-api-key-change-in-production` | API-key для камер ЧЗ |
| `LOG_LEVEL` | ❌ | `INFO` | Уровень логирования |
| `CORS_ORIGINS` | ❌ | `http://localhost:5173` | Разрешённые origin'ы |

---

## Docker-параметры

### PostgreSQL

```bash
docker run --name aps_postgres \
  -e POSTGRES_USER=aps \
  -e POSTGRES_PASSWORD=aps_secret \
  -e POSTGRES_DB=household \
  -p 5432:5432 \
  -d postgres:16
```

| Параметр | Значение | Описание |
|----------|----------|----------|
| `POSTGRES_USER` | `aps` | Пользователь БД |
| `POSTGRES_PASSWORD` | `aps_secret` | Пароль |
| `POSTGRES_DB` | `household` | Имя БД |
| `-p` | `5432:5432` | Порт |

### Backend

| Параметр | Значение | Описание |
|----------|----------|----------|
| Порт | `8000` | Uvicorn |
| Host | `0.0.0.0` | Слушает все интерфейсы |
| Workers | `1` | Для async-приложения |
| Timeout | `600` | Solver timeout (по умолчанию) |

### Frontend

| Параметр | Значение | Описание |
|----------|----------|----------|
| Порт | `5173` | Vite dev server |
| Host | `localhost` | Локально |
| API URL | `http://localhost:8000` | Backend |

---

## Приоритеты

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

---

## Валидация

### На уровне БД

- `UNIQUE (schedule_version_id, setting_key)` — защита от дублей.
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

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.