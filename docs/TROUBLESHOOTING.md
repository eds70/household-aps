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

### 8. `ModuleNotFoundError` при запуске

**Симптом:** `ModuleNotFoundError: No module named 'app'`.

**Причина:** запуск не из корня `backend/`.

**Решение:** перейти в `backend/`:

```bash
cd backend
python run_server.py
```

---

### 9. `ImportError` после добавления нового модуля

**Симптом:** `ImportError: cannot import name ...`.

**Причина:** кэш Python или неверный путь импорта.

**Решение:**

1. Очистить `__pycache__` (см. пункт 2).
2. Проверить `__init__.py` в директории.
3. Перезапустить сервер.

---

### 10. Backend не стартует: `Address already in use`

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

### 11. JWT-токен истёк

**Симптом:** `401 Unauthorized` после некоторого времени работы.

**Причина:** `JWT_EXPIRES_MINUTES` (по умолчанию 60).

**Решение:** войти заново или увеличить `JWT_EXPIRES_MINUTES` в `.env`.

---

### 12. `snapshot.py` не импортируется (Итерация 13.15)

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

### 13. `snapshot_all_catalogs` падает с `UndefinedColumnError`

**Симптом:** при создании плана или расчёте — ошибка типа `column operation_template.operator_pool does not exist`.

**Причина:** не применена миграция `add_09.sql`, но `snapshot.py` пытается вставить `operator_pool` в `operation_snapshot`.

**Решение:** модуль `snapshot.py` содержит graceful-обработку — проверяет наличие колонки `operator_pool` через `_has_column`. Если ошибка всё же возникает — примените миграцию:

```bash
docker cp backend/migrations/add_09.sql aps_postgres:/tmp/add_09.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09.sql
```

---

### 14. `500 Internal Server Error` при пересчёте с `replace_version_id`

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

### 15. `usePlan must be used within PlanProvider`

**Симптом:** ошибка `usePlan must be used within PlanProvider`.

**Причина:** кэш Vite.

**Решение:** перезапустить Vite с очисткой кэша:

```bash
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

---

### 16. Advisor «дёргается» (бесконечный ре-рендер)

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

### 17. `401 Unauthorized` при первом заходе на `/login`

**Симптом:** при открытии `/login` в консоли — `401 Unauthorized`.

**Причина:** `loadVersions` вызывается до аутентификации.

**Решение:** см. пункт 16 — вызывать `loadVersions` только после аутентификации.

---

### 18. `axios` не отправляет токен

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

### 19. Диаграмма Ганта: pan не работает

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

### 20. Диаграмма Ганта: задачи не таскаются

**Симптом:** drag-and-drop не работает.

**Причина:** `editable.updateTime` возвращает `false` для всех задач.

**Решение:** см. пункт 19. `updateTime` должен быть **функцией**, возвращающей `true` для реальных задач и `false` для setup/downtime.

---

### 21. Мастер смены: шапка «уезжает» вверх

**Симптом:** при большом количестве задач шапка уходит вверх при скролле.

**Решение:** в `ShiftPage.tsx`:

```tsx
<Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
   <Box sx={{ flexShrink: 0 }}>{/* Заголовок */}</Box>
   <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>{/* Список */}</Box>
</Box>
```

---

### 22. `npm install` падает с ошибкой

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

### 23. Frontend не видит backend

**Симптом:** запросы к API падают с `Network Error`.

**Решение:**

1. Проверить, что backend запущен: `curl http://localhost:8000/docs`.
2. Проверить `CORS_ORIGINS` в `.env`.
3. Проверить `vite.config.ts` (proxy).

---

### 24. План в списке помечен ⚠ (Итерация 13.15)

**Симптом:** рядом с планом жёлтая иконка ⚠.

**Причина:** `has_snapshot = false` — снапшоты справочников не заполнены.

**Решение:** см. пункт 30 (в разделе «Снапшоты справочников»).

---

### 25. GanttPage показывает «План пуст» (Итерация 13.15)

**Симптом:** при открытии плана вместо диаграммы — предупреждение «План пуст».

**Причина:** `currentPlanHasSnapshot === false` в `PlanContext`.

**Решение:** см. пункт 30.

---

### 26. Пункт «Аудит» отсутствует в меню

**Симптом:** в левом сайдбаре нет пункта «Аудит».

**Причина:** это **by design** — в Итерации 13.16 раздел «Аудит» временно скрыт из меню.

**Решение (если нужна отладка):** открыть страницу по прямой ссылке: http://localhost:5173/audit

