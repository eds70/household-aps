#!/usr/bin/env python3
# scripts/generate_license.py
"""
CLI для генерации лицензий APS Production Scheduler.

Запускается ВЕНОДОРОМ (на вашей машине), не клиентом.

Поддерживаются три алгоритма подписи:

  HS256 (по умолчанию, для локальной разработки)
    Симметричный. Ключ = секрет, хранится в
    ~/.aps/license_master_key.hex.
    ⚠️  Клиент получает ТОТ ЖЕ секрет, что и подписывает,
       поэтому технически может выпустить себе любую лицензию.
       Только для dev.

  RS256 (рекомендуется для продакшена)
    Асимметричный, RSA. Ключи хранятся в
    ~/.aps/license_master_key.private.pem  (у вендора, СЕКРЕТ)
    ~/.aps/license_master_key.public.pem   (раздаётся клиентам)
    Клиент может только ПРОВЕРИТЬ подпись, но не подписать.

  ES256 (опционально, ECDSA)
    Асимметричный, короче ключи. Тот же принцип, что RS256.

Использование:
    # 1. Сгенерировать ключ подписи (один раз)
    python scripts/generate_license.py init-master-key --algorithm HS256
    python scripts/generate_license.py init-master-key --algorithm RS256

    # 2. Выдать лицензию
    python scripts/generate_license.py generate \\
        --algorithm RS256 \\
        --org "ООО Ромашка" \\
        --tier enterprise \\
        --days 365 \\
        --output romashka.license

    # 3. Посмотреть содержимое
    python scripts/generate_license.py inspect \\
        --algorithm RS256 --key-file romashka.license

    # 4. Узнать instance_id текущей машины
    python scripts/generate_license.py instance-id

ВАЖНО про порядок аргументов:
    Глобальный --master-key идёт ДО подкоманды:
        generate_license.py --master-key <путь> generate --algorithm RS256 ...
    Остальные флаги (--algorithm, --org, ...) — ПОСЛЕ подкоманды.
"""
from __future__ import annotations

import argparse
import csv
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ==========================================
# sys.path: добавляем backend/ для импорта app.core.license
# ==========================================
# Файл лежит в: <project>/backend/scripts/generate_license.py
# Path(__file__).resolve().parent.parent → <project>/backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.core.license import (
        DEFAULT_FEATURES_BY_TIER,
        LICENSE_ISSUER,
        SIGNING_ALGORITHM_DEFAULT,
        SUPPORTED_ALGORITHMS,
        TIER_HIERARCHY,
        compute_instance_id,
        create_license_token,
        verify_license,
    )
