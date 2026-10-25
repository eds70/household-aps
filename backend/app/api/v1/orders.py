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
    # Итерация 24
    AutoSplitOptimizedRequest,
    AutoSplitOptimizedResponse,
    AutoSplitBatchResult,
    AutoSplitReactorSummary,
)

router = APIRouter(prefix="/api/v1/orders", tags=["Производственные заказы"])


# ==========================================
# Итерация 17.5 (fix): определение продукта партии
# ==========================================
# Продукт партии всегда выводится из заказа:
#   COALESCE(product.parent_pf_id, product.id)
# ==========================================

async def _resolve_batch_product_id(
        db: AsyncSession,
        order_id: UUID,
        org_id: UUID,
) -> UUID:
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


# ==========================================
# ИТЕРАЦИЯ 24 (fix #units):
# Пересчёт target_qty (штуки ГП) → target_kg (килограммы ПФ)
# ==========================================

async def _resolve_target_kg(
        db: AsyncSession,
        order_id: UUID,
        org_id: UUID,
) -> tuple[float, str, Optional[float]]:
    """
    Возвращает (target_kg, target_unit, bottle_volume_l).

    Логика:
      - Если заказ на ПФ (product.type = 'PF') — target_qty уже в кг.
      - Если заказ на ГП (product.type = 'GP') — target_qty × bottle_volume_l.

    bottle_volume_l берётся из product (для ГП). Для ПФ = None.

    Raises:
        HTTPException(404) — заказ или продукт не найдены.
        HTTPException(400) — у ГП нет bottle_volume_l, или target_qty ≤ 0.
    """
    result = await db.execute(
        text("""
            SELECT o.target_qty,
                   o.product_id,
                   p.type AS product_type,
                   p.code AS product_code,
                   p.bottle_volume_l
            FROM production_order o
            JOIN product p ON p.id = o.product_id
            WHERE o.id = :order_id AND o.organization_id = :org_id
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    target_qty = float(row.target_qty)
    if target_qty <= 0:
        raise HTTPException(
            status_code=400, detail="target_qty заказа должно быть > 0"
        )

    if row.product_type == "GP":
        bottle_volume_l = row.bottle_volume_l
        if bottle_volume_l is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"У ГП '{row.product_code}' не задан bottle_volume_l — "
                    f"невозможно пересчитать штуки в кг. Заполните поле "
                    f"в карточке продукта."
                ),
            )
        bottle_volume_l = float(bottle_volume_l)
        target_kg = target_qty * bottle_volume_l
        return target_kg, "kg", bottle_volume_l

    # PF — target_qty сразу в кг
    return target_qty, "kg", None


@router.get("/", response_model=List[ProductionOrderResponse])
async def get_all_orders(
        status: Optional[str] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
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


# ==========================================
# Старый endpoint: auto-split на ОДИН реактор
# ==========================================

@router.post("/{order_id}/auto-split")
async def auto_split_order(
        order_id: UUID,
        equipment_id: UUID,
        max_fill_percent: float = 0.70,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Автоматически разбить заказ на партии по объёму ОДНОГО реактора.

    Итерация 24 (fix #units): target_qty (штуки ГП) пересчитывается
    в target_kg через bottle_volume_l.

    Для оптимального распределения между НЕСКОЛЬКИМИ реакторами
    используйте /auto-split-optimized.
    """
    effective_product_id = await _resolve_batch_product_id(db, order_id, org_id)

    # target в КГ (с пересчётом из штук для ГП)
    target_kg, _, _ = await _resolve_target_kg(db, order_id, org_id)

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

    max_batch = float(eq_row.volume_kg) * max_fill_percent
    num_batches = int(target_kg / max_batch) + (
        1 if target_kg % max_batch > 0 else 0
    )

    created_batches = []
    remaining_qty = target_kg

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
        "target_qty": target_kg,
        "equipment": eq_row.name,
        "max_batch_volume": max_batch,
        "batches_created": num_batches,
        "batches": created_batches,
    }


# ==========================================
# ИТЕРАЦИЯ 24: auto-split-optimized
# ==========================================

async def _find_compatible_reactors(
        db: AsyncSession,
        org_id: UUID,
        pf_id: UUID,
        equipment_ids: Optional[List[UUID]] = None,
) -> List[dict]:
    """
    Возвращает список реакторов, которые могут варить заданный ПФ.

    Жёсткая привязка: только те реакторы, для которых есть запись
    в equipment_capability с (equipment_id, product_id = pf_id).
    """
    params: dict = {"org_id": org_id, "pf_id": pf_id}
    filter_sql = ""

    if equipment_ids:
        params["equipment_ids"] = [str(e) for e in equipment_ids]
        filter_sql = "AND e.id::text = ANY(:equipment_ids)"

    result = await db.execute(
        text(f"""
            SELECT e.id AS equipment_id, e.name, e.volume_kg,
                   ec.max_fill_percent
            FROM equipment e
            JOIN equipment_capability ec ON ec.equipment_id = e.id
            WHERE ec.product_id = :pf_id
              AND e.organization_id = :org_id
              AND e.type = 'REACTOR'
              AND e.is_active = TRUE
              {filter_sql}
            ORDER BY e.volume_kg DESC
        """),
        params,
    )
    return [dict(row._mapping) for row in result.fetchall()]


def _plan_batches_greedy_makespan(
        reactors: List[dict],
        target_qty: float,
        max_fill_percent: float,
) -> List[dict]:
    batches: List[dict] = []
    loads: dict = {str(r["equipment_id"]): 0.0 for r in reactors}
    max_batch = {
        str(r["equipment_id"]): float(r["volume_kg"]) * max_fill_percent
        for r in reactors
    }
    by_id = {str(r["equipment_id"]): r for r in reactors}

    remaining = target_qty
    safety = 0
    MAX_ITER = 10_000

    while remaining > 1e-6 and safety < MAX_ITER:
        safety += 1

        best_id = min(
            loads.keys(),
            key=lambda eid: (
                loads[eid] / max_batch[eid]
                if max_batch[eid] > 0 else float("inf")
            ),
        )
        batch_volume = min(max_batch[best_id], remaining)
        if batch_volume <= 1e-6:
            break

        batches.append({
            "equipment_id": best_id,
            "volume_kg": batch_volume,
            "equipment_name": by_id[best_id]["name"],
        })
        loads[best_id] += batch_volume
        remaining -= batch_volume

    return batches


def _plan_batches_round_robin(
        reactors: List[dict],
        target_qty: float,
        max_fill_percent: float,
) -> List[dict]:
    batches: List[dict] = []
    if not reactors:
        return batches

    remaining = target_qty
    idx = 0
    safety = 0
    MAX_ITER = 10_000

    while remaining > 1e-6 and safety < MAX_ITER:
        safety += 1
        r = reactors[idx % len(reactors)]
        idx += 1
        cap = float(r["volume_kg"]) * max_fill_percent
        batch_volume = min(cap, remaining)
        if batch_volume <= 1e-6:
            continue
        batches.append({
            "equipment_id": str(r["equipment_id"]),
            "volume_kg": batch_volume,
            "equipment_name": r["name"],
        })
        remaining -= batch_volume

    return batches


def _plan_batches_proportional(
        reactors: List[dict],
        target_qty: float,
        max_fill_percent: float,
) -> List[dict]:
    batches: List[dict] = []
    if not reactors:
        return batches

    total_capacity = sum(
        float(r["volume_kg"]) * max_fill_percent for r in reactors
    )
    if total_capacity <= 1e-6:
        return batches

    remaining = target_qty
    for r in reactors:
        cap = float(r["volume_kg"]) * max_fill_percent
        share = cap / total_capacity
        want = target_qty * share
        while want > 1e-6 and remaining > 1e-6:
            batch_volume = min(cap, want, remaining)
            if batch_volume <= 1e-6:
                break
            batches.append({
                "equipment_id": str(r["equipment_id"]),
                "volume_kg": batch_volume,
                "equipment_name": r["name"],
            })
            remaining -= batch_volume
            want -= batch_volume

    if remaining > 1e-6:
        biggest = max(reactors, key=lambda x: x["volume_kg"])
        cap = float(biggest["volume_kg"]) * max_fill_percent
        while remaining > 1e-6:
            batch_volume = min(cap, remaining)
            batches.append({
                "equipment_id": str(biggest["equipment_id"]),
                "volume_kg": batch_volume,
                "equipment_name": biggest["name"],
            })
            remaining -= batch_volume

    return batches


def _plan_batches_equal_split(
        reactors: List[dict],
        target_qty: float,
        max_fill_percent: float,
) -> List[dict]:
    if not reactors:
        return []

    min_cap = min(
        float(r["volume_kg"]) * max_fill_percent for r in reactors
    )
    if min_cap <= 1e-6:
        return []

    batches: List[dict] = []
    remaining = target_qty
    idx = 0
    safety = 0

    while remaining > 1e-6 and safety < 10_000:
        safety += 1
        r = reactors[idx % len(reactors)]
        idx += 1
        batch_volume = min(min_cap, remaining)
        batches.append({
            "equipment_id": str(r["equipment_id"]),
            "volume_kg": batch_volume,
            "equipment_name": r["name"],
        })
        remaining -= batch_volume

    return batches


STRATEGY_MAP = {
    "greedy_makespan": _plan_batches_greedy_makespan,
    "round_robin": _plan_batches_round_robin,
    "proportional": _plan_batches_proportional,
    "equal_split": _plan_batches_equal_split,
}


@router.post(
    "/{order_id}/auto-split-optimized",
    response_model=AutoSplitOptimizedResponse,
)
async def auto_split_optimized(
        order_id: UUID,
        request: AutoSplitOptimizedRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Оптимально распределить заказ между реакторами.

    Итерация 24. Алгоритм:
      1. Определяем ПФ заказа (COALESCE(parent_pf_id, id)).
      2. Пересчитываем target_qty → target_kg (для ГП — ×bottle_volume_l).
      3. Находим все реакторы, способные варить ПФ (equipment_capability).
      4. Применяем стратегию (default: greedy_makespan).
      5. Создаём партии в БД с assigned_equipment_id.

    Итерация 26 (fix #idempotency):
      - Если у заказа уже есть партии со статусом NOT_STARTED,
        возвращаем 409 Conflict. Эндпоинт не идемпотентен.
    """
    strategy = request.strategy
    if strategy not in STRATEGY_MAP:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Неизвестная стратегия '{strategy}'. "
                f"Доступно: {list(STRATEGY_MAP.keys())}"
            ),
        )

    # 1. ПФ заказа
    effective_product_id = await _resolve_batch_product_id(db, order_id, org_id)

    # 2. target в КГ (с пересчётом из штук для ГП)
    target_kg, _, bottle_volume_l = await _resolve_target_kg(
        db, order_id, org_id,
    )

    # ==========================================
    # Итерация 26 (fix #idempotency):
    # Защита от дублей — если у заказа уже есть партии
    # со статусом NOT_STARTED, отказываем.
    # ==========================================
    existing_count_res = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM batch
            WHERE order_id = :order_id
              AND organization_id = :org_id
              AND status = 'NOT_STARTED'
        """),
        {"order_id": order_id, "org_id": org_id},
    )
    existing_count = existing_count_res.scalar() or 0
    if existing_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"У заказа уже есть {existing_count} партий со статусом "
                f"NOT_STARTED. Удалите их перед повторным вызовом "
                f"auto-split-optimized (эндпоинт не идемпотентен)."
            ),
        )

    # 3. Совместимые реакторы (по capability)
    reactors = await _find_compatible_reactors(
        db, org_id, effective_product_id, request.equipment_ids,
    )
    if not reactors:
        raise HTTPException(
            status_code=404,
            detail=(
                "Не найдено ни одного реактора, способного варить ПФ "
                "этого заказа (по equipment_capability). "
                "Проверьте справочник «Оборудование → Capability»."
            ),
        )

    # 4. Планируем партии
    planner = STRATEGY_MAP[strategy]
    planned = planner(
        reactors=reactors,
        target_qty=target_kg,
        max_fill_percent=request.max_fill_percent,
    )
    if not planned:
        raise HTTPException(
            status_code=400,
            detail="Не удалось спланировать партии (проверьте объёмы реакторов)",
        )

    # 5. Создаём партии в БД
    created_batches: List[AutoSplitBatchResult] = []
    per_reactor_acc: dict = {}

    try:
        for plan in planned:
            new_batch_id = uuid4()
            await db.execute(
                text("""
                    INSERT INTO batch
                    (id, organization_id, order_id, product_id, volume_kg,
                     assigned_equipment_id, status)
                    VALUES
                    (:id, :org_id, :order_id, :product_id, :volume_kg,
                     :eq_id, 'NOT_STARTED')
                """),
                {
                    "id": new_batch_id,
                    "org_id": org_id,
                    "order_id": order_id,
                    "product_id": effective_product_id,
                    "volume_kg": plan["volume_kg"],
                    "eq_id": plan["equipment_id"],
                },
            )
            created_batches.append(AutoSplitBatchResult(
                batch_id=new_batch_id,
                volume_kg=plan["volume_kg"],
                equipment_id=UUID(plan["equipment_id"]),
                equipment_name=plan["equipment_name"],
            ))
            key = plan["equipment_id"]
            if key not in per_reactor_acc:
                per_reactor_acc[key] = {
                    "count": 0,
                    "total": 0.0,
                    "name": plan["equipment_name"],
                }
            per_reactor_acc[key]["count"] += 1
            per_reactor_acc[key]["total"] += plan["volume_kg"]

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # 6. Сводка per_reactor
    reactors_by_id = {str(r["equipment_id"]): r for r in reactors}
    per_reactor: List[AutoSplitReactorSummary] = []
    for eq_id_str, acc in per_reactor_acc.items():
        r = reactors_by_id[eq_id_str]
        cap = float(r["volume_kg"]) * request.max_fill_percent
        per_reactor.append(AutoSplitReactorSummary(
            equipment_id=UUID(eq_id_str),
            equipment_name=acc["name"],
            max_batch_volume=cap,
            batches_count=acc["count"],
            total_volume_kg=acc["total"],
            load_percent=(
                (acc["total"] / cap * 100.0) if cap > 0 else 0.0
            ),
        ))

    # 7. Код продукта (для ответа)
    prod_res = await db.execute(
        text("SELECT code FROM product WHERE id = :id"),
        {"id": effective_product_id},
    )
    prod_row = prod_res.fetchone()
    product_code = prod_row.code if prod_row else None

    unit_msg = ""
    if bottle_volume_l is not None:
        unit_msg = f" (bottle_volume_l={bottle_volume_l})"

    return AutoSplitOptimizedResponse(
        order_id=order_id,
        product_id=effective_product_id,
        product_code=product_code,
        target_qty=target_kg,
        strategy=strategy,
        total_batches_created=len(created_batches),
        batches=created_batches,
        per_reactor=per_reactor,
        message=(
            f"Создано {len(created_batches)} партий на "
            f"{len(per_reactor)} реакторах (стратегия: {strategy}). "
            f"Объём: {target_kg:.0f} кг{unit_msg}"
        ),
    )


async def _get_order_by_id(db: AsyncSession, order_id: UUID, org_id: UUID) -> dict:
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