---

### 27. «История планов» показывает много версий

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

### 28. Иерархия планов не строится (Tree Data)

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

### 29. Кнопка «↩ Разархивировать» не появляется

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

### 30. `psql: FATAL: database "household" does not exist`

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

### 31. Кириллица отображается как «кракозябры»

**Симптом:** русские буквы в БД выглядят как `????` или `ÐŸÑ€Ð¸Ð²ÐµÑ‚`.

**Причина:** применение SQL-файла через `Get-Content | docker exec`.

**Решение:** применять через `docker cp` + `psql -f`:

```bash
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
```

---

### 32. `relation "..." does not exist`

**Симптом:** `relation "plan_settings" does not exist`.

**Причина:** не применена миграция.

**Решение:** см. пункт 5. Применить нужную миграцию.

---

### 33. `duplicate key value violates unique constraint`

**Симптом:** при вставке — `duplicate key value violates unique constraint`.

**Решение:** зависит от констрейнта:

| Констрейнт | Причина | Решение |
|------------|---------|---------|
| `plan_settings (schedule_version_id, setting_key)` | Дубль настройки | `ON CONFLICT DO NOTHING` |
| `resource_pool (organization_id, type)` | Дубль пула | Удалить старый или обновить |
| `cz_scan_log (organization_id, cz_code)` | Повторный скан | Идемпотентно, `duplicate: true` |
| `equipment_snapshot (id, version_id)` | Дубль снапшота | `ON CONFLICT DO NOTHING` (by design) |

---

### 34. PostgreSQL не стартует

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

### 35. Долгий запрос блокирует БД

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

### 36. Solver выдаёт `FEASIBLE` вместо `OPTIMAL`

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

### 37. Solver не находит решение (`INFEASIBLE`)

**Симптом:** `status: "INFEASIBLE"`.

**Решение:**

1. Проверить Advisor: `GET /api/v1/schedule/advice`.
2. Проверить заказы и доступность оборудования.
3. Проверить календарь простоев.
4. Уменьшить `horizon_hours`.
5. Проверить, нет ли заблокированных партий, которые нельзя запланировать.

---

### 38. Solver работает слишком долго

**Симптом:** расчёт занимает >10 минут.

**Решение:**

1. Уменьшить `horizon_hours` (например, до 720).
2. Уменьшить `timeout_seconds` (например, до 600).
3. Упростить задачу (убрать лишние заказы).

---

### 39. `overlaps_after > 0` после постобработки

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

### 40. `dependency_violations > 0`

**Симптом:** после постобработки есть нарушения зависимостей.

**Решение:** пересчитать план. Если повторяется — сообщить о баге.

---

## What-if

### 41. Сценарий завис в статусе `RUNNING`

**Симптом:** сценарий не завершается.

**Решение:**

1. Подождать (solver может работать до 10 минут).
2. Проверить логи backend.
3. Удалить сценарий (если не удаляется — см. пункт 42).

---

### 42. Не удаётся удалить сценарий

**Симптом:** `DELETE /api/v1/whatif/scenarios/{id}` возвращает ошибку.

**Причина:** сценарий в статусе `RUNNING` — удаление запрещено.

**Решение:** дождаться завершения (`DONE`/`FAILED`) или убить процесс solver.

---

### 43. What-if не откатывает изменения

**Симптом:** после what-if изменения в БД остались.

**Решение:**

1. Проверить, что `ProductionScheduler` получает `session` извне.
2. Проверить, что `ScheduleSaver` не делает commit при `_owns_session=False`.
3. Перезапустить backend.

---

### 44. What-if: `500 Internal Server Error`

**Симптом:** `POST /run` возвращает 500.

**Решение:**

1. Проверить логи backend.
2. Проверить формат `changes` (JSON).
3. Убедиться, что `base_version_id` существует.

---

## plan_settings

### 45. Таблица `plan_settings` пуста

**Симптом:** `SELECT COUNT(*) FROM plan_settings` возвращает 0.

**Причина:** не применена миграция `add_21.sql`.

**Решение:**

```bash
docker cp backend/migrations/add_21.sql aps_postgres:/tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
```

---

### 46. Триггер `copy_app_settings_to_plan` не срабатывает

**Симптом:** создали план, но `plan_settings` пуст.

**Решение:** проверить наличие триггера:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname FROM pg_trigger WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

Если пусто — пересоздать миграцию `add_21.sql`.

---

### 47. `404 Not Found` при `GET /api/v1/plan-settings/version/{id}`

