# backend/tests/test_license_rs256.py
"""
Тесты RS256/ES256 лицензирования APS Production Scheduler.

Покрытие:
  - генерация пары ключей RSA и ECDSA;
  - round-trip: подпись приватным → проверка публичным;
  - отказ при несовпадении ключа;
  - отказ при модификации payload (подпись);
  - отказ при истёкшем токене;
  - instance_id binding;
  - авто-определение алгоритма (algorithm=None);
  - отказ при явном неверном algorithm;
  - защита от alg=none;
  - jti генерируется автоматически;
  - обратная совместимость с HS256.

Все тесты — unit. Не требуют БД, сети, реального приватного ключа.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.license import (
    DEFAULT_FEATURES_BY_TIER,
    LICENSE_ISSUER,
    SUPPORTED_ALGORITHMS,
    LicenseExpiredError,
    LicenseInfo,
    LicenseInstanceMismatchError,
    LicenseInvalidError,
    LicenseMissingError,
    create_license_token,
    verify_license,
)

# ==========================================
# ФИКСТУРЫ
# ==========================================

# 2048 бит вместо 3072 — для скорости тестов достаточно и безопасно.
# 3072 используется в проде, но в unit-тестах это лишние секунды.
_RSA_KEY_SIZE = 2048


def _generate_rsa_pair() -> tuple[str, str]:
    """Генерирует RSA-пару (private_pem, public_pem)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(
        public_exponent=65537,
        key_size=_RSA_KEY_SIZE,
    )
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _generate_ec_pair() -> tuple[str, str]:
    """Генерирует ECDSA P-256 пару (private_pem, public_pem)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """Одна RSA-пара на весь модуль (генерация — дорогая)."""
    return _generate_rsa_pair()


@pytest.fixture(scope="module")
def rsa_keypair_other() -> tuple[str, str]:
    """Вторая, независимая RSA-пара — для негативных тестов."""
    return _generate_rsa_pair()


@pytest.fixture(scope="module")
def ec_keypair() -> tuple[str, str]:
    """ECDSA-пара — для проверки ES256."""
    return _generate_ec_pair()


@pytest.fixture
def rsa_private(rsa_keypair) -> str:
    return rsa_keypair[0]


@pytest.fixture
def rsa_public(rsa_keypair) -> str:
    return rsa_keypair[1]


@pytest.fixture
def rsa_private_other(rsa_keypair_other) -> str:
    return rsa_keypair_other[0]


@pytest.fixture
def rsa_public_other(rsa_keypair_other) -> str:
    return rsa_keypair_other[1]


@pytest.fixture
def valid_rsa_token(rsa_private) -> str:
    """Валидный RS256-токен на 30 дней, tier=enterprise, без instance_id."""
    return create_license_token(
        holder="ООО RS256 Тест",
        secret=rsa_private,
        tier="enterprise",
        days=30,
        algorithm="RS256",
    )


@pytest.fixture
def expired_rsa_token(rsa_private) -> str:
    """Истёкший RS256-токен (1 день назад)."""
    return create_license_token(
        holder="ООО RS256 Тест",
        secret=rsa_private,
        tier="enterprise",
        days=-1,
        algorithm="RS256",
    )


@pytest.fixture
def rsa_token_with_instance(rsa_private) -> str:
    """RS256-токен с instance_id."""
    return create_license_token(
        holder="ООО RS256 Тест",
        secret=rsa_private,
        tier="enterprise",
        days=30,
        instance_id="rsa-instance-abc123",
        algorithm="RS256",
    )


@pytest.fixture
def valid_es256_token(ec_keypair) -> str:
    """Валидный ES256-токен."""
    private_pem, _ = ec_keypair
    return create_license_token(
        holder="ООО ES256 Тест",
        secret=private_pem,
        tier="enterprise",
        days=30,
        algorithm="ES256",
    )


# ==========================================
# 1. КОНСТАНТЫ
# ==========================================

def test_supported_algorithms_contains_rs256():
    """SUPPORTED_ALGORITHMS содержит RS256/384/512."""
    assert "RS256" in SUPPORTED_ALGORITHMS
    assert "RS384" in SUPPORTED_ALGORITHMS
    assert "RS512" in SUPPORTED_ALGORITHMS


def test_supported_algorithms_contains_es256():
    """SUPPORTED_ALGORITHMS содержит ES256/384/512."""
    assert "ES256" in SUPPORTED_ALGORITHMS
    assert "ES384" in SUPPORTED_ALGORITHMS
    assert "ES512" in SUPPORTED_ALGORITHMS


def test_supported_algorithms_contains_hs256():
    """SUPPORTED_ALGORITHMS содержит HS256/384/512 (обратная совместимость)."""
    assert "HS256" in SUPPORTED_ALGORITHMS
    assert "HS384" in SUPPORTED_ALGORITHMS
    assert "HS512" in SUPPORTED_ALGORITHMS


# ==========================================
# 2. ГЕНЕРАЦИЯ ПАР КЛЮЧЕЙ
# ==========================================

def test_rsa_keypair_format(rsa_keypair):
    """RSA-пара — валидные PEM-строки."""
    private_pem, public_pem = rsa_keypair
    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert private_pem.strip().endswith("-----END PRIVATE KEY-----")
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert public_pem.strip().endswith("-----END PUBLIC KEY-----")


def test_ec_keypair_format(ec_keypair):
    """ECDSA-пара — валидные PEM-строки."""
    private_pem, public_pem = ec_keypair
    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")


def test_rsa_keypairs_are_independent(rsa_keypair, rsa_keypair_other):
    """Две пары — разные ключи (не пересекаются)."""
    assert rsa_keypair[0] != rsa_keypair_other[0]
    assert rsa_keypair[1] != rsa_keypair_other[1]


# ==========================================
# 3. create_license_token — RS256/ES256
# ==========================================

def test_create_rs256_token_returns_jwt(rsa_private):
    """RS256-токен имеет 3 сегмента."""
    token = create_license_token(
        holder="Test",
        secret=rsa_private,
        tier="trial",
        days=10,
        algorithm="RS256",
    )
    assert len(token.split(".")) == 3


def test_create_rs256_token_alg_in_header(rsa_private):
    """Заголовок JWT содержит alg=RS256."""
    token = create_license_token(
        holder="Test",
        secret=rsa_private,
        tier="trial",
        days=10,
        algorithm="RS256",
    )
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"
    assert header["typ"] == "JWT"


def test_create_es256_token_alg_in_header(ec_keypair):
    """Заголовок ES256-токена содержит alg=ES256."""
    private_pem, _ = ec_keypair
    token = create_license_token(
        holder="Test",
        secret=private_pem,
        tier="trial",
        days=10,
        algorithm="ES256",
    )
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "ES256"


def test_create_rs256_token_contains_jti(rsa_private):
    """jti генерируется автоматически и попадает в payload."""
    token = create_license_token(
        holder="Test",
        secret=rsa_private,
        tier="trial",
        days=10,
        algorithm="RS256",
    )
    payload = jwt.get_unverified_claims(token)
    assert "jti" in payload
    assert isinstance(payload["jti"], str)
    assert len(payload["jti"]) > 0


def test_create_rs256_token_unique_jti(rsa_private):
    """Два токена — разные jti (UUID4)."""
    token1 = create_license_token(
        holder="Test", secret=rsa_private, tier="trial", days=10, algorithm="RS256"
    )
    token2 = create_license_token(
        holder="Test", secret=rsa_private, tier="trial", days=10, algorithm="RS256"
    )
    jti1 = jwt.get_unverified_claims(token1)["jti"]
    jti2 = jwt.get_unverified_claims(token2)["jti"]
    assert jti1 != jti2


def test_create_rs256_token_invalid_tier(rsa_private):
    """Неизвестный tier → ValueError."""
    with pytest.raises(ValueError, match="Неизвестный tier"):
        create_license_token(
            holder="Test",
            secret=rsa_private,
            tier="super_pro",
            days=10,
            algorithm="RS256",
        )


def test_create_rs256_token_invalid_algorithm(rsa_private):
    """Неподдерживаемый algorithm → ValueError."""
    with pytest.raises(ValueError, match="алгоритм"):
        create_license_token(
            holder="Test",
            secret=rsa_private,
            tier="trial",
            days=10,
            algorithm="MAGIC_ALG",
        )


def test_create_rs256_token_default_features(rsa_private):
    """Если features не заданы — берутся по tier."""
    token = create_license_token(
        holder="Test",
        secret=rsa_private,
        tier="enterprise",
        days=10,
        algorithm="RS256",
    )
    payload = jwt.get_unverified_claims(token)
    assert set(payload["features"]) == DEFAULT_FEATURES_BY_TIER["enterprise"]


# ==========================================
# 4. verify_license — позитивные сценарии (RS256)
# ==========================================

def test_verify_rs256_valid(valid_rsa_token, rsa_public):
    """Валидный RS256-токен → LicenseInfo."""
    info = verify_license(valid_rsa_token, rsa_public, algorithm="RS256")
    assert isinstance(info, LicenseInfo)
    assert info.holder == "ООО RS256 Тест"
    assert info.tier == "enterprise"
    assert not info.is_expired
    assert info.days_left > 25
    assert info.algorithm == "RS256"


def test_verify_rs256_algorithm_auto_detect(valid_rsa_token, rsa_public):
    """algorithm=None → jose сам определяет RS256 по заголовку."""
    info = verify_license(valid_rsa_token, rsa_public)
    assert info.algorithm == "RS256"
    assert info.holder == "ООО RS256 Тест"


def test_verify_rs256_jti_present(valid_rsa_token, rsa_public):
    """jti попадает в LicenseInfo."""
    info = verify_license(valid_rsa_token, rsa_public, algorithm="RS256")
    assert info.jti is not None
    assert isinstance(info.jti, str)
    assert len(info.jti) > 0


def test_verify_rs256_features_parsed(valid_rsa_token, rsa_public):
    """Features разбираются в FrozenSet."""
    info = verify_license(valid_rsa_token, rsa_public, algorithm="RS256")
    assert isinstance(info.features, frozenset)
    assert "audit_export" in info.features


def test_verify_rs256_max_users(rsa_private, rsa_public):
    """max_users из payload попадает в LicenseInfo."""
    token = create_license_token(
        holder="Test",
        secret=rsa_private,
        tier="enterprise",
        days=30,
        max_users=10,
        algorithm="RS256",
    )
    info = verify_license(token, rsa_public, algorithm="RS256")
    assert info.max_users == 10


# ==========================================
# 5. verify_license — ES256
# ==========================================

def test_verify_es256_valid(valid_es256_token, ec_keypair):
    """Валидный ES256-токен → LicenseInfo."""
    _, public_pem = ec_keypair
    info = verify_license(valid_es256_token, public_pem, algorithm="ES256")
    assert info.holder == "ООО ES256 Тест"
    assert info.algorithm == "ES256"


def test_verify_es256_auto_detect(valid_es256_token, ec_keypair):
    """algorithm=None → jose сам определяет ES256."""
    _, public_pem = ec_keypair
    info = verify_license(valid_es256_token, public_pem)
    assert info.algorithm == "ES256"


# ==========================================
# 6. verify_license — негативные сценарии
# ==========================================

def test_verify_rs256_wrong_public_key(valid_rsa_token, rsa_public_other):
    """Подпись одним ключом, проверка другим → LicenseInvalidError."""
    with pytest.raises(LicenseInvalidError):
        verify_license(valid_rsa_token, rsa_public_other, algorithm="RS256")


def test_verify_rs256_expired(expired_rsa_token, rsa_public):
    """Истёкший RS256-токен → LicenseExpiredError."""
    with pytest.raises(LicenseExpiredError):
        verify_license(expired_rsa_token, rsa_public, algorithm="RS256")


def test_verify_rs256_missing_key():
    """Пустой ключ → LicenseMissingError."""
    with pytest.raises(LicenseMissingError):
        verify_license("", "some-key")


def test_verify_rs256_whitespace_key():
    """Ключ из пробелов → LicenseMissingError."""
    with pytest.raises(LicenseMissingError):
        verify_license("   \n\t  ", "some-key")


def test_verify_rs256_malformed_token(rsa_public):
    """Мусорный токен → LicenseInvalidError."""
    with pytest.raises(LicenseInvalidError):
        verify_license("not.a.jwt", rsa_public, algorithm="RS256")


def test_verify_rs256_tampered_payload(valid_rsa_token, rsa_public):
    """Модифицированный payload (подпись старая) → LicenseInvalidError."""
    parts = valid_rsa_token.split(".")

    # Меняем один символ в payload-сегменте
    payload = parts[1]
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    with pytest.raises(LicenseInvalidError):
        verify_license(tampered, rsa_public, algorithm="RS256")


def test_verify_rs256_wrong_issuer(rsa_private, rsa_public):
    """Токен с чужим issuer → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "another-vendor",
        "jti": "test-jti",
        "holder": "Test",
        "tier": "trial",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private, algorithm="RS256")

    with pytest.raises(LicenseInvalidError):
        verify_license(token, rsa_public, algorithm="RS256")


