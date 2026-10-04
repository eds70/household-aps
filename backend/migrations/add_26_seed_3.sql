-- ==========================================
-- SEED 26/3: СПРАВКА — FAQ (ЛАБОРАТОРИЯ + ОСТАЛЬНОЕ)
-- ==========================================
-- 5 статей FAQ категории 'faq'.
-- Все — глобальные (organization_id = NULL).
--
-- Идемпотентна: ON CONFLICT (slug) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_article
(organization_id, slug, title, category, content_md, tags,
 display_order, is_published)
VALUES

-- ==========================================
-- 11. faq-lab-blocked-batch
-- ==========================================
(NULL,
 'faq-lab-blocked-batch',
 'Партия заблокирована лабораторией — как разблокировать?',
 'faq',
 $md$# Партия заблокирована лабораторией

**Категория:** FAQ

**Симптом:** На **Ганте** задача помечена красной рамкой **🔒**. В **Мастере смены** — фон розовый, кнопки «Отметить выполнение» отключены. Advisor показывает `LAB_BLOCKED`.

 ## Что значит «заблокирована»

 `batch.is_lab_blocked = TRUE` — партия **исключена из планирования**. Solver её **не учитывает** при построении плана. Задачи партии видны, но не двигаются.

## Кто может разблокировать

- **LAB** (лаборант)
- **MASTER** (мастер смены)
- **ADMIN**

Другие роли получат `403 Forbidden`.

## Как разблокировать через UI

### Способ 1: Мастер смены

1. Открыть **Мастер смены**.
2. Найти задачу с 🔒.
3. Кликнуть иконку **🔓** (Разблокировать).
4. При желании — оставить комментарий.
5. Нажать **«Разблокировать»**.

### Способ 2: Страница «Лаборатория»

1. Открыть раздел **«Лаборатория»** (если включён).
2. Найти партию в списке **«Ожидают / Заблокированы»**.
3. Кликнуть **«Одобрить»** (`ApproveBatchRequest.result = "PASSED"`).
4. Заполнить комментарий (обязательно при `FAILED`).

## Как разблокировать через API

### Простое разблокирование

```bash
curl -X POST http://localhost:8000/api/v1/lab/batch/{batch_id}/unblock \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Одобрено после повторного анализа"}'
```

### Одобрение после анализа

```bash
curl -X POST http://localhost:8000/api/v1/lab/batch/{batch_id}/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "result": "PASSED",
    "comment": "pH в норме, вязкость 1.28"
  }'
```

## Что происходит после разблокировки

1. `is_lab_blocked = FALSE`, `lab_status = 'APPROVED'`.
     2. **Автоматическое перепланирование** запускается в фоне (`BackgroundTasks`).
     3. Через 30–120 секунд создаётся **новая версия плана**.
4. Открыть её через «Историю планов».

## Как найти все заблокированные

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    b.id,
    p.code AS product_code,
    b.volume_kg,
    b.lab_block_reason,
    b.lab_blocked_at,
    u.full_name AS blocked_by
FROM batch b
JOIN product p ON p.id = b.product_id
LEFT JOIN app_user u ON u.id = b.lab_blocked_by
WHERE b.organization_id = '00000000-0000-0000-0000-000000000001'
  AND b.is_lab_blocked = TRUE;
"
```

## Что делать, если разблокировка не помогает

**Проверьте**: применена ли миграция `add_08.sql`? Без неё колонки `is_lab_blocked` могут отсутствовать.

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT column_name FROM information_schema.columns
WHERE table_name = 'batch' AND column_name = 'is_lab_blocked';
"
```

## Связанные статьи

- [Лабораторные блокировки](/help/lab-blocks)
- [Мастер смены](/help/shift-overview)
- [Пересчёт плана](/help/planning-recalculate)$md$,
 '["faq", "лаборатория", "блокировка", "разблокировать"]'::jsonb,
 110, TRUE),

