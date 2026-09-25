# backend/app/api/v1/calendar_models.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalendarEventBase(BaseModel):
    equipment_id: Optional[UUID] = None  # NULL = простой на всё производство
    event_type: str = "REPAIR"           # WEEKEND, REPAIR, BREAKDOWN, SHIFT_END, LUNCH
    starts_at: datetime
    ends_at: datetime
    comment: Optional[str] = None


class CalendarEventCreate(CalendarEventBase):
    organization_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))


class CalendarEventUpdate(BaseModel):
    equipment_id: Optional[UUID] = None
    event_type: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    comment: Optional[str] = None


class CalendarEventResponse(CalendarEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID