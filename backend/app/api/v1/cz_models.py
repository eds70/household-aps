# backend/app/api/v1/cz_models.py
"""
Pydantic-модели для API Честного Знака (Итерация 8).

Описывают:
  - входящий скан от камеры (CzScanRequest);
  - ответ на скан (CzScanResponse);
  - прогресс маркировки партии (CzProgressResponse);
  - строку журнала (CzScanLogResponse);
  - сводку по маркировке (CzStatsResponse);
  - ручное сопоставление сироты (CzAttachRequest).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ==========================================
# ТИПЫ
# ==========================================

CZ_STATUS_VALUES = ("NOT_APPLICABLE", "PENDING", "IN_PROGRESS", "COMPLETED")


# ==========================================
# ЗАПРОСЫ
# ==========================================

class CzScanRequest(BaseModel):
    """
    Скан от камеры технического зрения.

    Обязательные поля:
      - cz_code — код маркировки ЧЗ.

    Опциональные:
      - gtin        — GTIN продукта.
      - batch_id    — ID партии (если камера знает).
      - task_id     — ID задачи слива (если камера знает).
      - line_code   — код линии (LINE_1, LINE_2, LINE_3).
      - camera_id   — ID камеры (CAM-01 и т.п.).
      - scanned_at  — время скана (если нет — NOW()).
      - qty         — количество единиц (обычно 1).
      - comment     — свободный комментарий.
    """
    cz_code: str = Field(..., min_length=5, max_length=200,
                         description="Код маркировки ЧЗ (DataMatrix)")
    gtin: Optional[str] = Field(default=None, max_length=50)
    batch_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    line_code: Optional[str] = Field(default=None, max_length=50)
    camera_id: Optional[str] = Field(default=None, max_length=50)
    scanned_at: Optional[datetime] = None
    qty: Optional[float] = Field(default=1.0, ge=0)
    comment: Optional[str] = None


class CzAttachRequest(BaseModel):
    """Ручное сопоставление скана-сироты с партией/задачей."""
    batch_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    comment: Optional[str] = None


# ==========================================
# ОТВЕТЫ
# ==========================================

class CzScanResponse(BaseModel):
    """Ответ на приём скана."""
    id: UUID
    cz_code: str
    batch_id: Optional[UUID] = None
    scheduled_task_id: Optional[UUID] = None
    qty: float
    duplicate: bool = Field(
        default=False,
        description="True, если код уже был зарегистрирован ранее",
    )
    resolved: bool = Field(
        default=False,
        description="True, если удалось сопоставить скан с партией",
    )
    message: str


class CzProgressResponse(BaseModel):
    """Прогресс маркировки партии."""
    batch_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    planned_qty: Optional[float] = Field(
        default=None,
        description="Ожидаемое количество бутылок по заказу",
    )
    marked_qty: float = 0.0
    progress_percent: float = 0.0
    cz_status: str = "PENDING"
    threshold: float = 0.95
    last_scan_at: Optional[datetime] = None
    scans_count: int = 0


class CzScanLogResponse(BaseModel):
    """Строка журнала сканирований."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    batch_id: Optional[UUID] = None
    scheduled_task_id: Optional[UUID] = None
    cz_code: str
    gtin: Optional[str] = None
    qty: float
    line_code: Optional[str] = None
    camera_id: Optional[str] = None
    scanned_at: datetime
    created_at: datetime
    comment: Optional[str] = None

    # Денормализованные поля для UI
    batch_name: Optional[str] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None


class CzPendingBatch(BaseModel):
    """Партия в ожидании маркировки."""
    batch_id: UUID
    order_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    equipment_name: Optional[str] = None
    volume_kg: float
    cz_status: str
    marked_qty: float
    planned_qty: Optional[float] = None
    progress_percent: float
    last_scan_at: Optional[datetime] = None


class CzStatsResponse(BaseModel):
    """Сводка по маркировке."""
    total_batches: int
    not_applicable: int
    pending: int
    in_progress: int
    completed: int
    total_scans: int
    unresolved_scans: int
    threshold: float


class CzActionResponse(BaseModel):
    """Ответ на действие (attach, delete)."""
    id: UUID
    message: str
    resolved: bool = False