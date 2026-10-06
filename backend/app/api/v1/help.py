# backend/app/api/v1/help.py
"""
API встроенной справки (Итерация 15.1 + 15.2 + 15.4 + 15.5).

Эндпоинты:
  GET    /api/v1/help/articles                 — список статей
  GET    /api/v1/help/articles/{slug}          — одна статья
  POST   /api/v1/help/articles                 — создать статью (ADMIN) [15.5]
  PUT    /api/v1/help/articles/{slug}          — обновить статью (ADMIN) [15.5]
  DELETE /api/v1/help/articles/{slug}          — удалить статью (ADMIN) [15.5]
  GET    /api/v1/help/categories               — список категорий
  GET    /api/v1/help/search?q=...             — поиск
  GET    /api/v1/help/hints                    — контекстные подсказки (15.2)

Все GET-эндпоинты доступны любому авторизованному пользователю.
CRUD-эндпоинты (POST/PUT/DELETE) доступны только ADMIN (Итерация 15.5).
Глобальные статьи (organization_id IS NULL) видны всем.
Статьи организации (organization_id = X) видны только ей.
"""
import json
import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_db_session,
    require_admin,
)
from .help_models import (
    HelpArticleCreate,
    HelpArticleDeleteResponse,
    HelpArticleListItem,
    HelpArticleResponse,
    HelpArticleUpdate,
    HelpArticlesListResponse,
    HelpCategoriesResponse,
    HelpCategoryResponse,
    HelpHint,
    HelpHintsResponse,
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
    # Итерация 15.4: категория FAQ
    "faq": "FAQ",
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
    # Итерация 15.4: FAQ — последняя категория
    "faq",
]


# ==========================================
# Итерация 15.5: утилиты для slug
# ==========================================

# Простая транслитерация RU → EN для генерации slug из заголовка.
_TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    " ": "-", "_": "-",
}


def _slugify(text_value: str) -> str:
    """
    Генерирует slug из произвольной строки (обычно — заголовка).

    Алгоритм:
      1. Lowercase.
      2. Транслитерация RU → EN.
      3. Замена всех не-буквенно-цифровых символов на дефис.
      4. Склейка повторных дефисов.
      5. Обрезка дефисов по краям.
      6. Обрезка до 100 символов.
    """
    lower = text_value.lower().strip()
    translit = "".join(_TRANSLIT_MAP.get(ch, ch) for ch in lower)
    cleaned = re.sub(r"[^a-z0-9\-]+", "-", translit)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:100] or "article"


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


