# backend/tests/test_help.py
"""
Тесты API встроенной справки (Итерация 15.1).

Проверяют:
  1. Pydantic-модели.
  2. Константы категорий.
  3. Хелперы (_parse_tags, _make_snippet).
  4. Структуру модулей (роутеры, эндпоинты).
  5. Миграцию add_24.sql.
  6. Seed-файлы add_24_seed_*.sql.
  7. Безопасность help_docs (path traversal).

Тесты структурные — БД не требуется.
"""
import inspect
import os
from datetime import datetime, timezone

import pytest

from app.api.v1 import help as help_module
from app.api.v1 import help_docs as help_docs_module
from app.api.v1.help_models import (
    HelpArticleListItem,
    HelpArticleResponse,
    HelpArticlesListResponse,
    HelpCategoriesResponse,
    HelpCategoryResponse,
    HelpSearchHit,
    HelpSearchResponse,
)


# ==========================================
# 1. МОДЕЛИ
# ==========================================

def test_help_article_list_item():
    item = HelpArticleListItem(
        slug="intro-overview",
        title="Обзор системы",
        category="getting-started",
        tags=["обзор"],
        display_order=10,
        updated_at=datetime.now(timezone.utc),
    )
    assert item.slug == "intro-overview"
    assert item.tags == ["обзор"]


def test_help_article_response():
    art = HelpArticleResponse(
        slug="gantt-overview",
        title="Обзор Ганта",
        category="gantt",
        content_md="# Заголовок\n\nТекст.",
        tags=[],
        display_order=10,
        updated_at=datetime.now(timezone.utc),
    )
    assert art.content_md.startswith("# Заголовок")


def test_help_category_response():
    cat = HelpCategoryResponse(
        key="planning",
        label="Планирование",
        article_count=4,
    )
    assert cat.key == "planning"
    assert cat.article_count == 4


def test_help_categories_response():
    resp = HelpCategoriesResponse(categories=[
        HelpCategoryResponse(key="gantt", label="Гант", article_count=4),
    ])
    assert len(resp.categories) == 1


def test_help_articles_list_response():
    resp = HelpArticlesListResponse(articles=[], total=0)
    assert resp.total == 0
    assert resp.articles == []


def test_help_search_hit():
    hit = HelpSearchHit(
        slug="gantt-editing",
        title="Редактирование",
        category="gantt",
        snippet="...перетаскивание задачи...",
    )
    assert hit.slug == "gantt-editing"


def test_help_search_response():
    resp = HelpSearchResponse(query="гант", hits=[], total=0)
    assert resp.query == "гант"
    assert resp.total == 0


# ==========================================
# 2. КОНСТАНТЫ
# ==========================================

def test_category_labels_has_all_keys():
    """CATEGORY_LABELS содержит все 8 категорий."""
    expected = {
        "getting-started", "planning", "gantt", "shift",
        "lab", "cz", "whatif", "settings",
    }
    assert set(help_module.CATEGORY_LABELS.keys()) == expected


def test_category_order_matches_labels():
    """CATEGORY_ORDER содержит те же ключи, что CATEGORY_LABELS."""
    assert set(help_module.CATEGORY_ORDER) == set(
        help_module.CATEGORY_LABELS.keys()
    )


def test_category_order_is_deterministic():
    """Порядок категорий фиксирован."""
    assert help_module.CATEGORY_ORDER[0] == "getting-started"
    assert help_module.CATEGORY_ORDER[-1] == "settings"


# ==========================================
# 3. ХЕЛПЕРЫ
# ==========================================

def test_parse_tags_from_list():
    assert help_module._parse_tags(["a", "b"]) == ["a", "b"]


def test_parse_tags_from_json_string():
    assert help_module._parse_tags('["a", "b"]') == ["a", "b"]


def test_parse_tags_from_none():
    assert help_module._parse_tags(None) == []


def test_parse_tags_from_bad_string():
    assert help_module._parse_tags("not json") == []


def test_make_snippet_finds_query():
    content = "A" * 100 + " НАЙДЕНО " + "B" * 100
    snippet = help_module._make_snippet(content, "НАЙДЕНО")
    assert "НАЙДЕНО" in snippet


def test_make_snippet_no_query():
    content = "Просто текст без совпадений"
    snippet = help_module._make_snippet(content, "xyz")
    assert snippet.startswith("Просто текст")


