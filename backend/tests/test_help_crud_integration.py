# backend/tests/test_help_crud_integration.py
"""
Интеграционные тесты CRUD-эндпоинтов справки (Итерация 15.5).

Требуют:
  - запущенной PostgreSQL;
  - применённых миграций add_24.sql (help_article).

Если БД недоступна — все тесты автоматически skip'аются
(через фикстуру async_client → db_available).

Проверяют:
  1. POST /articles — создание (успех, конфликт slug, невалидная
     категория, авто-генерация slug, авто display_order).
  2. PUT /articles/{slug} — обновление (успех, частичное,
     смена slug, конфликт, 404).
  3. DELETE /articles/{slug} — удаление (успех, 404).
  4. Права: PLANNER/MASTER/VIEWER → 403.
  5. Изоляция по organization_id.

ВАЖНО (Итерация 15.5, fix):
  Раньше использовался синхронный TestClient + async_session из
  conftest. Это давало конфликт двух event loop'ов и asyncpg
  кидал InterfaceError. Сейчас используется httpx.AsyncClient
  + ASGITransport (см. conftest.async_client) — один loop,
  конфликт устранён.

  Все проверки — через HTTP. Прямой доступ к БД в тестах не
  используется. Cleanup — через DELETE /articles/{slug}.
"""
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.auth.security import create_access_token

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
    """Генерирует валидный JWT для теста."""
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
# ХЕЛПЕРЫ: работа через HTTP
# ==========================================

