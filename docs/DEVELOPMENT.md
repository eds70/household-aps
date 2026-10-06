# DEVELOPMENT.md

Руководство разработчика APS Production Scheduler.

## Связанные файлы

- [README.md](../README.md) — основная документация.
- [CHANGELOG.md](../CHANGELOG.md) — история изменений.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — соглашения проекта.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура системы.
- [ROADMAP.md](ROADMAP.md) — план развития.
- [AI_WORKFLOW.md](../tools/prompts/AI_WORKFLOW.md) — работа с AI-ассистентом.
- [COLLECT_PROJECT_CHEATSHEET.md](../tools/prompts/COLLECT_PROJECT_CHEATSHEET.md) — шпаргалка по `collect_project.py`.
- [tools/check_docs.py](../tools/check_docs.py) — аудит документации.

---

## 1. Настройка окружения

### 1.1. Требования

- Python 3.12+
- Node.js 18+
- Docker 24+
- PostgreSQL 16 (в Docker)

### 1.2. Установка

Из корня проекта:

```powershell
.\quickstart.ps1
```

Скрипт выполнит:

1. Поднимет PostgreSQL в Docker.
2. Применит `init_schema.sql` и `seed_demo_data.sql`.
3. Создаст Python venv и поставит зависимости.
4. Установит npm-пакеты.
5. Создаст админа `admin@household.ru`.

Флаги:

| Флаг | Что делает |
|------|------------|
| `-SkipDb` | Не поднимать PostgreSQL |
| `-SkipSeed` | Не применять схему и демо-данные |
| `-SkipFrontend` | Не ставить npm-зависимости |
| `-Help` | Справка |

### 1.3. Запуск вручную

**Терминал 1 — Backend:**

```powershell
cd backend
..venv\Scripts\Activate.ps1
python run_server.py
```

**Терминал 2 — Frontend:**

```powershell
cd frontend
npm run dev
```

**Открыть:** http://localhost:5173

### 1.4. Настройка IDE

Рекомендуется **IntelliJ IDEA** (Ultimate или Community):

| Плагин | Назначение |
|--------|------------|
| Python | Backend |
| JavaScript and TypeScript | Frontend |
| Docker | Работа с контейнерами |
| Continue.dev | AI-ассистент |
| Markdown | Документация |

Настройки Python SDK:

- **File → Project Structure → SDKs → Add Python SDK → Existing**.
- Укажите путь к `backend\.venv\Scripts\python.exe`.
- **File → Settings → Tools → Python Integrated Tools** → default test runner = pytest.

---

## 2. Запуск тестов

### 2.1. Backend

```powershell
cd backend
..venv\Scripts\Activate.ps1
pytest tests/ -v
```

Ожидаемо: **738 passed**.

### 2.2. Frontend

```powershell
cd frontend
npm run test
npm run typecheck
npm run lint
```

### 2.3. Отдельные файлы

```powershell
# Только тесты справки
pytest tests/test_help.py -v

# Только CRUD-интеграция справки
pytest tests/test_help_crud_integration.py -v

# С фильтром по имени
pytest tests/ -k "help or crud" -v
```

### 2.4. Покрытие

```powershell
cd backend
pytest tests/ --cov=app --cov-report=html
# Открыть htmlcov/index.html
```

### 2.5. Кириллица на Windows

