#!/usr/bin/env python3
"""
Сборка кода проекта в один текстовый файл.

Используется для передачи контекста AI-ассистенту.
Поддерживает частичную сборку: по поддереву, по конкретным файлам,
по расширениям, в режиме «оглавление» (только пути + docstrings).

Использование:
    # Полный дамп (как раньше)
    python collect_project.py

    # Только поддерево
    python collect_project.py --path backend/app/scheduler

    # Только конкретные файлы
    python collect_project.py --files backend/app/api/v1/help.py backend/tests/test_help.py

    # Только .py + .sql, с ограничением размера
    python collect_project.py --path backend --extensions .py .sql --max-size 50000

    # Оглавление (пути + первая строка docstring) — быстро и компактно
    python collect_project.py --outline

    # Оглавление только для backend
    python collect_project.py --path backend --outline

    # Исключить тесты (для анализа только кода приложения)
    python collect_project.py --path backend/app --no-tests

    # Комбинации
    python collect_project.py --path backend/app --extensions .py --outline
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

# ==========================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ==========================================

PROJECT_ROOT = Path(__file__).parent.resolve()

# Директории, которые исключаем всегда
EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".next",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".tox",
    ".eggs",
    "*.egg-info",
    "docker",
    "tools",
}

# Файлы, которые исключаем всегда
EXCLUDED_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "tsconfig.tsbuildinfo",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "collect_project.py",
    "collect_project_full.py",
    "project_dump.txt",
    ".env",
    ".env.local",
    ".env.production",
}

# Regex-паттерны для исключения файлов (по имени)
EXCLUDED_PATTERNS = [
    r".*_seed_.*\.sql$",       # seed-миграции (большие, не нужны для анализа кода)
    r".*\.min\.js$",           # минифицированные
    r".*\.map$",               # source maps
    r".*\.pyc$",
    r".*\.log$",
]

# Расширения, которые включаем по умолчанию
DEFAULT_EXTENSIONS = {
    ".py",
    ".tsx", ".ts", ".jsx", ".js",
    ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".css", ".scss", ".less",
    ".html", ".htm",
    ".sql",
    ".md", ".txt", ".rst",
    ".dockerfile",
    ".env", ".env.example",
}

# Максимальный размер одного файла (1 MB)
DEFAULT_MAX_FILE_SIZE = 1024 * 1024

# Кодировка вывода
OUTPUT_ENCODING = "utf-8"


# ==========================================
# ФИЛЬТРАЦИЯ
# ==========================================

def _matches_any_pattern(name: str, patterns: Iterable[str]) -> bool:
    """True, если имя совпадает хотя бы с одним regex-паттерном."""
    for pattern in patterns:
        try:
            if re.match(pattern, name):
                return True
        except re.error:
            # Если паттерн некорректный — игнорируем
            continue
    return False


def should_include_file(
        file_path: Path,
        extensions: set[str],
        max_size: int,
        no_tests: bool = False,
) -> bool:
    """Проверяет, включать ли файл в дамп."""
    name = file_path.name

    # Имя файла — точное исключение
    if name in EXCLUDED_FILES:
        return False

    # Regex-исключения
    if _matches_any_pattern(name, EXCLUDED_PATTERNS):
        return False

    # --no-tests: пропускаем test_*.py и *_test.py, tests/ директории
    if no_tests:
        if name.startswith("test_") or name.endswith("_test.py"):
            return False
        if "tests" in file_path.parts:
            return False

    # Расширение
    suffix = file_path.suffix.lower()
    if suffix not in extensions:
        # Dockerfile без расширения — исключение
        if name.lower() != "dockerfile":
            return False

    # Размер
    try:
        size = file_path.stat().st_size
    except OSError:
        return False

    if size > max_size:
        return False

    return True


def should_include_dir(dir_name: str) -> bool:
    """Проверяет, обходить ли директорию."""
    if dir_name in EXCLUDED_DIRS:
        return False
    if dir_name.startswith(".") and dir_name not in {".github", ".gitlab"}:
        return False
    return True


def collect_files(root: Path, extensions: set[str], max_size: int, no_tests: bool) -> List[Path]:
    """Собирает все файлы поддерева, удовлетворяющие фильтрам."""
    if not root.exists():
        raise FileNotFoundError(f"Путь не найден: {root}")
    if root.is_file():
        return [root] if should_include_file(root, extensions, max_size, no_tests) else []

    files: List[Path] = []
    for dir_path, dir_names, file_names in os.walk(root):
        dir_p = Path(dir_path)

        # Фильтруем директории «на лету»
        dir_names[:] = [d for d in dir_names if should_include_dir(d)]

        for file_name in sorted(file_names):
            file_path = dir_p / file_name
            if should_include_file(file_path, extensions, max_size, no_tests):
                files.append(file_path)

    files.sort(key=lambda p: str(p.relative_to(PROJECT_ROOT)))
    return files


# ==========================================
# ЧТЕНИЕ
# ==========================================

def read_file_content(file_path: Path) -> str:
    """Читает содержимое файла с fallback-кодировками."""
    for encoding in (OUTPUT_ENCODING, "windows-1251", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"[Ошибка чтения: {e}]"
    return f"[Бинарный файл: {file_path.name}]"


def extract_docstring_or_first_line(content: str, max_len: int = 120) -> str:
    """
    Извлекает краткое описание файла:
      - первую строку docstring (если есть),
      - иначе — первый комментарий,
      - иначе — пустую строку.
    """
    lines = content.splitlines()
    in_docstring = False
    docstring_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Пропускаем shebang, пустые строки, coding
        if not stripped or stripped.startswith("#!") or "coding:" in stripped:
            continue

        # Начало docstring
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote = stripped[:3]
                inner = stripped[3:]
                if inner.endswith(quote) and len(inner) > 3:
                    # Однострочный docstring
                    return inner[:-3].strip()[:max_len]
                docstring_lines.append(inner)
                in_docstring = True
                continue
            # Однострочный комментарий
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()[:max_len]
            # Первая «кодовая» строка — сдаёмся
            return ""
        else:
            # Внутри docstring
            if stripped.endswith('"""') or stripped.endswith("'''"):
                docstring_lines.append(stripped[:-3].strip())
                break
            docstring_lines.append(stripped)

    if docstring_lines:
        text = " ".join(l for l in docstring_lines if l)
        return text[:max_len]
    return ""


