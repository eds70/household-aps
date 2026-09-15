# backend/app/api/v1/equipment.py
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from .equipment_models import EquipmentCreate, EquipmentUpdate, EquipmentResponse
from app.auth.dependencies import get_current_org_id, get_db_session

router = APIRouter(prefix="/api/v1/equipment", tags=["Оборудование"])


@router.get("/", response_model=List[EquipmentResponse])
async def get_all_equipment(
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить все оборудование (или снимок версии)"""
    if version_id:
        query = text("""
            SELECT id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
            FROM equipment_snapshot
            WHERE organization_id = :org_id AND version_id = :version_id
            ORDER BY name
        """)
        params = {"org_id": org_id, "version_id": version_id}
    else:
        query = text("""
            SELECT id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
            FROM equipment
            WHERE organization_id = :org_id
            ORDER BY name
        """)
        params = {"org_id": org_id}

    result = await db.execute(query, params)
    equipment_list = []
    for row in result.fetchall():
        equipment_list.append({
            "id": row.id,
            "organization_id": row.organization_id,
            "name": row.name,
            "type": row.type,
            "volume_kg": float(row.volume_kg) if row.volume_kg else None,
            "speed_coeff": float(row.speed_coeff) if row.speed_coeff else 1.0,
            "mixer_type": row.mixer_type,
            "is_active": row.is_active,
        })
    return equipment_list


@router.post("/", response_model=EquipmentResponse, status_code=201)
async def create_equipment(
        equipment: EquipmentCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    new_id = uuid4()
    result = await db.execute(text("""
        INSERT INTO equipment (id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active)
        VALUES (:id, :org_id, :name, :type, :volume_kg, :speed_coeff, :mixer_type, :is_active)
        RETURNING id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
    """), {
        "id": new_id,
        "org_id": org_id,
        "name": equipment.name,
        "type": equipment.type,
        "volume_kg": equipment.volume_kg,
        "speed_coeff": equipment.speed_coeff,
        "mixer_type": equipment.mixer_type,
        "is_active": equipment.is_active,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать оборудование")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "name": row.name,
        "type": row.type,
        "volume_kg": float(row.volume_kg) if row.volume_kg else None,
        "speed_coeff": float(row.speed_coeff) if row.speed_coeff else 1.0,
        "mixer_type": row.mixer_type,
        "is_active": row.is_active,
    }


@router.put("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(
        equipment_id: UUID,
        equipment: EquipmentUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    update_data = equipment.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"UPDATE equipment SET {set_clause} "
        f"WHERE id = :equipment_id AND organization_id = :org_id "
        f"RETURNING id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active"
    )
    params = {"equipment_id": equipment_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "name": row.name,
        "type": row.type,
        "volume_kg": float(row.volume_kg) if row.volume_kg else None,
        "speed_coeff": float(row.speed_coeff) if row.speed_coeff else 1.0,
        "mixer_type": row.mixer_type,
        "is_active": row.is_active,
    }


@router.delete("/{equipment_id}")
async def delete_equipment(
        equipment_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        text("DELETE FROM equipment WHERE id = :equipment_id AND organization_id = :org_id"),
        {"equipment_id": equipment_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await db.commit()
    return {"message": "Оборудование удалено"}