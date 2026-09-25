# backend/app/api/v1/product_models.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    code: str
    name: str
    type: str  # 'PF' или 'GP'
    viscosity_coeff: Optional[float] = 1.0
    requires_heating: Optional[bool] = False
    bottle_volume_l: Optional[float] = None
    fill_speed_per_min: Optional[float] = None
    parent_pf_id: Optional[UUID] = None


class ProductCreate(ProductBase):
    organization_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))


class ProductUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    viscosity_coeff: Optional[float] = None
    requires_heating: Optional[bool] = None
    bottle_volume_l: Optional[float] = None
    fill_speed_per_min: Optional[float] = None
    parent_pf_id: Optional[UUID] = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID