from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from uuid import UUID, uuid4
from .equipment_models import EquipmentCreate, EquipmentUpdate, EquipmentResponse

router = APIRouter(prefix="/api/v1/equipment", tags=["Оборудование"])
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

@router.get("/", response_model=List[EquipmentResponse])
async def get_all_equipment(
        version_id: Optional[UUID] = Query(default=None),
        db: AsyncSession = Depends(get_db)
):
    """Получить все оборудование (или снимок версии)"""
    if version_id:
        query = text("""
            SELECT id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
            FROM equipment_snapshot
            WHERE organization_id = :org_id AND version_id = :version_id
            ORDER BY name
        """)
        params = {"org_id": ORG_ID, "version_id": version_id}
    else:
        query = text("""
            SELECT id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
            FROM equipment
            WHERE organization_id = :org_id
            ORDER BY name
        """)
        params = {"org_id": ORG_ID}

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

@router.post("/", response_model=EquipmentResponse)
async def create_equipment(equipment: EquipmentCreate, db: AsyncSession = Depends(get_db)):
    new_id = uuid4()
    result = await db.execute(text("""
        INSERT INTO equipment (id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active)
        VALUES (:id, :org_id, :name, :type, :volume_kg, :speed_coeff, :mixer_type, :is_active)
        RETURNING id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active
    """), {
        "id": new_id, "org_id": equipment.organization_id, "name": equipment.name,
        "type": equipment.type, "volume_kg": equipment.volume_kg, "speed_coeff": equipment.speed_coeff,
        "mixer_type": equipment.mixer_type, "is_active": equipment.is_active,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать оборудование")
    await db.commit()
    return {
        "id": row.id, "organization_id": row.organization_id, "name": row.name,
        "type": row.type, "volume_kg": float(row.volume_kg) if row.volume_kg else None,
        "speed_coeff": float(row.speed_coeff) if row.speed_coeff else 1.0,
        "mixer_type": row.mixer_type, "is_active": row.is_active,
    }

@router.put("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(equipment_id: UUID, equipment: EquipmentUpdate, db: AsyncSession = Depends(get_db)):
    update_data = equipment.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = f"UPDATE equipment SET {set_clause} WHERE id = :equipment_id AND organization_id = :org_id RETURNING id, organization_id, name, type, volume_kg, speed_coeff, mixer_type, is_active"
    params = {"equipment_id": equipment_id, "org_id": ORG_ID, **update_data}
    result = await db.execute(text(query), params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await db.commit()
    return {
        "id": row.id, "organization_id": row.organization_id, "name": row.name,
        "type": row.type, "volume_kg": float(row.volume_kg) if row.volume_kg else None,
        "speed_coeff": float(row.speed_coeff) if row.speed_coeff else 1.0,
        "mixer_type": row.mixer_type, "is_active": row.is_active,
    }

@router.delete("/{equipment_id}")
async def delete_equipment(equipment_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("DELETE FROM equipment WHERE id = :equipment_id AND organization_id = :org_id"), {"equipment_id": equipment_id, "org_id": ORG_ID})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await db.commit()
    return {"message": "Оборудование удалено"}