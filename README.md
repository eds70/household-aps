## ⚠️ Известные ограничения

1. **Слив на линию** добавляется в конец цепочки (после замыва). Семантически неверно (по ТЗ замыв после слива), но структурно работает: NoOverlap не даёт им пересечься.

2. **Материальные ограничения** — предупреждения Advisor, не жёсткие constraints в CP-SAT.

3. **График поставок** — все поставки считаются доступными (без учёта `expected_at` vs дата старта партии).

4. **Крем-мыло 5л (Р2)** имеет `route_type=VIA_TANK`, но Р2 не связан с танком. Advisor подсвечивает это как ROUTE_MISMATCH.

5. **Лабораторные блокировки:** после блокировки партии нужно **вручную запустить перепланирование** (`POST /api/v1/schedule/reschedule`) — автоматическое не реализовано.

6. **Персонал:** на Итерации 6 нет HR-подсистемы (нет ФИО, смен, отпусков). Только пулы с capacity.

7. **Solver:** при большом горизонте и множестве `AddCumulative` + модель деградации охлаждения (O(N²) bool-переменных) solver может не успеть найти OPTIMAL за отведённое время — выдаёт FEASIBLE. На тестовом кейсе ТЗ — OPTIMAL за 78 сек.

8. **Деградация охлаждения (Итерация 7)** активна, но в тестовом кейсе ТЗ `slow` не появляется — узкие места в других ресурсах (линии, аппаратчики, единственный tank). Чтобы увидеть `slow` в UI — уменьшите `cooling_degradation_factor` до 1.05 или разгрузите Line 1.

9. **ЧЗ (Итерация 8):** формат данных от камер — **гибкий JSON** с опциональными `batch_id`/`task_id`/`line_code`. Реальный формат камер ТС будет уточнён; текущая модель — задел на будущее.

10. **ЧЗ:** `enable_cz_auto_close = false` — закрытие задачи слива при завершении маркировки отключено. Включается через `app_settings`.

11. **ЧЗ:** ручное сопоставление сироты требует ввода UUID партии — UI подсказки/автоподбора по продукту не реализовано.

12. **Режимы смен (Итерация 11):** при смене `shift_mode` через `/api/v1/settings/shift-mode` **все задачи теряют привязку к сменам** (`shift_id = NULL`). Требуется пересчитать план.

13. **Разбиение LINE_FILL (Итерация 10):** длинные задачи (например, слив 7000 кг крем-мыла 5л = 7000 минут) разбиваются на **много подзадач** (для `3x8` — до 20 частей). Это увеличивает общее число задач в плане.

14. **Pan + drag на Ганте:** setup и downtime не таскаются (только pan). Это by design — они генерируются автоматически и не должны менять положение вручную.

## 🐛 Troubleshooting

### 1. FastAPI 0.139+: `_IncludedRouter` в `app.routes`

**Симптом:** скрипт проверки `getattr(r, 'path', None)` возвращает `None` для всех `include_router(...)`.

**Решение:** проверять через `app.openapi()['paths']`:

```python
from app.main import app
paths = sorted(app.openapi()['paths'].keys())
print([p for p in paths if '/shift' in p])
```

### 2. Кэш Python (`__pycache__`) на Windows

**Симптом:** после правки `main.py` изменений не видно.

**Решение:** удалить `__pycache__` в проекте:

```
cd backend
Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

### 3. Кэш браузера — Swagger/UI показывает старое

**Решение:**
1. Открыть в **режиме инкогнито** (Ctrl+Shift+N).
2. Или **Ctrl+Shift+Delete** → очистить кэш.
3. В крайнем случае — **перезагрузить компьютер**.

### 4. Таймзона naive datetime в asyncpg

**Симптом:** `GET /api/v1/shift/by-date/2026-09-01` возвращает 404.

**Решение:** сравнение по **МСК-дате** (Итерация 11):

```sql
WHERE (starts_at AT TIME ZONE 'Europe/Moscow')::date = :shift_date
```

### 5. `UndefinedColumnError: column "updated_at" does not exist`

**Симптом:** `GET /api/v1/personnel/pools` возвращает 500.

**Причина:** не применена миграция `add_09c.sql`.

**Решение:**

```
docker cp backend\migrations\add_09c.sql aps_postgres:/tmp/add_09c.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09c.sql
```

### 6. `UndefinedColumnError: column "operator_pool" does not exist`

**Симптом:** `GET /api/v1/personnel/pools` возвращает 500.

**Причина:** не применена миграция `add_09d.sql`.

**Решение:**

```
docker cp backend\migrations\add_09d.sql aps_postgres:/tmp/add_09d.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_09d.sql
```

### 7. `UndefinedColumnError: column "cooling_mode" does not exist`

**Симптом:** `GET /api/v1/gantt/` возвращает 500.

**Причина:** не применена миграция `add_10b.sql` (Итерация 7).

**Решение:**

```
docker cp backend\migrations\add_10b.sql aps_postgres:/tmp/add_10b.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_10b.sql
```

### 8. Все охлаждения помечены `slow`, хотя идут последовательно

**Симптом:** на диаграмме Ганта много оранжевых пунктирных задач с иконкой ⏳, но по времени они не пересекаются.

**Причина:** не применён hotfix Итерации 7 (модель `b_slow ⟺ пересечение` не активна).

**Решение:** убедиться, что в `core.py` вызывается `_apply_cooling_degradation_model`, а в `plugins.py` убран `AddNoOverlap(fast_intervals)` из `CoolingDegradationConstraint`. Проверить логи backend:

```
[scheduler] [INFO] [stage=build] Итерация 7 (fix): применяем модель деградации для N cooling-задач
```

### 9. `UndefinedColumnError: column "cz_status" does not exist`

**Симптом:** `GET /api/v1/cz/stats` возвращает 500; при этом `/api/v1/gantt/` тоже падает.

**Причина:** не применена миграция `add_11.sql` (Итерация 8).

**Решение:**

```
docker cp backend\migrations\add_11.sql aps_postgres:/tmp/add_11.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_11.sql
```

### 10. `401 Unauthorized` при отправке скана ЧЗ

**Симптом:** `POST /api/v1/cz/scan` возвращает 401 с текстом «Неверный или отсутствующий X-CZ-Api-Key».

**Причина:** неверный или отсутствующий заголовок `X-CZ-Api-Key`.

**Решение:** проверить ключ в БД:

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_value FROM app_settings WHERE setting_key = 'cz_api_key';"
```

Значение по умолчанию: `dev-cz-api-key-change-in-production` (без внешних кавычек при отправке в заголовке).

### 11. `400 Интеграция с ЧЗ отключена`

**Симптом:** любой эндпоинт `/api/v1/cz/*` возвращает 400 с текстом «Интеграция с ЧЗ отключена (enable_cz_integration = false)».

**Причина:** `enable_cz_integration = false` в `app_settings`.

**Решение:**

```
docker exec -i aps_postgres psql -U aps -d household -c "UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'enable_cz_integration';"
```

### 12. Скан ЧЗ не сопоставляется с партией («сирота»)

**Симптом:** `POST /api/v1/cz/scan` возвращает `resolved: false`, `batch_id: null`.

**Возможные причины:**
1. Камера не передала `batch_id`/`task_id`, а `line_code` не совпадает с `equipment.code` в БД.
2. На линии нет активной `LINE_FILL` задачи в окне ±2 часа от `scanned_at`.
3. Время скана сильно отличается от планового (`planned_start`/`planned_end`).

**Решение:**
- Проверить журнал сканов на странице **«Честный Знак»** → фильтр «Только сироты».
- Сопоставить вручную через иконку «?» в строке скана (роли `MASTER`/`PLANNER`/`ADMIN`).

### 13. `app_settings` пустой (нет настроек)

**Симптом:** `GET /api/v1/settings/` возвращает пустой объект или ошибку.

**Причина:** не применена миграция `add_13.sql` (Итерация 11).

**Решение:**

```
docker cp backend\migrations\add_13.sql aps_postgres:/tmp/add_13.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_13.sql
```

**Проверка:**

```
docker exec -i aps_postgres psql -U aps -d household -c "SELECT COUNT(*) FROM app_settings WHERE organization_id = '00000000-0000-0000-0000-000000000001';"
```

Ожидаемо: **> 20** строк.

### 14. `UndefinedColumnError: column "operation_name" does not exist`

**Симптом:** `GET /api/v1/gantt/` возвращает 500, если запрашивается `operation_name`.

**Причина:** не применена миграция `add_12.sql` (Итерация 10).

**Решение:**

```
docker cp backend\migrations\add_12.sql aps_postgres:/tmp/add_12.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_12.sql
```

### 15. `allow_weekend_work` отсутствует в настройках

**Симптом:** `POST /api/v1/settings/shift-mode` работает, но в UI настройки «Работа в выходные» нет.

**Причина:** не применена миграция `add_14.sql` (Итерация 11).

**Решение:**

```
docker cp backend\migrations\add_14.sql aps_postgres:/tmp/add_14.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_14.sql
```

### 16. `usePlan must be used within PlanProvider` (frontend)

**Симптом:** в консоли браузера ошибка `Uncaught Error: usePlan must be used within PlanProvider` на странице `/schedule` или других.

**Причина:** `PlanProvider` не обёрнут вокруг `AppRoutes`, либо **HMR** сохранил старый модуль `PlainContext.tsx` в кэше Vite.

**Решение:**
1. Проверить `frontend/src/App.tsx` — порядок:
   ```tsx
   <AuthProvider>
       <PlanProvider>
           <BrowserRouter>
               <AppRoutes />
           </BrowserRouter>
       </PlanProvider>
   </AuthProvider>
   ```
2. Если порядок правильный — **перезапустить Vite с очисткой кэша**:
   ```powershell
   cd frontend
   # Ctrl+C — остановить dev server
   Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue
   npm run dev
   ```
3. Жёсткая перезагрузка браузера: **Ctrl+Shift+R**.

### 17. Advisor «дёргается» (бесконечный ре-рендер)

**Симптом:** панель Advisor мигает: `loading` → данные → `loading` → данные → ...

**Причина:** `loadVersions` из `PlainContext` не обёрнут в `useCallback` — при каждом ре-рендере `PlanProvider` создаётся новая ссылка на функцию, `useEffect` в `SchedulePage` перезапускается.

**Решение:** в `frontend/src/context/PlainContext.tsx` обернуть `loadVersions`, `setPlan`, `createPlan`, `deletePlan` в `useCallback`. Также вызывать `loadVersions` только после аутентификации:

```tsx
useEffect(() => {
    if (!isLoading && isAuthenticated) {
        loadVersions();
    }
}, [isLoading, isAuthenticated, loadVersions]);
```

### 18. `TS2322: Type '(item: any) => boolean' is not assignable to type 'boolean | undefined'`

**Симптом:** TypeScript ругается на строку в `GanttPage.tsx`, где `editable.updateTime` задан функцией.

**Причина:** типы `vis-timeline` объявляют `updateTime?: boolean`, хотя в рантайме библиотека поддерживает функцию.

**Решение:** привести тип через `as any`:

```tsx
editable: {
    add: false,
    updateTime: ((item: any) => {
        // ...
    }) as any,
    updateGroup: false,
    remove: false,
} as any,
```

### 19. Pan в Ганте не работает (диаграмма не таскается)

**Симптом:** клик на пустом месте + drag — ничего не происходит.

**Причина:** `moveable: false` в `GanttPage.tsx` (осталось с Итерации 9).

**Решение:** убедиться, что в `options` установлено:
```tsx
moveable: true,
zoomable: true,
```

### 20. Zoom колёсиком в Ганте не работает

**Симптом:** крутим колесо мыши на диаграмме — масштаб не меняется.

**Причина:** `zoomable: false` в `options`.

**Решение:** добавить `zoomable: true` в `options` в `GanttPage.tsx`.

### 21. Setup и downtime таскаются (не должны)

**Симптом:** при перетаскивании замывки или выходного — они перемещаются (что некорректно).

**Причина:** `editable.updateTime` не проверяет `item.id` — установлен в `true` (boolean), а не как функция.

**Решение:** использовать `editable.updateTime` как функцию:

```tsx
updateTime: ((item: any) => {
    const itemId = String(item?.id ?? '');
    if (itemId.startsWith('setup_') || itemId.startsWith('weekend_')) {
        return false;
    }
    return true;
}) as any,
```

## 🗺️ Roadmap

| # | Итерация | Длит. | Приоритет | Статус |
|---|----------|-------|-----------|--------|
| 0 | Подготовка | 4 дня | 🔥 | ✅ |
| 1 | Цепочки рабочих центров | 2 нед | 🔥🔥🔥 | ✅ |
| 2 | Материальные ограничения и Advisor | 2 нед | 🔥🔥🔥 | ✅ |
| 3 | Сменное планирование и РМ мастера | 2 нед | 🔥🔥🔥 | ✅ |
| 4 | Перепланирование | 2 нед | 🔥🔥🔥 | ✅ |
| 5 | Лаборатория и блокировки | 1.5 нед | 🔥🔥 | ✅ |
| 5h | Hotfix: версии + tz + Gantt | 2 дня | 🔥🔥🔥 | ✅ |
| 6 | Люди как ресурс | 2 нед | 🔥🔥 | ✅ |
| 7 | Охлаждение с деградацией | 1.5 нед | 🔥 | ✅ |
| 7h | Hotfix: модель деградации охлаждения | 2 дня | 🔥🔥🔥 | ✅ |
| 8 | ЧЗ и интеграции | 2 нед | 🔥 | ✅ |
| 9 | Рефакторинг, A3 (реальный пересчет), C2 (drag-and-drop) | 2 нед | 🟡 | ✅ |
| 10 | Календарная постобработка, разбиение длинных задач | 2 нед | 🟡 | ✅ |
| 11 | Режимы смен, `app_settings`, pan/zoom в Ганте | 2 нед | 🟡 | ✅ |
| 12 | Multi-objective и what-if | 2 нед | 🟡 | ⏳ |
| 13 | Встроенная справка пользователя | 1 нед | 🟡 | ⏳ |

## 📄 Лицензия

Внутренний проект.

---

**Итерации 0, 1, 2, 3, 4, 5, 5h, 6, 7, 7h, 8, 9, 10, 11 завершены.**

**Следующая — Итерация 12: Multi-objective и what-if (⏳).**