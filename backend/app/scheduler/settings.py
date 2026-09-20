# backend/app/scheduler/settings.py
"""
Единый реестр всех настроек планировщика.

Итерация 11: централизация настроек в модуле app_settings.
Итерация 12: категория optimization — веса multi-objective.

Все настройки описаны в SETTINGS_REGISTRY. UI и API читают
метаданные оттуда — это обеспечивает единый источник правды.

Использование:
    from app.scheduler.settings import get_setting, get_all_settings

    mode = await get_setting(session, org_id, "shift_mode", default="2x12")
    all_settings = await get_all_settings(session, org_id)
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.scheduler.settings")


# ==========================================
# Реестр настроек
# ==========================================

@dataclass
class SettingSpec:
    """Описание одной настройки."""
    key: str
    category: str
    label: str
    value_type: str              # "int" | "float" | "bool" | "str" | "json" | "select"
    default: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[List[Dict[str, Any]]] = None
    display_order: int = 0
    is_system: bool = False      # нельзя менять через UI


# ==========================================
# Все настройки проекта (единый реестр)
# ==========================================

SETTINGS_REGISTRY: List[SettingSpec] = [
    # ==========================================
    # ПЛАНИРОВАНИЕ
    # ==========================================
    SettingSpec(
        key="planning_start_date",
        category="planning",
        label="Дата начала планирования",
        value_type="str",
        default="2026-09-01T08:00:00",
        description="Дата и время старта планирования (МСК)",
        display_order=10,
    ),
    SettingSpec(
        key="horizon_hours",
        category="planning",
        label="Горизонт планирования (ч)",
        value_type="int",
        default=720,
        description="Сколько часов вперёд строить план",
        min_value=24,
        max_value=8760,
        display_order=20,
    ),
    SettingSpec(
        key="timeout_seconds",
        category="planning",
        label="Таймаут solver (сек)",
        value_type="int",
        default=600,
        description="Максимальное время работы CP-SAT solver",
        min_value=10,
        max_value=3600,
        display_order=30,
    ),
    SettingSpec(
        key="max_fill_percent",
        category="planning",
        label="Максимальная загрузка реактора",
        value_type="float",
        default=0.70,
        description="Доля от объёма реактора (0.0–1.0)",
        min_value=0.1,
        max_value=1.0,
        display_order=40,
    ),

    # ==========================================
    # РЕЖИМ СМЕН
    # ==========================================
    SettingSpec(
        key="shift_mode",
        category="shifts",
        label="Режим смен",
        value_type="select",
        default="2x12",
        description="Режим работы: одна 8ч, три 8ч или две 12ч",
        options=[
            {"value": "1x8", "label": "1 смена × 8 часов"},
            {"value": "3x8", "label": "3 смены × 8 часов"},
            {"value": "2x12", "label": "2 смены × 12 часов"},
        ],
        display_order=10,
    ),
    SettingSpec(
        key="shift_intervals",
        category="shifts",
        label="Интервалы смен",
        value_type="json",
        default=[
            {"start": "08:00", "end": "20:00"},
            {"start": "20:00", "end": "08:00"},
        ],
        description="Список интервалов смен в сутках (управляется режимом)",
        display_order=20,
        is_system=True,
    ),
    SettingSpec(
        key="shift_duration_hours",
        category="shifts",
        label="Длительность смены (ч)",
        value_type="int",
        default=12,
        description="Длительность одной смены (управляется режимом)",
        min_value=1,
        max_value=24,
        display_order=30,
        is_system=True,
    ),
    SettingSpec(
        key="work_start_time",
        category="shifts",
        label="Начало рабочего дня",
        value_type="str",
        default="08:00",
        description="Начало первого рабочего интервала",
        display_order=40,
    ),
    SettingSpec(
        key="work_end_time",
        category="shifts",
        label="Конец рабочего дня",
        value_type="str",
        default="20:00",
        description="Конец последнего рабочего интервала",
        display_order=50,
    ),

    # ==========================================
    # КАЛЕНДАРЬ
    # ==========================================
    SettingSpec(
        key="allow_weekend_work",
        category="calendar",
        label="Работа в выходные",
        value_type="bool",
        default=False,
        description="Разрешить работу в субботу и воскресенье",
        display_order=5,
    ),
    SettingSpec(
        key="max_task_hours_for_calendar",
        category="calendar",
        label="Макс. длительность задачи (ч)",
        value_type="float",
        default=12.0,
        description="Задачи длиннее — пропускаются в календарных ограничениях",
        min_value=1.0,
        max_value=48.0,
        display_order=10,
    ),
    SettingSpec(
        key="max_fill_part_hours",
        category="calendar",
        label="Макс. длительность части слива (ч)",
        value_type="float",
        default=8.0,
        description="Длинные LINE_FILL разбиваются на части по этой длительности",
        min_value=2.0,
        max_value=12.0,
        display_order=20,
    ),

    # ==========================================
    # ОХЛАЖДЕНИЕ
    # ==========================================
    SettingSpec(
        key="enable_cooling_degradation",
        category="cooling",
        label="Деградация охлаждения",
        value_type="bool",
        default=True,
        description="Замедлять охлаждение при 2+ параллельных реакторах",
        display_order=10,
    ),
    SettingSpec(
        key="cooling_degradation_factor",
        category="cooling",
        label="Коэффициент замедления",
        value_type="float",
        default=1.3,
        description="Во сколько раз замедлять охлаждение (например, 1.3)",
        min_value=1.0,
        max_value=3.0,
        display_order=20,
    ),
    SettingSpec(
        key="cooling_zone_capacity",
        category="cooling",
        label="Ёмкость зоны охлаждения",
        value_type="int",
        default=2,
        description="Сколько реакторов могут охлаждаться одновременно",
        min_value=1,
        max_value=10,
        display_order=30,
    ),

    # ==========================================
    # ЛАБОРАТОРИЯ
    # ==========================================
    SettingSpec(
        key="enable_lab_blocking",
        category="lab",
        label="Блокировка лабораторией",
        value_type="bool",
        default=True,
        description="Партия не участвует в планировании до одобрения",
        display_order=10,
    ),

    # ==========================================
    # МАТЕРИАЛЫ
    # ==========================================
    SettingSpec(
        key="enable_material_constraints",
        category="materials",
        label="Учёт остатков сырья",
        value_type="bool",
        default=True,
        description="Advisor проверяет дефицит сырья",
        display_order=10,
    ),

    # ==========================================
    # ЧЕСТНЫЙ ЗНАК
    # ==========================================
    SettingSpec(
        key="enable_cz_integration",
        category="cz",
        label="Интеграция с ЧЗ",
        value_type="bool",
        default=True,
        description="Приём сканов от камер ТС",
        display_order=10,
    ),
    SettingSpec(
        key="cz_completion_threshold",
        category="cz",
        label="Порог завершения ЧЗ",
        value_type="float",
        default=0.95,
        description="Доля от плана (0.0–1.0)",
        min_value=0.1,
        max_value=1.0,
        display_order=20,
    ),
    SettingSpec(
        key="cz_api_key",
        category="cz",
        label="API-ключ ЧЗ",
        value_type="str",
        default="dev-cz-api-key-change-in-production",
        description="Заголовок X-CZ-Api-Key для вебхука",
        display_order=30,
    ),
    SettingSpec(
        key="enable_cz_auto_close",
        category="cz",
        label="Автозакрытие при ЧЗ",
        value_type="bool",
        default=False,
        description="Закрывать задачу слива при завершении маркировки",
        display_order=40,
    ),

    # ==========================================
    # ПЕРСОНАЛ
    # ==========================================
    SettingSpec(
        key="enable_operator_pools",
        category="resources",
        label="Пулы операторов",
        value_type="bool",
        default=True,
        description="Учитывать ограничения по людям",
        display_order=10,
    ),
    SettingSpec(
        key="enable_manual_station",
        category="resources",
        label="Ручная станция",
        value_type="bool",
        default=True,
        description="Использовать LINE_3 (ручной слив)",
        display_order=20,
    ),

    # ==========================================
    # FEATURE-ФЛАГИ
    # ==========================================
    SettingSpec(
        key="enable_tank_routing",
        category="features",
        label="Маршруты через танк",
        value_type="bool",
        default=True,
        description="Реактор → танк → линия",
        display_order=10,
    ),
    SettingSpec(
        key="enable_shift_planning",
        category="features",
        label="Сменное планирование",
        value_type="bool",
        default=True,
        description="Разбивка по сменам и РМ мастера",
        display_order=20,
    ),
    SettingSpec(
        key="enable_rescheduling",
        category="features",
        label="Перепланирование",
        value_type="bool",
        default=True,
        description="Пересчёт при изменениях",
        display_order=30,
    ),
    SettingSpec(
        key="enable_advisor",
        category="features",
        label="Advisor (подсказки)",
        value_type="bool",
        default=True,
        description="Анализ плана и подсказки",
        display_order=40,
    ),

    # ==========================================
    # ОПТИМИЗАЦИЯ (Итерация 12)
    # ==========================================
    # Multi-objective: взвешенная сумма нормализованных компонентов.
    # Все веса в [0, 1]. Хотя бы один должен быть > 0.
    # По умолчанию: только makespan = 1.0 (обратная совместимость).
    # ==========================================
    SettingSpec(
        key="weight_makespan",
        category="optimization",
        label="Вес: Makespan",
        value_type="float",
        default=1.0,
        description="Приоритет минимизации общего времени плана (0 — отключено)",
        min_value=0.0,
        max_value=1.0,
        display_order=10,
    ),
    SettingSpec(
        key="weight_setup",
        category="optimization",
        label="Вес: Переналадки",
        value_type="float",
        default=0.0,
        description="Приоритет минимизации времени переналадок (setup)",
        min_value=0.0,
        max_value=1.0,
        display_order=20,
    ),
    SettingSpec(
        key="weight_underload",
        category="optimization",
        label="Вес: Недогрузка реакторов",
        value_type="float",
        default=0.0,
        description="Приоритет равномерной загрузки реакторов",
        min_value=0.0,
        max_value=1.0,
        display_order=30,
    ),
    SettingSpec(
        key="weight_cooling_slow",
        category="optimization",
        label="Вес: Замедленное охлаждение",
        value_type="float",
        default=0.0,
        description="Приоритет избегания замедленного охлаждения",
        min_value=0.0,
        max_value=1.0,
        display_order=40,
    ),
    SettingSpec(
        key="weight_tardiness",
        category="optimization",
        label="Вес: Просрочка заказов",
        value_type="float",
        default=0.0,
        description="Приоритет соблюдения due_date",
        min_value=0.0,
        max_value=1.0,
        display_order=50,
    ),
]


# Индекс по ключу для быстрого поиска
_SETTINGS_BY_KEY: Dict[str, SettingSpec] = {s.key: s for s in SETTINGS_REGISTRY}


# ==========================================
# Категории (для UI)
# ==========================================

CATEGORY_LABELS: Dict[str, str] = {
    "planning": "Планирование",
    "shifts": "Режим смен",
    "cooling": "Охлаждение",
    "calendar": "Календарь",
    "lab": "Лаборатория",
    "materials": "Материалы",
    "cz": "Честный Знак",
    "resources": "Персонал",
    "features": "Feature-флаги",
    "optimization": "Оптимизация",       # Итерация 12
}

CATEGORY_ORDER: List[str] = [
    "planning",
    "shifts",
    "cooling",
    "calendar",
    "lab",
    "materials",
    "cz",
    "resources",
    "features",
    "optimization",                       # Итерация 12
]


# ==========================================
# API модуля
# ==========================================

def _parse_value(raw: Any, value_type: Optional[str] = None) -> Any:
    """
    Парсит JSONB-значение из БД в Python-тип.

    Если value_type задан — приводит к нему.
    """
    if raw is None:
        return None

    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw

    if isinstance(raw, str):
        stripped = raw.strip()

        if value_type == "bool" or stripped.lower() in ("true", "false"):
            return stripped.lower() == "true"

        if value_type == "int":
            try:
                return int(float(stripped))
            except (ValueError, TypeError):
                pass

        if value_type == "float":
            try:
                return float(stripped)
            except (ValueError, TypeError):
                pass

        if stripped.startswith('"') and stripped.endswith('"'):
            return stripped[1:-1]

        if stripped.startswith('[') or stripped.startswith('{'):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # Попытка распарсить число
        try:
            if "." in stripped:
                return float(stripped)
            return int(stripped)
        except (ValueError, TypeError):
            return stripped

    if isinstance(raw, (list, dict)):
        return raw

    return raw


async def get_setting(
        session: AsyncSession,
        org_id: UUID,
        key: str,
        default: Any = None,
) -> Any:
    """
    Читает настройку из БД. Если не найдена — возвращает default
    из реестра или указанный default.
    """
    spec = _SETTINGS_BY_KEY.get(key)
    value_type = spec.value_type if spec else None

    result = await session.execute(
        text("""
            SELECT setting_value FROM app_settings
            WHERE organization_id = :org_id AND setting_key = :key
        """),
        {"org_id": org_id, "key": key},
    )
    row = result.fetchone()

    if row is not None:
        return _parse_value(row.setting_value, value_type)

    # Fallback — из реестра
    if spec is not None:
        return spec.default

    return default


async def get_all_settings(
        session: AsyncSession,
        org_id: UUID,
) -> Dict[str, Any]:
    """
    Возвращает все настройки организации в виде словаря {key: value}.
    Недостающие заполняются значениями по умолчанию из реестра.
    """
    result = await session.execute(
        text("""
            SELECT setting_key, setting_value FROM app_settings
            WHERE organization_id = :org_id
        """),
        {"org_id": org_id},
    )
    db_settings = {}
    for row in result.fetchall():
        spec = _SETTINGS_BY_KEY.get(row.setting_key)
        vt = spec.value_type if spec else None
        db_settings[row.setting_key] = _parse_value(row.setting_value, vt)

    # Добавляем значения по умолчанию
    for spec in SETTINGS_REGISTRY:
        if spec.key not in db_settings:
            db_settings[spec.key] = spec.default

    return db_settings


async def get_category_settings(
        session: AsyncSession,
        org_id: UUID,
        category: str,
) -> Dict[str, Any]:
    """Возвращает настройки одной категории."""
    result = await session.execute(
        text("""
            SELECT setting_key, setting_value FROM app_settings
            WHERE organization_id = :org_id AND category = :category
        """),
        {"org_id": org_id, "category": category},
    )

    db_settings = {}
    for row in result.fetchall():
        spec = _SETTINGS_BY_KEY.get(row.setting_key)
        vt = spec.value_type if spec else None
        db_settings[row.setting_key] = _parse_value(row.setting_value, vt)

    # Добавляем недостающие из реестра
    for spec in SETTINGS_REGISTRY:
        if spec.category == category and spec.key not in db_settings:
            db_settings[spec.key] = spec.default

    return db_settings


def get_settings_schema() -> List[Dict[str, Any]]:
    """
    Возвращает полный реестр настроек для UI.
    Используется эндпоинтом GET /api/v1/settings/schema.
    """
    return [
        {
            "key": s.key,
            "category": s.category,
            "category_label": CATEGORY_LABELS.get(s.category, s.category),
            "label": s.label,
            "value_type": s.value_type,
            "default": s.default,
            "description": s.description,
            "min_value": s.min_value,
            "max_value": s.max_value,
            "options": s.options,
            "display_order": s.display_order,
            "is_system": s.is_system,
        }
        for s in SETTINGS_REGISTRY
    ]


def get_categories() -> List[Dict[str, str]]:
    """Возвращает список категорий для UI."""
    return [
        {"key": cat, "label": CATEGORY_LABELS.get(cat, cat)}
        for cat in CATEGORY_ORDER
    ]


def validate_setting(key: str, value: Any) -> Any:
    """
    Валидирует значение настройки по реестру.

    Raises:
        ValueError: если значение не проходит валидацию.
    """
    spec = _SETTINGS_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Неизвестная настройка: {key}")

    if spec.is_system:
        raise ValueError(
            f"Настройка '{key}' системная — изменить нельзя через UI"
        )

    # Приведение типа
    if spec.value_type == "int":
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"'{key}' должно быть целым числом")
        if spec.min_value is not None and value < spec.min_value:
            raise ValueError(f"'{key}' должно быть >= {spec.min_value}")
        if spec.max_value is not None and value > spec.max_value:
            raise ValueError(f"'{key}' должно быть <= {spec.max_value}")

    elif spec.value_type == "float":
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"'{key}' должно быть числом")
        if spec.min_value is not None and value < spec.min_value:
            raise ValueError(f"'{key}' должно быть >= {spec.min_value}")
        if spec.max_value is not None and value > spec.max_value:
            raise ValueError(f"'{key}' должно быть <= {spec.max_value}")

    elif spec.value_type == "bool":
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "1", "yes", "on")
        else:
            value = bool(value)

    elif spec.value_type == "select":
        if spec.options:
            valid = [o["value"] for o in spec.options]
            if value not in valid:
                raise ValueError(
                    f"'{key}' должно быть одним из: {valid}"
                )

    elif spec.value_type in ("str", "json"):
        # Принимаем как есть
        pass

    return value


async def update_setting(
        session: AsyncSession,
        org_id: UUID,
        key: str,
        value: Any,
) -> Any:
    """
    Обновляет одну настройку. Возвращает новое значение.
    """
    value = validate_setting(key, value)

    # Сериализация в JSONB
    if isinstance(value, str):
        serialized = json.dumps(value)
    elif isinstance(value, bool):
        serialized = "true" if value else "false"
    elif isinstance(value, (int, float)):
        serialized = str(value)
    else:
        serialized = json.dumps(value)

    await session.execute(
        text("""
            INSERT INTO app_settings
                (organization_id, category, setting_key, setting_value,
                 value_type, label, updated_at)
            VALUES
                (:org_id, :category, :key, CAST(:value AS jsonb),
                 :vtype, :label, NOW())
            ON CONFLICT (organization_id, setting_key) DO UPDATE
                SET setting_value = EXCLUDED.setting_value,
                    updated_at = NOW()
        """),
        {
            "org_id": org_id,
            "category": _SETTINGS_BY_KEY[key].category,
            "key": key,
            "value": serialized,
            "vtype": _SETTINGS_BY_KEY[key].value_type,
            "label": _SETTINGS_BY_KEY[key].label,
        },
    )
    await session.commit()

    return value


async def update_settings_bulk(
        session: AsyncSession,
        org_id: UUID,
        updates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Обновляет несколько настроек за один раз.

    Returns:
        Словарь {key: new_value} для успешно обновлённых.
    """
    result = {}
    errors = {}

    for key, value in updates.items():
        try:
            result[key] = await update_setting(session, org_id, key, value)
        except ValueError as e:
            errors[key] = str(e)
            logger.warning(f"Ошибка обновления '{key}': {e}")

    if errors:
        raise ValueError(f"Ошибки валидации: {errors}")

    return result