def test_make_snippet_empty_content():
    assert help_module._make_snippet("", "x") == ""


def test_make_snippet_strips_markdown():
    content = "# Заголовок\n\n**жирный** текст с `кодом`"
    snippet = help_module._make_snippet(content, "текст")
    assert "#" not in snippet
    assert "**" not in snippet
    assert "`" not in snippet


# ==========================================
# 4. СТРУКТУРА МОДУЛЕЙ
# ==========================================

def test_help_router_prefix():
    assert help_module.router.prefix == "/api/v1/help"
    assert "Справка" in help_module.router.tags


def test_help_docs_router_prefix():
    assert help_docs_module.router.prefix == "/api/v1/help/docs"


def test_help_has_all_endpoints():
    paths = {route.path for route in help_module.router.routes}
    expected = {
        "/api/v1/help/articles",
        "/api/v1/help/articles/{slug}",
        "/api/v1/help/categories",
        "/api/v1/help/search",
    }
    assert expected.issubset(paths), f"Не хватает: {expected - paths}"


def test_help_docs_has_endpoint():
    paths = {route.path for route in help_docs_module.router.routes}
    assert "/api/v1/help/docs/{filename}" in paths


# ==========================================
# 5. БЕЗОПАСНОСТЬ help_docs
# ==========================================

def test_help_docs_rejects_non_md():
    """Файлы без .md отклоняются."""
    src = inspect.getsource(help_docs_module.get_doc_file)
    assert '.endswith(".md")' in src


def test_help_docs_rejects_path_traversal():
    """Имя файла не должно содержать /, \\, .. ."""
    src = inspect.getsource(help_docs_module.get_doc_file)
    assert '"/"' in src or "'/'" in src
    assert '"\\\\"' in src or "'\\\\'" in src
    assert '".."' in src or "'..'" in src


def test_help_docs_has_size_limit():
    """Ограничение размера файла."""
    assert help_docs_module.MAX_FILE_SIZE == 1024 * 1024


# ==========================================
# 6. МИГРАЦИЯ add_24.sql
# ==========================================

MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "add_24.sql"
)


def test_migration_add_24_exists():
    assert os.path.exists(MIGRATION_PATH)


def test_migration_creates_help_article_table():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE TABLE IF NOT EXISTS help_article" in content


def test_migration_has_unique_slug():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "UNIQUE (slug)" in content


def test_migration_has_indexes():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "idx_help_article_category" in content
    assert "idx_help_article_tags" in content


def test_migration_has_trigger():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "trg_help_article_updated_at" in content


def test_migration_is_idempotent():
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "IF NOT EXISTS" in content
    assert "ON CONFLICT" in content or "DROP TRIGGER IF EXISTS" in content


# ==========================================
# 7. SEED-ФАЙЛЫ
# ==========================================

SEED_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "migrations",
                 f"add_24_seed_{i}.sql")
    for i in (1, 2, 3)
]


def test_seed_files_exist():
    for path in SEED_PATHS:
        assert os.path.exists(path), f"Не найден {path}"


def test_seed_files_are_idempotent():
    for path in SEED_PATHS:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "ON CONFLICT (slug) DO NOTHING" in content


def test_seed_files_contain_all_slugs():
    """Все 15 slug присутствуют в трёх seed-файлах."""
    all_content = ""
    for path in SEED_PATHS:
        with open(path, "r", encoding="utf-8") as f:
            all_content += f.read()

    expected_slugs = [
        "intro-overview", "intro-first-plan",
        "planning-build-plan", "planning-history",
        "planning-recalculate", "planning-advisor",
        "gantt-overview", "gantt-editing",
        "gantt-grouping", "gantt-filters",
        "shift-overview", "lab-blocks", "cz-overview",
        "whatif-overview", "settings-app-vs-plan",
    ]
    for slug in expected_slugs:
        assert f"'{slug}'" in all_content, f"Slug '{slug}' не найден в seed"


# ==========================================
# 8. РЕГИСТРАЦИЯ В MAIN.PY
# ==========================================

def test_main_includes_help_routers():
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert "help_router" in src
    assert "help_docs_router" in src
    assert "include_router(help_router)" in src
    assert "include_router(help_docs_router)" in src


def test_main_has_help_tag():
    from app import main as main_module
    src = inspect.getsource(main_module)
    assert '"Справка"' in src or "'Справка'" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])