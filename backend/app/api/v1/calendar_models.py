from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


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
    id: UUID
    organization_id: UUID

    class Config:
        from_attributes = True