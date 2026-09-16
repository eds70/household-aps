# backend/app/scheduler/feature_flags.py
"""
Feature-флаги планировщика.

Читает флаги из organization_settings (JSONB).
Позволяет включать/выключать функциональность поэтапно
без изменения кода и пересборки.
"""

from typing import Dict, Any, Optional


class FeatureFlags:
    """
    Обёртка над organization_settings для удобного доступа к флагам.

    Использование:
        flags = FeatureFlags(org_settings)
        if flags.tank_routing:
            # включить цепочки через танк
    """

    # Значения по умолчанию (если в БД нет ключа)
    DEFAULTS: Dict[str, Any] = {
        "enable_tank_routing": False,
        "enable_shift_planning": False,
        "enable_rescheduling": False,
        "enable_material_constraints": False,
        "enable_advisor": True,
        "enable_lab_blocking": False,
        "enable_cooling_degradation": False,
        "enable_operator_pools": False,
        "enable_manual_station": False,
        "enable_cz_integration": False,
    }

    # Ключи, которые в БД хранятся как bool
    BOOL_KEYS = {
        "enable_tank_routing",
        "enable_shift_planning",
        "enable_rescheduling",
        "enable_material_constraints",
        "enable_advisor",
        "enable_lab_blocking",
        "enable_cooling_degradation",
        "enable_operator_pools",
        "enable_manual_station",
        "enable_cz_integration",
    }

    def __init__(self, org_settings: Optional[Dict[str, Any]] = None):
        """
        Args:
            org_settings: словарь {setting_key: setting_value} из organization_settings.
                          setting_value может быть JSONB (list/dict/str/bool/int).
        """
        self._settings = org_settings or {}
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

    def __getattr__(self, item: str) -> Any:
        """
        Позволяет обращаться к флагам как к атрибутам:
            flags.enable_tank_routing
            flags.enable_advisor
        """
        # Убираем префикс 'enable_' для краткости? Нет — оставляем как есть,
        # чтобы совпадало с ключами в БД.
        if item.startswith("_"):
            raise AttributeError(item)
        if item in self._flags:
            return self._flags[item]
        raise AttributeError(f"FeatureFlag '{item}' not found")

    def as_dict(self) -> Dict[str, Any]:
        """Вернуть все флаги как dict (для логирования)."""
        return dict(self._flags)

    def __repr__(self) -> str:
        enabled = [k for k, v in self._flags.items() if v is True]
        return f"FeatureFlags(enabled={enabled})"


# ==========================================
# Удобные свойства для часто используемых флагов
# ==========================================
# Ниже — не код, а пример использования:
#
#   flags = FeatureFlags(org_settings)
#   if flags.enable_tank_routing:
#       ...
#   if flags.enable_advisor:
#       ...