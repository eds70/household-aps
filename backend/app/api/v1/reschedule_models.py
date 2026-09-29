# backend/app/api/v1/reschedule_models.py
"""
Pydantic-модели для API перепланирования (Итерация 4).

Итерация 13.17 (9q): MoveTaskRequest получил валидатор, который
приводит new_start / new_end к naive-UTC. Это нужно потому что:
  - фронт (vis-timeline) шлёт ISO-строки с timezone (например,
    "2026-09-03T19:00:00.000Z");
  - Pydantic парсит их как aware datetime;
  - planning_start из БД — naive-UTC;
  - сравнение aware и naive падает с TypeError.

Валидатор приводит все времена к одной форме — naive-UTC.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ==========================================
# ЗАПРОС НА ПЕРЕПЛАНИРОВАНИЕ
# ==========================================

class RescheduleRequest(BaseModel):
    """Запрос на перепланирование."""
    from_version_id: UUID = Field(..., description="ID исходной версии плана")
    reason: str = Field(..., description="DELAY | BREAKDOWN | QTY_CHANGE | MANUAL")
    changes: Dict[str, Any] = Field(default_factory=dict, description="Параметры изменения")
    frozen_before: Optional[datetime] = Field(
        default=None,
        description="До какого момента задачи заморожены (не двигаются)"
    )
    comment: Optional[str] = None


# ==========================================
# ОТВЕТ
# ==========================================

class RescheduleResponse(BaseModel):
    status: str
    from_version_id: Optional[str] = None
    to_version_id: Optional[str] = None
    affected_tasks: int = 0
    moved_tasks: int = 0
    frozen_tasks: int = 0
    message: str = ""
    diff: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# СРАВНЕНИЕ ВЕРСИЙ
# ==========================================

class MovedTaskInfo(BaseModel):
    task_id: str
    batch_id: Optional[str] = None
    old_start: str
    old_end: str
    new_start: str
    new_end: str
    delta_minutes: int


class CompareResponse(BaseModel):
    v1_id: str
    v2_id: str
    v1_task_count: int
    v2_task_count: int
    only_in_v1: List[str] = []
    only_in_v2: List[str] = []
    moved: List[MovedTaskInfo] = []
    unchanged_count: int = 0
    moved_count: int = 0


# ==========================================
# ЗАКРЕПЛЕНИЕ ЗАДАЧИ
# ==========================================

class PinTaskRequest(BaseModel):
    is_pinned: bool = True


class PinTaskResponse(BaseModel):
    task_id: str
    is_pinned: bool
    message: str


# ==========================================
# MOVE TASK (Итерация 9, C2: drag-and-drop на Ганте)
# ==========================================

class MoveTaskRequest(BaseModel):
    """
    Запрос на перемещение/изменение длительности задачи
    (drag-and-drop на Ганте).

    Frontend отправляет новое время planned_start/planned_end.
    Backend обновляет задачу или запускает каскад.

    Итерация 13.17 (9q): валидаторы приводят new_start / new_end
    к naive-UTC. Это устраняет TypeError при сравнении с
    planning_start из БД (тоже naive-UTC).
    """
    new_start: datetime = Field(..., description="Новое время начала")
    new_end: datetime = Field(..., description="Новое время окончания")

    @field_validator("new_start", "new_end", mode="after")
    @classmethod
    def _to_naive_utc(cls, v: datetime) -> datetime:
        """
        Приводит datetime к naive-UTC.

        Если значение aware (с timezone) — конвертируем в UTC
        и убираем tzinfo. Если naive — оставляем как есть
        (предполагаем, что оно уже в UTC).
        """
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class MoveTaskResponse(BaseModel):
    """Ответ на перемещение/изменение задачи."""
    task_id: str
    planned_start: datetime
    planned_end: datetime
    is_pinned: bool
    message: str
    moved_tasks: List[dict] = []