def _unique_slug(prefix: str = TEST_SLUG_PREFIX) -> str:
    """Уникальный slug для теста (kebab-case)."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


async def _cleanup_test_article(
        client: AsyncClient,
        headers: dict,
        slug: str,
) -> None:
    """
    Удаляет тестовую статью (если существует).

    Идемпотентно: 404 игнорируется. Не бросает исключений.
    Используется в finally каждого теста.
    """
    try:
        await client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=headers,
        )
    except Exception:
        # Не мешаем оригинальному исключению теста
        pass


async def _create_article(
        client: AsyncClient,
        headers: dict,
        **fields,
) -> dict:
    """
    Хелпер: создать статью через HTTP.

    Возвращает JSON ответа. Бросает AssertionError, если
    статус != 201.
    """
    response = await client.post(
        "/api/v1/help/articles",
        headers=headers,
        json=fields,
    )
    assert response.status_code == 201, (
        f"Ожидался 201, получен {response.status_code}: {response.text}"
    )
    return response.json()


# ==========================================
# FIXTURES
# ==========================================

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
async def test_create_article_success(async_client, admin_headers):
    """Успешное создание статьи с явным slug."""
    slug = _unique_slug()
    try:
        response = await async_client.post(
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

        # Проверка через GET
        get_resp = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Тестовая статья CRUD"

    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_create_article_auto_generates_slug(
        async_client,
        admin_headers,
):
    """Slug генерируется из title, если не задан."""
    created_slug: str | None = None
    try:
        response = await async_client.post(
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
        created_slug = data["slug"]

        # slug должен начинаться с "crud-test-article-auto"
        assert "crud-test-article-auto" in created_slug
    finally:
        if created_slug:
            await _cleanup_test_article(
                async_client, admin_headers, created_slug,
            )


@pytest.mark.asyncio
async def test_create_article_auto_display_order(
        async_client,
        admin_headers,
):
    """display_order задаётся автоматически (не 0, если есть другие)."""
    slug = _unique_slug()
    try:
        # Создаём первую — узнаём display_order
        first = await _create_article(
            async_client,
            admin_headers,
            title="FAQ Test 1",
            slug=slug,
            category="faq",
            content_md="body",
        )

        # Создаём вторую — display_order должен быть БОЛЬШЕ первой
        slug2 = _unique_slug()
        try:
            second = await _create_article(
                async_client,
                admin_headers,
                title="FAQ Test 2",
                slug=slug2,
                category="faq",
                content_md="body",
            )
            assert second["display_order"] > first["display_order"]
        finally:
            await _cleanup_test_article(
                async_client, admin_headers, slug2,
            )
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_create_article_slug_conflict(async_client, admin_headers):
    """Дубликат slug → 409."""
    slug = _unique_slug()
    try:
        # Первое создание
        r1 = await async_client.post(
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
        r2 = await async_client.post(
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
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_create_article_unknown_category(
        async_client,
        admin_headers,
):
    """Неизвестная категория → 400."""
    response = await async_client.post(
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
async def test_update_article_success(async_client, admin_headers):
    """Полное обновление полей статьи."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Оригинал",
            slug=slug,
            category="planning",
            content_md="old body",
            tags=["old"],
        )

        # Обновляем
        response = await async_client.put(
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

        # Проверка через GET
        get_resp = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Обновлено"
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_update_article_partial(async_client, admin_headers):
    """Частичное обновление — только title."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Оригинал",
            slug=slug,
            category="planning",
            content_md="original body",
            tags=["orig"],
        )

        response = await async_client.put(
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
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_update_article_change_slug(async_client, admin_headers):
    """Изменение slug статьи."""
    old_slug = _unique_slug()
    new_slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Статья",
            slug=old_slug,
            category="planning",
            content_md="body",
        )

        response = await async_client.put(
            f"/api/v1/help/articles/{old_slug}",
            headers=admin_headers,
            json={"slug": new_slug},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["slug"] == new_slug

        # Старого больше нет
        old_get = await async_client.get(
            f"/api/v1/help/articles/{old_slug}",
            headers=admin_headers,
        )
        assert old_get.status_code == 404

        # Новый есть
        new_get = await async_client.get(
            f"/api/v1/help/articles/{new_slug}",
            headers=admin_headers,
        )
        assert new_get.status_code == 200
    finally:
        await _cleanup_test_article(async_client, admin_headers, old_slug)
        await _cleanup_test_article(async_client, admin_headers, new_slug)


@pytest.mark.asyncio
async def test_update_article_slug_conflict(async_client, admin_headers):
    """Попытка занять чужой slug → 409."""
    slug_a = _unique_slug()
    slug_b = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Article A",
            slug=slug_a,
            category="planning",
            content_md="a",
        )
        await _create_article(
            async_client,
            admin_headers,
            title="Article B",
            slug=slug_b,
            category="planning",
            content_md="b",
        )

        # Пытаемся slug B занять статьёй A
        response = await async_client.put(
            f"/api/v1/help/articles/{slug_a}",
            headers=admin_headers,
            json={"slug": slug_b},
        )
        assert response.status_code == 409
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug_a)
        await _cleanup_test_article(async_client, admin_headers, slug_b)


@pytest.mark.asyncio
async def test_update_article_not_found(async_client, admin_headers):
    """Несуществующий slug → 404."""
    fake_slug = f"{TEST_SLUG_PREFIX}nonexistent-{uuid.uuid4().hex[:8]}"
    response = await async_client.put(
        f"/api/v1/help/articles/{fake_slug}",
        headers=admin_headers,
        json={"title": "Новый"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_article_unknown_category(
        async_client,
        admin_headers,
):
    """Неизвестная категория при обновлении → 400."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Статья",
            slug=slug,
            category="planning",
            content_md="body",
        )
        response = await async_client.put(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
            json={"category": "unknown"},
        )
        assert response.status_code == 400
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


# ==========================================
# 3. DELETE /articles/{slug} — удаление
# ==========================================

