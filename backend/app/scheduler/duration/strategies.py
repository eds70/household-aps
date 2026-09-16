# backend/app/scheduler/duration/strategies.py
"""
Стратегии расчёта длительности операций.

Итерация 1:
- Все числовые значения приводятся через _to_float() — избегаем Decimal / float
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, Union


Number = Union[int, float, Decimal]


def _to_float(value: Any, default: float = 0.0) -> float:
    """Безопасно приводит значение к float (работает с Decimal из asyncpg)."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class DurationContext:
    operation: Dict[str, Any]
    batch: Dict[str, Any]
    equipment: Dict[str, Any]
    product: Dict[str, Any]


class BaseDurationStrategy:
    name: str

    def calculate(self, ctx: DurationContext) -> int:
        raise NotImplementedError


class WaterLoadingStrategy(BaseDurationStrategy):
    name = "water_loading"

    def calculate(self, ctx: DurationContext) -> int:
        base = _to_float(ctx.operation.get("base_duration_mins"), 60.0)
        volume = _to_float(ctx.batch.get("volume_kg"), 0.0)
        speed = _to_float(ctx.equipment.get("speed_coeff"), 1.0) or 1.0
        return max(10, int(base * (volume / 5000.0) / speed))


class HeatingStrategy(BaseDurationStrategy):
    name = "heating"
    BOILER_VOLUME = 2000

    def calculate(self, ctx: DurationContext) -> int:
        base = _to_float(ctx.operation.get("base_duration_mins"), 120.0)
        volume = _to_float(ctx.batch.get("volume_kg"), 0.0)
        cycles = max(1, int((volume + self.BOILER_VOLUME - 1) // self.BOILER_VOLUME))
        return int(base * cycles)


class MixingStrategy(BaseDurationStrategy):
    name = "mixing"
    MIXER_COEFFS = {"standard": 1.0, "high_speed": 0.7, "low_speed": 1.3}

    def calculate(self, ctx: DurationContext) -> int:
        base = _to_float(ctx.operation.get("base_duration_mins"), 60.0)
        mixer = ctx.equipment.get("mixer_type") or "standard"
        mixer_coeff = self.MIXER_COEFFS.get(mixer, 1.0)
        viscosity = _to_float(ctx.product.get("viscosity_coeff"), 1.0)
        return int(base * mixer_coeff * viscosity)


class CoolingStrategy(BaseDurationStrategy):
    name = "cooling"

    def calculate(self, ctx: DurationContext) -> int:
        base = _to_float(ctx.operation.get("base_duration_mins"), 120.0)
        volume = _to_float(ctx.batch.get("volume_kg"), 0.0)
        viscosity = _to_float(ctx.product.get("viscosity_coeff"), 1.0)
        return int(base * (volume / 5000.0) * viscosity)


class PumpingStrategy(BaseDurationStrategy):
    name = "pumping"

    def calculate(self, ctx: DurationContext) -> int:
        base = _to_float(ctx.operation.get("base_duration_mins"), 60.0)
        volume = _to_float(ctx.batch.get("volume_kg"), 0.0)
        viscosity = _to_float(ctx.product.get("viscosity_coeff"), 1.0)
        return int(base * (volume / 5000.0) * viscosity)


class WashingStrategy(BaseDurationStrategy):
    name = "washing"

    def calculate(self, ctx: DurationContext) -> int:
        return int(_to_float(ctx.operation.get("base_duration_mins"), 90.0))


STRATEGIES = {
    "water_loading": WaterLoadingStrategy(),
    "heating": HeatingStrategy(),
    "mixing": MixingStrategy(),
    "cooling": CoolingStrategy(),
    "pumping": PumpingStrategy(),
    "washing": WashingStrategy(),
}


def get_strategy(name: str) -> BaseDurationStrategy:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {name}")
    return STRATEGIES[name]