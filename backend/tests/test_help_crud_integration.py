# backend/tests/test_help_crud_integration.py
"""
Интеграционные тесты CRUD-эндпоинтов справки (Итерация 15.5).

Требуют:
  - запущенной PostgreSQL;
  - применённых миграций add_24.sql (help_article).

Если БД недоступна — все тесты автоматически skip'аются
(см. фикстуру async_session в conftest.py).

Проверяют:
  1. POST /articles — создание (успех, конфликт slug, невалидная
     категория, авто-генерация slug, авто display_order).
  2. PUT /articles/{slug} — обновление (успех, частичное,
     смена slug, конфликт, 404).
  3. DELETE /articles/{slug} — удаление (успех, 404).
  4. Права: PLANNER/MASTER/VIEWER → 403.
  5. Изоляция по organization_id.

ВАЖНО: TestClient использует собственный engine из
app.auth.dependencies (get_db_session). Это значит, что HTTP-запросы
идут в РЕАЛЬНУЮ БД. Тестовая фикстура async_session тоже смотрит
в ту же БД — значит, для проверки/очистки можно её использовать.
"""
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token
from app.main import app

# ==========================================
# КОНСТАНТЫ
# ==========================================

TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ORG_ID = UUID("00000000-0000-0000-0000-000000000099")

# Префикс slug'ов, созданных тестами. Гарантирует,
# что мы не тронем реальные статьи и легко их найдём
# для cleanup.
TEST_SLUG_PREFIX = "test-crud-"


# ==========================================
# ХЕЛПЕРЫ: JWT
# ==========================================

def _make_token(role: str = "ADMIN", org_id: UUID = TEST_ORG_ID) -> str:
    """
    Генерирует валидный JWT для теста.

    sub — тестовый user_id (валидный UUID), org_id — указанная
    организация, role — указанная роль.
    """
    return create_access_token({
        "sub": str(uuid.uuid4()),
        "org_id": str(org_id),
        "role": role,
        "email": f"{role.lower()}@test.com",
    })


def _auth_headers(role: str = "ADMIN", org_id: UUID = TEST_ORG_ID) -> dict:
    """Готовые заголовки авторизации."""
    return {"Authorization": f"Bearer {_make_token(role, org_id)}"}


# ==========================================
# ХЕЛПЕРЫ: работа с БД
# ==========================================

def _unique_slug(prefix: str = TEST_SLUG_PREFIX) -> str:
    """Уникальный slug для теста (kebab-case)."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


async def _cleanup_test_articles(
        session: AsyncSession,
        org_id: UUID = TEST_ORG_ID,
) -> None:
    """
    Удаляет все тестовые статьи (по префиксу slug).

    Идемпотентно: если тест упал посередине — повторный вызов
    всё подчистит.
    """
    await session.execute(
        text("""
            DELETE FROM help_article
            WHERE organization_id = :org_id
              AND slug LIKE :prefix
        """),
        {"org_id": org_id, "prefix": f"{TEST_SLUG_PREFIX}%"},
    )
    await session.commit()


async def _fetch_article_from_db(
        session: AsyncSession,
        slug: str,
):
    """Читает статью из БД напрямую (для проверки)."""
    result = await session.execute(
        text("""
            SELECT slug, title, category, content_md, tags,
                   display_order, is_published, organization_id
            FROM help_article
            WHERE slug = :slug
        """),
        {"slug": slug},
    )
    return result.fetchone()


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def client():
    """TestClient для HTTP-запросов."""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Заголовки ADMIN."""
    return _auth_headers("ADMIN")


@pytest.fixture
def planner_headers():
    """Заголовки PLANNER (не имеет доступа к CRUD)."""
    return _auth_headers("PLANNER")


@pytest.fixture
def master_headers():
    """Заголовки MASTER."""
    return _auth_headers("MASTER")


@pytest.fixture
def viewer_headers():
    """Заголовки VIEWER."""
    return _auth_headers("VIEWER")


