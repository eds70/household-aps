# backend/app/core/license.py
"""
Модуль лицензирования APS Production Scheduler.

Уровень 1 (offline JWT): лицензия — это JWT-токен, подписанный
ключом вендора. Поддерживаются:
  - HS256/384/512 — симметричные, ключ = секрет. Для локальной
    разработки, когда вендор = клиент.
  - RS256/384/512 — асимметричные, подпись приватным ключом,
    проверка публичным. Для продакшена: клиент получает только
    публичный ключ и не может выпустить себе лицензию.
  - ES256/384/512 — ECDSA, тоже асимметричные (короче ключи).

Backend валидирует подпись, срок и набор фич локально, без
обращения к внешним серверам.

Уровень 2 (machine fingerprint): лицензия может быть привязана
к конкретному инстансу через `instance_id` — SHA256-хеш от
machine-id + MAC + hostname (для Docker — из volume-файла
`/data/license_instance`). Если привязка задана — лицензия
работает только на этом сервере.

Использование:
    from app.core.license import verify_license, LicenseInfo

    # HS256 (dev):
    info = verify_license(key=LICENSE_KEY, secret=MASTER_SECRET,
                          algorithm="HS256")

    # RS256 (prod):
    info = verify_license(key=LICENSE_KEY, secret=PUBLIC_KEY_PEM,
                          algorithm="RS256")

    # Или без явного алгоритма — verify_license сам определит
    # по заголовку JWT (список разрешённых — SUPPORTED_ALGORITHMS).
    info = verify_license(key=LICENSE_KEY, secret=VERIFY_KEY)

    if info.has_feature("audit_export"):
        ...

FastAPI dependencies:
    @router.post("/export")
    async def export(
        _: None = Depends(require_feature("audit_export")),
    ):
        ...
"""
from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Optional, Set

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.scheduler.logging_config import setup_scheduler_logging

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# КОНСТАНТЫ
# ==========================================

LICENSE_ISSUER: str = "aps-scheduler-vendor"

# Алгоритм по умолчанию — HS256. Используется, если явно не указан
# ни в .env, ни при вызове create_license_token / verify_license.
# Для продакшена переключиться на RS256 через LICENSE_PUBLIC_KEY в .env.
LICENSE_ALGORITHM: str = "HS256"

# Все алгоритмы, которые мы принимаем в JWT при проверке.
#
# ВАЖНО: список ФИКСИРОВАННЫЙ. jwt.decode проверяет, что alg в
# заголовке входит в этот список. Это защищает от:
#   1. alg="none" — тривиальная подделка (jose отклонит).
#   2. Algorithm confusion (HS256 с публичным ключом в роли HMAC-
#      секрета) — тоже не пройдёт, потому что тип ключа не совпадёт.
SUPPORTED_ALGORITHMS: tuple[str, ...] = (
    "HS256", "HS384", "HS512",   # симметричные (dev)
    "RS256", "RS384", "RS512",   # RSA (prod)
    "ES256", "ES384", "ES512",   # ECDSA (prod)
)

# Алгоритмы, которые используются для ПОДПИСИ по умолчанию.
# CLI generate_license.py использует это, если не передан --algorithm.
SIGNING_ALGORITHM_DEFAULT: str = "HS256"

# Иерархия tiers: чем выше индекс — тем больше прав.
TIER_HIERARCHY: tuple[str, ...] = ("trial", "community", "enterprise")

# Фичи, доступные на каждом уровне (по умолчанию).
DEFAULT_FEATURES_BY_TIER: Dict[str, Set[str]] = {
    "trial": {
        "audit_export",
        "whatif",
        "cz",
        "multi_objective",
        "help_crud",
    },
    "community": set(),   # базовые фичи, без специальных
    "enterprise": {
        "audit_export",
        "whatif",
        "cz",
        "multi_objective",
        "help_crud",
    },
}

# Куда сохранять instance_id (в Docker — это должно быть в volume).
INSTANCE_FILE_PATH: Path = Path(os.getenv("LICENSE_INSTANCE_FILE", "/data/license_instance"))

