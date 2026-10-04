# backend/tests/test_help_faq.py
"""
Тесты FAQ-статей справки (Итерация 15.4).

Проверяют:
  1. Категория 'faq' добавлена в CATEGORY_LABELS и CATEGORY_ORDER.
  2. Миграции add_26_seed_1/2/3.sql существуют.
  3. Все 15 FAQ-статей присутствуют в seed-файлах.
  4. Article slug'и из FAQ согласованы (уникальны, с префиксом 'faq-').
  5. Категория 'faq' корректно обрабатывается в API (структурно).

Тесты структурные — БД не требуется.
"""
import inspect
import os
import re

import pytest

from app.api.v1 import help as help_module


# ==========================================
# 1. КАТЕГОРИЯ FAQ
# ==========================================

def test_faq_in_category_labels():
    """CATEGORY_LABELS содержит 'faq'."""
    assert "faq" in help_module.CATEGORY_LABELS
    assert help_module.CATEGORY_LABELS["faq"] == "FAQ"


def test_faq_in_category_order():
    """CATEGORY_ORDER содержит 'faq'."""
    assert "faq" in help_module.CATEGORY_ORDER


def test_faq_is_last_in_order():
    """'faq' — последняя категория (отображается после настроек)."""
    assert help_module.CATEGORY_ORDER[-1] == "faq"


def test_category_labels_matches_order():
    """CATEGORY_LABELS и CATEGORY_ORDER содержат одни и те же ключи."""
    assert set(help_module.CATEGORY_LABELS.keys()) == set(help_module.CATEGORY_ORDER)


def test_total_categories_is_nine():
    """Всего категорий — 9 (8 базовых + faq)."""
    assert len(help_module.CATEGORY_ORDER) == 9
    assert len(help_module.CATEGORY_LABELS) == 9


# ==========================================
# 2. ФАЙЛЫ МИГРАЦИЙ
# ==========================================

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "migrations"
)

SEED_1 = os.path.join(MIGRATIONS_DIR, "add_26_seed_1.sql")
SEED_2 = os.path.join(MIGRATIONS_DIR, "add_26_seed_2.sql")
SEED_3 = os.path.join(MIGRATIONS_DIR, "add_26_seed_3.sql")


def test_seed_1_exists():
    """add_26_seed_1.sql существует."""
    assert os.path.exists(SEED_1), "migrations/add_26_seed_1.sql не найден"


def test_seed_2_exists():
    """add_26_seed_2.sql существует."""
    assert os.path.exists(SEED_2), "migrations/add_26_seed_2.sql не найден"


def test_seed_3_exists():
    """add_26_seed_3.sql существует."""
    assert os.path.exists(SEED_3), "migrations/add_26_seed_3.sql не найден"


# ==========================================
# 3. СОДЕРЖИМОЕ SEED-ФАЙЛОВ
# ==========================================

def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_seed_1_has_category_faq():
    """Каждый seed-файл использует category = 'faq'."""
    for path in (SEED_1, SEED_2, SEED_3):
        content = _read(path)
        assert "'faq'" in content, f"{os.path.basename(path)}: нет 'faq'"


def test_seed_files_are_idempotent():
    """Все seed-файлы используют ON CONFLICT (slug) DO NOTHING."""
    for path in (SEED_1, SEED_2, SEED_3):
        content = _read(path)
        assert "ON CONFLICT (slug) DO NOTHING" in content, (
            f"{os.path.basename(path)}: нет ON CONFLICT (slug) DO NOTHING"
        )


def test_seed_files_have_transaction():
    """Все seed-файлы обёрнуты в BEGIN/COMMIT."""
    for path in (SEED_1, SEED_2, SEED_3):
        content = _read(path)
        assert "BEGIN;" in content, f"{os.path.basename(path)}: нет BEGIN"
        assert "COMMIT;" in content, f"{os.path.basename(path)}: нет COMMIT"


