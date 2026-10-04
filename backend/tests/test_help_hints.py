# backend/tests/test_help_hints.py
"""
Тесты контекстных подсказок (Итерация 15.2).

Проверяют:
  1. Pydantic-модели HelpHint / HelpHintsResponse.
  2. Структуру эндпоинта GET /api/v1/help/hints.
  3. Миграцию add_25.sql (таблица help_hint).
  4. Seed-файл add_25_seed.sql (8 подсказок).
  5. Соответствие hint_key ↔ article_slug.

Тесты структурные — БД не требуется.
"""
import inspect
import os
import re

import pytest

from app.api.v1 import help as help_module
from app.api.v1.help_models import HelpHint, HelpHintsResponse


# ==========================================
# 1. PYDANTIC-МОДЕЛИ
# ==========================================

def test_help_hint_minimal():
    """HelpHint с обязательными полями."""
    hint = HelpHint(
        hint_key="planning.recalc",
        title="Пересчёт плана",
        body_md="Кнопка **Пересчитать** активна при planDirty.",
    )
    assert hint.hint_key == "planning.recalc"
    assert hint.article_slug is None
    assert hint.display_order == 0


def test_help_hint_with_article():
    """HelpHint со ссылкой на статью."""
    hint = HelpHint(
        hint_key="gantt.edit_mode",
        title="Режим редактирования",
        body_md="Кликните ✏️ для редактирования.",
        article_slug="gantt-editing",
        display_order=10,
    )
    assert hint.article_slug == "gantt-editing"
    assert hint.display_order == 10


def test_help_hint_requires_hint_key():
    """Без hint_key — ошибка валидации."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        HelpHint(title="X", body_md="Y")


def test_help_hint_requires_title():
    """Без title — ошибка."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        HelpHint(hint_key="x", body_md="Y")


def test_help_hint_requires_body_md():
    """Без body_md — ошибка."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        HelpHint(hint_key="x", title="Y")


def test_help_hints_response_empty():
    """Пустой ответ."""
    resp = HelpHintsResponse()
    assert resp.hints == {}
    assert resp.total == 0


def test_help_hints_response_with_hints():
    """Ответ с подсказками."""
    hint = HelpHint(
        hint_key="planning.recalc",
        title="Пересчёт",
        body_md="...",
        article_slug="planning-recalculate",
    )
    resp = HelpHintsResponse(hints={"planning.recalc": hint}, total=1)
    assert "planning.recalc" in resp.hints
    assert resp.hints["planning.recalc"].title == "Пересчёт"
    assert resp.total == 1


def test_help_hint_serialization():
    """model_dump возвращает корректную структуру."""
    hint = HelpHint(
        hint_key="test",
        title="T",
        body_md="B",
        article_slug="slug",
        display_order=5,
    )
    dumped = hint.model_dump()
    assert dumped["hint_key"] == "test"
    assert dumped["article_slug"] == "slug"
    assert dumped["display_order"] == 5


# ==========================================
# 2. ЭНДПОИНТ
# ==========================================

def test_help_router_has_hints_endpoint():
    """Эндпоинт /hints зарегистрирован."""
    paths = {route.path for route in help_module.router.routes}
    assert "/api/v1/help/hints" in paths, (
        "Эндпоинт GET /api/v1/help/hints не найден"
    )


def test_hints_endpoint_is_get():
    """GET /hints."""
    route = next(
        r for r in help_module.router.routes
        if r.path == "/api/v1/help/hints"
    )
    assert "GET" in route.methods


def test_get_hints_function_exists():
    """Функция get_hints существует."""
    assert hasattr(help_module, "get_hints")
    assert callable(help_module.get_hints)


def test_get_hints_is_async():
    """get_hints — async-функция."""
    assert inspect.iscoroutinefunction(help_module.get_hints)


def test_get_hints_queries_help_hint_table():
    """SQL-запрос обращается к таблице help_hint."""
    src = inspect.getsource(help_module.get_hints)
    assert "help_hint" in src, "SQL должен читать из help_hint"
    assert "is_published" in src
    assert "organization_id" in src


def test_get_hints_returns_dict_keyed_by_hint_key():
    """Результат — словарь {hint_key: HelpHint}."""
    src = inspect.getsource(help_module.get_hints)
    assert "hints[hint.hint_key] = hint" in src, (
        "Результат должен индексироваться по hint_key"
    )


# ==========================================
# 3. МИГРАЦИЯ add_25.sql
# ==========================================

MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_25.sql"
)

SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_25_seed.sql"
)


def test_migration_add_25_exists():
    """Файл add_25.sql существует."""
    assert os.path.exists(MIGRATION_PATH), (
        "migrations/add_25.sql должен существовать"
    )


def test_migration_creates_help_hint_table():
    """CREATE TABLE IF NOT EXISTS help_hint."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE TABLE IF NOT EXISTS help_hint" in content


