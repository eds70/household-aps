# backend/app/api/v1/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class ScheduleBuildRequest(BaseModel):
    # organization_id удален, так как теперь берется из токена
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

class GanttResponse(BaseModel):
    tasks: List[GanttTask]
    total_tasks: int
    makespan_hours: float
    equipment_list: List[str]
    product_list: List[str]