def test_seed_files_use_global_articles():
    """Все FAQ-статьи глобальные (organization_id = NULL)."""
    for path in (SEED_1, SEED_2, SEED_3):
        content = _read(path)
        # Все INSERT начинаются с (NULL, 'faq-...
        faq_inserts = re.findall(r"\(NULL,\s*'(faq-[a-z0-9-]+)'", content)
        assert len(faq_inserts) == 5, (
            f"{os.path.basename(path)}: ожидалось 5 FAQ-статей, "
            f"найдено {len(faq_inserts)}"
        )


# ==========================================
# 4. ВСЕ 15 FAQ-СТАТЕЙ
# ==========================================

EXPECTED_FAQ_SLUGS = [
    # add_26_seed_1.sql — планирование
    "faq-plan-feasible-not-optimal",
    "faq-task-not-movable",
    "faq-plan-is-empty",
    "faq-plan-settings-empty",
    "faq-material-shortage",
    # add_26_seed_2.sql — гант, смены, what-if, чз
    "faq-move-pinned-task",
    "faq-old-version-not-archived",
    "faq-shift-mode-change",
    "faq-whatif-running",
    "faq-cz-orphan-scan",
    # add_26_seed_3.sql — лаборатория, advisor
    "faq-lab-blocked-batch",
    "faq-route-mismatch",
    "faq-cooling-degradation",
    "faq-cz-incomplete",
    "faq-underload",
]


def test_all_15_faq_slugs_present():
    """Все 15 FAQ-статей присутствуют в seed-файлах."""
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)

    for slug in EXPECTED_FAQ_SLUGS:
        assert f"'{slug}'" in all_content, (
            f"Slug '{slug}' не найден ни в одном seed-файле"
        )


def test_total_15_faq_slugs():
    """Ровно 15 FAQ-статей (не больше, не меньше)."""
    assert len(EXPECTED_FAQ_SLUGS) == 15


def test_faq_slugs_are_unique():
    """Все FAQ-slug уникальны."""
    assert len(EXPECTED_FAQ_SLUGS) == len(set(EXPECTED_FAQ_SLUGS))


def test_faq_slugs_have_prefix():
    """Все FAQ-slug начинаются с 'faq-'."""
    for slug in EXPECTED_FAQ_SLUGS:
        assert slug.startswith("faq-"), (
            f"Slug '{slug}' не начинается с 'faq-'"
        )


def test_faq_slugs_are_kebab_case():
    """Все FAQ-slug в kebab-case (только a-z, 0-9, дефисы)."""
    for slug in EXPECTED_FAQ_SLUGS:
        assert re.match(r"^faq-[a-z0-9-]+$", slug), (
            f"Slug '{slug}' не соответствует kebab-case"
        )


# ==========================================
# 5. ССЫЛКИ НА ДРУГИЕ СТАТЬИ
# ==========================================

def test_faq_articles_link_to_existing_slugs():
    """
    FAQ-статьи ссылаются на реальные slug'и из add_24_seed_*.

    Все внутренние ссылки вида [текст](/help/slug) должны
    указывать на существующие статьи.
    """
    # Собираем известные slug'и из add_24_seed_*
    seed_dir = MIGRATIONS_DIR
    known_slugs = set()
    for i in (1, 2, 3):
        seed_file = os.path.join(seed_dir, f"add_24_seed_{i}.sql")
        if not os.path.exists(seed_file):
            continue
        with open(seed_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Ищем паттерн 'slug' (в одиночных кавычках)
        for match in re.finditer(r"'([a-z][a-z0-9-]+)'\s*,", content):
            known_slugs.add(match.group(1))

    # Также добавляем FAQ-slug'и — они ссылаются друг на друга
    known_slugs.update(EXPECTED_FAQ_SLUGS)

    # Проверяем ссылки в FAQ-статьях
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)
    links = re.findall(r"\]\(/help/([a-z0-9-]+)\)", all_content)

    for link_slug in set(links):
        assert link_slug in known_slugs, (
            f"FAQ-статья ссылается на несуществующий slug '{link_slug}'. "
            f"Известные: {sorted(known_slugs)[:5]}..."
        )


