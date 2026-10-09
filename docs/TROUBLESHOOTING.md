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
- [Интерактивный туториал (15.3)](#интерактивный-туториал-153)
- [FAQ (15.4)](#faq-154)
- [Редактирование статей через UI (15.5)](#редактирование-статей-через-ui-155)
- [Docker / облако (production)](#docker--облако-production)
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
| `is_archived` | `add_23.sql` |
| `help_article` (таблица) | `add_24.sql` |
| `help_hint` (таблица) | `add_25.sql` |
| `audit_saved_view` (таблица) | `add_28.sql` |

> **Замечание:** если разворачиваете с нуля через `backend/init_schema_v4.9.sql`
> + `init_schema_v4.9_seed.sql` — **все эти миграции уже включены**. Проблема
    > возникает только при апгрейде старой БД.

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
   Должно быть **31** (после Итерации 15.3).
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
7. Проверить, что применена seed-миграция `add_27_seed_1.sql` (туториал):
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT COUNT(*) FROM help_article WHERE slug = 'tutorial-interactive';
   "
   ```
   Должно быть **1**.

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

**Причина:** `ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию 1440 = 24 часа).

**Решение:** войти заново или увеличить `ACCESS_TOKEN_EXPIRE_MINUTES` в `.env`.

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
2. Проверить `ALLOWED_ORIGINS` в `.env`.
3. Проверить `vite.config.ts` (proxy).

---

### 25. План в списке помечен ⚠ (Итерация 13.15)

**Симптом:** рядом с планом жёлтая иконка ⚠.

**Причина:** `has_snapshot = false` — снапшоты справочников не заполнены.

**Решение:** см. пункт 59 (в разделе «Снапшоты справочников»).

---

### 26. GanttPage показывает «План пуст» (Итерация 13.15)

**Симптом:** при открытии плана вместо диаграммы — предупреждение «План пуст».

**Причина:** `currentPlanHasSnapshot === false` в `PlanContext`.

**Решение:** см. пункт 59.

---

### 27. Пункт «Аудит» отсутствует в меню

**Симптом:** в левом сайдбаре нет пункта «Аудит».

**Причина:** в **старых версиях** (до Итерации 16) — by design, раздел был временно скрыт. **С версии 4.9.0** — пункт меню должен быть виден.

**Решение:**

1. Проверить, что `frontend/src/components/layout/MainLayout.tsx` содержит:
   ```tsx
   { path: '/audit', label: 'Аудит', icon: <HistoryIcon /> },
   ```
2. Проверить, что `frontend/src/App.tsx` содержит:
   ```tsx
   <Route path="audit" element={<AuditPage />} />
   ```
3. Если оба на месте, но пункта нет — очистить кэш:
   ```bash
   cd frontend
   Remove-Item -Recurse -Force node_modules\.vite
   npm run dev
   ```
4. Пока — открыть по прямой ссылке: http://localhost:5173/audit

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
  -d postgres:17
```

---

### 32. Кириллица отображается как «кракозябры»

**Симптом:** русские буквы в БД выглядят как `????` или `ÐŸÑ€Ð¸Ð²ÐµÑ‚`.

**Причина:** применение SQL-файла через `Get-Content | docker exec`.

**Решение:** применять через `docker cp` + `psql -f`:

```bash
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/init_schema_v4.9.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql
```

**Для production (Docker):** см. пункт 127 в разделе «Docker / облако».

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
| `audit_saved_view (organization_id, user_id, name)` | Дубль имени представления | Выбрать другое имя |

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
  -d postgres:17
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

Должно быть **31** (после Итерации 15.3).

> **Альтернатива:** если разворачиваете через `init_schema_v4.9.sql` +
> `init_schema_v4.9_seed.sql` — все статьи уже внутри.

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

---

## Интерактивный туториал (15.3)

### 96. Туториал не запускается

**Симптом:** клик на кнопку «Запустить тур» — ничего не происходит, или появляется ошибка.

**Причина:** возможные варианты:
1. Библиотека `react-joyride` не установлена.
2. `TutorialProvider` не обёрнут вокруг приложения в `App.tsx`.
3. Кэш Vite устарел после добавления `react-joyride`.

**Решение:**

**Шаг 1. Проверить установку:**

```bash
cd frontend
npm list react-joyride
```

Если пусто — установить:

```bash
npm install react-joyride@^3.2.0
```

**Шаг 2. Проверить провайдер в `App.tsx`:**

```tsx
<AuthProvider>
    <PlanProvider>
        <HelpHintsProvider>
            <TutorialProvider>
                <BrowserRouter>
                    <AppRoutes />
                </BrowserRouter>
            </TutorialProvider>
        </HelpHintsProvider>
    </PlanProvider>
</AuthProvider>
```

**Шаг 3. Очистить кэш Vite:**

```bash
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

**Шаг 4. Перезагрузить страницу** (`Ctrl+F5`).

---

### 97. Туториал не подсвечивает нужный элемент

**Симптом:** тур запускается, но подсвечивает пустое место или другое место.

**Причина:** `target` в конфигурации тура не совпадает с реальным `data-tour-id` в DOM, или элемент ещё не отрисован.

**Решение:**

**Шаг 1. Проверить `data-tour-id` в DOM:**

1. Откройте DevTools → Elements.
2. Найдите целевой элемент (например, кнопку «Построить план»).
3. Проверьте, что у него есть атрибут `data-tour-id="schedule-build-button"`.

**Шаг 2. Сверить с `tours.ts`:**

В `frontend/src/tutorial/tours.ts`:

```typescript
{
    target: '[data-tour-id="schedule-build-button"]',
    content: '...',
}
```

`target` и `data-tour-id` должны совпадать **точно** (включая все дефисы).

**Шаг 3. Проверить порядок рендера:**

Если элемент ещё не отрисован (например, страница только загрузилась), Joyride подсветит пустое место. Туры должны запускаться на **полностью отрисованной** странице.

**Обходное решение:** использовать `before` в конфигурации шага:

```typescript
{
    target: '[data-tour-id="some-element"]',
    content: '...',
    before: () => new Promise((resolve) => setTimeout(resolve, 300)),
}
```

---

### 98. Туториал показывается повторно после завершения

**Симптом:** прошли тур, но при следующем заходе он снова предлагается.

**Причина:** `localStorage` ключ `aps_tutorial_completed_<tour_id>` не сохранён.

**Решение:**

**Шаг 1. Проверить `localStorage`:**

DevTools → Application → Local Storage → `http://localhost:5173`.

Ищите ключи:
- `aps_tutorial_completed_getting-started`
- `aps_tutorial_completed_gantt-basics`
- `aps_tutorial_completed_shift-management`

**Шаг 2. Если ключа нет — проверить `TutorialContext`:**

В `TutorialContext.tsx` должно быть:

```typescript
const completeTour = () => {
    if (activeTourId) {
        localStorage.setItem(
            `aps_tutorial_completed_${activeTourId}`,
            'true'
        );
    }
    setActiveTourId(null);
};
```

Метод `completeTour` должен вызываться в `onComplete` callback от Joyride.

**Шаг 3. Если ключ есть, но тур всё равно запускается:**

Проверить `isTourCompleted`:

```typescript
const isTourCompleted = (tourId: string): boolean => {
    return localStorage.getItem(`aps_tutorial_completed_${tourId}`) === 'true';
};
```

И что `HelpPage` использует `isTourCompleted` перед запуском.

---

### 99. Туториал не проходит через все шаги

**Симптом:** тур останавливается после 3-4 шагов, кнопки «Далее» пропадают.

**Причина:** возможные варианты:
1. Один из целевых элементов отсутствует в DOM (например, скрыт из-за фильтра).
2. Ошибка в JS-коде внутри шага.
3. Открылся модальный диалог, который перекрывает подсветку.

**Решение:**

**Шаг 1. Открыть DevTools → Console:**

Ищите ошибки вроде `[Joyride] Target not found: ...`.

**Шаг 2. Проверить каждый `target`:**

Для каждого шага вручную выполните в Console:

```javascript
document.querySelector('[data-tour-id="schedule-build-button"]')
```

Если возвращает `null` — элемент не отрисован. Проверьте, что вы на **правильной странице** для этого тура.

**Шаг 3. Ограничения туров:**

Тур `gantt-basics` требует, чтобы открыт план на Ганте. Тур `shift-management` требует открытой смены. Если этих условий нет — часть шагов пропустится.

**Обходное решение:** сделать шаги условными:

```typescript
{
    target: '[data-tour-id="gantt-toolbar"]',
    content: '...',
    skipBeacon: true,
    disableBeacon: true,
}
```

---

### 100. Прогресс туров сохраняется между разными пользователями

**Симптом:** коллега прошёл тур на моём компьютере — у меня он тоже считается пройденным.

**Причина:** `localStorage` не разделяется по пользователям.

**Решение:**

Это **by design** — прогресс хранится в браузере, не в БД.

**Обходные пути:**

1. **Не использовать общий браузер** — каждый сотрудник заходит со своего устройства.
2. **Сбрасывать при выходе из системы** — модифицировать `AuthContext.logout()`:
   ```typescript
   const logout = () => {
       // ...
       localStorage.removeItem('aps_tutorial_completed_getting-started');
       localStorage.removeItem('aps_tutorial_completed_gantt-basics');
       localStorage.removeItem('aps_tutorial_completed_shift-management');
   };
   ```
3. **Планируемое решение (Итерация 16.x):** перенос прогресса в `app_user`.

---

### 101. Кнопка «Пройти заново» не работает

**Симптом:** клик по «Пройти заново» не сбрасывает прогресс.

**Причина:** метод `resetTour` не удаляет ключ из `localStorage`, или UI не обновляется.

**Решение:**

**Шаг 1. Проверить `resetTour` в `TutorialContext`:**

```typescript
const resetTour = (tourId: string) => {
    localStorage.removeItem(`aps_tutorial_completed_${tourId}`);
    // Триггерим ререндер через setState
    setForceUpdate((n) => n + 1);
};
```

**Шаг 2. Проверить, что `HelpPage` подписан на изменения:**

Использовать `useTutorial()` и вызывать `resetTour` из контекста. После сброса — обновлять локальный стейт.

**Шаг 3. Проверить вручную:**

DevTools → Console:

```javascript
localStorage.removeItem('aps_tutorial_completed_getting-started');
location.reload();
```

Если после этого тур запускается — проблема в UI-обновлении, не в сохранении.

---

## FAQ (15.4)

### 102. FAQ-статьи не появились в справке

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

**Шаг 3. Перезагрузить страницу** (`Ctrl+F5`).

**Шаг 4. Проверить через API:**

```bash
curl -s http://localhost:8000/api/v1/help/categories \
  -H "Authorization: Bearer $TOKEN" | grep -i faq
```

Должно быть `"key": "faq"`.

---

### 103. Категория FAQ не отображается в сайдбаре `/help`

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

**Шаг 4. Hard reload на фронте** (`Ctrl+Shift+R`).

---

### 104. FAQ-статьи не находятся через поиск

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

### 105. `ON CONFLICT DO NOTHING` в seed-миграции FAQ не работает

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

### 106. FAQ-статья отображается с «кракозябрами» вместо кириллицы

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

---

### 107. FAQ-статьи дублируются в поиске и категориях

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

### 108. Кнопка «Связанные статьи» в FAQ ведёт не туда

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

Полная проверка ссылок — в тестах `tests/test_help_faq.py`.

---

## Редактирование статей через UI (15.5)

### 109. Кнопка «Новая статья» не появляется

**Симптом:** на странице `/help` в шапке нет кнопки «Новая статья».

**Причина:** кнопка видна только роли **ADMIN**.

**Решение:**

1. Проверить роль текущего пользователя:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/auth/me | jq '.role'
   ```
   Должно быть `"ADMIN"`.
2. Если роль другая — войти под админом.
3. Если роль ADMIN, но кнопки нет — очистить кэш Vite:
   ```bash
   cd frontend
   Remove-Item -Recurse -Force node_modules\.vite
   npm run dev
   ```

---

### 110. `403 Forbidden` при попытке создать/изменить статью

**Симптом:** `POST /api/v1/help/articles` (или `PUT`/`DELETE`) возвращает `403`.

**Причина:** роль пользователя не ADMIN.

**Решение:**

1. Проверить роль:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/auth/me | jq '.role'
   ```
2. CRUD-эндпоинты защищены `Depends(require_admin)` — доступ только ADMIN.
3. Если роль нужно изменить — обновить в БД:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   UPDATE app_user SET role = 'ADMIN' WHERE email = '<email>';
   "
   ```

---

### 111. `409 Conflict` при создании статьи

**Симптом:** `POST /api/v1/help/articles` возвращает `409`.

**Причина:** slug уже занят другой статьёй.

**Ответ сервера:**
```json
{
  "detail": "Статья со slug 'my-article' уже существует"
}
```

**Решение:**

1. Выбрать другой slug.
2. Или не передавать slug вовсе — он сгенерируется из title
   (`_slugify`) и будет уникальным.
3. Проверить занятые slug'и:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT slug FROM help_article WHERE slug LIKE '%my-article%';
   "
   ```

---

### 112. `400 Bad Request` при создании статьи

**Симптом:** `POST /api/v1/help/articles` возвращает `400`.

**Возможные причины и решения:**

| detail | Причина | Решение |
|--------|---------|---------|
| `Неизвестная категория: 'xxx'` | Опечатка в category | Использовать одну из 9 категорий |
| `Не удалось сгенерировать slug из title` | Заголовок из одних символов | Добавить буквы в заголовок |
| `slug не может быть пустым` | Пустой slug при update | Убрать поле slug из запроса |
| `Нет данных для обновления` | Все поля update = null | Передать хотя бы одно поле |

**Проверить допустимые категории:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT DISTINCT category FROM help_article ORDER BY category;
"
```

Ожидаемо: `getting-started`, `planning`, `gantt`, `shift`, `lab`, `cz`,
`whatif`, `settings`, `faq`.

---

### 113. Статья не появляется в списке после создания

**Симптом:** создали статью через UI, но её нет в сайдбаре `/help`.

**Причина:** возможные варианты:
1. `is_published = false` (статья скрыта).
2. `organization_id` не совпадает с текущей организацией.
3. Frontend кэширует список статей (загружается один раз при монтировании).

**Решение:**

1. Проверить в БД:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT slug, is_published, organization_id, category
   FROM help_article
   WHERE slug = 'my-article';
   "
   ```
   - `is_published` должно быть `true`.
   - `organization_id` должна совпадать с вашей организацией.

2. Перезагрузить страницу (`Ctrl+F5`).

3. Если статьи нет в списке категории — проверить, что её category
   входит в `CATEGORY_ORDER`:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT category, COUNT(*) FROM help_article
   WHERE slug = 'my-article' GROUP BY category;
   "
   ```

---

### 114. Удаление статьи прошло, но она всё ещё видна

**Симптом:** `DELETE /api/v1/help/articles/{slug}` вернул success, но
статья отображается в UI.

**Причина:** frontend не перезагрузил список статей после удаления.

**Решение:**

1. Перезагрузить страницу (`Ctrl+F5`).
2. Проверить в БД:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT slug FROM help_article WHERE slug = 'my-article';
   "
   ```
   Если пусто — статья удалена, проблема в UI (перезагрузить).
3. Если статья есть в БД — эндпоинт вернул 404, но UI показал success
   (баг клиента, сообщить).

---

### 115. Редактор статьи: кнопка «Сохранить» серая

**Симптом:** форма редактора открыта, но кнопка «Сохранить» неактивна.

**Причина:** не заполнены обязательные поля.

**Решение:** проверить:

| Поле | Требование |
|------|------------|
| `title` | Минимум 3 символа, обязательно |
| `category` | Обязательно (селект) |
| `content_md` | Минимум 1 символ, обязательно |
| `slug` | Опционально — генерируется из title |
| `display_order` | Опционально — авто `max+10` |

Кнопка активируется, когда все три обязательных поля заполнены.

---

### 116. `changedKeys` в мастере настроек не содержит изменённых полей

**Симптом:** изменили поле в мастере, но кнопка «Сохранить» всё ещё
неактивна.

**Причина:** возможно, изменили поле, которое **не** относится к категории
текущего шага. Мастер сохраняет только поля, отличающиеся от `originalValues`.

**Решение:**

1. Проверить в React DevTools → `PlanSettingsWizard` → `changedKeys`.
2. Если изменённое поле в списке — баг, сообщить.
3. Если нет — возможно, поле относится к системным (`is_system=true`) и
   не сохраняется через мастер.

---

## Docker / облако (production)

Проблемы при развёртывании через `docker-compose.prod.yml`.

### 120. `curl` в PowerShell ведёт себя странно

**Симптом:** команда `curl -I http://localhost/health` в PowerShell
выдаёт `Invoke-WebRequest : Укажите значения для следующих параметров: Uri`.

**Причина:** в PowerShell `curl` — это **алиас** для `Invoke-WebRequest`,
а не настоящий curl из Linux. Флаги `-I`, `-X`, `-d` работают иначе.

**Решение:** использовать **`curl.exe`** (настоящий curl из `System32`):

```powershell
curl.exe -I http://your-server-ip/health
```

Или PowerShell-нативный вариант:

```powershell
(Invoke-WebRequest -Uri http://your-server-ip/health -UseBasicParsing).Content
```

**Правило:** в PowerShell `curl` без `.exe` — **всегда** `Invoke-WebRequest`.

---

### 121. `docker compose down -v` удалил базу данных

**Симптом:** после `docker compose -f docker-compose.prod.yml down -v`
БД пуста, все данные потеряны.

**Причина:** флаг `-v` **удаляет именованные volumes**, включая `pgdata`.

**Решение:**

**Шаг 1.** Если есть бэкап — восстановить:
```bash
gunzip -c backup_YYYYMMDD_HHMMSS.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household
```

**Шаг 2.** Если бэкапа нет — БД пересоздать:
```bash
./scripts/deploy_init.sh   # или .ps1
```

**Профилактика:**
- **Никогда** не использовать `down -v` без явного намерения удалить данные.
- Настроить cron-бэкап (см. [DEPLOYMENT.md](DEPLOYMENT.md), шаг 11).
- Остановка — только `docker compose -f docker-compose.prod.yml down`.

---

### 122. Backend падает с `connection refused` (PostgreSQL)

**Симптом:** `docker compose logs backend` показывает `ConnectionRefusedError:
[Errno 111] Connection refused`.

**Причина:** backend стартует **раньше**, чем PostgreSQL готов принимать
соединения.

**Решение:**

**Шаг 1.** Проверить `docker-compose.prod.yml`:
```yaml
depends_on:
  postgres:
    condition: service_healthy
```

**Шаг 2.** Проверить, что у `postgres` есть `healthcheck`:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U aps -d household"]
  interval: 5s
  timeout: 5s
  retries: 12
  start_period: 20s
```

**Шаг 3.** Проверить статус:
```bash
docker compose -f docker-compose.prod.yml ps
```

`aps_postgres` должен быть `Up (healthy)`.

**Если проблема есть при правильном конфиге** — перезапустить:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

---

### 123. Frontend стучится на `localhost:8000` вместо домена

**Симптом:** страница открывается, но запросы к API идут на
`http://localhost:8000` → `Network Error`.

**Причина:** `VITE_API_URL` не задан при **сборке** frontend.

**Ключевое:** Vite вшивает переменные `VITE_*` в бандл **на этапе сборки**,
не в runtime.

**Решение:**

**Шаг 1.** Проверить `.env` в корне:
```bash
grep VITE_API_URL .env
```

**Шаг 2.** Пересобрать frontend:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Шаг 3.** Проверить в браузере: DevTools → Network → запросы должны
идти на `https://your-domain.com/api/v1/...`.

---

### 124. CORS-ошибка: `No 'Access-Control-Allow-Origin'`

**Симптом:** в браузере `Access to XMLHttpRequest at 'http://your-server-ip/api/v1/...'
from origin 'http://your-server-ip' has been blocked by CORS policy`.

**Причина:** домен/IP облака не в `ALLOWED_ORIGINS`.

**Решение:**

**Шаг 1.** Проверить `.env`:
```bash
grep ALLOWED_ORIGINS .env
# Ожидаемо: ALLOWED_ORIGINS=http://your-server-ip,https://your-domain.com
```

**Шаг 2.** Перезапустить backend:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

**Частая ошибка:** `ALLOWED_ORIGINS` с пробелами (`a, b`) — использовать
**без пробелов**.

---

### 125. `Port is already allocated` при `up -d`

**Симптом:** `docker compose up -d` падает с
`Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:80
-> 0.0.0.0:0: listen tcp 0.0.0.0:80: bind: address already in use`.

**Причина:** порт 80 (или 443) занят другим процессом.

**Решение:**

**Шаг 1.** Найти занятый порт:
```bash
sudo lsof -i :80
# или
sudo netstat -tlnp | grep :80
```

**Шаг 2.** Остановить конфликтующий сервис:
```bash
sudo systemctl stop nginx
sudo systemctl disable nginx
```

**Шаг 3.** Проверить, что порты свободны:
```bash
sudo lsof -i :80
sudo lsof -i :443
```

**Шаг 4.** Запустить снова:
```bash
docker compose -f docker-compose.prod.yml up -d
```

---

### 126. `dependency failed to start: container aps_postgres is unhealthy`

**Симптом:** `docker compose up -d` → `dependency failed to start`.

**Причина:** PostgreSQL не может инициализироваться — обычно из-за прав
доступа к volume `pgdata` или неправильных `POSTGRES_*` env.

**Решение:**

**Шаг 1.** Посмотреть логи postgres:
```bash
docker compose -f docker-compose.prod.yml logs postgres --tail=100
```

**Шаг 2.** Частые причины:
- `POSTGRES_PASSWORD` не задан.
- Volume `pgdata` повреждён (был создан с другим паролем).
- Не хватает места на диске.

**Шаг 3.** Если volume повреждён:
```bash
# ⚠️ ЭТО УДАЛИТ ДАННЫЕ. Только если БД не нужна.
docker compose -f docker-compose.prod.yml down
docker volume rm household-aps_pgdata
docker compose -f docker-compose.prod.yml up -d
```

---

### 127. Кириллица в БД превратилась в `????`

**Симптом:** статьи справки, названия смен, имена пользователей —
всё русское отображается как `????` или `ÐŸÑ€Ð¸Ð²ÐµÑ‚`.

**Причина:** SQL-файл применён через **pipe**.

**Решение:**

**Шаг 1.** Понять, что испорчено:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "SELECT slug, title FROM help_article LIMIT 3;"
```

**Шаг 2.** Удалить испорченные seed-данные:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "DELETE FROM help_article WHERE category = 'faq';"
```

**Шаг 3.** Применить заново **правильным способом**:
```bash
docker compose -f docker-compose.prod.yml cp \
    backend/init_schema_v4.9_seed.sql postgres:/tmp/init_schema_v4.9_seed.sql
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -f /tmp/init_schema_v4.9_seed.sql
```

**Правило:** SQL-файлы с кириллицей — **только** `docker cp` + `psql -f`.

---

### 128. `permission denied` при `docker ps` / `docker compose`

**Симптом:** `permission denied while trying to connect to the Docker daemon
socket at unix:///var/run/docker.sock`.

**Причина:** пользователь не в группе `docker`.

**Решение:**

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Затем перелогиниться (выйти и зайти снова по SSH).

**Проверка:**
```bash
groups | grep docker
docker ps
```

---

### 129. `--workers 2` + `Too many connections` в PostgreSQL

**Симптом:** в логах backend — `asyncpg.exceptions.TooManyConnectionsError:
sorry, too many clients already`.

**Причина:** 2 uvicorn worker'а создают **отдельный пул соединений** к БД.

**Решение:**

**Вариант 1 — уменьшить workers до 1:**
```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Вариант 2 — увеличить `max_connections` PostgreSQL:**
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -c "ALTER SYSTEM SET max_connections = 200;"
docker compose -f docker-compose.prod.yml restart postgres
```

**Вариант 3 — настроить pool_size** в `backend/app/auth/dependencies.py`:
```python
_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=3,
    max_overflow=5,
)
```

**Рекомендация:** для теста пользователем — `--workers 1`.

---

### 130. `VITE_API_URL` изменили, но frontend не обновился

**Симптом:** поменяли `VITE_API_URL` в `.env`, перезапустили `up -d`, но
frontend всё равно стучится на старый URL.

**Причина:** `VITE_API_URL` вшивается **при сборке образа**.

**Решение:**

**Шаг 1.** Пересобрать frontend:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Шаг 2.** Hard reload в браузере (`Ctrl+Shift+R`).

**Шаг 3.** Проверить, что новый URL вшит:
```bash
docker compose -f docker-compose.prod.yml exec frontend \
    grep -r "your-domain.com" /usr/share/nginx/html/assets/ | head -3
```

**Правило:** после изменения любой `VITE_*` переменной — пересобрать frontend.

---

### 131. Nginx выдаёт `502 Bad Gateway`

**Симптом:** браузер → `502 Bad Gateway`, в логах nginx — `connect() failed
(111: Connection refused)`.

**Причина:** nginx не может достучаться до backend или frontend.

**Решение:**

**Шаг 1.** Проверить статус:
```bash
docker compose -f docker-compose.prod.yml ps
```

**Шаг 2.** Логи backend:
```bash
docker compose -f docker-compose.prod.yml logs backend --tail=50
```

**Шаг 3.** Проверить сеть:
```bash
docker compose -f docker-compose.prod.yml exec nginx \
    ping -c 1 backend
docker compose -f docker-compose.prod.yml exec nginx \
    ping -c 1 frontend
```

**Шаг 4.** Проверить имена сервисов в `nginx/nginx.conf`:
```nginx
upstream aps_backend {
    server backend:8000;   # ← должно быть "backend", не "aps_backend"
}
```

---

### 132. Nginx не отдаёт SPA-роуты (`/audit`, `/help/xxx`) — 404

**Симптом:** главная работает, но прямой переход на `/audit` → 404.

**Причина:** nginx не делает SPA-fallback. Проверить в **внутреннем**
nginx (`frontend/nginx.conf`).

**Решение:**

**Шаг 1.** Проверить в `frontend/nginx.conf`:
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

**Шаг 2.** Пересобрать frontend:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Шаг 3.** Проверить:
```bash
curl.exe -I http://your-server-ip/audit
# Ожидаемо: HTTP/1.1 200 OK
```

---

### 133. Сайт работает по HTTP, но HTTPS не поднимается

**Симптом:** после настройки certbot `https://your-domain.com` не
открывается.

**Возможные причины и решения:**

| Причина | Решение |
|---------|---------|
| Сертификаты не скопированы в `nginx/certs/` | Проверить: `ls nginx/certs/` |
| Порты 443 не проброшены | Раскомментировать `- "443:443"` в compose |
| Порт 443 закрыт в firewall | `sudo ufw allow 443/tcp` |
| Security Group облака блокирует 443 | Открыть 443 в консоли |
| Опечатка в `server_name` | Проверить домен в `nginx/nginx.conf` |
| Плейсхолдер `your-domain.com` не заменён | `grep -r "your-domain.com" nginx/` |

**Проверка SSL:**
```bash
openssl s_client -connect your-domain.com:443 -servername your-domain.com < /dev/null
```

Должно быть `Verify return code: 0 (ok)`.

---

### 134. `504 Gateway Timeout` при построении плана

**Симптом:** POST `/api/v1/schedule/build` возвращает 504 через 60 секунд.

**Причина:** дефолтный `proxy_read_timeout` в nginx — 60 секунд.

**Решение:**

**Шаг 1.** В `nginx/nginx.conf` для `location /api/`:
```nginx
proxy_read_timeout 900s;
proxy_send_timeout 900s;
```

**Шаг 2.** Перезапустить nginx:
```bash
docker compose -f docker-compose.prod.yml restart nginx
```

**Шаг 3.** Если не помогло — уменьшить `timeout_seconds`:

**UI:** Настройки → Таймаут solver → `300`.

**SQL:**
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "
UPDATE app_settings
SET setting_value = '300'::jsonb
WHERE setting_key = 'timeout_seconds';
"
```

---

### 135. Логи Docker занимают весь диск

**Симптом:** `df -h` показывает 100% на `/var/lib/docker`.

**Причина:** без ограничения размера логи растут неограниченно.

**Решение:**

**Шаг 1.** Проверить текущий размер:
```bash
sudo du -sh /var/lib/docker/containers/*/*-json.log
```

**Шаг 2.** Очистить логи:
```bash
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

**Шаг 3.** Настроить ограничение в `docker-compose.prod.yml`:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

**Шаг 4.** Пересоздать контейнеры:
```bash
docker compose -f docker-compose.prod.yml up -d
```

---

### 136. `unsupported locale` при `psql`

**Симптом:** `WARNING: database "household" has a collation version mismatch`.

**Причина:** несовпадение локали хоста и контейнера.

**Решение:**

**Шаг 1.** Проверить кодировку:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household -c "SHOW lc_collate; SHOW server_encoding;"
```

**Ожидаемо:**
```
lc_collate   | C
server_encoding | UTF8
```

**Шаг 2.** Если не так — пересоздать БД (`deploy_init.sh` с
`init_schema_v4.9.sql`).

---

### 137. `docker compose build` падает на `ortools` (долго)

**Симптом:** при сборке backend `pip install ortools` занимает 5+ минут.

**Причина:** `ortools` — большой пакет (~150 MB).

**Решение:**

**Шаг 1.** Увеличить timeout:
```bash
docker compose -f docker-compose.prod.yml build backend
```

**Шаг 2.** Проверить интернет:
```bash
curl -I https://pypi.org/simple/ortools/
```

**Ожидаемое время:** первая сборка — 5–10 минут.

---

### 138. `Hot reload` не работает в Docker (ожидаемо)

**Симптом:** изменили код в `backend/app/`, но в контейнере — старая версия.

**Причина:** это **by design** для prod.

**Решение:**

**Шаг 1.** Пересобрать образ:
```bash
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

**Шаг 2.** Для dev — использовать dev-режим:
```bash
docker compose -f docker/docker-compose.yml up -d
cd backend && python run_server.py
```

---

### 139. Frontend отдаётся, но иконки/шрифты 404

**Симптом:** UI отображается, но иконки (MUI) не грузятся.

**Причина:** файлы не попали в финальный образ.

**Решение:**

**Шаг 1.** Проверить содержимое:
```bash
docker compose -f docker-compose.prod.yml exec frontend \
    ls /usr/share/nginx/html/assets/ | head -10
```

**Шаг 2.** Проверить `frontend/nginx.conf`:
```nginx
location /assets/ {
    try_files $uri =404;
}
```

**Шаг 3.** Пересобрать:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

---

### 140. Контейнер backend `restarting` в цикле

**Симптом:** `docker compose ps` показывает `aps_backend` в статусе
`Restarting (1) X seconds ago`.

**Причина:** приложение падает при старте.

**Решение:**

**Шаг 1.** Посмотреть логи:
```bash
docker compose -f docker-compose.prod.yml logs backend --tail=100
```

**Шаг 2.** Частые причины:

| Ошибка в логах | Причина | Решение |
|----------------|---------|---------|
| `ModuleNotFoundError: app` | Неправильный `WORKDIR` | Проверить `WORKDIR /app` |
| `pydantic_settings.errors.SettingsError` | Отсутствует env | Проверить `.env` |
| `asyncpg.exceptions.InvalidPasswordError` | Неверный пароль | Синхронизировать `.env` |
| `ImportError: snapshot` | Не применён `add_21.sql` | Применить миграции |
| `SECRET_KEY слишком короткий` | `SECRET_KEY` < 32 символов | `openssl rand -hex 32` |

**Шаг 3.** После исправления — перезапустить:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

---

### 141. Случайно удалили volume `pgdata`

**Симптом:** `docker volume rm household-aps_pgdata` → БД пуста.

**Решение:**

**Если есть бэкап:**
```bash
docker compose -f docker-compose.prod.yml up -d postgres
gunzip -c ~/backups/household_YYYYMMDD_HHMMSS.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household
```

**Если бэкапа нет:**
1. Восстановить структуру через `deploy_init.sh`.
2. Восстановить данные из других источников.

**Профилактика:**
- Cron-бэкап — **обязательно**.
- Не удалять volume'ы вручную.
- Не запускать `down -v`.

---

### 142. Долгий старт контейнеров (backoff)

**Симптом:** `up -d` запускает сервисы, но первые 30–60 секунд `/health`
возвращает 502.

**Причина:** PostgreSQL инициализируется, backend грузит OR-Tools.

**Решение:** это **нормально**. Подождать 30–60 секунд. В `backend` есть
`healthcheck` с `start_period: 60s`.

**Если 5+ минут** — проблема (см. другие пункты).

---

### 143. Бэкап не восстанавливается

**Симптом:** `pg_restore` или `psql < backup.sql` падает с
`ERROR: role "aps" does not exist`.

**Причина:** при восстановлении **в новую БД** — роли и БД ещё не созданы.

**Решение:**

**Шаг 1.** Создать пользователя и БД:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres -c "CREATE USER aps WITH PASSWORD 'aps_secret';"
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres -c "CREATE DATABASE household OWNER aps;"
```

**Шаг 2.** Применить бэкап:
```bash
gunzip -c backup.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U aps -d household
```

---

### 144. После `down -v` остались volume'ы БД

**Симптом:** сделали `docker compose down -v`, но `docker volume ls` показывает
`household-aps_pgdata`.

**Причина:** `-v` удаляет только volumes из **этого** compose-файла.

**Решение:**

**Шаг 1.** Посмотреть все volumes:
```bash
docker volume ls | grep pgdata
```

**Шаг 2.** Удалить ненужные:
```bash
docker volume rm household-aps_pgdata
docker volume rm docker_pgdata
```

---

### 145. Файлы `.env` случайно попали в git

**Симптом:** `git log --all --full-history -- .env` показывает коммиты
с реальным `SECRET_KEY`.

**Решение:**

**Шаг 1.** Удалить из истории:
```bash
git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch .env backend/.env" \
    --prune-empty --tag-name-filter cat -- --all
```

**Шаг 2.** Force push:
```bash
git push origin --force --all
```

**Шаг 3.** **Обязательно** сменить все утекшие секреты:
- `SECRET_KEY` — новый.
- `POSTGRES_PASSWORD` — новый.
- `CZ_API_KEY` — новый.

**Шаг 4.** Добавить в `.gitignore`:
```
.env
.env.local
backend/.env
```

---

### 146. Домен не резолвится / DNS не обновился

**Симптом:** `curl https://your-domain.com` → `Could not resolve host`.

**Причина:** DNS-запись ещё не обновилась, или не настроена.

**Решение:**

**Шаг 1.** Проверить DNS:
```bash
nslookup your-domain.com
```

**Шаг 2.** Настроить A-запись у DNS-провайдера:
- Type: `A`
- Name: `@`
- Value: IP сервера
- TTL: 300

**Шаг 3.** Дождаться обновления (5–30 минут при TTL 300).

**Пока DNS не работает** — использовать IP-адрес.

### 147. Frontend стучится на `your-server-ip` (`ERR_NAME_NOT_RESOLVED`)

**Симптом:** страница логина открывается, но при попытке входа — «Ошибка авторизации». В DevTools → Console:

```
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
POST http://your-server-ip/api/v1/auth/login
```

Вместо `localhost:8080` или реального домена frontend стучится на **`your-server-ip`** — плейсхолдер из `.env.example`.

**Причина:** `VITE_API_URL` в `.env` **не заменён** с плейсхолдера `http://your-server-ip` на реальный адрес.

**Почему это критично:** Vite **вшивает** `VITE_API_URL` в JS-бандл **на этапе сборки** (`docker compose build frontend`). После сборки значение **нельзя изменить** без пересборки.

**Решение:**

**Шаг 1. Проверить `.env`:**

```bash
cd ~/household-aps
grep VITE_API_URL .env
```

Если видишь `VITE_API_URL=http://your-server-ip` — **подтверждено**.

**Шаг 2. Заменить значение:**

Для локальной VM (VirtualBox):
```bash
sed -i 's|^VITE_API_URL=.*|VITE_API_URL=http://localhost:8080|' .env
```

Для облака по IP:
```bash
sed -i 's|^VITE_API_URL=.*|VITE_API_URL=http://YOUR-IP|' .env
```

Для облака по домену:
```bash
sed -i 's|^VITE_API_URL=.*|VITE_API_URL=https://your-domain.com|' .env
```

**Шаг 3. Проверить `ALLOWED_ORIGINS`** (заодно):

```bash
sed -i 's|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=http://localhost:8080,http://localhost|' .env
```

**Шаг 4. Пересобрать frontend** (обязательно!):

```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

**Шаг 5. Перезапустить backend** (для новых CORS):

```bash
docker compose -f docker-compose.prod.yml restart backend
```

**Шаг 6. Проверить, что URL вшит правильно:**

```bash
docker compose -f docker-compose.prod.yml exec frontend \
    grep -r "localhost:8080" /usr/share/nginx/html/assets/ | head -2
```

Ожидаемо: найдено совпадение в `index-xxx.js`.

**Шаг 7. Hard reload в браузере:**

`Ctrl+Shift+R` — очистить кэш. Открыть `http://localhost:8080/login`, войти.

**Профилактика:**

С 2026-10-09 в `frontend/src/config.ts` добавлена **защита** — если `VITE_API_URL` содержит плейсхолдер или пустой, используется fallback `http://localhost:8080`. **Но для облака** всё равно нужно явно задать правильный URL.

**Связанные статьи:**

- [docs/DEPLOYMENT.md](DEPLOYMENT.md) — Шаг 6.1 «Проверка критичных переменных».
- Пункт 130 (VITE_API_URL изменили, но frontend не обновился).

### 148. Оборудование не грузится, 307 redirect без порта

**Симптом:** UI открывается, логин проходит, но страница `/equipment` пуста — «Нет данных для отображения», «Ошибка загрузки оборудования». В DevTools → Network:

```
GET /api/v1/equipment → 307 Temporary Redirect
location: http://localhost/api/v1/equipment/    ← без порта :8080!
```

Браузер следует редиректу на `http://localhost/api/v1/equipment/` — а там ничего нет.

**Причина:** в `nginx/nginx.conf` установлен `proxy_set_header Host $host;` — **без порта**. Когда backend отвечает 307 (redirect на trailing slash), nginx формирует `Location` через `$host`, теряя `:8080`.

**Решение:**

**Шаг 1. Заменить все `$host` на `$http_host` в `nginx/nginx.conf`:**

```bash
cd ~/household-aps
sed -i 's|proxy_set_header Host \$host;|proxy_set_header Host $http_host;|g' nginx/nginx.conf
```

**Шаг 2. Проверить замену:**

```bash
grep -n "proxy_set_header Host" nginx/nginx.conf
```

Ожидаемо: все активные вхождения содержат `$http_host`, ни одной `$host`.

**Шаг 3. Перезапустить nginx:**

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

**Шаг 4. Проверить через curl** (в PowerShell):

```powershell
curl.exe -i http://localhost:8080/api/v1/equipment
```

Ожидаемо:
```
HTTP/1.1 401 Unauthorized     ← уже не 307
location: (нет)
```

Или — если `Location` есть:
```
location: http://localhost:8080/api/v1/equipment/   ← с портом
```

**Шаг 5. Hard reload в браузере:**

`Ctrl+Shift+R`, открыть `/equipment`. Должны загрузиться **10 записей оборудования**.

**Почему это работает:**

`$http_host` — переменная nginx, которая содержит `Host` **с портом** (то, что прислал клиент). `$host` — только домен, без порта. Для reverse-proxy на нестандартном порту (8080 → 80) обязательно использовать `$http_host`.

**Профилактика:**

С 2026-10-09 в `nginx/nginx.conf` **все** `proxy_set_header Host $host;` заменены на `$http_host` по умолчанию.

**Связанные статьи:**

- Пункт 131 (502 Bad Gateway — похожая проблема с Host).
- Пункт 132 (SPA-роуты 404 — проблема nginx без порта).

---

## Диагностика

### 149.Общая проверка системы

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

# Туториал
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT COUNT(*) AS tutorial_articles FROM help_article WHERE slug = 'tutorial-interactive';
"

# Сохранённые представления аудита
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

### 150.Полная очистка и пересоздание

**Dev** (PostgreSQL в Docker):

```bash
# 1. Снести контейнер
docker rm -f aps_postgres

# 2. Создать заново
docker run --name aps_postgres \
  -e POSTGRES_USER=aps \
  -e POSTGRES_PASSWORD=aps_secret \
  -e POSTGRES_DB=household \
  -p 5432:5432 \
  -d postgres:17

# 3. Применить схему v4.9.0
docker cp backend/init_schema_v4.9.sql aps_postgres:/tmp/init_schema_v4.9.sql
docker cp backend/init_schema_v4.9_seed.sql aps_postgres:/tmp/init_schema_v4.9_seed.sql
docker cp backend/seed_demo_data.sql aps_postgres:/tmp/seed_demo_data.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema_v4.9_seed.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/seed_demo_data.sql

# 4. Создать админа
cd backend
python -m scripts.create_admin_user

# 5. Запустить backend и frontend
python run_server.py
cd ../frontend; npm run dev
```

**Prod** (полный стек):

```bash
# 1. Остановить (БЕЗ -v!)
docker compose -f docker-compose.prod.yml down

# 2. Если нужно — удалить volume (⚠️ потеря данных)
# docker volume rm household-aps_pgdata

# 3. Запустить заново
docker compose -f docker-compose.prod.yml up -d

# 4. Инициализировать БД
./scripts/deploy_init.sh    # или .ps1
```

---

### 151. Полезные ссылки

- [README.md](../README.md) — основная документация.
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание в облаке.
- [docs/DOCKER.md](DOCKER.md) — Docker: устройство и отладка.
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