async def _check_slug_conflict(
        db: AsyncSession,
        slug: str,
        exclude_id: Optional[str] = None,
) -> bool:
    """
    Проверяет, что slug не занят (кроме exclude_id — для update).

    Возвращает True, если конфликт есть.
    """
    if exclude_id is None:
        result = await db.execute(
            text("SELECT id FROM help_article WHERE slug = :slug"),
            {"slug": slug},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id FROM help_article
                WHERE slug = :slug AND id::text <> :exclude_id
            """),
            {"slug": slug, "exclude_id": exclude_id},
        )
    return result.fetchone() is not None


async def _next_display_order(
        db: AsyncSession,
        category: str,
) -> int:
    """Возвращает следующий display_order для категории."""
    result = await db.execute(
        text("""
            SELECT COALESCE(MAX(display_order), 0) AS max_order
            FROM help_article
            WHERE category = :category
        """),
        {"category": category},
    )
    row = result.fetchone()
    max_order = int(row.max_order) if row and row.max_order is not None else 0
    return max_order + 10


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
# ИТЕРАЦИЯ 15.5: POST /articles — создать статью
# ==========================================

@router.post("/articles", response_model=HelpArticleResponse, status_code=201)
async def create_article(
        payload: HelpArticleCreate,
        current_user: dict = Depends(require_admin),
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Создаёт новую статью справки. Доступно только ADMIN (Итерация 15.5).

    Логика:
      1. Если slug не задан — генерируется из title.
      2. Проверяется уникальность slug.
      3. Проверяется, что category входит в CATEGORY_LABELS.
      4. display_order: если не задан — max+10 в категории.
      5. organization_id = org_id (статья привязана к организации пользователя).

    Теги сериализуются в JSONB.
    """
    # 1. Категория должна быть известной
    if payload.category not in CATEGORY_LABELS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Неизвестная категория: '{payload.category}'. "
                f"Допустимые: {sorted(CATEGORY_LABELS.keys())}"
            ),
        )

    # 2. Slug
    slug = payload.slug.strip() if payload.slug else _slugify(payload.title)
    if not slug:
        raise HTTPException(
            status_code=400,
            detail="Не удалось сгенерировать slug из title",
        )

    if await _check_slug_conflict(db, slug):
        raise HTTPException(
            status_code=409,
            detail=f"Статья со slug '{slug}' уже существует",
        )

    # 3. display_order
    display_order = payload.display_order
    if display_order is None:
        display_order = await _next_display_order(db, payload.category)

    # 4. INSERT
    tags_json = json.dumps(payload.tags, ensure_ascii=False)
    result = await db.execute(
        text("""
            INSERT INTO help_article
                (organization_id, slug, title, category, content_md,
                 tags, display_order, is_published)
            VALUES
                (:org_id, :slug, :title, :category, :content_md,
                 CAST(:tags AS jsonb), :display_order, :is_published)
            RETURNING slug, title, category, content_md, tags,
                      display_order, updated_at
        """),
        {
            "org_id": org_id,
            "slug": slug,
            "title": payload.title,
            "category": payload.category,
            "content_md": payload.content_md,
            "tags": tags_json,
            "display_order": display_order,
            "is_published": payload.is_published,
        },
    )
    row = result.fetchone()
    await db.commit()

    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать статью")

    logger.info(
        f"[help] Создана статья slug='{row.slug}' "
        f"(user={current_user.get('email')})"
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
# ИТЕРАЦИЯ 15.5: PUT /articles/{slug} — обновить статью
# ==========================================

@router.put("/articles/{slug}", response_model=HelpArticleResponse)
async def update_article(
        slug: str,
        payload: HelpArticleUpdate,
        current_user: dict = Depends(require_admin),
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Обновляет статью справки. Доступно только ADMIN (Итерация 15.5).

    Логика:
      1. Находит статью по slug (в рамках организации).
      2. Проверяет, что новая category (если задана) — известная.
      3. Проверяет, что новый slug (если задан) — не занят.
      4. Обновляет только переданные поля.
      5. Теги сериализуются в JSONB.
    """
    # 1. Найти статью
    existing = await db.execute(
        text("""
            SELECT id, slug, title, category, content_md, tags,
                   display_order, is_published, updated_at
            FROM help_article
            WHERE slug = :slug
              AND organization_id = :org_id
        """),
        {"slug": slug, "org_id": org_id},
    )
    row = existing.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Статья '{slug}' не найдена или недоступна для редактирования",
        )

    article_id = str(row.id)

    # 2. Категория
    if payload.category is not None and payload.category not in CATEGORY_LABELS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Неизвестная категория: '{payload.category}'. "
                f"Допустимые: {sorted(CATEGORY_LABELS.keys())}"
            ),
        )

    # 3. Slug
    new_slug = None
    if payload.slug is not None:
        new_slug = payload.slug.strip()
        if not new_slug:
            raise HTTPException(status_code=400, detail="slug не может быть пустым")
        if new_slug != slug:
            if await _check_slug_conflict(db, new_slug, exclude_id=article_id):
                raise HTTPException(
                    status_code=409,
                    detail=f"Статья со slug '{new_slug}' уже существует",
                )

    # 4. Собираем UPDATE
    updates: Dict[str, object] = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if new_slug is not None:
        updates["slug"] = new_slug
    if payload.category is not None:
        updates["category"] = payload.category
    if payload.content_md is not None:
        updates["content_md"] = payload.content_md
    if payload.tags is not None:
        updates["tags"] = json.dumps(payload.tags, ensure_ascii=False)
    if payload.display_order is not None:
        updates["display_order"] = payload.display_order
    if payload.is_published is not None:
        updates["is_published"] = payload.is_published

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Нет данных для обновления",
        )

    # 5. Формируем SQL
    set_parts = []
    params: Dict[str, object] = {"article_id": article_id}
    for key, value in updates.items():
        if key == "tags":
            set_parts.append(f"{key} = CAST(:{key} AS jsonb)")
        else:
            set_parts.append(f"{key} = :{key}")
        params[key] = value

    query = text(f"""
        UPDATE help_article
        SET {', '.join(set_parts)}
        WHERE id = :article_id
        RETURNING slug, title, category, content_md, tags,
                  display_order, updated_at
    """)

    result = await db.execute(query, params)
    updated = result.fetchone()
    await db.commit()

    if not updated:
        raise HTTPException(status_code=500, detail="Не удалось обновить статью")

    logger.info(
        f"[help] Обновлена статья slug='{updated.slug}' "
        f"(user={current_user.get('email')}, "
        f"fields={list(updates.keys())})"
    )

    return HelpArticleResponse(
        slug=updated.slug,
        title=updated.title,
        category=updated.category,
        content_md=updated.content_md,
        tags=_parse_tags(updated.tags),
        display_order=updated.display_order,
        updated_at=updated.updated_at,
    )


# ==========================================
# ИТЕРАЦИЯ 15.5: DELETE /articles/{slug} — удалить статью
# ==========================================

@router.delete(
    "/articles/{slug}",
    response_model=HelpArticleDeleteResponse,
)
async def delete_article(
        slug: str,
        current_user: dict = Depends(require_admin),
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Удаляет статью справки. Доступно только ADMIN (Итерация 15.5).

    Статья удаляется физически. Если нужно скрыть — используйте
    PUT с is_published=false.
    """
    result = await db.execute(
        text("""
            DELETE FROM help_article
            WHERE slug = :slug AND organization_id = :org_id
            RETURNING slug
        """),
        {"slug": slug, "org_id": org_id},
    )
    row = result.fetchone()
    await db.commit()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Статья '{slug}' не найдена или недоступна для удаления",
        )

    logger.info(
        f"[help] Удалена статья slug='{row.slug}' "
        f"(user={current_user.get('email')})"
    )

    return HelpArticleDeleteResponse(
        status="success",
        slug=row.slug,
        message=f"Статья '{row.slug}' удалена",
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


# ==========================================
# ИТЕРАЦИЯ 15.2: GET /hints — контекстные подсказки
# ==========================================

@router.get("/hints", response_model=HelpHintsResponse)
async def get_hints(
        org_id=Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает словарь всех опубликованных подсказок.

    Формат ответа:
      {
        "hints": {
          "planning.recalc": {
            "hint_key": "planning.recalc",
            "title": "Пересчёт плана",
            "body_md": "...",
            "article_slug": "planning-recalculate",
            "display_order": 10
          },
          ...
        },
        "total": 8
      }

    Фронт загружает один раз и кэширует в HelpHintsContext.
    Используется через useHint(hintKey).
    """
    result = await db.execute(
        text("""
            SELECT hint_key, title, body_md, article_slug, display_order
            FROM help_hint
            WHERE is_published = TRUE
              AND (organization_id IS NULL OR organization_id = :org_id)
            ORDER BY display_order, hint_key
        """),
        {"org_id": org_id},
    )

    hints: Dict[str, HelpHint] = {}
    for row in result.fetchall():
        hint = HelpHint(
            hint_key=row.hint_key,
            title=row.title,
            body_md=row.body_md,
            article_slug=row.article_slug,
            display_order=row.display_order,
        )
        hints[hint.hint_key] = hint

    return HelpHintsResponse(
        hints=hints,
        total=len(hints),
    )