def test_verify_rs256_missing_holder(rsa_private, rsa_public):
    """Токен без holder → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": LICENSE_ISSUER,
        "jti": "test-jti",
        "tier": "trial",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private, algorithm="RS256")

    with pytest.raises(LicenseInvalidError, match="обязательные поля"):
        verify_license(token, rsa_public, algorithm="RS256")


def test_verify_rs256_invalid_tier(rsa_private, rsa_public):
    """Неизвестный tier в payload → LicenseInvalidError."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": LICENSE_ISSUER,
        "jti": "test-jti",
        "holder": "Test",
        "tier": "super_pro",
        "features": [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private, algorithm="RS256")

    with pytest.raises(LicenseInvalidError, match="tier"):
        verify_license(token, rsa_public, algorithm="RS256")


# ==========================================
# 7. Algorithm confusion / alg=none
# ==========================================

def test_verify_rs256_token_with_hs256_flag(valid_rsa_token, rsa_public):
    """
    RS256-токен, проверяемый как HS256 → LicenseInvalidError.

    Защита от классической атаки algorithm confusion:
    злоумышленник переподписывает JWT алгоритмом HS256, используя
    публичный ключ в роли HMAC-секрета. Наш код принимает только
    те алгоритмы, которые указаны в `algorithm` (или в
    SUPPORTED_ALGORITHMS при None), поэтому HS256 «не пройдёт»,
    если явно запрошен RS256.
    """
    with pytest.raises(LicenseInvalidError):
        verify_license(valid_rsa_token, rsa_public, algorithm="HS256")


