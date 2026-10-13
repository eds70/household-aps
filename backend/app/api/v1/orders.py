# backend/app/api/v1/orders.py
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from .material_models import (
    ProductionOrderCreate,
    ProductionOrderUpdate,
    ProductionOrderResponse,
    BatchCreate,
    BatchUpdate,
    BatchResponse,
)

router = APIRouter(prefix="/api/v1/orders", tags=["Производственные заказы"])


# ==========================================
# Итерация 17.5 (fix): определение продукта партии
# ==========================================
# Проблема: заказы в UI создаются на ГП (type='GP'), а operation_template
# заведены на ПФ (type='PF'). Если партия создаётся с product_id = ГП, то
# build_routing() в routing.py возвращает [] → партия молча выпадает из
# плана (см. лог [routing] пропущена партия ...).
#
# Решение: продукт партии всегда выводится из заказа:
#   COALESCE(product.parent_pf_id, product.id)
# Для заказов на ПФ это даёт сам ПФ, для заказов на ГП — родительский ПФ.
# ==========================================

async def _resolve_batch_product_id(
        db: AsyncSession,
        order_id: UUID,
        org_id: UUID,
) -> UUID:
    """
    Возвращает эффективный product_id для партии заказа.

    Логика:
      - Берём product_id заказа.
      - Если у продукта задан parent_pf_id → используем его (ГП → ПФ).
      - Иначе → используем сам product_id (чисто-ПФ-заказ).

    Raises:
        HTTPException(404) — заказ или продукт не найдены.
    """
    result = await db.execute(
        text("""
            SELECT COALESCE(p.parent_pf_id, p.id) AS effective_product_id,
                   p.code AS product_code,
                   p.type AS product_type
            FROM production_order o
            JOIN product p ON p.id = o.product_id
            WHERE o.id = :order_id AND o.organization_id = :org_id
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Заказ не найден (или его продукт отсутствует)",
        )
    return row.effective_product_id


@router.get("/", response_model=List[ProductionOrderResponse])
async def get_all_orders(
        status: Optional[str] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить список заказов с количеством партий"""
    if status:
        query = text("""
            SELECT o.id, o.organization_id, o.product_id,
            o.target_qty, o.due_date, o.priority,
            o.status, o.created_at, o.comment,
            p.name as product_name, p.code as product_code,
            COUNT(b.id) as batches_count
            FROM production_order o
            LEFT JOIN product p ON p.id = o.product_id
            LEFT JOIN batch b ON b.order_id = o.id
            WHERE o.organization_id = :org_id AND o.status = :status
            GROUP BY o.id, p.name, p.code
            ORDER BY o.priority, o.due_date
        """)
        params = {"org_id": org_id, "status": status}
    else:
        query = text("""
            SELECT o.id, o.organization_id, o.product_id,
            o.target_qty, o.due_date, o.priority,
            o.status, o.created_at, o.comment,
            p.name as product_name, p.code as product_code,
            COUNT(b.id) as batches_count
            FROM production_order o
            LEFT JOIN product p ON p.id = o.product_id
            LEFT JOIN batch b ON b.order_id = o.id
            WHERE o.organization_id = :org_id
            GROUP BY o.id, p.name, p.code
            ORDER BY o.priority, o.due_date
        """)
        params = {"org_id": org_id}

    result = await db.execute(query, params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "product_id": row.product_id,
            "target_qty": float(row.target_qty),
            "due_date": row.due_date,
            "priority": row.priority,
            "status": row.status,
            "created_at": row.created_at,
            "comment": row.comment,
            "product_name": row.product_name,
            "product_code": row.product_code,
            "batches_count": row.batches_count,
        }
        for row in result.fetchall()
    ]


@router.post("/", response_model=ProductionOrderResponse, status_code=201)
async def create_order(
        order: ProductionOrderCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Создать производственный заказ"""
    new_id = uuid4()
    result = await db.execute(
        text("""
            INSERT INTO production_order
            (id, organization_id, product_id, target_qty, due_date, priority, comment)
            VALUES
            (:id, :org_id, :product_id, :target_qty, :due_date, :priority, :comment)
            RETURNING id, organization_id, product_id, target_qty, due_date,
            priority, status, created_at, comment
        """),
        {
            "id": new_id,
            "org_id": org_id,
            "product_id": order.product_id,
            "target_qty": order.target_qty,
            "due_date": order.due_date,
            "priority": order.priority,
            "comment": order.comment,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать заказ")
    await db.commit()
    return await _get_order_by_id(db, new_id, org_id)


@router.put("/{order_id}", response_model=ProductionOrderResponse)
async def update_order(
        order_id: UUID,
        order: ProductionOrderUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить заказ"""
    update_data = order.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE production_order
            SET {set_clause}
            WHERE id = :order_id AND organization_id = :org_id
            RETURNING id, organization_id, product_id, target_qty, due_date,
            priority, status, created_at, comment
        """
    )
    params = {"order_id": order_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    await db.commit()
    return await _get_order_by_id(db, order_id, org_id)


@router.delete("/{order_id}")
async def delete_order(
        order_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить заказ (партии удалятся по CASCADE)"""
    result = await db.execute(
        text(
            """
                DELETE FROM production_order
                WHERE id = :order_id AND organization_id = :org_id
            """
        ),
        {"order_id": order_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    await db.commit()
    return {"message": "Заказ удален"}


@router.get("/{order_id}/batches", response_model=List[BatchResponse])
async def get_order_batches(
        order_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить партии заказа"""
    result = await db.execute(
        text("""
            SELECT b.id, b.organization_id, b.order_id, b.product_id,
            b.volume_kg, b.assigned_equipment_id,
            b.planned_start, b.planned_end, b.status, b.comment,
            p.name as product_name, p.code as product_code,
            e.name as equipment_name
            FROM batch b
            LEFT JOIN product p ON p.id = b.product_id
            LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
            WHERE b.order_id = :order_id AND b.organization_id = :org_id
            ORDER BY b.planned_start
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "order_id": row.order_id,
            "product_id": row.product_id,
            "volume_kg": float(row.volume_kg),
            "assigned_equipment_id": row.assigned_equipment_id,
            "planned_start": row.planned_start,
            "planned_end": row.planned_end,
            "status": row.status,
            "comment": row.comment,
            "product_name": row.product_name,
            "product_code": row.product_code,
            "equipment_name": row.equipment_name,
        }
        for row in result.fetchall()
    ]


@router.post("/{order_id}/batches", response_model=BatchResponse, status_code=201)
async def create_batch(
        order_id: UUID,
        batch: BatchCreate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Создать партию для заказа.

    Итерация 17.5 (fix): продукт партии выводится из заказа —
    COALESCE(product.parent_pf_id, product.id). Поле batch.product_id
    больше не принимается от клиента.
    """
    effective_product_id = await _resolve_batch_product_id(db, order_id, org_id)

    new_id = uuid4()
    result = await db.execute(
        text("""
            INSERT INTO batch
            (id, organization_id, order_id, product_id, volume_kg,
            assigned_equipment_id, comment)
            VALUES
            (:id, :org_id, :order_id, :product_id, :volume_kg,
            :eq_id, :comment)
            RETURNING id, organization_id, order_id, product_id, volume_kg,
            assigned_equipment_id, planned_start, planned_end,
            status, comment
        """),
        {
            "id": new_id,
            "org_id": org_id,
            "order_id": order_id,
            "product_id": effective_product_id,
            "volume_kg": batch.volume_kg,
            "eq_id": batch.assigned_equipment_id,
            "comment": batch.comment,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать партию")
    await db.commit()
    return await _get_batch_by_id(db, new_id)


@router.put("/{order_id}/batches/{batch_id}", response_model=BatchResponse)
async def update_batch(
        order_id: UUID,
        batch_id: UUID,
        batch: BatchUpdate,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить партию"""
    update_data = batch.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE batch
            SET {set_clause}
            WHERE id = :batch_id AND order_id = :order_id
            AND organization_id = :org_id
            RETURNING id, organization_id, order_id, product_id, volume_kg,
            assigned_equipment_id, planned_start, planned_end,
            status, comment
        """
    )
    params = {
        "batch_id": batch_id,
        "order_id": order_id,
        "org_id": org_id,
        **update_data,
    }
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")
    await db.commit()
    return await _get_batch_by_id(db, batch_id)


@router.delete("/{order_id}/batches/{batch_id}")
async def delete_batch(
        order_id: UUID,
        batch_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить партию"""
    result = await db.execute(
        text(
            """
                DELETE FROM batch
                WHERE id = :batch_id AND order_id = :order_id
                AND organization_id = :org_id
            """
        ),
        {"batch_id": batch_id, "order_id": order_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Партия не найдена")
    await db.commit()
    return {"message": "Партия удалена"}


@router.post("/{order_id}/auto-split")
async def auto_split_order(
        order_id: UUID,
        equipment_id: UUID,
        max_fill_percent: float = 0.70,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Автоматически разбить заказ на партии по объёму оборудования.

    Итерация 17.5 (fix): продукт партии выводится из заказа —
    COALESCE(product.parent_pf_id, product.id). Раньше брался
    order.product_id (ГП), из-за чего партии выпадали из плана.
    """
    # Эффективный product_id для партии (ПФ для ГП-заказов).
    effective_product_id = await _resolve_batch_product_id(db, order_id, org_id)

    # Получаем target_qty заказа.
    order_result = await db.execute(
        text("""
            SELECT target_qty
            FROM production_order
            WHERE id = :order_id AND organization_id = :org_id
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    order_row = order_result.fetchone()
    if not order_row:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Получаем оборудование
    eq_result = await db.execute(
        text("""
            SELECT id, name, volume_kg
            FROM equipment
            WHERE id = :eq_id AND organization_id = :org_id
        """),
        {"eq_id": equipment_id, "org_id": org_id},
    )
    eq_row = eq_result.fetchone()
    if not eq_row:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")

    if not eq_row.volume_kg:
        raise HTTPException(
            status_code=400,
            detail="У оборудования не указан объём (volume_kg)",
        )

    target_qty = float(order_row.target_qty)
    max_batch = float(eq_row.volume_kg) * max_fill_percent
    num_batches = int(target_qty / max_batch) + (
        1 if target_qty % max_batch > 0 else 0
    )

    created_batches = []
    remaining_qty = target_qty

    for i in range(num_batches):
        batch_volume = min(max_batch, remaining_qty)
        batch_id = uuid4()

        await db.execute(
            text("""
                INSERT INTO batch
                (id, organization_id, order_id, product_id, volume_kg,
                assigned_equipment_id, status)
                VALUES
                (:id, :org_id, :order_id, :product_id, :volume_kg,
                :eq_id, 'NOT_STARTED')
                RETURNING id
            """),
            {
                "id": batch_id,
                "org_id": org_id,
                "order_id": order_id,
                "product_id": effective_product_id,
                "volume_kg": batch_volume,
                "eq_id": equipment_id,
            },
        )
        created_batches.append(
            {
                "batch_id": str(batch_id),
                "volume_kg": batch_volume,
                "equipment": eq_row.name,
            }
        )
        remaining_qty -= batch_volume

    await db.commit()

    return {
        "order_id": str(order_id),
        "target_qty": target_qty,
        "equipment": eq_row.name,
        "max_batch_volume": max_batch,
        "batches_created": num_batches,
        "batches": created_batches,
    }


async def _get_order_by_id(db: AsyncSession, order_id: UUID, org_id: UUID) -> dict:
    """Вспомогательная функция для получения заказа с количеством партий"""
    result = await db.execute(
        text("""
            SELECT o.id, o.organization_id, o.product_id,
            o.target_qty, o.due_date, o.priority,
            o.status, o.created_at, o.comment,
            p.name as product_name, p.code as product_code,
            COUNT(b.id) as batches_count
            FROM production_order o
            LEFT JOIN product p ON p.id = o.product_id
            LEFT JOIN batch b ON b.order_id = o.id
            WHERE o.id = :order_id AND o.organization_id = :org_id
            GROUP BY o.id, p.name, p.code
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "product_id": row.product_id,
        "target_qty": float(row.target_qty),
        "due_date": row.due_date,
        "priority": row.priority,
        "status": row.status,
        "created_at": row.created_at,
        "comment": row.comment,
        "product_name": row.product_name,
        "product_code": row.product_code,
        "batches_count": row.batches_count,
    }


async def _get_batch_by_id(db: AsyncSession, batch_id: UUID) -> dict:
    """Вспомогательная функция для получения партии"""
    result = await db.execute(
        text("""
            SELECT b.id, b.organization_id, b.order_id, b.product_id,
            b.volume_kg, b.assigned_equipment_id,
            b.planned_start, b.planned_end, b.status, b.comment,
            p.name as product_name, p.code as product_code,
            e.name as equipment_name
            FROM batch b
            LEFT JOIN product p ON p.id = b.product_id
            LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
            WHERE b.id = :batch_id
        """),
        {"batch_id": batch_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Партия не найдена")
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "order_id": row.order_id,
        "product_id": row.product_id,
        "volume_kg": float(row.volume_kg),
        "assigned_equipment_id": row.assigned_equipment_id,
        "planned_start": row.planned_start,
        "planned_end": row.planned_end,
        "status": row.status,
        "comment": row.comment,
        "product_name": row.product_name,
        "product_code": row.product_code,
        "equipment_name": row.equipment_name,
    }