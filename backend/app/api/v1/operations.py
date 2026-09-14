from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from uuid import UUID, uuid4
from .operation_models import OperationCreate, OperationUpdate, OperationResponse

router = APIRouter(prefix="/api/v1/operations", tags=["Технологические карты"])
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

@router.get("/", response_model=List[OperationResponse])
async def get_all_operations(
        version_id: Optional[UUID] = Query(default=None),
        db: AsyncSession = Depends(get_db)
):
    if version_id:
        query = text("""
            SELECT ot.id, ot.organization_id, ot.product_id, ot.stage_order, ot.name, ot.base_duration_mins,
            ot.is_setup, ot.is_parallel_group, ot.parallel_group_id, ot.needs_boiler, ot.needs_cooling_zone,
            ot.needs_operator, ot.needs_lab, ot.duration_formula, ot.comment, p.name as product_name
            FROM operation_snapshot ot LEFT JOIN product p ON p.id = ot.product_id
            WHERE ot.organization_id = :org_id AND ot.version_id = :version_id ORDER BY p.name, ot.stage_order
        """)
        params = {"org_id": ORG_ID, "version_id": version_id}
    else:
        query = text("""
            SELECT ot.id, ot.organization_id, ot.product_id, ot.stage_order, ot.name, ot.base_duration_mins,
            ot.is_setup, ot.is_parallel_group, ot.parallel_group_id, ot.needs_boiler, ot.needs_cooling_zone,
            ot.needs_operator, ot.needs_lab, ot.duration_formula, ot.comment, p.name as product_name
            FROM operation_template ot LEFT JOIN product p ON p.id = ot.product_id
            WHERE ot.organization_id = :org_id ORDER BY p.name, ot.stage_order
        """)
        params = {"org_id": ORG_ID}

    result = await db.execute(query, params)
    operations_list = []
    for row in result.fetchall():
        operations_list.append({
            "id": row.id, "organization_id": row.organization_id, "product_id": row.product_id, "stage_order": row.stage_order,
            "name": row.name, "base_duration_mins": row.base_duration_mins, "is_setup": row.is_setup,
            "is_parallel_group": row.is_parallel_group, "parallel_group_id": row.parallel_group_id,
            "needs_boiler": row.needs_boiler, "needs_cooling_zone": row.needs_cooling_zone,
            "needs_operator": row.needs_operator, "needs_lab": row.needs_lab,
            "duration_formula": row.duration_formula, "comment": row.comment, "product_name": row.product_name,
        })
    return operations_list

@router.post("/", response_model=OperationResponse)
async def create_operation(operation: OperationCreate, db: AsyncSession = Depends(get_db)):
    new_id = str(uuid4())
    result = await db.execute(text("""
        INSERT INTO operation_template (id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, comment)
        VALUES (:id, :org_id, :product_id, :stage_order, :name, :base_duration_mins, :is_setup, :is_parallel_group, :parallel_group_id, :needs_boiler, :needs_cooling_zone, :needs_operator, :needs_lab, :duration_formula, :comment)
        RETURNING id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, comment
    """), {
        "id": new_id, "org_id": operation.organization_id, "product_id": operation.product_id, "stage_order": operation.stage_order,
        "name": operation.name, "base_duration_mins": operation.base_duration_mins, "is_setup": operation.is_setup,
        "is_parallel_group": operation.is_parallel_group, "parallel_group_id": operation.parallel_group_id,
        "needs_boiler": operation.needs_boiler, "needs_cooling_zone": operation.needs_cooling_zone,
        "needs_operator": operation.needs_operator, "needs_lab": operation.needs_lab,
        "duration_formula": operation.duration_formula, "comment": operation.comment,
    })
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать операцию")
    await db.commit()

    product_result = await db.execute(text("SELECT name FROM product WHERE id = :product_id"), {"product_id": operation.product_id})
    product_row = product_result.fetchone()
    return {
        "id": row.id, "organization_id": row.organization_id, "product_id": row.product_id, "stage_order": row.stage_order,
        "name": row.name, "base_duration_mins": row.base_duration_mins, "is_setup": row.is_setup,
        "is_parallel_group": row.is_parallel_group, "parallel_group_id": row.parallel_group_id,
        "needs_boiler": row.needs_boiler, "needs_cooling_zone": row.needs_cooling_zone,
        "needs_operator": row.needs_operator, "needs_lab": row.needs_lab,
        "duration_formula": row.duration_formula, "comment": row.comment, "product_name": product_row.name if product_row else None,
    }

@router.put("/{operation_id}", response_model=OperationResponse)
async def update_operation(operation_id: UUID, operation: OperationUpdate, db: AsyncSession = Depends(get_db)):
    update_data = operation.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = f"UPDATE operation_template SET {set_clause} WHERE id = :operation_id AND organization_id = :org_id RETURNING id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, comment"
    params = {"operation_id": operation_id, "org_id": ORG_ID, **update_data}
    result = await db.execute(text(query), params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    await db.commit()

    product_result = await db.execute(text("SELECT name FROM product WHERE id = :product_id"), {"product_id": row.product_id})
    product_row = product_result.fetchone()
    return {
        "id": row.id, "organization_id": row.organization_id, "product_id": row.product_id, "stage_order": row.stage_order,
        "name": row.name, "base_duration_mins": row.base_duration_mins, "is_setup": row.is_setup,
        "is_parallel_group": row.is_parallel_group, "parallel_group_id": row.parallel_group_id,
        "needs_boiler": row.needs_boiler, "needs_cooling_zone": row.needs_cooling_zone,
        "needs_operator": row.needs_operator, "needs_lab": row.needs_lab,
        "duration_formula": row.duration_formula, "comment": row.comment, "product_name": product_row.name if product_row else None,
    }

@router.delete("/{operation_id}")
async def delete_operation(operation_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("DELETE FROM operation_template WHERE id = :operation_id AND organization_id = :org_id"), {"operation_id": operation_id, "org_id": ORG_ID})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    await db.commit()
    return {"message": "Операция удалена"}

@router.get("/products", response_model=List[dict])
async def get_products_for_operations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT id, name, code FROM product WHERE organization_id = :org_id AND type = 'PF' ORDER BY name"), {"org_id": ORG_ID})
    return [{"id": str(row.id), "name": row.name, "code": row.code} for row in result.fetchall()]