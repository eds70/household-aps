# backend/app/api/v1/reschedule_models.py
"""
Pydantic-модели для API перепланирования (Итерация 4).
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ==========================================
# ЗАПРОС НА ПЕРЕПЛАНИРОВАНИЕ
# ==========================================

class RescheduleRequest(BaseModel):
    """Запрос на перепланирование."""
    from_version_id: UUID = Field(..., description="ID исходной версии плана")
    reason: str = Field(..., description="DELAY | BREAKDOWN | QTY_CHANGE | MANUAL")
    changes: Dict[str, Any] = Field(default_factory=dict, description="Параметры изменения")
    frozen_before: Optional[datetime] = Field(
        default=None,
        description="До какого момента задачи заморожены (не двигаются)"
    )
    comment: Optional[str] = None


# ==========================================
# ОТВЕТ
# ==========================================

class RescheduleResponse(BaseModel):
    status: str
    from_version_id: Optional[str] = None
    to_version_id: Optional[str] = None
    affected_tasks: int = 0
    moved_tasks: int = 0
    frozen_tasks: int = 0
    message: str = ""
    diff: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# СРАВНЕНИЕ ВЕРСИЙ
# ==========================================

class MovedTaskInfo(BaseModel):
    task_id: str
    batch_id: Optional[str] = None
    old_start: str
    old_end: str
    new_start: str
    new_end: str
    delta_minutes: int


class CompareResponse(BaseModel):
    v1_id: str
    v2_id: str
    v1_task_count: int
    v2_task_count: int
    only_in_v1: List[str] = []
    only_in_v2: List[str] = []
    moved: List[MovedTaskInfo] = []
    unchanged_count: int = 0
    moved_count: int = 0


# ==========================================
# ЗАКРЕПЛЕНИЕ ЗАДАЧИ
# ==========================================

class PinTaskRequest(BaseModel):
    is_pinned: bool = True


class PinTaskResponse(BaseModel):
    task_id: str
    is_pinned: bool
    message: str

# ==========================================
# MOVE TASK (Итерация 9, C2: drag-and-drop на Ганте)
# ==========================================

class MoveTaskRequest(BaseModel):
    """
    Запрос на перемещение задачи (drag-and-drop на Ганте).

    Frontend отправляет новое время planned_start/planned_end.
    Backend обновляет задачу и ставит is_pinned=TRUE, чтобы solver
    (при следующем пересчете) не сдвинул её обратно.
    """
    new_start: datetime = Field(..., description="Новое время начала")
    new_end: datetime = Field(..., description="Новое время окончания")


class MoveTaskResponse(BaseModel):
    """Ответ на перемещение задачи."""
    task_id: str
    planned_start: datetime
    planned_end: datetime
    is_pinned: bool
    message: str