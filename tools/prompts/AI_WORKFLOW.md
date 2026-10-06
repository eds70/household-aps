# AI Workflow: работа с ассистентом над APS Scheduler

Описание процесса работы над проектом с использованием AI-ассистента
(Continue.dev, Claude, ChatGPT или другого). Покрывает подготовку
файлов, вставку в чат и итеративную работу над кодом и документацией.

## Связанные файлы

- [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md) — промт для первого сообщения в новом чате.
- [COLLECT_PROJECT_CHEATSHEET.md](COLLECT_PROJECT_CHEATSHEET.md) — шпаргалка по `collect_project.py`.
- [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) — руководство разработчика.
- [ROADMAP.md](../../docs/ROADMAP.md) — план развития.

---

## 1. Зачем это нужно

Дамп проекта растёт (сейчас ~2.7 MB, 253 файла). Полный дамп:

- не влезает в контекст модели целиком;
- тратит токены на нерелевантный код;
- замедляет ответы.

Решение — **точечные выборки** через `collect_project.py` и
**структурированный промт** для нового чата.

Типичная экономия контекста — в 20–50 раз.

---

## 2. Сценарий работы

### Шаг 1. Подготовка файлов

Запустите в терминале из корня проекта:

```powershell
cd D:\Working\household-aps

# 1. Оглавление всего проекта — что вообще есть (~50 KB)
python collect_project.py --outline -o project_dump.txt

# 2. Ключевые MD-файлы (~30 KB)
python collect_project.py --files `
  README.md `
  CHANGELOG.md `
  docs/ROADMAP.md `
  -o project_meta.txt

# 3. Ядро планировщика (~150 KB) — опционально
python collect_project.py --files `
  backend/app/main.py `
  backend/app/scheduler/core.py `
  backend/app/scheduler/data_loader.py `
  backend/app/scheduler/saver.py `
  backend/app/api/v1/help.py `
  -o project_core.txt
```

Подробнее о параметрах — в [COLLECT_PROJECT_CHEATSHEET.md](COLLECT_PROJECT_CHEATSHEET.md).

### Шаг 2. Открытие нового чата

1. Откройте [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md).
2. Скопируйте блок «Копипаста» целиком.
3. Вставьте в поле ввода нового чата.
4. Приложите файлы через теги:

```
<file name="project_dump.txt">
...содержимое project_dump.txt...
</file>

<file name="project_meta.txt">
...содержимое project_meta.txt...
</file>

<file name="project_core.txt">
...содержимое project_core.txt...
</file>
```

**Приоритет приложений:**

| Файл | Обязателен | Когда |
|------|------------|-------|
| `README.md` | Да | Всегда |
| `docs/ROADMAP.md` | Да | Всегда |
| `CHANGELOG.md` | Желателен | Всегда |
| `project_dump.txt` | Да | Для обзора структуры |
| `project_core.txt` | Опционально | Если нужно анализировать код |
| `docs/requirements/ТЗ.txt` | Опционально | Если сверяемся с исходными требованиями |

### Шаг 3. Первый ответ ассистента

Ассистент выдаст:

1. Краткий анализ (5–10 строк).
2. Текущую стадию (vX.Y.Z, итерации).
3. Что реализовано и какие известные ограничения.
4. 2–3 варианта следующего шага (A / B / C).
5. Остановку и ожидание выбора.

### Шаг 4. Выбор варианта

Ответьте ассистенту, например:

```
Вариант A. Составь детальный план.
```

Ассистент:

- разобьёт итерацию на подзадачи;
- перечислит файлы для правки;
- даст порядок работ;
- дождётся команды «ок» для первого файла.

### Шаг 5. Итеративная работа

После каждой правки ассистент:

- выводит **один файл целиком** (правило 1);
- ждёт команду «ок» перед следующим (правило 2);
- даёт **сжатый** комментарий (правило 3);
- все SQL-команды — **только через docker** (правило 4).

---

## 3. Соглашения об именовании

### Файлы для чата

