# API Reference

REST API системы **APS Production Scheduler**.

**Базовый URL:** `http://localhost:8000`
**Swagger UI:** `http://localhost:8000/docs`
**OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## 📋 Содержание

- [Авторизация](#авторизация)
- [Справочники](#справочники)
- [Планирование](#планирование)
- [Advisor](#advisor)
- [Сменное планирование](#сменное-планирование)
- [Перепланирование](#перепланирование)
- [Лаборатория](#лаборатория)
- [Персонал](#персонал)
- [Честный Знак](#честный-знак)
- [Настройки](#настройки)
- [Настройки плана](#настройки-плана)
- [What-if](#what-if)
- [Аудит](#аудит)
- [Справка](#справка)
- [Гант](#гант)
- [Соглашения](#соглашения)

---

## Авторизация

### `POST /api/v1/auth/login`

Вход в систему.

**Тело:**
```json
{
  "email": "admin@household.ru",
  "password": "admin123"
}
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Права:** публичный.

---

### `GET /api/v1/auth/me`

Профиль текущего пользователя.

**Заголовки:** `Authorization: Bearer <token>`

**Ответ:**
```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "email": "admin@household.ru",
  "role": "ADMIN",
  "organization_id": "00000000-0000-0000-0000-000000000001"
}
```

**Права:** любой авторизованный.

---

### `POST /api/v1/auth/change-password`

Смена пароля.

**Тело:**
```json
{
  "old_password": "admin123",
  "new_password": "newsecurepassword"
}
```

**Права:** любой авторизованный.

---

## Справочники

### Оборудование

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/equipment` | Список оборудования | любой |
| `POST` | `/api/v1/equipment` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/equipment/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/equipment/{id}` | Удалить | ADMIN |

**Поля:** `id`, `code`, `name`, `equipment_type`, `capacity_kg`, `is_active`.

**Query-параметр:** `version_id` (optional) — читать из снапшота.

---

### Продукты

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/products` | Список | любой |
| `POST` | `/api/v1/products` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/products/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/products/{id}` | Удалить | ADMIN |

**Query-параметр:** `version_id` (optional).

---

### Материалы

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/materials` | Список | любой |
| `POST` | `/api/v1/materials` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/materials/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/materials/{id}` | Удалить | ADMIN |

**Итерация 13.1–13.3:** в ответе `GET /` — остатки (`stock_qty`, `reserved_qty`).

---

### Рецептуры

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/recipes` | Список | любой |
| `POST` | `/api/v1/recipes` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/recipes/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/recipes/{id}` | Удалить | ADMIN |

---

### Техкарты (операции)

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/operations` | Список | любой |
| `POST` | `/api/v1/operations` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/operations/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/operations/{id}` | Удалить | ADMIN |

**Поля:** `id`, `code`, `name`, `equipment_type`, `duration_min`, `needs_lab`, `needs_cooling_zone`, `needs_boiler`, `linked_equipment_id`.

---

### Заказы

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/orders` | Список | любой |
| `POST` | `/api/v1/orders` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/orders/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/orders/{id}` | Удалить | ADMIN |

**Поля:** `id`, `product_id`, `volume_kg`, `due_date`, `priority`, `status`.

---

### Календарь простоев

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/calendar` | Список событий | любой |
| `POST` | `/api/v1/calendar` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/calendar/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/calendar/{id}` | Удалить | ADMIN |

**Поля:** `id`, `equipment_id`, `event_type`, `start_at`, `end_at`, `reason`.

**Типы событий:** `WEEKEND`, `MAINTENANCE`, `BREAKDOWN`, `HOLIDAY`.

---

## Планирование

### `POST /api/v1/schedule/build`

Построить план.

**Тело:**
```json
{
  "version_name": "План на октябрь",
  "horizon_hours": 720,
  "timeout_seconds": 600,
  "version_id": null
}
```

**Ответ:**
```json
{
  "version_id": "uuid",
  "status": "OPTIMAL",
  "makespan_min": 12526,
  "tasks_count": 282,
  "solve_time_sec": 78.3
}
```

**Права:** ADMIN, PLANNER.

---

### `GET /api/v1/schedule/versions`

Список версий плана.

**Query:**
- `include_archived` (optional, bool, default=`false`) — показывать ли архивные версии.

**Ответ:**
```json
[
  {
    "id": "uuid",
    "name": "План на октябрь",
    "is_active": true,
    "is_archived": false,
    "parent_version_id": null,
    "created_at": "2026-09-25T10:00:00Z",
    "created_by": "admin@household.ru",
    "has_snapshot": true
  },
  {
    "id": "uuid-2",
    "name": "z1",
    "is_active": false,
    "is_archived": true,
    "parent_version_id": null,
    "created_at": "2026-09-25T13:46:20Z",
    "has_snapshot": false
  }
]
```

**Поля ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `has_snapshot` | `bool` | `true` — снапшоты справочников заполнены, план можно открыть в readonly-режиме. `false` — план пуст. |
| `is_archived` | `bool` | Итерация 13.21: `true` — версия в архиве, скрыта из списка по умолчанию. |
| `parent_version_id` | `UUID \| null` | Итерация 13.21: ID родительской версии для построения иерархии. |

**Права:** любой.

---

### `POST /api/v1/schedule/versions`

Создать пустую версию (без расчёта).

**Тело:**
```json
{
  "name": "Черновик",
  "version_type": "MONTHLY",
  "comment": "..."
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "name": "Черновик",
  "version_type": "MONTHLY",
  "is_active": false,
  "is_archived": false,
  "created_at": "2026-09-25T17:22:00Z",
  "comment": "...",
  "has_snapshot": true,
  "snapshot_stats": {
    "equipment": 10,
    "products": 7,
    "operations": 27,
    "calendar_events": 5
  }
}
```

**Права:** ADMIN, PLANNER.

**Логика (Итерация 13.15):**
1. `INSERT INTO schedule_version`.
2. Триггер `copy_app_settings_to_plan` копирует `app_settings` → `plan_settings`.
3. `snapshot_all_catalogs()` заполняет снапшоты.

---

### `DELETE /api/v1/schedule/versions/{id}`

Удалить версию (CASCADE).

**Права:** ADMIN.

---

### `PUT /api/v1/schedule/versions/{id}/unarchive`

**Итерация 13.21:** разархивировать версию плана.

Возвращает версию в список «Истории планов» (`is_archived = FALSE`).
Версия НЕ становится активной автоматически.

**Ответ:**
```json
{
  "status": "success",
  "version_id": "uuid",
  "name": "План на октябрь",
  "is_archived": false,
  "is_active": false,
  "message": "Версия «План на октябрь» разархивирована"
}
```

**Ошибки:**
- `400` — колонка `is_archived` не найдена (не применена миграция `add_23.sql`).
- `400` — версия не находится в архиве.
- `404` — версия не найдена.

**Права:** ADMIN, PLANNER.

---

## Advisor

### `GET /api/v1/schedule/advice`

Подсказки Advisor.

**Query:**
- `version_id` (optional) — ID плана. Если не задан — последняя активная версия.

**Ответ:**
```json
{
  "advice": [
    {
      "type": "MATERIAL_SHORTAGE",
      "severity": "CRITICAL",
      "message": "Дефицит отдушки: 150 кг",
      "batch_id": "uuid",
      "material_id": "uuid"
    },
    {
      "type": "CZ_INCOMPLETE",
      "severity": "WARNING",
      "message": "Партия слита, но не промаркирована",
      "batch_id": "uuid"
    }
  ]
}
```

**Типы:** `MATERIAL_SHORTAGE`, `UNDERLOAD`, `ROUTE_MISMATCH`, `EQUIPMENT_GAP`, `COOLING_DEGRADATION`, `CZ_INCOMPLETE`.

**Права:** любой.

---

### `POST /api/v1/schedule/feasibility`

Оценка исполнимости плана.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
{
  "is_feasible": true,
  "score": 0.85,
  "issues": []
}
```

**Права:** любой.

---

## Сменное планирование

### `GET /api/v1/shift/list`

Список смен.

**Query:**
- `version_id` (optional).
- `date_from`, `date_to` (optional).

**Права:** любой.

---

### `GET /api/v1/shift/by-date/{date}`

Смены на дату.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
[
  {
    "id": "uuid",
    "name": "Смена 1",
    "starts_at": "2026-09-01T08:00:00+03:00",
    "ends_at": "2026-09-01T16:00:00+03:00",
    "is_working": true
  }
]
```

**Права:** любой.

---

### `GET /api/v1/shift/{shift_id}/tasks`

Задачи смены.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

### `GET /api/v1/shift/{shift_id}/carryover`

Переходящие задачи из предыдущей смены.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

### `POST /api/v1/shift/task/{task_id}/fact`

Внести факт по задаче.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "actual_start": "2026-09-01T08:30:00Z",
  "actual_end": "2026-09-01T10:15:00Z",
  "actual_qty": 4800,
  "status": "DONE"
}
```

**Права:** MASTER, ADMIN, PLANNER.

---

## Перепланирование

### `POST /api/v1/schedule/reschedule`

Перепланировать.

**Тело:**
```json
{
  "from_version_id": "uuid",
  "reason": "BREAKDOWN",
  "changes": {
    "equipment_id": "uuid",
    "start_at": "2026-09-25T00:00:00Z",
    "end_at": "2026-09-28T00:00:00Z"
  },
  "frozen_before": "2026-09-25T00:00:00Z",
  "replace_version_id": "uuid"
}
```

**Типы изменений:** `DELAY`, `BREAKDOWN`, `QTY_CHANGE`, `MANUAL`.

**Итерация 13.21:** `replace_version_id` (optional) — если передан, старая версия архивируется после пересчёта (при условии, что она не используется в what-if).

**Ответ:**
```json
{
  "status": "success",
  "from_version_id": "uuid",
  "to_version_id": "uuid",
  "affected_tasks": 10,
  "moved_tasks": 282,
  "frozen_tasks": 0,
  "message": "Создана новая версия плана",
  "diff": {},
  "replace_archived": true,
  "replace_blocked": false,
  "replace_blocked_reason": null,
  "used_by_whatif": []
}
```

**Поля ответа (Итерация 13.21):**

| Поле | Тип | Описание |
|------|-----|----------|
| `replace_archived` | `bool` | `true` — старая версия успешно архивирована. |
| `replace_blocked` | `bool` | `true` — архивация не удалась (версия используется в what-if). |
| `replace_blocked_reason` | `string \| null` | Причина, по которой архивация пропущена. |
| `used_by_whatif` | `[str]` | ID what-if сценариев, из-за которых архивация пропущена. |

**Права:** ADMIN, PLANNER.

---

### `GET /api/v1/schedule/compare`

Сравнить две версии.

**Query:**
- `version_a` — ID первой версии.
- `version_b` — ID второй версии.

**Ответ:**
```json
{
  "makespan_a": 12526,
  "makespan_b": 11800,
  "delta_min": -726,
  "tasks_changed": 45
}
```

**Права:** любой.

---

### `PUT /api/v1/schedule/task/{id}/pin`

Закрепить/открепить задачу.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "is_pinned": true
}
```

**Права:** ADMIN, PLANNER.

---

### `PUT /api/v1/schedule/task/{id}/move`

Переместить задачу (drag-and-drop).

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "new_start": "2026-09-25T10:00:00Z"
}
```

**Валидация:** длительность задачи не может меняться при перемещении.

**Права:** ADMIN, PLANNER.

---

### `PUT /api/v1/schedule/task/{id}/resize`

**Итерация 13.17:** изменить длительность задачи.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "new_start": "2026-09-25T10:00:00Z",
  "new_end": "2026-09-25T14:00:00Z"
}
```

**Ошибки:**
- `400` — с `detail.reason` и `detail.details`.
- `409` — каскад заблокирован pinned-задачей.

**Права:** ADMIN, PLANNER.

---

### `PUT /api/v1/schedule/task/{id}/move-cascade`

**Итерация 13.17:** переместить задачу с каскадом.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "new_start": "2026-09-25T10:00:00Z",
  "new_end": "2026-09-25T14:00:00Z"
}
```

**Ответ:** содержит `moved_tasks: [{task_id, operation_name, equipment_id, new_start, new_end}]`.

**Права:** ADMIN, PLANNER.

---

## Лаборатория

### `GET /api/v1/lab/pending`

Партии, ожидающие анализа / заблокированные.

**Query:**
- `version_id` (optional).

**Права:** LAB, MASTER, ADMIN.

---

### `GET /api/v1/lab/batch/{id}`

Статус партии по лаборатории.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
{
  "batch_id": "uuid",
  "lab_status": "PENDING_LAB",
  "is_lab_blocked": false,
  "lab_block_reason": null
}
```

**Права:** LAB, MASTER, ADMIN.

---

### `GET /api/v1/lab/batch/{id}/log`

Журнал проверок партии.

**Query:**
- `version_id` (optional).

**Права:** LAB, MASTER, ADMIN.

---

### `POST /api/v1/lab/batch/{id}/block`

Заблокировать партию.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "reason": "Не соответствует ГОСТ"
}
```

**Права:** LAB, MASTER, ADMIN.

---

### `POST /api/v1/lab/batch/{id}/unblock`

Разблокировать.

**Query:**
- `version_id` (optional).

**Права:** LAB, MASTER, ADMIN.

---

### `POST /api/v1/lab/batch/{id}/approve`

Одобрить после анализа.

**Query:**
- `version_id` (optional).

**Права:** LAB, MASTER, ADMIN.

---

### `POST /api/v1/lab/batch/{id}/request`

Запросить анализ.

**Query:**
- `version_id` (optional).

**Права:** LAB, MASTER, ADMIN.

---

## Персонал

### `GET /api/v1/personnel/pools`

Список пулов с загрузкой.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
[
  {
    "id": "uuid",
    "type": "REACTOR_OPERATOR",
    "capacity": 3,
    "tasks_count": 45,
    "peak_concurrent": 3,
    "load_percent": 100.0
  }
]
```

**Права:** любой.

---

### `GET /api/v1/personnel/pools/{id}`

Один пул.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

### `PUT /api/v1/personnel/pools/{id}`

Редактировать capacity.

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "capacity": 5
}
```

**Права:** ADMIN, PLANNER.

---

### `GET /api/v1/personnel/load`

Краткая загрузка.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

## Честный Знак

### `POST /api/v1/cz/scan`

Приём скана от камеры.

**Заголовки:** `X-CZ-Api-Key: <key>`

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "cz_code": "0104600000000001215TEST0000000001",
  "gtin": "04600000000001",
  "line_code": "LINE_1",
  "camera_id": "CAM-01",
  "batch_id": null,
  "task_id": null
}
```

**Ответ:**
```json
{
  "scan_id": "uuid",
  "batch_id": "uuid",
  "duplicate": false
}
```

**Идемпотентность:** `UNIQUE (organization_id, cz_code)` + `ON CONFLICT DO NOTHING`.

**Права:** камера (API-key).

---

### `GET /api/v1/cz/batch/{id}/progress`

Прогресс маркировки партии.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
{
  "batch_id": "uuid",
  "planned_qty": 5000,
  "marked_qty": 4750,
  "percent": 95.0,
  "cz_status": "COMPLETED"
}
```

**Права:** любой.

---

### `GET /api/v1/cz/pending`

Партии в ожидании маркировки.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

### `GET /api/v1/cz/log`

Журнал сканирований с фильтрами.

**Query:**
- `version_id` (optional).
- `line_code` (optional).
- `only_orphans` (optional, bool).

**Права:** любой.

---

### `GET /api/v1/cz/stats`

Сводная статистика.

**Query:**
- `version_id` (optional).

**Права:** любой.

---

### `POST /api/v1/cz/scan/{id}/attach`

Ручное сопоставление «сироты».

**Query:**
- `version_id` (optional).

**Тело:**
```json
{
  "batch_id": "uuid"
}
```

**Права:** ADMIN, PLANNER, MASTER.

---

### `DELETE /api/v1/cz/scan/{id}`

Удаление скана.

**Query:**
- `version_id` (optional).

**Права:** ADMIN.

---

## Настройки

### `GET /api/v1/settings/schema`

Схема всех настроек с метаданными.

**Права:** любой.

---

### `GET /api/v1/settings/categories`

Список категорий.

**Права:** любой.

---

### `GET /api/v1/settings/`

Все настройки.

**Права:** любой.

---

### `GET /api/v1/settings/category/{cat}`

Настройки категории.

**Категории:** `planning`, `shifts`, `cooling`, `calendar`, `lab`, `materials`, `cz`, `resources`, `features`, `optimization`.

**Права:** любой.

---

### `PUT /api/v1/settings/`

Массовое обновление.

**Тело:**
```json
{
  "settings": {
    "horizon_hours": 1440,
    "timeout_seconds": 900,
    "auto_archive_on_recalc": true
  }
}
```

**Права:** ADMIN, PLANNER.

**Итерация 13.21:** настройка `auto_archive_on_recalc` управляет архивацией старой версии при пересчёте.

---

### `PUT /api/v1/settings/{key}`

Обновить одну настройку.

**Тело:**
```json
{
  "value": 1440
}
```

**Права:** ADMIN, PLANNER.

---

### `POST /api/v1/settings/shift-mode`

Сменить режим смен.

**Тело:**
```json
{
  "mode": "3x8"
}
```

**Режимы:** `1x8`, `3x8`, `2x12`.

**Права:** ADMIN.

---

## Настройки плана

### `GET /api/v1/plan-settings/version/{version_id}`

Настройки плана + метаданные.

**Ответ:**
```json
{
  "version_id": "uuid",
  "settings": {
    "horizon_hours": {
      "value": 720,
      "value_type": "int",
      "category": "planning",
      "label": "Горизонт планирования (ч)",
      "min_value": 24,
      "max_value": 8760,
      "is_system": false
    }
  }
}
```

**Права:** любой.

---

### `PUT /api/v1/plan-settings/version/{version_id}`

Массовое обновление.

**Тело:**
```json
{
  "settings": {
    "horizon_hours": 1440,
    "weight_makespan": 0.8,
    "weight_tardiness": 0.2
  }
}
```

**Валидация:** через `validate_setting`.

**Права:** ADMIN, PLANNER.

---

### `POST /api/v1/plan-settings/version/{version_id}/reset`

Сброс к глобальным `app_settings`.

**Права:** ADMIN, PLANNER.

---

## What-if

### `POST /api/v1/whatif/scenarios`

Создать сценарий.

**Тело:**
```json
{
  "name": "Test +20% cream",
  "base_version_id": "uuid",
  "changes": {
    "shift_mode": "3x8",
    "resource_capacity": {
      "REACTOR_OPERATOR": 5
    }
  }
}
```

**Типы изменений:** `add_order`, `cancel_order`, `change_qty`, `change_due_date`, `shift_mode`, `resource_capacity`, `calendar_events`.

**Права:** ADMIN, PLANNER.

---

### `GET /api/v1/whatif/scenarios`

Список сценариев.

**Права:** любой.

---

### `GET /api/v1/whatif/scenarios/{id}`

Один сценарий.

**Права:** любой.

---

### `PUT /api/v1/whatif/scenarios/{id}`

Обновить.

**Права:** ADMIN, PLANNER.

---

### `DELETE /api/v1/whatif/scenarios/{id}`

Удалить.

**Ограничение:** нельзя удалить сценарий в статусе `RUNNING`.

**Права:** ADMIN, PLANNER.

---

### `POST /api/v1/whatif/scenarios/{id}/run`

Запустить.

**Ответ:** `202 Accepted`

**Статусы:** `DRAFT` → `RUNNING` → `DONE`/`FAILED`.

**Права:** ADMIN, PLANNER.

---

### `GET /api/v1/whatif/scenarios/{id}/compare`

Сравнить base vs result.

**Ответ:**
```json
{
  "base": {
    "makespan_min": 12526,
    "setup_min": 450,
    "underload_kg": 1200
  },
  "result": {
    "makespan_min": 11800,
    "setup_min": 420,
    "underload_kg": 800
  },
  "delta": {
    "makespan_min": -726,
    "setup_min": -30,
    "underload_kg": -400
  }
}
```

**Права:** любой.

---

## Аудит

### `GET /api/v1/audit/log`

Объединённый журнал событий из 4 источников.

**Query:**
- `sources` (optional, CSV) — `STOCK,RESCHEDULE,LAB,CZ`.
- `severity` (optional) — `INFO | WARNING | CRITICAL`.
- `date_from`, `date_to` (optional).
- `search` (optional) — подстрока в title/description.
- `limit` (default 200, max 2000).

**Ответ:**
```json
{
  "events": [
    {
      "id": "uuid",
      "source": "LAB",
      "event_type": "BLOCKED",
      "severity": "WARNING",
      "title": "Лаборатория: заблокировано",
      "description": "Причина: pH вне нормы",
      "entity_type": "batch",
      "entity_id": "uuid",
      "entity_name": "Крем-мыло 1л",
      "actor_name": "Иванов И.И.",
      "occurred_at": "2026-09-25T12:00:00Z",
      "details": {}
    }
  ],
  "total": 42,
  "by_source": {"STOCK": 20, "RESCHEDULE": 10, "LAB": 8, "CZ": 4}
}
```

**Права:** любой.

---

### `GET /api/v1/audit/stats`

Счётчики по источникам за период.

**Query:**
- `days` (default 7).

**Ответ:**
```json
{
  "period_days": 7,
  "date_from": "2026-09-18T00:00:00Z",
  "date_to": "2026-09-25T00:00:00Z",
  "total": 42,
  "by_source": {"STOCK": 20, "RESCHEDULE": 10, "LAB": 8, "CZ": 4},
  "by_severity": {"INFO": 30, "WARNING": 10, "CRITICAL": 2}
}
```

**Права:** любой.

---

### `GET /api/v1/audit/sources`

Список доступных источников.

**Ответ:**
```json
{
  "sources": [
    {"key": "STOCK", "label": "Изменения остатков", "description": "Журнал material_stock_log"},
    {"key": "RESCHEDULE", "label": "Перепланирования", "description": "Журнал reschedule_log"},
    {"key": "LAB", "label": "Лаборатория", "description": "Блокировки и одобрения"},
    {"key": "CZ", "label": "Честный Знак", "description": "Сканы ЧЗ"}
  ]
}
```

**Права:** любой.

---

## Справка

**Итерации 15.1, 15.2 и 15.4.**

### `GET /api/v1/help/articles`

Список статей справки.

**Query:**
- `category` (optional) — фильтр по категории.

**Ответ:**
```json
{
  "articles": [
    {
      "slug": "intro-overview",
      "title": "Обзор системы",
      "category": "getting-started",
      "tags": ["обзор", "начало работы"],
      "display_order": 10,
      "updated_at": "2026-10-02T10:00:00Z"
    }
  ],
  "total": 30
}
```

**Права:** любой.

---

### `GET /api/v1/help/articles/{slug}`

Одна статья с markdown-контентом.

**Ответ:**
```json
{
  "slug": "intro-overview",
  "title": "Обзор системы",
  "category": "getting-started",
  "content_md": "# Обзор системы\n\n...",
  "tags": ["обзор", "начало работы"],
  "display_order": 10,
  "updated_at": "2026-10-02T10:00:00Z"
}
```

**Ошибки:**
- `404` — статья не найдена.

**Права:** любой.

---

### `GET /api/v1/help/categories`

Список категорий справки с количеством статей.

**Ответ:**
```json
{
  "categories": [
    {"key": "getting-started", "label": "Начало работы", "article_count": 2},
    {"key": "planning", "label": "Планирование", "article_count": 4},
    {"key": "gantt", "label": "Диаграмма Ганта", "article_count": 4},
    {"key": "shift", "label": "Мастера смены", "article_count": 1},
    {"key": "lab", "label": "Лаборатория", "article_count": 1},
    {"key": "cz", "label": "Честный Знак", "article_count": 1},
    {"key": "whatif", "label": "What-if", "article_count": 1},
    {"key": "settings", "label": "Настройки", "article_count": 1},
    {"key": "faq", "label": "FAQ", "article_count": 15}
  ]
}
```

**Итерация 15.4:** категория `faq` — последняя. Возвращается как обычная категория, без изменений в API.

**Права:** любой.

---

### `GET /api/v1/help/search`

Поиск по статьям.

**Query:**
- `q` (required, min 2) — поисковый запрос.
- `limit` (default 30, max 100).

**Ответ:**
```json
{
  "query": "гант",
  "hits": [
    {
      "slug": "gantt-overview",
      "title": "Обзор диаграммы Ганта",
      "category": "gantt",
      "snippet": "…Диаграмма Ганта — главный инструмент визуализации плана…"
    }
  ],
  "total": 1
}
```

**Логика:** поиск по `title ILIKE %q%` / `content_md ILIKE %q%` / `tags::text ILIKE %q%`.

**Примечание (15.4):** поиск работает и по FAQ-статьям — они хранятся в той же таблице `help_article`.

**Права:** любой.

---

### `GET /api/v1/help/hints`

**Итерация 15.2:** контекстные подсказки для элементов UI.

Возвращает словарь всех опубликованных подсказок. Фронт загружает
один раз в `HelpHintsContext` и раздаёт через `useHint(hintKey)`.

**Ответ:**
```json
{
  "hints": {
    "planning.recalc": {
      "hint_key": "planning.recalc",
      "title": "Пересчёт плана",
      "body_md": "Кнопка **«Пересчитать»** активна только при наличии несохранённых изменений.",
      "article_slug": "planning-recalculate",
      "display_order": 10
    },
    "gantt.edit_mode": {
      "hint_key": "gantt.edit_mode",
      "title": "Режим редактирования",
      "body_md": "По умолчанию план открывается в режиме **🔒 Просмотр**.",
      "article_slug": "gantt-editing",
      "display_order": 10
    }
  },
  "total": 8
}
```

**Права:** любой.

**Формат `hint_key`:** `<module>.<action>` (например, `planning.recalc`,
`gantt.edit_mode`, `shift.lab_block`, `whatif.json`, `settings.system`).

**Примечание:** если в `article_slug` указан slug статьи справки — фронт
показывает в Popover кнопку «Читать подробнее». Если `null` — подсказка
самодостаточна.

---

### `GET /api/v1/help/docs/{filename}`

Отдача файлов `docs/*.md`.

**Ограничения:**
- Только файлы `.md`.
- Имя файла не должно содержать `/`, `\`, `..`.
- Размер файла — не более 1 МБ.

**Ответ:**
```json
{
  "filename": "API.md",
  "content_md": "# API Reference\n\n...",
  "size": 29045
}
```

**Ошибки:**
- `400` — не `.md`, или содержит path traversal.
- `404` — файл не найден.
- `413` — файл больше 1 МБ.

**Права:** любой.

---

## Гант

### `GET /api/v1/gantt/`

Данные для диаграммы Ганта.

**Query:**
- `version_id` (optional).

**Ответ:**
```json
{
  "tasks": [
    {
      "id": "uuid",
      "batch_id": "uuid",
      "equipment_id": "uuid",
      "operation_name": "fill_LINE_1",
      "start_at": "2026-09-01T08:00:00Z",
      "end_at": "2026-09-01T10:00:00Z",
      "task_role": "LINE_FILL",
      "cooling_mode": "fast",
      "cz_status": "IN_PROGRESS",
      "cz_marked_qty": 2500,
      "is_lab_blocked": false,
      "is_pinned": false,
      "depends_on_task_ids": []
    }
  ]
}
```

**Права:** любой.

---

### `GET /api/v1/gantt/export`

Excel-экспорт.

**Query:**
- `version_id` (optional).

**Ответ:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**Права:** любой.

---

## Соглашения

### Аутентификация

Все эндпоинты, кроме `POST /api/v1/auth/login` и `POST /api/v1/cz/scan`, требуют заголовок:
```
Authorization: Bearer <token>
```

### Формат ошибок

```json
{
  "detail": "Описание ошибки"
}
```

**Коды:**
- `400` — неверный запрос.
- `401` — не авторизован.
- `403` — нет прав.
- `404` — не найдено.
- `409` — конфликт (например, каскад заблокирован pinned-задачей).
- `413` — файл слишком большой (для `help/docs`).
- `422` — ошибка валидации.
- `500` — внутренняя ошибка.

### Пагинация

Пока не реализована. Все списки возвращаются целиком.

### `version_id`

Большинство эндпоинтов принимают опциональный `version_id`:
- Если задан — работают с указанным планом.
- Если не задан — с последней активной версией (`is_active = TRUE`).

### `has_snapshot` (Итерация 13.15)

`GET /api/v1/schedule/versions` возвращает `has_snapshot` для каждой версии:
- `true` — снапшоты справочников заполнены, план можно открывать в readonly-режиме.
- `false` — план пуст (создан до Итерации 13.15 или снапшоты удалены). UI индицирует ⚠.

### `is_archived` (Итерация 13.21)

`GET /api/v1/schedule/versions`:
- По умолчанию (`include_archived=false`) возвращает только НЕархивные версии.
- С `include_archived=true` — возвращает все, включая архивные.
- Каждая версия имеет поле `is_archived: bool`.
- Разархивация — через `PUT /versions/{id}/unarchive`.

### Справка (Итерация 15.1)

- `GET /api/v1/help/articles` — глобальные + per-org статьи.
- `GET /api/v1/help/search` — простой `ILIKE`, неполнотекстовый.
- `GET /api/v1/help/docs/{filename}` — отдача `docs/*.md` без дублирования в БД.
- Все эндпоинты `/help/*` — read-only, доступны любому авторизованному.

### Контекстные подсказки (Итерация 15.2)

- `GET /api/v1/help/hints` — словарь `{hint_key: HelpHint}`.
- Формат `hint_key`: `<module>.<action>`.
- Если `article_slug` задан — фронт показывает кнопку «Читать подробнее».
- Фронт кэширует ответ в `HelpHintsContext` на время сессии.

### FAQ (Итерация 15.4)

- FAQ — **не отдельная сущность**, а **категория** в `help_article`.
- `GET /api/v1/help/categories` возвращает `faq` как обычную категорию.
- `GET /api/v1/help/articles?category=faq` возвращает 15 FAQ-статей.
- `GET /api/v1/help/search` ищет и по FAQ — они в той же таблице.
- Все FAQ-статьи глобальные (`organization_id IS NULL`).
- Дополнительных эндпоинтов **не требуется**.

### Идемпотентность

- `POST /api/v1/cz/scan` — идемпотентен по `cz_code`.
- `POST /api/v1/plan-settings/version/{id}/reset` — идемпотентен.
- `POST /api/v1/schedule/versions` — **не** идемпотентен (создаёт новую версию при каждом вызове).
- `snapshot_all_catalogs` (внутренняя функция) — идемпотентна (`ON CONFLICT DO NOTHING`).
- `PUT /api/v1/schedule/versions/{id}/unarchive` — идемпотентен (повторная разархивация → `400`, но не сломает данные).

### Роли

| Роль | Права |
|------|-------|
| `ADMIN` | Полный доступ |
| `PLANNER` | Планирование, what-if, plan_settings |
| `MASTER` | Мастер смены, блокировка партий, ЧЗ |
| `LAB` | Лаборатория |
| `VIEWER` | Только просмотр |

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.