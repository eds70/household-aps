# backend/app/api/v1/models.py
"""
Pydantic-модели для API планирования и Ганта.

Итерация 2:
- Добавлены модели для Advisor (AdvisorTip, AdvisorResponse).
- Добавлены модели для Feasibility (FeasibilityResponse).

Итерация 5 (hotfix #3):
- Добавлены поля is_lab_blocked, lab_status, lab_block_reason
  в GanttTask для отображения блокировок лабораторией на Ганте.

Итерация 7:
- Добавлено поле cooling_mode в GanttTask.

Итерация 10:
- horizon_hours по умолчанию уменьшен с 2160 (90 дней)
  до 720 (30 дней).
  Обоснование: реальный план укладывается в 30 дней, а меньшее
  число переменных ускоряет propagation в OR-Tools и позволяет
  solver'у найти решение, полностью соблюдающее календарные
  ограничения (работа в выходные запрещена).
- timeout_seconds увеличен с 120 до 600.
  Solver получает больше времени на поиск OPTIMAL или корректного
  FEASIBLE с полным propagation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduleBuildRequest(BaseModel):
    """
    Параметры запроса на построение расписания.

    Итерация 10: horizon_hours уменьшен с 2160 до 720 (30 дней).
    Реальный план укладывается в 30 дней; меньшее число переменных
    ускоряет propagation.
    """
    horizon_hours: int = Field(
        default=720,
        description="Горизонт планирования в часах (по умолчанию 30 дней)",
    )
    timeout_seconds: int = Field(
        default=600,
        description="Таймаут solver'а в секундах",
    )


class ScheduleBuildResponse(BaseModel):
    status: str
    total_tasks: int
    makespan_minutes: float
    makespan_hours: float
    version_id: Optional[UUID] = None
    message: str


class GanttTask(BaseModel):
    id: str
    batch_id: str
    operation_name: str
    equipment_id: str
    product_id: str
    start: datetime
    end: datetime
    duration_minutes: int
    item_type: str = "task"
    setup_type: Optional[str] = None
    downtime_type: Optional[str] = None
    linked_equipment_id: Optional[str] = None
    linked_equipment_name: Optional[str] = None
    task_role: Optional[str] = None
    # Итерация 5: блокировка лабораторией
    is_lab_blocked: Optional[bool] = False
    lab_status: Optional[str] = None
    lab_block_reason: Optional[str] = None
    # Итерация 7: режим охлаждения
    cooling_mode: Optional[str] = None   # "fast" | "slow" | None


class GanttResponse(BaseModel):
    tasks: List[GanttTask]
    total_tasks: int
    makespan_hours: float
    equipment_list: List[str]
    product_list: List[str]


# ==========================================
# ADVISOR (Итерация 2)
# ==========================================

class AdvisorTipModel(BaseModel):
    code: str
    severity: str  # CRITICAL | WARNING | INFO
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AdvisorResponse(BaseModel):
    tips: List[AdvisorTipModel]
    critical_count: int
    warning_count: int
    info_count: int
    generated_at: datetime


class FeasibilityIssueModel(BaseModel):
    code: str
    severity: str  # BLOCKER | WARNING
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class FeasibilityResponse(BaseModel):
    feasible: bool
    issues: List[FeasibilityIssueModel]
    warnings: List[FeasibilityIssueModel]