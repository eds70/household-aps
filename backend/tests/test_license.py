# backend/tests/test_license.py
"""
Тесты модуля лицензирования APS Production Scheduler.

Покрытие:
  - compute_instance_id — стабильность, формат.
  - create_license_token — генерация JWT.
  - verify_license — валидация, все виды ошибок.
  - LicenseInfo — методы и свойства.
  - FastAPI dependencies — require_valid_license, require_feature, require_tier.
  - HTTP-эндпоинты /license/info, /license/instance.
  - Middleware — блокировка защищённых путей.

Все тесты — unit. Не требуют БД, сети, реального мастер-ключа.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from jose import jwt

from app.core.license import (
    DEFAULT_FEATURES_BY_TIER,
    LICENSE_ALGORITHM,
    LICENSE_ISSUER,
    PUBLIC_PATH_PREFIXES,
    TIER_HIERARCHY,
    LicenseExpiredError,
    LicenseInfo,
    LicenseInstanceMismatchError,
    LicenseInvalidError,
    LicenseMissingError,
    compute_instance_id,
    create_license_token,
    get_or_create_instance_id,
    require_feature,
    require_tier,
    require_valid_license,
    verify_license,
)

# ==========================================
# ФИКСТУРЫ
# ==========================================

TEST_MASTER_SECRET = "test-master-secret-for-license-tests-min-32-chars-long"


@pytest.fixture
def valid_token() -> str:
    """Валидный токен на 30 дней, tier=enterprise, без instance_id."""
    return create_license_token(
        holder="ООО Тест",
        secret=TEST_MASTER_SECRET,
        tier="enterprise",
        days=30,
    )


@pytest.fixture
def expired_token() -> str:
    """Истёкший токен (1 день назад)."""
    return create_license_token(
        holder="ООО Тест",
        secret=TEST_MASTER_SECRET,
        tier="enterprise",
        days=-1,   # прошедший срок
    )


@pytest.fixture
def token_with_instance() -> str:
    """Токен, привязанный к конкретному instance_id."""
    return create_license_token(
        holder="ООО Тест",
        secret=TEST_MASTER_SECRET,
        tier="enterprise",
        days=30,
        instance_id="abc123def456",
    )


# ==========================================
# 1. КОНСТАНТЫ
# ==========================================

def test_tier_hierarchy_ordered():
    """TIER_HIERARCHY содержит 3 уровня в порядке возрастания."""
    assert TIER_HIERARCHY == ("trial", "community", "enterprise")


def test_default_features_by_tier_keys():
    """DEFAULT_FEATURES_BY_TIER содержит ключи для всех tier."""
    assert set(DEFAULT_FEATURES_BY_TIER.keys()) == set(TIER_HIERARCHY)


def test_license_issuer_constant():
    """LICENSE_ISSUER — непустая строка."""
    assert isinstance(LICENSE_ISSUER, str)
    assert len(LICENSE_ISSUER) > 0


def test_license_algorithm_is_hs256():
    """По умолчанию — HS256."""
    assert LICENSE_ALGORITHM == "HS256"


# ==========================================
# 2. compute_instance_id
# ==========================================

def test_compute_instance_id_format():
    """instance_id — 64-символьная hex-строка."""
    iid = compute_instance_id()
    assert isinstance(iid, str)
    assert len(iid) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", iid)


def test_compute_instance_id_stable():
    """Повторные вызовы дают тот же результат (при неизменной системе)."""
    iid1 = compute_instance_id()
    iid2 = compute_instance_id()
    assert iid1 == iid2


def test_get_or_create_instance_id_returns_string():
    """get_or_create_instance_id возвращает hex-строку."""
    iid = get_or_create_instance_id()
    assert isinstance(iid, str)
    assert len(iid) == 64


def test_public_path_prefixes_includes_license_endpoints():
    """Публичные пути включают /license/info и /license/instance."""
    assert "/api/v1/license/info" in PUBLIC_PATH_PREFIXES
    assert "/api/v1/license/instance" in PUBLIC_PATH_PREFIXES


# ==========================================
# 3. create_license_token
# ==========================================

def test_create_license_token_returns_jwt():
    """Токен имеет 3 сегмента (JWT-формат)."""
    token = create_license_token(
        holder="Test", secret=TEST_MASTER_SECRET, tier="trial", days=10
    )
    parts = token.split(".")
    assert len(parts) == 3


def test_create_license_token_invalid_tier():
    """Неизвестный tier → ValueError."""
    with pytest.raises(ValueError, match="Неизвестный tier"):
        create_license_token(
            holder="Test", secret=TEST_MASTER_SECRET, tier="super_pro", days=10
        )


def test_create_license_token_default_features_by_tier():
    """Если features не заданы — берутся по tier."""
    token = create_license_token(
        holder="Test", secret=TEST_MASTER_SECRET, tier="enterprise", days=10
    )
    payload = jwt.get_unverified_claims(token)
    assert set(payload["features"]) == DEFAULT_FEATURES_BY_TIER["enterprise"]


def test_create_license_token_custom_features():
    """Явные features перекрывают дефолт."""
    token = create_license_token(
        holder="Test",
        secret=TEST_MASTER_SECRET,
        tier="community",
        days=10,
        features={"custom_feature"},
    )
    payload = jwt.get_unverified_claims(token)
    assert set(payload["features"]) == {"custom_feature"}


def test_create_license_token_with_instance_id():
    """instance_id попадает в payload."""
    token = create_license_token(
        holder="Test",
        secret=TEST_MASTER_SECRET,
        tier="trial",
        days=10,
        instance_id="abc123",
    )
    payload = jwt.get_unverified_claims(token)
    assert payload["instance_id"] == "abc123"


def test_create_license_token_with_max_users():
    """max_users попадает в payload."""
    token = create_license_token(
        holder="Test",
        secret=TEST_MASTER_SECRET,
        tier="enterprise",
        days=10,
        max_users=5,
    )
    payload = jwt.get_unverified_claims(token)
    assert payload["max_users"] == 5


# ==========================================
# 4. verify_license — позитивные сценарии
# ==========================================

def test_verify_license_valid(valid_token):
    """Валидная лицензия → LicenseInfo с правильными полями."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert isinstance(info, LicenseInfo)
    assert info.holder == "ООО Тест"
    assert info.tier == "enterprise"
    assert not info.is_expired
    assert info.days_left > 25   # ~30 дней (может быть 29 из-за округления)
    assert not info.is_instance_bound


