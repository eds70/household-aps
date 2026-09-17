# backend/app/api/v1/personnel_models.py
"""
Pydantic-модели для API персонала (Итерация 6).

Описывают пулы операторов (REACTOR_OPERATOR, LINE_OPERATOR,
MANUAL_OPERATOR) и их загрузку в текущем плане.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PersonnelPoolBase(BaseModel):
    name: str
    type: str
    capacity: int
    comment: Optional[str] = None


class PersonnelPoolUpdate(BaseModel):
    """Обновление пула (только capacity и name)."""
    name: Optional[str] = None
    capacity: Optional[int] = None
    comment: Optional[str] = None


class PersonnelPoolResponse(PersonnelPoolBase):
    """Пул операторов."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    updated_at: Optional[datetime] = None
    scheduled_count: int = 0
    peak_concurrent: int = 0
    load_percent: float = 0.0


class PersonnelPoolListResponse(BaseModel):
    """Список пулов."""
    pools: List[PersonnelPoolResponse]
    total_capacity: int
    total_scheduled: int
    version_id: Optional[str] = None
    version_name: Optional[str] = None