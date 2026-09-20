# backend/app/api/v1/whatif_models.py
"""
Pydantic-модели для What-if сценариев (Итерация 12).

Описывают:
  - запрос на создание сценария (WhatIfScenarioCreate);
  - запрос на обновление (WhatIfScenarioUpdate);
  - ответ со сценарием (WhatIfScenarioResponse);
  - запрос на запуск (WhatIfRunRequest);
  - ответ с результатом сравнения (WhatIfCompareResponse);
  - структуру changes (WhatIfChanges — нестрогая модель).
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ==========================================
# ТИПЫ
# ==========================================

WHATIF_STATUS_VALUES = ("DRAFT", "RUNNING", "DONE", "FAILED")

ORDER_ACTIONS = (
    "add_order",
    "cancel_order",
    "change_qty",
    "change_due_date",
)

CALENDAR_ACTIONS = (
    "add",
    "remove",
)


# ==========================================
# ЗАПРОСЫ
# ==========================================

class WhatIfScenarioCreate(BaseModel):
    """
    Запрос на создание what-if сценария.

    changes — свободная структура (JSONB):
      {
        "orders": [
          {"action": "add_order", "product_code": "GP_CREAM_1L",
           "target_qty": 20000, "due_date": "2026-09-30T23:59:59+03:00"},
          {"action": "cancel_order", "order_id": "uuid"},
          {"action": "change_qty", "order_id": "uuid", "new_qty": 30000},
          {"action": "change_due_date", "order_id": "uuid",
           "new_due_date": "2026-10-15T23:59:59+03:00"}
        ],
        "shift_mode": "3x8",
        "resource_capacity": {
          "REACTOR_OPERATOR": 4,
          "LINE_OPERATOR": 3
        },
        "calendar_events": [
          {"action": "add", "event_type": "BREAKDOWN",
           "equipment_code": "REACTOR_4",
           "starts_at": "2026-09-25T00:00:00+03:00",
           "ends_at": "2026-09-29T00:00:00+03:00"}
        ]
      }
    """
    name: str = Field(..., min_length=3, max_length=200,
                      description="Название сценария")
    comment: Optional[str] = Field(default=None, max_length=2000)
    base_version_id: UUID = Field(
        ..., description="ID базового плана (schedule_version)"
    )
    changes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Изменения (JSON). Формат см. в описании класса."
    )


class WhatIfScenarioUpdate(BaseModel):
    """Запрос на обновление сценария (только DRAFT)."""
    name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    comment: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None


class WhatIfRunRequest(BaseModel):
    """Запрос на запуск сценария."""
    horizon_hours: Optional[int] = Field(
        default=None,
        description="Переопределить горизонт (часов). "
                    "Если None — из app_settings.",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Переопределить таймаут solver (сек). "
                    "Если None — из app_settings.",
    )


# ==========================================
# ОТВЕТЫ
# ==========================================

class WhatIfScenarioResponse(BaseModel):
    """Информация о сценарии."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    comment: Optional[str] = None
    base_version_id: UUID
    result_version_id: Optional[UUID] = None
    changes: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None


class WhatIfScenarioListItem(BaseModel):
    """Краткая информация для списка."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    comment: Optional[str] = None
    base_version_id: UUID
    result_version_id: Optional[UUID] = None
    status: str
    created_at: datetime


class WhatIfMetrics(BaseModel):
    """Метрики одного плана."""
    makespan_minutes: float
    makespan_hours: float
    total_tasks: int
    blocked_tasks: int
    cooling_slow_tasks: int
    cz_incomplete_tasks: int


class WhatIfCompareResponse(BaseModel):
    """
    Результат сравнения базового и результирующего планов.

    Все метрики: base (из базового плана) и result (из результирующего).
    delta — разница (result - base).
    delta_percent — процент изменения.
    """
    scenario_id: UUID
    scenario_name: str
    scenario_status: str
    base_version_id: UUID
    result_version_id: Optional[UUID] = None

    base_metrics: WhatIfMetrics
    result_metrics: Optional[WhatIfMetrics] = None

    # Изменения метрик
    makespan_delta_minutes: Optional[float] = None
    makespan_delta_percent: Optional[float] = None
    total_tasks_delta: Optional[int] = None
    blocked_tasks_delta: Optional[int] = None
    cooling_slow_tasks_delta: Optional[int] = None
    cz_incomplete_tasks_delta: Optional[int] = None

    error_message: Optional[str] = None
    run_at: Optional[datetime] = None


class WhatIfRunResponse(BaseModel):
    """Ответ на запуск сценария."""
    scenario_id: UUID
    status: str
    message: str
    result_version_id: Optional[UUID] = None
    wall_time_seconds: Optional[float] = None
    compare: Optional[WhatIfCompareResponse] = None