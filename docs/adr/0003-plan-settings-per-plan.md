# 0003. Plan settings per plan

**Дата:** 2026-09-25
**Статус:** Принято
**Контекст:** Итерация 13.14

---

## Контекст

Система APS Production Scheduler использует **глобальные настройки** (`app_settings`) для конфигурации планирования:
- `horizon_hours` — горизонт планирования.
- `timeout_seconds` — таймаут solver.
- `shift_mode` — режим смен.
- `enable_cooling_degradation` — деградация охлаждения.
- `weight_makespan`, `weight_setup`, ... — веса multi-objective.
- И ещё ~30 настроек.

**Проблема:**
Глобальные настройки применяются ко **всем** планам одновременно. Если пользователь изменил `horizon_hours` с 720 на 1000 и пересчитал план — старые планы становятся «невалидными»:
- Нельзя воспроизвести результат старого плана.
- Нельзя сравнить два плана, построенные с разными настройками.
- Нельзя понять, почему старый план выглядит именно так.

**Пример:**
1. Построили план A с `horizon_hours = 720`.
2. Изменили `horizon_hours = 1000`.
3. Построили план B.
4. Пытаемся сравнить A и B — но A был построен с другими настройками, сравнение некорректно.
5. Пытаемся воспроизвести A — но `app_settings` уже изменены.

**Что нужно:**
- Каждый план должен хранить **свой снапшот** настроек.
- Планировщик должен читать настройки **этого плана**, а не глобальные.
- Глобальные `app_settings` остаются дефолтом для новых планов.
- Обратная совместимость: старые планы без снапшота работают через `app_settings`.

---

## Решение

Создать таблицу **`plan_settings`** — снапшот настроек для **конкретного плана**.

### Структура

```sql
CREATE TABLE plan_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    schedule_version_id UUID NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    setting_key TEXT NOT NULL,
    setting_value JSONB,
    value_type TEXT NOT NULL DEFAULT 'str',
    category TEXT NOT NULL DEFAULT 'general',
    label TEXT,
    description TEXT,
    min_value NUMERIC,
    max_value NUMERIC,
    options JSONB,
    display_order INT NOT NULL DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (schedule_version_id, setting_key)
);
```

### Триггер `copy_app_settings_to_plan`

```sql
CREATE OR REPLACE FUNCTION copy_app_settings_to_plan()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO plan_settings (
        organization_id, schedule_version_id,
        setting_key, setting_value,
        value_type, category, label, description,
        min_value, max_value, options, display_order, is_system
    )
    SELECT
        NEW.organization_id, NEW.id,
        setting_key, setting_value,
        value_type, category, label, description,
        min_value, max_value, options, display_order, is_system
    FROM app_settings
    WHERE organization_id = NEW.organization_id
    ON CONFLICT (schedule_version_id, setting_key) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_copy_app_settings_to_plan
    AFTER INSERT ON schedule_version
    FOR EACH ROW
    EXECUTE FUNCTION copy_app_settings_to_plan();
```

**Ключевые особенности триггера:**
- `AFTER INSERT ON schedule_version` — срабатывает автоматически при создании плана.
- Идемпотентен (`ON CONFLICT DO NOTHING`).
- Работает на уровне БД — не нужен ни Python, ни API.
- Копирует **все** `app_settings` (32 настройки) в `plan_settings` нового плана.

### Логика чтения

```python
async def read_setting(
    db: AsyncSession,
    org_id: UUID,
    key: str,
    default: Optional[str] = None,
    version_id: Optional[UUID] = None,
) -> Optional[str]:
    # 1. Если version_id задан — читаем из plan_settings
    if version_id is not None:
        row = await db.execute(
            select(PlanSetting.setting_value)
            .where(PlanSetting.schedule_version_id == version_id)
            .where(PlanSetting.setting_key == key)
        )
        value = row.scalar_one_or_none()
        if value is not None:
            return value

    # 2. Fallback на app_settings
    row = await db.execute(
        select(AppSetting.setting_value)
        .where(AppSetting.organization_id == org_id)
        .where(AppSetting.setting_key == key)
    )
    value = row.scalar_one_or_none()
    if value is not None:
        return value

    # 3. Default
    return default
```

### API

| Метод | Путь | Назначение | Права |
|-------|------|------------|-------|
| `GET` | `/api/v1/plan-settings/version/{version_id}` | Настройки плана | любой |
| `PUT` | `/api/v1/plan-settings/version/{version_id}` | Массовое обновление | ADMIN, PLANNER |
| `POST` | `/api/v1/plan-settings/version/{version_id}/reset` | Сброс к глобальным | ADMIN, PLANNER |

### Frontend

- `PlanSettingsWizard.tsx` — мастер настроек плана (9 шагов).
- `SchedulePage.tsx` — кнопка «Настройки плана» (⚙) в действиях таблицы планов.
- `planSettingsApi` в `api.ts` — 3 метода.

---

## Последствия

### Положительные

