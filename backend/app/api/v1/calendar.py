# backend/app/api/v1/calendar.py
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from .calendar_models import CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse
from app.auth.dependencies import get_current_org_id, get_db_session

router = APIRouter(prefix="/api/v1/calendar", tags=["Календарь простоев"])


@router.get("/", response_model=List[CalendarEventResponse])
async def get_calendar_events(
        equipment_id: Optional[UUID] = Query(default=None),
        version_id: Optional[UUID] = Query(default=None),
        include_global: bool = Query(default=True),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    table_name = "calendar_snapshot" if version_id else "calendar_event"
    version_filter = "AND version_id = :version_id" if version_id else ""

    if equipment_id:
        if include_global:
            query = text(
                f"SELECT id, organization_id, equipment_id, event_type, starts_at, ends_at, comment "
                f"FROM {table_name} "
                f"WHERE organization_id = :org_id AND (equipment_id = :eq_id OR equipment_id IS NULL) {version_filter} "
                f"ORDER BY starts_at"
            )
            params = {"org_id": org_id, "eq_id": equipment_id}
        else:
            query = text(
                f"SELECT id, organization_id, equipment_id, event_type, starts_at, ends_at, comment "
                f"FROM {table_name} "
                f"WHERE organization_id = :org_id AND equipment_id = :eq_id {version_filter} "
                f"ORDER BY starts_at"
            )
            params = {"org_id": org_id, "eq_id": equipment_id}
    else:
        query = text(
            f"SELECT id, organization_id, equipment_id, event_type, starts_at, ends_at, comment "
            f"FROM {table_name} "
            f"WHERE organization_id = :org_id {version_filter} "
            f"ORDER BY starts_at"
        )
        params = {"org_id": org_id}

    if version_id:
        params["version_id"] = version_id

    result = await db.execute(query, params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "equipment_id": row.equipment_id,
            "event_type": row.event_type,
            "starts_at": row.starts_at,
            "ends_at": row.ends_at,
            "comment": row.comment,
        }
        for row in result.fetchall()
    ]


@router.post("/", response_model=CalendarEventResponse, status_code=201)
async def create_calendar_event(
        event: CalendarEventCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    if event.ends_at <= event.starts_at:
        raise HTTPException(status_code=400, detail="ends_at должен быть позже starts_at")

    new_id = uuid4()
    result = await db.execute(text("""
        INSERT INTO calendar_event (id, organization_id, equipment_id, event_type, starts_at, ends_at, comment)
        VALUES (:id, :org_id, :eq_id, :type, :start, :end, :comment)
        RETURNING id, organization_id, equipment_id, event_type, starts_at, ends_at, comment
    """), {
        "id": new_id,
        "org_id": org_id,
        "eq_id": event.equipment_id,
        "type": event.event_type,
        "start": event.starts_at,
        "end": event.ends_at,
        "comment": event.comment,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать событие")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "equipment_id": row.equipment_id,
        "event_type": row.event_type,
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "comment": row.comment,
    }


@router.put("/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
        event_id: UUID,
        event: CalendarEventUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    update_data = event.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    if "starts_at" in update_data and "ends_at" in update_data and update_data["ends_at"] <= update_data["starts_at"]:
        raise HTTPException(status_code=400, detail="ends_at должен быть позже starts_at")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"UPDATE calendar_event SET {set_clause} "
        f"WHERE id = :event_id AND organization_id = :org_id "
        f"RETURNING id, organization_id, equipment_id, event_type, starts_at, ends_at, comment"
    )
    params = {"event_id": event_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "equipment_id": row.equipment_id,
        "event_type": row.event_type,
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "comment": row.comment,
    }


@router.delete("/{event_id}")
async def delete_calendar_event(
        event_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        text("DELETE FROM calendar_event WHERE id = :event_id AND organization_id = :org_id"),
        {"event_id": event_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    await db.commit()
    return {"message": "Событие удалено"}