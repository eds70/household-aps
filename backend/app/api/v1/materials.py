# backend/app/api/v1/materials.py
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from uuid import UUID, uuid4
from .material_models import (
    MaterialCreate,
    MaterialUpdate,
    MaterialResponse,
    MaterialStockUpdate,
    MaterialStockResponse,
)

router = APIRouter(prefix="/api/v1/materials", tags=["Материалы"])

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with async_session() as session:
        yield session


@router.get("/", response_model=List[MaterialResponse])
async def get_all_materials(
        category: Optional[str] = Query(default=None),
        db: AsyncSession = Depends(get_db),
):
    """Получить список материалов с фильтрацией по категории"""
    if category:
        query = text("""
            SELECT id, organization_id, code, name, unit, category, comment
            FROM material
            WHERE organization_id = :org_id AND category = :category
            ORDER BY name
        """)
        params = {"org_id": ORG_ID, "category": category}
    else:
        query = text("""
            SELECT id, organization_id, code, name, unit, category, comment
            FROM material
            WHERE organization_id = :org_id
            ORDER BY name
        """)
        params = {"org_id": ORG_ID}

    result = await db.execute(query, params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "code": row.code,
            "name": row.name,
            "unit": row.unit,
            "category": row.category,
            "comment": row.comment,
        }
        for row in result.fetchall()
    ]


@router.post("/", response_model=MaterialResponse, status_code=201)
async def create_material(
        material: MaterialCreate, db: AsyncSession = Depends(get_db)
):
    """Создать новый материал"""
    new_id = uuid4()
    result = await db.execute(
        text("""
            INSERT INTO material
            (id, organization_id, code, name, unit, category, comment)
            VALUES
            (:id, :org_id, :code, :name, :unit, :category, :comment)
            RETURNING id, organization_id, code, name, unit, category, comment
        """),
        {
            "id": new_id,
            "org_id": material.organization_id,
            "code": material.code,
            "name": material.name,
            "unit": material.unit,
            "category": material.category,
            "comment": material.comment,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать материал")

    # Создаём запись об остатках с нулевым количеством
    await db.execute(
        text("""
            INSERT INTO material_stock
            (organization_id, material_id, qty, reserved_qty)
            VALUES (:org_id, :mat_id, 0, 0)
        """),
        {"org_id": material.organization_id, "mat_id": new_id},
    )

    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "code": row.code,
        "name": row.name,
        "unit": row.unit,
        "category": row.category,
        "comment": row.comment,
    }


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
        material_id: UUID,
        material: MaterialUpdate,
        db: AsyncSession = Depends(get_db),
):
    """Обновить материал"""
    update_data = material.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE material
            SET {set_clause}
            WHERE id = :material_id AND organization_id = :org_id
            RETURNING id, organization_id, code, name, unit, category, comment
        """
    )
    params = {"material_id": material_id, "org_id": ORG_ID, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Материал не найден")

    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "code": row.code,
        "name": row.name,
        "unit": row.unit,
        "category": row.category,
        "comment": row.comment,
    }


@router.delete("/{material_id}")
async def delete_material(
        material_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Удалить материал"""
    result = await db.execute(
        text(
            """
                DELETE FROM material
                WHERE id = :material_id AND organization_id = :org_id
            """
        ),
        {"material_id": material_id, "org_id": ORG_ID},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await db.commit()
    return {"message": "Материал удален"}


@router.get("/stock", response_model=List[MaterialStockResponse])
async def get_all_stock(
        material_id: Optional[UUID] = Query(default=None),
        db: AsyncSession = Depends(get_db),
):
    """Получить остатки (все или по конкретному материалу)"""
    if material_id:
        query = text("""
            SELECT id, organization_id, material_id, qty, reserved_qty, updated_at
            FROM material_stock
            WHERE organization_id = :org_id AND material_id = :mat_id
        """)
        params = {"org_id": ORG_ID, "mat_id": material_id}
    else:
        query = text("""
            SELECT s.id, s.organization_id, s.material_id,
                   s.qty, s.reserved_qty, s.updated_at
            FROM material_stock s
            JOIN material m ON m.id = s.material_id
            WHERE s.organization_id = :org_id
            ORDER BY m.name
        """)
        params = {"org_id": ORG_ID}

    result = await db.execute(query, params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "material_id": row.material_id,
            "qty": float(row.qty),
            "reserved_qty": float(row.reserved_qty),
            "updated_at": row.updated_at,
        }
        for row in result.fetchall()
    ]


@router.put("/{material_id}/stock", response_model=MaterialStockResponse)
async def update_material_stock(
        material_id: UUID,
        stock: MaterialStockUpdate,
        db: AsyncSession = Depends(get_db),
):
    """Обновить остатки материала"""
    update_data = stock.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE material_stock
            SET {set_clause}, updated_at = NOW()
            WHERE material_id = :material_id AND organization_id = :org_id
            RETURNING id, organization_id, material_id, qty, reserved_qty, updated_at
        """
    )
    params = {"material_id": material_id, "org_id": ORG_ID, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Остатки не найдены")

    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "material_id": row.material_id,
        "qty": float(row.qty),
        "reserved_qty": float(row.reserved_qty),
        "updated_at": row.updated_at,
    }