@pytest.mark.asyncio
async def test_delete_article_success(async_client, admin_headers):
    """Успешное удаление статьи."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Удаляемая",
            slug=slug,
            category="planning",
            content_md="body",
        )

        response = await async_client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "success"
        assert data["slug"] == slug

        # Проверка, что удалено
        get_resp = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert get_resp.status_code == 404
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_delete_article_not_found(async_client, admin_headers):
    """Несуществующий slug → 404."""
    fake_slug = f"{TEST_SLUG_PREFIX}missing-{uuid.uuid4().hex[:8]}"
    response = await async_client.delete(
        f"/api/v1/help/articles/{fake_slug}",
        headers=admin_headers,
    )
    assert response.status_code == 404


# ==========================================
# 4. Проверка прав
# ==========================================

@pytest.mark.asyncio
async def test_planner_cannot_create(async_client, planner_headers):
    """PLANNER не может создавать статьи → 403."""
    response = await async_client.post(
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
async def test_master_cannot_create(async_client, master_headers):
    """MASTER не может создавать статьи → 403."""
    response = await async_client.post(
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
async def test_viewer_cannot_create(async_client, viewer_headers):
    """VIEWER не может создавать статьи → 403."""
    response = await async_client.post(
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
        async_client,
        admin_headers,
        planner_headers,
):
    """PLANNER не может обновлять статьи → 403."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Тест",
            slug=slug,
            category="planning",
            content_md="body",
        )
        response = await async_client.put(
            f"/api/v1/help/articles/{slug}",
            headers=planner_headers,
            json={"title": "Изменено"},
        )
        assert response.status_code == 403
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


@pytest.mark.asyncio
async def test_planner_cannot_delete(
        async_client,
        admin_headers,
        planner_headers,
):
    """PLANNER не может удалять статьи → 403."""
    slug = _unique_slug()
    try:
        await _create_article(
            async_client,
            admin_headers,
            title="Тест",
            slug=slug,
            category="planning",
            content_md="body",
        )
        response = await async_client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=planner_headers,
        )
        assert response.status_code == 403
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


# ==========================================
# 5. Изоляция по организации
# ==========================================

@pytest.mark.asyncio
async def test_article_not_visible_from_other_org(
        async_client,
        admin_headers,
):
    """
    Статья, созданная org A, не видна org B.

    GET/PUT/DELETE из org B → 404.
    """
    slug = _unique_slug()
    other_org_headers = _auth_headers("ADMIN", org_id=OTHER_ORG_ID)

    try:
        # Создаём в TEST_ORG
        r = await async_client.post(
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
        r_get = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
        )
        assert r_get.status_code == 404

        # Пытаемся обновить из другой org
        r_put = await async_client.put(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
            json={"title": "Hijack"},
        )
        assert r_put.status_code == 404

        # Пытаемся удалить из другой org
        r_del = await async_client.delete(
            f"/api/v1/help/articles/{slug}",
            headers=other_org_headers,
        )
        assert r_del.status_code == 404

        # Статья всё ещё существует в TEST_ORG
        r_check = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert r_check.status_code == 200
        assert r_check.json()["title"] == "Org A"

    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


# ==========================================
# 6. Sanity: cleanup работает
# ==========================================

@pytest.mark.asyncio
async def test_cleanup_removes_only_test_slugs(
        async_client,
        admin_headers,
):
    """
    Cleanup по slug удаляет только тестовую статью.

    Реальные статьи (например, 'planning-build-plan') не затрагиваются.
    """
    slug = _unique_slug()
    try:
        # Создаём тестовую статью
        await _create_article(
            async_client,
            admin_headers,
            title="Test",
            slug=slug,
            category="planning",
            content_md="body",
        )

        # Проверяем, есть ли реальная статья (если seed применён)
        real_check = await async_client.get(
            "/api/v1/help/articles/planning-build-plan",
            headers=admin_headers,
        )
        real_exists_before = real_check.status_code == 200

        # Cleanup
        await _cleanup_test_article(async_client, admin_headers, slug)

        # Тестовая удалена
        gone = await async_client.get(
            f"/api/v1/help/articles/{slug}",
            headers=admin_headers,
        )
        assert gone.status_code == 404

        # Реальная статья (если была) — не тронута
        if real_exists_before:
            real_after = await async_client.get(
                "/api/v1/help/articles/planning-build-plan",
                headers=admin_headers,
            )
            assert real_after.status_code == 200
    finally:
        await _cleanup_test_article(async_client, admin_headers, slug)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])