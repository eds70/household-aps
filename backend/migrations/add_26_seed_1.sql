-- ==========================================
-- SEED 26/1: СПРАВКА — FAQ (ПЛАНИРОВАНИЕ)
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
-- 1. faq-plan-feasible-not-optimal
-- ==========================================
(NULL,
 'faq-plan-feasible-not-optimal',
 'План получился FEASIBLE, а не OPTIMAL — что делать?',
 'faq',
 $md$# План FEASIBLE, а не OPTIMAL

**Категория:** FAQ

**Симптом:** В ответе `/schedule/build` приходит `status: "FEASIBLE"` вместо `"OPTIMAL"`.

## Причина

Solver **не успел найти оптимальное решение** за отведённый `timeout_seconds` (по умолчанию 600 сек), но нашёл **допустимое** решение. Это не ошибка — это компромисс между качеством и временем.

FEASIBLE бывает в трёх случаях:

1. **Слишком большой горизонт** — 30+ дней, сотни задач.
2. **Мало времени** — `timeout_seconds = 60` не хватит для 282 задач.
3. **Сложные ограничения** — много pinned-задач, узкие календарные окна.

## Что делать

### Вариант 1: Увеличить timeout

```bash
curl -X PUT http://localhost:8000/api/v1/settings/timeout_seconds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": 1800}'
```

Максимум — 3600 сек (1 час). Дальше solver редко что-то улучшает.

### Вариант 2: Уменьшить горизонт

```bash
curl -X PUT http://localhost:8000/api/v1/settings/horizon_hours \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": 720}'
```

720 часов (30 дней) — оптимально для тестового кейса.

### Вариант 3: Уменьшить число pinned-задач

Pinned-задачи жёстко фиксируют время. Чем их больше — тем сложнее solver найти OPTIMAL.

На Ганте: контекстное меню → **«Открепить»**.

## Чем FEASIBLE отличается от OPTIMAL

| Статус | Что значит |
|--------|------------|
| **OPTIMAL** | Solver доказал, что решение — лучшее из возможных |
| **FEASIBLE** | Solver нашёл решение, но не доказал оптимальность |

Для практики FEASIBLE часто **достаточно хорош** — отличие от OPTIMAL в 5–15%.

## Проверка

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    EXTRACT(EPOCH FROM (MAX(planned_end) - MIN(planned_start))) / 60 AS makespan_min
FROM scheduled_task st
JOIN schedule_version sv ON sv.id = st.schedule_version_id
WHERE sv.is_active = TRUE;
"
```

Если makespan укладывается в сроки заказов — можно оставить FEASIBLE.

## Связанные статьи

- [Advisor: подсказки планировщика](/help/planning-advisor)
- [Пересчёт плана](/help/planning-recalculate)
- [Как построить план](/help/planning-build-plan)$md$,
 '["faq", "solver", "optimal", "feasible", "timeout"]'::jsonb,
 10, TRUE),

-- ==========================================
-- 2. faq-task-not-movable
-- ==========================================
(NULL,
 'faq-task-not-movable',
 'Задача не двигается на Ганте - что делать?',
 'faq',
 $md$# Задача не двигается на Ганте

**Категория:** FAQ

**Симптом:** Перетаскиваете задачу мышкой — она возвращается на место.

## Причины (по приоритету)

### 1. План в режиме 🔒 Просмотр

**Самая частая причина.** План открыт в readonly-режиме.

**Что делать:** в тулбаре Ганта кликнуть **✏️** (переключатель `🔒/✏️`).

Индикатор в шапке тоже сменится на `✏️ План от ...` (зелёный).

### 2. Задача закреплена 📌

Задача с `is_pinned = TRUE` **перетаскивать нельзя**, но **длительность менять можно**.

**Что делать:** контекстное меню → **«Открепить»**.

### 3. Статус DONE или IN_PROGRESS

Завершённые и начатые задачи не двигаются.

**Что делать:** сменить статус в **Мастере смены** → карточка задачи → **Отменить**.

### 4. Задача — setup или downtime

     «🧼 Замывка» и «📅 Выходные» — вычисляемые элементы. Они **не сохраняются в БД**, двигать их нельзя.

### 5. Каскад заблокирован pinned-задачей

Соседняя или зависимая задача закреплена. Появляется диалог **«Изменение заблокировано»**.

**Что делать:**
- Кликнуть **«Показать задачу»** — Гант отцентрируется на мешающей задаче.
- Открепить её.
- Повторить перетаскивание.

### 6. Выходной день

Если `allow_weekend_work = false` — задача не встанет на сб/вс.

**Что делать:** в мастере настроек плана (⚙) → шаг «Календарь» → включить **«Работа в выходные»**.

## Диагностика

Откройте **DevTools → Network**, перетащите задачу, найдите запрос `PUT /api/v1/schedule/task/{id}/move-cascade`. В ответе:

- `200` — всё ок.
- `400` — валидация не прошла (смотрите `detail.reason`).
- `409` — каскад заблокирован pinned-задачей (смотрите `detail.blocked_task`).

## Связанные статьи

- [Редактирование задач на Ганте](/help/gantt-editing)
- [Обзор диаграммы Ганта](/help/gantt-overview)$md$,
 '["faq", "гант", "drag", "задача", "не двигается"]'::jsonb,
 20, TRUE),

-- ==========================================
-- 3. faq-plan-is-empty
-- ==========================================
(NULL,
 'faq-plan-is-empty',
 'План пуст (⚠) — что делать?',
 'faq',
 $md$# План пуст (⚠) — что делать?

**Категория:** FAQ

**Симптом:** В «Истории планов» строка подсвечена жёлтым, рядом иконка **⚠**. При открытии — сообщение «План пуст».

## Причина

План был создан **до Итерации 13.15** (или вручную через API), когда снапшоты справочников ещё не заполнялись. Или снапшоты были удалены.

Без снапшотов UI не может отрисовать диаграмму Ганта — нет данных об оборудовании, продуктах, операциях.

     ## Что делать

### Вариант 1 (рекомендую): Пересоздать план

1. Закрыть план (кнопка ✕).
2. Удалить план (кнопка 🗑).
3. Создать новый через **мастер настроек** (⚙) или **«Новый план»**.
4. Снапшоты заполнятся автоматически.

### Вариант 2: Заполнить снапшоты вручную

Через API (только для отладки):

```bash
curl -X POST http://localhost:8000/api/v1/schedule/versions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Новый план",
    "version_type": "MONTHLY",
    "comment": "Проверка снапшотов"
  }'
