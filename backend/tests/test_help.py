# backend/tests/test_help.py
"""
Тесты API встроенной справки (Итерация 15.1 + 15.5).

Проверяют:
  1. Pydantic-модели (чтение + CRUD).
  2. Константы категорий.
  3. Хелперы (_parse_tags, _make_snippet, _slugify).
  4. Структуру модулей (роутеры, эндпоинты).
  5. Миграцию add_24.sql.
  6. Seed-файлы add_24_seed_*.sql.
  7. Безопасность help_docs (path traversal).
  8. Итерация 15.5: CRUD-эндпоинты.

Тесты структурные — БД не требуется.
"""
import inspect
import os
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.v1 import help as help_module
from app.api.v1 import help_docs as help_docs_module
from app.api.v1.help_models import (
    HelpArticleCreate,
    HelpArticleDeleteResponse,
    HelpArticleListItem,
    HelpArticleResponse,
    HelpArticlesListResponse,
    HelpArticleUpdate,
    HelpCategoriesResponse,
    HelpCategoryResponse,
    HelpHint,
    HelpHintsResponse,
    HelpSearchHit,
    HelpSearchResponse,
)


# ==========================================
# 1. МОДЕЛИ (чтение)
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


def test_help_hint():
    hint = HelpHint(
        hint_key="planning.recalc",
        title="Пересчёт",
        body_md="...",
        article_slug="planning-recalculate",
        display_order=10,
    )
    assert hint.hint_key == "planning.recalc"
    assert hint.article_slug == "planning-recalculate"


def test_help_hints_response():
    resp = HelpHintsResponse(
        hints={
            "planning.recalc": HelpHint(
                hint_key="planning.recalc",
                title="Пересчёт",
                body_md="...",
            ),
        },
        total=1,
    )
    assert "planning.recalc" in resp.hints
    assert resp.total == 1


# ==========================================
# 2. КОНСТАНТЫ
# ==========================================

def test_category_labels_has_all_keys():
    """CATEGORY_LABELS содержит все 9 категорий (включая faq)."""
    expected = {
        "getting-started", "planning", "gantt", "shift",
        "lab", "cz", "whatif", "settings", "faq",
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
    assert help_module.CATEGORY_ORDER[-1] == "faq"


# ==========================================
# 3. ХЕЛПЕРЫ (чтение)
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
        "/api/v1/help/hints",
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


# ==========================================
# ==========================================
#  ИТЕРАЦИЯ 15.5: CRUD-ЭНДПОИНТЫ
# ==========================================
# ==========================================


# ------------------------------------------
# 8.1. Pydantic-модели CRUD
# ------------------------------------------

def test_article_create_minimal():
    """Минимальный запрос на создание."""
    payload = HelpArticleCreate(
        title="Новая статья",
        category="planning",
        content_md="# Содержимое",
    )
    assert payload.title == "Новая статья"
    assert payload.slug is None
    assert payload.tags == []
    assert payload.is_published is True
    assert payload.display_order is None


def test_article_create_full():
    """Полный запрос на создание."""
    payload = HelpArticleCreate(
        title="Новая статья",
        slug="custom-slug",
        category="gantt",
        content_md="# Содержимое",
        tags=["a", "b"],
        display_order=42,
        is_published=False,
    )
    assert payload.slug == "custom-slug"
    assert payload.tags == ["a", "b"]
    assert payload.display_order == 42
    assert payload.is_published is False


def test_article_create_short_title_rejected():
    """Заголовок короче 3 символов — ошибка."""
    with pytest.raises(ValidationError):
        HelpArticleCreate(
            title="ab",
            category="planning",
            content_md="x",
        )


def test_article_create_empty_content_rejected():
    """Пустое содержимое — ошибка."""
    with pytest.raises(ValidationError):
        HelpArticleCreate(
            title="Тестовая статья",
            category="planning",
            content_md="",
        )


def test_article_update_all_optional():
    """Update — все поля опциональны."""
    payload = HelpArticleUpdate()
    assert payload.title is None
    assert payload.slug is None
    assert payload.category is None
    assert payload.content_md is None
    assert payload.tags is None
    assert payload.display_order is None
    assert payload.is_published is None


def test_article_update_partial():
    """Update — только часть полей."""
    payload = HelpArticleUpdate(title="Новый заголовок")
    assert payload.title == "Новый заголовок"
    assert payload.content_md is None


def test_article_update_negative_display_order_rejected():
    """display_order < 0 — ошибка."""
    with pytest.raises(ValidationError):
        HelpArticleUpdate(display_order=-5)


def test_article_delete_response():
    """Модель ответа на удаление."""
    resp = HelpArticleDeleteResponse(
        status="success",
        slug="test-article",
        message="Статья удалена",
    )
    assert resp.status == "success"
    assert resp.slug == "test-article"


def test_article_create_long_title_rejected():
    """Заголовок длиннее 200 символов — ошибка."""
    with pytest.raises(ValidationError):
        HelpArticleCreate(
            title="x" * 201,
            category="planning",
            content_md="y",
        )


# ------------------------------------------
# 8.2. Хелпер _slugify
# ------------------------------------------

def test_slugify_simple_latin():
    """Простой латинский текст."""
    assert help_module._slugify("Hello World") == "hello-world"


def test_slugify_cyrillic():
    """Кириллица транслитерируется."""
    # "Первый план за 5 минут" → "pervyy-plan-za-5-minut"
    result = help_module._slugify("Первый план за 5 минут")
    assert result == "pervyy-plan-za-5-minut"


def test_slugify_punctuation_removed():
    """Пунктуация заменяется дефисами."""
    result = help_module._slugify("Hello, World! (2026)")
    assert result == "hello-world-2026"


def test_slugify_multiple_hyphens_collapsed():
    """Повторные дефисы склеиваются."""
    result = help_module._slugify("Hello   ---   World")
    assert result == "hello-world"


def test_slugify_trim_hyphens():
    """Дефисы по краям обрезаются."""
    assert help_module._slugify("--- hello ---") == "hello"


def test_slugify_empty_returns_fallback():
    """Пустая строка → 'article'."""
    assert help_module._slugify("") == "article"


def test_slugify_only_punctuation_returns_fallback():
    """Строка из одной пунктуации → 'article'."""
    assert help_module._slugify("!!!???") == "article"


def test_slugify_truncates_to_100_chars():
    """Результат не длиннее 100 символов."""
    long_text = "a" * 250
    result = help_module._slugify(long_text)
    assert len(result) <= 100
    assert result == "a" * 100


# ------------------------------------------
# 8.3. Роутер: наличие и методы эндпоинтов
# ------------------------------------------

def test_router_has_create_endpoint():
    """POST /articles зарегистрирован."""
    methods_by_path = {}
    for route in help_module.router.routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods)

    assert "/api/v1/help/articles" in methods_by_path
    assert "POST" in methods_by_path["/api/v1/help/articles"]


