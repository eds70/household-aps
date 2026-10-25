# backend/app/api/v1/material_models.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    stock_qty: Optional[float] = 0.0
    reserved_qty: Optional[float] = 0.0


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    organization_id: UUID
    updated_at: datetime


# ==========================================
# MATERIAL STOCK LOG
# ==========================================

class MaterialStockLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None

    action: str

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


class MaterialStockLogListResponse(BaseModel):
    entries: List[MaterialStockLogEntry]
    total: int


# ==========================================
# MATERIAL IMPORT
# ==========================================

class MaterialImportRow(BaseModel):
    row_number: int
    code: str
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    qty: Optional[float] = None
    reserved_qty: Optional[float] = None
    status: str
    message: Optional[str] = None


class MaterialImportResponse(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: int
    rows: List[MaterialImportRow]
    message: str


# ==========================================
# MATERIAL STOCK LOG ROLLBACK
# ==========================================

class MaterialStockLogRevertResponse(BaseModel):
    log_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    reverted: bool
    old_qty: Optional[float] = None
    new_qty: Optional[float] = None
    message: str


class MaterialStockLogCleanupResponse(BaseModel):
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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipe_id: UUID
    material_name: Optional[str] = None
    material_code: Optional[str] = None
    material_unit: Optional[str] = None


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    items: List[RecipeItemResponse] = []


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    status: str
    created_at: datetime
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    batches_count: int = 0


# ==========================================
# BATCH (Итерация 5: лаборатория)
# ==========================================

class BatchBase(BaseModel):
    volume_kg: float
    assigned_equipment_id: Optional[UUID] = None
    comment: Optional[str] = None
    is_lab_blocked: bool = False
    lab_status: str = "NOT_REQUIRED"
    lab_block_reason: Optional[str] = None
    lab_blocked_at: Optional[datetime] = None
    lab_blocked_by: Optional[UUID] = None


class BatchCreate(BatchBase):
    """
    Итерация 17.5 (fix): product_id убран — вычисляется backend'ом.
    """
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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    order_id: UUID
    product_id: UUID
    status: str
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    equipment_name: Optional[str] = None


# ==========================================
# ИТЕРАЦИЯ 24: AUTO-SPLIT-OPTIMIZED
# ==========================================

class AutoSplitOptimizedRequest(BaseModel):
    """
    Запрос на оптимальное распределение заказа между реакторами.

    Если equipment_ids не задан — используются ВСЕ реакторы,
    которые могут варить ПФ этого заказа (по equipment_capability).

    Если задан — распределение идёт только между ними (жёсткая
    привязка к capability всё равно применяется).

    max_fill_percent — доля загрузки реактора (по ТЗ ≤ 0.70).
    """

    equipment_ids: Optional[List[UUID]] = Field(
        default=None,
        description=(
            "Список реакторов для распределения. Если None — "
            "все подходящие по equipment_capability."
        ),
    )
    strategy: str = Field(
        default="greedy_makespan",
        description=(
            "Стратегия распределения: greedy_makespan (default), "
            "round_robin, proportional, equal_split"
        ),
    )
    max_fill_percent: float = Field(
        default=0.70,
        ge=0.1,
        le=1.0,
        description="Доля загрузки реактора (по ТЗ ≤ 0.70).",
    )


class AutoSplitBatchResult(BaseModel):
    """Информация об одной созданной партии."""
    batch_id: UUID
    volume_kg: float
    equipment_id: UUID
    equipment_name: str


class AutoSplitReactorSummary(BaseModel):
    """Сводка по одному реактору: сколько партий, суммарный объём."""
    equipment_id: UUID
    equipment_name: str
    max_batch_volume: float       # volume_kg × max_fill_percent
    batches_count: int
    total_volume_kg: float
    load_percent: float           # total / (volume_kg × max_fill_percent)


class AutoSplitOptimizedResponse(BaseModel):
    """Ответ на оптимальное распределение."""
    order_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    target_qty: float
    strategy: str
    total_batches_created: int
    batches: List[AutoSplitBatchResult]
    per_reactor: List[AutoSplitReactorSummary]
    message: str