def test_verify_alg_none_rejected(rsa_public):
    """
    Токен с alg=none → LicenseInvalidError.

    jose не принимает "none" из коробки — но проверяем,
    что наш список SUPPORTED_ALGORITHMS его тоже не содержит.
    """
    assert "none" not in SUPPORTED_ALGORITHMS

    # Конструируем «none»-токен вручную
    import base64
    import json

    header = {"alg": "none", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    payload = {
        "iss": LICENSE_ISSUER,
        "jti": "test-jti",
        "holder": "Hacker",
        "tier": "enterprise",
        "features": ["audit_export"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=10)).timestamp()),
    }

    def _b64(obj):
        return (
            base64.urlsafe_b64encode(json.dumps(obj).encode())
            .rstrip(b"=")
            .decode()
        )

    token = f"{_b64(header)}.{_b64(payload)}."

    with pytest.raises(LicenseInvalidError):
        verify_license(token, rsa_public)


# ==========================================
# 8. instance_id binding (RS256)
# ==========================================

def test_verify_rs256_instance_match(rsa_token_with_instance, rsa_public):
    """instance_id совпадает → OK."""
    info = verify_license(
        rsa_token_with_instance,
        rsa_public,
        expected_instance_id="rsa-instance-abc123",
        algorithm="RS256",
    )
    assert info.is_instance_bound
    assert info.instance_id == "rsa-instance-abc123"