# Публичные эндпоинты, не требующие валидной лицензии.
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Все эндпоинты авторизации — публичные:
    #   /api/v1/auth/login   — вход
    #   /api/v1/auth/me      — проверка текущего пользователя
    #   /api/v1/auth/change-password — смена пароля
    "/api/v1/auth/",
    # Лицензия:
    "/api/v1/license/instance",  # для первичной генерации лицензии
    "/api/v1/license/info",      # для UI: показать статус даже при невалидной лицензии
)


# ==========================================
# ИСКЛЮЧЕНИЯ
# ==========================================

class LicenseError(Exception):
    """Базовое исключение для ошибок лицензии."""
    pass


class LicenseMissingError(LicenseError):
    """LICENSE_KEY не задан или пуст."""
    pass


class LicenseInvalidError(LicenseError):
    """Подпись/формат токена невалидны."""
    pass


class LicenseExpiredError(LicenseError):
    """Срок действия лицензии истёк."""
    pass


class LicenseInstanceMismatchError(LicenseError):
    """instance_id в токене не совпадает с текущим."""
    pass


# ==========================================
# DATACLASS: LicenseInfo
# ==========================================

@dataclass(frozen=True)
class LicenseInfo:
    """
    Разобранная и валидированная лицензия.

    Все поля — из JWT-payload, проверенные:
      - подпись (HS256/RS256/ES256 — какой указан в заголовке);
      - issuer (LICENSE_ISSUER);
      - срок (exp);
      - instance_id (если задан).
    """
    holder: str                        # организация-владелец
    tier: str                          # trial | community | enterprise
    features: FrozenSet[str]           # активные фичи
    issued_at: datetime                # когда выпущена
    expires_at: datetime               # когда истекает
    instance_id: Optional[str] = None  # привязка к машине (если есть)
    max_users: Optional[int] = None    # лимит на количество пользователей
    # Итерация 17.x: уникальный ID лицензии. Готовит почву для
    # revocation list в будущем. Сейчас не используется в проверке.
    jti: Optional[str] = None
    # Итерация 17.x: алгоритм подписи, которым была выпущена лицензия
    # (взят из заголовка JWT). Полезно для UI и логов.
    algorithm: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)  # для отладки

    # ---------- свойства ----------

    @property
    def days_left(self) -> int:
        """Сколько дней осталось до истечения (может быть отрицательным)."""
        delta = self.expires_at - datetime.now(timezone.utc)
        return delta.days

    @property
    def is_expired(self) -> bool:
        """Истёк ли срок."""
        return self.expires_at <= datetime.now(timezone.utc)

    @property
    def is_instance_bound(self) -> bool:
        """Привязана ли лицензия к конкретному инстансу."""
        return self.instance_id is not None

    @property
    def tier_index(self) -> int:
        """Индекс tier в иерархии (для сравнения уровней)."""
        try:
            return TIER_HIERARCHY.index(self.tier)
        except ValueError:
            return -1

    # ---------- методы ----------

    def has_feature(self, feature: str) -> bool:
        """
        Проверяет наличие фичи.

        Логика:
          1. Если фича в явном списке features — да.
          2. Если фича в DEFAULT_FEATURES_BY_TIER[tier] — да.
          3. Иначе — нет.
        """
        if feature in self.features:
            return True
        return feature in DEFAULT_FEATURES_BY_TIER.get(self.tier, set())

    def has_tier(self, min_tier: str) -> bool:
        """Проверяет, что tier не ниже указанного."""
        try:
            required = TIER_HIERARCHY.index(min_tier)
        except ValueError:
            return False
        return self.tier_index >= required


# ==========================================
# INSTANCE ID
# ==========================================

def _read_machine_id() -> Optional[str]:
    """Читает /etc/machine-id (Linux) или его аналог."""
    candidates = [
        Path("/etc/machine-id"),
        Path("/var/lib/dbus/machine-id"),
    ]
    for path in candidates:
        if path.exists():
            try:
                content = path.read_text().strip()
                if content:
                    return content
            except OSError:
                continue
    return None


