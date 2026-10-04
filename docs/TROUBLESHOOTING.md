# Troubleshooting

Решение проблем в системе **APS Production Scheduler**.

Формат: **Симптом → Причина → Решение**.

---

## 📋 Содержание

- [Backend](#backend)
- [Frontend](#frontend)
- [База данных](#база-данных)
- [Solver](#solver)
- [What-if](#what-if)
- [plan_settings](#plan_settings)
- [Архивация версий (13.21)](#архивация-версий-1321)
- [Снапшоты справочников (13.15)](#снапшоты-справочников-1315)
- [Честный Знак](#честный-знак)
- [Лаборатория](#лаборатория)
- [Смены](#смены)
- [Гант](#гант)
- [Редактирование плана (14.2)](#редактирование-плана-142)
- [Встроенная справка (15.1)](#встроенная-справка-151)
- [Контекстные подсказки (15.2)](#контекстные-подсказки-152)
- [FAQ (15.4)](#faq-154)
- [Диагностика](#диагностика)

---

## Backend

### 1. FastAPI 0.139+: `_IncludedRouter` в `app.routes`

**Симптом:** проверка `getattr(r, 'path', None)` возвращает `None` для всех `include_router(...)`.

**Причина:** в FastAPI 0.139+ роутеры, подключённые через `include_router`, оборачиваются в `_IncludedRouter` и не имеют атрибута `path` на верхнем уровне.

**Решение:** использовать `app.openapi()['paths']`:

```python
paths = app.openapi()['paths']
assert '/api/v1/plan-settings/version/{version_id}' in paths
```

---

### 2. Кэш Python (`__pycache__`) на Windows

**Симптом:** изменения в коде не применяются после перезапуска сервера.

**Причина:** Windows кэширует `.pyc`-файлы в `__pycache__`, и иногда они не инвалидируются.

**Решение:**

```bash
cd backend
Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

Затем перезапустить `python run_server.py`.

---

### 3. Кэш браузера

**Симптом:** изменения во frontend не видны.

**Причина:** браузер кэширует JS/CSS.

**Решение:** режим инкогнито или `Ctrl+Shift+Delete` → очистить кэш.

---

### 4. Таймзона naive datetime в asyncpg

**Симптом:** `by-date` не находит смену на дату, хотя она есть.

**Причина:** naive datetime из Python не находит смену, если сессия asyncpg не в UTC.

**Решение:** сравнение по МСК-дате:

```sql
(starts_at AT TIME ZONE 'Europe/Moscow')::date = :shift_date
```

См. `backend/app/api/v1/shift.py`.

---

### 5. `UndefinedColumnError` при запуске

**Симптом:** при запуске возникает `UndefinedColumnError: column ... does not exist`.

**Причина:** не применена соответствующая миграция.

**Решение:** применить миграцию:

```bash
docker cp backend/migrations/add_XX.sql aps_postgres:/tmp/add_XX.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_XX.sql
```

Определить, какая миграция нужна, по имени колонки:

| Колонка | Миграция |
|---------|----------|
| `operation_name` | `add_12.sql` |
| `cooling_mode` | `add_10b.sql` |
| `operator_pool` | `add_09.sql` |
| `cz_marked_qty`, `cz_status` | `add_11.sql` |
| `is_lab_blocked`, `lab_status` | `add_08.sql` |
| `shift_id`, `actual_qty` | `add_07.sql` |
| `app_settings` (таблица) | `add_13.sql` |
| `whatif_scenario` (таблица) | `add_16.sql` |
| `plan_settings` (таблица) | `add_21.sql` |
| **`is_archived`** | **`add_23.sql`** |
| **`help_article` (таблица)** | **`add_24.sql`** |
| **`help_hint` (таблица)** | **`add_25.sql`** |

---

### 6. `404 Not Found` на `/api/v1/plan-settings/version/{id}`

**Симптом:** GET-запрос возвращает `404`.

**Причина:** эндпоинт не подключён в `main.py`.

**Решение:** проверить `backend/app/main.py`:

```python
from app.api.v1.plan_settings import router as plan_settings_router
app.include_router(plan_settings_router)
```

---

### 7. `404 Not Found` на `/api/v1/schedule/versions/{id}/unarchive`

**Симптом:** PUT-запрос разархивации возвращает `404` или `405`.

**Причина:** эндпоинт не подключён или не зарегистрирован.

**Решение:** проверить, что `schedule.py` содержит:

```python
@router.put("/versions/{version_id}/unarchive", ...)
async def unarchive_schedule_version(...):
   ...
```

Проверка через OpenAPI:

```bash
curl http://localhost:8000/openapi.json | grep "unarchive"
```

---

### 8. `404 Not Found` на `/api/v1/help/*`

**Симптом:** запросы к справке возвращают `404`.

**Причина:** эндпоинты не подключены или не применена миграция `add_24.sql` / `add_25.sql`.

**Решение:**

1. Проверить `main.py`:
   ```python
   from app.api.v1.help import router as help_router
   from app.api.v1.help_docs import router as help_docs_router
   app.include_router(help_router)
   app.include_router(help_docs_router)
   ```
2. Проверить, что применена миграция `add_24.sql`:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'help_article');
   "
   ```
3. Проверить, что применена миграция `add_25.sql` (для подсказок):
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'help_hint');
   "
   ```
4. Проверить, что применены seed-миграции `add_24_seed_1/2/3.sql`:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT COUNT(*) FROM help_article;
   "
   ```
   Должно быть **30** (после Итерации 15.4).
5. Проверить, что применены FAQ-миграции `add_26_seed_1/2/3.sql`:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT COUNT(*) FROM help_article WHERE category = 'faq';
   "
   ```
   Должно быть **15**.
6. Проверить, что применена seed-миграция `add_25_seed.sql`:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT COUNT(*) FROM help_hint;
   "
   ```
   Должно быть **8**.

---

### 9. `ModuleNotFoundError` при запуске

**Симптом:** `ModuleNotFoundError: No module named 'app'`.

**Причина:** запуск не из корня `backend/`.

**Решение:** перейти в `backend/`:

```bash
cd backend
python run_server.py
```

---

### 10. `ImportError` после добавления нового модуля

**Симптом:** `ImportError: cannot import name ...`.

**Причина:** кэш Python или неверный путь импорта.

**Решение:**

1. Очистить `__pycache__` (см. пункт 2).
2. Проверить `__init__.py` в директории.
3. Перезапустить сервер.

---

### 11. Backend не стартует: `Address already in use`

**Симптом:** `OSError: [Errno 98] Address already in use`.

**Причина:** порт 8000 занят.

**Решение:**

```bash
# Найти процесс
netstat -ano | findstr :8000

# Убить процесс
taskkill /PID <pid> /F
```

Или изменить порт в `run_server.py`.

---

### 12. JWT-токен истёк

**Симптом:** `401 Unauthorized` после некоторого времени работы.

**Причина:** `JWT_EXPIRES_MINUTES` (по умолчанию 60).

**Решение:** войти заново или увеличить `JWT_EXPIRES_MINUTES` в `.env`.

---

### 13. `snapshot.py` не импортируется (Итерация 13.15)

**Симптом:** при запуске backend — `ModuleNotFoundError: No module named 'app.scheduler.snapshot'`.

**Причина:** файл `backend/app/scheduler/snapshot.py` отсутствует или не перезапущен сервер.

**Решение:**

1. Проверить наличие файла:
   ```bash
   ls backend/app/scheduler/snapshot.py
   ```
2. Очистить кэш Python:
   ```bash
   cd backend
   Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
   ```
3. Перезапустить сервер.
4. Проверить:
   ```bash
   python -c "from app.scheduler.snapshot import snapshot_all_catalogs; print('OK')"
   ```

---

### 14. `snapshot_all_catalogs` падает с `UndefinedColumnError`

**Симптом:** при создании плана или расчёте — ошибка типа `column operation_template.operator_pool does not exist`.

**Причина:** не применена миграция `add_09.sql`, но `snapshot.py` пытается вставить `operator_pool` в `operation_snapshot`.

**Решение:** модуль `snapshot.py` содержит graceful-обработку — проверяет наличие колонки `operator_pool` через `_has_column`. Если ошибка всё же возникает — примените миграцию:

```bash
docker cp backend/migrations/add_09.sql aps_postgres:/tmp/add_09.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09.sql
```

---

### 15. `500 Internal Server Error` при пересчёте с `replace_version_id`

**Симптом:** `POST /api/v1/schedule/reschedule` возвращает `500`, хотя задача вроде валидна.

**Причина:** возможные причины:
1. Не применена миграция `add_23.sql` — колонки `is_archived` нет.
2. Ошибка в `_archive_version` (например, неожиданная структура `whatif_scenario`).

**Решение:**

1. Проверить, что колонка `is_archived` существует:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT column_name FROM information_schema.columns
   WHERE table_name = 'schedule_version' AND column_name = 'is_archived';
   "
   ```
2. Если пусто — применить миграцию `add_23.sql`.
3. Проверить логи backend на конкретную ошибку.

**Graceful-поведение:** `saver.py` содержит `_has_column(session, "schedule_version", "is_archived")` — если колонки нет, архивация просто пропускается, а `save_schedule` возвращает `replace_archived=False, replace_blocked=False`. Ошибка 500 не должна возникать — сообщить о баге.

---

## Frontend

### 16. `usePlan must be used within PlanProvider`

**Симптом:** ошибка `usePlan must be used within PlanProvider`.

**Причина:** кэш Vite.

**Решение:** перезапустить Vite с очисткой кэша:

```bash
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

---

### 17. Advisor «дёргается» (бесконечный ре-рендер)

**Симптом:** панель Advisor постоянно перезагружается, в консоли — бесконечные запросы.

**Причина:** функции в `PlanContext.tsx` не обёрнуты в `useCallback`.

**Решение:** в `PlanContext.tsx` обернуть функции в `useCallback`:

```tsx
const loadVersions = useCallback(async () => {
   // ...
}, [isAuthenticated, isLoading]);

const setPlan = useCallback((plan: Plan | null) => {
   // ...
}, []);
```

Также `loadVersions` вызывается **только после аутентификации**.

---

### 18. `401 Unauthorized` при первом заходе на `/login`

**Симптом:** при открытии `/login` в консоли — `401 Unauthorized`.

**Причина:** `loadVersions` вызывается до аутентификации.

**Решение:** см. пункт 17 — вызывать `loadVersions` только после аутентификации.

---

### 19. `axios` не отправляет токен

**Симптом:** все запросы идут без `Authorization` header.

**Причина:** интерсептор не настроен или токен отсутствует в `localStorage`.

**Решение:** проверить `frontend/src/services/api.ts`:

```typescript
api.interceptors.request.use((config) => {
   const token = localStorage.getItem('access_token');
   if (token) {
      config.headers.Authorization = `Bearer ${token}`;
   }
   return config;
});
```

Проверить в DevTools → Application → Local Storage → `access_token`.

---

### 20. Диаграмма Ганта: pan не работает

**Симптом:** нельзя панорамировать диаграмму.

**Причина:** `moveable: false` или конфликт с drag.

**Решение:** в `GanttPage.tsx`:

```tsx
<Timeline
        options={{
           moveable: true,        // pan по пустому месту
           zoomable: true,        // zoom колёсиком
           editable: {
              updateTime: (item) => {
                 // true только для реальных задач
                 return item.type !== 'downtime' && item.type !== 'setup';
              },
           },
        }}
/>
```

---

### 21. Диаграмма Ганта: задачи не таскаются

**Симптом:** drag-and-drop не работает.

**Причина:** `editable.updateTime` возвращает `false` для всех задач, или включён readonly-режим.

**Решение:** см. пункт 20. `updateTime` должен быть **функцией**, возвращающей `true` для реальных задач и `false` для setup/downtime. Также проверить, что план открыт в режиме `✏️ Редактирование` (см. [Редактирование плана (14.2)](#редактирование-плана-142)).

---

### 22. Мастер смены: шапка «уезжает» вверх

**Симптом:** при большом количестве задач шапка уходит вверх при скролле.

**Решение:** в `ShiftPage.tsx`:

```tsx
<Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
   <Box sx={{ flexShrink: 0 }}>{/* Заголовок */}</Box>
   <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>{/* Список */}</Box>
</Box>
```

---

### 23. `npm install` падает с ошибкой

**Симптом:** `npm install` завершается с ошибкой.

**Решение:**

```bash
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm cache clean --force
npm install
```

---

### 24. Frontend не видит backend

**Симптом:** запросы к API падают с `Network Error`.

**Решение:**

1. Проверить, что backend запущен: `curl http://localhost:8000/docs`.
2. Проверить `CORS_ORIGINS` в `.env`.
3. Проверить `vite.config.ts` (proxy).

---

### 25. План в списке помечен ⚠ (Итерация 13.15)

**Симптом:** рядом с планом жёлтая иконка ⚠.

**Причина:** `has_snapshot = false` — снапшоты справочников не заполнены.

**Решение:** см. пункт 33 (в разделе «Снапшоты справочников»).

---

### 26. GanttPage показывает «План пуст» (Итерация 13.15)

**Симптом:** при открытии плана вместо диаграммы — предупреждение «План пуст».

**Причина:** `currentPlanHasSnapshot === false` в `PlanContext`.

**Решение:** см. пункт 33.

---

### 27. Пункт «Аудит» отсутствует в меню

**Симптом:** в левом сайдбаре нет пункта «Аудит».

**Причина:** это **by design** — в Итерации 13.16 раздел «Аудит» временно скрыт из меню.

**Решение (если нужна отладка):** открыть страницу по прямой ссылке: http://localhost:5173/audit

---

### 28. «История планов» показывает много версий

**Симптом:** в списке «История планов» десятки версий.

**Причина:** архивные версии включены (чекбокс «Показать архивные»),
или настройка `auto_archive_on_recalc = false`.

**Решение:**
1. Снять чекбокс «Показать архивные».
2. Проверить `auto_archive_on_recalc` через `SettingsPage` или:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT setting_value FROM app_settings
   WHERE setting_key = 'auto_archive_on_recalc';
   "
   ```
3. При необходимости — массово архивировать старые (см. раздел
   «Архивация версий» в OPERATIONS.md).

---

### 29. Иерархия планов не строится (Tree Data)

**Симптом:** все версии показываются плоско, без иерархии.

**Причина:** у версий отсутствует `parent_version_id` или он ссылается
на несуществующую версию.

**Решение:**

1. Проверить, что `parent_version_id` заполняется при пересчёте.
2. Проверить в БД:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT id, name, parent_version_id
   FROM schedule_version
   WHERE organization_id = '00000000-0000-0000-0000-000000000001'
     AND parent_version_id IS NOT NULL
   LIMIT 10;
   "
   ```
3. Если пусто — все корни, иерархии не будет. Это не баг, если планы
   создавались независимо (не через пересчёт).

---

### 30. Кнопка «↩ Разархивировать» не появляется

**Симптом:** у архивной версии нет кнопки разархивации.

**Причина:** возможно, версия не помечена как архивная (`is_archived` не приходит с бэкенда).

**Решение:**

1. Проверить ответ `GET /api/v1/schedule/versions?include_archived=true`:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/api/v1/schedule/versions?include_archived=true"
   ```
2. Убедиться, что в ответе есть `is_archived: true`.
3. Если нет — проверить, что миграция `add_23.sql` применена.

---

## База данных

### 31. `psql: FATAL: database "household" does not exist`

**Симптом:** не удаётся подключиться к БД.

**Решение:**

```bash
docker exec aps_postgres psql -U aps -c "CREATE DATABASE household;"
```

Или пересоздать контейнер:

```bash
docker rm -f aps_postgres
docker run --name aps_postgres \
  -e POSTGRES_USER=aps \
  -e POSTGRES_PASSWORD=aps_secret \
  -e POSTGRES_DB=household \
  -p 5432:5432 \
  -d postgres:16
```

---

### 32. Кириллица отображается как «кракозябры»

**Симптом:** русские буквы в БД выглядят как `????` или `ÐŸÑ€Ð¸Ð²ÐµÑ‚`.

**Причина:** применение SQL-файла через `Get-Content | docker exec`.

**Решение:** применять через `docker cp` + `psql -f`:

```bash
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
```

---

### 33. `relation "..." does not exist`

**Симптом:** `relation "plan_settings" does not exist`.

**Причина:** не применена миграция.

**Решение:** см. пункт 5. Применить нужную миграцию.

---

### 34. `duplicate key value violates unique constraint`

**Симптом:** при вставке — `duplicate key value violates unique constraint`.

**Решение:** зависит от констрейнта:

| Констрейнт | Причина | Решение |
|------------|---------|---------|
| `plan_settings (schedule_version_id, setting_key)` | Дубль настройки | `ON CONFLICT DO NOTHING` |
| `resource_pool (organization_id, type)` | Дубль пула | Удалить старый или обновить |
| `cz_scan_log (organization_id, cz_code)` | Повторный скан | Идемпотентно, `duplicate: true` |
| `equipment_snapshot (id, version_id)` | Дубль снапшота | `ON CONFLICT DO NOTHING` (by design) |
| `help_article (slug)` | Дубль статьи | `ON CONFLICT (slug) DO NOTHING` |
| `help_hint (hint_key)` | Дубль подсказки | `ON CONFLICT (hint_key) DO NOTHING` |

---

### 35. PostgreSQL не стартует

**Симптом:** `docker ps` не показывает `aps_postgres`.

**Решение:**

```bash
# Проверить логи
docker logs aps_postgres --tail 50

# Пересоздать контейнер
docker rm -f aps_postgres
docker run --name aps_postgres \
  -e POSTGRES_USER=aps \
  -e POSTGRES_PASSWORD=aps_secret \
  -e POSTGRES_DB=household \
  -p 5432:5432 \
  -d postgres:16
```

---

### 36. Долгий запрос блокирует БД

**Симптом:** запросы висят, БД не отвечает.

**Решение:**

```bash
# Найти долгие запросы
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 seconds'
ORDER BY duration DESC;
"

# Убить процесс
docker exec -i aps_postgres psql -U aps -d household -c "SELECT pg_terminate_backend(<pid>);"
```

---

## Solver

### 37. Solver выдаёт `FEASIBLE` вместо `OPTIMAL`

**Симптом:** в ответе `status: "FEASIBLE"`.

**Причина:** истёк таймаут (`timeout_seconds`), но решение найдено.

**Решение:**

1. Увеличить `timeout_seconds` в `app_settings` (или `plan_settings`):

```bash
curl -X PUT http://localhost:8000/api/v1/settings/timeout_seconds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": 1800}'
```

2. Уменьшить `horizon_hours`.

---

### 38. Solver не находит решение (`INFEASIBLE`)

**Симптом:** `status: "INFEASIBLE"`.

**Решение:**

1. Проверить Advisor: `GET /api/v1/schedule/advice`.
2. Проверить заказы и доступность оборудования.
3. Проверить календарь простоев.
4. Уменьшить `horizon_hours`.
5. Проверить, нет ли заблокированных партий, которые нельзя запланировать.

---

### 39. Solver работает слишком долго

**Симптом:** расчёт занимает >10 минут.

**Решение:**

1. Уменьшить `horizon_hours` (например, до 720).
2. Уменьшить `timeout_seconds` (например, до 600).
3. Упростить задачу (убрать лишние заказы).

---

### 40. `overlaps_after > 0` после постобработки

**Симптом:** после `calendar_postprocess` остаются пересечения.

**Решение:**

1. Проверить пересечения:
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
2. Пересчитать план.
3. Если повторяется — сообщить о баге.

---

### 41. `dependency_violations > 0`

**Симптом:** после постобработки есть нарушения зависимостей.

**Решение:** пересчитать план. Если повторяется — сообщить о баге.

---

## What-if

### 42. Сценарий завис в статусе `RUNNING`

**Симптом:** сценарий не завершается.

**Решение:**

1. Подождать (solver может работать до 10 минут).
2. Проверить логи backend.
3. Удалить сценарий (если не удаляется — см. пункт 43).

---

### 43. Не удаётся удалить сценарий

**Симптом:** `DELETE /api/v1/whatif/scenarios/{id}` возвращает ошибку.

**Причина:** сценарий в статусе `RUNNING` — удаление запрещено.

**Решение:** дождаться завершения (`DONE`/`FAILED`) или убить процесс solver.

---

### 44. What-if не откатывает изменения

**Симптом:** после what-if изменения в БД остались.

**Решение:**

1. Проверить, что `ProductionScheduler` получает `session` извне.
2. Проверить, что `ScheduleSaver` не делает commit при `_owns_session=False`.
3. Перезапустить backend.

---

### 45. What-if: `500 Internal Server Error`

**Симптом:** `POST /run` возвращает 500.

**Решение:**

1. Проверить логи backend.
2. Проверить формат `changes` (JSON).
3. Убедиться, что `base_version_id` существует.

---

## plan_settings

### 46. Таблица `plan_settings` пуста

**Симптом:** `SELECT COUNT(*) FROM plan_settings` возвращает 0.

**Причина:** не применена миграция `add_21.sql`.

**Решение:**

```bash
docker cp backend/migrations/add_21.sql aps_postgres:/tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
```

---

### 47. Триггер `copy_app_settings_to_plan` не срабатывает

**Симптом:** создали план, но `plan_settings` пуст.

**Решение:** проверить наличие триггера:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname FROM pg_trigger WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

Если пусто — пересоздать миграцию `add_21.sql`.

---

### 48. `404 Not Found` при `GET /api/v1/plan-settings/version/{id}`

**Причина:** не подключён в `main.py`.

**Решение:** см. пункт 6.

---

### 49. Мастер настроек показывает пустой список полей

**Причина:** `settingsApi.getSchema()` вернул пустой `settings`.

**Решение:** проверить `SETTINGS_REGISTRY` в `backend/app/scheduler/settings.py` — там должно быть 30+ записей.

---

### 50. В мастере настроек отсутствует кнопка «Сохранить»

**Причина:** `changedKeys.length === 0` — нет изменений.

**Решение:** это by design. Измените любое поле — кнопка активируется.

---

### 51. `plan_settings` не обновляются при изменении `app_settings`

**Причина:** это by design (снапшот).

**Решение:** сбросить `plan_settings` к глобальным:

```bash
curl -X POST http://localhost:8000/api/v1/plan-settings/version/$VERSION_ID/reset \
  -H "Authorization: Bearer $TOKEN"
```

---

### 52. Существующие планы не имеют `plan_settings`

**Причина:** планы созданы до миграции `add_21.sql`.

**Решение:** сбросить к глобальным (см. пункт 51) или создать новый план.

---

## Архивация версий (13.21)

### 53. Старая версия не архивируется при пересчёте

**Симптом:** пользователь нажал «Пересчитать», но старая версия осталась
в списке (не архивировалась).

**Причина:** возможные варианты:
1. Версия используется в `whatif_scenario` со статусом `DRAFT` или `RUNNING`.
2. Настройка `auto_archive_on_recalc = false`.
3. Не применена миграция `add_23.sql`.

**Решение:**

**Шаг 1. Проверить настройку:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT setting_value FROM app_settings
WHERE setting_key = 'auto_archive_on_recalc'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

Если `false` — включить:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE app_settings
SET setting_value = 'true'::jsonb, updated_at = NOW()
WHERE setting_key = 'auto_archive_on_recalc'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

**Шаг 2. Проверить what-if сценарии:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, status, base_version_id, result_version_id
FROM whatif_scenario
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND status IN ('DRAFT', 'RUNNING');
"
```

Если версия используется — либо завершить сценарий (запустить его),
либо удалить, либо разархивировать вручную (см. пункт 55).

**Шаг 3. Проверить миграцию:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT column_name FROM information_schema.columns
WHERE table_name = 'schedule_version' AND column_name = 'is_archived';
"
```

Если пусто — применить миграцию `add_23.sql` (см. пункт 5).

**Также:** GanttPage показывает снекбар после пересчёта:
- info — старая версия архивирована.
- warning — не архивирована (с указанием сценариев).

---

### 54. Колонка `is_archived` не найдена

**Симптом:** `saver.py` логирует «Колонка is_archived не найдена — архивация пропущена».

**Причина:** не применена миграция `add_23.sql`.

**Решение:**

```bash
docker cp backend/migrations/add_23.sql aps_postgres:/tmp/add_23.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_23.sql
```

Проверка:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'schedule_version' AND column_name = 'is_archived'
);
"
```

Должно быть `t`.

---

### 55. Разархивировать версию вручную через SQL

**Симптом:** нужно разархивировать версию, но UI не работает.

**Решение:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = FALSE
WHERE id = '<version-uuid>'
  AND organization_id = '00000000-0000-0000-0000-000000000001';
"
```

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_archived, is_active
FROM schedule_version
WHERE id = '<version-uuid>';
"
```

---

### 56. В списке планов 50+ версий после отключения архивации

**Симптом:** пользователь отключил `auto_archive_on_recalc`, и список
стал длинным.

**Решение:** массово архивировать неактивные версии:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = TRUE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND is_active = FALSE
  AND is_archived = FALSE;
"
```

Вывод покажет количество затронутых строк (например, `UPDATE 12`).

---

### 57. Иерархия планов плоская (все корни)

**Симптом:** в «Истории планов» все версии на одном уровне, иерархии нет.

**Причина:** у версий отсутствует `parent_version_id` — либо версии
создавались независимо, либо поле не заполняется.

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS with_parent
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND parent_version_id IS NOT NULL;
"
```

Если `0` — иерархии не будет (это нормально для независимо созданных
планов). Если `> 0` — проверить, что `rescheduler.py` устанавливает
`parent_version_id`:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, parent_version_id
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC LIMIT 5;
"
```

---

### 58. Снекбар об архивации не показывается

**Симптом:** после пересчёта не появляется уведомление в правом нижнем углу.

**Причина:** возможные варианты:
1. `RescheduleResponse` не содержит полей архивации.
2. `GanttPage` не подключен к `Snackbar`.
3. Пересчёт шёл без `replace_version_id`.

**Решение:**

1. Проверить ответ `POST /schedule/reschedule`:
   ```bash
   curl -X POST http://localhost:8000/api/v1/schedule/reschedule \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"from_version_id": "...", "reason": "MANUAL", "changes": {}, "replace_version_id": "..."}'
   ```
   В ответе должны быть `replace_archived`, `replace_blocked`.

2. Убедиться, что `useRecalculate` передаёт `replace_version_id`:
   - Проверить, что `auto_archive_on_recalc = true` (или явно передаётся).
   - Проверить в DevTools → Network → Payload запроса.

---

## Снапшоты справочников (13.15)

### 59. План открыт, но все справочники пусты

**Симптом:** открыли план, но на страницах «Продукты», «Оборудование»,
«Техкарты» гриды пусты.

**Причина:** план создан до Итерации 13.15 — снапшоты не заполнялись.

**Решение:**

1. Закройте план (кнопка ✕).
2. Удалите его через UI (кнопка 🗑).
3. Создайте новый план через мастер — снапшоты заполнятся автоматически.

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment
FROM schedule_version sv
ORDER BY sv.created_at DESC LIMIT 5;
"
```

Если у плана `products = 0` — снапшоты не заполнены.

---

### 60. `POST /schedule/versions` создаёт план, но снапшоты пусты

**Симптом:** создали план через API, но `snapshot_stats` показывает нули.

**Решение:**

1. Проверить, что `schedule.py` содержит:
   ```python
   from app.scheduler.snapshot import snapshot_all_catalogs
   ```
2. Очистить кэш Python:
   ```bash
   cd backend
   Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
   ```
3. Перезапустить сервер.
4. Проверить в логах backend строку `[snapshot] Готово для version=...`.

---

### 61. Удалить все пустые планы одной командой

**Симптом:** накопилось много планов без снапшотов.

**Решение:**

```bash
# Бэкап
docker exec aps_postgres pg_dump -U aps household > backup_before_cleanup.sql

# Удалить пустые
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = schedule_version.id LIMIT 1
  );
"
```

**Альтернатива (безопаснее):** архивировать их:
```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE schedule_version
SET is_archived = TRUE
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (
      SELECT 1 FROM equipment_snapshot WHERE version_id = schedule_version.id LIMIT 1
  )
  AND is_active = FALSE;
"
```

---

## Честный Знак

### 62. Скан не привязывается к партии

**Симптом:** скан попадает в «сироты» (`batch_id = NULL`).

**Решение:**

1. Проверить, что `line_code` и время скана соответствуют задаче `LINE_FILL` (±2 часа).
2. Вручную сопоставить:
   ```bash
   curl -X POST http://localhost:8000/api/v1/cz/scan/$SCAN_ID/attach \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"batch_id": "uuid"}'
   ```

---

### 63. Дубликаты сканов

**Симптом:** `duplicate: true` в ответе.

**Причина:** идемпотентность по `cz_code`.

**Решение:** это by design. Повторный скан не увеличивает `cz_marked_qty`.

---

### 64. `cz_status` не обновляется

**Симптом:** после сканов `cz_status` остаётся `PENDING`.

**Причина:** не достигнут порог `cz_completion_threshold`.

**Решение:** проверить `cz_marked_qty` и `planned_qty`. Порог по умолчанию — 0.95.

---

### 65. `CZ_INCOMPLETE` в Advisor, но маркировка завершена

**Симптом:** Advisor выдаёт `CZ_INCOMPLETE`, хотя `cz_status = COMPLETED`.

**Причина:** кэш Advisor.

**Решение:** перезагрузить страницу или пересчитать план.

---

## Лаборатория

### 66. Заблокированная партия всё равно в плане

**Симптом:** партия с `is_lab_blocked = true` есть в расписании.

**Причина:** план не пересчитан после блокировки.

**Решение:** запустить перепланирование:

```bash
curl -X POST http://localhost:8000/api/v1/schedule/reschedule \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_version_id": "uuid", "reason": "MANUAL", "changes": {}}'
```

---

### 67. `LAB` не может заблокировать партию

**Симптом:** `403 Forbidden`.

**Решение:** блокировать могут `LAB`, `MASTER`, `ADMIN`. Проверить роль.

---

### 68. После разблокировки партия не появляется в плане

**Решение:** см. пункт 66.

---

## Смены

### 69. При смене `shift_mode` задачи теряют привязку

**Симптом:** после `POST /api/v1/settings/shift-mode` у задач `shift_id = NULL`.

**Причина:** это by design — старые UUID смен невалидны.

**Решение:** пересчитать план.

---

### 70. `by-date` не находит смену

**Решение:** сравнение по МСК-дате (см. пункт 4).

---

### 71. Смены не созданы

**Симптом:** таблица `shift` пуста.

**Решение:** сменить режим смен:

```bash
curl -X POST http://localhost:8000/api/v1/settings/shift-mode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "1x8"}'
```

---

## Гант

### 72. Pan диаграммы не работает

**Симптом:** нельзя таскать диаграмму.

**Решение:** см. пункт 20.

---

### 73. Задачи не таскаются

**Решение:** см. пункт 21.

---

### 74. Tooltip не показывается при перетаскивании

**Симптом:** при drag-and-drop задачи tooltip не появляется.

**Причина:** в vis-timeline 8.x события `itemmoving` / `itemresizing` не генерируются. Мы используем нативные pointer-события.

**Решение:**

1. Проверить, что `useGanttTimeline` содержит `attachNativeDragListeners`.
2. Проверить, что `onItemChange` передан в `useGanttTimeline`.
3. Открыть DevTools → Console — при drag не должно быть ошибок.

---

### 75. Resize задачи не работает

**Симптом:** нельзя изменить длительность задачи.

**Решение:**

1. Проверить `frontend/src/index.css`:
   ```css
   .gantt-container .vis-item.vis-range .vis-drag-left,
   .gantt-container .vis-item.vis-range .vis-drag-right {
       cursor: ew-resize !important;
       width: 10px !important;
   }
   ```
2. Проверить `vis-timeline` events — используется `editable.updateTime: !isReadOnly`.

---

### 76. Группа LINE_FILL не раскрывается

**Симптом:** при клике на свёрнутую группу ничего не происходит.

**Причина:** обработчик `onToggleGroup` не подключён.

**Решение:** проверить `useGanttTimeline`:

```tsx
newTimeline.on('click', (props) => {
   if (itemId.startsWith('__group__') && onToggleGroup) {
      onToggleGroup(getGroupKeyFromId(itemId));
   }
});
```

---

### 77. Скобки партий не отображаются

**Симптом:** в режиме «По оборудованию» не видно цветных скобок партий.

**Причина:** возможные варианты:
1. `showBatchBrackets = false` (снят чекбокс «Скобки партий»).
2. Режим группировки — `'batch'` (в этом режиме скобки не нужны).
3. Ошибка в `drawBatchBrackets`.

**Решение:**

1. Проверить чекбокс «Скобки партий» в тулбаре Ганта.
2. Проверить режим группировки — должен быть «По оборудованию».
3. Открыть DevTools → Console — при ошибке в `drawBatchBrackets` будет `[GanttPage] drawBatchBrackets failed:`.
4. Очистить кэш браузера.

---

### 78. Режим «По партиям» показывает «спагетти» из связей

**Симптом:** в режиме «По партиям» слишком много красных линий-связей.

**Причина:** это by design — в режиме `'batch'` показываются только межпартийные связи, но их может быть много.

**Решение:**

1. Отключить связи кнопкой 🔗 в тулбаре.
2. Или оставить связи только при hover (по умолчанию).
3. Проверить `showAllDependencies` — должен быть `false`.

---

### 79. Ошибка `<rect> attribute width: A negative value is not valid`

**Симптом:** при zoom/pan в консоли браузера появляется эта ошибка.

**Причина:** в Итерации 14.2 добавлена защита от отрицательной ширины в `drawBatchBrackets`.

**Решение:** обновиться до версии 4.3.0+. Если ошибка осталась — очистить кэш Vite:

```bash
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

---

## Редактирование плана (14.2)

### 80. Задачи не перетаскиваются, хотя план открыт

**Симптом:** открыт план, но задачи нельзя таскать.

**Причина:** план открыт в режиме `🔒 Просмотр` (readonly).

**Решение:**

1. Проверить иконку в тулбаре Ганта: должна быть активна `✏️ Редактирование` (синяя).
2. Если активна `🔒` — кликнуть на `✏️`.
3. Проверить иконку в шапке `MainLayout` — должна быть `✏️ План от ...` (зелёная).

**Что это значит:**
- `🔒 Просмотр` — readonly (безопасный режим, задачи не двигаются).
- `✏️ Редактирование` — задачи можно таскать/ресайзить.

---

### 81. Иконка в шапке не меняется при переключении режима

**Симптом:** переключили `✏️` в тулбаре, но чип в шапке остался `🔒`.

**Причина:** `MainLayout` не подписан на `localEditMode` из `PlanContext`.

**Решение:**

1. Проверить `MainLayout.tsx` — должен брать `localEditMode` из `usePlan()`.
2. Проверить `PlanContext.tsx` — `localEditMode` и `setLocalEditMode` должны быть в `value` провайдера.
3. Очистить кэш Vite:
   ```bash
   cd frontend
   Remove-Item -Recurse -Force node_modules\.vite
   npm run dev
   ```

---

### 82. При открытии плана всегда readonly

**Симптом:** при открытии плана через 👁️ всегда включается `🔒 Просмотр`.

**Причина:** это **by design** — безопасный режим по умолчанию.

**Решение:** для редактирования кликнуть `✏️` в тулбаре Ганта.

**Логика:**
- план открыт → `localEditMode = false` (readonly);
- план закрыт → `localEditMode = true` (редактирование).

---

### 83. Кнопка «Пересчитать» недоступна, хотя есть изменения

**Симптом:** кнопка 🔄 в тулбаре серая, хотя меняли задачи.

**Причина:** `planDirty === false` — нет несохранённых изменений, влияющих на расчёт.

**Решение:**

1. Проверить, какие именно изменения делались — они должны влиять на расчёт (справочники, заказы, capacity, настройки, move/resize задач).
2. Проверить в React DevTools → `PlanProvider` → `planDirty`.
3. Если `false`, но изменения были — возможно, вы меняли только метаданные (name/comment), которые на расчёт не влияют.

---

## Встроенная справка (15.1)

### 84. Страница «Помощь» пуста

**Симптом:** открыли `/help`, но список категорий пуст, статья не отображается.

**Причина:** не применены seed-миграции `add_24_seed_1/2/3.sql`.

**Решение:**

```bash
docker cp backend/migrations/add_24.sql aps_postgres:/tmp/add_24.sql
docker cp backend/migrations/add_24_seed_1.sql aps_postgres:/tmp/add_24_seed_1.sql
docker cp backend/migrations/add_24_seed_2.sql aps_postgres:/tmp/add_24_seed_2.sql
docker cp backend/migrations/add_24_seed_3.sql aps_postgres:/tmp/add_24_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_24_seed_3.sql
```

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) FROM help_article;
"
```

Должно быть **30** (после Итерации 15.4).

---

### 85. Статья не открывается (404)

**Симптом:** клик по статье в сайдбаре — статья не открывается, в консоли 404.

**Причина:** slug в URL не совпадает с `slug` в БД.

**Решение:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug FROM help_article ORDER BY slug;
"
```

Проверить, что URL вида `/help/intro-overview` совпадает с slug из БД.

---

### 86. Поиск не находит статьи

**Симптом:** вводишь запрос, а результатов нет.

**Причина:** поиск использует `ILIKE` — если запрос меньше 2 символов, поиск не срабатывает.

**Решение:**

1. Ввести минимум 2 символа.
2. Проверить, что `title` / `content_md` / `tags` содержат искомое слово:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT slug, title FROM help_article
   WHERE title ILIKE '%ваш_запрос%' OR content_md ILIKE '%ваш_запрос%';
   "
   ```

---

### 87. `Markdown` отображается как plain text

**Симптом:** в статье видны символы `#`, `**`, `[]()` вместо форматирования.

**Причина:** `react-markdown` не установлен или не подключён.

**Решение:**

```bash
cd frontend
npm install react-markdown@^9.0.1 remark-gfm@^4.0.0
npm run dev
```

Проверить, что в `HelpArticleView.tsx` есть:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
```

---

### 88. Внутренние ссылки в статьях не работают

**Симптом:** клик по ссылке вида `[текст](/help/some-article)` — ничего не происходит.

**Причина:** не передан `onInternalLink` в `HelpArticleView`.

**Решение:** в `HelpPage.tsx` проверить:

```tsx
<HelpArticleView
    content={article.content_md}
    onInternalLink={handleSelectArticle}
/>
```

---

### 89. Файлы `docs/*.md` не отдаются

**Симптом:** `GET /api/v1/help/docs/ARCHITECTURE.md` возвращает 404.

**Причина:** файл отсутствует в папке `docs/` или некорректный path.

**Решение:**

1. Проверить наличие файла:
   ```bash
   ls docs/ARCHITECTURE.md
   ```
2. Проверить, что в `help_docs.py` корректно определён `_DOCS_DIR`:
   ```python
   _BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
   _DOCS_DIR = _BACKEND_DIR.parent / "docs"
   ```
3. Проверить, что файл `.md`, не превышает 1 МБ.

---

### 90. Ошибка path traversal при запросе `/help/docs/`

**Симптом:** `GET /api/v1/help/docs/../etc/passwd` возвращает 400.

**Причина:** это защита от path traversal — by design.

**Решение:** используйте только корректные имена файлов (например, `ARCHITECTURE.md`).

---

## Контекстные подсказки (15.2)

### 91. Иконка `?` (подсказка) не отображается

**Симптом:** рядом с элементом UI нет иконки `?`, хотя ожидается подсказка.

**Причина:** возможные варианты:
1. Не применена миграция `add_25.sql` (таблицы `help_hint` нет).
2. Не применена seed-миграция `add_25_seed.sql` (8 подсказок не загружены).
3. `HelpHintsProvider` не обёрнут вокруг приложения.
4. `hint_key` в БД не совпадает с `id` в `<Hint id="..."/>`.
5. Подсказка имеет `is_published = FALSE`.

**Решение:**

**Шаг 1. Проверить миграции:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'help_hint') AS has_table,
       (SELECT COUNT(*) FROM help_hint WHERE is_published = TRUE) AS published_hints;
"
```

Должно быть `has_table = t` и `published_hints = 8`.

**Шаг 2. Применить миграции (если пусто):**

```bash
docker cp backend/migrations/add_25.sql aps_postgres:/tmp/add_25.sql
docker cp backend/migrations/add_25_seed.sql aps_postgres:/tmp/add_25_seed.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_25.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_25_seed.sql
```

**Шаг 3. Проверить конкретный ключ:**

Например, для подсказки в тулбаре Ганта (`gantt.edit_mode`):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT hint_key, title, is_published
FROM help_hint
WHERE hint_key = 'gantt.edit_mode';
"
```

Если пусто — либо ключ не совпадает с тем, что в `Hint.tsx`, либо не применён seed.

**Шаг 4. Проверить провайдер в `App.tsx`:**

```tsx
<HelpHintsProvider>
    <BrowserRouter>
        <AppRoutes />
    </BrowserRouter>
</HelpHintsProvider>
```

Провайдер должен быть **внутри** `AuthProvider` (загрузка подсказок начинается только после аутентификации).

**Шаг 5. Перезагрузить страницу** (`Ctrl+F5`) — кэш подсказок сбрасывается только при монтировании приложения.

---

### 92. Popover подсказки пустой (заголовок есть, тела нет)

**Симптом:** клик на `?` открывает Popover, но текст пустой.

**Причина:** в БД `body_md` пустая или `NULL` для этой подсказки.

**Решение:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT hint_key, title, LENGTH(body_md) AS body_len
FROM help_hint
WHERE hint_key = '<ваш_ключ>';
"
```

Если `body_len` = 0 или NULL — пересоздать seed-миграцию `add_25_seed.sql`.

---

### 93. Popover подсказки «дёргается» или не позиционируется

**Симптом:** Popover появляется не там, где нужно, или мигает.

**Причина:** MUI Popover позиционируется по `anchorEl`. Если иконка `?` внутри переиспользуемого компонента (например, в `TableCell`), `anchorEl` может терять ссылку при ре-рендере таблицы.

**Решение:**

1. Проверить, что в `Hint.tsx` `anchorEl` хранится в **локальном** `useState` (а не в общем контексте).
2. Проверить, что `onClick` не вызывает `setState` родителя (иначе таблица перерисуется и `anchorEl` станет stale).
3. Если проблема воспроизводится в AG Grid — использовать `event.currentTarget` (уже сделано в `Hint.tsx`).

---

### 94. Кнопка «Читать подробнее» ведёт на несуществующую статью

**Симптом:** клик по «Читать подробнее» → `/help/xxx` → «Статья не найдена».

**Причина:** `help_hint.article_slug` ссылается на slug, которого нет в `help_article`.

**Решение:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT h.hint_key, h.article_slug,
       CASE WHEN a.slug IS NULL THEN '❌ NOT FOUND' ELSE '✅ OK' END AS status
FROM help_hint h
LEFT JOIN help_article a ON a.slug = h.article_slug
WHERE h.article_slug IS NOT NULL
ORDER BY h.hint_key;
"
```

Если есть `❌ NOT FOUND` — либо исправить slug в `help_hint` (SQL UPDATE), либо создать недостающую статью через seed.

---

### 95. Подсказки не обновляются после правки в БД

**Симптом:** изменили `body_md` в `help_hint` через SQL, перезагрузили страницу, но текст подсказки старый.

**Причина:** кэш `HelpHintsContext` сохраняется на время жизни страницы (загружается **один раз** при монтировании приложения).

**Решение:**

1. **Hard reload** (`Ctrl+Shift+R`).
2. Если не помогло — проверить, что в `HelpHintsContext.tsx` есть `useEffect` на `[authLoading, isAuthenticated, loadHints]` (без `[]`).
3. Если всё ещё не обновляется — возможно, браузер кэширует GET `/api/v1/help/hints`. Проверить в DevTools → Network → Headers → `Cache-Control`.

**Долгосрочное решение:** в Итерации 15.5 (редактирование статей в UI) появится кнопка «Обновить кэш подсказок» — вызов `reload()` из `useHelpHints()`.

---

## FAQ (15.4)

### 96. FAQ-статьи не появились в справке

**Симптом:** в разделе «Помощь» (`/help`) нет категории «FAQ» и/или нет самих статей.

**Причина:** не применены seed-миграции `add_26_seed_1/2/3.sql` (Итерация 15.4).

**Решение:**

**Шаг 1. Проверить, что миграции применены:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS faq_count
FROM help_article
WHERE category = 'faq';
"
```

**Ожидаемо:** `faq_count = 15`.

Если `faq_count = 0` — применить:

```bash
docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker cp backend/migrations/add_26_seed_2.sql aps_postgres:/tmp/add_26_seed_2.sql
docker cp backend/migrations/add_26_seed_3.sql aps_postgres:/tmp/add_26_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_3.sql
```

**Шаг 2. Проверить, что 15 FAQ-статей действительно в БД:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title FROM help_article
WHERE category = 'faq'
ORDER BY display_order;
"
```

Должно быть 15 строк с префиксом `faq-`.

**Шаг 3. Перезагрузить страницу** (`Ctrl+F5`) — если FAQ-статьи добавлены
уже после открытия страницы.

**Шаг 4. Проверить через API:**

```bash
curl -s http://localhost:8000/api/v1/help/categories \
  -H "Authorization: Bearer $TOKEN" | grep -i faq
```

Должно быть `"key": "faq"`.

---

### 97. Категория FAQ не отображается в сайдбаре `/help`

**Симптом:** FAQ-статьи в БД есть, но в левой панели `/help` категории
«FAQ» нет.

**Причина:** возможные варианты:
1. Backend не перезапущен после добавления `faq` в `CATEGORY_ORDER`.
2. Frontend кэширует список категорий (загружается один раз).
3. `help.py` содержит опечатку в `CATEGORY_LABELS` / `CATEGORY_ORDER`.

**Решение:**

**Шаг 1. Проверить `help.py`:**

В `backend/app/api/v1/help.py` должно быть:

```python
CATEGORY_LABELS = {
    ...
    "faq": "FAQ",
}

CATEGORY_ORDER = [
    ...
    "settings",
    "faq",
]
```

**Шаг 2. Перезапустить backend:**

```bash
cd backend
# Ctrl+C в терминале backend
python run_server.py
```

**Шаг 3. Проверить API:**

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

Если ответ пустой — backend не видит FAQ-статьи в БД (см. пункт 96).

**Шаг 4. Hard reload на фронте** (`Ctrl+Shift+R`).

---

### 98. FAQ-статьи не находятся через поиск

**Симптом:** вводишь в поиске «FEASIBLE» или «сирота» — результатов нет.

**Причина:** возможные варианты:
1. Поиск использует `ILIKE` — если слово короче 2 символов, поиск не срабатывает.
2. В `title` / `content_md` / `tags` нет искомого слова.

**Решение:**

**Шаг 1. Проверить наличие слова в БД:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title
FROM help_article
WHERE category = 'faq'
  AND (title ILIKE '%FEASIBLE%' OR content_md ILIKE '%FEASIBLE%');
"
```

**Шаг 2. Проверить API:**

```bash
curl -s "http://localhost:8000/api/v1/help/search?q=FEASIBLE" \
  -H "Authorization: Bearer $TOKEN"
```

**Ожидаемо:** `hits` содержит `faq-plan-feasible-not-optimal`.

**Шаг 3. Если пусто** — проверить, что seed-миграция `add_26_seed_1.sql`
действительно содержит эту статью:

```bash
grep "faq-plan-feasible" backend/migrations/add_26_seed_1.sql
```

---

### 99. `ON CONFLICT DO NOTHING` в seed-миграции FAQ не работает

**Симптом:** при повторном применении `add_26_seed_*.sql` появляется
ошибка `ON CONFLICT (slug) DO NOTHING не срабатывает` или дубли.

**Причина:** миграция применялась через `Get-Content | docker exec`,
кириллица в `$md$...$md$` испортилась, slug-и не совпадают.

**Решение:**

1. Применять через `docker cp` + `psql -f` (не через pipe):

```bash
docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
```

2. Проверить, что дублей нет:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, COUNT(*)
FROM help_article
WHERE category = 'faq'
GROUP BY slug
HAVING COUNT(*) > 1;
"
```

Пусто — всё ок.

3. Если дубли уже появились — удалить лишние:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM help_article a
USING help_article b
WHERE a.id > b.id AND a.slug = b.slug;
"
```

---

### 100. FAQ-статья отображается с «кракозябрами» вместо кириллицы

**Симптом:** вместо «Что делать» отображается `Ð§Ñ‚Ð¾ Ð´ÐµÐ»Ð°Ñ‚ÑŒ`.

**Причина:** миграция применена через `Get-Content | docker exec` (или другой
pipe-способ) — PowerShell испортил UTF-8.

**Решение:**

1. **Удалить испорченные статьи:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM help_article WHERE category = 'faq';
"
```

2. **Применить заново через `docker cp`:**

```bash
docker cp backend/migrations/add_26_seed_1.sql aps_postgres:/tmp/add_26_seed_1.sql
docker cp backend/migrations/add_26_seed_2.sql aps_postgres:/tmp/add_26_seed_2.sql
docker cp backend/migrations/add_26_seed_3.sql aps_postgres:/tmp/add_26_seed_3.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_1.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_2.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_26_seed_3.sql
```

3. **Проверить:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title FROM help_article WHERE category = 'faq' ORDER BY display_order LIMIT 3;
"
```

Заголовки должны быть читаемыми на русском.

**Профилактика:** никогда не применять SQL-файлы с кириллицей через
`Get-Content | docker exec` — только `docker cp` + `psql -f`.

---

### 101. FAQ-статьи дублируются в поиске и категориях

**Симптом:** одна и та же FAQ-статья отображается 2-3 раза.

**Причина:** seed-миграции `add_26_seed_1/2/3.sql` применялись несколько раз
без `ON CONFLICT DO NOTHING` (или через pipe, испортивший slug).

**Решение:**

1. Найти дубли:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, COUNT(*) AS cnt
FROM help_article
WHERE category = 'faq'
GROUP BY slug
HAVING COUNT(*) > 1
ORDER BY slug;
"
```

2. Удалить дубли (оставить самую свежую запись):

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
DELETE FROM help_article a
USING help_article b
WHERE a.id < b.id AND a.slug = b.slug;
"
```

3. Проверить:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS faq_count FROM help_article WHERE category = 'faq';
"
```

Должно быть **15**.

---

### 102. Кнопка «Связанные статьи» в FAQ ведёт не туда

**Симптом:** клик по ссылке вида `[Обзор Ганта](/help/gantt-overview)` в
FAQ-статье — открывается 404 или не та статья.

**Причина:** возможные варианты:
1. Опечатка в slug внутри `content_md`.
2. Статья, на которую ссылаются, не была создана.
3. Ссылка не соответствует формату `/help/{slug}`.

**Решение:**

**Шаг 1. Найти все ссылки в FAQ-статьях:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, content_md
FROM help_article
WHERE category = 'faq' AND content_md LIKE '%/help/%';
"
```

**Шаг 2. Проверить, что все slug существуют:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT DISTINCT a.slug AS faq_slug
FROM help_article a
WHERE a.category = 'faq'
  AND a.content_md LIKE '%/help/%';
"
```

Вручную сопоставить slug'и из ссылок с существующими в `help_article`.

**Шаг 3. Исправить опечатки через UPDATE:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
UPDATE help_article
SET content_md = REPLACE(content_md, '/help/wrong-slug', '/help/correct-slug')
WHERE slug = 'faq-xxx';
"
```

Полная проверка ссылок — в тестах `tests/test_help_faq.py`
(`test_faq_articles_link_to_existing_slugs`).

---

## Диагностика

### 103. Общая проверка системы

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

# Снапшоты активного плана
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
```

**Ожидаемые значения:**

| Проверка | Ожидание |
|----------|----------|
| `help_articles` | 30 |
| `help_hints` | 8 |
| `faq_articles` | 15 |
| `active` версия | 1 |
| `plan_settings` активного плана | >0 |

---

### 104. Полная очистка и пересоздание

```bash
# 1. Снести контейнер
docker rm -f aps_postgres

# 2. Создать заново
docker run --name aps_postgres \
  -e POSTGRES_USER=aps \
  -e POSTGRES_PASSWORD=aps_secret \
  -e POSTGRES_DB=household \
  -p 5432:5432 \
  -d postgres:16

# 3. Применить схему
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

# 4. Применить миграции
$migrations = @("add_06.sql", "add_06b.sql", "add_07.sql", "add_08.sql",
                "fix_versions_hotfix.sql",
                "add_09.sql", "add_09b.sql", "add_09c.sql", "add_09d.sql",
                "add_10.sql", "add_10b.sql", "add_11.sql", "add_12.sql",
                "add_13.sql", "add_14.sql", "add_15.sql", "add_16.sql",
                "add_17.sql", "add_18.sql", "add_19.sql", "add_20.sql",
                "add_21.sql", "add_22.sql", "add_23.sql",
                "add_24.sql", "add_24_seed_1.sql", "add_24_seed_2.sql", "add_24_seed_3.sql",
                "add_25.sql", "add_25_seed.sql",
                "add_26_seed_1.sql", "add_26_seed_2.sql", "add_26_seed_3.sql",
                "fix_shift_names.sql", "fix_work_time.sql")
foreach ($m in $migrations) {
    docker cp "backend/migrations/$m" "aps_postgres:/tmp/$m"
    docker exec -i aps_postgres psql -U aps -d household -f "/tmp/$m"
}

# 5. Создать админа
cd backend
python -m scripts.create_admin_user

# 6. Запустить backend и frontend
python run_server.py
cd ../frontend; npm run dev
```

---

### 105. Полезные ссылки

- [README.md](../README.md) — основная документация.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — руководство разработчика.

---

## Если проблема не решена

1. Проверьте логи backend.
2. Проверьте логи PostgreSQL: `docker logs aps_postgres --tail 100`.
3. Проверьте консоль браузера (F12).
4. Откройте issue с описанием:
   - Симптом.
   - Шаги воспроизведения.
   - Логи.
   - Версия (см. README.md).