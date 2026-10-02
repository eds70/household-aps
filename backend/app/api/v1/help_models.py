# backend/app/api/v1/help_models.py
"""
Pydantic-модели для API встроенной справки (Итерация 15.1).

Эндпоинты:
  GET /api/v1/help/articles       — список статей
  GET /api/v1/help/articles/{slug} — одна статья
  GET /api/v1/help/categories     — категории
  GET /api/v1/help/search         — поиск
"""
from datetime import datetime
from typing import List

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