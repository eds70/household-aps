# Development

Руководство разработчика системы **APS Production Scheduler**.

---

## 📋 Содержание

- [Настройка IDE](#настройка-ide)
- [Запуск тестов](#запуск-тестов)
- [Как добавить миграцию](#как-добавить-миграцию)
- [Как добавить эндпоинт](#как-добавить-эндпоинт)
- [Как добавить настройку](#как-добавить-настройку)
- [Как добавить ADR](#как-добавить-adr)
- [Conventional Commits](#conventional-commits)
- [Как обновлять CHANGELOG](#как-обновлять-changelog)
- [Полезные команды](#полезные-команды)

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

**Текущее состояние:** **535 passed**, 13 warnings.

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
| `test_advisor.py` | Подсказки Advisor |
| `test_routing.py` | Цепочки операций |
| `test_shifts.py` | Смены и API |
| `test_rescheduler.py` | Перепланирование |
| `test_lab.py` | Лабораторные блокировки |
| `test_personnel.py` | Люди как ресурс |
| `test_cooling_degradation.py` | Охлаждение |
| `test_cz.py` | Честный Знак |
| `test_whatif.py` | What-if сценарии |
| `test_plan_settings_*.py` | plan_settings |
| `test_rescheduler_uses_plan_settings.py` | rescheduler + version_id |
| `test_whatif_uses_plan_settings.py` | whatif + version_id |
| `test_audit.py` | API аудита |
| `test_audit_models.py` | Модели аудита |
| `test_material_import.py` | Импорт/экспорт Excel |
| `test_material_stock_log.py` | Журнал остатков |
| `test_materials_stock.py` | Остатки материалов |
| **`test_snapshot.py`** | **Модуль snapshot (13.15)** |
| **`test_schedule_create_version.py`** | **Создание версии + снапшоты (13.15)** |
| **`test_saver_uses_snapshot.py`** | **saver → snapshot_all_catalogs (13.15)** |

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

### Пример: миграция `add_21.sql` (plan_settings)

```sql
-- Итерация 13.14: plan_settings
BEGIN;

CREATE TABLE IF NOT EXISTS plan_settings (
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

CREATE INDEX IF NOT EXISTS idx_plan_settings_version
    ON plan_settings (schedule_version_id);

CREATE INDEX IF NOT EXISTS idx_plan_settings_org_category
    ON plan_settings (organization_id, category);

-- Триггер: копирование app_settings в plan_settings при создании плана
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

DROP TRIGGER IF EXISTS trg_copy_app_settings_to_plan ON schedule_version;
CREATE TRIGGER trg_copy_app_settings_to_plan
    AFTER INSERT ON schedule_version
    FOR EACH ROW
    EXECUTE FUNCTION copy_app_settings_to_plan();

COMMIT;
```

**Итерация 13.15 не требует миграции** — используются уже существующие снапшот-таблицы.

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

## Как добавить ADR

### 1. Создать файл

`docs/adr/NNNN-<название>.md`, где `NNNN` — следующий номер (0001, 0002, ...).

### 2. Формат

```markdown
# NNNN. Название решения

**Дата:** 2026-09-25
**Статус:** Принято
**Контекст:** Итерация 13.14

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
| 0005 | [Новое решение](0005-new-decision.md) | Принято |
```

### 4. Обновить CHANGELOG

```markdown
### Added
- ADR 0005: Новое решение.
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

`scheduler`, `api`, `frontend`, `db`, `settings`, `whatif`, `cz`, `lab`, `shift`, `personnel`, `gantt`, `snapshot`, `docs`.

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
## [4.2.0] — 2026-10-01

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

#### Итерация 13.15 — Снапшоты при создании плана

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

### Git

```bash
# Создать ветку
git checkout -b feature/iteration-14-help

# Коммит
git add .
git commit -m "feat(scheduler): add plan_settings support"

# Пуш
git push origin feature/iteration-14-help

# Обновить от main
git checkout main
git pull
git checkout feature/iteration-14-help
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