# backend/app/api/v1/recipes.py
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from .material_models import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
)
from app.auth.dependencies import get_current_org_id, get_db_session

router = APIRouter(prefix="/api/v1/recipes", tags=["Рецептуры"])


@router.get("/", response_model=List[RecipeResponse])
async def get_all_recipes(
        product_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить все рецепты с компонентами"""
    if product_id:
        query = text("""
            SELECT r.id, r.organization_id, r.product_id,
            r.base_volume_kg, r.comment,
            p.name as product_name, p.code as product_code
            FROM recipe r
            LEFT JOIN product p ON p.id = r.product_id
            WHERE r.organization_id = :org_id AND r.product_id = :product_id
            ORDER BY p.name
        """)
        params = {"org_id": org_id, "product_id": product_id}
    else:
        query = text("""
            SELECT r.id, r.organization_id, r.product_id,
            r.base_volume_kg, r.comment,
            p.name as product_name, p.code as product_code
            FROM recipe r
            LEFT JOIN product p ON p.id = r.product_id
            WHERE r.organization_id = :org_id
            ORDER BY p.name
        """)
        params = {"org_id": org_id}

    result = await db.execute(query, params)
    recipes = []
    for row in result.fetchall():
        items_result = await db.execute(
            text("""
                SELECT ri.id, ri.recipe_id, ri.material_id, ri.qty_per_base,
                m.name as material_name, m.code as material_code,
                m.unit as material_unit
                FROM recipe_item ri
                LEFT JOIN material m ON m.id = ri.material_id
                WHERE ri.recipe_id = :recipe_id
                ORDER BY m.name
            """),
            {"recipe_id": row.id},
        )
        items = [
            {
                "id": item.id,
                "recipe_id": item.recipe_id,
                "material_id": item.material_id,
                "qty_per_base": float(item.qty_per_base),
                "material_name": item.material_name,
                "material_code": item.material_code,
                "material_unit": item.material_unit,
            }
            for item in items_result.fetchall()
        ]
        recipes.append(
            {
                "id": row.id,
                "organization_id": row.organization_id,
                "product_id": row.product_id,
                "base_volume_kg": float(row.base_volume_kg),
                "comment": row.comment,
                "product_name": row.product_name,
                "product_code": row.product_code,
                "items": items,
            }
        )
    return recipes


@router.post("/", response_model=RecipeResponse, status_code=201)
async def create_recipe(
        recipe: RecipeCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Создать рецепт с компонентами"""
    new_id = uuid4()
    result = await db.execute(
        text("""
            INSERT INTO recipe
            (id, organization_id, product_id, base_volume_kg, comment)
            VALUES
            (:id, :org_id, :product_id, :base_volume, :comment)
            RETURNING id, organization_id, product_id, base_volume_kg, comment
        """),
        {
            "id": new_id,
            "org_id": org_id,
            "product_id": recipe.product_id,
            "base_volume": recipe.base_volume_kg,
            "comment": recipe.comment,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать рецепт")

    # Добавляем компоненты рецепта
    for item in recipe.items:
        await db.execute(
            text("""
                INSERT INTO recipe_item
                (recipe_id, material_id, qty_per_base)
                VALUES (:recipe_id, :material_id, :qty)
            """),
            {
                "recipe_id": new_id,
                "material_id": item.material_id,
                "qty": item.qty_per_base,
            },
        )

    await db.commit()
    return await _get_recipe_by_id(db, new_id)


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
        recipe_id: UUID,
        recipe: RecipeUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить рецепт (только базовые поля)"""
    update_data = recipe.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE recipe
            SET {set_clause}
            WHERE id = :recipe_id AND organization_id = :org_id
            RETURNING id, organization_id, product_id, base_volume_kg, comment
        """
    )
    params = {"recipe_id": recipe_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Рецепт не найден")
    await db.commit()
    return await _get_recipe_by_id(db, recipe_id)


@router.delete("/{recipe_id}")
async def delete_recipe(
        recipe_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить рецепт (компоненты удалятся по CASCADE)"""
    result = await db.execute(
        text(
            """
                DELETE FROM recipe
                WHERE id = :recipe_id AND organization_id = :org_id
            """
        ),
        {"recipe_id": recipe_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Рецепт не найден")
    await db.commit()
    return {"message": "Рецепт удален"}


@router.post("/{recipe_id}/items", response_model=dict)
async def add_recipe_item(
        recipe_id: UUID,
        material_id: UUID,
        qty_per_base: float,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Добавить компонент к рецепту"""
    new_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO recipe_item
            (id, recipe_id, material_id, qty_per_base)
            VALUES (:id, :recipe_id, :material_id, :qty)
        """),
        {
            "id": new_id,
            "recipe_id": recipe_id,
            "material_id": material_id,
            "qty": qty_per_base,
        },
    )
    await db.commit()
    return {"id": str(new_id), "message": "Компонент добавлен"}


@router.delete("/{recipe_id}/items/{item_id}")
async def delete_recipe_item(
        recipe_id: UUID,
        item_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить компонент из рецепта"""
    result = await db.execute(
        text(
            """
                DELETE FROM recipe_item
                WHERE id = :item_id AND recipe_id = :recipe_id
            """
        ),
        {"item_id": item_id, "recipe_id": recipe_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Компонент не найден")
    await db.commit()
    return {"message": "Компонент удален"}


async def _get_recipe_by_id(db: AsyncSession, recipe_id: UUID) -> dict:
    """Вспомогательная функция для получения полного рецепта по ID"""
    result = await db.execute(
        text("""
            SELECT r.id, r.organization_id, r.product_id,
            r.base_volume_kg, r.comment,
            p.name as product_name, p.code as product_code
            FROM recipe r
            LEFT JOIN product p ON p.id = r.product_id
            WHERE r.id = :recipe_id
        """),
        {"recipe_id": recipe_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    items_result = await db.execute(
        text("""
            SELECT ri.id, ri.recipe_id, ri.material_id, ri.qty_per_base,
            m.name as material_name, m.code as material_code,
            m.unit as material_unit
            FROM recipe_item ri
            LEFT JOIN material m ON m.id = ri.material_id
            WHERE ri.recipe_id = :recipe_id
            ORDER BY m.name
        """),
        {"recipe_id": recipe_id},
    )
    items = [
        {
            "id": item.id,
            "recipe_id": item.recipe_id,
            "material_id": item.material_id,
            "qty_per_base": float(item.qty_per_base),
            "material_name": item.material_name,
            "material_code": item.material_code,
            "material_unit": item.material_unit,
        }
        for item in items_result.fetchall()
    ]
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "product_id": row.product_id,
        "base_volume_kg": float(row.base_volume_kg),
        "comment": row.comment,
        "product_name": row.product_name,
        "product_code": row.product_code,
        "items": items,
    }