def test_verify_license_with_instance_match(token_with_instance):
    """instance_id совпадает → OK."""
    info = verify_license(
        token_with_instance,
        TEST_MASTER_SECRET,
        expected_instance_id="abc123def456",
    )
    assert info.is_instance_bound
    assert info.instance_id == "abc123def456"


def test_verify_license_features_parsed(valid_token):
    """Features разбираются в FrozenSet."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert isinstance(info.features, frozenset)
    assert "audit_export" in info.features


# ==========================================
# 5. verify_license — ошибки
# ==========================================

def test_verify_license_missing_key():
    """Пустой ключ → LicenseMissingError."""
    with pytest.raises(LicenseMissingError):
        verify_license("", TEST_MASTER_SECRET)


def test_verify_license_whitespace_key():
    """Ключ из пробелов → LicenseMissingError."""
    with pytest.raises(LicenseMissingError):
        verify_license("   \n\t  ", TEST_MASTER_SECRET)


def test_verify_license_bad_signature(valid_token):
    """Неверный секрет → LicenseInvalidError."""
    with pytest.raises(LicenseInvalidError):
        verify_license(valid_token, "wrong-secret-completely-different-key")


def test_verify_license_malformed_token():
    """Мусорный токен → LicenseInvalidError."""
    with pytest.raises(LicenseInvalidError):
        verify_license("not.a.jwt", TEST_MASTER_SECRET)


def test_verify_license_expired(expired_token):
    """Истёкшая лицензия → LicenseExpiredError."""
    with pytest.raises(LicenseExpiredError):
        verify_license(expired_token, TEST_MASTER_SECRET)


def test_verify_license_wrong_issuer():
    """Токен с чужим issuer → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "another-vendor",
        "holder": "Test",
        "tier": "trial",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, TEST_MASTER_SECRET, algorithm="HS256")

    with pytest.raises(LicenseInvalidError):
        verify_license(token, TEST_MASTER_SECRET)