def test_verify_rs256_instance_mismatch(rsa_token_with_instance, rsa_public):
    """Разные instance_id → LicenseInstanceMismatchError."""
    with pytest.raises(LicenseInstanceMismatchError):
        verify_license(
            rsa_token_with_instance,
            rsa_public,
            expected_instance_id="different-instance",
            algorithm="RS256",
        )


def test_verify_rs256_instance_not_expected(rsa_token_with_instance, rsa_public):
    """expected_instance_id=None → проверка пропускается (warning)."""
    info = verify_license(
        rsa_token_with_instance,
        rsa_public,
        expected_instance_id=None,
        algorithm="RS256",
    )
    assert info.instance_id == "rsa-instance-abc123"


# ==========================================
# 9. Обратная совместимость с HS256
# ==========================================

TEST_HS256_SECRET = "test-hs256-secret-for-compat-tests-min-32-chars"


def test_hs256_still_works():
    """HS256 продолжает работать после добавления RS256/ES256."""
    token = create_license_token(
        holder="ООО HS256 Тест",
        secret=TEST_HS256_SECRET,
        tier="enterprise",
        days=30,
        algorithm="HS256",
    )
    info = verify_license(token, TEST_HS256_SECRET, algorithm="HS256")
    assert info.holder == "ООО HS256 Тест"
    assert info.algorithm == "HS256"


def test_hs256_auto_detect():
    """algorithm=None → jose сам определяет HS256."""
    token = create_license_token(
        holder="ООО HS256 Тест",
        secret=TEST_HS256_SECRET,
        tier="enterprise",
        days=30,
        algorithm="HS256",
    )
    info = verify_license(token, TEST_HS256_SECRET)
    assert info.algorithm == "HS256"


def test_hs256_wrong_secret():
    """HS256 с неверным секретом → LicenseInvalidError."""
    token = create_license_token(
        holder="Test",
        secret=TEST_HS256_SECRET,
        tier="trial",
        days=10,
        algorithm="HS256",
    )
    with pytest.raises(LicenseInvalidError):
        verify_license(token, "wrong-secret-completely-different-key")


# ==========================================
# 10. Кросс-алгоритменная защита
# ==========================================

def test_hs256_token_verified_as_rs256_fails(rsa_public):
    """
    HS256-токен, проверяемый как RS256 → LicenseInvalidError.

    Публичный RSA-ключ — не HMAC-секрет, подпись не сойдётся.
    Это вторая половина защиты от algorithm confusion.
    """
    token = create_license_token(
        holder="Test",
        secret=TEST_HS256_SECRET,
        tier="trial",
        days=10,
        algorithm="HS256",
    )
    with pytest.raises(LicenseInvalidError):
        verify_license(token, rsa_public, algorithm="RS256")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])