```

В ответе будет `has_snapshot: true` и `snapshot_stats` со счётчиками.

## Как понять, что план «пуст»

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    (SELECT COUNT(*) FROM product_snapshot WHERE version_id = sv.id) AS products,
    (SELECT COUNT(*) FROM equipment_snapshot WHERE version_id = sv.id) AS equipment,
    (SELECT COUNT(*) FROM operation_snapshot WHERE version_id = sv.id) AS ops,
    (SELECT COUNT(*) FROM plan_settings WHERE schedule_version_id = sv.id) AS settings
FROM schedule_version sv
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY sv.created_at DESC
LIMIT 5;
"
```

Если `products = 0` или `equipment = 0` — снапшоты не заполнены.

## Профилактика

С Итерации 13.15 все новые планы получают снапшоты **автоматически**. Если создать план через мастер — снапшоты гарантированы.

## Связанные статьи

- [История планов](/help/planning-history)
- [Как построить план](/help/planning-build-plan)
- [Снапшоты и версионирование](/help/intro-overview)$md$,
 '["faq", "план", "снапшот", "пустой"]'::jsonb,
 30, TRUE),

-- ==========================================
-- 4. faq-plan-settings-empty
-- ==========================================
(NULL,
 'faq-plan-settings-empty',
 '«Настройки плана не заполнены» при пересчёте',
 'faq',
 $md$# «Настройки плана не заполнены» при пересчёте

 **Категория:** FAQ

 **Симптом:** Нажимаете **🔄 «Пересчитать»** на Ганте — открывается диалог **«Настройки плана не заполнены»**.

 ## Причина

 План был создан **до Итерации 13.14**, когда `plan_settings` ещё не существовало. Сейчас настройки хранятся в `app_settings` (глобально), но не имеют снапшота на уровне плана.

Без `plan_settings` пересчёт может дать другой результат при изменении глобальных настроек — это небезопасно.

## Что делать

В диалоге есть **две кнопки**:

### 1. «Открыть мастер настроек»

Открывается **мастер настроек плана** (9 шагов). Заполните параметры (или оставьте значения по умолчанию) и сохраните. После этого можно пересчитывать.

### 2. «Пересчитать без изменений»

Форс-режим: пересчёт с текущими глобальными `app_settings`. Быстро, но **не рекомендуется** для важных планов — если глобальные настройки потом изменятся, план не будет воспроизводим.

## Рекомендация

**Создавайте планы через мастер настроек** (⚙ в списке планов) — тогда `plan_settings` заполняются сразу.

## Проверка

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    sv.name,
    COUNT(ps.id) AS settings_count
FROM schedule_version sv
LEFT JOIN plan_settings ps ON ps.schedule_version_id = sv.id
WHERE sv.organization_id = '00000000-0000-0000-0000-000000000001'
GROUP BY sv.id, sv.name
ORDER BY sv.created_at DESC
LIMIT 5;
"
```

Если `settings_count = 0` — план без настроек, при пересчёте появится диалог.

## Связанные статьи

- [app_settings vs plan_settings](/help/settings-app-vs-plan)
- [Пересчёт плана](/help/planning-recalculate)
- [История планов](/help/planning-history)$md$,
 '["faq", "настройки", "plan_settings", "пересчёт"]'::jsonb,
 40, TRUE),

-- ==========================================
-- 5. faq-material-shortage
-- ==========================================
(NULL,
 'faq-material-shortage',
 'Не хватает сырья — что делать?',
 'faq',
 $md$# Не хватает сырья — что делать?

**Категория:** FAQ

**Симптом:** Advisor показывает 🔴 **MATERIAL_SHORTAGE** — «Нехватка сырья: Отдушка цветочная, дефицит 150 кг».

## Причина

Суммарная потребность в материале **превышает** доступный остаток на складе (с учётом `reserved_qty`).

## Что делать (по приоритету)

### 1. Увеличить остаток на складе

Если сырьё физически есть — обновить остаток на странице **«Материалы»** (двойной клик по ячейке «Остаток»).

Или через API:

```bash
curl -X PUT http://localhost:8000/api/v1/materials/{material_id}/stock \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"qty": 2000}'
```

### 2. Уменьшить объём партий

Открыть **«Заказы»** → найти нужный заказ → уменьшить `target_qty`. Партии пересоздадутся.

Или уменьшить `volume_kg` конкретной партии.

### 3. Удалить партии

Если сырья точно нет — удалить партии, которые не будут производиться. На странице **«Заказы»** → развернуть заказ → удалить партии.

### 4. Проверить рецептуру

Открыть **«Рецептуры»** → проверить, что `qty_per_base` для материала указан правильно. Ошибка в 10 раз — рецепт показывает 20 кг вместо 2 кг.

## Как посчитать дефицит

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT
    m.code,
    m.name,
    COALESCE(ms.qty, 0) AS stock,
    COALESCE(ms.reserved_qty, 0) AS reserved,
    COALESCE(ms.qty, 0) - COALESCE(ms.reserved_qty, 0) AS available
FROM material m
LEFT JOIN material_stock ms ON ms.material_id = m.id
WHERE m.organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY available ASC;
"
```

## Advisor — не блокировка

**Важно:** `MATERIAL_SHORTAGE` — это **предупреждение**, а не блокировка. Solver построит план независимо от дефицита, но задачи, требующие этот материал, могут быть запланированы в конце.

## Связанные статьи

- [Advisor: подсказки планировщика](/help/planning-advisor)
- [Материалы и остатки](/help/intro-overview)
- [Рецептуры](/help/intro-overview)$md$,
 '["faq", "материалы", "дефицит", "advisor"]'::jsonb,
 50, TRUE)

    ON CONFLICT (slug) DO NOTHING;

COMMIT;

-- ==========================================
-- ПРОВЕРКА
-- ==========================================
SELECT COUNT(*) AS seeded
FROM help_article
WHERE slug IN (
               'faq-plan-feasible-not-optimal',
               'faq-task-not-movable',
               'faq-plan-is-empty',
               'faq-plan-settings-empty',
               'faq-material-shortage'
    );
-- Ожидаемо: 5