- ✅ **Изоляция:** два плана имеют независимые настройки. Изменение одного не влияет на другой.
- ✅ **Воспроизводимость:** зная `plan_settings`, можно пересчитать ровно тот же результат через N месяцев.
- ✅ **Сравнимость:** можно корректно сравнивать два плана, построенных с разными настройками.
- ✅ **Обратная совместимость:** все API-эндпоинты с опциональным `version_id`. Без него — работа как раньше (глобальные `app_settings`).
- ✅ **Fallback:** старые планы без `plan_settings` (до миграции) — работают через `app_settings`.
- ✅ **CASCADE DELETE:** при удалении плана его настройки удаляются автоматически.
- ✅ **Идемпотентность:** повторное применение миграции/триггера безопасно.
- ✅ **Не нужен Python/API для копирования** — триггер работает на уровне БД.
- ✅ **Снапшот метаданных** — `label`, `description`, `min_value`, `max_value`, `options` копируются в `plan_settings`.

### Отрицательные

- ⚠️ **Дублирование данных** — 32 настройки × N планов.
- ⚠️ **Снапшот не обновляется** при изменении `app_settings` — это by design.
- ⚠️ **Нужно явно указывать `version_id`** — в API-эндпоинтах.
- ⚠️ **Существующие планы без `plan_settings`** — работают через fallback.
- ⚠️ **Мастер настроек работает только с существующими планами** — для новых планов сначала создать, потом открыть мастер.
- ⚠️ **Системные настройки** (`shift_intervals`, `shift_duration_hours`) — `is_system = true`, не редактируются через мастер.

**Митигации:**
- `version_id` опционален в API — без него берётся активная версия.
- `POST /reset` — сброс к глобальным настройкам.
- `POST /reset` создаёт полный набор настроек, если `plan_settings` пуст.
- Старые планы можно «мигрировать», вызвав `POST /reset`.

### Альтернативы

#### 1. JSONB-поле в `schedule_version`

**Идея:** добавить колонку `settings JSONB` в `schedule_version`.

**Плюсы:**
- Простота — одна колонка.
- Нет отдельной таблицы.

**Минусы:**
- ❌ **Нет валидации** на уровне БД.
- ❌ **Сложность запросов** — JSONB не так удобен, как реляционные таблицы.
- ❌ **Нет индексов** на отдельные поля.
- ❌ **Нет `UNIQUE`** на ключ.
- ❌ **Сложность UI** — сложно отображать.
- ❌ **Нет метаданных** — `label`, `description`, `min_value`, `max_value`, `options` нужно хранить отдельно или дублировать.

**Почему отклонён:** нет валидации, сложность запросов, нет индексов.

---

#### 2. Отдельная таблица `plan_settings` без триггера

**Идея:** создать таблицу `plan_settings`, но заполнять её через API/Python.

**Плюсы:**
- Гибкость — можно контролировать процесс.

**Минусы:**
- ❌ **Нужно не забыть вызвать** копирование при создании плана.
- ❌ **Дублирование логики** — Python + API.
- ❌ **Сложность** — нужно поддерживать.

**Почему отклонён:** триггер надёжнее, работает автоматически.

---

#### 3. Отдельная БД для каждого плана

**Идея:** каждый план — отдельная БД со своими настройками.

**Плюсы:**
- Полная изоляция.

**Минусы:**
- ❌ **Огромная сложность** — управление соединениями, миграции.
- ❌ **Не масштабируется** — 100 планов = 100 БД.
- ❌ **Проблемы с бэкапами** — нужно бэкапить каждую БД.

**Почему отклонён:** избыточно, не масштабируется.

---

#### 4. Версионирование `app_settings` через `valid_from`/`valid_to`

**Идея:** добавить `valid_from`, `valid_to` в `app_settings`.

**Плюсы:**
- Нет дублирования.
- Единый источник правды.

**Минусы:**
- ❌ **Сложность запросов** — везде нужно учитывать временные интервалы.
- ❌ **Сложность UI** — нужно показывать историю.
- ❌ **Проблемы с производительностью** — индексы на временные интервалы.
- ❌ **Не решает проблему полностью** — настройки «на момент времени» не всегда совпадают с настройками конкретного плана.

**Почему отклонён:** сложность, не решает проблему полностью.

---

#### 5. Настройки в `schedule_version` как отдельные колонки

**Идея:** добавить 32 колонки в `schedule_version` (по одной на настройку).

**Плюсы:**
- Простота запросов.
- Валидация на уровне БД.

**Минусы:**
- ❌ **Схема БД меняется** при добавлении новой настройки.
- ❌ **Миграции** при каждом изменении.
- ❌ **Нет метаданных** — `label`, `description`, `min_value`, `max_value`, `options` нужно хранить отдельно.
- ❌ **Сложность UI** — 32 колонки.

**Почему отклонён:** схема БД меняется при добавлении настройки.

---

## Ссылки

- [ADR 0002: Snapshot tables for versioning](0002-snapshot-tables-for-versioning.md)
- [ADR 0004: What-if two transactions](0004-whatif-two-transactions.md)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — архитектура.
- [docs/CONFIGURATION.md](../CONFIGURATION.md) — настройки.
- [docs/OPERATIONS.md](../OPERATIONS.md) — операции с БД.
- [README.md](../../README.md) — основная документация.