def test_router_has_update_endpoint():
    """PUT /articles/{slug} зарегистрирован."""
    methods_by_path = {}
    for route in help_module.router.routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods)

    assert "/api/v1/help/articles/{slug}" in methods_by_path
    assert "PUT" in methods_by_path["/api/v1/help/articles/{slug}"]


def test_router_has_delete_endpoint():
    """DELETE /articles/{slug} зарегистрирован."""
    methods_by_path = {}
    for route in help_module.router.routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods)

    assert "/api/v1/help/articles/{slug}" in methods_by_path
    assert "DELETE" in methods_by_path["/api/v1/help/articles/{slug}"]


def test_crud_handlers_exist():
    """Функции-обработчики CRUD существуют."""
    assert hasattr(help_module, "create_article")
    assert hasattr(help_module, "update_article")
    assert hasattr(help_module, "delete_article")


def test_crud_handlers_are_async():
    """Все CRUD-обработчики — async."""
    assert inspect.iscoroutinefunction(help_module.create_article)
    assert inspect.iscoroutinefunction(help_module.update_article)
    assert inspect.iscoroutinefunction(help_module.delete_article)


# ------------------------------------------
# 8.4. Защита CRUD (require_admin)
# ------------------------------------------

def test_create_article_requires_admin():
    """create_article зависит от require_admin."""
    src = inspect.getsource(help_module.create_article)
    assert "require_admin" in src


def test_update_article_requires_admin():
    """update_article зависит от require_admin."""
    src = inspect.getsource(help_module.update_article)
    assert "require_admin" in src


def test_delete_article_requires_admin():
    """delete_article зависит от require_admin."""
    src = inspect.getsource(help_module.delete_article)
    assert "require_admin" in src


# ------------------------------------------
# 8.5. Структурные проверки CRUD
# ------------------------------------------

def test_create_article_validates_category():
    """create_article проверяет, что категория известна."""
    src = inspect.getsource(help_module.create_article)
    assert "CATEGORY_LABELS" in src


def test_create_article_generates_slug():
    """create_article использует _slugify."""
    src = inspect.getsource(help_module.create_article)
    assert "_slugify" in src


def test_create_article_checks_slug_conflict():
    """create_article проверяет конфликт slug."""
    src = inspect.getsource(help_module.create_article)
    assert "_check_slug_conflict" in src


def test_update_article_checks_slug_conflict():
    """update_article проверяет конфликт slug."""
    src = inspect.getsource(help_module.update_article)
    assert "_check_slug_conflict" in src


def test_delete_article_returns_slug():
    """delete_article использует RETURNING slug."""
    src = inspect.getsource(help_module.delete_article)
    assert "RETURNING slug" in src


def test_crud_helpers_exist():
    """Вспомогательные функции CRUD существуют."""
    assert hasattr(help_module, "_slugify")
    assert hasattr(help_module, "_check_slug_conflict")
    assert hasattr(help_module, "_next_display_order")


def test_check_slug_conflict_is_async():
    """_check_slug_conflict — async."""
    assert inspect.iscoroutinefunction(help_module._check_slug_conflict)


def test_next_display_order_is_async():
    """_next_display_order — async."""
    assert inspect.iscoroutinefunction(help_module._next_display_order)


# ------------------------------------------
# 8.6. HTTP-контракты (без токена → 401/403)
# ------------------------------------------

def test_post_articles_requires_auth():
    """POST /articles без токена → 401/403."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/help/articles",
        json={
            "title": "Test",
            "category": "planning",
            "content_md": "text",
        },
    )
    assert response.status_code in (401, 403)


def test_put_articles_requires_auth():
    """PUT /articles/{slug} без токена → 401/403."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.put(
        "/api/v1/help/articles/some-slug",
        json={"title": "New"},
    )
    assert response.status_code in (401, 403)


def test_delete_articles_requires_auth():
    """DELETE /articles/{slug} без токена → 401/403."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.delete("/api/v1/help/articles/some-slug")
    assert response.status_code in (401, 403)


# ------------------------------------------
# 8.7. Sanity
# ------------------------------------------

def test_slugify_idempotent_for_clean_slug():
    """Slug из kebab-case остаётся неизменным."""
    assert help_module._slugify("planning-recalculate") == "planning-recalculate"
    assert help_module._slugify("gantt-overview") == "gantt-overview"
    assert help_module._slugify("faq-plan-is-empty") == "faq-plan-is-empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])