def test_verify_license_missing_holder():
    """Токен без holder → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": LICENSE_ISSUER,
        "tier": "trial",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, TEST_MASTER_SECRET, algorithm="HS256")

    with pytest.raises(LicenseInvalidError, match="обязательные поля"):
        verify_license(token, TEST_MASTER_SECRET)


def test_verify_license_invalid_tier_in_payload():
    """Неизвестный tier в payload → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": LICENSE_ISSUER,
        "holder": "Test",
        "tier": "super_pro",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, TEST_MASTER_SECRET, algorithm="HS256")

    with pytest.raises(LicenseInvalidError, match="tier"):
        verify_license(token, TEST_MASTER_SECRET)


def test_verify_license_instance_mismatch(token_with_instance):
    """Разные instance_id → LicenseInstanceMismatchError."""
    with pytest.raises(LicenseInstanceMismatchError):
        verify_license(
            token_with_instance,
            TEST_MASTER_SECRET,
            expected_instance_id="different-instance-id",
        )


def test_verify_license_instance_no_expected(token_with_instance):
    """Если expected_instance_id не задан — проверка пропускается (warning)."""
    info = verify_license(
        token_with_instance,
        TEST_MASTER_SECRET,
        expected_instance_id=None,
    )
    # Не падает, возвращает info
    assert info.instance_id == "abc123def456"


# ==========================================
# 6. LicenseInfo — методы и свойства
# ==========================================

def test_license_info_days_left_positive(valid_token):
    """days_left > 0 для валидной лицензии."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert info.days_left > 0


def test_license_info_is_expired_false(valid_token):
    """is_expired = False для валидной лицензии."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert not info.is_expired


def test_license_info_has_feature_present(valid_token):
    """has_feature → True для фичи из токена."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert info.has_feature("audit_export")


def test_license_info_has_feature_absent(valid_token):
    """has_feature → False для неизвестной фичи."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert not info.has_feature("nonexistent_feature")


def test_license_info_has_tier_equal(valid_token):
    """has_tier для своего же уровня → True."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert info.has_tier("enterprise")


def test_license_info_has_tier_lower(valid_token):
    """has_tier для более низкого уровня → True (enterprise >= community)."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert info.has_tier("community")
    assert info.has_tier("trial")


def test_license_info_has_tier_higher():
    """has_tier для более высокого уровня → False (trial < enterprise)."""
    token = create_license_token(
        holder="Test", secret=TEST_MASTER_SECRET, tier="trial", days=10
    )
    info = verify_license(token, TEST_MASTER_SECRET)
    assert not info.has_tier("community")
    assert not info.has_tier("enterprise")


def test_license_info_is_instance_bound_true(token_with_instance):
    """is_instance_bound = True для лицензии с instance_id."""
    info = verify_license(
        token_with_instance, TEST_MASTER_SECRET, expected_instance_id="abc123def456"
    )
    assert info.is_instance_bound


def test_license_info_is_instance_bound_false(valid_token):
    """is_instance_bound = False для лицензии без instance_id."""
    info = verify_license(valid_token, TEST_MASTER_SECRET)
    assert not info.is_instance_bound


# ==========================================
# 7. FastAPI dependencies
# ==========================================

@pytest.fixture
def app_with_license():
    """FastAPI app с валидной лицензией в state."""
    app = FastAPI()

    @app.get("/protected")
    async def protected(_: LicenseInfo = Depends(require_valid_license)):
        return {"ok": True}

    @app.get("/with-feature")
    async def with_feature(
            _: LicenseInfo = Depends(require_feature("audit_export"))
    ):
        return {"ok": True}

    @app.get("/without-feature")
    async def without_feature(
            _: LicenseInfo = Depends(require_feature("nonexistent"))
    ):
        return {"ok": True}

    @app.get("/enterprise-only")
    async def enterprise_only(
            _: LicenseInfo = Depends(require_tier("enterprise"))
    ):
        return {"ok": True}

    @app.get("/community-ok")
    async def community_ok(
            _: LicenseInfo = Depends(require_tier("community"))
    ):
        return {"ok": True}

    # Устанавливаем валидную лицензию в state
    app.state.license_info = verify_license(
        create_license_token(
            holder="Test", secret=TEST_MASTER_SECRET, tier="enterprise", days=30
        ),
        TEST_MASTER_SECRET,
    )
    app.state.license_error = None

    return app