# ==========================================
# ГЕНЕРАЦИЯ ДАМПА
# ==========================================

def generate_outline(files: List[Path]) -> str:
    """Генерирует компактное оглавление: путь + краткое описание."""
    lines = []
    lines.append("=" * 80)
    lines.append("📋 ОГЛАВЛЕНИЕ ПРОЕКТА APS PRODUCTION SCHEDULER")
    lines.append("=" * 80)
    lines.append(f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Корневая директория: {PROJECT_ROOT}")
    lines.append(f"Всего файлов: {len(files)}")
    lines.append("=" * 80)
    lines.append("")

    # Группируем по директориям
    by_dir: dict[str, List[Path]] = {}
    for f in files:
        rel = f.relative_to(PROJECT_ROOT)
        parent = str(rel.parent) if str(rel.parent) != "." else "."
        by_dir.setdefault(parent, []).append(f)

    total_size = 0

    for dir_path in sorted(by_dir.keys()):
        lines.append(f"📁 {dir_path}/")
        for f in sorted(by_dir[dir_path], key=lambda p: p.name):
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            total_size += size

            rel_name = f.name
            size_kb = size / 1024

            # Извлекаем docstring для py/ts файлов
            description = ""
            if f.suffix.lower() in (".py", ".ts", ".tsx", ".js", ".jsx"):
                content = read_file_content(f)
                description = extract_docstring_or_first_line(content, max_len=80)
                if description:
                    description = f" — {description}"

            lines.append(f"  • {rel_name} ({size_kb:.1f} KB){description}")
        lines.append("")

    lines.append("=" * 80)
    lines.append(f"📊 Всего файлов: {len(files)}, суммарный размер: {total_size / 1024:.1f} KB")
    lines.append("=" * 80)

    return "\n".join(lines)


def generate_dump(files: List[Path]) -> str:
    """Генерирует полный дамп с содержимым файлов."""
    lines = []
    lines.append("=" * 80)
    lines.append("📦 ДАМП ПРОЕКТА APS PRODUCTION SCHEDULER")
    lines.append("=" * 80)
    lines.append(f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Корневая директория: {PROJECT_ROOT}")
    lines.append(f"Всего файлов: {len(files)}")
    lines.append("=" * 80)
    lines.append("")

    total_size = 0

    for file_path in files:
        rel_path = file_path.relative_to(PROJECT_ROOT)
        content = read_file_content(file_path)
        file_size = len(content.encode(OUTPUT_ENCODING, errors="replace"))
        total_size += file_size

        lines.append("")
        lines.append("─" * 80)
        lines.append(f"📄 ФАЙЛ: {rel_path}")
        lines.append(f"   Размер: {file_size:,} байт ({file_size / 1024:.1f} KB)")
        lines.append("─" * 80)
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("─" * 80)
        lines.append(f"📄 КОНЕЦ ФАЙЛА: {rel_path}")
        lines.append("─" * 80)

    # Статистика
    lines.append("")
    lines.append("=" * 80)
    lines.append("📊 СТАТИСТИКА")
    lines.append("=" * 80)
    lines.append(f"Всего файлов: {len(files)}")
    lines.append(
        f"Общий размер: {total_size:,} байт "
        f"({total_size / 1024:.1f} KB, {total_size / 1024 / 1024:.2f} MB)"
    )

    ext_stats: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower() or "(без расширения)"
        ext_stats[ext] = ext_stats.get(ext, 0) + 1

    lines.append("")
    lines.append("Распределение по типам файлов:")
    for ext, count in sorted(ext_stats.items(), key=lambda x: -x[1]):
        lines.append(f"  {ext:15s}: {count} файлов")

    lines.append("")
    lines.append("=" * 80)
    lines.append("КОНЕЦ ДАМПА")
    lines.append("=" * 80)

    return "\n".join(lines)


# ==========================================
# MAIN
# ==========================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сборка дампа проекта для AI-ассистента.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Поддиректория (относительно корня проекта) для обхода.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="Список конкретных файлов (относительно корня или абсолютные).",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=None,
        help="Оставить только файлы с этими расширениями (например, .py .sql).",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE,
        help=f"Максимальный размер файла в байтах (по умолчанию {DEFAULT_MAX_FILE_SIZE}).",
    )
    parser.add_argument(
        "--outline",
        action="store_true",
        help="Только оглавление (путь + docstring), без содержимого.",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Исключить тесты (test_*.py, *_test.py, tests/).",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Показать только статистику, файл не создавать.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Имя выходного файла (по умолчанию: project_dump.txt).",
    )

    return parser.parse_args()


def print_stats(files: List[Path]) -> None:
    """Печатает статистику в консоль."""
    total_size = 0
    for f in files:
        try:
            total_size += f.stat().st_size
        except OSError:
            pass

    print()
    print("📊 Статистика:")
    print(f"   Корень: {PROJECT_ROOT}")
    print(f"   Файлов найдено: {len(files)}")
    print(f"   Общий размер: {total_size / 1024 / 1024:.2f} MB")
    print(f"   Примерный размер дампа: ~{total_size * 1.1 / 1024 / 1024:.2f} MB")


def main() -> int:
    args = parse_args()

    # --- Определяем расширения ---
    if args.extensions:
        extensions = {
            e if e.startswith(".") else f".{e}"
            for e in args.extensions
        }
    else:
        extensions = DEFAULT_EXTENSIONS

    # --- Определяем, что обходить ---
    if args.files:
        files = []
        for f_str in args.files:
            p = Path(f_str)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            p = p.resolve()
            if not p.exists():
                print(f"⚠️  Файл не найден: {f_str}", file=sys.stderr)
                continue
            if should_include_file(p, extensions, args.max_size, args.no_tests):
                files.append(p)
        files.sort(key=lambda p: str(p.relative_to(PROJECT_ROOT)))
        output_default = "project_files_dump.txt"
    elif args.path:
        root = PROJECT_ROOT / args.path
        print(f"🔍 Обход: {root}")
        try:
            files = collect_files(root, extensions, args.max_size, args.no_tests)
        except FileNotFoundError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        # Имя выходного файла: project_dump_<path>.txt
        safe_path = args.path.replace("/", "_").replace("\\", "_").strip("_")
        output_default = f"project_dump_{safe_path}.txt"
    else:
        print(f"🔍 Обход: {PROJECT_ROOT} (полный дамп)")
        files = collect_files(PROJECT_ROOT, extensions, args.max_size, args.no_tests)
        output_default = "project_dump.txt"

    output_file = args.output or output_default

    print(f"📄 Расширения: {sorted(extensions)}")
    print(f"📏 Макс. размер файла: {args.max_size} байт")
    if args.no_tests:
        print("🚫 Тесты исключены")
    print(f"✅ Найдено файлов: {len(files)}")

    if args.stats_only:
        print_stats(files)
        return 0

    if not files:
        print("⚠️  Не найдено ни одного файла по заданным фильтрам.", file=sys.stderr)
        return 1

    # --- Генерация ---
    print(f"⏳ Генерация ({'оглавление' if args.outline else 'полный дамп'})...")

    if args.outline:
        content = generate_outline(files)
    else:
        content = generate_dump(files)

    # --- Сохранение ---
    output_path = PROJECT_ROOT / output_file
    output_path.write_text(content, encoding=OUTPUT_ENCODING)

    size = output_path.stat().st_size
    print(f"✅ Сохранено: {output_path}")
    print(f"📊 Размер файла: {size / 1024:.1f} KB ({size / 1024 / 1024:.2f} MB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())