def _read_mac_address() -> Optional[str]:
    """Возвращает MAC-адрес первого non-loopback интерфейса."""
    try:
        mac = uuid.getnode()
        # uuid.getnode() может вернуть случайный MAC, если не удалось определить.
        # Проверяем, что бит multicast не установлен (не «случайный»).
        if (mac >> 40) % 2:
            return None
        return f"{mac:012x}"
    except Exception:
        return None


def compute_instance_id() -> str:
    """
    Вычисляет instance_id текущего сервера.

    Компоненты (в порядке приоритета):
      1. Файл /data/license_instance — если существует (Docker volume).
      2. machine-id + MAC + hostname — для bare-metal / VM.

    Возвращает HEX-строку (SHA256, 64 символа).
    """
    # 1. Файл instance (для Docker — в volume)
    if INSTANCE_FILE_PATH.exists():
        try:
            content = INSTANCE_FILE_PATH.read_text().strip()
            if content:
                return content
        except OSError as e:
            logger.warning(
                f"[license] Не удалось прочитать {INSTANCE_FILE_PATH}: {e}"
            )

    # 2. Системные идентификаторы
    parts: list[str] = []
    machine_id = _read_machine_id()
    if machine_id:
        parts.append(f"machine:{machine_id}")
    mac = _read_mac_address()
    if mac:
        parts.append(f"mac:{mac}")
    parts.append(f"hostname:{socket.gethostname()}")
    parts.append(f"platform:{platform.system()}:{platform.machine()}")

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_or_create_instance_id(
        path: Optional[Path] = None,
) -> str:
    """
    Возвращает instance_id, создавая файл, если его нет.

    При создании — записывает в файл (для Docker — в volume).
    Если файл недоступен для записи (нет volume) — работает только
    с системным идентификатором.
    """
    target = path or INSTANCE_FILE_PATH

    if target.exists():
        try:
            content = target.read_text().strip()
            if content:
                return content
        except OSError:
            pass

    instance_id = compute_instance_id()

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(instance_id, encoding="utf-8")
        logger.info(f"[license] instance_id сохранён в {target}")
    except OSError as e:
        logger.warning(
            f"[license] Не удалось сохранить instance_id в {target}: {e}. "
            f"Использую вычисленное значение (может меняться между перезапусками)."
        )

    return instance_id


# ==========================================
# JWT: СОЗДАНИЕ (для CLI и тестов)
# ==========================================

def create_license_token(
        holder: str,
        secret: str,
        tier: str = "enterprise",
        days: int = 90,
        features: Optional[Set[str]] = None,
        instance_id: Optional[str] = None,
        max_users: Optional[int] = None,
        algorithm: str = SIGNING_ALGORITHM_DEFAULT,
        jti: Optional[str] = None,
) -> str:
    """
    Создаёт подписанный JWT-токен лицензии.

    ВНИМАНИЕ: в production эта функция вызывается только из CLI
    (scripts/generate_license.py) на стороне вендора. В backend
    она доступна только для тестов.

    Args:
        holder: название организации-владельца.
        secret:
            - HS256/384/512: мастер-секрет (64 hex-символа).
            - RS256/384/512, ES256/384/512: ПРИВАТНЫЙ ключ в PEM.
        tier: trial | community | enterprise.
        days: срок в днях от текущего момента.
        features: множество фич (если None — берётся по tier).
        instance_id: привязка к машине (опционально).
        max_users: лимит пользователей (опционально).
        algorithm: алгоритм подписи (HS256 по умолчанию).
        jti: уникальный ID лицензии. Если не задан — генерируется
            автоматически (UUID4). Используется для будущего
            revocation list.

    Returns:
        Подписанный JWT (строка).
    """
    if tier not in TIER_HIERARCHY:
        raise ValueError(
            f"Неизвестный tier: {tier!r}. "
            f"Допустимые: {', '.join(TIER_HIERARCHY)}"
        )

    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Неподдерживаемый алгоритм: {algorithm!r}. "
            f"Допустимые: {', '.join(SUPPORTED_ALGORITHMS)}"
        )

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)

    if features is None:
        features = DEFAULT_FEATURES_BY_TIER.get(tier, set())

    if jti is None:
        jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "iss": LICENSE_ISSUER,
        "jti": jti,
        "holder": holder,
        "tier": tier,
        "features": sorted(features),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if instance_id:
        payload["instance_id"] = instance_id
    if max_users is not None:
        payload["max_users"] = max_users

    return jwt.encode(payload, secret, algorithm=algorithm)