@pytest.fixture
def app_without_license():
    """FastAPI app без лицензии (state.license_info = None)."""
    app = FastAPI()

    @app.get("/protected")
    async def protected(_: LicenseInfo = Depends(require_valid_license)):
        return {"ok": True}

    app.state.license_info = None
    app.state.license_error = "Тестовая ошибка"
    return app


def test_require_valid_license_ok(app_with_license):
    """Валидная лицензия → 200."""
    client = TestClient(app_with_license)
    response = client.get("/protected")
    assert response.status_code == 200


def test_require_valid_license_missing(app_without_license):
    """Нет лицензии → 403 с кодом LICENSE_INVALID."""
    client = TestClient(app_without_license)
    response = client.get("/protected")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_INVALID"


def test_require_feature_present(app_with_license):
    """Фича есть → 200."""
    client = TestClient(app_with_license)
    response = client.get("/with-feature")
    assert response.status_code == 200


def test_require_feature_absent(app_with_license):
    """Фича отсутствует → 403 с кодом LICENSE_FEATURE_MISSING."""
    client = TestClient(app_with_license)
    response = client.get("/without-feature")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_FEATURE_MISSING"
    assert detail["feature"] == "nonexistent"


def test_require_tier_exact(app_with_license):
    """Точный tier → 200."""
    client = TestClient(app_with_license)
    response = client.get("/enterprise-only")
    assert response.status_code == 200


def test_require_tier_lower_ok(app_with_license):
    """enterprise проходит require_tier('community') → 200."""
    client = TestClient(app_with_license)
    response = client.get("/community-ok")
    assert response.status_code == 200


def test_require_tier_higher_fails():
    """trial не проходит require_tier('enterprise') → 403."""
    app = FastAPI()

    @app.get("/enterprise-only")
    async def enterprise_only(
            _: LicenseInfo = Depends(require_tier("enterprise"))
    ):
        return {"ok": True}

    app.state.license_info = verify_license(
        create_license_token(
            holder="Test", secret=TEST_MASTER_SECRET, tier="trial", days=30
        ),
        TEST_MASTER_SECRET,
    )
    app.state.license_error = None

    client = TestClient(app)
    response = client.get("/enterprise-only")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_TIER_INSUFFICIENT"


def test_require_tier_invalid_argument():
    """Неизвестный min_tier → ValueError при создании dependency."""
    with pytest.raises(ValueError, match="Неизвестный min_tier"):
        require_tier("super_pro")


# ==========================================
# 8. HTTP-эндпоинты /license/info, /license/instance
# ==========================================

@pytest.fixture
def app_with_license_endpoints():
    """FastAPI app с роутером лицензии и валидной лицензией в state."""
    from app.api.v1.license import router as license_router

    app = FastAPI()
    app.include_router(license_router)

    app.state.license_info = verify_license(
        create_license_token(
            holder="ООО Тест",
            secret=TEST_MASTER_SECRET,
            tier="enterprise",
            days=30,
        ),
        TEST_MASTER_SECRET,
    )
    app.state.license_error = None
    app.state.instance_id = "test-instance-id-abc123"

    return app


@pytest.fixture
def app_without_license_endpoints():
    """FastAPI app без лицензии."""
    from app.api.v1.license import router as license_router

    app = FastAPI()
    app.include_router(license_router)

    app.state.license_info = None
    app.state.license_error = "LICENSE_KEY не задан"
    app.state.instance_id = "test-instance-id-abc123"

    return app


def test_license_info_valid(app_with_license_endpoints):
    """GET /license/info с валидной лицензией → valid=true."""
    client = TestClient(app_with_license_endpoints)
    response = client.get("/api/v1/license/info")
    assert response.status_code == 200

    data = response.json()
    assert data["valid"] is True
    assert data["holder"] == "ООО Тест"
    assert data["tier"] == "enterprise"
    assert data["days_left"] > 25
    assert "audit_export" in data["features"]
    assert data["instance_id"] == "test-instance-id-abc123"
    assert data["instance_bound"] is False
    assert data["error"] is None