| Файл | Назначение | Режим `collect_project.py` |
|------|------------|----------------------------|
| `project_dump.txt` | Оглавление всего проекта | `--outline` |
| `project_meta.txt` | README + CHANGELOG + ROADMAP | `--files` |
| `project_core.txt` | Ядро планировщика | `--files` |
| `project_tz.txt` | Исходное ТЗ | `--files` |
| `project_files_dump.txt` | Конкретные файлы | `--files` |
| `project_dump_<path>.txt` | Поддерево | `--path X` |

### Git-игнор

Файлы дампов не должны попадать в git. Добавьте в `.gitignore`:

```
project_dump*.txt
project_meta.txt
project_core.txt
project_files_dump.txt
project_tz.txt
```

---

## 4. Полный сценарий: пример

Допустим, вы хотите начать работу над **Итерацией 16**
(Расширенный аудит и отчёты).

### Сессия 1: подготовка

```powershell
cd D:\Working\household-aps

# 1. Оглавление (~50 KB)
python collect_project.py --outline -o project_dump.txt

# 2. README + ROADMAP + CHANGELOG (~30 KB)
python collect_project.py --files `
  README.md CHANGELOG.md docs/ROADMAP.md `
  -o project_meta.txt

# 3. Только модули аудита (~80 KB)
python collect_project.py --files `
  backend/app/api/v1/audit.py `
  backend/app/api/v1/audit_models.py `
  frontend/src/pages/AuditPage.tsx `
  -o project_audit.txt
```

### Сессия 2: открытие чата

1. Копируете промт из [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md).
2. Вставляете в чат.
3. Прикладываете `project_dump.txt`, `project_meta.txt`, `project_audit.txt`.

### Сессия 3: анализ и планирование

Ассистент отвечает:

> Текущая стадия: v4.8.0. Известные ограничения аудита...
> Варианты: A) экспорт в Excel, B) дашборд, C) realtime...

Вы выбираете вариант. Ассистент составляет детальный план.

### Сессия 4: работа по файлам

Ассистент выдаёт файл за файлом, вы:

- сохраняете каждый файл;
- отвечаете «ок» для следующего;
- после всех правок — запускаете тесты.

---

## 5. Проверка после сессии

После каждой сессии правок:

```powershell
cd backend
python -m pytest tests/ -v
```

Ожидаемо: **738 passed** (или больше, если добавлены новые тесты).

Проверка БД:

```powershell
docker exec -i aps_postgres psql -U aps -d household -c "SELECT COUNT(*) FROM help_article;"
```

Проверка frontend:

```powershell
cd frontend
npm run typecheck
npm run lint
```

---

## 6. Что делать, если что-то пошло не так

### Ассистент выдаёт файл не полностью

Напишите:

```
Файл неполный, выведи целиком.
```

### Ассистент не дождался команды «ок»

Напишите:

```
Правило 2: после каждого файла — остановка. Выведи один файл и жди.
```

### SQL-команда без docker

Напишите:

```
Правило 4: все команды БД — только через docker exec.
```

### Ассистент выдумывает функциональность

Напишите:

```
Не выдумывай. Только то, что есть в project_dump.txt.
```

---

## 7. Расширение workflow

### Для конкретной подсистемы

Если работаете только над одним поддеревом, используйте `--path`:

```powershell
python collect_project.py --path backend/app/scheduler -o project_scheduler.txt
```

### Только код приложения, без тестов

```powershell
python collect_project.py --path backend/app --no-tests -o project_app.txt
```

### Ограничение по размеру файлов

```powershell
python collect_project.py --path backend --extensions .py --max-size 30000 -o project_small.txt
```

---

## 8. Ограничения

- Ассистент не имеет прямого доступа к файловой системе — вы должны
  прикладывать файлы вручную.
- Ассистент не может запускать тесты — вы запускаете их сами.
- Ассистент не может обращаться к БД — вы даёте ему вывод SQL-команд.
- Контекст модели ограничен — не посылайте полный дамп без
  необходимости.

**Альтернатива:** MCP-сервер filesystem даёт ассистенту прямой доступ
к файлам и снимает эти ограничения. См. документацию Continue.dev
или Claude Desktop.

---

*Последнее обновление: 2026-10-06*