except ImportError as e:
    print(f"ОШИБКА: не удалось импортировать app.core.license: {e}", file=sys.stderr)
    print(
        f"Проверьте, что файл {__file__} лежит в <project>/backend/scripts/, "
        f"а рядом есть <project>/backend/app/core/license.py",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    from jose import jwt
except ImportError:
    print(
        "ОШИБКА: не установлен python-jose. "
        "Установите: pip install 'python-jose[cryptography]'",
        file=sys.stderr,
    )
    sys.exit(2)

# Криптография для генерации ключей — нужна только для RS256/ES256.
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# ==========================================
# КОНСТАНТЫ
# ==========================================

# Где хранятся ключи (по умолчанию).
APS_DIR = Path.home() / ".aps"
DEFAULT_MASTER_KEY_PATH = APS_DIR / "license_master_key.hex"
DEFAULT_KEYPAIR_BASENAME = APS_DIR / "license_master_key"

# Журнал выданных лицензий.
JOURNAL_PATH = APS_DIR / "license_journal.csv"

# Симметричные алгоритмы (HS*).
HS_ALGORITHMS = ("HS256", "HS384", "HS512")
# Асимметричные (RS*, ES*).
ASYMMETRIC_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")


# ==========================================
# ХЕЛПЕРЫ: ЧТЕНИЕ/ЗАПИСЬ КЛЮЧЕЙ
# ==========================================

def _read_master_key(path: Path) -> str:
    """Читает мастер-секрет HS256 из файла. Ошибка, если файла нет."""
    if not path.exists():
        print(
            f"ОШИБКА: мастер-ключ не найден: {path}\n"
            f"Сгенерируйте его командой:\n"
            f"    python {Path(__file__).name} init-master-key --algorithm HS256\n"
            f"или укажите путь через --master-key",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        print(f"ОШИБКА: не удалось прочитать {path}: {e}", file=sys.stderr)
        sys.exit(1)

    if len(content) < 32:
        print(
            f"ОШИБКА: мастер-ключ слишком короткий ({len(content)} символов). "
            f"Ожидается минимум 32 символа (лучше — 64 hex).",
            file=sys.stderr,
        )
        sys.exit(1)

    return content


def _write_master_key(path: Path, key: str) -> None:
    """Записывает мастер-ключ в файл с правами 600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key, encoding="utf-8")

    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError as e:
            print(
                f"ПРЕДУПРЕЖДЕНИЕ: не удалось установить права 600 на {path}: {e}",
                file=sys.stderr,
            )


def _read_private_key_pem(path: Path) -> str:
    """Читает приватный ключ (для подписи RS/ES). Ошибка, если нет файла."""
    if not path.exists():
        print(
            f"ОШИБКА: приватный ключ не найден: {path}\n"
            f"Сгенерируйте его командой:\n"
            f"    python {Path(__file__).name} init-master-key --algorithm RS256\n"
            f"или укажите путь через --master-key",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ОШИБКА: не удалось прочитать {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _read_public_key_pem(path: Path) -> str:
    """Читает публичный ключ (для проверки RS/ES)."""
    if not path.exists():
        print(
            f"ОШИБКА: публичный ключ не найден: {path}\n"
            f"Сгенерируйте пару командой:\n"
            f"    python {Path(__file__).name} init-master-key --algorithm RS256",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ОШИБКА: не удалось прочитать {path}: {e}", file=sys.stderr)
        sys.exit(1)


# ==========================================
# ХЕЛПЕРЫ: ГЕНЕРАЦИЯ КЛЮЧЕЙ
# ==========================================

def _ensure_crypto_available() -> None:
    """Проверяет, что установлен пакет cryptography (для RS/ES)."""
    if not _CRYPTO_AVAILABLE:
        print(
            "ОШИБКА: для RS256/ES256 нужен пакет `cryptography`.\n"
            "Установите: pip install cryptography",
            file=sys.stderr,
        )
        sys.exit(2)


def _generate_rsa_keypair(bits: int = 3072) -> tuple[str, str]:
    """
    Генерирует пару RSA-ключей.

    Args:
        bits: размер ключа. 2048 — минимум, 3072 — рекомендуется,
            4096 — избыточно.

    Returns:
        (private_pem, public_pem) — обе строки в формате PEM (PKCS8/SPKI).
    """
    _ensure_crypto_available()

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def _generate_ec_keypair() -> tuple[str, str]:
    """
    Генерирует пару ECDSA-ключей (P-256, что соответствует ES256).

    Returns:
        (private_pem, public_pem) — обе строки в формате PEM.
    """
    _ensure_crypto_available()

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


# ==========================================
# ХЕЛПЕРЫ: ОБЩИЕ
# ==========================================

def _parse_features(raw: Optional[str], tier: str) -> set[str]:
    """Парсит строку фич 'a,b,c' или берёт дефолт по tier."""
    if raw is None:
        return set(DEFAULT_FEATURES_BY_TIER.get(tier, set()))
    return {f.strip() for f in raw.split(",") if f.strip()}


def _format_dt(dt: datetime) -> str:
    """Форматирует datetime в читаемый вид."""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _is_asymmetric(algorithm: str) -> bool:
    """True для RS*/ES*, False для HS*."""
    return algorithm in ASYMMETRIC_ALGORITHMS


def _write_journal_entry(
        algorithm: str,
        info,
        token: str,
        output_path: Optional[Path] = None,
) -> None:
    """
    Дописывает строку в CSV-журнал выданных лицензий.

    Журнал — простая таблица для разбора инцидентов: кому, когда,
    на какой срок, с каким instance_id выдана лицензия. Хранится
    в ~/.aps/license_journal.csv, дополняется через append.

    Не критичен для работы — ошибки записи только логируются.
    """
    try:
        APS_DIR.mkdir(parents=True, exist_ok=True)
        file_exists = JOURNAL_PATH.exists()

        with JOURNAL_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "issued_at_utc",
                    "jti",
                    "algorithm",
                    "holder",
                    "tier",
                    "instance_id",
                    "max_users",
                    "expires_at_utc",
                    "days",
                    "output_file",
                    "token_preview",
                ])
            writer.writerow([
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                info.jti or "",
                algorithm,
                info.holder,
                info.tier,
                info.instance_id or "",
                info.max_users if info.max_users is not None else "",
                info.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                info.days_left,
                str(output_path) if output_path else "",
                token[:40] + "...",
                ])
    except OSError as e:
        print(
            f"ПРЕДУПРЕЖДЕНИЕ: не удалось записать в журнал {JOURNAL_PATH}: {e}",
            file=sys.stderr,
        )


# ==========================================
# КОМАНДА: init-master-key
# ==========================================

def cmd_init_master_key(args: argparse.Namespace) -> int:
    """Создаёт ключ подписи (HS256) или пару ключей (RS256/ES256)."""
    algorithm = args.algorithm

    if algorithm in HS_ALGORITHMS:
        return _init_hs_key(args)
    elif algorithm in ASYMMETRIC_ALGORITHMS:
        return _init_asymmetric_keypair(args, algorithm)
    else:
        print(f"ОШИБКА: неизвестный алгоритм: {algorithm}", file=sys.stderr)
        return 1


def _init_hs_key(args: argparse.Namespace) -> int:
    """Создаёт симметричный мастер-ключ HS256."""
    path = Path(args.master_key) if args.master_key else DEFAULT_MASTER_KEY_PATH

    if path.exists() and not args.force:
        print(
            f"ОШИБКА: файл {path} уже существует.\n"
            f"Если хотите перезаписать — добавьте --force (ВНИМАНИЕ: "
            f"все ранее выданные лицензии перестанут работать!).",
            file=sys.stderr,
        )
        return 1

    key = secrets.token_hex(32)   # 64 hex-символа = 32 байта = 256 бит
    _write_master_key(path, key)

    print("=" * 70)
    print("Мастер-ключ HS256 успешно создан")
    print("=" * 70)
    print()
    print(f"Путь:      {path}")
    print(f"Длина:     {len(key)} символов")
    print()
    print("LICENSE_MASTER_SECRET (положить в .env backend'а):")
    print()
    print(f"    {key}")
    print()
    print("⚠️  ВНИМАНИЕ:")
    print("   1. Этот ключ ОДИНАКОВ для подписи и проверки.")
    print("   2. Клиент, зная его, может выпускать свои лицензии.")
    print("   3. Используйте HS256 только для локальной разработки.")
    print("   4. Для продакшена: init-master-key --algorithm RS256")
    print()

    return 0


def _init_asymmetric_keypair(args: argparse.Namespace, algorithm: str) -> int:
    """Создаёт пару ключей для RS256/ES256 (приватный + публичный)."""
    _ensure_crypto_available()

    base = Path(args.master_key) if args.master_key else DEFAULT_KEYPAIR_BASENAME
    private_path = base.with_suffix(".private.pem")
    public_path = base.with_suffix(".public.pem")

    if (private_path.exists() or public_path.exists()) and not args.force:
        print(
            f"ОШИБКА: файлы ключей уже существуют:\n"
            f"  {private_path}\n"
            f"  {public_path}\n"
            f"Если хотите перезаписать — добавьте --force (ВНИМАНИЕ: "
            f"все ранее выданные лицензии перестанут работать!).",
            file=sys.stderr,
        )
        return 1

    if algorithm.startswith("RS"):
        bits = 3072
        if hasattr(args, "key_size") and args.key_size:
            bits = args.key_size
        private_pem, public_pem = _generate_rsa_keypair(bits=bits)
        key_desc = f"RSA-{bits}"
    elif algorithm.startswith("ES"):
        private_pem, public_pem = _generate_ec_keypair()
        key_desc = "ECDSA P-256"
    else:
        print(f"ОШИБКА: неподдерживаемый алгоритм: {algorithm}", file=sys.stderr)
        return 1

    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_text(private_pem, encoding="utf-8")
    public_path.write_text(public_pem, encoding="utf-8")

    if os.name != "nt":
        try:
            private_path.chmod(0o600)
        except OSError as e:
            print(
                f"ПРЕДУПРЕЖДЕНИЕ: не удалось установить права 600 на "
                f"{private_path}: {e}",
                file=sys.stderr,
            )

    print("=" * 70)
    print(f"Пара ключей {algorithm} ({key_desc}) успешно создана")
    print("=" * 70)
    print()
    print(f"Приватный ключ (СЕКРЕТ вендора):  {private_path}")
    print(f"Публичный ключ  (раздаётся):      {public_path}")
    print()
    print("=" * 70)
    print("ПУБЛИЧНЫЙ КЛЮЧ — вставить в .env клиента как LICENSE_PUBLIC_KEY")
    print("=" * 70)
    print()
    print(public_pem)
    print()
    print("⚠️  ВАЖНО:")
    print("   1. Приватный ключ НИКОГДА не передавайте клиенту.")
    print("   2. Публичный ключ безопасно хранить и распространять.")
    print("   3. Если приватный ключ утечёт — перегенерируйте пару")
    print("      и перевыпустите лицензии (старые JWT перестанут работать).")
    print()

    return 0


# ==========================================
# КОМАНДА: generate
# ==========================================

def cmd_generate(args: argparse.Namespace) -> int:
    """Генерирует лицензию (HS256 или RS256/ES256)."""
    algorithm = args.algorithm

    if args.tier not in TIER_HIERARCHY:
        print(
            f"ОШИБКА: неизвестный tier: {args.tier!r}. "
            f"Допустимые: {', '.join(TIER_HIERARCHY)}",
            file=sys.stderr,
        )
        return 1

    # Читаем подходящий ключ для ПОДПИСИ
    if algorithm in HS_ALGORITHMS:
        master_key_path = (
            Path(args.master_key) if args.master_key else DEFAULT_MASTER_KEY_PATH
        )
        signing_key = _read_master_key(master_key_path)
        key_location = str(master_key_path)
    elif algorithm in ASYMMETRIC_ALGORITHMS:
        base = (
            Path(args.master_key) if args.master_key else DEFAULT_KEYPAIR_BASENAME
        )
        private_path = base.with_suffix(".private.pem")
        signing_key = _read_private_key_pem(private_path)
        key_location = str(private_path)
    else:
        print(f"ОШИБКА: неподдерживаемый алгоритм: {algorithm}", file=sys.stderr)
        return 1

    features = _parse_features(args.features, args.tier)

    # Подпись
    try:
        token = create_license_token(
            holder=args.org,
            secret=signing_key,
            tier=args.tier,
            days=args.days,
            features=features,
            instance_id=args.instance_id or None,
            max_users=args.max_users,
            algorithm=algorithm,
        )
    except ValueError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1

    # ==========================================
    # Разбор обратно — для сводки
    # ==========================================
    # ВАЖНО (косметика):
    #   Для верификации используем ПУБЛИЧНЫЙ ключ (для RS/ES).
    #   Если верифицировать приватным — python-jose выдаёт
    #   UserWarning "Attempting to verify a message with a private key".
    #   Для HS256 публичного ключа нет — там и подпись, и проверка
    #   одним и тем же секретом.
    if algorithm in HS_ALGORITHMS:
        verify_key = signing_key
    else:
        base = (
            Path(args.master_key) if args.master_key else DEFAULT_KEYPAIR_BASENAME
        )
        verify_key = _read_public_key_pem(base.with_suffix(".public.pem"))

    info = verify_license(
        key=token,
        secret=verify_key,
        expected_instance_id=args.instance_id or None,
        algorithm=algorithm,
    )

    output_path = Path(args.output) if args.output else None

    # Вывод
    print("=" * 70)
    print("Лицензия успешно сгенерирована")
    print("=" * 70)
    print()
    print(f"Алгоритм:         {algorithm}")
    print(f"Организация:      {info.holder}")
    print(f"Tier:             {info.tier}")
    print(f"Срок действия:    {info.days_left} дней (до {_format_dt(info.expires_at)})")
    print(f"Фичи:             {', '.join(sorted(info.features)) or '(по tier)'}")
    print(f"JTI:              {info.jti}")
    if info.instance_id:
        print(f"Instance ID:      {info.instance_id}")
        print(f"                  (привязана к этому серверу)")
    else:
        print(f"Instance ID:      не задан (лицензия работает на любом сервере)")
    if info.max_users is not None:
        print(f"Max users:        {info.max_users}")
    print()
    print("LICENSE_KEY:")
    print()
    print(token)
    print()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(token, encoding="utf-8")
        print(f"LICENSE_KEY сохранён в: {output_path}")
        print()

    # Запись в журнал
    _write_journal_entry(
        algorithm=algorithm,
        info=info,
        token=token,
        output_path=output_path,
    )
    print(f"Журнал выдачи: {JOURNAL_PATH}")
    print()

    # Инструкция для клиента
    print("=" * 70)
    print("ИНСТРУКЦИЯ ДЛЯ КЛИЕНТА")
    print("=" * 70)
    print()
    print("Передайте клиенту LICENSE_KEY (строку выше) и следующие шаги:")
    print()
    print("  1. Открыть .env в корне проекта")
    print("  2. Добавить/заменить:")
    print()
    print(f"     LICENSE_VERIFY=true")
    print(f"     LICENSE_KEY={token[:40]}...")
    print()
    if _is_asymmetric(algorithm):
        base = Path(args.master_key) if args.master_key else DEFAULT_KEYPAIR_BASENAME
        public_path = base.with_suffix(".public.pem")
        print(f"     LICENSE_PUBLIC_KEY=<содержимое {public_path}>")
        print()
        print(f"  ℹ️  Алгоритм {algorithm}: клиенту нужен ПУБЛИЧНЫЙ ключ.")
        print(f"     Он не может подписать лицензию — это безопасно.")
    else:
        print(f"     LICENSE_MASTER_SECRET=<мастер-ключ, из init-master-key>")
        print()
        print(f"  ⚠️  Алгоритм HS256: клиент получает тот же секрет, что и")
        print(f"     подпись. Технически он может выпустить свои лицензии.")
        print(f"     Для продакшена используйте --algorithm RS256.")
    print()
    print("  3. Перезапустить backend")
    print("  4. Проверить статус: curl http://localhost:8000/api/v1/license/info")
    print()

    return 0


# ==========================================
# КОМАНДА: inspect
# ==========================================

def cmd_inspect(args: argparse.Namespace) -> int:
    """Разбирает лицензию и показывает содержимое."""
    algorithm = args.algorithm

    # Читаем проверяемый ключ
    if args.key_file:
        path = Path(args.key_file)
        if not path.exists():
            print(f"ОШИБКА: файл не найден: {path}", file=sys.stderr)
            return 1
        key = path.read_text(encoding="utf-8").strip()
    elif args.key:
        key = args.key
    else:
        print("ОШИБКА: укажите --key или --key-file", file=sys.stderr)
        return 1

    # Читаем ключ для проверки подписи
    if algorithm in HS_ALGORITHMS:
        master_key_path = (
            Path(args.master_key) if args.master_key else DEFAULT_MASTER_KEY_PATH
        )
        verify_key = _read_master_key(master_key_path)
    elif algorithm in ASYMMETRIC_ALGORITHMS:
        base = (
            Path(args.master_key) if args.master_key else DEFAULT_KEYPAIR_BASENAME
        )
        public_path = base.with_suffix(".public.pem")
        verify_key = _read_public_key_pem(public_path)
    else:
        print(f"ОШИБКА: неподдерживаемый алгоритм: {algorithm}", file=sys.stderr)
        return 1

    try:
        info = verify_license(
            key=key,
            secret=verify_key,
            expected_instance_id=args.instance_id or None,
            algorithm=algorithm,
        )
    except Exception as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1

    # Сырой payload (без проверки подписи)
    try:
        raw = jwt.get_unverified_claims(key)
        header = jwt.get_unverified_header(key)
    except Exception:
        raw = {}
        header = {}

    # Вывод
    print("=" * 70)
    print("Разбор лицензии")
    print("=" * 70)
    print()
    print(f"Holder:           {info.holder}")
    print(f"Tier:             {info.tier}")
    print(f"Issuer:           {LICENSE_ISSUER}")
    print(f"Algorithm:        {header.get('alg', '?')}   (запрошен: {algorithm})")
    print(f"JTI:              {info.jti or '—'}")
    print()
    print(f"Issued at:        {_format_dt(info.issued_at)}")
    print(f"Expires at:       {_format_dt(info.expires_at)}")
    print(f"Days left:        {info.days_left}")
    print(f"Is expired:       {'ДА' if info.is_expired else 'нет'}")
    print()
    print(f"Instance ID:      {info.instance_id or '— (не привязана)'}")
    print(f"Max users:        {info.max_users if info.max_users is not None else '—'}")
    print()
    print(f"Features:         {', '.join(sorted(info.features)) or '(нет в токене)'}")
    print()

    print("Сырой payload (без проверки подписи):")
    for k, v in raw.items():
        print(f"   {k}: {v}")
    print()

    return 0


# ==========================================
# КОМАНДА: instance-id
# ==========================================

def cmd_instance_id(args: argparse.Namespace) -> int:
    """Показывает instance_id текущей машины."""
    instance_id = compute_instance_id()

    print("=" * 70)
    print("Instance ID текущей машины")
    print("=" * 70)
    print()
    print(instance_id)
    print()
    print("Используйте это значение для генерации привязанной лицензии:")
    print()
    print(f"    python {Path(__file__).name} generate \\")
    print(f"        --algorithm RS256 \\")
    print(f"        --org \"ООО Ромашка\" \\")
    print(f"        --tier enterprise \\")
    print(f"        --days 365 \\")
    print(f"        --instance-id {instance_id}")
    print()

    return 0


# ==========================================
# MAIN
# ==========================================

def _add_algorithm_arg(parser: argparse.ArgumentParser, default: str) -> None:
    """Добавляет общий аргумент --algorithm."""
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=list(SUPPORTED_ALGORITHMS),
        default=default,
        help=(
            "Алгоритм подписи. HS256 — dev (симметричный). "
            "RS256 — prod (асимметричный). ES256 — prod (короче ключи). "
            f"(default: {default})"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI для генерации лицензий APS Production Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--master-key",
        type=str,
        default=None,
        help=(
            f"Путь к файлу с ключом. Для HS256 — файл .hex "
            f"(default: {DEFAULT_MASTER_KEY_PATH}). Для RS256/ES256 — "
            f"базовое имя пары .private.pem / .public.pem "
            f"(default: {DEFAULT_KEYPAIR_BASENAME}). "
            f"ВАЖНО: этот аргумент идёт ДО подкоманды."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- init-master-key ----
    p_init = subparsers.add_parser(
        "init-master-key",
        help="Сгенерировать ключ подписи (HS256 — файл, RS/ES — пара)",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Перезаписать существующий ключ/пару",
    )
    _add_algorithm_arg(p_init, default=SIGNING_ALGORITHM_DEFAULT)
    p_init.add_argument(
        "--key-size",
        type=int,
        default=3072,
        choices=[2048, 3072, 4096],
        help="Размер RSA-ключа в битах (только для RS*, default: 3072)",
    )
    p_init.set_defaults(func=cmd_init_master_key)

    # ---- generate ----
    p_gen = subparsers.add_parser(
        "generate",
        help="Сгенерировать лицензию",
    )
    _add_algorithm_arg(p_gen, default=SIGNING_ALGORITHM_DEFAULT)
    p_gen.add_argument(
        "--org",
        type=str,
        required=True,
        help="Название организации-владельца",
    )
    p_gen.add_argument(
        "--tier",
        type=str,
        default="enterprise",
        choices=list(TIER_HIERARCHY),
        help="Уровень лицензии (default: enterprise)",
    )
    p_gen.add_argument(
        "--days",
        type=int,
        default=90,
        help="Срок действия в днях (default: 90)",
    )
    p_gen.add_argument(
        "--features",
        type=str,
        default=None,
        help=(
            "Список фич через запятую (default: по tier). "
            "Пример: --features audit_export,whatif"
        ),
    )
    p_gen.add_argument(
        "--instance-id",
        type=str,
        default=None,
        help=(
            "Привязать лицензию к конкретному instance_id "
            "(получить: команда instance-id)"
        ),
    )
    p_gen.add_argument(
        "--max-users",
        type=int,
        default=None,
        help="Ограничение на количество пользователей",
    )
    p_gen.add_argument(
        "--output",
        type=str,
        default=None,
        help="Сохранить LICENSE_KEY в файл (опционально)",
    )
    p_gen.set_defaults(func=cmd_generate)

    # ---- inspect ----
    p_insp = subparsers.add_parser(
        "inspect",
        help="Разобрать и показать содержимое лицензии",
    )
    _add_algorithm_arg(p_insp, default=SIGNING_ALGORITHM_DEFAULT)
    p_insp.add_argument(
        "--key",
        type=str,
        default=None,
        help="LICENSE_KEY (JWT-строка)",
    )
    p_insp.add_argument(
        "--key-file",
        type=str,
        default=None,
        help="Файл с LICENSE_KEY",
    )
    p_insp.add_argument(
        "--instance-id",
        type=str,
        default=None,
        help="Проверить совпадение instance_id",
    )
    p_insp.set_defaults(func=cmd_inspect)

    # ---- instance-id ----
    p_iid = subparsers.add_parser(
        "instance-id",
        help="Показать instance_id текущей машины",
    )
    p_iid.set_defaults(func=cmd_instance_id)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())