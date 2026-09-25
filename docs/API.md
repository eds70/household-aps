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

## Справочники

### Оборудование

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/equipment` | Список оборудования | любой |
| `POST` | `/api/v1/equipment` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/equipment/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/equipment/{id}` | Удалить | ADMIN |

**Поля:** `id`, `code`, `name`, `equipment_type`, `capacity_kg`, `is_active`.

---

### Продукты

| Метод | Путь | Описание | Права |
|-------|------|----------|-------|
| `GET` | `/api/v1/products` | Список | любой |
| `POST` | `/api/v1/products` | Создать | ADMIN, PLANNER |
| `PUT` | `/api/v1/products/{id}` | Обновить | ADMIN, PLANNER |
| `DELETE` | `/api/v1/products/{id}` | Удалить | ADMIN |

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

**Итерация 13.15:** в ответе добавлено поле `has_snapshot`.

**Ответ:**
```json
[
  {
    "id": "uuid",
    "name": "План на октябрь",
    "is_active": true,
    "parent_version_id": null,
    "created_at": "2026-09-25T10:00:00Z",
    "created_by": "admin@household.ru",
    "has_snapshot": true
  },
  {
    "id": "uuid-2",
    "name": "z1",
    "is_active": false,
    "created_at": "2026-09-25T13:46:20Z",
    "has_snapshot": false
  }
]
```

**Поля ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `has_snapshot` | `bool` | `true` — снапшоты справочников заполнены, план можно открыть в readonly-режиме. `false` — план пуст (создан до Итерации 13.15), UI покажет предупреждение. |

**Права:** любой.

---

### `POST /api/v1/schedule/versions`

Создать пустую версию (без расчёта).

**Итерация 13.15:** теперь **заполняет снапшоты справочников** сразу при создании.

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
3. `snapshot_all_catalogs()` заполняет `equipment_snapshot`, `product_snapshot`, `operation_snapshot`, `calendar_snapshot`.

---

### `DELETE /api/v1/schedule/versions/{id}`

Удалить версию.

**Права:** ADMIN.

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
  "change_type": "BREAKDOWN",
  "change_data": {
    "equipment_id": "uuid",
    "start_at": "2026-09-25T00:00:00Z",
    "end_at": "2026-09-28T00:00:00Z"
  },
  "frozen_before": "2026-09-25T00:00:00Z"
}
```

**Типы изменений:** `DELAY`, `BREAKDOWN`, `QTY_CHANGE`, `MANUAL`.

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
    "timeout_seconds": 900
  }
}
```

**Права:** ADMIN, PLANNER.

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

### Идемпотентность

- `POST /api/v1/cz/scan` — идемпотентен по `cz_code`.
- `POST /api/v1/plan-settings/version/{id}/reset` — идемпотентен.
- `POST /api/v1/schedule/versions` — **не** идемпотентен (создаёт новую версию при каждом вызове).
- `snapshot_all_catalogs` (внутренняя функция) — идемпотентна (`ON CONFLICT DO NOTHING`).

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