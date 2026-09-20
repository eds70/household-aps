# backend/app/scheduler/optimization.py
"""
Multi-objective оптимизация для планировщика.

Итерация 12.

Модуль реализует взвешенную сумму пяти компонентов:
  1. makespan        — общее время плана (мин)
  2. setup_sum       — сумма переналадок (мин)
  3. underload_sum   — сумма недогрузки реакторов (кг)
  4. cooling_slow    — число замедленных охлаждений (шт)
  5. tardiness_sum   — сумма просрочек due_date (мин)

Каждый компонент нормируется в [0, 1] через деление на свой максимум:
  - makespan    / horizon_minutes
  - setup_sum   / horizon_minutes
  - underload   / total_max_fill_kg
  - cooling     / total_cooling_count
  - tardiness   / (num_batches * horizon_minutes)

Веса в [0, 1] — задаются пользователем в app_settings.
По умолчанию: только makespan = 1.0 (обратная совместимость).

Для integer-модели CP-SAT используется fixed-point масштабирование
(PRECISION = 10000).

Использование:
    from app.scheduler.optimization import (
        OptimizationWeights,
        build_multi_objective,
    )

    weights = OptimizationWeights.from_settings(org_settings)
    weights.validate()
    build_multi_objective(
        model=model,
        weights=weights,
        makespan_var=makespan,
        horizon_minutes=horizon,
        setup_sum_var=setup_sum,
        underload_sum_var=underload_sum,
        cooling_slow_count_var=cooling_slow,
        tardiness_sum_var=tardiness_sum,
        total_max_fill_kg=total_max_fill_kg,
        total_cooling_count=total_cooling_count,
        num_batches=num_batches,
    )
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ortools.sat.python import cp_model

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# КОНСТАНТЫ
# ==========================================

# Точность fixed-point: 4 знака после запятой.
# 10000 — достаточно для нормализованных весов [0, 1].
# OR-Tools использует int64, поэтому большие значения могут
# переполниться. 10000 — безопасный компромисс.
PRECISION = 10000


# ==========================================
# DATACLASS: ВЕСА
# ==========================================

@dataclass
class OptimizationWeights:
    """
    Веса компонентов целевой функции.

    Все веса в диапазоне [0, 1]:
      - 0.0 — компонент отключён.
      - 1.0 — максимальный приоритет.
      - 0.5 — половина приоритета.

    По умолчанию: только makespan = 1.0, остальные = 0.0
    (обратная совместимость с Итерацией 0-11).
    """
    weight_makespan: float = 1.0
    weight_setup: float = 0.0
    weight_underload: float = 0.0
    weight_cooling_slow: float = 0.0
    weight_tardiness: float = 0.0

    @classmethod
    def from_settings(cls, settings: Dict[str, Any]) -> "OptimizationWeights":
        """
        Читает веса из app_settings.

        Args:
            settings: словарь {setting_key: setting_value} из app_settings.

        Returns:
            OptimizationWeights с прочитанными значениями.
            Отсутствующие ключи → дефолты из dataclass.
        """
        def _read(key: str, default: float) -> float:
            raw = settings.get(key, default)
            if raw is None:
                return default
            try:
                if isinstance(raw, str):
                    return float(raw.strip().strip('"').strip("'"))
                return float(raw)
            except (ValueError, TypeError):
                return default

        return cls(
            weight_makespan=_read("weight_makespan", 1.0),
            weight_setup=_read("weight_setup", 0.0),
            weight_underload=_read("weight_underload", 0.0),
            weight_cooling_slow=_read("weight_cooling_slow", 0.0),
            weight_tardiness=_read("weight_tardiness", 0.0),
        )

    def validate(self) -> None:
        """
        Проверяет, что веса в [0, 1] и хотя бы один > 0.

        Raises:
            ValueError: если вес вне [0, 1] или все веса = 0.
        """
        items = [
            ("weight_makespan", self.weight_makespan),
            ("weight_setup", self.weight_setup),
            ("weight_underload", self.weight_underload),
            ("weight_cooling_slow", self.weight_cooling_slow),
            ("weight_tardiness", self.weight_tardiness),
        ]

        for name, value in items:
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} должен быть в [0, 1], получено: {value}"
                )

        if all(v == 0.0 for _, v in items):
            raise ValueError("Хотя бы один вес должен быть > 0")

    def to_int(self) -> Dict[str, int]:
        """
        Приводит веса к fixed-point int (для CP-SAT).

        Returns:
            {компонент: вес * PRECISION}
        """
        return {
            "makespan": int(round(self.weight_makespan * PRECISION)),
            "setup": int(round(self.weight_setup * PRECISION)),
            "underload": int(round(self.weight_underload * PRECISION)),
            "cooling_slow": int(round(self.weight_cooling_slow * PRECISION)),
            "tardiness": int(round(self.weight_tardiness * PRECISION)),
        }

    def as_dict(self) -> Dict[str, float]:
        """Возвращает веса как dict (для логирования)."""
        return {
            "makespan": self.weight_makespan,
            "setup": self.weight_setup,
            "underload": self.weight_underload,
            "cooling_slow": self.weight_cooling_slow,
            "tardiness": self.weight_tardiness,
        }

    def is_single_objective(self) -> bool:
        """True, если только makespan > 0 (обратная совместимость)."""
        return (
                self.weight_makespan > 0
                and self.weight_setup == 0
                and self.weight_underload == 0
                and self.weight_cooling_slow == 0
                and self.weight_tardiness == 0
        )

    def __repr__(self) -> str:
        active = [
            f"{k}={v}" for k, v in self.as_dict().items() if v > 0
        ]
        return f"OptimizationWeights({', '.join(active) if active else 'none'})"


# ==========================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: НОРМАЛИЗАЦИЯ
# ==========================================

def _normalize_int(
        model: cp_model.CpModel,
        value_var: cp_model.IntVar,
        max_value: int,
        name: str,
) -> cp_model.IntVar:
    """
    Нормирует IntVar в [0, PRECISION] через деление на max_value.

    Формула: normalized = (value * PRECISION) // max_value.

    Args:
        model: CpModel.
        value_var: исходная переменная.
        max_value: максимум (должен быть > 0).
        name: имя для новой переменной.

    Returns:
        IntVar в [0, PRECISION].
    """
    if max_value <= 0:
        # Fallback: возвращаем 0, чтобы не делить на ноль.
        # Это значит, что компонент не вносит вклад в целевую функцию.
        zero = model.NewConstant(0)
        return zero

    normalized = model.NewIntVar(0, PRECISION, name)
    model.AddDivisionEquality(
        normalized,
        value_var * PRECISION,
        max_value,
        )
    return normalized


# ==========================================
# ГЛАВНАЯ ФУНКЦИЯ: ПОСТРОЕНИЕ ЦЕЛЕВОЙ
# ==========================================

def build_multi_objective(
        model: cp_model.CpModel,
        weights: OptimizationWeights,
        makespan_var: cp_model.IntVar,
        horizon_minutes: int,
        setup_sum_var: Optional[cp_model.IntVar] = None,
        underload_sum_var: Optional[cp_model.IntVar] = None,
        cooling_slow_count_var: Optional[cp_model.IntVar] = None,
        tardiness_sum_var: Optional[cp_model.IntVar] = None,
        total_max_fill_kg: int = 0,
        total_cooling_count: int = 0,
        num_batches: int = 0,
) -> None:
    """
    Строит взвешенную целевую функцию с нормализацией.

    Каждый активный компонент:
      1. Нормируется в [0, PRECISION] через деление на свой максимум.
      2. Умножается на вес (int).
      3. Суммируется с остальными.

    Результат передаётся в `model.Minimize(...)`.

    Args:
        model: CpModel.
        weights: веса компонентов.
        makespan_var: переменная makespan (обязательна).
        horizon_minutes: горизонт (для нормализации makespan и setup).
        setup_sum_var: сумма setup (опционально).
        underload_sum_var: сумма недогрузки (опционально).
        cooling_slow_count_var: число замедленных охлаждений (опционально).
        tardiness_sum_var: сумма просрочек (опционально).
        total_max_fill_kg: сумма max_fill_kg по всем партиям (для underload).
        total_cooling_count: общее число cooling-задач (для cooling).
        num_batches: число партий (для tardiness).

    Note:
        Если передан вес > 0, но соответствующая переменная = None,
        компонент игнорируется (с предупреждением в лог).
    """
    w = weights.to_int()
    terms = []
    active_components = []

    # ==========================================
    # 1. Makespan
    # ==========================================
    if w["makespan"] > 0:
        makespan_norm = _normalize_int(
            model=model,
            value_var=makespan_var,
            max_value=horizon_minutes,
            name="obj_makespan_norm",
        )
        terms.append(w["makespan"] * makespan_norm)
        active_components.append("makespan")

    # ==========================================
    # 2. Setup
    # ==========================================
    if w["setup"] > 0:
        if setup_sum_var is not None:
            setup_norm = _normalize_int(
                model=model,
                value_var=setup_sum_var,
                max_value=horizon_minutes,
                name="obj_setup_norm",
            )
            terms.append(w["setup"] * setup_norm)
            active_components.append("setup")
        else:
            log_with_context(
                logger, logging.WARNING,
                "weight_setup > 0, но setup_sum_var не передан — "
                "компонент setup игнорируется",
                stage="multi_objective",
            )

    # ==========================================
    # 3. Underload
    # ==========================================
    if w["underload"] > 0:
        if underload_sum_var is not None and total_max_fill_kg > 0:
            underload_norm = _normalize_int(
                model=model,
                value_var=underload_sum_var,
                max_value=total_max_fill_kg,
                name="obj_underload_norm",
            )
            terms.append(w["underload"] * underload_norm)
            active_components.append("underload")
        else:
            log_with_context(
                logger, logging.WARNING,
                f"weight_underload > 0, но "
                f"underload_sum_var={underload_sum_var} или "
                f"total_max_fill_kg={total_max_fill_kg} — "
                f"компонент underload игнорируется",
                stage="multi_objective",
            )

    # ==========================================
    # 4. Cooling slow
    # ==========================================
    if w["cooling_slow"] > 0:
        if cooling_slow_count_var is not None and total_cooling_count > 0:
            cooling_norm = _normalize_int(
                model=model,
                value_var=cooling_slow_count_var,
                max_value=total_cooling_count,
                name="obj_cooling_norm",
            )
            terms.append(w["cooling_slow"] * cooling_norm)
            active_components.append("cooling_slow")
        else:
            log_with_context(
                logger, logging.WARNING,
                f"weight_cooling_slow > 0, но "
                f"cooling_slow_count_var={cooling_slow_count_var} или "
                f"total_cooling_count={total_cooling_count} — "
                f"компонент cooling_slow игнорируется",
                stage="multi_objective",
            )

    # ==========================================
    # 5. Tardiness
    # ==========================================
    if w["tardiness"] > 0:
        max_tardiness = num_batches * horizon_minutes
        if tardiness_sum_var is not None and max_tardiness > 0:
            tardiness_norm = _normalize_int(
                model=model,
                value_var=tardiness_sum_var,
                max_value=max_tardiness,
                name="obj_tardiness_norm",
            )
            terms.append(w["tardiness"] * tardiness_norm)
            active_components.append("tardiness")
        else:
            log_with_context(
                logger, logging.WARNING,
                f"weight_tardiness > 0, но "
                f"tardiness_sum_var={tardiness_sum_var} или "
                f"num_batches={num_batches} — "
                f"компонент tardiness игнорируется",
                stage="multi_objective",
            )

    # ==========================================
    # Итоговая целевая функция
    # ==========================================
    if not terms:
        # Fallback: минимизируем makespan напрямую.
        log_with_context(
            logger, logging.WARNING,
            "Все компоненты целевой функции отключены — "
            "fallback на single-objective makespan",
            stage="multi_objective",
        )
        model.Minimize(makespan_var)
        return

    if len(terms) == 1:
        model.Minimize(terms[0])
    else:
        model.Minimize(sum(terms))

    log_with_context(
        logger, logging.INFO,
        f"Multi-objective: активные компоненты = {active_components}, "
        f"веса = {weights.as_dict()}",
        stage="multi_objective",
    )


# ==========================================
# УТИЛИТЫ ДЛЯ АККУМУЛЯТОРОВ
# ==========================================

def build_setup_accumulator(
        model: cp_model.CpModel,
        setup_pairs: list,
        horizon_minutes: int,
) -> cp_model.IntVar:
    """
    Создаёт переменную setup_sum = Σ setup_time_i_j * i_before_j.

    Args:
        model: CpModel.
        setup_pairs: список троек (i_before_j_var, setup_minutes, pair_name).
        horizon_minutes: горизонт (для верхней границы IntVar).

    Returns:
        IntVar с суммой setup-минут.
    """
    setup_sum = model.NewIntVar(0, horizon_minutes, "setup_sum")
    terms = []

    for i_before_j, setup_mins, _ in setup_pairs:
        # Если i_before_j = 1 → вклад = setup_mins, иначе 0.
        term = model.NewIntVar(0, setup_mins, f"setup_term_{i_before_j.Name()}")
        model.Add(term == setup_mins).OnlyEnforceIf(i_before_j)
        model.Add(term == 0).OnlyEnforceIf(i_before_j.Not())
        terms.append(term)

    if terms:
        model.Add(setup_sum == sum(terms))
    else:
        model.Add(setup_sum == 0)

    return setup_sum


def build_underload_accumulator(
        model: cp_model.CpModel,
        batches: list,
        equipment_map: dict,
        max_fill_percent: float,
) -> tuple:
    """
    Создаёт underload_sum = Σ max(0, max_fill_kg - actual_volume_kg).

    Args:
        model: CpModel.
        batches: список партий (dict с полями id, volume_kg, assigned_equipment_id).
        equipment_map: {equipment_id: {volume_kg, ...}}.
        max_fill_percent: доля (например, 0.70).

    Returns:
        (underload_sum_var, total_max_fill_kg).
    """
    terms = []
    total_max_fill_kg = 0.0

    for batch in batches:
        eq_id = str(batch.get("assigned_equipment_id") or "")
        if not eq_id:
            continue

        eq = equipment_map.get(eq_id, {})
        reactor_volume = float(eq.get("volume_kg") or 0)
        if reactor_volume <= 0:
            continue

        max_fill_kg = reactor_volume * max_fill_percent
        volume_kg = float(batch.get("volume_kg") or 0)
        underload_kg = max(0.0, max_fill_kg - volume_kg)

        total_max_fill_kg += max_fill_kg

        if underload_kg > 0:
            # Партия фиксирована по объёму — это константа.
            # Но можно сделать переменной, если объём станет переменным
            # в будущих итерациях.
            underload_const = int(round(underload_kg))
            term = model.NewConstant(underload_const)
            terms.append(term)

    # Верхняя граница: total_max_fill_kg (все реакторы пустые).
    max_total = int(round(total_max_fill_kg))
    underload_sum = model.NewIntVar(0, max(max_total, 0), "underload_sum")

    if terms:
        model.Add(underload_sum == sum(terms))
    else:
        model.Add(underload_sum == 0)

    return underload_sum, max_total


def build_cooling_slow_accumulator(
        model: cp_model.CpModel,
        cooling_tasks: list,
) -> tuple:
    """
    Создаёт cooling_slow_count = Σ b_slow_i.

    Args:
        model: CpModel.
        cooling_tasks: список cooling-задач с полем b_slow (BoolVar).

    Returns:
        (cooling_slow_count_var, total_cooling_count).
    """
    total_cooling_count = len(cooling_tasks)
    cooling_slow_count = model.NewIntVar(
        0, total_cooling_count, "cooling_slow_count"
    )

    b_slow_vars = [
        t.get("b_slow") for t in cooling_tasks if t.get("b_slow") is not None
    ]

    if b_slow_vars:
        model.Add(cooling_slow_count == sum(b_slow_vars))
    else:
        model.Add(cooling_slow_count == 0)

    return cooling_slow_count, total_cooling_count


def build_tardiness_accumulator(
        model: cp_model.CpModel,
        batches: list,
        batch_end_vars: dict,
        horizon_minutes: int,
        t0=None,
) -> tuple:
    """
    Создаёт tardiness_sum = Σ max(0, batch_end - due_date).

    Args:
        model: CpModel.
        batches: список партий с полем due_date (datetime | None).
        batch_end_vars: {batch_id: IntVar} — время окончания партии.
        horizon_minutes: горизонт (для верхней границы).
        t0: базовое время (datetime).

    Returns:
        (tardiness_sum_var, max_tardiness).
    """
    terms = []
    num_batches = len(batches)

    for batch in batches:
        batch_id = str(batch.get("id") or "")
        due_date = batch.get("due_date")

        if not batch_id or due_date is None:
            continue

        batch_end_var = batch_end_vars.get(batch_id)
        if batch_end_var is None:
            continue

        # Преобразуем due_date в минуты от t0.
        if t0 is not None and hasattr(due_date, "timestamp"):
            due_minutes = int(
                (due_date.replace(tzinfo=None) - t0).total_seconds() / 60
            )
            due_minutes = max(0, due_minutes)
        else:
            continue

        # tardiness_i = max(0, batch_end - due_minutes)
        tardiness_i = model.NewIntVar(0, horizon_minutes, f"tardiness_{batch_id[:8]}")
        model.Add(tardiness_i >= batch_end_var - due_minutes)
        model.Add(tardiness_i >= 0)
        terms.append(tardiness_i)

    # Верхняя граница: num_batches * horizon (все опаздывают на весь горизонт).
    max_tardiness = num_batches * horizon_minutes
    tardiness_sum = model.NewIntVar(0, max_tardiness, "tardiness_sum")

    if terms:
        model.Add(tardiness_sum == sum(terms))
    else:
        model.Add(tardiness_sum == 0)

    return tardiness_sum, max_tardiness