#!/usr/bin/env python3
"""
Скрипт сборки всего кода проекта в один текстовый файл.
Используется для передачи контекста проекта AI-ассистенту.

Использование:
    python collect_project.py                  # Сохранить в project_dump.txt
    python collect_project.py -o my_dump.txt   # Сохранить в указанный файл
    python collect_project.py --stats          # Только статистика
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# === НАСТРОЙКИ ===

# Корневая директория проекта (автоматически определяется)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Директории, которые нужно исключить
EXCLUDED_DIRS = {
    'node_modules',
    '.venv',
    'venv',
    '__pycache__',
    '.git',
    'dist',
    'build',
    '.next',
    '.cache',
    '.idea',
    '.vscode',
    'docker',  # Если не нужны конфиги Docker
}

# Расширения файлов для включения
INCLUDED_EXTENSIONS = {
    # Backend (Python)
    '.py',
    # Frontend (TypeScript/React)
    '.tsx', '.ts', '.jsx', '.js',
    # Конфиги
    '.json', '.yml', '.yaml', '.toml', '.cfg', '.ini',
    # Стили
    '.css', '.scss', '.less',
    # HTML
    '.html', '.htm',
    # SQL
    '.sql',
    # Документация
    '.md', '.txt', '.rst',
    # Docker
    '.dockerfile', 'Dockerfile',
    # Env
    '.env', '.env.example',
}

# Файлы, которые нужно исключить по имени
EXCLUDED_FILES = {
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'tsconfig.tsbuildinfo',
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    'collect_project.py',  # Сам скрипт не включаем
    'project_dump.txt',    # Предыдущий дамп не включаем
}

# Максимальный размер одного файла (1 MB) - слишком большие файлы пропускаем
MAX_FILE_SIZE = 1024 * 1024

# Кодировка вывода
OUTPUT_ENCODING = 'utf-8'


def should_include_file(file_path: Path) -> bool:
    """Проверяет, нужно ли включать файл в дамп"""
    # Проверяем имя файла
    if file_path.name in EXCLUDED_FILES:
        return False

    # Проверяем расширение
    if file_path.suffix.lower() not in INCLUDED_EXTENSIONS:
        # Исключение для Dockerfile без расширения
        if file_path.name.lower() != 'dockerfile':
            return False

    # Проверяем размер
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            print(f"  ⚠️  Пропуск большого файла: {file_path.relative_to(PROJECT_ROOT)} "
                  f"({file_path.stat().st_size / 1024:.1f} KB)")
            return False
    except OSError:
        return False

    return True


def should_include_dir(dir_path: Path) -> bool:
    """Проверяет, нужно ли обходить директорию"""
    return dir_path.name not in EXCLUDED_DIRS and not dir_path.name.startswith('.')


def collect_files(root: Path) -> list[Path]:
    """Собирает все файлы проекта в отсортированный список"""
    files = []

    for dir_path, dir_names, file_names in os.walk(root):
        dir_p = Path(dir_path)

        # Фильтруем директории "на лету" (os.walk модифицирует список)
        dir_names[:] = [d for d in dir_names if should_include_dir(dir_p / d)]

        for file_name in sorted(file_names):
            file_path = dir_p / file_name
            if should_include_file(file_path):
                files.append(file_path)

    # Сортируем по пути для стабильного порядка
    files.sort(key=lambda p: str(p.relative_to(root)))
    return files


def read_file_content(file_path: Path) -> str:
    """Читает содержимое файла с обработкой ошибок кодировки"""
    # Пробуем UTF-8
    try:
        return file_path.read_text(encoding=OUTPUT_ENCODING)
    except UnicodeDecodeError:
        # Пробуем Windows-1251 (для старых файлов)
        try:
            return file_path.read_text(encoding='windows-1251')
        except UnicodeDecodeError:
            return f"[Бинарный файл, не удалось прочитать: {file_path.name}]"
    except Exception as e:
        return f"[Ошибка чтения: {e}]"


def generate_dump(files: list[Path]) -> str:
    """Генерирует текстовый дамп проекта"""
    lines = []

    # Заголовок
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
        file_size = len(content.encode(OUTPUT_ENCODING, errors='replace'))
        total_size += file_size

        # Разделитель файла
        lines.append("")
        lines.append("─" * 80)
        lines.append(f"📄 ФАЙЛ: {rel_path}")
        lines.append(f"   Размер: {file_size:,} байт ({file_size / 1024:.1f} KB)")
        lines.append("─" * 80)
        lines.append("")

        # Содержимое файла
        lines.append(content)

        # Завершающий разделитель
        lines.append("")
        lines.append("─" * 80)
        lines.append(f"📄 КОНЕЦ ФАЙЛА: {rel_path}")
        lines.append("─" * 80)

    # Статистика в конце
    lines.append("")
    lines.append("=" * 80)
    lines.append("📊 СТАТИСТИКА")
    lines.append("=" * 80)
    lines.append(f"Всего файлов: {len(files)}")
    lines.append(f"Общий размер: {total_size:,} байт ({total_size / 1024:.1f} KB, "
                 f"{total_size / 1024 / 1024:.2f} MB)")

    # Статистика по расширениям
    ext_stats = {}
    for file_path in files:
        ext = file_path.suffix.lower() or '(без расширения)'
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


def print_stats(files: list[Path]):
    """Выводит только статистику без генерации файла"""
    print(f"\n📊 Статистика проекта:")
    print(f"   Корень: {PROJECT_ROOT}")
    print(f"   Файлов найдено: {len(files)}")

    total_size = 0
    for file_path in files:
        try:
            total_size += file_path.stat().st_size
        except OSError:
            pass

    print(f"   Общий размер: {total_size / 1024 / 1024:.2f} MB")
    print(f"   Примерный размер дампа: ~{total_size * 1.5 / 1024 / 1024:.2f} MB "
          f"(с заголовками и разделителями)")


def main():
    # Парсинг аргументов
    output_file = "project_dump.txt"
    stats_only = False

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ('-o', '--output') and i + 1 < len(args):
            output_file = args[i + 1]
        elif arg in ('--stats',):
            stats_only = True

    print(f"🔍 Сканирование проекта в: {PROJECT_ROOT}")
    print(f" Исключенные директории: {', '.join(sorted(EXCLUDED_DIRS))}")
    print(f"📄 Включаемые расширения: {', '.join(sorted(INCLUDED_EXTENSIONS))}")
    print()

    # Сбор файлов
    print("⏳ Сбор файлов...")
    files = collect_files(PROJECT_ROOT)
    print(f"✅ Найдено файлов: {len(files)}")

    if stats_only:
        print_stats(files)
        return

    # Генерация дампа
    print(f"⏳ Генерация дампа...")
    dump_content = generate_dump(files)

    # Сохранение
    output_path = PROJECT_ROOT / output_file
    output_path.write_text(dump_content, encoding=OUTPUT_ENCODING)

    file_size = output_path.stat().st_size
    print(f"✅ Дамп сохранен: {output_path}")
    print(f"📊 Размер файла: {file_size / 1024:.1f} KB ({file_size / 1024 / 1024:.2f} MB)")
    print(f"\n💡 Теперь вы можете открыть {output_file} и скопировать его содержимое "
          f"для передачи AI-ассистенту.")


if __name__ == "__main__":
    main()