# backend/app/api/v1/models.py
"""
Pydantic-модели для API планирования и Ганта.

Итерация 2:
- Добавлены модели для Advisor (AdvisorTip, AdvisorResponse)
- Добавлены модели для Feasibility (FeasibilityResponse)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class ScheduleBuildRequest(BaseModel):
    horizon_hours: int = Field(default=2160)
    timeout_seconds: int = Field(default=120)


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