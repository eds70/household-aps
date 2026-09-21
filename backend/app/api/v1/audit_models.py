# backend/app/api/v1/audit_models.py
"""
Pydantic-модели для страницы «Аудит» (Итерация 13.3).

Собирает в одном месте события из разных журналов:
  - material_stock_log   → изменения остатков
  - reschedule_log       → перепланирования
  - lab_analysis_log     → лабораторные блокировки
  - cz_scan_log          → сканы ЧЗ
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ==========================================
# ДОПУСТИМЫЕ ИСТОЧНИКИ
# ==========================================
AUDIT_SOURCES = ("STOCK", "RESCHEDULE", "LAB", "CZ")


# ==========================================
# СОБЫТИЕ АУДИТА
# ==========================================
class AuditEvent(BaseModel):
    """
    Универсальное событие для страницы аудита.

    Все 4 источника нормализуются в эту модель.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    # STOCK | RESCHEDULE | LAB | CZ
    source: str

    # UPDATE | INSERT | DELETE | DELAY | BREAKDOWN | BLOCKED | APPROVED | SCAN | ...
    event_type: str

    # INFO | WARNING | CRITICAL
    severity: str

    title: str
    description: Optional[str] = None

    # material | batch | schedule_version | order | ...
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    entity_name: Optional[str] = None

    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None

    occurred_at: datetime

    details: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# СПИСОК СОБЫТИЙ
# ==========================================
class AuditListResponse(BaseModel):
    """Список событий + агрегация по источникам."""
    events: List[AuditEvent]
    total: int
    by_source: Dict[str, int]


# ==========================================
# СТАТИСТИКА ЗА ПЕРИОД
# ==========================================
class AuditStatsResponse(BaseModel):
    """
    Сводная статистика за период.

    Используется эндпоинтом GET /api/v1/audit/stats.
    """
    period_days: int
    date_from: datetime
    date_to: datetime
    total: int
    by_source: Dict[str, int]
    by_severity: Dict[str, int]      # {INFO, WARNING, CRITICAL}