# ==========================================
# 1. POST /articles — создание
# ==========================================

@pytest.mark.asyncio
async def test_create_article_success(
        async_session,
        client,
        admin_headers,
):
    """Успешное создание статьи с явным slug."""
    slug = _unique_slug()

    try:
        response = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Тестовая статья CRUD",
                "slug": slug,
                "category": "planning",
                "content_md": "# Заголовок\n\nТело.",
                "tags": ["test", "crud"],
                "is_published": True,
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["slug"] == slug
        assert data["title"] == "Тестовая статья CRUD"
        assert data["category"] == "planning"
        assert data["tags"] == ["test", "crud"]

        # Проверка в БД
        row = await _fetch_article_from_db(async_session, slug)
        assert row is not None
        assert row.title == "Тестовая статья CRUD"
        assert row.organization_id == TEST_ORG_ID

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_create_article_auto_generates_slug(
        async_session,
        client,
        admin_headers,
):
    """Slug генерируется из title, если не задан."""
    try:
        response = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "CRUD Test Article Auto",
                "category": "planning",
                "content_md": "body",
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()
        # slug должен начинаться с "crud-test-article-auto"
        assert "crud-test-article-auto" in data["slug"]

        # Убираем мусор — slug сгенерированный, префикс не наш
        await async_session.execute(
            text("DELETE FROM help_article WHERE slug = :slug"),
            {"slug": data["slug"]},
        )
        await async_session.commit()
    except Exception:
        await _cleanup_test_articles(async_session)
        raise


@pytest.mark.asyncio
async def test_create_article_auto_display_order(
        async_session,
        client,
        admin_headers,
):
    """display_order = max + 10, если не задан."""
    slug = _unique_slug()
    try:
        # Находим текущий max для категории 'faq'
        result = await async_session.execute(
            text("""
                SELECT COALESCE(MAX(display_order), 0) AS m
                FROM help_article
                WHERE category = 'faq'
            """),
        )
        max_before = int(result.fetchone().m)

        response = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "FAQ Test",
                "slug": slug,
                "category": "faq",
                "content_md": "body",
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        # display_order должен быть max_before + 10
        assert data["display_order"] == max_before + 10

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_create_article_slug_conflict(
        async_session,
        client,
        admin_headers,
):
    """Дубликат slug → 409."""
    slug = _unique_slug()
    try:
        # Первое создание
        r1 = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Первая",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        assert r1.status_code == 201

        # Второе создание с тем же slug → 409
        r2 = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Вторая",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        assert r2.status_code == 409
        assert "уже существует" in r2.json()["detail"].lower()

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_create_article_unknown_category(
        async_session,
        client,
        admin_headers,
):
    """Неизвестная категория → 400."""
    response = client.post(
        "/api/v1/help/articles",
        headers=admin_headers,
        json={
            "title": "Статья",
            "category": "unknown-category",
            "content_md": "body",
        },
    )
    assert response.status_code == 400
    assert "категория" in response.json()["detail"].lower()


# ==========================================
# 2. PUT /articles/{slug} — обновление
# ==========================================

@pytest.mark.asyncio
async def test_update_article_success(
        async_session,
        client,
        admin_headers,
):
    """Полное обновление полей статьи."""
    slug = _unique_slug()
    try:
        # Создаём
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Оригинал",
                "slug": slug,
                "category": "planning",
                "content_md": "old body",
                "tags": ["old"],
            },
        )

        # Обновляем
        response = client.put(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
            json={
                "title": "Обновлено",
                "content_md": "new body",
                "tags": ["new1", "new2"],
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "Обновлено"
        assert data["content_md"] == "new body"
        assert data["tags"] == ["new1", "new2"]
        assert data["slug"] == slug  # slug не менялся

        # Проверка в БД
        row = await _fetch_article_from_db(async_session, slug)
        assert row.title == "Обновлено"

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_update_article_partial(
        async_session,
        client,
        admin_headers,
):
    """Частичное обновление — только title."""
    slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Оригинал",
                "slug": slug,
                "category": "planning",
                "content_md": "original body",
                "tags": ["orig"],
            },
        )

        response = client.put(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
            json={"title": "Только заголовок"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "Только заголовок"
        # content_md и tags не менялись
        assert data["content_md"] == "original body"
        assert data["tags"] == ["orig"]

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_update_article_change_slug(
        async_session,
        client,
        admin_headers,
):
    """Изменение slug статьи."""
    old_slug = _unique_slug()
    new_slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Статья",
                "slug": old_slug,
                "category": "planning",
                "content_md": "body",
            },
        )

        response = client.put(
            f"/api/v1/help/articles/{old_slug}",
            headers=admin_headers,
            json={"slug": new_slug},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["slug"] == new_slug

        # Старого больше нет
        row_old = await _fetch_article_from_db(async_session, old_slug)
        assert row_old is None
        # Новый есть
        row_new = await _fetch_article_from_db(async_session, new_slug)
        assert row_new is not None

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_update_article_slug_conflict(
        async_session,
        client,
        admin_headers,
):
    """Попытка занять чужой slug → 409."""
    slug_a = _unique_slug()
    slug_b = _unique_slug()
    try:
        # Создаём две статьи
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "A",
                "slug": slug_a,
                "category": "planning",
                "content_md": "a",
            },
        )
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "B",
                "slug": slug_b,
                "category": "planning",
                "content_md": "b",
            },
        )

        # Пытаемся slug B занять статьёй A
        response = client.put(
            f"/api/v1/help/articles/{slug_a}",
            headers=admin_headers,
            json={"slug": slug_b},
        )
        assert response.status_code == 409

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_update_article_not_found(
        async_session,
        client,
        admin_headers,
):
    """Несуществующий slug → 404."""
    fake_slug = f"{TEST_SLUG_PREFIX}nonexistent-{uuid.uuid4().hex[:8]}"
    response = client.put(
        f"/api/v1/help/articles/{fake_slug}",
        headers=admin_headers,
        json={"title": "Новый"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_article_unknown_category(
        async_session,
        client,
        admin_headers,
):
    """Неизвестная категория при обновлении → 400."""
    slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Статья",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        response = client.put(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
            json={"category": "unknown"},
        )
        assert response.status_code == 400
    finally:
        await _cleanup_test_articles(async_session)


# ==========================================
# 3. DELETE /articles/{slug} — удаление
# ==========================================

@pytest.mark.asyncio
async def test_delete_article_success(
        async_session,
        client,
        admin_headers,
):
    """Успешное удаление статьи."""
    slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Удаляемая",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )

        response = client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "success"
        assert data["slug"] == slug

        # Проверка, что удалено
        row = await _fetch_article_from_db(async_session, slug)
        assert row is None

    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_delete_article_not_found(
        async_session,
        client,
        admin_headers,
):
    """Несуществующий slug → 404."""
    fake_slug = f"{TEST_SLUG_PREFIX}missing-{uuid.uuid4().hex[:8]}"
    response = client.delete(
        f"/api/v1/help/articles/{fake_slug}",
        headers=admin_headers,
    )
    assert response.status_code == 404


# ==========================================
# 4. Проверка прав
# ==========================================

@pytest.mark.asyncio
async def test_planner_cannot_create(
        async_session,
        client,
        planner_headers,
):
    """PLANNER не может создавать статьи → 403."""
    response = client.post(
        "/api/v1/help/articles",
        headers=planner_headers,
        json={
            "title": "Тест",
            "category": "planning",
            "content_md": "body",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_master_cannot_create(
        async_session,
        client,
        master_headers,
):
    """MASTER не может создавать статьи → 403."""
    response = client.post(
        "/api/v1/help/articles",
        headers=master_headers,
        json={
            "title": "Тест",
            "category": "planning",
            "content_md": "body",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_create(
        async_session,
        client,
        viewer_headers,
):
    """VIEWER не может создавать статьи → 403."""
    response = client.post(
        "/api/v1/help/articles",
        headers=viewer_headers,
        json={
            "title": "Тест",
            "category": "planning",
            "content_md": "body",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_planner_cannot_update(
        async_session,
        client,
        admin_headers,
        planner_headers,
):
    """PLANNER не может обновлять статьи → 403."""
    slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Тест",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        response = client.put(
            f"/api/v1/help/articles/{slug}",
            headers=planner_headers,
            json={"title": "Изменено"},
        )
        assert response.status_code == 403
    finally:
        await _cleanup_test_articles(async_session)


@pytest.mark.asyncio
async def test_planner_cannot_delete(
        async_session,
        client,
        admin_headers,
        planner_headers,
):
    """PLANNER не может удалять статьи → 403."""
    slug = _unique_slug()
    try:
        client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Тест",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        response = client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=planner_headers,
        )
        assert response.status_code == 403
    finally:
        await _cleanup_test_articles(async_session)


# ==========================================
# 5. Изоляция по организации
# ==========================================

@pytest.mark.asyncio
async def test_article_not_visible_from_other_org(
        async_session,
        client,
        admin_headers,
):
    """
    Статья, созданная org A, не видна org B.

    PUT/DELETE из org B → 404.
    GET /articles/{slug} из org B → 404.
    """
    slug = _unique_slug()
    other_org_headers = _auth_headers("ADMIN", org_id=OTHER_ORG_ID)

    try:
        # Создаём в TEST_ORG
        r = client.post(
            "/api/v1/help/articles",
            headers=admin_headers,
            json={
                "title": "Org A",
                "slug": slug,
                "category": "planning",
                "content_md": "body",
            },
        )
        assert r.status_code == 201

        # Пытаемся прочитать из другой org
        r_get = client.get(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
        )
        assert r_get.status_code == 404

        # Пытаемся обновить из другой org
        r_put = client.put(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
            json={"title": "Hijack"},
        )
        assert r_put.status_code == 404

        # Пытаемся удалить из другой org
        r_del = client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
        )
        assert r_del.status_code == 404

        # Статья всё ещё существует в TEST_ORG
        row = await _fetch_article_from_db(async_session, slug)
        assert row is not None
        assert row.title == "Org A"

    finally:
        await _cleanup_test_articles(async_session)


# ==========================================
# 6. Sanity: cleanup работает
# ==========================================

@pytest.mark.asyncio
async def test_cleanup_removes_only_test_slugs(
        async_session,
        client,
        admin_headers,
):
    """
    _cleanup_test_articles удаляет только slug'и с префиксом.

    Реальные статьи (например, 'planning-build-plan') не затрагиваются.
    """
    # Создаём тестовую статью
    slug = _unique_slug()
    client.post(
        "/api/v1/help/articles",
        headers=admin_headers,
        json={
            "title": "Test",
            "slug": slug,
            "category": "planning",
            "content_md": "body",
        },
    )

    # Проверяем, что реальная статья 'planning-build-plan' есть
    # (если seed-миграции применены)
    real_slug_result = await async_session.execute(
        text("""
            SELECT slug FROM help_article
            WHERE slug = 'planning-build-plan'
        """)
    )
    real_slug_before = real_slug_result.fetchone()

    # Cleanup
    await _cleanup_test_articles(async_session)

    # Тестовая удалена
    row = await _fetch_article_from_db(async_session, slug)
    assert row is None

    # Реальная статья (если была) — не тронута
    if real_slug_before is not None:
        real_slug_after_result = await async_session.execute(
            text("""
                SELECT slug FROM help_article
                WHERE slug = 'planning-build-plan'
            """)
        )
        assert real_slug_after_result.fetchone() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])