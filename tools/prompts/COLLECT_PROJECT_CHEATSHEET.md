# Шпаргалка: collect_project.py

Быстрая сборка дампа проекта для AI-ассистента.
Заменяет полный дамп (2.7 MB) на точечные выборки (50–500 KB).

## Связанные файлы

- [collect_project.py](../../collect_project.py) — сам скрипт.
- [AI_WORKFLOW.md](AI_WORKFLOW.md) — процесс работы с ассистентом.
- [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md) — промт для нового чата.
- [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) — руководство разработчика.

---

## TL;DR — что использовать в 90% случаев

```powershell
# 1. Общий контекст (что вообще есть в проекте) — 50 KB
python collect_project.py --outline

# 2. Правлю конкретный модуль — только он + тесты — 70 KB
python collect_project.py --files `
  backend/app/api/v1/help.py `
  backend/tests/test_help.py

# 3. Работаю в поддереве (например, scheduler) — 500 KB
python collect_project.py --path backend/app/scheduler

# 4. Только код приложения, без тестов — 600 KB
python collect_project.py --path backend/app --no-tests

# 5. Полный дамп (только когда реально нужен весь проект) — 2.7 MB
python collect_project.py
```

---

## Все параметры

| Параметр | Что делает | Пример |
|----------|-----------|--------|
| `--path PATH` | Обходить только указанную поддиректорию | `--path backend/app/scheduler` |
| `--files F1 F2 ...` | Включить только перечисленные файлы | `--files backend/app/main.py` |
| `--extensions EXT ...` | Оставить только файлы с этими расширениями | `--extensions .py .sql` |
| `--max-size N` | Максимальный размер файла в байтах | `--max-size 50000` (50 KB) |
| `--outline` | Только оглавление (пути + docstrings), без кода | `--outline` |
| `--no-tests` | Исключить `test_*.py`, `*_test.py`, `tests/` | `--no-tests` |
| `--stats-only` | Только статистика, файл не создавать | `--stats-only` |
| `-o FILE`, `--output FILE` | Своё имя выходного файла | `-o help_dump.txt` |

Полная справка:

```powershell
python collect_project.py --help
```

---

## Готовые рецепты под задачу

### «Хочу понять структуру проекта»

```powershell
python collect_project.py --outline
# → project_dump.txt (~50 KB)
# Внутри: список всех файлов с кратким описанием из docstring
```

Что посылать AI: этот файл целиком + свой вопрос.

---

### «Правлю баг в конкретном модуле»

```powershell
# Пример: правка в advisor.py
python collect_project.py --files `
  backend/app/scheduler/advisor.py `
  backend/tests/test_advisor.py `
  backend/app/api/v1/advisor.py
# → project_files_dump.txt (~70 KB)
```

Что посылать AI: этот файл + описание бага + шаги воспроизведения.

---

### «Работаю над подсистемой (scheduler, api, help)»

```powershell
# Только scheduler
python collect_project.py --path backend/app/scheduler
# → project_dump_backend_app_scheduler.txt (~500 KB)

# Только API-роутеры
python collect_project.py --path backend/app/api/v1 --no-tests
# → project_dump_backend_app_api_v1.txt (~600 KB)

# Только тесты справки
python collect_project.py --path backend/tests --extensions .py --outline
# → project_dump_backend_tests.txt (~15 KB)
```

---

### «Пишу миграцию БД»

```powershell
# Только схема + конкретные миграции (без seed)
python collect_project.py --files `
  backend/init_schema.sql `
  backend/migrations/add_24.sql `
  backend/migrations/add_25.sql `
  backend/app/scheduler/snapshot.py
# → project_files_dump.txt (~50 KB)
```

Совет: seed-миграции (`add_*_seed_*.sql`) исключаются
автоматически — они не нужны для анализа кода.

---

### «Работаю над фронтендом»

```powershell
# Только конкретная страница + её компоненты
python collect_project.py --files `
  frontend/src/pages/GanttPage.tsx `
  frontend/src/components/gantt/GanttToolbar.tsx `
  frontend/src/components/gantt/GanttTaskDialog.tsx `
  frontend/src/hooks/useGanttTimeline.ts `
  frontend/src/types/index.ts
# → project_files_dump.txt (~150 KB)

# Или — всё поддерево компонентов Gantt
python collect_project.py --path frontend/src/components/gantt
# → project_dump_frontend_src_components_gantt.txt (~200 KB)

# Или — оглавление всего фронта
python collect_project.py --path frontend/src --outline
# → project_dump_frontend_src.txt (~15 KB)
```