def test_faq_articles_have_related_links():
    """
    Каждая FAQ-статья должна иметь блок «Связанные статьи».

    Это улучшает навигацию.
    """
    for path in (SEED_1, SEED_2, SEED_3):
        content = _read(path)
        # Считаем секции "## Связанные статьи" — должно быть 5 на файл
        related_count = content.count("## Связанные статьи")
        assert related_count == 5, (
            f"{os.path.basename(path)}: ожидалось 5 блоков "
            f"«Связанные статьи», найдено {related_count}"
        )


def test_faq_articles_have_symptom_section():
    """
    Каждая FAQ-статья должна содержать секцию с симптомом.

    Это делает статьи более понятными.
    """
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)
    # Формулировки симптомов варьируются, но обычно есть "**Симптом:**"
    symptoms = all_content.count("**Симптом:**")
    assert symptoms == 15, (
        f"Ожидалось 15 секций «Симптом:», найдено {symptoms}"
    )


# ==========================================
# 6. API (структурные)
# ==========================================

def test_list_categories_uses_category_order():
    """
    list_categories использует CATEGORY_ORDER для сортировки.

    (проверяем исходник — так как функция обёрнута в @router.get)
    """
    src = inspect.getsource(help_module.list_categories)
    assert "CATEGORY_ORDER" in src
    assert "CATEGORY_LABELS" in src


def test_list_articles_supports_faq_filter():
    """
    list_articles поддерживает фильтр по category.

    (faq-статьи будут отдаваться при ?category=faq)
    """
    src = inspect.getsource(help_module.list_articles)
    assert "category = :category" in src


def test_router_unchanged():
    """Роутер не изменил свой префикс и теги."""
    assert help_module.router.prefix == "/api/v1/help"
    assert "Справка" in help_module.router.tags


# ==========================================
# 7. SANITY
# ==========================================

def test_all_slugs_fit_db_constraint():
    """
    Все slug'и ≤ 100 символов (slug VARCHAR(100)).

    Максимальный наш slug: faq-plan-feasible-not-optimal (31 символ).
    """
    for slug in EXPECTED_FAQ_SLUGS:
        assert len(slug) <= 100, f"Slug '{slug}' длиннее 100 символов"


def test_all_titles_are_readable():
    """
    Заголовки FAQ должны быть читаемыми: непустыми и осмысленными.

    Требования:
      - длина от 5 до 200 символов;
      - первая буква (пропуская пунктуацию вроде «, ", ') — заглавная;
      - нет переводов строк.

    Замечание: заголовки могут быть сформулированы как угодно —
    вопросом, утверждением или описанием проблемы. Все три формы
    допустимы.
    """
    all_content = _read(SEED_1) + _read(SEED_2) + _read(SEED_3)

    # Ищем titles строго в шапке INSERT-блока:
    # (NULL, 'faq-slug',\n  'Title',
    titles = re.findall(
        r"\(NULL,\s*\n\s*'(faq-[a-z0-9-]+)',\s*\n\s*'([^']+)',",
        all_content,
    )
    assert len(titles) == 15, (
        f"Найдено {len(titles)} заголовков "
        f"(ожидалось 15): {[t[0] for t in titles]}"
    )

    for slug, title in titles:
        # 1. Длина
        assert 5 <= len(title) <= 200, (
            f"Заголовок '{title}' (slug={slug}) имеет недопустимую "
            f"длину: {len(title)}"
        )

        # 2. Нет переводов строк
        assert "\n" not in title, (
            f"Заголовок '{title}' (slug={slug}) содержит перевод строки"
        )

        # 3. Первая БУКВА — заглавная.
        #    Пропускаем пунктуацию в начале (кавычки, скобки, дефисы).
        first_letter = next(
            (ch for ch in title if ch.isalpha()),
            None,
        )
        assert first_letter is not None, (
            f"Заголовок '{title}' (slug={slug}) не содержит букв"
        )
        assert first_letter.isupper(), (
            f"Заголовок '{title}' (slug={slug}) должен начинаться "
            f"с заглавной буквы (первая буква: '{first_letter}')"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])