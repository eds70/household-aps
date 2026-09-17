# backend/app/api/v1/material_models.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class MaterialBase(BaseModel):
    code: str
    name: str
    unit: str = "kg"
    category: str  # RAW, PACKAGING, LABEL
    comment: Optional[str] = None


class MaterialCreate(MaterialBase):
    organization_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001")
    )


class MaterialUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    comment: Optional[str] = None


class MaterialResponse(MaterialBase):
    id: UUID
    organization_id: UUID

    class Config:
        from_attributes = True


class MaterialStockBase(BaseModel):
    qty: float = 0
    reserved_qty: float = 0


class MaterialStockUpdate(BaseModel):
    qty: Optional[float] = None
    reserved_qty: Optional[float] = None


class MaterialStockResponse(MaterialStockBase):
    id: UUID
    material_id: UUID
    organization_id: UUID
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeItemBase(BaseModel):
    material_id: UUID
    qty_per_base: float


class RecipeItemCreate(RecipeItemBase):
    pass


class RecipeItemResponse(RecipeItemBase):
    id: UUID
    recipe_id: UUID
    material_name: Optional[str] = None
    material_code: Optional[str] = None
    material_unit: Optional[str] = None

    class Config:
        from_attributes = True


class RecipeBase(BaseModel):
    product_id: UUID
    base_volume_kg: float
    comment: Optional[str] = None


class RecipeCreate(RecipeBase):
    organization_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001")
    )
    items: List[RecipeItemCreate] = []


class RecipeUpdate(BaseModel):
    base_volume_kg: Optional[float] = None
    comment: Optional[str] = None


class RecipeResponse(RecipeBase):
    id: UUID
    organization_id: UUID
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    items: List[RecipeItemResponse] = []

    class Config:
        from_attributes = True


class ProductionOrderBase(BaseModel):
    product_id: UUID
    target_qty: float
    due_date: datetime
    priority: int = 5
    comment: Optional[str] = None


class ProductionOrderCreate(ProductionOrderBase):
    organization_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001")
    )


class ProductionOrderUpdate(BaseModel):
    target_qty: Optional[float] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    comment: Optional[str] = None


class ProductionOrderResponse(ProductionOrderBase):
    id: UUID
    organization_id: UUID
    status: str
    created_at: datetime
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    batches_count: int = 0

    class Config:
        from_attributes = True


# ==========================================
# BATCH: обновлено в Итерации 5 (Лаборатория)
# ==========================================

class BatchBase(BaseModel):
    product_id: UUID
    volume_kg: float
    assigned_equipment_id: Optional[UUID] = None
    comment: Optional[str] = None
    # Новые поля Итерации 5
    is_lab_blocked: bool = False
    lab_status: str = "NOT_REQUIRED"   # NOT_REQUIRED | PENDING_LAB | APPROVED | BLOCKED
    lab_block_reason: Optional[str] = None
    lab_blocked_at: Optional[datetime] = None
    lab_blocked_by: Optional[UUID] = None


class BatchCreate(BatchBase):
    organization_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000001")
    )


class BatchUpdate(BaseModel):
    volume_kg: Optional[float] = None
    assigned_equipment_id: Optional[UUID] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    status: Optional[str] = None
    comment: Optional[str] = None
    # Новые поля Итерации 5
    is_lab_blocked: Optional[bool] = None
    lab_status: Optional[str] = None
    lab_block_reason: Optional[str] = None


class BatchResponse(BatchBase):
    id: UUID
    organization_id: UUID
    order_id: UUID
    status: str
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    equipment_name: Optional[str] = None

    class Config:
        from_attributes = True