-- ==========================================
-- 12. faq-route-mismatch
-- ==========================================
(NULL,
 'faq-route-mismatch',
 'Advisor: ROUTE_MISMATCH — что это значит?',
 'faq',
 $md$# Advisor: ROUTE_MISMATCH

**Категория:** FAQ

**Симптом:** Advisor показывает 🔵 **ROUTE_MISMATCH** — «Маршрут через танк невозможен: Реактор 2».

## Что это значит

У продукта `route_type = 'VIA_TANK'` (слив через накопительную ёмкость), но **реактор не подключён к танку**. Слив пойдёт **напрямую на линию**, что может замедлить процесс.

## Пример

**Крем-мыло 5л** производится в **Реакторе 2** (10 000 л). Продукт `PF_CREAM` имеет `route_type = 'VIA_TANK'`. Но только **Реактор 1** подключён к **Накопительной ёмкости 1**. Реактор 2 → **нет танка**.

Advisor это замечает и советует добавить связь `REACTOR_2 → TANK_2 → LINE_2`.

## Что делать

### Вариант 1: Добавить связь реактор → танк

**Через UI:**

1. Открыть **«Оборудование»**.
2. Проверить, есть ли у Реактора 2 связанный танк (через `equipment_link`).
3. Если нет — создать танк и связи (нужно править БД — UI связей пока нет).

**Через миграцию** (как в `add_19.sql`):

```sql
-- Создать TANK_2 (если нет)
INSERT INTO equipment (id, organization_id, code, name, type, volume_kg, speed_coeff)
SELECT gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
       'TANK_2', 'Накопительная емкость 2', 'TANK', 10000, 1.0
WHERE NOT EXISTS (
    SELECT 1 FROM equipment
    WHERE organization_id = '00000000-0000-0000-0000-000000000001'
      AND code = 'TANK_2'
);

-- Связь Р2 → TANK_2
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct)
SELECT '00000000-0000-0000-0000-000000000001',
       (SELECT id FROM equipment WHERE code = 'REACTOR_2'),
       (SELECT id FROM equipment WHERE code = 'TANK_2'),
       TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM equipment_link el
    JOIN equipment e1 ON e1.id = el.from_equipment_id
    JOIN equipment e2 ON e2.id = el.to_equipment_id
    WHERE e1.code = 'REACTOR_2' AND e2.code = 'TANK_2'
);

-- Связь TANK_2 → LINE_2
INSERT INTO equipment_link (organization_id, from_equipment_id, to_equipment_id, is_direct)
SELECT '00000000-0000-0000-0000-000000000001',
       (SELECT id FROM equipment WHERE code = 'TANK_2'),
       (SELECT id FROM equipment WHERE code = 'LINE_2'),
       TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM equipment_link el
    JOIN equipment e1 ON e1.id = el.from_equipment_id
    JOIN equipment e2 ON e2.id = el.to_equipment_id
    WHERE e1.code = 'TANK_2' AND e2.code = 'LINE_2'
);
```

### Вариант 2: Изменить `route_type` продукта

Если слив через танк **не критичен** — можно поставить `DIRECT`:

```bash
curl -X PUT http://localhost:8000/api/v1/products/{pf_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"route_type": "DIRECT"}'
```

**Осторожно:** это повлияет на построение цепочки операций. Убедитесь, что это соответствует ТЗ.

## Как проверить текущие связи

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    e1.code AS from_eq,
    e2.code AS to_eq,
    el.is_direct
FROM equipment_link el
JOIN equipment e1 ON e1.id = el.from_equipment_id
JOIN equipment e2 ON e2.id = el.to_equipment_id
WHERE e1.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY e1.code, e2.code;
"
```

## После изменений — пересчитать план

Solver заново построит цепочки операций с учётом новых связей.

## Связанные статьи

- [Advisor: подсказки планировщика](/help/planning-advisor)
- [Обзор системы](/help/intro-overview)$md$,
 '["faq", "advisor", "route", "танк", "маршрут"]'::jsonb,
 120, TRUE),

-- ==========================================
-- 13. faq-cooling-degradation
-- ==========================================
(NULL,
 'faq-cooling-degradation',
 'Advisor: COOLING_DEGRADATION — что это значит?',
 'faq',
 $md$# Advisor: COOLING_DEGRADATION

**Категория:** FAQ

**Симптом:** Advisor показывает 🟡 **COOLING_DEGRADATION** — «Охлаждение с деградацией: N операций».

## Что это значит

По ТЗ (Раздел 3, п. 11): **когда в зоне охлаждения работают 2+ реактора одновременно, каждая операция замедляется ×1.3**.

Зона охлаждения имеет `capacity = 2`. Если одновременно охлаждается **3+ реактора** — модель деградации применяется ко всем. Это добавляет ~10–30 мин к каждой cooling-операции.

## Пример

- Реактор 1 охлаждает крем-мыло, старт в 10:00.
- Реактор 2 охлаждает крем-мыло, старт в 10:30.
- Оба попадают в зону охлаждения одновременно.
- Advisor: 🔴 **COOLING_DEGRADATION** — 2 операции замедлены ×1.3.

## Что делать

### Вариант 1: Ничего

Это **не ошибка**. Модель работает корректно: длительности увеличены, план построен с учётом деградации. Это нормально, если нет срочности.

### Вариант 2: Разнести охлаждения во времени

Открыть **Гант** → найти задачи с иконкой ⏳ (замедленные). Разнести их по времени вручную (если есть возможность).

**Или** уменьшить число параллельных партий в реакторах с охлаждением.

### Вариант 3: Увеличить зону охлаждения

Если физически возможно — увеличить `capacity` пула `COOLING_ZONE`:

```bash
curl -X PUT http://localhost:8000/api/v1/personnel/pools/{pool_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"capacity": 3}'
```

**Осторожно:** это физическое ограничение. Меняйте, только если у вас реально 3+ зоны охлаждения.

### Вариант 4: Отключить деградацию

Если для вашего производства модель не критична:

```bash
curl -X PUT http://localhost:8000/api/v1/settings/enable_cooling_degradation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": false}'
```

**Не рекомендую** — модель заложена в ТЗ и соответствует реальности.

## Как найти замедленные задачи

### На Ганте

1. Тулбар → **🎛 Фильтры**.
2. Чекбокс **«⏳ Только замедленное охлаждение»**.
3. Гант покажет только их.

### Через БД

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    st.id,
    st.operation_name,
    st.planned_start,
    st.planned_end,
    st.cooling_mode
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = TRUE
  AND st.cooling_mode = 'slow'
ORDER BY st.planned_start;
"
```

## Связанные статьи

- [Advisor: подсказки планировщика](/help/planning-advisor)
- [Обзор диаграммы Ганта](/help/gantt-overview)
- [Персонал](/help/shift-overview)$md$,
 '["faq", "advisor", "охлаждение", "деградация", "cooling"]'::jsonb,
 130, TRUE),

-- ==========================================
-- 14. faq-cz-incomplete
-- ==========================================
(NULL,
 'faq-cz-incomplete',
 'Advisor: CZ_INCOMPLETE — что это значит?',
 'faq',
 $md$# Advisor: CZ_INCOMPLETE

**Категория:** FAQ

**Симптом:** Advisor показывает 🟡 **CZ_INCOMPLETE** — «Партия слита, но не промаркирована».

## Что это значит

Задача **слива на линию** (`LINE_FILL`) имеет статус `DONE`, но партия **не достигла порога маркировки ЧЗ** (`cz_completion_threshold = 0.95` по умолчанию).

Возможные ситуации:

- Партия слита полностью, но камеры ЧЗ ещё не отсканировали все бутылки.
- Сканы идут, но с задержкой.
- Камеры отключены.

## Что делать

### Вариант 1: Подождать

Если производство продолжается — сканы придут в течение 5–15 минут. Advisor сам «погасит» подсказку при следующем обновлении.

**Обновить Advisor:**

1. Открыть **«Планирование»**.
2. Кликнуть **🔄 Обновить** в панели Advisor.

### Вариант 2: Проверить камеры

Открыть **«Честный Знак»** → посмотреть журнал сканов. Если сканы не идут с определённой линии:

- Проверить, что камера подключена к сети.
- Проверить, что `cz_api_key` в настройках совпадает с ключом камеры.
- Проверить логи backend: `[cz_auth] Неверный X-CZ-Api-Key`.

### Вариант 3: Ручное закрытие партии

Если по факту партия промаркирована, но сканы не пришли — можно снизить порог:

```bash
curl -X PUT http://localhost:8000/api/v1/settings/cz_completion_threshold \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": 0.80}'
```

**Не рекомендую** — это снижает требования к маркировке.

### Вариант 4: Привязать сканы-сироты вручную

Если сканы есть, но не сопоставлены с партией → открыть **«Честный Знак»** → найти «сироты» → привязать.

## Как посмотреть прогресс партии

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/cz/batch/{batch_id}/progress
```

Ответ:

```json
{
  "batch_id": "...",
  "planned_qty": 3500.0,
  "marked_qty": 3400.0,
  "progress_percent": 97.1,
  "cz_status": "COMPLETED",
  "threshold": 0.95
}
```

Если `progress_percent < 95` — маркировка не завершена.

## Advisory-подсказка информационная

**Важно:** `CZ_INCOMPLETE` — это **предупреждение**, а не блокировка. Партия может отгружаться, но факт маркировки нужен для отчётности.

## Связанные статьи

- [Честный Знак](/help/cz-overview)
- [Скан ЧЗ попал в «сироты»](/help/faq-cz-orphan-scan)
- [Advisor: подсказки планировщика](/help/planning-advisor)$md$,
 '["faq", "advisor", "честный знак", "cz", "маркировка"]'::jsonb,
 140, TRUE),

-- ==========================================
-- 15. faq-underload
-- ==========================================
(NULL,
 'faq-underload',
 'Advisor: UNDERLOAD — неполная загрузка реактора',
 'faq',
 $md$# Advisor: UNDERLOAD

**Категория:** FAQ

**Симптом:** Advisor показывает 🔵 **UNDERLOAD** — «Неполная загрузка: Реактор 1. Партия 2500 кг загружает реактор (5000 кг) на 50%».

## Что это значит

Объём партии **значительно меньше** объёма реактора. По ТЗ максимальная загрузка — **70%** (`max_fill_percent = 0.70`). Если партия загружает реактор **меньше 50% от 70%** — Advisor считает это неэффективным.

**Пример:** реактор 5000 кг × 0.7 = 3500 кг максимум. Партия 2500 кг = 50% от максимума.

## Что делать

### Вариант 1: Увеличить партию

Если возможно — увеличить `volume_kg` партии до 3500 кг. Это уменьшит количество партий и увеличит производительность.

**Как:** страница **«Заказы»** → развернуть заказ → редактировать партии.

### Вариант 2: Объединить партии

Если есть 2+ маленькие партии того же продукта в одном реакторе — слить в одну.

### Вариант 3: Использовать меньший реактор

Если есть реактор меньшего объёма (например, 3000 л вместо 5000 л) — переключить партию на него.

**Как:** страница **«Заказы»** → развернуть заказ → изменить `assigned_equipment_id` партии.

### Вариант 4: Ничего не делать

`UNDERLOAD` — **информационная** подсказка (INFO). Если план устраивает и загрузка реакторов допустима — игнорировать.

## Когда это нормально

- Заказ **сам по себе меньше** 70% реактора.
- Продукт **нельзя варить в больших объёмах** (ограничения техкарты).
- Партия — **остаток** после распределения.

## Как найти все перегруженные/недогруженные реакторы

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    e.name AS equipment,
    e.volume_kg AS reactor_volume,
    b.volume_kg AS batch_volume,
    ROUND(100.0 * b.volume_kg / e.volume_kg, 1) AS fill_percent,
    CASE
        WHEN 100.0 * b.volume_kg / e.volume_kg < 35 THEN 'UNDERLOAD'
        WHEN 100.0 * b.volume_kg / e.volume_kg > 70 THEN 'OVERLOAD'
        ELSE 'OK'
    END AS status
FROM batch b
JOIN equipment e ON e.id = b.assigned_equipment_id
WHERE b.organization_id = '00000000-0000-0000-0000-000000000001'
  AND e.type = 'REACTOR'
ORDER BY fill_percent ASC;
"
```

## Связанные статьи

- [Advisor: подсказки планировщика](/help/planning-advisor)
- [Материалы и остатки](/help/intro-overview)
- [Не хватает сырья — что делать?](/help/faq-material-shortage)$md$,
 '["faq", "advisor", "underload", "недогрузка", "реактор"]'::jsonb,
 150, TRUE)

    ON CONFLICT (slug) DO NOTHING;

COMMIT;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT COUNT(*) AS seeded
FROM help_article
WHERE slug IN (
               'faq-lab-blocked-batch',
               'faq-route-mismatch',
               'faq-cooling-degradation',
               'faq-cz-incomplete',
               'faq-underload'
    );
-- Ожидаемо: 5