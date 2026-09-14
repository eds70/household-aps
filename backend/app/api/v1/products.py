from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from uuid import UUID, uuid4
from .product_models import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/api/v1/products", tags=["Продукты"])
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

@router.get("/", response_model=List[ProductResponse])
async def get_all_products(
        version_id: Optional[UUID] = Query(default=None),
        db: AsyncSession = Depends(get_db)
):
    if version_id:
        query = text("""
            SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
            FROM product_snapshot WHERE organization_id = :org_id AND version_id = :version_id ORDER BY type, name
        """)
        params = {"org_id": ORG_ID, "version_id": version_id}
    else:
        query = text("""
            SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
            FROM product WHERE organization_id = :org_id ORDER BY type, name
        """)
        params = {"org_id": ORG_ID}

    result = await db.execute(query, params)
    products_list = []
    for row in result.fetchall():
        products_list.append({
            "id": row.id, "organization_id": row.organization_id, "code": row.code, "name": row.name, "type": row.type,
            "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0,
            "requires_heating": row.requires_heating,
            "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
            "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None,
            "parent_pf_id": row.parent_pf_id,
        })
    return products_list

@router.post("/", response_model=ProductResponse)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    new_id = str(uuid4())
    result = await db.execute(text("""
        INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id)
        VALUES (:id, :org_id, :code, :name, :type, :viscosity, :requires_heating, :bottle_volume, :fill_speed, :parent_pf_id)
        RETURNING id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
    """), {
        "id": new_id, "org_id": product.organization_id, "code": product.code, "name": product.name, "type": product.type,
        "viscosity": product.viscosity_coeff, "requires_heating": product.requires_heating,
        "bottle_volume": product.bottle_volume_l, "fill_speed": product.fill_speed_per_min, "parent_pf_id": product.parent_pf_id,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать продукт")
    await db.commit()
    return {
        "id": row.id, "organization_id": row.organization_id, "code": row.code, "name": row.name, "type": row.type,
        "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0, "requires_heating": row.requires_heating,
        "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
        "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None, "parent_pf_id": row.parent_pf_id,
    }

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: UUID, product: ProductUpdate, db: AsyncSession = Depends(get_db)):
    update_data = product.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = f"UPDATE product SET {set_clause} WHERE id = :product_id AND organization_id = :org_id RETURNING id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id"
    params = {"product_id": product_id, "org_id": ORG_ID, **update_data}
    result = await db.execute(text(query), params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await db.commit()
    return {
        "id": row.id, "organization_id": row.organization_id, "code": row.code, "name": row.name, "type": row.type,
        "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0, "requires_heating": row.requires_heating,
        "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
        "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None, "parent_pf_id": row.parent_pf_id,
    }

@router.delete("/{product_id}")
async def delete_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("DELETE FROM product WHERE id = :product_id AND organization_id = :org_id"), {"product_id": product_id, "org_id": ORG_ID})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await db.commit()
    return {"message": "Продукт удален"}