---

### «Хочу посмотреть, сколько это весит»

```powershell
# Статистика по всему проекту
python collect_project.py --stats-only

# Статистика по поддереву
python collect_project.py --path backend/app/scheduler --stats-only

# Вывод:
# 📊 Статистика:
#    Корень: D:\Working\household-aps
#    Файлов найдено: 45
#    Общий размер: 0.52 MB
#    Примерный размер дампа: ~0.57 MB
```

---

### «Хочу только .py-файлы, без тяжёлых»

```powershell
python collect_project.py --path backend --extensions .py --max-size 30000
# → только .py-файлы ≤ 30 KB
```

---

## Что создаётся

| Команда | Выходной файл | Размер |
|---------|---------------|--------|
| `--outline` | `project_dump.txt` | ~50 KB |
| (без параметров) | `project_dump.txt` | ~2.7 MB |
| `--path X` | `project_dump_X.txt` (X — путь с `_`) | 100 KB – 700 KB |
| `--files F1 F2` | `project_files_dump.txt` | 20 KB – 200 KB |
| `-o NAME` | `NAME` (как указали) | любой |

---

## Стратегия работы

### Золотое правило

Никогда не посылайте полный дамп, если задача локальная.

### Три сценария

1. Начинаю новую задачу — не знаю, где искать.

   ```powershell
   python collect_project.py --outline
   ```

   Посмотреть структуру, найти нужные файлы по описанию.

2. Нашёл нужные файлы — копаю глубже.

   ```powershell
   python collect_project.py --files FILE1 FILE2 FILE3
   ```

   Посылать AI файлы целиком + вопрос.

3. Работаю над подсистемой несколько дней.

   ```powershell
   python collect_project.py --path backend/app/scheduler -o scheduler_WIP.txt
   ```

   Держать под рукой один раз, обновлять по мере правок.

---

## Что исключается автоматически

Не попадают в дамп (независимо от параметров):

- `node_modules/`, `.venv/`, `__pycache__/`, `.git/`
- `package-lock.json`, `poetry.lock`, `yarn.lock`
- `*.log`, `*.pyc`, `*.map`, `*.min.js`
- `*_seed_*.sql` (seed-миграции — большие, не нужны для кода)
- `.env`, `.env.local` (секреты)
- `project_dump.txt`, `collect_project.py` (сам себя не включает)

---

## Расширенные примеры

### Комбинация: только .py и .tsx, без тестов, ≤ 40 KB

```powershell
python collect_project.py `
  --path frontend/src `
  --extensions .tsx .ts `
  --no-tests `
  --max-size 40000 `
  -o frontend_small.txt
```

### Только файлы, изменённые недавно

```powershell
# Если у вас git — используйте его для отбора
git diff --name-only HEAD~5 > changed.txt
python collect_project.py --files (Get-Content changed.txt)
```

### Несколько раз — по разным подсистемам

```powershell
python collect_project.py --path backend/app/scheduler -o dump_scheduler.txt
python collect_project.py --path backend/app/api/v1  -o dump_api.txt
python collect_project.py --path frontend/src/components/gantt -o dump_gantt.txt
```

---

## Ключевая мысль

Экономия контекста = экономия денег и времени.

| Способ | Размер | Когда |
|--------|--------|-------|
| Полный дамп | 2.7 MB | Только для первого знакомства с проектом |
| `--outline` | 50 KB | Общий контекст, поиск нужного файла |
| `--path` | 100–700 KB | Работа над подсистемой |
| `--files` | 20–200 KB | Правка конкретного модуля |
| `--stats-only` | 0 KB | Проверка размера |

Типичная экономия — в 20–50 раз.

---

## Git-игнор

Файлы дампов не должны попадать в git. Добавьте в `.gitignore`:

```
project_dump*.txt
project_meta.txt
project_core.txt
project_files_dump.txt
project_tz.txt
```

---

*Последнее обновление: 2026-10-06*