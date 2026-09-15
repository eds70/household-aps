# backend/app/api/v1/products.py
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from .product_models import ProductCreate, ProductUpdate, ProductResponse
from app.auth.dependencies import get_current_org_id, get_db_session

router = APIRouter(prefix="/api/v1/products", tags=["Продукты"])


@router.get("/", response_model=List[ProductResponse])
async def get_all_products(
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    if version_id:
        query = text("""
            SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
            FROM product_snapshot WHERE organization_id = :org_id AND version_id = :version_id ORDER BY type, name
        """)
        params = {"org_id": org_id, "version_id": version_id}
    else:
        query = text("""
            SELECT id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
            FROM product WHERE organization_id = :org_id ORDER BY type, name
        """)
        params = {"org_id": org_id}

    result = await db.execute(query, params)
    products_list = []
    for row in result.fetchall():
        products_list.append({
            "id": row.id,
            "organization_id": row.organization_id,
            "code": row.code,
            "name": row.name,
            "type": row.type,
            "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0,
            "requires_heating": row.requires_heating,
            "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
            "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None,
            "parent_pf_id": row.parent_pf_id,
        })
    return products_list


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
        product: ProductCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    new_id = str(uuid4())
    result = await db.execute(text("""
        INSERT INTO product (id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id)
        VALUES (:id, :org_id, :code, :name, :type, :viscosity, :requires_heating, :bottle_volume, :fill_speed, :parent_pf_id)
        RETURNING id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id
    """), {
        "id": new_id,
        "org_id": org_id,
        "code": product.code,
        "name": product.name,
        "type": product.type,
        "viscosity": product.viscosity_coeff,
        "requires_heating": product.requires_heating,
        "bottle_volume": product.bottle_volume_l,
        "fill_speed": product.fill_speed_per_min,
        "parent_pf_id": product.parent_pf_id,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать продукт")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "code": row.code,
        "name": row.name,
        "type": row.type,
        "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0,
        "requires_heating": row.requires_heating,
        "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
        "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None,
        "parent_pf_id": row.parent_pf_id,
    }


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
        product_id: UUID,
        product: ProductUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    update_data = product.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"UPDATE product SET {set_clause} "
        f"WHERE id = :product_id AND organization_id = :org_id "
        f"RETURNING id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id"
    )
    params = {"product_id": product_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "code": row.code,
        "name": row.name,
        "type": row.type,
        "viscosity_coeff": float(row.viscosity_coeff) if row.viscosity_coeff else 1.0,
        "requires_heating": row.requires_heating,
        "bottle_volume_l": float(row.bottle_volume_l) if row.bottle_volume_l else None,
        "fill_speed_per_min": float(row.fill_speed_per_min) if row.fill_speed_per_min else None,
        "parent_pf_id": row.parent_pf_id,
    }


@router.delete("/{product_id}")
async def delete_product(
        product_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        text("DELETE FROM product WHERE id = :product_id AND organization_id = :org_id"),
        {"product_id": product_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await db.commit()
    return {"message": "Продукт удален"}