def test_license_info_invalid(app_without_license_endpoints):
    """GET /license/info без лицензии → valid=false, error заполнен."""
    client = TestClient(app_without_license_endpoints)
    response = client.get("/api/v1/license/info")
    assert response.status_code == 200   # публичный, не блокируется

    data = response.json()
    assert data["valid"] is False
    assert data["error"] == "LICENSE_KEY не задан"
    assert data["holder"] is None


def test_license_instance_endpoint(app_with_license_endpoints):
    """GET /license/instance возвращает instance_id."""
    client = TestClient(app_with_license_endpoints)
    response = client.get("/api/v1/license/instance")
    assert response.status_code == 200

    data = response.json()
    assert data["instance_id"] == "test-instance-id-abc123"
    assert data["algorithm"] == "sha256"
    assert "machine-id" in data["components"]


def test_license_info_public_no_auth(app_with_license_endpoints):
    """GET /license/info доступен без авторизации."""
    client = TestClient(app_with_license_endpoints)
    response = client.get("/api/v1/license/info")
    assert response.status_code == 200


def test_license_info_contains_tier_hierarchy(app_with_license_endpoints):
    """GET /license/info возвращает tier_hierarchy."""
    client = TestClient(app_with_license_endpoints)
    data = client.get("/api/v1/license/info").json()
    assert data["tier_hierarchy"] == ["trial", "community", "enterprise"]


def test_license_info_contains_default_features(app_with_license_endpoints):
    """GET /license/info возвращает default_features_by_tier."""
    client = TestClient(app_with_license_endpoints)
    data = client.get("/api/v1/license/info").json()
    assert "enterprise" in data["default_features_by_tier"]
    assert "audit_export" in data["default_features_by_tier"]["enterprise"]


# ==========================================
# 9. Middleware
# ==========================================

@pytest.fixture
def app_with_middleware_and_license():
    """App с LicenseMiddleware + валидной лицензией + тестовым эндпоинтом."""
    from app.main import LicenseMiddleware
    from app.core.config import settings

    # Временно включаем проверку
    original_verify = settings.LICENSE_VERIFY
    settings.LICENSE_VERIFY = True

    app = FastAPI()
    app.add_middleware(LicenseMiddleware)

    @app.get("/api/v1/test-protected")
    async def protected():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.state.license_info = verify_license(
        create_license_token(
            holder="Test", secret=TEST_MASTER_SECRET, tier="enterprise", days=30
        ),
        TEST_MASTER_SECRET,
    )
    app.state.license_error = None

    yield app

    # Восстанавливаем
    settings.LICENSE_VERIFY = original_verify


@pytest.fixture
def app_with_middleware_no_license():
    """App с LicenseMiddleware без лицензии."""
    from app.main import LicenseMiddleware
    from app.core.config import settings

    original_verify = settings.LICENSE_VERIFY
    settings.LICENSE_VERIFY = True

    app = FastAPI()
    app.add_middleware(LicenseMiddleware)

    @app.get("/api/v1/test-protected")
    async def protected():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    app.state.license_info = None
    app.state.license_error = "LICENSE_KEY не задан"

    yield app

    settings.LICENSE_VERIFY = original_verify


def test_middleware_allows_protected_with_license(app_with_middleware_and_license):
    """С валидной лицензией защищённые пути доступны."""
    client = TestClient(app_with_middleware_and_license)
    response = client.get("/api/v1/test-protected")
    assert response.status_code == 200


def test_middleware_blocks_protected_without_license(app_with_middleware_no_license):
    """Без лицензии защищённые пути → 403."""
    client = TestClient(app_with_middleware_no_license)
    response = client.get("/api/v1/test-protected")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "LICENSE_INVALID"


def test_middleware_allows_public_paths(app_with_middleware_no_license):
    """Публичные пути доступны без лицензии."""
    client = TestClient(app_with_middleware_no_license)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/auth/login").status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])