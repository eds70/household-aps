# backend/app/scheduler/feature_flags.py
"""
Feature-флаги планировщика.

Читает флаги из app_settings (JSONB).
Позволяет включать/выключать функциональность поэтапно
без изменения кода и пересборки.

Итерация 5: enable_lab_blocking.
Итерация 6: enable_operator_pools, enable_manual_station.
Итерация 7: enable_cooling_degradation.
Итерация 8: enable_cz_integration.
Итерация 11 (Шаг 5): переход на app_settings.
"""

from typing import Dict, Any, Optional


class FeatureFlags:
    """
    Обёртка над app_settings для удобного доступа к флагам.

    Использование:
        flags = FeatureFlags(app_settings)
        if flags.enable_tank_routing:
            ...
    """

    # Значения по умолчанию (если в БД нет ключа)
    DEFAULTS: Dict[str, Any] = {
        "enable_tank_routing": False,
        "enable_shift_planning": False,
        "enable_rescheduling": False,
        "enable_material_constraints": False,
        "enable_advisor": True,
        "enable_lab_blocking": False,
        "enable_operator_pools": False,
        "enable_manual_station": False,
        "enable_cooling_degradation": False,
        "enable_cz_integration": False,
    }

    BOOL_KEYS = {
        "enable_tank_routing",
        "enable_shift_planning",
        "enable_rescheduling",
        "enable_material_constraints",
        "enable_advisor",
        "enable_lab_blocking",
        "enable_operator_pools",
        "enable_manual_station",
        "enable_cooling_degradation",
        "enable_cz_integration",
    }

    def __init__(self, app_settings: Optional[Dict[str, Any]] = None):
        """
        Args:
            app_settings: словарь {setting_key: setting_value} из app_settings.
        """
        self._settings = app_settings or {}
        self._flags: Dict[str, Any] = {}
        self._parse()

    def _parse(self) -> None:
        """Разобрать настройки в удобный dict."""
        for key, default in self.DEFAULTS.items():
            raw = self._settings.get(key, default)
            if key in self.BOOL_KEYS:
                self._flags[key] = self._coerce_bool(raw)
            else:
                self._flags[key] = raw

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        """Привести значение из JSONB к bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение флага по ключу."""
        return self._flags.get(key, default)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Получить числовое значение настройки."""
        raw = self._settings.get(key, default)
        try:
            if isinstance(raw, str):
                return float(raw.strip().strip('"').strip("'"))
            return float(raw)
        except (ValueError, TypeError):
            return default

    def __getattr__(self, item: str) -> Any:
        """Позволяет обращаться к флагам как к атрибутам."""
        if item.startswith("_"):
            raise AttributeError(item)
        if item in self._flags:
            return self._flags[item]
        raise AttributeError(f"FeatureFlag '{item}' not found")

    def as_dict(self) -> Dict[str, Any]:
        """Вернуть все флаги как dict."""
        return dict(self._flags)

    def __repr__(self) -> str:
        enabled = [k for k, v in self._flags.items() if v is True]
        return f"FeatureFlags(enabled={enabled})"