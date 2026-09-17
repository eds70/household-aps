# backend/app/api/v1/shift_models.py
"""
Pydantic-модели для API смен (Итерация 3).

Итерация 5: добавлены поля is_lab_blocked, lab_status, lab_block_reason
            в ShiftTaskResponse.
Итерация 7: добавлено поле cooling_mode в ShiftTaskResponse.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ==========================================
# СМЕНА
# ==========================================

class ShiftResponse(BaseModel):
    id: UUID
    name: str
    starts_at: datetime
    ends_at: datetime
    is_working: bool
    comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# ЗАДАНИЕ НА СМЕНУ
# ==========================================

class ShiftTaskResponse(BaseModel):
    id: UUID
    batch_id: Optional[UUID] = None
    batch_name: Optional[str] = None
    product_id: Optional[UUID] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    operation_name: str
    task_role: Optional[str] = None
    equipment_id: UUID
    equipment_name: str
    linked_equipment_id: Optional[UUID] = None
    linked_equipment_name: Optional[str] = None
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    actual_qty: Optional[float] = None
    material_load_at: Optional[datetime] = None
    status: str = "PLANNED"
    duration_minutes: int
    is_carryover: bool = False
    # Итерация 5: блокировка лабораторией
    is_lab_blocked: Optional[bool] = False
    lab_status: Optional[str] = None
    lab_block_reason: Optional[str] = None
    # Итерация 7: режим охлаждения ("fast" | "slow" | None)
    cooling_mode: Optional[str] = None


class ShiftTasksGrouped(BaseModel):
    """Задания, сгруппированные по рабочим центрам."""
    equipment_id: UUID
    equipment_name: str
    equipment_code: Optional[str] = None
    tasks: List[ShiftTaskResponse]


class ShiftTasksResponse(BaseModel):
    shift: ShiftResponse
    groups: List[ShiftTasksGrouped]
    total_tasks: int
    carryover_count: int
    done_count: int


# ==========================================
# ВНЕСЕНИЕ ФАКТА
# ==========================================

class TaskFactRequest(BaseModel):
    """Мастер вносит факт выполнения задания."""
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    actual_qty: Optional[float] = None
    material_load_at: Optional[datetime] = None
    status: Optional[str] = None  # PLANNED | IN_PROGRESS | DONE | CANCELLED
    comment: Optional[str] = None


class TaskFactResponse(BaseModel):
    id: UUID
    status: str
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    actual_qty: Optional[float] = None
    material_load_at: Optional[datetime] = None
    message: str