# backend/app/api/v1/lab_models.py
"""
Pydantic-модели для API лаборатории (Итерация 5).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# ЗАПРОСЫ
# ==========================================

class BlockBatchRequest(BaseModel):
    """Запрос на блокировку партии лабораторией."""
    reason: str = Field(..., min_length=3, max_length=500,
                        description="Причина блокировки (обязательно)")
    scheduled_task_id: Optional[UUID] = Field(
        default=None,
        description="ID задачи лабораторного анализа, по которой блокируется"
    )
    comment: Optional[str] = None


class UnblockBatchRequest(BaseModel):
    """Запрос на разблокировку партии (одобрение лабораторией)."""
    comment: Optional[str] = None


class ApproveBatchRequest(BaseModel):
    """Запрос на одобрение партии после анализа."""
    result: str = Field(default="PASSED", description="PASSED | FAILED")
    comment: Optional[str] = None


class RequestAnalysisRequest(BaseModel):
    """Запрос на лабораторный анализ для партии."""
    comment: Optional[str] = None


# ==========================================
# ОТВЕТЫ
# ==========================================

class LabAnalysisLogResponse(BaseModel):
    """Одна запись журнала лаборатории."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    batch_id: UUID
    scheduled_task_id: Optional[UUID] = None
    action: str
    result: Optional[str] = None
    reason: Optional[str] = None
    performed_by: Optional[UUID] = None
    performed_by_name: Optional[str] = None
    performed_at: datetime
    comment: Optional[str] = None


class BatchLabStatusResponse(BaseModel):
    """Текущий статус партии по лаборатории."""
    batch_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    volume_kg: float
    is_lab_blocked: bool
    lab_status: str
    lab_block_reason: Optional[str] = None
    lab_blocked_at: Optional[datetime] = None
    lab_blocked_by: Optional[UUID] = None
    lab_blocked_by_name: Optional[str] = None
    equipment_name: Optional[str] = None


class LabPendingBatchResponse(BaseModel):
    """Партия, ожидающая анализа / заблокированная."""
    batch_id: UUID
    order_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    volume_kg: float
    equipment_id: Optional[UUID] = None
    equipment_name: Optional[str] = None
    is_lab_blocked: bool
    lab_status: str
    lab_block_reason: Optional[str] = None
    lab_blocked_at: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    # Ближайшая задача needs_lab
    next_lab_task_id: Optional[UUID] = None
    next_lab_task_start: Optional[datetime] = None
    next_lab_task_end: Optional[datetime] = None


class LabActionResponse(BaseModel):
    """Ответ на действие с партией."""
    batch_id: UUID
    action: str
    is_lab_blocked: bool
    lab_status: str
    message: str
    log_id: Optional[UUID] = None