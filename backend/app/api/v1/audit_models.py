# backend/app/api/v1/audit_models.py
"""
Pydantic-модели для страницы «Аудит» (Итерация 13.3 + 16).

Собирает в одном месте события из разных журналов:
  - material_stock_log   → изменения остатков
  - reschedule_log       → перепланирования
  - lab_analysis_log     → лабораторные блокировки
  - cz_scan_log          → сканы ЧЗ

Итерация 16 расширяет модели:
  - AuditFilterSpec           — расширенные фильтры (16.1)
  - AuditStatsSeriesResponse  — серии для дашборда (16.3)
  - AuditSavedView*           — сохранённые представления (16.2)
  - AuditExportRequest        — экспорт в xlsx (16.4)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==========================================
# ДОПУСТИМЫЕ ИСТОЧНИКИ
# ==========================================
AUDIT_SOURCES = ("STOCK", "RESCHEDULE", "LAB", "CZ")

# Допустимые значения severity (для валидации фильтра)
AUDIT_SEVERITIES = ("INFO", "WARNING", "CRITICAL")

# Допустимые варианты группировки для дашборда (16.3)
AUDIT_GROUP_BY = ("day", "source", "severity")


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


# ==========================================
# ИТЕРАЦИЯ 16.1: РАСШИРЕННЫЕ ФИЛЬТРЫ
# ==========================================
class AuditFilterSpec(BaseModel):
    """
    Расширенная спецификация фильтров.

    Используется для:
      - валидации query-параметров GET /api/v1/audit/log;
      - сериализации фильтров в audit_saved_view.filters (JSONB).

    ВАЖНО: все поля опциональны. None означает «фильтр не применён».
    """
    model_config = ConfigDict(from_attributes=True)

    # Источники: пустой список / None = «все».
    sources: Optional[List[str]] = None

    # Диапазон дат (UTC, inclusive).
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    # INFO | WARNING | CRITICAL
    severity: Optional[str] = None

    # Поиск по title/description/entity_name/actor_name (подстрока).
    search: Optional[str] = None

    # Итерация 16.1: фильтр по автору события.
    actor_id: Optional[UUID] = None

    # Итерация 16.1: фильтр по типу сущности (material | batch | ...).
    entity_type: Optional[str] = None

    # Итерация 16.1: диапазон delta_qty (только для STOCK-событий).
    # События других источников, у которых delta_qty отсутствует,
    # будут отфильтрованы, если задан хотя бы один из порогов.
    delta_qty_from: Optional[float] = None
    delta_qty_to: Optional[float] = None

    # Лимит (после фильтрации).
    limit: int = Field(default=200, ge=1, le=2000)

    @field_validator("sources")
    @classmethod
    def _validate_sources(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Оставляем только валидные источники; пустой список → None."""
        if not v:
            return None
        cleaned = [s.upper() for s in v if s and s.upper() in AUDIT_SOURCES]
        return cleaned or None

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: Optional[str]) -> Optional[str]:
        """Нормализуем регистр; пустое → None."""
        if not v:
            return None
        v_upper = v.upper()
        if v_upper not in AUDIT_SEVERITIES:
            raise ValueError(
                f"severity must be one of {AUDIT_SEVERITIES}, got {v!r}"
            )
        return v_upper

    @field_validator("delta_qty_from", "delta_qty_to")
    @classmethod
    def _validate_delta_range(cls, v: Optional[float]) -> Optional[float]:
        """Просто пропускаем None."""
        return v


# ==========================================
# ИТЕРАЦИЯ 16.3: СЕРИИ ДЛЯ ДАШБОРДА
# ==========================================
class AuditStatsSeriesPoint(BaseModel):
    """Одна точка серии: метка + количество."""
    label: str
    count: int


class AuditStatsSeriesResponse(BaseModel):
    """
    Серии для графиков на дашборде.

    Пример для group_by='source':
        points = [
          {"label": "STOCK",      "count": 120},
          {"label": "RESCHEDULE", "count": 34},
          ...
        ]

    Пример для group_by='day':
        points = [
          {"label": "2026-10-01", "count": 12},
          {"label": "2026-10-02", "count": 27},
          ...
        ]
    """
    group_by: str                # day | source | severity
    date_from: datetime
    date_to: datetime
    total: int
    points: List[AuditStatsSeriesPoint]


# ==========================================
# ИТЕРАЦИЯ 16.2: СОХРАНЁННЫЕ ПРЕДСТАВЛЕНИЯ
# ==========================================
class AuditSavedViewFilters(BaseModel):
    """
    Фильтры внутри сохранённого представления.

    Отличается от AuditFilterSpec тем, что это *хранимая* форма:
      - все поля опциональны;
      - список источников — как есть;
      - даты — ISO-строки (JSONB не понимает datetime).
    """
    model_config = ConfigDict(from_attributes=True)

    sources: Optional[List[str]] = None
    severity: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1, le=2000)
    actor_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    delta_qty_from: Optional[float] = None
    delta_qty_to: Optional[float] = None


class AuditSavedView(BaseModel):
    """Одно сохранённое представление."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    comment: Optional[str] = None
    filters: Dict[str, Any]
    is_default: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class AuditSavedViewsListResponse(BaseModel):
    """Список сохранённых представлений пользователя."""
    views: List[AuditSavedView]
    total: int


class AuditSavedViewCreate(BaseModel):
    """Тело запроса на создание представления."""
    name: str = Field(min_length=1, max_length=100)
    comment: Optional[str] = None
    filters: AuditSavedViewFilters = Field(default_factory=AuditSavedViewFilters)
    is_default: bool = False
    display_order: int = 0


class AuditSavedViewUpdate(BaseModel):
    """Тело запроса на обновление представления (все поля опциональны)."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    comment: Optional[str] = None
    filters: Optional[AuditSavedViewFilters] = None
    is_default: Optional[bool] = None
    display_order: Optional[int] = None


class AuditSavedViewDeleteResponse(BaseModel):
    """Ответ на удаление представления."""
    status: str
    id: UUID
    message: str


# ==========================================
# ИТЕРАЦИЯ 16.4: ЭКСПОРТ В XLSX
# ==========================================
class AuditExportRequest(BaseModel):
    """
    Тело POST /api/v1/audit/export.xlsx.

    Дублирует фильтры AuditFilterSpec, чтобы не мешать их в query
    (у POST-запроса query-параметры работают, но некрасиво).
    """
    filters: AuditFilterSpec = Field(default_factory=AuditFilterSpec)
    # Заголовок отчёта (опционально).
    title: Optional[str] = None
    # Максимум строк в выгрузке (защита от гигантских файлов).
    max_rows: int = Field(default=10000, ge=1, le=100000)