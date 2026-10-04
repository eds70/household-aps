# backend/app/api/v1/help_models.py
"""
Pydantic-модели для API встроенной справки (Итерация 15.1 + 15.2).

Эндпоинты:
  GET /api/v1/help/articles       — список статей
  GET /api/v1/help/articles/{slug} — одна статья
  GET /api/v1/help/categories     — категории
  GET /api/v1/help/search         — поиск
  GET /api/v1/help/hints          — контекстные подсказки (Итерация 15.2)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# СТАТЬЯ
# ==========================================

class HelpArticleListItem(BaseModel):
    """Краткая информация о статье (для списка)."""
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    category: str
    tags: List[str] = Field(default_factory=list)
    display_order: int = 0
    updated_at: datetime


class HelpArticleResponse(BaseModel):
    """Полная статья с markdown-контентом."""
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    category: str
    content_md: str
    tags: List[str] = Field(default_factory=list)
    display_order: int = 0
    updated_at: datetime


# ==========================================
# КАТЕГОРИИ
# ==========================================

class HelpCategoryResponse(BaseModel):
    """Категория справки."""
    key: str
    label: str
    article_count: int = 0


class HelpCategoriesResponse(BaseModel):
    """Список категорий."""
    categories: List[HelpCategoryResponse]


# ==========================================
# СПИСКИ
# ==========================================

class HelpArticlesListResponse(BaseModel):
    """Список статей."""
    articles: List[HelpArticleListItem]
    total: int


# ==========================================
# ПОИСК
# ==========================================

class HelpSearchHit(BaseModel):
    """Один результат поиска."""
    slug: str
    title: str
    category: str
    snippet: str = Field(
        ...,
        description="Фрагмент контента вокруг найденного совпадения",
    )


class HelpSearchResponse(BaseModel):
    """Результаты поиска."""
    query: str
    hits: List[HelpSearchHit]
    total: int


# ==========================================
# ИТЕРАЦИЯ 15.2: КОНТЕКСТНЫЕ ПОДСКАЗКИ
# ==========================================

class HelpHint(BaseModel):
    """
    Одна контекстная подсказка.

    Используется в UI через компонент <Hint id="hint_key"/>.
    """
    hint_key: str = Field(
        ...,
        description="Уникальный ключ, например 'planning.recalc'",
    )
    title: str = Field(
        ...,
        description="Заголовок подсказки для Popover",
    )
    body_md: str = Field(
        ...,
        description="Markdown-тело (короткое, 2-3 предложения)",
    )
    article_slug: Optional[str] = Field(
        default=None,
        description=(
            "Slug статьи справки для подробностей. "
            "Если NULL — кнопка «Читать подробнее» не показывается."
        ),
    )
    display_order: int = 0


class HelpHintsResponse(BaseModel):
    """
    Словарь всех подсказок, доступных пользователю.

    Формат: {"planning.recalc": HelpHint, "gantt.edit_mode": HelpHint, ...}

    Фронт кэширует ответ в HelpHintsContext и раздаёт через
    useHint(hintKey).
    """
    hints: dict[str, HelpHint] = Field(
        default_factory=dict,
        description="Словарь {hint_key: HelpHint}",
    )
    total: int = Field(
        default=0,
        description="Общее количество подсказок",
    )