from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

class EquipmentBase(BaseModel):
    name: str
    type: str
    volume_kg: Optional[float] = None
    speed_coeff: Optional[float] = 1.0
    mixer_type: Optional[str] = None
    is_active: bool = True

class EquipmentCreate(EquipmentBase):
    organization_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))

class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    volume_kg: Optional[float] = None
    speed_coeff: Optional[float] = None
    mixer_type: Optional[str] = None
    is_active: Optional[bool] = None

class EquipmentResponse(EquipmentBase):
    id: UUID
    organization_id: UUID

    class Config:
        from_attributes = True
