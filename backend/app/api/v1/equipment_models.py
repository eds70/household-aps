# backend/app/api/v1/equipment_models.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID