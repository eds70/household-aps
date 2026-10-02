# backend/app/api/v1/help.py
"""
API встроенной справки (Итерация 15.1).

Эндпоинты:
  GET /api/v1/help/articles                 — список статей
  GET /api/v1/help/articles/{slug}          — одна статья
  GET /api/v1/help/categories               — список категорий
  GET /api/v1/help/search?q=...             — поиск

Все эндпоинты доступны любому авторизованному пользователю.
Глобальные статьи (organization_id IS NULL) видны всем.
Статьи организации (organization_id = X) видны только ей.
"""
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from .help_models import (
    HelpArticleListItem,
    HelpArticleResponse,
    HelpArticlesListResponse,
    HelpCategoriesResponse,
    HelpCategoryResponse,
    HelpSearchHit,
    HelpSearchResponse,
)

router = APIRouter(prefix="/api/v1/help", tags=["Справка"])
logger = logging.getLogger("app.api.help")


# ==========================================
# КАТЕГОРИИ (справочник)
# ==========================================

CATEGORY_LABELS = {
    "getting-started": "Начало работы",
    "planning": "Планирование",
    "gantt": "Диаграмма Ганта",
    "shift": "Мастера смены",
    "lab": "Лаборатория",
    "cz": "Честный Знак",
    "whatif": "What-if",
    "settings": "Настройки",
}

CATEGORY_ORDER = [
    "getting-started",
    "planning",
    "gantt",
    "shift",
    "lab",
    "cz",
    "whatif",
    "settings",
]


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ
# ==========================================

def _parse_tags(raw) -> List[str]:
    """Парсит JSONB-теги в list[str]."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t) for t in raw]
    if isinstance(raw, str):
        import json
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(t) for t in parsed]
        except (ValueError, TypeError):
            pass
    return []


def _make_snippet(content: str, query: str, context_chars: int = 120) -> str:
    """
    Возвращает фрагмент контента вокруг первого вхождения query.

    Если query не найден — возвращает первые context_chars символов.
    """
    if not content:
        return ""

    lower_content = content.lower()
    lower_query = query.lower()
    idx = lower_content.find(lower_query)

    if idx < 0:
        # Не нашли — берём начало
        snippet = content[:context_chars].strip()
        if len(content) > context_chars:
            snippet += "…"
        return snippet

    start = max(0, idx - context_chars // 2)
    end = min(len(content), idx + len(query) + context_chars // 2)

    snippet = content[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(content):
        snippet = snippet + "…"

    # Убираем markdown-разметку из сниппета (простая эвристика)
    snippet = re.sub(r"[#*`>\[\]()]", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip()

    return snippet


# ==========================================
# GET /articles — список статей
# ==========================================

@router.get("/articles", response_model=HelpArticlesListResponse)
async def list_articles(
        category: Optional[str] = Query(
            default=None,
            description="Фильтр по категории. Если не задан — все.",
        ),
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает список статей справки.

    Глобальные статьи (organization_id IS NULL) видны всем.
    Статьи организации — только ей.
    """
    where = ["is_published = TRUE"]
    params: dict = {"org_id": org_id}

    where.append(
        "(organization_id IS NULL OR organization_id = :org_id)"
    )

    if category:
        where.append("category = :category")
        params["category"] = category

    result = await db.execute(
        text(f"""
            SELECT slug, title, category, tags, display_order, updated_at
            FROM help_article
            WHERE {' AND '.join(where)}
            ORDER BY category, display_order, title
        """),
        params,
    )

    rows = result.fetchall()
    articles = [
        HelpArticleListItem(
            slug=row.slug,
            title=row.title,
            category=row.category,
            tags=_parse_tags(row.tags),
            display_order=row.display_order,
            updated_at=row.updated_at,
        )
        for row in rows
    ]

    return HelpArticlesListResponse(
        articles=articles,
        total=len(articles),
    )


# ==========================================
# GET /articles/{slug} — одна статья
# ==========================================

@router.get("/articles/{slug}", response_model=HelpArticleResponse)
async def get_article(
        slug: str,
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает статью по slug."""
    result = await db.execute(
        text("""
            SELECT slug, title, category, content_md, tags,
                   display_order, updated_at
            FROM help_article
            WHERE slug = :slug
              AND is_published = TRUE
              AND (organization_id IS NULL OR organization_id = :org_id)
        """),
        {"slug": slug, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Статья '{slug}' не найдена",
        )

    return HelpArticleResponse(
        slug=row.slug,
        title=row.title,
        category=row.category,
        content_md=row.content_md,
        tags=_parse_tags(row.tags),
        display_order=row.display_order,
        updated_at=row.updated_at,
    )


# ==========================================
# GET /categories — список категорий
# ==========================================

@router.get("/categories", response_model=HelpCategoriesResponse)
async def list_categories(
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает список категорий справки с количеством статей.

    Категории без статей не показываются.
    """
    result = await db.execute(
        text("""
            SELECT category, COUNT(*) AS cnt
            FROM help_article
            WHERE is_published = TRUE
              AND (organization_id IS NULL OR organization_id = :org_id)
            GROUP BY category
        """),
        {"org_id": org_id},
    )

    counts = {row.category: int(row.cnt) for row in result.fetchall()}

    categories = []
    for key in CATEGORY_ORDER:
        if counts.get(key, 0) > 0:
            categories.append(HelpCategoryResponse(
                key=key,
                label=CATEGORY_LABELS.get(key, key),
                article_count=counts[key],
            ))

    return HelpCategoriesResponse(categories=categories)


# ==========================================
# GET /search — поиск
# ==========================================

@router.get("/search", response_model=HelpSearchResponse)
async def search_articles(
        q: str = Query(..., min_length=2, description="Поисковый запрос"),
        limit: int = Query(default=30, ge=1, le=100),
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Простой поиск по title, content_md и tags.

    Использует ILIKE (регистронезависимо). Для продакшена можно
    заменить на полнотекстовый поиск PostgreSQL.
    """
    pattern = f"%{q}%"

    result = await db.execute(
        text("""
            SELECT slug, title, category, content_md, tags
            FROM help_article
            WHERE is_published = TRUE
              AND (organization_id IS NULL OR organization_id = :org_id)
              AND (
                    title ILIKE :pattern
                 OR content_md ILIKE :pattern
                 OR tags::text ILIKE :pattern
              )
            ORDER BY
                CASE
                    WHEN title ILIKE :pattern THEN 0
                    WHEN tags::text ILIKE :pattern THEN 1
                    ELSE 2
                END,
                category,
                display_order
            LIMIT :limit
        """),
        {"org_id": org_id, "pattern": pattern, "limit": limit},
    )

    rows = result.fetchall()
    hits = [
        HelpSearchHit(
            slug=row.slug,
            title=row.title,
            category=row.category,
            snippet=_make_snippet(row.content_md or "", q),
        )
        for row in rows
    ]

    return HelpSearchResponse(
        query=q,
        hits=hits,
        total=len(hits),
    )