# ==========================================
# JWT: ПРОВЕРКА
# ==========================================

def verify_license(
        key: str,
        secret: str,
        expected_instance_id: Optional[str] = None,
        algorithm: Optional[str] = None,
) -> LicenseInfo:
    """
    Проверяет JWT-лицензию и возвращает LicenseInfo.

    Args:
        key: LICENSE_KEY (JWT-строка).
        secret:
            - HS256/384/512: тот же секрет, что использовался при подписи.
            - RS256/384/512, ES256/384/512: ПУБЛИЧНЫЙ ключ вендора
              (PEM-строка).
        expected_instance_id: текущий instance_id сервера.
            Если задан и в токене есть instance_id — они должны совпадать.
        algorithm: конкретный алгоритм. Если None — принимаются
            любые из SUPPORTED_ALGORITHMS, jwt.decode сам выберет
            нужный по заголовку токена. Это позволяет клиенту не
            знать заранее, каким алгоритмом подписана лицензия.

    Raises:
        LicenseMissingError: key пустой.
        LicenseInvalidError: подпись/issuer/формат невалидны.
        LicenseExpiredError: срок истёк.
        LicenseInstanceMismatchError: instance_id не совпал.

    Returns:
        LicenseInfo с разобранными полями.
    """
    if not key or not key.strip():
        raise LicenseMissingError("LICENSE_KEY не задан")

    # Если algorithm не задан явно — принимаем все поддерживаемые.
    # python-jose сам выберет нужный по заголовку JWT. Список
    # фиксированный, "none" и algorithm confusion невозможны.
    algorithms = [algorithm] if algorithm else list(SUPPORTED_ALGORITHMS)

    try:
        payload = jwt.decode(
            key,
            secret,
            algorithms=algorithms,
            issuer=LICENSE_ISSUER,
        )
    except JWTError as e:
        msg = str(e)
        if "expired" in msg.lower() or "ExpiredSignature" in msg:
            raise LicenseExpiredError(f"Срок действия лицензии истёк: {e}")
        raise LicenseInvalidError(f"Невалидная лицензия: {e}")

    # Алгоритм, которым реально подписан токен (из заголовка).
    # jose умеет возвращать заголовок через jwt.get_unverified_header,
    # но здесь достаточно взять из исключения/успеха — и добавить
    # в LicenseInfo для отладки.
    try:
        header = jwt.get_unverified_header(key)
        used_algorithm = header.get("alg")
    except JWTError:
        used_algorithm = None

    # Обязательные поля
    holder = payload.get("holder")
    tier = payload.get("tier")
    exp = payload.get("exp")
    iat = payload.get("iat")

    if not holder or not tier or not exp or not iat:
        raise LicenseInvalidError(
            "В лицензии отсутствуют обязательные поля "
            "(holder, tier, exp, iat)"
        )

    if tier not in TIER_HIERARCHY:
        raise LicenseInvalidError(
            f"Неизвестный tier в лицензии: {tier!r}"
        )

    # Проверка instance_id (Уровень 2)
    token_instance = payload.get("instance_id")
    if token_instance:
        if expected_instance_id is None:
            logger.warning(
                "[license] Лицензия привязана к instance_id, но "
                "ожидаемое значение не передано — пропускаю проверку."
            )
        elif token_instance != expected_instance_id:
            raise LicenseInstanceMismatchError(
                f"Лицензия привязана к другому серверу. "
                f"Ожидалось: {expected_instance_id[:16]}..., "
                f"в лицензии: {token_instance[:16]}..."
            )

    features = frozenset(payload.get("features", []))

    info = LicenseInfo(
        holder=holder,
        tier=tier,
        features=features,
        issued_at=datetime.fromtimestamp(iat, tz=timezone.utc),
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        instance_id=token_instance,
        max_users=payload.get("max_users"),
        jti=payload.get("jti"),
        algorithm=used_algorithm,
        raw_payload=payload,
    )

    # Дополнительная проверка (jwt.decode уже бросил бы, но перестрахуемся)
    if info.is_expired:
        raise LicenseExpiredError(
            f"Срок действия лицензии истёк "
            f"({info.expires_at.isoformat()})"
        )

    return info


# ==========================================
# FASTAPI DEPENDENCIES
# ==========================================

def get_license_info(request: Request) -> Optional[LicenseInfo]:
    """
    Возвращает LicenseInfo из app.state (заполняется при старте).

    Если LICENSE_VERIFY=false или лицензия не загружена — None.
    """
    return getattr(request.app.state, "license_info", None)


def get_license_error(request: Request) -> Optional[str]:
    """
    Возвращает текст ошибки лицензии (для 403-ответов и UI).

    None — если ошибки нет.
    """
    return getattr(request.app.state, "license_error", None)


def require_valid_license(
        request: Request,
) -> LicenseInfo:
    """
    FastAPI-dependency: требует валидную лицензию.

    Использование:
        @router.get("/protected")
        async def protected(
            _: LicenseInfo = Depends(require_valid_license),
        ):
            ...

    Raises:
        HTTPException 403: если лицензия невалидна.
        HTTPException 500: если LICENSE_VERIFY=true, но license_info
            не был загружен при старте (баг конфигурации).
    """
    info = get_license_info(request)
    if info is not None and not info.is_expired:
        return info

    error = get_license_error(request) or "Лицензия недействительна"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "LICENSE_INVALID",
            "message": error,
        },
    )


def require_feature(feature: str) -> Callable[..., LicenseInfo]:
    """
    Factory: возвращает dependency, требующую наличия фичи.

    Использование:
        @router.post("/export")
        async def export(
            _: LicenseInfo = Depends(require_feature("audit_export")),
        ):
            ...

    Raises:
        HTTPException 403: если фичи нет.
    """
    def _check(request: Request) -> LicenseInfo:
        info = require_valid_license(request)

        if not info.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LICENSE_FEATURE_MISSING",
                    "message": (
                        f"Фича {feature!r} не входит в вашу лицензию "
                        f"(tier={info.tier})."
                    ),
                    "feature": feature,
                    "tier": info.tier,
                },
            )
        return info

    return _check


def require_tier(min_tier: str) -> Callable[..., LicenseInfo]:
    """
    Factory: возвращает dependency, требующую минимальный tier.

    Использование:
        @router.get("/enterprise-only")
        async def enterprise_only(
            _: LicenseInfo = Depends(require_tier("enterprise")),
        ):
            ...

    Raises:
        HTTPException 403: если tier ниже требуемого.
    """
    if min_tier not in TIER_HIERARCHY:
        raise ValueError(
            f"Неизвестный min_tier: {min_tier!r}. "
            f"Допустимые: {', '.join(TIER_HIERARCHY)}"
        )

    def _check(request: Request) -> LicenseInfo:
        info = require_valid_license(request)

        if not info.has_tier(min_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LICENSE_TIER_INSUFFICIENT",
                    "message": (
                        f"Требуется tier {min_tier!r} или выше. "
                        f"Текущий: {info.tier!r}."
                    ),
                    "required_tier": min_tier,
                    "current_tier": info.tier,
                },
            )
        return info

    return _check