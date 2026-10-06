# Development

Руководство разработчика системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Настройка IDE](#настройка-ide)
- [Запуск тестов](#запуск-тестов)
- [Как добавить миграцию](#как-добавить-миграцию)
- [Как добавить эндпоинт](#как-добавить-эндпоинт)
- [Как добавить настройку](#как-добавить-настройку)
- [Как добавить статью справки](#как-добавить-статью-справки)
- [Как добавить FAQ-статью](#как-добавить-faq-статью)
- [Как добавить контекстную подсказку](#как-добавить-контекстную-подсказку)
- [Как добавить интерактивный тур](#как-добавить-интерактивный-тур)
- [Как добавить ADR](#как-добавить-adr)
- [Conventional Commits](#conventional-commits)
- [Как обновлять CHANGELOG](#как-обновлять-changelog)
- [Полезные команды](#полезные-команды)
- [Отладка](#отладка)

---

## Настройка IDE

### VS Code (рекомендуется)

**Расширения:**

| Расширение | Назначение |
|------------|------------|
| Python | Языковая поддержка |
| Pylance | Типизация, автодополнение |
| Ruff | Линтер + форматтер |
| ESLint | Линтер для TS/JS |
| Prettier | Форматтер для TS/JS |
| Docker | Управление контейнерами |
| PostgreSQL | Подключение к БД |
| GitLens | История Git |

**`.vscode/settings.json`:**

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/Scripts/python.exe",
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.ruff": "explicit",
    "source.organizeImports.ruff": "explicit"
  },
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "**/node_modules": true,
    "**/.vite": true
  }
}
```

**`.vscode/launch.json`:**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Backend",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/backend/run_server.py",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/backend/.env"
    },
    {
      "name": "Python: Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### PyCharm

1. **File → Open** → выбрать `backend/`.
2. **Settings → Project → Python Interpreter** → выбрать `.venv`.
3. **Settings → Tools → File Watchers** → добавить Ruff.
4. **Run → Edit Configurations** → добавить `run_server.py`.

### Настройка Python-окружения

```bash
cd backend
python -m venv .venv
..venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

**`requirements-dev.txt`:**

```
pytest
pytest-asyncio
pytest-cov
httpx
ruff
black
mypy
```

---

## Запуск тестов

### Все тесты

```bash
cd backend
..venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Текущее состояние:** **714 passed**, 0 warnings.

### Конкретный файл

```bash
pytest tests/test_plan_settings_api.py -v
```

### Конкретный тест

```bash
pytest tests/test_plan_settings_api.py::test_get_settings -v
```

### С покрытием

```bash
pytest tests/ --cov=app --cov-report=html
```

Открыть `htmlcov/index.html`.

### Только быстрые тесты (без solver)

```bash
pytest tests/ -v -m "not slow"
```

### Параллельно (pytest-xdist)

```bash
pytest tests/ -v -n auto
```

### Фильтр по имени

```bash
pytest tests/ -v -k "plan_settings"
```

### Логирование

```bash
pytest tests/ -v --log-cli-level=DEBUG
```

### Структура тестов

| Файл | Что проверяет |
|------|---------------|
| `test_tz_case.py` | Эталонный кейс ТЗ |
| `test_materials.py` | Расчёт потребности в сырье |
| `test_materials_stock.py` | Остатки материалов (13.1) |
| `test_material_stock_log.py` | Журнал остатков (13.2–13.3) |
| `test_material_import.py` | Импорт/экспорт Excel (13.2) |
| `test_advisor.py` | Подсказки Advisor |
| `test_routing.py` | Цепочки операций |
| `test_shifts.py` | Смены и API |
| `test_rescheduler.py` | Перепланирование (9, A3) |
| `test_rescheduler_uses_plan_settings.py` | Rescheduler + version_id (13.14) |
| `test_reschedule_cascade.py` | Каскадный сдвиг (13.17) |
| `test_lab.py` | Лабораторные блокировки |
| `test_personnel.py` | Люди как ресурс |
| `test_cooling_degradation.py` | Охлаждение |
| `test_cz.py` | Честный Знак |
| `test_whatif.py` | What-if сценарии |
| `test_whatif_uses_plan_settings.py` | Whatif + version_id (13.14) |
| `test_plan_settings_models.py` | Модели plan_settings |
| `test_plan_settings_api.py` | API plan_settings |
| `test_plan_settings_migration.py` | Миграция add_21.sql |
| `test_plan_settings_integration.py` | Интеграция plan_settings |
| `test_plan_settings_data_loader.py` | DataLoader + version_id |
| `test_snapshot.py` | Модуль snapshot (13.15) |
| `test_schedule_create_version.py` | Создание версии + снапшоты (13.15) |
| `test_saver_uses_snapshot.py` | saver → snapshot_all_catalogs (13.15) |
| `test_schedule_versions_archive.py` | Архивация версий (13.21) |
| `test_audit.py` | API аудита (13.3) |
| `test_audit_models.py` | Модели аудита (13.3) |
| `test_versions.py` | Версии планов (5h) |
| `test_help.py` | Встроенная справка + CRUD (15.1, 15.5) |
| `test_help_hints.py` | Контекстные подсказки (15.2) |
| `test_help_faq.py` | FAQ-статьи (15.4) |
| `test_help_crud_integration.py` | Интеграция CRUD справки (15.5) |
| `test_dependencies.py` | Auth dependencies |
| `test_auth_models.py` | Auth models |
| `test_security.py` | Security utilities |
| `test_config.py` | Конфигурация |

---

## Как добавить миграцию

### 1. Создать файл

`backend/migrations/add_NN.sql`, где `NN` — следующий номер.

### 2. Обернуть в транзакцию

```sql
-- Итерация N: описание
BEGIN;

-- ... SQL ...

COMMIT;
```

### 3. Сделать идемпотентной

```sql
CREATE TABLE IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;
INSERT INTO ... ON CONFLICT DO NOTHING;
```

### 4. Применить

```bash
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
```

### 5. Проверить

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'new_table'
);
"
```

### 6. Добавить тест

`tests/test_<модуль>_migration.py`:

```python
import pytest
from pathlib import Path

def test_migration_file_exists():
    migration = Path("migrations/add_NN.sql")
    assert migration.exists()

def test_migration_is_idempotent():
    sql = Path("migrations/add_NN.sql").read_text()
    assert "IF NOT EXISTS" in sql
    assert "ON CONFLICT DO NOTHING" in sql

def test_migration_wrapped_in_transaction():
    sql = Path("migrations/add_NN.sql").read_text()
    assert sql.strip().startswith("--")
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
```

### 7. Обновить CHANGELOG

См. [Как обновлять CHANGELOG](#как-обновлять-changelog).

### Пример: миграция `add_26_seed_1.sql` (FAQ, Итерация 15.4)

**Важно:** FAQ **не создаёт новых таблиц** — используется существующая
`help_article` (миграция `add_24.sql`). FAQ-миграции — это **только seed**:

```sql
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
(NULL, 'faq-plan-feasible-not-optimal',
 'План получился FEASIBLE, а не OPTIMAL — что делать?',
 'faq',
 $md$# План FEASIBLE, а не OPTIMAL

**Категория:** FAQ

**Симптом:** В ответе `/schedule/build` приходит `status: "FEASIBLE"`.

## Причина

Solver не успел найти оптимальное решение за `timeout_seconds`.

## Что делать

1. Увеличить `timeout_seconds` (до 1800 сек).
2. Уменьшить `horizon_hours`.
3. Уменьшить число pinned-задач.
$md$,
 '["faq", "solver", "optimal", "feasible", "timeout"]'::jsonb,
 10, TRUE)
ON CONFLICT (slug) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS seeded FROM help_article
WHERE slug = 'faq-plan-feasible-not-optimal';
-- Ожидаемо: 1
```

**Структура FAQ-статьи (единый формат):**

1. **Категория** — FAQ.
2. **Симптом** — что видит пользователь.
3. **Причина** — почему так происходит.
4. **Что делать** — варианты решения (по приоритету).
5. **Проверка** — SQL-запросы для диагностики.
6. **Связанные статьи** — ссылки на 2-3 других статьи.

**Тесты:** см. `tests/test_help_faq.py`.

---

## Как добавить эндпоинт

### 1. Определить Pydantic-модели

`backend/app/api/v1/<module>_models.py`:

```python
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

class ItemResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: str
```

### 2. Реализовать роутер

`backend/app/api/v1/<module>.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.<module>_models import ItemCreate, ItemResponse
from app.auth.dependencies import get_current_user, require_role
from app.core.database import get_db
from app.auth.models import User

router = APIRouter(prefix="/api/v1/<module>", tags=["<module>"])

@router.get("/", response_model=list[ItemResponse])
async def list_items(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Список элементов."""
    ...

@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("ADMIN", "PLANNER")),
):
    """Создать элемент."""
    ...
```

### 3. Подключить в `main.py`

`backend/app/main.py`:

```python
from app.api.v1.<module> import router as <module>_router

app.include_router(<module>_router)
```

### 4. Добавить тест

`tests/test_<module>_api.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_items(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/<module>/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_item(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/<module>/",
        json={"name": "Test"},
        headers=auth_headers,
    )
    assert response.status_code == 201
```

### 5. Обновить документацию

- `docs/API.md` — добавить эндпоинты.
- `README.md` — если эндпоинт ключевой.
- `CHANGELOG.md` — добавить в `[Unreleased]`.

### Пример с `version_id`

Если эндпоинт зависит от настроек плана:

```python
from uuid import UUID
from typing import Optional

@router.get("/")
async def list_items(
    version_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = await read_settings_dict(
        db, user.organization_id,
        ["enable_something"],
        version_id=version_id,
    )
    ...
```

### Пример: CRUD-эндпоинты справки (Итерация 15.5)

**`POST /api/v1/help/articles` — создание статьи (ADMIN):**

```python
@router.post("/articles", response_model=HelpArticleResponse, status_code=201)
async def create_article(
    payload: HelpArticleCreate,
    current_user: dict = Depends(require_admin),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db_session),
):
    # 1. Проверка category ∈ CATEGORY_LABELS
    # 2. Slug: если не задан — _slugify(title). Если занят — 409.
    # 3. display_order: если None — _next_display_order(category)
    # 4. INSERT с organization_id = org_id
    # 5. Теги сериализуются в JSONB
    ...
```

**Ключевые хелперы:**

- `_slugify(text)` — генерация slug из title (транслитерация RU→EN).
- `_check_slug_conflict(db, slug, exclude_id=None)` — проверка уникальности.
- `_next_display_order(db, category)` — авто-`display_order` (`max+10`).

Все CRUD-эндпоинты защищены `Depends(require_admin)`.

---

## Как добавить настройку

### 1. Добавить в `SETTINGS_REGISTRY`

`backend/app/scheduler/settings.py`:

```python
SETTINGS_REGISTRY = {
    # ...
    "my_new_setting": {
        "category": "planning",
        "value_type": "int",
        "default": 100,
        "min_value": 1,
        "max_value": 1000,
        "label": "Моя настройка",
        "description": "Описание настройки",
        "is_system": False,
        "display_order": 100,
    },
}
```

### 2. Добавить в миграцию

Новый SQL-файл или `INSERT` в существующий:

```sql
INSERT INTO app_settings (
    organization_id, setting_key, setting_value,
    value_type, category, label, description,
    min_value, max_value, display_order, is_system
)
SELECT
    id, 'my_new_setting', '100'::jsonb,
    'int', 'planning', 'Моя настройка', 'Описание настройки',
    1, 1000, 100, FALSE
FROM organization
ON CONFLICT (organization_id, setting_key) DO NOTHING;
```

### 3. Прочитать в коде

```python
from app.scheduler.settings_reader import read_setting

value = await read_setting(
    db, org_id,
    "my_new_setting",
    default=100,
    version_id=version_id,
)
```

### 4. Добавить в UI

`frontend/src/pages/SettingsPage.tsx` — настройка появится автоматически, если она в `SETTINGS_REGISTRY`.

`frontend/src/pages/PlanSettingsWizard.tsx` — если категория включена в мастер.

### 5. Добавить тест

```python
@pytest.mark.asyncio
async def test_my_new_setting(db_session, org_id):
    from app.scheduler.settings_reader import read_setting
    value = await read_setting(db_session, org_id, "my_new_setting", default=0)
    assert value == 100
```

---

## Как добавить статью справки

**Итерация 15.1.**

### 1. Создать seed-файл

`backend/migrations/add_NN_seed_M.sql`, где `NN` — номер миграции, `M` — номер seed-пакета.

### 2. Структура

```sql
-- ==========================================
-- SEED M/N: СПРАВКА — <НАЗВАНИЕ>
-- ==========================================
-- Добавляет N новых статей в категорию '<category>'.
--
-- Идемпотентна: ON CONFLICT (slug) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_article
    (organization_id, slug, title, category, content_md, tags,
     display_order, is_published)
VALUES
    (NULL, 'my-article-slug', 'Заголовок статьи', 'planning',
     $md$# Заголовок статьи

Текст статьи в **markdown**.

- Список
- Ещё пункт

| Колонка 1 | Колонка 2 |
|-----------|-----------|
| Значение  | Значение  |
$md$,
     '["тег1", "тег2"]'::jsonb,
     100, TRUE)
    ON CONFLICT (slug) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS seeded FROM help_article
WHERE slug = 'my-article-slug';
-- Ожидаемо: 1
```

### 3. Категории

Доступные категории:

| Ключ | Название |
|------|----------|
| `getting-started` | Начало работы |
| `planning` | Планирование |
| `gantt` | Диаграмма Ганта |
| `shift` | Мастера смены |
| `lab` | Лаборатория |
| `cz` | Честный Знак |
| `whatif` | What-if |
| `settings` | Настройки |
| `faq` | FAQ |

### 4. Применить

```bash
docker cp backend/migrations/add_NN_seed_M.sql aps_postgres:/tmp/add_NN_seed_M.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN_seed_M.sql
```

### 5. Добавить тест

`tests/test_help.py`:

```python
def test_seed_file_exists():
    path = Path("migrations/add_NN_seed_M.sql")
    assert path.exists()

def test_seed_contains_slug():
    sql = Path("migrations/add_NN_seed_M.sql").read_text()
    assert "'my-article-slug'" in sql
```

### 6. Альтернатива: редактирование через UI (Итерация 15.5)

**С 15.5** статьи можно создавать/редактировать через UI (**ADMIN**),
без SQL-миграций. Seed-миграции остаются для **глобальных** статей
(`organization_id = NULL`), а UI работает только со статьями **текущей
организации**.

| | Seed-миграция | UI-редактор (15.5) |
|--|---------------|---------------------|
| Права | Только разработчик (SQL) | ADMIN |
| organization_id | `NULL` (глобальная) | `= org_id` |
| Отображение | Видна всем | Видна только своей org |
| Авто-slug | Нет (задаётся вручную) | Да (`_slugify` из title) |
| Предпросмотр | Нет | Да (`HelpArticleEditor`) |

**UI:** `HelpPage` → кнопка **«Новая статья»** → форма с вкладками
«Редактор» / «Предпросмотр» → «Сохранить».

---

## Как добавить FAQ-статью

**Итерация 15.4.**

FAQ — это **категория** `faq` в существующей таблице `help_article`.
Отдельной таблицы/API/фронтенда **не требуется**.

### 1. Создать seed-файл

`backend/migrations/add_NN_seed_M.sql`, где `NN` — номер миграции, `M` — номер seed-пакета.

### 2. Структура (единый формат FAQ-статьи)

```sql
-- ==========================================
-- SEED M/N: СПРАВКА — FAQ (<ТЕМА>)
-- ==========================================
-- Добавляет N FAQ-статей в категорию 'faq'.
-- Все — глобальные (organization_id = NULL).
--
-- Идемпотентна: ON CONFLICT (slug) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_article
(organization_id, slug, title, category, content_md, tags,
 display_order, is_published)
VALUES
(NULL,
 'faq-my-problem-slug',
 'Короткий вопрос или проблема',
 'faq',
 $md$# Заголовок статьи

**Категория:** FAQ

**Симптом:** Что видит пользователь.

## Причина

Почему так происходит. 1-3 абзаца.

## Что делать

### Вариант 1: Первое решение

Пошаговая инструкция.

### Вариант 2: Второе решение

Пошаговая инструкция.

## Проверка

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT ...;"
```

## Связанные статьи

- [Название 1](/help/slug-1)
- [Название 2](/help/slug-2)
  $md$,
  '["faq", "тег1", "тег2"]'::jsonb,
  100, TRUE)
  ON CONFLICT (slug) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS seeded FROM help_article
WHERE slug = 'faq-my-problem-slug';
-- Ожидаемо: 1
```

### 3. Обязательные разделы

Каждая FAQ-статья **должна** содержать:

| Раздел | Обязателен? | Описание |
|--------|-------------|----------|
| `**Категория:** FAQ` | ✅ | Явно указать категорию |
| `**Симптом:**` | ✅ | Что видит пользователь |
| `## Причина` | ✅ | Почему так происходит |
| `## Что делать` | ✅ | Варианты решения (по приоритету) |
| `## Проверка` | ⚠️ опционально | SQL-запросы для диагностики |
| `## Связанные статьи` | ✅ | 2-3 ссылки на другие статьи |

### 4. Правила именования slug

- **Префикс `faq-`** — обязателен.
- **kebab-case** — только `a-z`, `0-9`, дефисы.
- **Длина ≤ 100** символов (ограничение `VARCHAR(100)`).
- **Описательный** — по симптому, а не по решению.

**Примеры:**
- ✅ `faq-plan-feasible-not-optimal`
- ✅ `faq-task-not-movable`
- ❌ `plan-feasible` (нет префикса)
- ❌ `faq_plan_feasible` (подчёркивания)

### 5. Применить

```bash
docker cp backend/migrations/add_NN_seed_M.sql aps_postgres:/tmp/add_NN_seed_M.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN_seed_M.sql
```

### 6. Проверить

```bash
docker exec -i aps_postgres psql -U aps -d household -c "
SELECT slug, title FROM help_article
WHERE category = 'faq' AND slug = 'faq-my-problem-slug';
"
```

### 7. Добавить тесты

`tests/test_help_faq.py`:

```python
EXPECTED_FAQ_SLUGS = [
    # ... существующие 15 ...
    "faq-my-problem-slug",
]

def test_all_faq_slugs_present():
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)
    for slug in EXPECTED_FAQ_SLUGS:
        assert f"'{slug}'" in all_content, f"Slug '{slug}' не найден"

def test_faq_articles_have_symptom_section():
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)
    symptoms = all_content.count("**Симптом:**")
    assert symptoms == 16  # было 15, стало 16
```

### 8. Обновить `test_help_faq.py` при добавлении

- Обновить `EXPECTED_FAQ_SLUGS` (добавить новый slug).
- Обновить ожидаемые счётчики (`15` → `16`, если добавляется одна статья).
- Обновить `README.md`, `CHANGELOG.md`, `docs/ROADMAP.md`.

### Ключевые гарантии

- ✅ **Не создаёт новых таблиц** — использует `help_article`.
- ✅ **Не требует миграции API** — `/categories` автоматически вернёт `faq`.
- ✅ **Фронт не меняется** — `HelpPage` подхватывает категорию.
- ✅ **Идемпотентность** — `ON CONFLICT (slug) DO NOTHING`.
- ✅ **Ссылки валидируются** — тест `test_faq_articles_link_to_existing_slugs`.

---

## Как добавить контекстную подсказку

**Итерация 15.2.**

### 1. Создать seed-файл

`backend/migrations/add_NN_seed_M.sql`, где `NN` — номер миграции, `M` — номер seed-пакета.

### 2. Структура

```sql
-- ==========================================
-- SEED M/N: КОНТЕКСТНЫЕ ПОДСКАЗКИ
-- ==========================================
-- Добавляет новые подсказки в таблицу help_hint.
--
-- Идемпотентна: ON CONFLICT (hint_key) DO NOTHING.
-- ==========================================

BEGIN;

INSERT INTO help_hint
    (organization_id, hint_key, title, body_md, article_slug,
     display_order, is_published)
VALUES
    (NULL, 'my_module.my_action', 'Заголовок подсказки',
     $md$Короткое описание **2-3 предложения**. Не отвлекает пользователя.$md$,
     'my-article-slug',
     100, TRUE)
    ON CONFLICT (hint_key) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS seeded FROM help_hint
WHERE hint_key = 'my_module.my_action';
-- Ожидаемо: 1
```

### 3. Формат `hint_key`

- Строго `<module>.<action>` в lowercase: `planning.recalc`, `gantt.edit_mode`.
- Точка — разделитель. Не использовать подчёркивания в `module` и `action`.

### 4. `article_slug`

Опционально. Если задан — в Popover появится кнопка «Читать подробнее»,
ведущая на `/help/{slug}`. Убедитесь, что slug существует в `help_article`.

### 5. Применить

```bash
docker cp backend/migrations/add_NN_seed_M.sql aps_postgres:/tmp/add_NN_seed_M.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN_seed_M.sql
```

### 6. Использовать в коде (frontend)

```tsx
import Hint from '../components/help/Hint';

<Box>
    <Typography>
        Пересчёт плана
        <Hint id="planning.recalc" size="small"/>
    </Typography>
</Box>
```

**Правила:**

- Если подсказки нет в БД — `<Hint/>` рендерит `null` (безопасно).
- `<Hint/>` читает кэш из `HelpHintsContext` — перезагрузка страницы не нужна.
- Размер: `small` (14px) или `medium` (18px).

### 7. Добавить тест

`tests/test_help_hints.py`:

```python
def test_seed_file_exists():
    path = Path("migrations/add_NN_seed_M.sql")
    assert path.exists()

def test_seed_contains_hint_key():
    sql = Path("migrations/add_NN_seed_M.sql").read_text()
    assert "'my_module.my_action'" in sql

def test_seed_links_to_existing_article():
    # Проверяем, что article_slug существует в add_24_seed_*
    ...
```

---

## Как добавить интерактивный тур

**Итерация 15.3.**

### 1. Добавить тур в `tours.ts`

`frontend/src/tutorial/tours.ts`:

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
            placement: 'bottom',
        },
        // ...
    ],
    // Итерация 15.3 (fix): маршруты для навигации между шагами
    stepRoutes: [
        '/equipment',       // шаг 0
        '/products',        // шаг 1
        '/schedule',        // шаг 2
        // null — остаёмся на текущей странице
    ],
}
```

### 2. Добавить `data-tour-id` в UI

В компоненте, который должен подсвечиваться:

```tsx
<Button
    data-tour-id="my-target"
    onClick={...}
>
    Кнопка
</Button>
```

### 3. Правила

- `target` — CSS-селектор. Обычно `[data-tour-id="..."]`.
- `content` — короткий текст (1-2 предложения).
- `placement` — `'top' | 'bottom' | 'left' | 'right' | 'center'`.
- `stepRoutes[stepIndex]` — маршрут, куда нужно перейти перед показом шага.
  Если `null` — остаёмся на текущей странице.
- `id` тура — уникальный (используется в `localStorage`).

### 4. Добавить тест

`frontend/src/tutorial/__tests__/tours.test.ts`:

```typescript
import {ALL_TOURS, getTourById} from '../tours';

describe('tours', () => {
    it('все туры имеют уникальные id', () => {
        const ids = ALL_TOURS.map(t => t.id);
        expect(new Set(ids).size).toBe(ids.length);
    });

    it('у каждого шага есть target и content', () => {
        for (const tour of ALL_TOURS) {
            for (const step of tour.steps) {
                expect(step.target).toBeTruthy();
                expect(step.content).toBeTruthy();
            }
        }
    });
});
```

### 5. Обновить статью `tutorial-interactive`

Если добавляется новый тур — обновить seed-миграцию
`add_27_seed_1.sql` или создать новую, добавив ссылку на тур.

### 6. Прогресс

Хранится в `localStorage`:

- Ключ: `aps_tutorial_completed_<tour_id>`.
- Значение: `'true'`.

**Сброс:** `HelpPage` → «Интерактивные туры» → «Пройти заново».

---

## Как добавить ADR

### 1. Создать файл

`docs/adr/NNNN-<название>.md`, где `NNNN` — следующий номер (0001, 0002, ...).

### 2. Формат

```markdown
# NNNN. Название решения

**Дата:** 2026-09-25
**Статус:** Принято
**Контекст:** Итерация 15.1

## Контекст

Описание проблемы, которая требует решения.

## Решение

Описание принятого решения.

## Последствия

### Положительные

- ...

### Отрицательные

- ...

### Альтернативы

- **Альтернатива 1:** почему отклонена.
- **Альтернатива 2:** почему отклонена.

## Ссылки

- [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- [README.md](../README.md)
```

### 3. Обновить индекс

`docs/adr/README.md`:

```markdown
| # | Название | Статус |
|---|----------|--------|
| 0001 | [Use OR-Tools CP-SAT](0001-use-ortools-cp-sat.md) | Принято |
| 0002 | [Snapshot tables for versioning](0002-snapshot-tables-for-versioning.md) | Принято |
| 0003 | [Plan settings per plan](0003-plan-settings-per-plan.md) | Принято |
| 0004 | [What-if two transactions](0004-whatif-two-transactions.md) | Принято |
| 0005 | [Help system](0005-help-system.md) | Принято |
| 0006 | [Новое решение](0006-new-decision.md) | Принято |
```

### 4. Обновить CHANGELOG

```markdown
### Added
- ADR 0006: Новое решение.
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
| `style` | Форматирование |
| `refactor` | Рефакторинг |
| `test` | Тесты |
| `chore` | Зависимости, конфиги |
| `perf` | Производительность |
| `ci` | CI/CD |

### Scope

`scheduler`, `api`, `frontend`, `db`, `settings`, `whatif`, `cz`, `lab`,
`shift`, `personnel`, `gantt`, `snapshot`, `help`, `docs`.

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
feat(help): add interactive tutorial (iteration 15.3)

- Библиотека react-joyride
- Конфигурация туров в tutorial/tours.ts
- TutorialContext, TutorialProvider, TutorialRunner
- Статья tutorial-interactive (add_27_seed_1.sql)
- +18 тестов, всего 643 passed
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

---

## Как обновлять CHANGELOG

### 1. Открыть `CHANGELOG.md`

### 2. Добавить запись в `[Unreleased]`

```markdown
## [Unreleased]

### Added
- Новая функциональность.

### Changed
- Изменение в существующей функциональности.

### Fixed
- Исправление бага.
```

### 3. При релизе — перенести в новую версию

```markdown
## [4.8.0] — 2026-10-06

### Added
- ...
```

И создать новый `[Unreleased]`:

```markdown
## [Unreleased]

### Added
- Заготовка для следующей итерации.
```

### 4. Следовать Keep a Changelog

- **Added** — новая функциональность.
- **Changed** — изменения.
- **Deprecated** — будет удалено.
- **Removed** — удалено.
- **Fixed** — исправления.
- **Security** — уязвимости.

### 5. Группировать по итерациям

```markdown
### Added

#### Итерация 15.4 — FAQ и расширение базы знаний

- ...
```

---

## Полезные команды

### Backend

```bash
# Активировать окружение
cd backend
..venv\Scripts\Activate.ps1

# Запустить сервер
python run_server.py

# Запустить тесты
pytest tests/ -v

# Линтер
ruff check app/ tests/

# Форматтер
ruff format app/ tests/
# или
black app/ tests/

# Типизация
mypy app/

# Очистить кэш
Get-ChildItem -Path "app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Создать админа
python -m scripts.create_admin_user

# Демо-данные
python seed_demo.py
```

### Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev-сервер
npm run dev

# Собрать
npm run build

# Линтер
npm run lint

# Типизация
npm run typecheck

# Форматтер
npm run format

# Очистить кэш
Remove-Item -Recurse -Force node_modules\.vite
```

### База данных

```bash
# Подключиться
docker exec -it aps_postgres psql -U aps -d household

# Применить миграцию
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql

# Бэкап
docker exec aps_postgres pg_dump -U aps household > backup.sql

# Восстановить
docker exec -i aps_postgres psql -U aps -d household < backup.sql

# Пересоздать схему
docker exec aps_postgres psql -U aps -d household -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

**Проверка справки (Итерация 15.1):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT COUNT(*) AS help_articles FROM help_article;"
```

Ожидаемо: 31 (15 базовых + 1 туториал + 15 FAQ).

**Проверка подсказок (Итерация 15.2):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT hint_key, title FROM help_hint WHERE is_published = TRUE ORDER BY display_order;"
```

Ожидаемо: 8 подсказок.

**Проверка связи hint → article:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT h.hint_key, h.article_slug, CASE WHEN a.slug IS NULL THEN '❌ NOT FOUND' ELSE '✅ OK' END AS status FROM help_hint h LEFT JOIN help_article a ON a.slug = h.article_slug WHERE h.article_slug IS NOT NULL ORDER BY h.hint_key;"
```

Все должны быть `✅ OK`.

**Проверка FAQ-статей (Итерация 15.4):**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT slug, title FROM help_article WHERE category = 'faq' ORDER BY display_order;"
```

Ожидаемо: 15 статей с префиксом `faq-`.

**Проверка, что все FAQ глобальные:**

```bash
docker exec -i aps_postgres psql -U aps -d household -c "SELECT COUNT(*) FROM help_article WHERE category = 'faq' AND organization_id IS NULL;"
```

Ожидаемо: 15.

### Git

```bash
# Создать ветку
git checkout -b feature/iteration-15-help

# Коммит
git add .
git commit -m "feat(scheduler): add plan_settings support"

# Пуш
git push origin feature/iteration-15-help

# Обновить от main
git checkout main
git pull
git checkout feature/iteration-15-help
git rebase main
```

---

## Отладка

### Backend

**Логирование:**

```python
from app.scheduler.logging_config import get_logger
logger = get_logger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

**Точка останова (VS Code):**

```python
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

**SQL-логирование:**

```python
# В .env
LOG_LEVEL=DEBUG
```

**Отладка snapshot.py (Итерация 13.15):**

В логах backend при создании плана появляются строки:
```
[snapshot] Старт заполнения снапшотов для version=abcd1234
[snapshot] Готово для version=abcd1234: equipment=10, products=7, operations=27, calendar=5
```

Если этих строк нет — проверьте, что `snapshot_all_catalogs` действительно вызывается.

**Отладка архивации (Итерация 13.21):**

В логах backend:
```
Версия abcd1234 'План на октябрь' перемещена в архив
Версия abcd1234 'План на октябрь' не архивирована: Используется в what-if сценариях: ...
```

**Отладка справки (Итерация 15.1):**

В логах backend:
```
[app.api.help] Загружено статей: 31
```

Если статей 0 — проверьте seed-миграции.

**Отладка подсказок (Итерация 15.2):**

Проверьте эндпоинт:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/help/hints
```

В ответе должен быть словарь `hints` с 8 ключами (`planning.recalc`, `planning.advisor`, и т.д.).

В логах backend при загрузке приложения:
```
[HelpHints] Не удалось загрузить подсказки: ...
```

(Эта ошибка — «тихая», не ломает UI.)

**Отладка FAQ (Итерация 15.4):**

Проверьте эндпоинт `/categories`:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/help/categories
```

В ответе должна быть категория `faq` с `article_count: 15`:

```json
{
  "categories": [
    ...
    {"key": "faq", "label": "FAQ", "article_count": 15}
  ]
}
```

Проверьте эндпоинт `/articles?category=faq`:

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/help/articles?category=faq"
```

В ответе должно быть 15 статей.

Если FAQ-статей нет:
1. Проверьте, что применены `add_26_seed_1/2/3.sql`.
2. Проверьте, что `help.py` содержит `faq` в `CATEGORY_LABELS` и `CATEGORY_ORDER`.
3. Перезапустите backend.

**Отладка CRUD справки (Итерация 15.5):**

Проверьте, что у пользователя роль ADMIN:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me | jq '.role'
```

Должно быть `"ADMIN"`. Иначе CRUD-эндпоинты вернут `403`.

Проверьте создание статьи:

```bash
curl -X POST http://localhost:8000/api/v1/help/articles \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Тест", "category": "planning", "content_md": "body"}'
```

Должен вернуть `201` с автогенерированным slug.

**Отладка тестов:**

```bash
# Запустить только FAQ-тесты
pytest tests/test_help_faq.py -v

# С логированием
pytest tests/test_help_faq.py -v --log-cli-level=DEBUG

# Только конкретный тест
pytest tests/test_help_faq.py::test_all_15_faq_slugs_present -v
```

### Frontend

**React DevTools** — расширение браузера.

**Console:**

```tsx
console.log('Debug:', value);
console.debug('Debug:', value);
console.warn('Warning:', value);
console.error('Error:', value);
```

**Отладка `has_snapshot`:**

В React DevTools выберите `PlanProvider` — увидите `currentPlan` с полем `has_snapshot`. Если `has_snapshot: false` — план пуст.

**Отладка `planDirty` (Итерация 13.19):**

В React DevTools выберите `PlanProvider` — увидите `planDirty`. Если `true` — кнопка «Пересчитать» активна.

**Отладка `localEditMode` (Итерация 14.2):**

В React DevTools выберите `PlanProvider` — увидите `localEditMode`. Если `false` — readonly-режим, задачи не таскаются.

**Отладка подсказок (Итерация 15.2):**

1. В React DevTools выберите `HelpHintsProvider` — увидите поле `hints` (словарь) и `loading`.
2. Если `hints` пуст — проверьте в Network-вкладке запрос `GET /api/v1/help/hints`.
3. Если статус 200, но `hints` пуст — значит, в БД нет подсказок.
4. Если статус 404 — не подключён `help_router` в `main.py`.
5. Если компонент `<Hint/>` возвращает `null` — проверьте, что `hint_key` в JSX совпадает с `hint_key` в БД.

**Проверка подсказки в консоли:**

```tsx
// В любом компоненте внутри HelpHintsProvider
import { useHelpHints } from '../context/HelpHintsContext';

const { hints } = useHelpHints();
console.log('Все подсказки:', Object.keys(hints));
```

**Отладка FAQ (Итерация 15.4):**

FAQ-статьи — это обычные статьи в `HelpSidebar` (категория `faq`). Проверьте в React DevTools:

1. В `HelpPage` → `HelpSidebar` → `categories` — должна быть запись `{key: 'faq', label: 'FAQ', article_count: 15}`.
2. В `articlesByCategory['faq']` — массив из 15 статей.

Если категории `faq` нет:
1. Проверьте Network-вкладку — запрос `GET /api/v1/help/categories`.
2. В ответе должна быть категория `faq`.
3. Если нет — см. «Отладка FAQ» в разделе Backend.

**Отладка туров (Итерация 15.3):**

1. В React DevTools выберите `TutorialProvider` — увидите `activeTour` и `currentStepIndex`.
2. Если тур не запускается — проверьте `localStorage` ключ `aps_tutorial_completed_<tour_id>`.
3. Если элемент не подсвечивается — проверьте, что `data-tour-id` в DOM совпадает с `target` в `tours.ts`.

**Сброс прогресса тура:**

```javascript
// DevTools → Console
localStorage.removeItem('aps_tutorial_completed_getting-started');
location.reload();
```

**Отладка CRUD справки (Итерация 15.5):**

1. Проверьте роль пользователя: `user.role === 'ADMIN'`.
2. Если кнопка «Новая статья» не появляется — проверьте, что `isAdmin` истинно.
3. Если редактор не открывается — проверьте, что `HelpArticleEditor` импортирован в `HelpPage`.
4. Если сохранение падает с `409` — slug уже занят, используйте другой.

### Solver

**Логирование CP-SAT:**

```python
solver.parameters.log_search_progress = True
```

**Статус решения:**

```python
status = solver.StatusName(response.status)
print(f"Solver status: {status}")
print(f"Objective: {response.objective_value}")
print(f"Wall time: {response.wall_time} sec")
```

---

## Ссылки

- [README.md](../README.md) — основная документация.
- [CHANGELOG.md](../CHANGELOG.md) — история изменений.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — как внести вклад.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/API.md](API.md) — описание API.
- [docs/CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [docs/OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [docs/ROADMAP.md](ROADMAP.md) — план развития.
- [docs/adr/README.md](adr/README.md) — индекс ADR.