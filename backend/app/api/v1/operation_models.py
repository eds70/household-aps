from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

class OperationBase(BaseModel):
    product_id: UUID
    stage_order: int
    name: str
    base_duration_mins: int
    is_setup: bool = False
    is_parallel_group: bool = False
    parallel_group_id: Optional[str] = None
    needs_boiler: bool = False
    needs_cooling_zone: bool = False
    needs_operator: bool = False
    needs_lab: bool = False
    duration_formula: Optional[str] = None
    comment: Optional[str] = None

class OperationCreate(OperationBase):
    organization_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))

class OperationUpdate(BaseModel):
    stage_order: Optional[int] = None
    name: Optional[str] = None
    base_duration_mins: Optional[int] = None
    is_setup: Optional[bool] = None
    is_parallel_group: Optional[bool] = None
    parallel_group_id: Optional[str] = None
    needs_boiler: Optional[bool] = None
    needs_cooling_zone: Optional[bool] = None
    needs_operator: Optional[bool] = None
    needs_lab: Optional[bool] = None
    duration_formula: Optional[str] = None
    comment: Optional[str] = None

class OperationResponse(OperationBase):
    id: UUID
    organization_id: UUID
    product_name: Optional[str] = None  # Для отображения

    class Config:
        from_attributes = True