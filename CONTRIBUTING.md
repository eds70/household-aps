# Contributing

Спасибо за интерес к проекту **APS Production Scheduler**! Этот документ описывает, как внести вклад в развитие системы.

---

## 📋 Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Как отправить PR](#как-отправить-pr)
- [Стиль кода](#стиль-кода)
- [Conventional Commits](#conventional-commits)
- [Тестирование](#тестирование)
- [Документация](#документация)
- [Разработка](#разработка)

---

## Кодекс поведения

- Уважайте других участников.
- Конструктивная критика приветствуется, переход на личности — нет.
- Все обсуждения — в issue или PR, не в личных сообщениях.

---

## Как отправить PR

### 1. Подготовка

1. Форкните репозиторий.
2. Создайте ветку от `main`:
   ```
   git checkout -b feature/iteration-17-recipes
   ```
3. Убедитесь, что локально всё работает:
   ```
   cd backend
   pytest tests/ -v
   ```

### 2. Внесение изменений

1. Следуйте [стилю кода](#стиль-кода).
2. Пишите тесты на новую функциональность.
3. Обновляйте `CHANGELOG.md` (секция `[Unreleased]`).
4. Обновляйте документацию в `docs/`, если затронуты API/настройки/архитектура.

### 3. Коммиты

Используйте [Conventional Commits](#conventional-commits):
```
feat(scheduler): add plan_settings support to DataLoader
fix(shift): correct timezone comparison for by-date endpoint
docs(readme): update version to 4.10.0
test(plan_settings): add integration tests for trigger
```

### 4. Pull Request

1. Запушьте ветку:
   ```
   git push origin feature/iteration-17-recipes
   ```
2. Откройте PR против `main`.
3. Заполните шаблон PR:
   - **Что сделано** — краткое описание.
   - **Зачем** — ссылка на issue или итерацию.
   - **Как проверить** — шаги для ревьюера.
   - **Чек-лист** — тесты, документация, CHANGELOG.

### 5. Ревью

- Минимум 1 approve от мейнтейнера.
- Все CI-чеки должны быть зелёными.
- Конфликты с `main` должны быть разрешены.

---

## Стиль кода

### Python (backend)

| Инструмент | Назначение | Команда |
|------------|------------|---------|
| **ruff** | Линтер + форматтер | `ruff check app/ tests/` |
| **black** | Форматтер | `black app/ tests/` |
| **mypy** | Типизация | `mypy app/` |

**Правила:**

- Длина строки: **100 символов**.
- Типизация: **обязательна** для всех публичных функций.
- Async: используйте `async def` для всех I/O-операций.
- Docstrings: Google-style для публичных модулей и классов.
- Импорты: сортировка через `ruff` (isort-совместимая).

**Пример:**
```python
from typing import Optional
from uuid import UUID

async def read_setting(
        db: AsyncSession,
        org_id: UUID,
        key: str,
        default: Optional[str] = None,
        version_id: Optional[UUID] = None,
) -> Optional[str]:
   """Читает настройку из plan_settings или app_settings.

   Args:
       db: Async-сессия SQLAlchemy.
       org_id: ID организации.
       key: Ключ настройки.
       default: Значение по умолчанию.
       version_id: ID плана (если None — читает из app_settings).

   Returns:
       Значение настройки или default.
   """
   ...
```

### TypeScript / React (frontend)

| Инструмент | Назначение | Команда |
|------------|------------|---------|
| **ESLint** | Линтер | `npm run lint` |
| **TypeScript** | Типизация | `npm run typecheck` |
| **Prettier** | Форматтер | `npm run format` |

**Правила:**

- Функциональные компоненты + hooks.
- Типизация props через `interface`.
- `useCallback` для функций, передаваемых в `useEffect` зависимости.
- Именование: `PascalCase` для компонентов, `camelCase` для функций/переменных.
- Отступ: 2 пробела.

**Пример:**
```tsx
interface PlanSettingsWizardProps {
   versionId: string;
   onSave: (settings: Record<string, unknown>) => void;
   onClose: () => void;
}

export const PlanSettingsWizard: React.FC<PlanSettingsWizardProps> = ({
                                                                         versionId,
                                                                         onSave,
                                                                         onClose,
                                                                      }) => {
   const [settings, setSettings] = useState<Record<string, unknown>>({});
   // ...
};
```

### SQL (миграции)

- Имя файла: `add_NN.sql` или `fix_<описание>.sql`.
- Идемпотентность: `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`.
- Комментарии: `-- Итерация N: описание`.
- Транзакции: оборачивайте в `BEGIN; ... COMMIT;`.

**Пример:**
```sql
-- Итерация 17.2: снапшоты рецептов для версионирования
BEGIN;

CREATE TABLE IF NOT EXISTS recipe_snapshot (
    id              UUID           NOT NULL,
    organization_id UUID,
    product_id      UUID           NOT NULL,
    base_volume_kg  NUMERIC(10,2)  NOT NULL,
    comment         TEXT,
    version_id      UUID           NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_ver
    ON recipe_snapshot(version_id);

COMMIT;
```

---

## Conventional Commits

Формат:
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Типы

| Тип | Назначение |
|-----|------------|
| `feat` | Новая функциональность |
| `fix` | Исправление бага |
| `docs` | Только документация |
| `style` | Форматирование (без изменения логики) |
| `refactor` | Рефакторинг (без новой функциональности) |
| `test` | Добавление/изменение тестов |
| `chore` | Обновление зависимостей, конфигов |
| `perf` | Оптимизация производительности |
| `ci` | Изменения в CI/CD |

### Scope (примеры)

- `scheduler` — ядро планировщика.
- `api` — REST API.
- `frontend` — React UI.
- `db` — миграции, схема.
- `settings` — app_settings, plan_settings.
- `whatif` — what-if сценарии.
- `cz` — Честный Знак.
- `lab` — лаборатория.
- `shift` — смены.
- `personnel` — персонал.
- `gantt` — диаграмма Ганта.
- `snapshot` — снапшоты справочников.
- `recipes` — рецептуры и их снапшоты.
- `help` — встроенная справка.
- `docs` — документация.

### Примеры

```
feat(settings): add plan_settings table with trigger

- Миграция add_21.sql
- Триггер copy_app_settings_to_plan
- Индексы idx_plan_settings_version, idx_plan_settings_org_category

Closes #123
```

```
fix(shift): correct timezone comparison in by-date endpoint

Раньше сравнение шло по UTC, из-за чего naive datetime из Python
не находил смену, если сессия asyncpg не в UTC.

Теперь: (starts_at AT TIME ZONE 'Europe/Moscow')::date = :shift_date

Fixes #456
```

```
fix(scheduler): fill snapshots on plan creation (iteration 13.15)

- Модуль snapshot.py с snapshot_all_catalogs
- create_schedule_version вызывает snapshot_all_catalogs
- saver._do_save делегирует в snapshot_all_catalogs
- API возвращает has_snapshot
- UI: ⚠ и предупреждение для пустых планов
- +43 теста, всего 535 passed
- Исправлен устаревший test_update_request_requires_settings
```

```
feat(gantt): add local edit mode toggle (iteration 14.2)

- Компактный ToggleButtonGroup 🔒/✏️ в тулбаре
- Глобальный localEditMode в PlanContext
- Синхронизация иконки в шапке MainLayout
- Кнопка «Пересчитать» доступна в обоих режимах
- Удалён Chip с названием плана (дублировал шапку)
- Фикс: защита от отрицательной ширины в drawBatchBrackets
```

```
feat(help): add markdown-based help system (iteration 15.1)

- Миграция add_24.sql: таблица help_article
- Seed-миграции add_24_seed_1/2/3.sql: 15 статей в 8 категориях
- API /api/v1/help: articles, categories, search, docs
- Frontend: HelpPage, HelpSidebar, HelpArticleView
- +38 тестов, всего 601 passed
```

```
feat(help): add contextual hints (iteration 15.2)

- Миграция add_25.sql: таблица help_hint
- Seed-миграция add_25_seed.sql: 8 подсказок
- API /api/v1/help/hints
- Frontend: HelpHintsContext, Hint.tsx
- Интеграция в 5 страниц (8 подсказок)
- +24 теста, всего 625 passed
```

```
feat(help): add FAQ category (iteration 15.4)

- Seed-миграции add_26_seed_1/2/3.sql: 15 FAQ-статей
- Категория faq в CATEGORY_LABELS и CATEGORY_ORDER
- Формат статей: Симптом → Причина → Что делать → Проверка
- +24 теста, всего 678 passed
```

```
feat(help): add article CRUD in UI (iteration 15.5)

- 3 эндпоинта POST/PUT/DELETE /help/articles (ADMIN)
- HelpArticleEditor.tsx — форма с предпросмотром
- HelpPage.tsx — кнопки «Новая статья» и «Редактировать»
- Хелперы: _slugify, _check_slug_conflict, _next_display_order
- +54 теста, всего 714 passed
```

```
feat(recipes): версионирование рецептов и inline-edit (iteration 17.1–17.2)

- Миграция add_29_recipe_snapshots.sql: таблицы recipe_snapshot,
  recipe_item_snapshot
- snapshot.py: блоки 5 и 6 в snapshot_all_catalogs
- recipes.py: PUT /items/{item_id}, POST /items (JSON body),
  version_id в GET /
- RecipesPage.tsx: inline-edit полей и состава, режим просмотра
- Фикс: селект «Продукт (ПФ)» использует products, а не materials
- Тесты не менялись, всего 789 passed
```

```
fix(recipes): селект «Продукт (ПФ)» использовал материалы

- Симптом: создание рецепта через UI → 500, FK violation
- Причина: material.id уходил в recipe.product_id
- Fix: селект использует productsApi.getAll() (фильтр type === 'PF')

Fixes #789
```

---

## Тестирование

### Backend

```
cd backend
..venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Требования:**

- Новый код → новые тесты.
- Покрытие: минимум 80% для новых модулей.
- Тесты: `pytest`, `pytest-asyncio`, `httpx` для API.

**Структура тестов:**

| Файл | Что проверяет |
|------|---------------|
| `test_<модуль>.py` | Юнит-тесты модуля |
| `test_<модуль>_api.py` | API-эндпоинты |
| `test_<модуль>_migration.py` | SQL-миграции |
| `test_<модуль>_integration.py` | Интеграционные тесты |

**Пример:**
```python
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_read_setting_from_plan_settings(db_session, org_id, version_id):
   """Читает настройку из plan_settings, если version_id передан."""
   # Arrange
   await db_session.execute(
      "INSERT INTO plan_settings (...) VALUES (...)"
   )
   await db_session.commit()

   # Act
   result = await read_setting(
      db_session, org_id, "horizon_hours", version_id=version_id
   )

   # Assert
   assert result == 1440
```

### Frontend

```
cd frontend
npm run test
npm run typecheck
npm run lint
```

---

## Документация

### Что обновлять

| Изменение | Файлы |
|-----------|-------|
| Новая функциональность | `README.md`, `CHANGELOG.md`, `docs/ROADMAP.md` |
| Новый API-эндпоинт | `docs/API.md`, `README.md` |
| Новая настройка | `docs/CONFIGURATION.md`, `README.md` |
| Новый ADR | `docs/adr/NNNN-<название>.md`, `docs/adr/README.md` |
| Архитектурное решение | `docs/ARCHITECTURE.md` |
| Команды БД | `docs/OPERATIONS.md`, `README.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md`, `README.md` |
| Новая таблица/миграция | `docs/OPERATIONS.md`, `README.md` |
| Статья справки | `backend/migrations/add_24_seed_*.sql` |
| Контекстная подсказка | `backend/migrations/add_25_seed.sql` |
| FAQ-статья | `backend/migrations/add_26_seed_*.sql` |
| Интерактивный тур | `frontend/src/tutorial/tours.ts` |
| Версионирование справочника | `backend/migrations/add_NN_snapshots.sql`, `backend/app/scheduler/snapshot.py` |

### Стиль документации

- Markdown, длина строки — без ограничений.
- Заголовки: `#` для названия, `##` для секций, `###` для подсекций.
- Код: тройные бэктики с указанием языка.
- Таблицы: для структурированных данных.
- Эмодзи: только в README и CHANGELOG (для визуального выделения).

---

## Разработка

### Настройка окружения

См. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

### Как добавить миграцию

1. Создайте файл `backend/migrations/add_NN.sql`.
2. Оберните в `BEGIN; ... COMMIT;`.
3. Сделайте идемпотентной (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).
4. Примените:
   ```
   docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
   docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
   ```
5. Добавьте тест в `test_<модуль>_migration.py`.
6. Обновите `CHANGELOG.md`.

**Пример миграции снапшотов** (`add_29_recipe_snapshots.sql`):

```sql
-- Итерация 17.2: снапшоты рецептов и компонентов
BEGIN;

CREATE TABLE IF NOT EXISTS recipe_snapshot (
    id              UUID           NOT NULL,
    organization_id UUID,
    product_id      UUID           NOT NULL,
    base_volume_kg  NUMERIC(10,2)  NOT NULL,
    comment         TEXT,
    version_id      UUID           NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_ver
    ON recipe_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_snap_org_ver
    ON recipe_snapshot(organization_id, version_id);

CREATE TABLE IF NOT EXISTS recipe_item_snapshot (
    id           UUID           NOT NULL,
    recipe_id    UUID           NOT NULL,
    material_id  UUID           NOT NULL,
    qty_per_base NUMERIC(10,3)  NOT NULL,
    version_id   UUID           NOT NULL
        REFERENCES schedule_version(id) ON DELETE CASCADE,
    PRIMARY KEY (id, version_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_ver
    ON recipe_item_snapshot(version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_item_snap_recipe_ver
    ON recipe_item_snapshot(recipe_id, version_id);

COMMIT;
```

### Как добавить эндпоинт

1. Создайте/откройте файл в `backend/app/api/v1/`.
2. Определите Pydantic-модели запроса/ответа.
3. Реализуйте роутер:
   ```python
   from fastapi import APIRouter, Depends
   from app.auth.dependencies import get_current_user

   router = APIRouter(prefix="/api/v1/<module>", tags=["<module>"])

   @router.get("/")
   async def list_items(
       db: AsyncSession = Depends(get_db),
       user: User = Depends(get_current_user),
   ):
       ...
   ```
4. Подключите в `backend/app/main.py`:
   ```python
   from app.api.v1.<module> import router as <module>_router
   app.include_router(<module>_router)
   ```
5. Добавьте тест в `test_<module>_api.py`.
6. Обновите `docs/API.md` и `README.md`.

**Пример: inline-edit эндпоинт** (как `PUT /recipes/{id}/items/{item_id}`):

```python
@router.put("/{recipe_id}/items/{item_id}", response_model=dict)
async def update_recipe_item(
        recipe_id: UUID,
        item_id: UUID,
        item: RecipeItemCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить компонент рецепта (qty_per_base). Inline-edit из UI."""
    check = await db.execute(
        text("SELECT 1 FROM recipe WHERE id = :recipe_id AND organization_id = :org_id"),
        {"recipe_id": recipe_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    result = await db.execute(
        text("""
            UPDATE recipe_item
            SET material_id = :material_id, qty_per_base = :qty
            WHERE id = :item_id AND recipe_id = :recipe_id
        """),
        {
            "item_id": item_id,
            "recipe_id": recipe_id,
            "material_id": item.material_id,
            "qty": item.qty_per_base,
        },
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Компонент не найден")
    await db.commit()
    return {"message": "Компонент обновлён"}
```

### Как добавить настройку

1. Добавьте запись в `SETTINGS_REGISTRY` (`backend/app/scheduler/settings.py`).
2. Создайте миграцию для `INSERT INTO app_settings`.
3. Обновите `docs/CONFIGURATION.md`.
4. Добавьте тест в `test_settings_*.py`.

### Как добавить статью справки

1. Создайте новый seed-файл `backend/migrations/add_NN_seed_M.sql`.
2. Используйте `INSERT INTO help_article ... ON CONFLICT (slug) DO NOTHING`.
3. Категории: `getting-started`, `planning`, `gantt`, `shift`,
   `lab`, `cz`, `whatif`, `settings`, `faq`.
4. Примените миграцию через `docker cp` + `psql -f`.
5. Добавьте тест в `tests/test_help.py` (или `test_help_faq.py` для FAQ).

### Как добавить контекстную подсказку

1. Создайте новый seed-файл `backend/migrations/add_NN_seed_M.sql`.
2. Используйте `INSERT INTO help_hint ... ON CONFLICT (hint_key) DO NOTHING`.
3. Формат `hint_key`: `<module>.<action>` (например, `planning.recalc`).
4. Примените миграцию через `docker cp` + `psql -f`.
5. Добавьте тест в `tests/test_help_hints.py`.

### Как добавить интерактивный тур

1. Откройте `frontend/src/tutorial/tours.ts`.
2. Добавьте новый объект тура в массив `ALL_TOURS`:
   ```typescript
   {
       id: 'my-tour',
       name: 'Мой тур',
       description: 'Краткое описание',
       icon: 'RocketLaunch',
       steps: [
           {
               target: '[data-tour-id="my-target"]',
               content: 'Текст подсказки для шага',
           },
           // ...
       ],
   }
   ```
3. Убедитесь, что у целевых элементов в UI есть атрибут
   `data-tour-id="my-target"`.
4. Добавьте тест в `frontend/src/tutorial/__tests__/tours.test.ts`.

### Как добавить версионируемый справочник (снапшот)

1. Создайте миграцию `add_NN_<name>_snapshots.sql` по паттерну
   `add_29_recipe_snapshots.sql`:
   - составной PK `(id, version_id)`;
   - FK `version_id → schedule_version(id) ON DELETE CASCADE`;
   - индексы на `version_id` и на бизнес-ключ.
2. Добавьте блок в `snapshot.py::snapshot_all_catalogs`:
   ```python
   result = await session.execute(
       text("""
           INSERT INTO <name>_snapshot
               (id, organization_id, ..., version_id)
           SELECT id, organization_id, ..., :version_id
           FROM <name>
           WHERE organization_id = :org_id
           ON CONFLICT (id, version_id) DO NOTHING
       """),
       {"version_id": version_id, "org_id": org_id},
   )
   ```
3. Добавьте ключ в `stats` (`snapshot_all_catalogs`) и в логи.
4. В API-эндпоинте чтения добавьте параметр `version_id` и
   переключение таблицы.
5. Обновите `docs/ARCHITECTURE.md` (раздел «Снапшоты») и
   `docs/OPERATIONS.md` (команды проверки).

### Как обновить CHANGELOG

1. Откройте `CHANGELOG.md`.
2. Добавьте запись в секцию `[Unreleased]`:
   ```
   ### Added
   - Новая функциональность.

   ### Fixed
   - Исправление бага.
   ```
3. При релизе — перенесите `[Unreleased]` в новую версию:
   ```
   ## [4.10.0] — 2026-10-12
   ```
4. Итерация без breaking changes и без новой функциональности —
   patch-релиз (`X.Y.Z+1`, без bump `README.md`).

---

## Ссылки

- [README.md](README.md) — основная документация.
- [CHANGELOG.md](CHANGELOG.md) — история изменений.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — руководство разработчика.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура.
- [docs/API.md](docs/API.md) — описание API.
- [docs/ROADMAP.md](docs/ROADMAP.md) — план развития.

---

## Вопросы?

Откройте issue с меткой `question` или напишите мейнтейнеру.