**Причина:** не подключён в `main.py`.

**Решение:** см. пункт 6.

---

### 48. Мастер настроек показывает пустой список полей

**Причина:** `settingsApi.getSchema()` вернул пустой `settings`.

**Решение:** проверить `SETTINGS_REGISTRY` в `backend/app/scheduler/settings.py` — там должно быть 30+ записей.

---

### 49. В мастере настроек отсутствует кнопка «Сохранить»

**Причина:** `changedKeys.length === 0` — нет изменений.

**Решение:** это by design. Измените любое поле — кнопка активируется.

---

### 50. `plan_settings` не обновляются при изменении `app_settings`

**Причина:** это by design (снапшот).

**Решение:** сбросить `plan_settings` к глобальным:

```bash
curl -X POST http://localhost:8000/api/v1/plan-settings/version/$VERSION_ID/reset \
  -H "Authorization: Bearer $TOKEN"
```

---

### 51. Существующие планы не имеют `plan_settings`

**Причина:** планы созданы до миграции `add_21.sql`.

**Решение:** сбросить к глобальным (см. пункт 50) или создать новый план.

---

## Архивация версий (13.21)

### 52. Старая версия не архивируется при пересчёте

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
либо удалить, либо разархивировать вручную (см. пункт 54).

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

### 53. Колонка `is_archived` не найдена

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

### 54. Разархивировать версию вручную через SQL

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

### 55. В списке планов 50+ версий после отключения архивации

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

### 56. Иерархия планов плоская (все корни)

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

### 57. Снекбар об архивации не показывается

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

### 58. План открыт, но все справочники пусты

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

### 59. `POST /schedule/versions` создаёт план, но снапшоты пусты

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

### 60. Удалить все пустые планы одной командой

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

### 61. Скан не привязывается к партии

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

### 62. Дубликаты сканов

**Симптом:** `duplicate: true` в ответе.

**Причина:** идемпотентность по `cz_code`.

**Решение:** это by design. Повторный скан не увеличивает `cz_marked_qty`.

---

### 63. `cz_status` не обновляется

**Симптом:** после сканов `cz_status` остаётся `PENDING`.

**Причина:** не достигнут порог `cz_completion_threshold`.

**Решение:** проверить `cz_marked_qty` и `planned_qty`. Порог по умолчанию — 0.95.

---

### 64. `CZ_INCOMPLETE` в Advisor, но маркировка завершена

**Симптом:** Advisor выдаёт `CZ_INCOMPLETE`, хотя `cz_status = COMPLETED`.

**Причина:** кэш Advisor.

**Решение:** перезагрузить страницу или пересчитать план.

---

## Лаборатория

### 65. Заблокированная партия всё равно в плане

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

### 66. `LAB` не может заблокировать партию

**Симптом:** `403 Forbidden`.

**Решение:** блокировать могут `LAB`, `MASTER`, `ADMIN`. Проверить роль.

---

### 67. После разблокировки партия не появляется в плане

**Решение:** см. пункт 65.

---

## Смены

### 68. При смене `shift_mode` задачи теряют привязку

**Симптом:** после `POST /api/v1/settings/shift-mode` у задач `shift_id = NULL`.

**Причина:** это by design — старые UUID смен невалидны.

**Решение:** пересчитать план.

---

### 69. `by-date` не находит смену

**Решение:** сравнение по МСК-дате (см. пункт 4).

---

### 70. Смены не созданы

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

### 71. Pan диаграммы не работает

**Симптом:** нельзя таскать диаграмму.

**Решение:** см. пункт 19.

---

### 72. Задачи не таскаются

**Решение:** см. пункт 20.

---

### 73. Tooltip не показывается при перетаскивании

**Симптом:** при drag-and-drop задачи tooltip не появляется.

**Причина:** в vis-timeline 8.x события `itemmoving` / `itemresizing` не генерируются. Мы используем нативные pointer-события.

**Решение:**

1. Проверить, что `useGanttTimeline` содержит `attachNativeDragListeners`.
2. Проверить, что `onItemChange` передан в `useGanttTimeline`.
3. Открыть DevTools → Console — при drag не должно быть ошибок.

---

### 74. Resize задачи не работает

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

### 75. Группа LINE_FILL не раскрывается

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

## Диагностика

### 76. Общая проверка системы

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
```

---

### 77. Полная очистка и пересоздание

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
                "add_21.sql", "add_23.sql", "fix_shift_names.sql")
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

### 78. Полезные ссылки

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