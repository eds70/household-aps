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
   git checkout -b feature/iteration-14-help
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
docs(readme): update version to 4.1.0
test(plan_settings): add integration tests for trigger
```

### 4. Pull Request

1. Запушьте ветку:
   ```
   git push origin feature/iteration-14-help
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
-- Итерация 13.14: plan_settings
BEGIN;

CREATE TABLE IF NOT EXISTS plan_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    schedule_version_id UUID NOT NULL REFERENCES schedule_version(id) ON DELETE CASCADE,
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
docs(readme): update version to 4.1.0

- Добавлена секция "Настройки, привязанные к плану"
- Обновлён Roadmap (13.3, 13.14)
- Добавлены команды проверки plan_settings
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
   ## [4.2.0] — 2026-10-01
   ```

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