def test_migration_has_unique_hint_key():
    """UNIQUE (hint_key)."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "UNIQUE (hint_key)" in content


def test_migration_has_all_columns():
    """Колонки hint_key, title, body_md, article_slug, display_order."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    for col in ("hint_key", "title", "body_md", "article_slug",
                "display_order", "is_published"):
        assert col in content, f"Колонка {col} отсутствует"


def test_migration_is_idempotent():
    """IF NOT EXISTS / OR REPLACE."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "IF NOT EXISTS" in content
    assert "OR REPLACE" in content


def test_migration_wrapped_in_transaction():
    """BEGIN / COMMIT."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "BEGIN;" in content
    assert "COMMIT;" in content


def test_migration_has_trigger():
    """Триггер updated_at."""
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "trg_help_hint_updated_at" in content


# ==========================================
# 4. SEED add_25_seed.sql
# ==========================================

def test_seed_file_exists():
    """Файл add_25_seed.sql существует."""
    assert os.path.exists(SEED_PATH)


def test_seed_is_idempotent():
    """ON CONFLICT (hint_key) DO NOTHING."""
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "ON CONFLICT (hint_key) DO NOTHING" in content


def test_seed_contains_all_8_hint_keys():
    """Все 8 ключей присутствуют в seed-файле."""
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    expected_keys = [
        "planning.recalc",
        "planning.advisor",
        "planning.plan_dirty",
        "gantt.edit_mode",
        "gantt.brackets",
        "shift.lab_block",
        "whatif.json",
        "settings.system",
    ]
    for key in expected_keys:
        assert f"'{key}'" in content, f"Ключ '{key}' не найден в seed"


def test_seed_article_slugs_exist():
    """
    article_slug в seed ссылаются на реальные статьи из add_24_seed_*.
    """
    # Собираем все slug'и из add_24_seed_*
    seed_dir = os.path.join(
        os.path.dirname(__file__), "..", "migrations"
    )
    known_slugs = set()
    for i in (1, 2, 3):
        seed_file = os.path.join(seed_dir, f"add_24_seed_{i}.sql")
        if not os.path.exists(seed_file):
            continue
        with open(seed_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Ищем паттерн 'slug-name'
        for match in re.finditer(r"'\s*([a-z0-9-]+)\s*'", content):
            known_slugs.add(match.group(1))

    # Читаем article_slug из add_25_seed
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Собираем пары (hint_key, article_slug) из INSERT
    # Простой подход: ищем article_slug-строки между $md$...$md$ и запятыми
    article_slugs = re.findall(r"'([a-z][a-z0-9-]+)'\s*,\s*\d+\s*,\s*TRUE",
                               content)

    # Проверяем, что каждый article_slug — известная статья
    for slug in article_slugs:
        # slug должны быть из известных (или это hint_key)
        if '.' in slug:
            continue
        assert slug in known_slugs, (
            f"article_slug '{slug}' не найден среди статей add_24_seed_*"
        )


# ==========================================
# 5. SANITY
# ==========================================

def test_hint_key_naming_convention():
    """
    hint_key имеют формат '<module>.<action>'.
    """
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    keys = re.findall(r"'([a-z_]+\.[a-z_]+)'", content)
    # Уникальные
    unique_keys = set(keys)
    assert len(unique_keys) >= 8

    for key in unique_keys:
        parts = key.split(".")
        assert len(parts) == 2, (
            f"Ключ '{key}' должен быть в формате '<module>.<action>'"
        )
        assert all(p.islower() or '_' in p for p in parts), (
            f"Ключ '{key}' должен быть в lowercase"
        )


def test_hints_endpoint_uses_correct_response_model():
    """response_model=HelpHintsResponse."""
    route = next(
        r for r in help_module.router.routes
        if r.path == "/api/v1/help/hints"
    )
    # response_model хранится в .response_model
    assert route.response_model is HelpHintsResponse


if __name__ == "__main__":
    pytest.main([__file__, "-v"])