Если в выводе pytest «кракозябры» — см. [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Быстрая проверка:

```powershell
cd backend
python -m pytest tests/ -v --no-header -p no:cacheprovider
```

---

## Аудит документации

Проверка консистентности README / CHANGELOG / ROADMAP / API.md /
CONFIGURATION.md с исходным кодом:

```powershell
python tools\check_docs.py
```

### Что проверяется

| # | Проверка | Что сверяется |
|---|----------|---------------|
| 1 | `versions` | Версия в `README.md` ↔ верхняя секция `## [X.Y.Z]` в `CHANGELOG.md` ↔ `docs/ROADMAP.md` |
| 2 | `tests` | Число тестов в `README.md` ↔ `CHANGELOG.md` (нормализуется: `passed + skipped`) |
| 3 | `roadmap` | Таблица Roadmap в `README.md` ↔ `docs/ROADMAP.md` (номер итерации + статус) |
| 4 | `api` | Эндпоинты `backend/app/api/v1/*.py` ↔ `docs/API.md` (с учётом `APIRouter(prefix=...)`) |
| 5 | `config-env` | ENV в `backend/app/core/config.py` ↔ `docs/CONFIGURATION.md` (pydantic-settings, `case_sensitive`) |
| 6 | `config-app` | Ключи `app_settings` из `backend/migrations/*.sql` и `backend/init_schema.sql` ↔ `docs/CONFIGURATION.md` (многострочные VALUES, `ON CONFLICT`, JSONB) |

### Флаги

```powershell
python tools\check_docs.py                       # обычный режим
python tools\check_docs.py --strict              # exit 1 при warnings (для CI)
python tools\check_docs.py --api-strict          # показать эндпоинты, которых нет в docs/API.md
python tools\check_docs.py --config-mode strict  # строгий режим для config-ключей
python tools\check_docs.py --json                # машинночитаемый вывод
python tools\check_docs.py --root <путь>         # явно указать корень проекта
```

### Когда падает CI

- **`versions`** — кто-то забампил версию в `CHANGELOG.md`, но забыл в `README.md` (или наоборот).
- **`tests`** — число тестов в доке разошлось с фактическим. Обновите `README.md` и `CHANGELOG.md`.
- **`roadmap`** — таблицы Roadmap в `README.md` и `docs/ROADMAP.md` разъехались. Синхронизируйте.
- **`config-env`** — ENV описан в доке, но не читается в `config.py` (или наоборот). Проверьте опечатку.
- **`config-app`** — ключ `app_settings` описан в доке, но не найден в миграциях (или наоборот). Проверьте, что миграция применена и ключ есть в `init_schema.sql`.

### В CI

Шаг в `.github/workflows/ci.yml` (после тестов):

```yaml
      - name: Docs consistency check
        run: python tools/check_docs.py --strict
```

При рассинхронизации доков с кодом сборка упадёт **до** merge.

### Текущий статус

**0 warnings, 0 errors.** Поддерживайте этот статус — тогда CI не будет шуметь.

---

## 3. Сборка дампа проекта для AI-ассистента

См. подробное руководство в [AI_WORKFLOW.md](../tools/prompts/AI_WORKFLOW.md) и
шпаргалку по командам в [COLLECT_PROJECT_CHEATSHEET.md](../tools/prompts/COLLECT_PROJECT_CHEATSHEET.md).

### 3.1. Быстрый старт

```powershell
cd D:\Working\household-aps

# Оглавление всего проекта (~50 KB)
python collect_project.py --outline -o project_dump.txt

# README + CHANGELOG + ROADMAP (~30 KB)
python collect_project.py --files `
  README.md CHANGELOG.md docs/ROADMAP.md `
  -o project_meta.txt
```

### 3.2. Промт для нового чата

Скопируйте блок из [NEW_CHAT_PROMPT.md](../tools/prompts/NEW_CHAT_PROMPT.md) и приложите
собранные файлы через теги `<file name="...">`.

### 3.3. Полезные команды

| Задача | Команда |
|--------|---------|
| Обзор структуры | `python collect_project.py --outline` |
| Конкретные файлы | `python collect_project.py --files F1 F2 F3` |
| Поддерево | `python collect_project.py --path backend/app/scheduler` |
| Без тестов | `... --no-tests` |
| Только статистика | `... --stats-only` |
| Своё имя выхода | `... -o help_dump.txt` |

---

## 4. Как добавить миграцию

### 4.1. Создать файл

`backend/migrations/add_NN.sql`:

```sql
-- Итерация N: описание
BEGIN;

-- ... SQL ...

COMMIT;
```

**Правила:**

- Имя: `add_NN.sql` или `fix_<описание>.sql`.
- Обернуть в `BEGIN; ... COMMIT;`.
- Идемпотентность: `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`.
- Комментарий в первой строке.

### 4.2. Применить

**Правильный способ** (через `docker cp` + `psql -f`):

```powershell
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
```

**НЕ использовать** `Get-Content | docker exec` — PowerShell испортит
кириллицу.

### 4.3. Проверить

```powershell
docker exec -i aps_postgres psql -U aps -d household -c "\d table_name"
```

### 4.4. Добавить тест

`backend/tests/test_<модуль>_migration.py`:

```python
import os

MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_NN.sql"
)


def test_migration_exists():
    assert os.path.exists(MIGRATION_PATH)


def test_migration_creates_table():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE TABLE IF NOT EXISTS" in content
```

### 4.5. Обновить документацию

- `backend/migrations/README.md` — добавить строку в таблицу.
- `CHANGELOG.md` — секция `[Unreleased]`.
- `docs/OPERATIONS.md` — если добавлены команды для новой таблицы.

---

## 5. Как добавить эндпоинт

### 5.1. Создать модель (Pydantic)

`backend/app/api/v1/<module>_models.py`:

```python
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
```

### 5.2. Создать роутер

`backend/app/api/v1/<module>.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_db_session,
)
from .<module>_models import ItemResponse, ItemCreate

router = APIRouter(prefix="/api/v1/<module>", tags=["<Название>"])


@router.get("/", response_model=list[ItemResponse])
async def list_items(
    org_id=Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        text("""
            SELECT id, name, created_at FROM <table>
            WHERE organization_id = :org_id
            ORDER BY created_at DESC
        """),
        {"org_id": org_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    payload: ItemCreate,
    org_id=Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        text("""
            INSERT INTO <table> (organization_id, name)
            VALUES (:org_id, :name)
            RETURNING id, name, created_at
        """),
        {"org_id": org_id, "name": payload.name},
    )
    row = result.fetchone()
    await db.commit()
    return dict(row._mapping)
```

### 5.3. Подключить в `main.py`

```python
from app.api.v1.<module> import router as <module>_router

app.include_router(<module>_router)
```

### 5.4. Добавить в `tags_metadata`

```python
tags_metadata = [
    # ...
    {"name": "<Название>"},
]
```

### 5.5. Добавить тест

`backend/tests/test_<module>_api.py`:

```python
import inspect

from app.api.v1 import <module> as module


def test_router_prefix():
    assert module.router.prefix == "/api/v1/<module>"


def test_router_has_endpoints():
    paths = {route.path for route in module.router.routes}
    assert "/api/v1/<module>/" in paths


def test_handlers_are_async():
    assert inspect.iscoroutinefunction(module.list_items)
    assert inspect.iscoroutinefunction(module.create_item)
```

### 5.6. Обновить документацию

- `docs/API.md` — добавить эндпоинты.
- `CHANGELOG.md` — секция `[Unreleased]`.

---

## 6. Как добавить настройку

### 6.1. Добавить в `SETTINGS_REGISTRY`

`backend/app/scheduler/settings.py`:

```python
SettingSpec(
    key="my_new_setting",
    category="planning",
    label="Моя настройка",
    value_type="int",
    default=42,
    description="Что делает настройка",
    min_value=1,
    max_value=100,
    display_order=100,
),
```

### 6.2. Миграция

`backend/migrations/add_NN.sql`:

```sql
BEGIN;

INSERT INTO app_settings
(organization_id, category, setting_key, setting_value, value_type,
 label, description, min_value, max_value, display_order)
VALUES
    ('00000000-0000-0000-0000-000000000001',
     'planning', 'my_new_setting', '42', 'int',
     'Моя настройка', 'Что делает настройка',
     1, 100, 100)
ON CONFLICT (organization_id, setting_key) DO NOTHING;

COMMIT;
```

### 6.3. Применить

```powershell
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql
```

### 6.4. Проверить

```powershell
docker exec -i aps_postgres psql -U aps -d household -c "SELECT setting_key, setting_value FROM app_settings WHERE setting_key = 'my_new_setting';"
```

### 6.5. Обновить документацию

- `docs/CONFIGURATION.md` — добавить в таблицу.
- `CHANGELOG.md`.

---

## 7. Как добавить ADR

### 7.1. Создать файл

`docs/adr/NNNN-<название>.md`:

```markdown
# NNNN. Название решения

## Контекст

Почему возник вопрос.

## Решение

Что решили.

## Последствия

Что стало лучше / хуже.

## Альтернативы

Что рассматривали.

## Ссылки

- Ссылка 1
- Ссылка 2
```

### 7.2. Обновить индекс

`docs/adr/README.md` — добавить в таблицу.

### 7.3. Обновить ссылки

- `README.md` — если решение важно для пользователя.
- `CHANGELOG.md` — секция `[Unreleased]`.

---

## 8. Conventional Commits

### 8.1. Формат

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 8.2. Типы

| Тип | Когда |
|-----|-------|
| `feat` | Новая функциональность |
| `fix` | Исправление бага |
| `docs` | Только документация |
| `style` | Форматирование |
| `refactor` | Рефакторинг |
| `test` | Тесты |
| `chore` | Зависимости, конфиги |
| `perf` | Оптимизация |
| `ci` | CI/CD |

### 8.3. Scope

`scheduler`, `api`, `frontend`, `db`, `settings`, `whatif`, `cz`,
`lab`, `shift`, `personnel`, `gantt`, `snapshot`, `help`, `docs`.

### 8.4. Примеры

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

---

## 9. Как обновлять CHANGELOG

### 9.1. Формат

```
## [Unreleased]

### Added
- Новая функциональность.

### Changed
- Изменения.

### Fixed
- Исправления.
```

### 9.2. При релизе

```markdown
## [X.Y.Z] — YYYY-MM-DD

Итерация N — Название.

### Added
- ...

### Changed
- ...
```

Правила:

- `[Unreleased]` — всегда вверху.
- При релизе: переносим содержимое `[Unreleased]` в `[X.Y.Z]`,
  создаём новый пустой `[Unreleased]`.
- Формат даты: `YYYY-MM-DD`.

---

## 10. Отладка

### 10.1. Backend логи

```powershell
cd backend
python run_server.py
# Логи идут в stdout
```

Уровень логирования — в `backend/app/scheduler/logging_config.py`.

### 10.2. Запросы к БД

```powershell
docker exec -it aps_postgres psql -U aps -d household
```

Полезные команды:

```sql
-- Список таблиц
\dt

-- Структура таблицы
\d scheduled_task

-- Активные версии планов
SELECT id, name, is_active, is_archived
FROM schedule_version
WHERE organization_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC;
```

### 10.3. Frontend

DevTools → Network — смотреть запросы.
Console — ошибки.
React DevTools — компоненты и контексты.

### 10.4. Очистка кэша Vite

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

### 10.5. Ошибка `usePlan must be used within PlanProvider`

Причина: кэш Vite или неправильная структура провайдеров.

Решение: очистить `.vite` и перезапустить.

---

## 11. Полезные команды

### 11.1. БД

```powershell
# Список смен
docker exec -i aps_postgres psql -U aps -d household -c "SELECT id, name, starts_at FROM shift ORDER BY starts_at LIMIT 5;"

# Проверить статьи справки
docker exec -i aps_postgres psql -U aps -d household -c "SELECT category, COUNT(*) FROM help_article GROUP BY category ORDER BY category;"

# Проверить подсказки
docker exec -i aps_postgres psql -U aps -d household -c "SELECT hint_key, title FROM help_hint WHERE is_published = TRUE;"

# Проверить пулы
docker exec -i aps_postgres psql -U aps -d household -c "SELECT type, capacity FROM resource_pool ORDER BY type;"
```

### 11.2. Тесты

```powershell
# Все тесты
pytest tests/ -v

# Один файл
pytest tests/test_help.py -v

# По имени
pytest tests/ -k "crud" -v

# С покрытием
pytest tests/ --cov=app --cov-report=html
```

### 11.3. Миграции

```powershell
# Применить одну
docker cp backend/migrations/add_NN.sql aps_postgres:/tmp/add_NN.sql
docker exec -i aps_postgres psql -U aps -d household -f /tmp/add_NN.sql

# Применить все (в порядке номеров)
$migrations = Get-ChildItem backend/migrations/add_*.sql | Sort-Object Name
foreach ($m in $migrations) {
    docker cp $m.FullName "aps_postgres:/tmp/$($m.Name)"
    docker exec -i aps_postgres psql -U aps -d household -f "/tmp/$($m.Name)"
}
```

---

## 12. Структура проекта (краткая)

```
backend/
  app/
    api/v1/          — REST API endpoints
    auth/            — JWT авторизация
    core/            — конфигурация
    scheduler/       — ядро планировщика
  migrations/        — SQL-миграции
  tests/             — pytest
  init_schema.sql    — схема БД
  seed_demo_data.sql — демо-данные

frontend/
  src/
    components/      — React-компоненты
    context/         — React-контексты
    hooks/           — кастомные хуки
    pages/           — страницы
    services/api.ts  — HTTP-обёртки
    types/index.ts   — типы TypeScript

docs/
  ARCHITECTURE.md
  API.md
  CONFIGURATION.md
  OPERATIONS.md
  TROUBLESHOOTING.md
  DEVELOPMENT.md    — этот файл
  ROADMAP.md
  AI_WORKFLOW.md
  COLLECT_PROJECT_CHEATSHEET.md
  NEW_CHAT_PROMPT.md
  adr/

tools/
  check_docs.py     — аудит документации
  prompts/          — промты для AI-ассистента
```

---

## 13. Ссылки

- [README.md](../README.md) — основная документация.
- [CHANGELOG.md](../CHANGELOG.md) — история изменений.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — соглашения проекта.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [API.md](API.md) — REST API.
- [CONFIGURATION.md](CONFIGURATION.md) — настройки.
- [OPERATIONS.md](OPERATIONS.md) — операции с БД.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — решение проблем.
- [ROADMAP.md](ROADMAP.md) — план развития.
- [AI_WORKFLOW.md](../tools/prompts/AI_WORKFLOW.md) — работа с AI-ассистентом.
- [COLLECT_PROJECT_CHEATSHEET.md](../tools/prompts/COLLECT_PROJECT_CHEATSHEET.md) — шпаргалка по `collect_project.py`.
- [NEW_CHAT_PROMPT.md](../tools/prompts/NEW_CHAT_PROMPT.md) — промт для нового чата.
- [tools/check_docs.py](../tools/check_docs.py) — аудит документации.

---

*Последнее обновление: 2026-10-06*