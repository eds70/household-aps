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
- [Снапшоты справочников (13.15)](#снапшоты-справочников-1315)
- [Честный Знак](#честный-знак)
- [Лаборатория](#лаборатория)
- [Смены](#смены)
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

### 7. `ModuleNotFoundError` при запуске

**Симптом:** `ModuleNotFoundError: No module named 'app'`.

**Причина:** запуск не из корня `backend/`.

**Решение:** перейти в `backend/`:

```bash
cd backend
python run_server.py
```

---

### 8. `ImportError` после добавления нового модуля

**Симптом:** `ImportError: cannot import name ...`.

**Причина:** кэш Python или неверный путь импорта.

**Решение:**

1. Очистить `__pycache__` (см. пункт 2).
2. Проверить `__init__.py` в директории.
3. Перезапустить сервер.

---

### 9. Backend не стартует: `Address already in use`

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

### 10. JWT-токен истёк

**Симптом:** `401 Unauthorized` после некоторого времени работы.

**Причина:** `JWT_EXPIRES_MINUTES` (по умолчанию 60).

**Решение:** войти заново или увеличить `JWT_EXPIRES_MINUTES` в `.env`.

---

### 11. `snapshot.py` не импортируется (Итерация 13.15)

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

### 12. `snapshot_all_catalogs` падает с `UndefinedColumnError`

**Симптом:** при создании плана или расчёте — ошибка типа `column operation_template.operator_pool does not exist`.

**Причина:** не применена миграция `add_09.sql`, но `snapshot.py` пытается вставить `operator_pool` в `operation_snapshot`.

**Решение:** модуль `snapshot.py` содержит graceful-обработку — проверяет наличие колонки `operator_pool` через `_has_column`. Если ошибка всё же возникает — примените миграцию:

```bash
docker cp backend/migrations/add_09.sql aps_postgres:/tmp/add_09.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09.sql
```

---

## Frontend

### 13. `usePlan must be used within PlanProvider`

**Симптом:** ошибка `usePlan must be used within PlanProvider`.

**Причина:** кэш Vite.

**Решение:** перезапустить Vite с очисткой кэша:

```bash
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

---

### 14. Advisor «дёргается» (бесконечный ре-рендер)

**Симптом:** панель Advisor постоянно перезагружается, в консоли — бесконечные запросы.

**Причина:** функции в `PlanContext.tsx` не обёрнуты в `useCallback`, из-за чего `useEffect` в потребителях перезапускается.

**Решение:** в `PlanContext.tsx` обернуть функции в `useCallback`:

```tsx
const loadVersions = useCallback(async () => {
   // ...
}, [isAuthenticated, isLoading]);

const setPlan = useCallback((plan: Plan | null) => {
   // ...
}, []);

const createPlan = useCallback(async (name: string) => {
   // ...
}, []);

const deletePlan = useCallback(async (id: string) => {
   // ...
}, []);
```

Также `loadVersions` вызывается **только после аутентификации**:

```tsx
useEffect(() => {
   if (isAuthenticated && !isLoading) {
      loadVersions();
   }
}, [isAuthenticated, isLoading, loadVersions]);
```

---

### 15. `401 Unauthorized` при первом заходе на `/login`

**Симптом:** при открытии `/login` в консоли — `401 Unauthorized`.

**Причина:** `loadVersions` вызывается до аутентификации.

**Решение:** см. пункт 14 — вызывать `loadVersions` только после аутентификации.

---

### 16. Диаграмма Ганта: pan не работает

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

### 17. Диаграмма Ганта: задачи не таскаются

**Симптом:** drag-and-drop не работает.

**Причина:** `editable.updateTime` возвращает `false` для всех задач, или `moveable: true` перехватывает drag.

**Решение:** см. пункт 16. `updateTime` должен быть **функцией**, возвращающей `true` для реальных задач и `false` для setup/downtime.

---

### 18. Мастер смены: шапка «уезжает» вверх

**Симптом:** при большом количестве задач шапка (заголовок, селектор смены, кнопки) уходит вверх при скролле.

**Причина:** нет фиксированной шапки.

**Решение:** в `ShiftPage.tsx`:

```tsx
<Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
   {/* Фиксированная шапка */}
   <Box sx={{ flexShrink: 0 }}>
      {/* Заголовок, селектор смены, кнопки */}
   </Box>

   {/* Скроллируемый список задач */}
   <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>
      {/* Список задач */}
   </Box>
</Box>
```

---

### 19. `npm install` падает с ошибкой

**Симптом:** `npm install` завершается с ошибкой.

**Причина:** кэш npm или несовместимость версий.

**Решение:**

```bash
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm cache clean --force
npm install
```

---

### 20. Frontend не видит backend

**Симптом:** запросы к API падают с `Network Error`.

**Причина:** backend не запущен или CORS.

**Решение:**

1. Проверить, что backend запущен: `curl http://localhost:8000/docs`.
2. Проверить `CORS_ORIGINS` в `.env`.
3. Проверить `vite.config.ts` (proxy).

---

### 21. План в списке помечен ⚠ (Итерация 13.15)

**Симптом:** рядом с планом в «Истории планов» жёлтая иконка ⚠.

**Причина:** `has_snapshot = false` — снапшоты справочников для этого плана не заполнены.

**Решение:** см. пункт 30 (в разделе «Снапшоты справочников»).

---

### 22. GanttPage показывает «План пуст» вместо диаграммы (Итерация 13.15)

**Симптом:** при открытии плана вместо диаграммы Ганта — предупреждение «План пуст».

**Причина:** `currentPlanHasSnapshot === false` в `PlanContext`. План создан до Итерации 13.15, снапшоты не заполнены.

**Решение:** см. пункт 30 (в разделе «Снапшоты справочников»).

---

## База данных

### 23. `psql: FATAL: database "household" does not exist`

**Симптом:** не удаётся подключиться к БД.

**Причина:** БД не создана.

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

### 24. Кириллица отображается как «кракозябры»

**Симптом:** русские буквы в БД выглядят как `????` или `ÐŸÑ€Ð¸Ð²ÐµÑ‚`.

**Причина:** применение SQL-файла через `Get-Content | docker exec` — PowerShell портит кодировку.

**Решение:** применять через `docker cp` + `psql -f`:

```bash
docker cp backend/init_schema.sql aps_postgres:/tmp/init_schema.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/init_schema.sql
```

---

### 25. `relation "..." does not exist`

**Симптом:** `relation "plan_settings" does not exist`.

**Причина:** не применена миграция.

**Решение:** см. пункт 5. Применить нужную миграцию.

---

### 26. `duplicate key value violates unique constraint`

**Симптом:** при вставке — `duplicate key value violates unique constraint`.

**Причина:** нарушение UNIQUE-констрейнта.

**Решение:** зависит от констрейнта:

| Констрейнт | Причина | Решение |
|------------|---------|---------|
| `plan_settings (schedule_version_id, setting_key)` | Дубль настройки | `ON CONFLICT DO NOTHING` |
| `resource_pool (organization_id, type)` | Дубль пула | Удалить старый или обновить |
| `cz_scan_log (organization_id, cz_code)` | Повторный скан | Идемпотентно, `duplicate: true` |
| `equipment_snapshot (id, version_id)` | Дубль снапшота | `ON CONFLICT DO NOTHING` (by design) |

---

### 27. PostgreSQL не стартует

**Симптом:** `docker ps` не показывает `aps_postgres`.

**Причина:** контейнер упал или не создан.

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

### 28. Долгий запрос блокирует БД

**Симптом:** запросы висят, БД не отвечает.

**Причина:** долгий запрос (например, от solver).

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

### 29. Solver выдаёт `FEASIBLE` вместо `OPTIMAL`

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

### 30. Solver не находит решение (`INFEASIBLE`)

**Симптом:** `status: "INFEASIBLE"`.

**Причина:** противоречивые ограничения.

**Решение:**

1. Проверить Advisor: `GET /api/v1/schedule/advice`.
2. Проверить заказы и доступность оборудования.
3. Проверить календарь простоев.
4. Уменьшить `horizon_hours`.
5. Проверить, нет ли заблокированных партий, которые нельзя запланировать.

---

### 31. Solver работает слишком долго

**Симптом:** расчёт занимает >10 минут.

**Причина:** большой горизонт, много задач.

**Решение:**

1. Уменьшить `horizon_hours` (например, до 720).
2. Уменьшить `timeout_seconds` (например, до 600).
3. Упростить задачу (убрать лишние заказы).

---

### 32. `overlaps_after > 0` после постобработки

**Симптом:** после `calendar_postprocess` остаются пересечения.

**Причина:** баг в постпроцессоре или неправильные зависимости.

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

### 33. `dependency_violations > 0`

**Симптом:** после постобработки есть нарушения зависимостей.

**Причина:** баг в топологической сортировке.

**Решение:** пересчитать план. Если повторяется — сообщить о баге.

---

## What-if

### 34. Сценарий завис в статусе `RUNNING`

**Симптом:** сценарий не завершается.

**Причина:** solver работает долго или упал.

**Решение:**

1. Подождать (solver может работать до 10 минут).
2. Проверить логи backend.
3. Удалить сценарий (если не удаляется — см. пункт 35).

---

### 35. Не удаётся удалить сценарий

**Симптом:** `DELETE /api/v1/whatif/scenarios/{id}` возвращает ошибку.

**Причина:** сценарий в статусе `RUNNING` — удаление запрещено.

**Решение:** дождаться завершения (`DONE`/`FAILED`) или убить процесс solver.

---

### 36. What-if не откатывает изменения

**Симптом:** после what-if изменения в БД остались.

**Причина:** баг в 2-транзакционной архитектуре.

**Решение:**

1. Проверить, что `ProductionScheduler` получает `session` извне.
2. Проверить, что `ScheduleSaver` не делает commit при `_owns_session=False`.
3. Перезапустить backend.

---

### 37. What-if: `500 Internal Server Error`

**Симптом:** `POST /run` возвращает 500.

**Причина:** ошибка в `_apply_changes`.

**Решение:**

1. Проверить логи backend.
2. Проверить формат `changes` (JSON).
3. Убедиться, что `base_version_id` существует.

---

## plan_settings

### 38. Таблица `plan_settings` пуста

**Симптом:** `SELECT COUNT(*) FROM plan_settings` возвращает 0.

**Причина:** не применена миграция `add_21.sql`.

**Решение:**

```bash
docker cp backend/migrations/add_21.sql aps_postgres:/tmp/add_21.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_21.sql
```

---

### 39. Триггер `copy_app_settings_to_plan` не срабатывает

**Симптом:** создали план, но `plan_settings` пуст.

**Причина:** триггер не создан на таблице `schedule_version`.

**Решение:** проверить наличие:

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT tgname FROM pg_trigger WHERE tgname = 'trg_copy_app_settings_to_plan';
"
```

Если пусто — пересоздать миграцию `add_21.sql`.

---

### 40. `404 Not Found` при `GET /api/v1/plan-settings/version/{id}`

**Симптом:** эндпоинт не найден.

**Причина:** не подключён в `main.py`.

**Решение:** см. пункт 6.

---

### 41. Мастер настроек показывает пустой список полей

**Симптом:** `PlanSettingsWizard` не отображает настройки.

**Причина:** `settingsApi.getSchema()` вернул пустой `settings`.

**Решение:** проверить `SETTINGS_REGISTRY` в `backend/app/scheduler/settings.py` — там должно быть 30+ записей.

---

### 42. В мастере настроек отсутствует кнопка «Сохранить»

**Симптом:** кнопка «Сохранить» неактивна.

**Причина:** `changedKeys.length === 0` — нет изменений.

**Решение:** это by design. Измените любое поле — кнопка активируется.

---

### 43. `plan_settings` не обновляются при изменении `app_settings`

**Симптом:** изменили `app_settings`, но `plan_settings` плана не изменились.

**Причина:** это by design (снапшот).

**Решение:** сбросить `plan_settings` к глобальным:

```bash
curl -X POST http://localhost:8000/api/v1/plan-settings/version/$VERSION_ID/reset \
  -H "Authorization: Bearer $TOKEN"
```

---

### 44. Существующие планы не имеют `plan_settings`

**Симптом:** для старых планов `plan_settings` пуст.

**Причина:** планы созданы до миграции `add_21.sql`.

**Решение:** либо сбросить к глобальным (см. пункт 43), либо создать новый план.

---

## Снапшоты справочников (13.15)

### 45. План открыт, но все справочники пусты

**Симптом:** открыли план из списка, но на страницах «Продукты», «Оборудование», «Техкарты» гриды пусты.

**Причина:** план создан до Итерации 13.15 (или до того, как появился фикс) — снапшоты не заполнялись. UI переключился в readonly-режим и читает из пустых снапшот-таблиц.

**Решение:**

1. Закройте план (кнопка ✕ в списке планов или в `MainLayout`).
2. Удалите его через UI (кнопка 🗑 в строке плана).
3. Создайте новый план через мастер (`Новый план`) — снапшоты заполнятся автоматически.

**Проверка:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment,
    (SELECT COUNT(*) FROM operation_snapshot WHERE version_id = sv.id) AS ops,
    (SELECT COUNT(*) FROM calendar_snapshot WHERE version_id = sv.id) AS cal
FROM schedule_version sv
ORDER BY sv.created_at DESC LIMIT 5;
"
```

Если у плана `products = 0` — снапшоты не заполнены.

---

### 46. Список планов показывает ⚠ рядом с некоторыми планами

**Симптом:** в «Истории планов» рядом с некоторыми планами — жёлтая иконка ⚠.

**Причина:** `has_snapshot = false` — снапшоты справочников не заполнены.

**Решение:** тот же, что в пункте 45.

---

### 47. `GanttPage` показывает «План пуст» вместо диаграммы

**Симптом:** при открытии плана вместо диаграммы Ганта — предупреждение «План пуст».

**Причина:** `currentPlanHasSnapshot === false` в `PlanContext`. План создан до Итерации 13.15.

**Решение:** тот же, что в пункте 45.

---

### 48. `POST /schedule/versions` создаёт план, но снапшоты пусты

**Симптом:** создали план через API, но `snapshot_stats` показывает нули или снапшоты не заполнились.

**Причина:** возможные причины:
1. Не перезапущен backend после обновления кода.
2. Импорт `snapshot_all_catalogs` в `schedule.py` не сработал.
3. Откатилась транзакция (например, ошибка в середине).

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

### 49. Старые планы не открываются, но и не удаляются

**Симптом:** план без снапшотов нельзя открыть нормально, и удалить не получается.

**Причина:** возможно, план активен (`is_active = true`) — тогда UI может вести себя странно.

**Решение:**

1. Проверить статус:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   SELECT id, name, is_active FROM schedule_version
   WHERE name = 'z1';
   "
   ```
2. Если активен — деактивировать вручную:
   ```bash
   docker exec -i aps_postgres psql -U aps -d household -c "
   UPDATE schedule_version SET is_active = FALSE WHERE name = 'z1';
   "
   ```
3. Затем удалить через UI.

---

### 50. Удалить все пустые планы одной командой

**Симптом:** накопилось много планов без снапшотов, вручную удалять долго.

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

Безопасно — удаляются только планы без снапшотов.

---

## Честный Знак

### 51. Скан не привязывается к партии

**Симптом:** скан попадает в «сироты» (`batch_id = NULL`).

**Причина:** не сработало fallback-сопоставление.

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

### 52. Дубликаты сканов

**Симптом:** `duplicate: true` в ответе.

**Причина:** идемпотентность по `cz_code`.

**Решение:** это by design. Повторный скан не увеличивает `cz_marked_qty`.

---

### 53. `cz_status` не обновляется

**Симптом:** после сканов `cz_status` остаётся `PENDING`.

**Причина:** не достигнут порог `cz_completion_threshold`.

**Решение:** проверить `cz_marked_qty` и `planned_qty`. Порог по умолчанию — 0.95.

---

### 54. `CZ_INCOMPLETE` в Advisor, но маркировка завершена

**Симптом:** Advisor выдаёт `CZ_INCOMPLETE`, хотя `cz_status = COMPLETED`.

**Причина:** кэш Advisor.

**Решение:** перезагрузить страницу или пересчитать план.

---

## Лаборатория

### 55. Заблокированная партия всё равно в плане

**Симптом:** партия с `is_lab_blocked = true` есть в расписании.

**Причина:** план не пересчитан после блокировки.

**Решение:** запустить перепланирование:

```bash
curl -X POST http://localhost:8000/api/v1/schedule/reschedule \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_version_id": "uuid", "change_type": "MANUAL", "change_data": {}}'
```

---

### 56. `LAB` не может заблокировать партию

**Симптом:** `403 Forbidden`.

**Причина:** у роли `LAB` нет прав.

**Решение:** блокировать могут `LAB`, `MASTER`, `ADMIN`. Проверить роль пользователя.

---

### 57. После разблокировки партия не появляется в плане

**Симптом:** разблокировали партию, но она не в расписании.

**Причина:** план не пересчитан.

**Решение:** см. пункт 55.

---

## Смены

### 58. При смене `shift_mode` задачи теряют привязку

**Симптом:** после `POST /api/v1/settings/shift-mode` у задач `shift_id = NULL`.

**Причина:** это by design — старые UUID смен невалидны.

**Решение:** пересчитать план.

---

### 59. `by-date` не находит смену

**Симптом:** `GET /api/v1/shift/by-date/2026-09-01` возвращает пусто.

**Причина:** таймзона.

**Решение:** сравнение по МСК-дате (см. пункт 4).

---

### 60. Смены не созданы

**Симптом:** таблица `shift` пуста.

**Причина:** не выполнен `regenerate_shifts`.

**Решение:** сменить режим смен:

```bash
curl -X POST http://localhost:8000/api/v1/settings/shift-mode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "1x8"}'
```

---

## Диагностика

### 61. Общая проверка системы

```bash
# PostgreSQL
docker ps --filter "name=aps_postgres"

# Backend
curl http://localhost:8000/docs

# Frontend
curl http://localhost:5173

# Активная версия
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT id, name, is_active FROM schedule_version
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

# Снапшоты активного плана (13.15)
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

### 62. Полная очистка и пересоздание

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
                "add_21.sql", "fix_shift_names.sql")
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

### 63. Полезные ссылки

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