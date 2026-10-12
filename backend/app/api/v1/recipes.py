# backend/app/api/v1/recipes.py
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from .material_models import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeItemCreate,
)

router = APIRouter(prefix="/api/v1/recipes", tags=["Рецептуры"])


@router.get("/", response_model=List[RecipeResponse])
async def get_all_recipes(
        product_id: Optional[UUID] = Query(default=None),
        version_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Получить все рецепты с компонентами.

    Итерация 17.x: если version_id задан — читаем из снапшот-таблиц
    (recipe_snapshot / recipe_item_snapshot). Иначе — из живых
    recipe / recipe_item.
    """
    # Выбор источника
    if version_id:
        recipe_table = "recipe_snapshot"
        item_table = "recipe_item_snapshot"
        version_filter = "AND r.version_id = :version_id"
        base_params: dict = {"org_id": org_id, "version_id": version_id}
    else:
        recipe_table = "recipe"
        item_table = "recipe_item"
        version_filter = ""
        base_params = {"org_id": org_id}

    if product_id:
        query = text(f"""
            SELECT r.id, r.organization_id, r.product_id,
            r.base_volume_kg, r.comment,
            p.name as product_name, p.code as product_code
            FROM {recipe_table} r
            LEFT JOIN product p ON p.id = r.product_id
            WHERE r.organization_id = :org_id
              {version_filter}
              AND r.product_id = :product_id
            ORDER BY p.name
        """)
        params = {**base_params, "product_id": product_id}
    else:
        query = text(f"""
            SELECT r.id, r.organization_id, r.product_id,
            r.base_volume_kg, r.comment,
            p.name as product_name, p.code as product_code
            FROM {recipe_table} r
            LEFT JOIN product p ON p.id = r.product_id
            WHERE r.organization_id = :org_id
              {version_filter}
            ORDER BY p.name
        """)
        params = base_params

    result = await db.execute(query, params)

    recipes = []
    for row in result.fetchall():
        # Компоненты — из соответствующей item-таблицы
        if version_id:
            items_query = text(f"""
                SELECT ri.id, ri.recipe_id, ri.material_id, ri.qty_per_base,
                m.name as material_name, m.code as material_code,
                m.unit as material_unit
                FROM {item_table} ri
                LEFT JOIN material m ON m.id = ri.material_id
                WHERE ri.recipe_id = :recipe_id
                  AND ri.version_id = :version_id
                ORDER BY m.name
            """)
            items_params = {"recipe_id": row.id, "version_id": version_id}
        else:
            items_query = text(f"""
                SELECT ri.id, ri.recipe_id, ri.material_id, ri.qty_per_base,
                m.name as material_name, m.code as material_code,
                m.unit as material_unit
                FROM {item_table} ri
                LEFT JOIN material m ON m.id = ri.material_id
                WHERE ri.recipe_id = :recipe_id
                ORDER BY m.name
            """)
            items_params = {"recipe_id": row.id}

        items_result = await db.execute(items_query, items_params)
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


@router.post("/{recipe_id}/items", response_model=dict, status_code=201)
async def add_recipe_item(
        recipe_id: UUID,
        item: RecipeItemCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Добавить компонент к рецепту (JSON body)"""
    check = await db.execute(
        text("SELECT 1 FROM recipe WHERE id = :recipe_id AND organization_id = :org_id"),
        {"recipe_id": recipe_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Рецепт не найден")

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
            "material_id": item.material_id,
            "qty": item.qty_per_base,
        },
    )
    await db.commit()
    return {"id": str(new_id), "message": "Компонент добавлен"}


@router.put("/{recipe_id}/items/{item_id}", response_model=dict)
async def update_recipe_item(
        recipe_id: UUID,
        item_id: UUID,
        item: RecipeItemCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить компонент рецепта (qty_per_base). Inline-edit из UI."""
    check = await db.execute(
        text("SELECT 1 FROM recipe WHERE id = :recipe_id AND organization_id = :org_id"),
        {"recipe_id": recipe_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    result = await db.execute(
        text("""
            UPDATE recipe_item
            SET material_id = :material_id, qty_per_base = :qty
            WHERE id = :item_id AND recipe_id = :recipe_id
        """),
        {
            "item_id": item_id,
            "recipe_id": recipe_id,
            "material_id": item.material_id,
            "qty": item.qty_per_base,
        },
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Компонент не найден")
    await db.commit()
    return {"message": "Компонент обновлён"}


@router.delete("/{recipe_id}/items/{item_id}")
async def delete_recipe_item(
        recipe_id: UUID,
        item_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить компонент из рецепта"""
    check = await db.execute(
        text("SELECT 1 FROM recipe WHERE id = :recipe_id AND organization_id = :org_id"),
        {"recipe_id": recipe_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Рецепт не найден")

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
    """
    Вспомогательная функция для получения полного рецепта по ID.

    Работает только с ЖИВЫМИ таблицами — используется после
    create/update, где мутации идут в recipe/recipe_item.
    """
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