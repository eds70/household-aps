#!/usr/bin/env python3
"""
check_docs.py — аудит консистентности markdown-файлов APS Production Scheduler.

Проверяет:
  1. Версия в README.md == CHANGELOG.md (верхняя запись) == docs/ROADMAP.md.
  2. Число тестов в README.md == CHANGELOG.md.
     Нормализация: 'N collected' > 'P passed + S skipped' > 'P passed' > 'всего N'.
  3. Таблица Roadmap в README.md == docs/ROADMAP.md (номер/статус).
  4. Эндпоинты в docs/API.md == роуты в backend/app/api/v1/*.py.
     Поддерживается prefix= внутри APIRouter; /health и / из main.py игнорируются.
  5. Ключи в docs/CONFIGURATION.md:
       - ENV-переменные   → backend/app/core/config.py
       - app_settings-ключи → backend/migrations/*.sql, init_schema.sql
     JSONB-мусор (поля audit-логов) отфильтровывается чёрным списком.

Запуск:
    python tools/check_docs.py
    python tools/check_docs.py --root .
    python tools/check_docs.py --json
    python tools/check_docs.py --strict
    python tools/check_docs.py --config-mode strict

Exit codes:
    0 — расхождений нет (или только warnings в не-strict режиме).
    1 — есть ошибки (или warnings в strict).
    2 — ошибка окружения (нет README.md).

Зависимости: только stdlib (Python 3.10+).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Модель проблемы
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    check: str
    severity: str
    file: str
    message: str
    hint: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    root: Path
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, int | str] = field(default_factory=dict)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warns(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warn"]


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


SEMVER_HEAD = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE)


# ---------------------------------------------------------------------------
# Проверка 1: версия
# ---------------------------------------------------------------------------

def check_versions(root: Path, report: Report) -> None:
    readme = root / "README.md"
    changelog = root / "CHANGELOG.md"
    roadmap = root / "docs" / "ROADMAP.md"

    missing = [p for p in (readme, changelog, roadmap) if not p.exists()]
    for p in missing:
        report.add(Issue(
            check="versions", severity="error",
            file=rel(root, p),
            message=f"файл не найден: {p}",
            hint="проверить структуру проекта",
        ))
    if missing:
        return

    readme_text = read_text(readme)
    m = re.search(r"Версия:\s*\*\*(\d+\.\d+\.\d+)\*\*", readme_text)
    readme_ver = m.group(1) if m else None

    changelog_text = read_text(changelog)
    versions = SEMVER_HEAD.findall(changelog_text)
    changelog_ver = versions[0] if versions else None

    roadmap_text = read_text(roadmap)
    m = re.search(r"версия[:\s]+(\d+\.\d+\.\d+)", roadmap_text, re.IGNORECASE)
    roadmap_ver = m.group(1) if m else None

    report.stats["readme_version"] = readme_ver or "-"
    report.stats["changelog_version"] = changelog_ver or "-"
    report.stats["roadmap_version"] = roadmap_ver or "-"

    if readme_ver is None:
        report.add(Issue(
            check="versions", severity="error",
            file=rel(root, readme),
            message="не найдена строка 'Версия: **X.Y.Z**'",
            hint="добавить в шапку: 'Версия: **X.Y.Z** (...)'",
        ))
    if changelog_ver is None:
        report.add(Issue(
            check="versions", severity="error",
            file=rel(root, changelog),
            message="не найден заголовок '## [X.Y.Z]'",
            hint="добавить секцию '## [X.Y.Z] — YYYY-MM-DD'",
        ))
    if readme_ver and changelog_ver and readme_ver != changelog_ver:
        report.add(Issue(
            check="versions", severity="error",
            file="README.md / CHANGELOG.md",
            message=f"версия расходится: README={readme_ver}, CHANGELOG={changelog_ver}",
            hint=f"привести к одной: {changelog_ver}",
        ))
    if readme_ver and roadmap_ver and readme_ver != roadmap_ver:
        report.add(Issue(
            check="versions", severity="warn",
            file="README.md / docs/ROADMAP.md",
            message=f"версия расходится: README={readme_ver}, ROADMAP={roadmap_ver}",
            hint=f"привести к одной: {readme_ver}",
        ))


# ---------------------------------------------------------------------------
# Проверка 2: число тестов
# ---------------------------------------------------------------------------

def _extract_test_count(text: str) -> int | None:
    m = re.search(r"(\d+)\s+collected", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m_passed = re.search(r"(\d+)\s+passed", text, re.IGNORECASE)
    m_skipped = re.search(r"(\d+)\s+skipped", text, re.IGNORECASE)
    if m_passed and m_skipped:
        return int(m_passed.group(1)) + int(m_skipped.group(1))
    if m_passed:
        return int(m_passed.group(1))

    for p in (r"всего\s+(\d+)", r"(\d+)\s+тестов"):
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def check_tests(root: Path, report: Report) -> None:
    readme = root / "README.md"
    changelog = root / "CHANGELOG.md"
    if not (readme.exists() and changelog.exists()):
        return

    readme_n = _extract_test_count(read_text(readme))
    changelog_n = _extract_test_count(read_text(changelog))
    report.stats["tests_readme"] = str(readme_n or "-")
    report.stats["tests_changelog"] = str(changelog_n or "-")

    if readme_n and changelog_n and readme_n != changelog_n:
        report.add(Issue(
            check="tests", severity="error",
            file="README.md / CHANGELOG.md",
            message=f"число тестов расходится: README={readme_n}, CHANGELOG={changelog_n}",
            hint="обновить оба до фактического значения pytest (passed + skipped)",
        ))


# ---------------------------------------------------------------------------
# Проверка 3: таблица Roadmap
# ---------------------------------------------------------------------------

ROW_RE = re.compile(
    r"^\|\s*\*{0,2}(\d+(?:\.\d+)?)\*{0,2}\s*\|"
    r"[^|]*\|"
    r"[^|]*\|"
    r"[^|]*\|"
    r"\s*\*{0,2}([✅⏳🟡🔥⛔]+|—|-)\*{0,2}\s*\|",
    re.MULTILINE,
)


def _parse_roadmap_rows(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in ROW_RE.finditer(text):
        num = m.group(1)
        status_raw = m.group(2)
        status = status_raw[0] if status_raw else "?"
        out.setdefault(num, status)
    return out


def check_roadmap(root: Path, report: Report) -> None:
    readme = root / "README.md"
    roadmap = root / "docs" / "ROADMAP.md"
    if not (readme.exists() and roadmap.exists()):
        return

    readme_rows = _parse_roadmap_rows(read_text(readme))
    roadmap_rows = _parse_roadmap_rows(read_text(roadmap))
    report.stats["roadmap_rows_readme"] = str(len(readme_rows))
    report.stats["roadmap_rows_roadmap"] = str(len(roadmap_rows))

    only_readme = sorted(set(readme_rows) - set(roadmap_rows), key=_num_key)
    only_roadmap = sorted(set(roadmap_rows) - set(readme_rows), key=_num_key)

    if only_readme:
        report.add(Issue(
            check="roadmap", severity="warn",
            file="README.md",
            message=f"итерации есть в README, нет в ROADMAP: {', '.join(only_readme)}",
            hint="синхронизировать таблицы",
        ))
    if only_roadmap:
        report.add(Issue(
            check="roadmap", severity="warn",
            file="docs/ROADMAP.md",
            message=f"итерации есть в ROADMAP, нет в README: {', '.join(only_roadmap)}",
            hint="синхронизировать таблицы",
        ))

    common = set(readme_rows) & set(roadmap_rows)
    for num in sorted(common, key=_num_key):
        if readme_rows[num] != roadmap_rows[num]:
            report.add(Issue(
                check="roadmap", severity="error",
                file="README.md / docs/ROADMAP.md",
                message=f"итерация {num}: статус расходится "
                        f"(README={readme_rows[num]}, ROADMAP={roadmap_rows[num]})",
                hint="привести к одному статусу",
            ))


def _num_key(s: str) -> tuple:
    return tuple(int(p) for p in s.split("."))


# ---------------------------------------------------------------------------
# Проверка 4: эндпоинты API
# ---------------------------------------------------------------------------

FASTAPI_ROUTE_RE = re.compile(
    r"@router\.(get|post|put|patch|delete)\("
    r"\s*[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)

APIRouter_PREFIX_RE = re.compile(
    r"APIRouter\s*\([^)]*?prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
    )

# Роутеры, которые реально подключаются через include_router
INCLUDE_ROUTER_RE = re.compile(
    r"app\.include_router\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,)]",
)

# Импорты: from app.api.v1.<name> import router as <alias>
IMPORT_ROUTER_RE = re.compile(
    r"from\s+app\.api\.v1\.([a-z_][a-z0-9_]*)\s+import\s+router\s+as\s+([A-Za-z_][A-Za-z0-9_]*)",
)

# Роуты приложения: @app.get("/health"), @app.get("/")
APP_ROUTE_RE = re.compile(
    r"@app\.(get|post|put|patch|delete)\(\s*[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)

# В API.md таблицы двух форматов
API_MD_ROW_RES = [
    re.compile(r"^\|\s*\**`?\s*(GET|POST|PUT|PATCH|DELETE)\s*`?\**\s*\|\s*\**`?([^`|*]+)`?\**\s*\|",
               re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\|\s*\**`?\s*(GET|POST|PUT|PATCH|DELETE)\s+`([^`]+)`\s*\**\s*\|",
               re.IGNORECASE | re.MULTILINE),
]


def _normalize_path(path: str) -> str:
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _join_paths(prefix: str, sub: str) -> str:
    if not prefix:
        return sub or "/"
    if not sub:
        return prefix
    if not prefix.endswith("/") and not sub.startswith("/"):
        return prefix + "/" + sub
    if prefix.endswith("/") and sub.startswith("/"):
        return prefix + sub[1:]
    return prefix + sub


def _collect_py_routes(root: Path) -> set[tuple[str, str]]:
    """
    Собирает пары (METHOD, full_path) из backend/app/api/v1/*.py,
    учитывая prefix= внутри APIRouter. Учитываются только те файлы,
    чьи роутеры реально подключены через app.include_router(...) в main.py.
    """
    v1 = root / "backend" / "app" / "api" / "v1"
    main_py = root / "backend" / "app" / "main.py"
    if not v1.exists():
        return set()

    # 1. Из main.py: alias роутера → имя модуля (для файла api/v1/<name>.py)
    alias_to_module: dict[str, str] = {}
    if main_py.exists():
        for m in IMPORT_ROUTER_RE.finditer(read_text(main_py)):
            module_name, alias = m.group(1), m.group(2)
            alias_to_module[alias] = module_name

    included_aliases: set[str] = set()
    if main_py.exists():
        for m in INCLUDE_ROUTER_RE.finditer(read_text(main_py)):
            included_aliases.add(m.group(1))

    # Множество активных модулей (если main.py не найден — берём все)
    if alias_to_module and included_aliases:
        active_modules = {
            alias_to_module[a] for a in included_aliases if a in alias_to_module
        }
    else:
        active_modules = {p.stem for p in v1.glob("*.py")}

    routes: set[tuple[str, str]] = set()
    for py in v1.glob("*.py"):
        if py.stem not in active_modules:
            continue
        text = read_text(py)
        m_prefix = APIRouter_PREFIX_RE.search(text)
        prefix = m_prefix.group(1) if m_prefix else ""
        for m in FASTAPI_ROUTE_RE.finditer(text):
            method = m.group(1).upper()
            sub = m.group(2)
            full = _join_paths(prefix, sub)
            routes.add((method, _normalize_path(full)))

    # 2. Роуты уровня приложения из main.py: @app.get("/health"), @app.get("/")
    #    Добавляем, но потом всё равно исключим из сравнения с API.md (служебные).
    if main_py.exists():
        for m in APP_ROUTE_RE.finditer(read_text(main_py)):
            method = m.group(1).upper()
            path = m.group(2)
            routes.add((method, _normalize_path(path or "/")))

    return routes


# Пути, которые не документируются в API.md (служебные).
API_DOC_IGNORE: set[tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/docs"),
    ("GET", "/redoc"),
    ("GET", "/openapi.json"),
}


def _collect_api_md_routes(root: Path) -> set[tuple[str, str]]:
    api_md = root / "docs" / "API.md"
    if not api_md.exists():
        return set()
    text = read_text(api_md)
    routes: set[tuple[str, str]] = set()
    for rx in API_MD_ROW_RES:
        for m in rx.finditer(text):
            method = m.group(1).upper()
            path = m.group(2).strip()
            if not path or not path.startswith("/"):
                continue
            routes.add((method, _normalize_path(path)))
    return routes


def check_api_endpoints(root: Path, report: Report, strict: bool = False) -> None:
    """
    Сравнивает эндпоинты в backend и docs/API.md.

    По умолчанию (strict=False):
      • 'в API.md есть, в коде нет'  → warn   (устаревшее — важно)
      • 'в коде есть, в API.md нет'  → info   (не выводится)

    При strict=True поведение как раньше: оба направления → warn.
    """
    py_routes_all = _collect_py_routes(root)
    py_routes = py_routes_all - API_DOC_IGNORE
    md_routes = _collect_api_md_routes(root)
    report.stats["routes_py"] = str(len(py_routes))
    report.stats["routes_api_md"] = str(len(md_routes))

    if not py_routes:
        report.add(Issue(
            check="api", severity="warn",
            file="backend/app/api/v1/",
            message="не найдено ни одного @router.<method> — проверить структуру",
        ))
        return
    if not md_routes:
        report.add(Issue(
            check="api", severity="warn",
            file="docs/API.md",
            message="не найдено табличных строк с эндпоинтами — "
                    "формат ожидается '| METHOD | /path | ...'",
            hint="проверить шапку таблицы или прислать пример строки",
        ))
        return

    md_norm: set[tuple[str, str]] = set()
    for method, path in md_routes:
        if not path.startswith("/api/"):
            path = "/api/v1" + (path if path.startswith("/") else "/" + path)
        md_norm.add((method, path))

    only_py = sorted(py_routes - md_norm)
    only_md = sorted(md_norm - py_routes)

    # 'в коде есть, в API.md нет' — info (по умолчанию не выводим)
    if strict:
        for method, path in only_py:
            report.add(Issue(
                check="api", severity="warn",
                file="docs/API.md",
                message=f"эндпоинт есть в коде, но не в API.md: {method} {path}",
                hint="добавить строку в таблицу API.md "
                     "(или запустить без --api-strict, чтобы скрыть)",
            ))
    else:
        # сохраняем в stats, но не в issues
        report.stats["api_undocumented"] = str(len(only_py))

    # 'в API.md есть, в коде нет' — всегда warn: это устаревшее
    for method, path in only_md:
        report.add(Issue(
            check="api", severity="warn",
            file="docs/API.md",
            message=f"эндпоинт есть в API.md, но не в коде: {method} {path}",
            hint="удалить устаревшую строку или пометить deprecated",
        ))


# ---------------------------------------------------------------------------
# Проверка 5: ключи настроек (ENV + app_settings)
# ---------------------------------------------------------------------------

CONFIG_ROW_RES = [
    re.compile(r"^\|\s*`([A-Za-z][A-Za-z0-9_]{1,})`\s*\|", re.MULTILINE),
    re.compile(r"^\|\s*([A-Za-z][A-Za-z0-9_]{1,})\s*\|", re.MULTILINE),
]

CONFIG_BLACKLIST = {
    "parameter", "key", "param", "parameter_key", "setting", "setting_key",
    "значение", "тип", "описание", "дефолт", "по", "умолчанию",
    "yes", "no", "true", "false", "none", "null",
    "type", "value", "default", "description", "name", "env", "variable",
    "переменная", "имя",
    # Имена категорий app_settings — это НЕ setting_key
    "features", "planning", "shifts", "calendar", "cooling",
    "materials", "lab", "cz", "resources", "optimization",
    # Параметры docker run PostgreSQL — не ENV приложения
    "postgres_user", "postgres_password", "postgres_db",
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
}

# JSONB-мусор: служебные поля audit-логов, snapshots, diff'ов.
# Эти ключи встречаются в миграциях как "key": в теле INSERT,
# но настройками не являются.
JSONB_NOISE = {
    "action", "batch_id", "calendar_events", "capacity", "changes",
    "comment", "cz_status", "due_date", "end", "ends_at", "equipment_code",
    "event_id", "event_type", "from_version_id", "is_pinned", "label",
    "marked_qty", "name", "new_due_date", "new_qty", "order_id", "orders",
    "planned_qty", "product_code", "progress_percent", "qty", "reason",
    "resource_capacity", "result", "route_type", "start", "starts_at",
    "target_qty", "threshold", "version_type", "work_end", "work_start",
    "true", "false", "null", "value",
}


def _collect_env_from_config_py(root: Path) -> set[str]:
    """
    ENV-переменные, читаемые в backend/app/core/config.py.

    Поддерживает два стиля:
      1) Явные: os.getenv("X"), Field(env="X"), Field(alias="X")
      2) pydantic-settings: class Settings(BaseSettings) с полями
         SECRET_KEY: str = Field(...)   → ENV SECRET_KEY
         case_sensitive=True            → имя ENV = имя поля
    """
    cfg = root / "backend" / "app" / "core" / "config.py"
    if not cfg.exists():
        return set()
    text = read_text(cfg)
    keys: set[str] = set()

    # 1) Явные ссылки
    for m in re.finditer(
            r"(?:getenv|environ(?:\.get)?|env)\s*[\(\[]\s*['\"]([A-Z][A-Z0-9_]{2,})['\"]",
            text,
    ):
        keys.add(m.group(1))
    for m in re.finditer(r"(?:alias|env)\s*=\s*['\"]([A-Z][A-Z0-9_]{2,})['\"]", text):
        keys.add(m.group(1))

    # 2) pydantic-settings: поля класса Settings
    #    Ищем блок class Settings(BaseSettings): ... до следующего class/def верхнего уровня
    m = re.search(
        r"class\s+Settings\s*\([^)]*BaseSettings[^)]*\)\s*:(.*?)(?=\nclass\s|\ndef\s|\Z)",
        text, re.DOTALL,
    )
    if m:
        body = m.group(1)
        # Поля вида: NAME: type = Field(...)  или  NAME: type = default
        for fm in re.finditer(r"^\s{4}([A-Z][A-Z0-9_]{2,})\s*:", body, re.MULTILINE):
            keys.add(fm.group(1))

    return keys

def _iter_values_rows(values_part: str) -> list[str]:
    """
    Возвращает список содержимого верхнеуровневых пар скобок из блока VALUES.
    Например, для '(a, b), (c, d)' вернёт ['a, b', 'c, d'].
    Корректно обрабатывает строки в кавычках и вложенные скобки.
    """
    rows: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    start = -1
    i = 0
    n = len(values_part)
    while i < n:
        ch = values_part[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < n and values_part[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "(" and not in_single and not in_double:
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")" and not in_single and not in_double:
            depth -= 1
            if depth == 0 and start >= 0:
                rows.append(values_part[start:i])
                start = -1
        i += 1
    return rows


def _collect_app_settings_keys(root: Path) -> set[str]:
    """
    Ключи app_settings из миграций и init_schema.sql.

    Поддерживает:
      • Многострочный INSERT INTO app_settings (...) VALUES (...), (...), ...
        с опциональным ON CONFLICT ... DO NOTHING после VALUES.
      • Однострочный INSERT.
      • ALTER TABLE app_settings ADD COLUMN x.

    Формат ячейки VALUES:
      ('<uuid>', '<category>', '<setting_key>', '<value>'[::jsonb], '<type>', ...)
    setting_key — ТРЕТИЙ элемент.

    organization_settings игнорируется (DEPRECATED, см. init_schema.sql).
    """
    keys: set[str] = set()
    candidates: list[Path] = []
    mig = root / "backend" / "migrations"
    if mig.exists():
        candidates.extend(sorted(mig.glob("*.sql")))
    init = root / "backend" / "init_schema.sql"
    if init.exists():
        candidates.append(init)

    for sql in candidates:
        text = read_text(sql)

        # Захватываем инструкцию INSERT INTO app_settings ... до ';'
        for block in re.finditer(
                r"INSERT\s+INTO\s+app_settings\b(.*?);",
                text, re.IGNORECASE | re.DOTALL,
        ):
            stmt = block.group(1)

            # Отрезаем всё до VALUES
            vm = re.search(r"\bVALUES\b(.*)", stmt, re.IGNORECASE | re.DOTALL)
            if not vm:
                continue
            values_part = vm.group(1)

            # Отрезаем хвост ON CONFLICT ... DO NOTHING (если есть)
            values_part = re.split(
                r"\bON\s+CONFLICT\b",
                values_part, maxsplit=1, flags=re.IGNORECASE,
            )[0]

            # Каждая строка VALUES: (...) — верхнеуровневые пары скобок
            for row in _iter_values_rows(values_part):
                cells = _split_sql_values(row)
                if len(cells) >= 3:
                    key = _unquote_sql(cells[2])
                    if key and re.match(r"^[a-z][a-z0-9_]{2,}$", key):
                        keys.add(key)

        # ALTER TABLE app_settings ADD COLUMN x
        for m in re.finditer(
                r"ALTER\s+TABLE\s+app_settings"
                r"\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z][a-z0-9_]+)",
                text, re.IGNORECASE,
        ):
            keys.add(m.group(1))

    return keys - JSONB_NOISE

def _split_sql_values(row: str) -> list[str]:
    """
    Разбивает содержимое одной пары скобок VALUES на ячейки.

    Правила SQL:
      • Внутри '...' двойные кавычки и запятые — часть строки.
      • Внутри "..." одинарные кавычки и запятые — часть строки.
      • Запятые вне строк и на нулевой вложенности скобок — разделители.
      • Скобки ( ) вне строк — учитывают вложенность (для JSONB-функций).
      • Кастовые суффиксы ::jsonb / ::text — не разделители, идут в буфер.
    """
    cells: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    current: list[str] = []
    i = 0
    while i < len(row):
        ch = row[i]

        if in_single:
            # Внутри одинарных кавычек всё — часть строки,
            # кроме закрывающей ' (с учётом '' → экранирование).
            if ch == "'" and i + 1 < len(row) and row[i + 1] == "'":
                current.append("''")
                i += 2
                continue
            if ch == "'":
                in_single = False
            current.append(ch)
        elif in_double:
            # Внутри двойных кавычек всё — часть строки.
            if ch == '"':
                in_double = False
            current.append(ch)
        else:
            # Вне строк.
            if ch == "'":
                in_single = True
                current.append(ch)
            elif ch == '"':
                in_double = True
                current.append(ch)
            elif ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                cells.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        i += 1
    if current:
        cells.append("".join(current).strip())
    return cells


def _unquote_sql(cell: str) -> str:
    """Убирает обрамляющие одинарные кавычки и удвоенные '' внутри."""
    cell = cell.strip()
    if len(cell) >= 2 and cell[0] == "'" and cell[-1] == "'":
        return cell[1:-1].replace("''", "'")
    return cell

def _collect_config_md_keys(root: Path) -> set[str]:
    cfg = root / "docs" / "CONFIGURATION.md"
    if not cfg.exists():
        return set()
    text = read_text(cfg)
    keys: set[str] = set()
    for rx in CONFIG_ROW_RES:
        for m in rx.finditer(text):
            keys.add(m.group(1))
    # Фильтр без учёта регистра: 'POSTGRES_USER' тоже исключаем,
    # если в CONFIG_BLACKLIST есть 'postgres_user'
    return {k for k in keys if k.lower() not in CONFIG_BLACKLIST}

def check_config_keys(root: Path, report: Report, mode: str = "lenient") -> None:
    """
    Проверяет ключи из docs/CONFIGURATION.md против:
      • ENV-переменных, читаемых в backend/app/core/config.py;
      • ключей app_settings, найденных в миграциях/init_schema.sql.

    'config-app' — только warning: некоторые ключи могут добавляться
    программно (например, через settings_reader.py).
    'config-env' — warning: если ENV описан, но не читается — либо док
    устарел, либо ключ читается где-то ещё (не в config.py).
    """
    env_py = _collect_env_from_config_py(root)
    app_keys = _collect_app_settings_keys(root)
    md_keys = _collect_config_md_keys(root)

    md_env = {k for k in md_keys if k.isupper()}
    md_lower = {k for k in md_keys if k.islower() or (k and k[0].islower())}

    report.stats["config_md_total"] = str(len(md_keys))
    report.stats["config_md_env"] = str(len(md_env))
    report.stats["config_md_lower"] = str(len(md_lower))
    report.stats["config_env_py"] = str(len(env_py))
    report.stats["config_app_keys"] = str(len(app_keys))

    # ENV: описано в доке, но не найдено в config.py
    for k in sorted(md_env - env_py):
        report.add(Issue(
            check="config-env", severity="warn",
            file="docs/CONFIGURATION.md",
            message=f"ENV-переменная описана, но не читается в config.py: {k}",
            hint="добавить os.getenv/Field(env=...) в config.py или убрать из доки",
        ))

    # app_settings: описано в доке, но не найдено в миграциях/init_schema
    for k in sorted(md_lower - app_keys):
        report.add(Issue(
            check="config-app", severity="warn",
            file="docs/CONFIGURATION.md",
            message=f"ключ описан, но не найден в миграциях/init_schema: {k}",
            hint="проверить, что миграция применена и ключ существует",
        ))

    # app_settings: найдено в миграциях, но не описано в доке
    for k in sorted(app_keys - md_lower - env_py):
        if len(k) < 3:
            continue
        report.add(Issue(
            check="config-app", severity="warn",
            file="docs/CONFIGURATION.md",
            message=f"ключ есть в миграциях, но не описан: {k}",
            hint="добавить строку в таблицу CONFIGURATION.md",
        ))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(10):
        if (cur / "README.md").exists() and (cur / "backend").is_dir():
            return cur
        cur = cur.parent
    return start.resolve()


def run(root: Path, config_mode: str = "lenient",
        api_strict: bool = False) -> Report:
    report = Report(root=root)
    check_versions(root, report)
    check_tests(root, report)
    check_roadmap(root, report)
    check_api_endpoints(root, report, strict=api_strict)
    check_config_keys(root, report, mode=config_mode)
    return report


def print_human(report: Report) -> None:
    print("=" * 72)
    print(f"check_docs.py — {report.root}")
    print("=" * 72)

    if not report.issues:
        print("\n✅ Расхождений не найдено.\n")
    else:
        errors = report.errors
        warns = report.warns
        if errors:
            print(f"\n❌ Ошибки ({len(errors)}):")
            for i in errors:
                print(f"  • [{i.check}] {i.file}")
                print(f"      {i.message}")
                if i.hint:
                    print(f"      ↳ {i.hint}")
        if warns:
            print(f"\n⚠️  Предупреждения ({len(warns)}):")
            for i in warns:
                print(f"  • [{i.check}] {i.file}")
                print(f"      {i.message}")
                if i.hint:
                    print(f"      ↳ {i.hint}")

    print("\n" + "-" * 72)
    print("Статистика:")
    for k in sorted(report.stats):
        print(f"  {k:<28} = {report.stats[k]}")
    print("-" * 72)


def print_json(report: Report) -> None:
    payload = {
        "root": str(report.root),
        "issues": [i.as_dict() for i in report.issues],
        "stats": report.stats,
        "errors": len(report.errors),
        "warns": len(report.warns),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Аудит консистентности md-файлов APS Production Scheduler."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 даже при warnings")
    parser.add_argument("--config-mode", choices=["lenient", "strict"],
                        default="lenient")
    parser.add_argument("--api-strict", action="store_true",
                        help="считать 'в коде, но не в API.md' тоже warning")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = args.root.resolve() if args.root else find_root(Path.cwd())
    if not (root / "README.md").exists():
        print(f"ERROR: не найден README.md в {root}", file=sys.stderr)
        return 2

    report = run(root, config_mode=args.config_mode,
                 api_strict=args.api_strict)

    if args.json:
        print_json(report)
    else:
        print_human(report)

    if report.errors:
        return 1
    if args.strict and report.warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())