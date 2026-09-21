# backend/app/api/v1/material_models.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ==========================================
# MATERIAL
# ==========================================

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
    # Итерация 13.1: начальный остаток при создании
    initial_qty: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Начальный остаток материала на складе (в единицах unit)",
    )
    initial_reserved_qty: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Начальное зарезервированное количество",
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
    # Итерация 13.1: остатки в ответе (JOIN с material_stock)
    stock_qty: Optional[float] = 0.0
    reserved_qty: Optional[float] = 0.0

    class Config:
        from_attributes = True


# ==========================================
# MATERIAL STOCK
# ==========================================

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


# ==========================================
# ИТЕРАЦИЯ 13.2: ЖУРНАЛ ИЗМЕНЕНИЙ ОСТАТКОВ
# ==========================================

class MaterialStockLogEntry(BaseModel):
    """Одна запись журнала изменений остатков."""
    id: UUID
    organization_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None

    action: str  # INSERT | UPDATE | DELETE

    old_qty: Optional[float] = None
    new_qty: Optional[float] = None
    old_reserved_qty: Optional[float] = None
    new_reserved_qty: Optional[float] = None
    delta_qty: Optional[float] = None
    delta_reserved_qty: Optional[float] = None

    changed_at: datetime
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class MaterialStockLogListResponse(BaseModel):
    """Список записей журнала + общее количество."""
    entries: List[MaterialStockLogEntry]
    total: int


# ==========================================
# ИТЕРАЦИЯ 13.2: ИМПОРТ ИЗ EXCEL
# ==========================================

class MaterialImportRow(BaseModel):
    """Результат импорта одной строки Excel."""
    row_number: int
    code: str
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    qty: Optional[float] = None
    reserved_qty: Optional[float] = None
    status: str  # CREATED | UPDATED | SKIPPED | ERROR
    message: Optional[str] = None


class MaterialImportResponse(BaseModel):
    """Результат импорта из Excel."""
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: int
    rows: List[MaterialImportRow]
    message: str


# ==========================================
# ИТЕРАЦИЯ 13.3: ROLLBACK + CLEANUP ЖУРНАЛА
# ==========================================

class MaterialStockLogRevertResponse(BaseModel):
    """Ответ на отмену изменения остатков."""
    log_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    reverted: bool
    old_qty: Optional[float] = None
    new_qty: Optional[float] = None
    message: str


class MaterialStockLogCleanupResponse(BaseModel):
    """Ответ на очистку журнала."""
    deleted: int
    kept: int
    message: str


# ==========================================
# RECIPES
# ==========================================

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


# ==========================================
# PRODUCTION ORDER
# ==========================================

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
# BATCH (Итерация 5: лаборатория)
# ==========================================

class BatchBase(BaseModel):
    product_id: UUID
    volume_kg: float
    assigned_equipment_id: Optional[UUID] = None
    comment: Optional[str] = None
    is_lab_blocked: bool = False
    lab_status: str = "NOT_REQUIRED"
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