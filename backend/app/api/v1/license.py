# backend/app/api/v1/license.py
"""
API лицензии APS Production Scheduler.

Эндпоинты:
  GET /api/v1/license/info      — статус лицензии (публичный)
  GET /api/v1/license/instance  — instance_id сервера (публичный)

Оба — публичные (не требуют авторизации и валидной лицензии),
потому что:
  - /info нужен UI, чтобы показать статус и причину невалидности;
  - /instance нужен для генерации привязанной лицензии до её установки.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.license import (
    DEFAULT_FEATURES_BY_TIER,
    LICENSE_ALGORITHM,
    LICENSE_ISSUER,
    TIER_HIERARCHY,
    LicenseInfo,
)

router = APIRouter(prefix="/api/v1/license", tags=["Лицензия"])


# ==========================================
# ХЕЛПЕРЫ
# ==========================================

def _get_license_info(request: Request) -> Optional[LicenseInfo]:
    """Возвращает LicenseInfo из app.state (или None)."""
    return getattr(request.app.state, "license_info", None)


def _get_license_error(request: Request) -> Optional[str]:
    """Возвращает текст ошибки лицензии (или None)."""
    return getattr(request.app.state, "license_error", None)


def _get_instance_id(request: Request) -> Optional[str]:
    """Возвращает instance_id сервера (или None)."""
    return getattr(request.app.state, "instance_id", None)


def _serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 или None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ==========================================
# GET /api/v1/license/info
# ==========================================

@router.get("/info")
async def get_license_info(request: Request) -> Dict[str, Any]:
    """
    Возвращает статус лицензии.

    Формат:
      {
        "valid": bool,
        "verify_enabled": bool,
        "holder": str | null,
        "tier": str | null,
        "tier_hierarchy": [...],          # список доступных tiers
        "features": [str],                # активные фичи
        "default_features_by_tier": {...},# для справки в UI
        "issued_at": str | null,
        "expires_at": str | null,
        "days_left": int | null,
        "is_expired": bool,
        "instance_id": str | null,        # текущий instance_id сервера
        "instance_bound": bool,           # привязана ли лицензия к серверу
        "max_users": int | null,
        "error": str | null               # текст ошибки, если невалидна
      }

    Публичный. Не требует авторизации и валидной лицензии.
    """
    info = _get_license_info(request)
    error = _get_license_error(request)
    instance_id = _get_instance_id(request)

    verify_enabled = settings.LICENSE_VERIFY
    key_provided = bool(settings.LICENSE_KEY)

    if info is not None and not info.is_expired:
        return {
            "valid": True,
            "verify_enabled": verify_enabled,
            "key_provided": key_provided,
            "holder": info.holder,
            "tier": info.tier,
            "tier_hierarchy": list(TIER_HIERARCHY),
            "features": sorted(info.features),
            "default_features_by_tier": {
                t: sorted(fs) for t, fs in DEFAULT_FEATURES_BY_TIER.items()
            },
            "issued_at": _serialize_datetime(info.issued_at),
            "expires_at": _serialize_datetime(info.expires_at),
            "days_left": info.days_left,
            "is_expired": False,
            "instance_id": instance_id,
            "instance_bound": info.is_instance_bound,
            "max_users": info.max_users,
            "error": None,
            "issuer": LICENSE_ISSUER,
            "algorithm": LICENSE_ALGORITHM,
        }

    # Невалидная (или отсутствует)
    return {
        "valid": False,
        "verify_enabled": verify_enabled,
        "key_provided": key_provided,
        "holder": None,
        "tier": None,
        "tier_hierarchy": list(TIER_HIERARCHY),
        "features": [],
        "default_features_by_tier": {
            t: sorted(fs) for t, fs in DEFAULT_FEATURES_BY_TIER.items()
        },
        "issued_at": None,
        "expires_at": None,
        "days_left": None,
        "is_expired": False,
        "instance_id": instance_id,
        "instance_bound": False,
        "max_users": None,
        "error": error or "Лицензия не проверена",
        "issuer": LICENSE_ISSUER,
        "algorithm": LICENSE_ALGORITHM,
    }


# ==========================================
# GET /api/v1/license/instance
# ==========================================

@router.get("/instance")
async def get_instance_id(request: Request) -> Dict[str, Any]:
    """
    Возвращает instance_id текущего сервера.

    Формат:
      {
        "instance_id": str | null,
        "algorithm": "sha256",
        "components": ["machine-id", "mac", "hostname", "platform"]
      }

    Публичный. Используется для генерации привязанной лицензии:
      1. Клиент запускает это эндпоинт (или CLI `instance-id`).
      2. Присылает instance_id вендору.
      3. Вендор генерирует лицензию с этим instance_id.
      4. Лицензия работает только на этом сервере.
    """
    instance_id = _get_instance_id(request)
    return {
        "instance_id": instance_id,
        "algorithm": "sha256",
        "components": ["machine-id", "mac", "hostname", "platform"],
    }