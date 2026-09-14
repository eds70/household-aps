from dataclasses import dataclass
from typing import Dict, Any
from decimal import Decimal

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
        base = ctx.operation["base_duration_mins"]
        volume = float(ctx.batch["volume_kg"])
        speed = float(ctx.equipment.get("speed_coeff", 1.0))
        return max(10, int(base * (volume / 5000) / speed))

class HeatingStrategy(BaseDurationStrategy):
    name = "heating"
    BOILER_VOLUME = 2000
    def calculate(self, ctx: DurationContext) -> int:
        base = ctx.operation["base_duration_mins"]
        volume = float(ctx.batch["volume_kg"])
        cycles = (volume + self.BOILER_VOLUME - 1) // self.BOILER_VOLUME
        return base * int(cycles)

class MixingStrategy(BaseDurationStrategy):
    name = "mixing"
    MIXER_COEFFS = {"standard": 1.0, "high_speed": 0.7, "low_speed": 1.3}
    def calculate(self, ctx: DurationContext) -> int:
        base = ctx.operation["base_duration_mins"]
        mixer = ctx.equipment.get("mixer_type", "standard")
        mixer_coeff = self.MIXER_COEFFS.get(mixer, 1.0)
        viscosity = float(ctx.product.get("viscosity_coeff", 1.0))
        return int(base * mixer_coeff * viscosity)

class CoolingStrategy(BaseDurationStrategy):
    name = "cooling"
    def calculate(self, ctx: DurationContext) -> int:
        base = ctx.operation["base_duration_mins"]
        volume = float(ctx.batch["volume_kg"])
        viscosity = float(ctx.product.get("viscosity_coeff", 1.0))
        return int(base * (volume / 5000) * viscosity)

class PumpingStrategy(BaseDurationStrategy):
    name = "pumping"
    def calculate(self, ctx: DurationContext) -> int:
        base = ctx.operation["base_duration_mins"]
        volume = float(ctx.batch["volume_kg"])
        viscosity = float(ctx.product.get("viscosity_coeff", 1.0))
        return int(base * (volume / 5000) * viscosity)

class WashingStrategy(BaseDurationStrategy):
    name = "washing"
    def calculate(self, ctx: DurationContext) -> int:
        return ctx.operation["base_duration_mins"]

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
