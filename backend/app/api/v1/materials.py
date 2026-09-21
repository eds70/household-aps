# backend/app/api/v1/materials.py
"""
API материалов.

Итерация 13.1: остатки в GET /, создание с initial_qty, upsert /stock.
Итерация 13.2: журнал изменений остатков, импорт/экспорт Excel.
"""
import io
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile,
)
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from .material_models import (
    MaterialCreate,
    MaterialImportResponse,
    MaterialImportRow,
    MaterialResponse,
    MaterialStockLogEntry,
    MaterialStockLogListResponse,
    MaterialStockLogRevertResponse,
    MaterialStockResponse,
    MaterialStockUpdate,
    MaterialUpdate, MaterialStockLogCleanupResponse,
)

router = APIRouter(prefix="/api/v1/materials", tags=["Материалы"])


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

async def _set_log_context(
        db: AsyncSession,
        user_id: Optional[str],
        source: str,
        reason: Optional[str] = None,
) -> None:
    """
    Устанавливает session variables для триггера material_stock_log.

    Вызывать ПЕРЕД любым INSERT/UPDATE/DELETE в material_stock,
    чтобы журнал записал корректный source и changed_by.
    """
    # set_config(name, value, is_local) — безопасная альтернатива SET LOCAL
    # с поддержкой параметров.
    await db.execute(
        text("SELECT set_config('app.current_user_id', :val, TRUE)"),
        {"val": user_id or ""},
    )
    await db.execute(
        text("SELECT set_config('app.change_source', :val, TRUE)"),
        {"val": source or "SYSTEM"},
    )
    await db.execute(
        text("SELECT set_config('app.change_reason', :val, TRUE)"),
        {"val": reason or ""},
    )


# ==========================================
# СПИСОК МАТЕРИАЛОВ С ОСТАТКАМИ (Итерация 13.1)
# ==========================================

@router.get("/", response_model=List[MaterialResponse])
async def get_all_materials(
        category: Optional[str] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить список материалов с остатками."""
    base_sql = """
        SELECT
            m.id, m.organization_id, m.code, m.name, m.unit, m.category, m.comment,
            COALESCE(ms.qty, 0) AS stock_qty,
            COALESCE(ms.reserved_qty, 0) AS reserved_qty
        FROM material m
        LEFT JOIN material_stock ms
            ON ms.material_id = m.id
           AND ms.organization_id = m.organization_id
        WHERE m.organization_id = :org_id
    """
    params = {"org_id": org_id}
    if category:
        base_sql += " AND m.category = :category"
        params["category"] = category
    base_sql += " ORDER BY m.name"

    result = await db.execute(text(base_sql), params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "code": row.code,
            "name": row.name,
            "unit": row.unit,
            "category": row.category,
            "comment": row.comment,
            "stock_qty": float(row.stock_qty) if row.stock_qty is not None else 0.0,
            "reserved_qty": float(row.reserved_qty) if row.reserved_qty is not None else 0.0,
        }
        for row in result.fetchall()
    ]


# ==========================================
# ЖУРНАЛ ИЗМЕНЕНИЙ ОСТАТКОВ (Итерация 13.2)
# ==========================================
# ВАЖНО: размещаем ДО /{material_id}, чтобы "stock-log" не был распарсен
# как UUID.

@router.get("/stock-log", response_model=MaterialStockLogListResponse)
async def get_stock_log(
        material_id: Optional[UUID] = Query(default=None),
        source: Optional[str] = Query(
            default=None,
            description="MANUAL | IMPORT | SYSTEM",
        ),
        date_from: Optional[datetime] = Query(default=None),
        date_to: Optional[datetime] = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Общий журнал изменений остатков с фильтрами."""
    where_clauses = ["l.organization_id = :org_id"]
    params: dict = {"org_id": org_id, "limit": limit}

    if material_id:
        where_clauses.append("l.material_id = :material_id")
        params["material_id"] = material_id
    if source:
        where_clauses.append("l.source = :source")
        params["source"] = source
    if date_from:
        where_clauses.append("l.changed_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("l.changed_at <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(where_clauses)

    # Общее количество
    count_result = await db.execute(
        text(f"SELECT COUNT(*) AS cnt FROM material_stock_log l WHERE {where_sql}"),
        params,
    )
    total = int(count_result.fetchone().cnt or 0)

    # Сами записи
    result = await db.execute(
        text(f"""
            SELECT
                l.id, l.organization_id, l.material_id, l.action,
                l.old_qty, l.new_qty, l.old_reserved_qty, l.new_reserved_qty,
                l.delta_qty, l.delta_reserved_qty,
                l.changed_at, l.changed_by, l.source, l.reason, l.comment,
                m.code   AS material_code,
                m.name   AS material_name,
                m.unit   AS material_unit,
                u.full_name AS changed_by_name
            FROM material_stock_log l
            LEFT JOIN material m ON m.id = l.material_id
            LEFT JOIN app_user u ON u.id = l.changed_by
            WHERE {where_sql}
            ORDER BY l.changed_at DESC
            LIMIT :limit
        """),
        params,
    )

    def _f(v):
        return float(v) if v is not None else None

    entries = [
        MaterialStockLogEntry(
            id=row.id,
            organization_id=row.organization_id,
            material_id=row.material_id,
            material_code=row.material_code,
            material_name=row.material_name,
            material_unit=row.material_unit,
            action=row.action,
            old_qty=_f(row.old_qty),
            new_qty=_f(row.new_qty),
            old_reserved_qty=_f(row.old_reserved_qty),
            new_reserved_qty=_f(row.new_reserved_qty),
            delta_qty=_f(row.delta_qty),
            delta_reserved_qty=_f(row.delta_reserved_qty),
            changed_at=row.changed_at,
            changed_by=row.changed_by,
            changed_by_name=row.changed_by_name,
            source=row.source,
            reason=row.reason,
            comment=row.comment,
        )
        for row in result.fetchall()
    ]

    return MaterialStockLogListResponse(entries=entries, total=total)


@router.get("/{material_id}/log", response_model=List[MaterialStockLogEntry])
async def get_material_log(
        material_id: UUID,
        limit: int = Query(default=100, ge=1, le=500),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Журнал изменений остатков для одного материала."""
    # Проверяем, что материал существует
    check = await db.execute(
        text("""
            SELECT id FROM material
            WHERE id = :material_id AND organization_id = :org_id
        """),
        {"material_id": material_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Материал не найден")

    result = await db.execute(
        text("""
            SELECT
                l.id, l.organization_id, l.material_id, l.action,
                l.old_qty, l.new_qty, l.old_reserved_qty, l.new_reserved_qty,
                l.delta_qty, l.delta_reserved_qty,
                l.changed_at, l.changed_by, l.source, l.reason, l.comment,
                m.code AS material_code,
                m.name AS material_name,
                m.unit AS material_unit,
                u.full_name AS changed_by_name
            FROM material_stock_log l
            LEFT JOIN material m ON m.id = l.material_id
            LEFT JOIN app_user u ON u.id = l.changed_by
            WHERE l.organization_id = :org_id
              AND l.material_id = :material_id
            ORDER BY l.changed_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "material_id": material_id, "limit": limit},
    )

    def _f(v):
        return float(v) if v is not None else None

    return [
        MaterialStockLogEntry(
            id=row.id,
            organization_id=row.organization_id,
            material_id=row.material_id,
            material_code=row.material_code,
            material_name=row.material_name,
            material_unit=row.material_unit,
            action=row.action,
            old_qty=_f(row.old_qty),
            new_qty=_f(row.new_qty),
            old_reserved_qty=_f(row.old_reserved_qty),
            new_reserved_qty=_f(row.new_reserved_qty),
            delta_qty=_f(row.delta_qty),
            delta_reserved_qty=_f(row.delta_reserved_qty),
            changed_at=row.changed_at,
            changed_by=row.changed_by,
            changed_by_name=row.changed_by_name,
            source=row.source,
            reason=row.reason,
            comment=row.comment,
        )
        for row in result.fetchall()
    ]


# ==========================================
# СОЗДАНИЕ МАТЕРИАЛА С НАЧАЛЬНЫМ ОСТАТКОМ
# ==========================================

@router.post("/", response_model=MaterialResponse, status_code=201)
async def create_material(
        material: MaterialCreate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Создать материал + запись об остатках с initial_qty."""
    # Контекст для триггера
    await _set_log_context(
        db,
        user_id=current_user.get("user_id"),
        source="MANUAL",
        reason=f"Создание материала {material.code}",
    )

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
            "org_id": org_id,
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

    initial_qty = material.initial_qty or 0.0
    initial_reserved = material.initial_reserved_qty or 0.0

    # INSERT в material_stock → триггер запишет INSERT в лог
    await db.execute(
        text("""
            INSERT INTO material_stock
            (organization_id, material_id, qty, reserved_qty)
            VALUES (:org_id, :mat_id, :qty, :reserved)
            ON CONFLICT (organization_id, material_id)
            DO UPDATE SET
                qty = EXCLUDED.qty,
                reserved_qty = EXCLUDED.reserved_qty,
                updated_at = NOW()
        """),
        {
            "org_id": org_id,
            "mat_id": new_id,
            "qty": initial_qty,
            "reserved": initial_reserved,
        },
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
        "stock_qty": float(initial_qty),
        "reserved_qty": float(initial_reserved),
    }


# ==========================================
# ОБНОВЛЕНИЕ СПРАВОЧНЫХ ПОЛЕЙ МАТЕРИАЛА
# ==========================================

@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
        material_id: UUID,
        material: MaterialUpdate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить справочные поля материала (не трогает остатки)."""
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
    params = {"material_id": material_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Материал не найден")

    stock_result = await db.execute(
        text("""
            SELECT qty, reserved_qty FROM material_stock
            WHERE material_id = :material_id AND organization_id = :org_id
        """),
        {"material_id": material_id, "org_id": org_id},
    )
    stock_row = stock_result.fetchone()
    stock_qty = float(stock_row.qty) if stock_row and stock_row.qty is not None else 0.0
    reserved_qty = float(stock_row.reserved_qty) if stock_row and stock_row.reserved_qty is not None else 0.0

    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "code": row.code,
        "name": row.name,
        "unit": row.unit,
        "category": row.category,
        "comment": row.comment,
        "stock_qty": stock_qty,
        "reserved_qty": reserved_qty,
    }


# ==========================================
# УДАЛЕНИЕ МАТЕРИАЛА
# ==========================================

@router.delete("/{material_id}")
async def delete_material(
        material_id: UUID,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить материал (material_stock и recipe_item — CASCADE)."""
    await _set_log_context(
        db,
        user_id=current_user.get("user_id"),
        source="MANUAL",
        reason="Удаление материала",
    )

    result = await db.execute(
        text("""
            DELETE FROM material
            WHERE id = :material_id AND organization_id = :org_id
        """),
        {"material_id": material_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await db.commit()
    return {"message": "Материал удален"}


# ==========================================
# ВСЕ ОСТАТКИ
# ==========================================

@router.get("/stock", response_model=List[MaterialStockResponse])
async def get_all_stock(
        material_id: Optional[UUID] = Query(default=None),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить остатки (все или по конкретному материалу)."""
    if material_id:
        query = text("""
            SELECT id, organization_id, material_id, qty, reserved_qty, updated_at
            FROM material_stock
            WHERE organization_id = :org_id AND material_id = :mat_id
        """)
        params = {"org_id": org_id, "mat_id": material_id}
    else:
        query = text("""
            SELECT s.id, s.organization_id, s.material_id,
                   s.qty, s.reserved_qty, s.updated_at
            FROM material_stock s
            JOIN material m ON m.id = s.material_id
            WHERE s.organization_id = :org_id
            ORDER BY m.name
        """)
        params = {"org_id": org_id}

    result = await db.execute(query, params)
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "material_id": row.material_id,
            "qty": float(row.qty),
            "reserved_qty": float(row.reserved_qty) if row.reserved_qty is not None else 0.0,
            "updated_at": row.updated_at,
        }
        for row in result.fetchall()
    ]


# ==========================================
# ОБНОВЛЕНИЕ ОСТАТКОВ (UPSERT)
# ==========================================

@router.put("/{material_id}/stock", response_model=MaterialStockResponse)
async def update_material_stock(
        material_id: UUID,
        stock: MaterialStockUpdate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Обновить остатки. Upsert + логирование через триггер."""
    update_data = stock.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    check = await db.execute(
        text("""
            SELECT id FROM material
            WHERE id = :material_id AND organization_id = :org_id
        """),
        {"material_id": material_id, "org_id": org_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Материал не найден")

    # Контекст для триггера
    await _set_log_context(
        db,
        user_id=current_user.get("user_id"),
        source="MANUAL",
        reason="Корректировка остатков через UI",
    )

    # Гарантируем наличие записи
    await db.execute(
        text("""
            INSERT INTO material_stock
            (organization_id, material_id, qty, reserved_qty)
            VALUES (:org_id, :material_id, 0, 0)
            ON CONFLICT (organization_id, material_id) DO NOTHING
        """),
        {"org_id": org_id, "material_id": material_id},
    )

    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    query = text(
        f"""
            UPDATE material_stock
            SET {set_clause}, updated_at = NOW()
            WHERE material_id = :material_id AND organization_id = :org_id
            RETURNING id, organization_id, material_id, qty, reserved_qty, updated_at
        """
    )
    params = {"material_id": material_id, "org_id": org_id, **update_data}
    result = await db.execute(query, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось обновить остатки")

    await db.commit()
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "material_id": row.material_id,
        "qty": float(row.qty),
        "reserved_qty": float(row.reserved_qty) if row.reserved_qty is not None else 0.0,
        "updated_at": row.updated_at,
    }


# ==========================================
# ИМПОРТ ИЗ EXCEL (Итерация 13.2)
# ==========================================

# Ожидаемые заголовки Excel (регистронезависимо)
_EXCEL_HEADERS = {
    "код": "code",
    "code": "code",
    "наименование": "name",
    "название": "name",
    "name": "name",
    "категория": "category",
    "category": "category",
    "ед.изм.": "unit",
    "единица": "unit",
    "unit": "unit",
    "остаток": "qty",
    "количество": "qty",
    "qty": "qty",
    "резерв": "reserved_qty",
    "зарезервировано": "reserved_qty",
    "reserved_qty": "reserved_qty",
}

_VALID_CATEGORIES = {"RAW", "PACKAGING", "LABEL"}


@router.post("/import-excel", response_model=MaterialImportResponse)
async def import_materials_from_excel(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Импорт материалов и остатков из Excel-файла (.xlsx).

    Ожидаемые колонки (регистронезависимо):
        Код | Наименование | Категория | Ед.изм. | Остаток | Резерв

    Логика:
      - Если материала с таким code нет — создаём.
      - Если есть — обновляем name/category/unit (если переданы).
      - Всегда обновляем остатки через material_stock (upsert).
      - Все изменения пишутся в material_stock_log (source='IMPORT').
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только файлы .xlsx/.xlsm",
        )

    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось открыть файл Excel: {e}",
        )

    ws = wb.active
    if ws is None:
        raise HTTPException(status_code=400, detail="Файл пуст")

    # --- Парсим шапку ---
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise HTTPException(status_code=400, detail="Не найдена шапка таблицы")

    col_map: dict = {}  # {field_name: column_index}
    for idx, header in enumerate(header_row):
        if header is None:
            continue
        key = str(header).strip().lower()
        field = _EXCEL_HEADERS.get(key)
        if field:
            col_map[field] = idx

    if "code" not in col_map:
        raise HTTPException(
            status_code=400,
            detail="В файле нет колонки 'Код' (или 'code')",
        )

    # --- Контекст для триггера ---
    await _set_log_context(
        db,
        user_id=current_user.get("user_id"),
        source="IMPORT",
        reason=f"Импорт из файла {file.filename}",
    )

    result_rows: List[MaterialImportRow] = []
    created = updated = skipped = errors = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Пропускаем полностью пустые строки
        if row is None or all(c is None for c in row):
            continue

        def _get(field: str):
            col = col_map.get(field)
            if col is None or col >= len(row):
                return None
            return row[col]

        code_raw = _get("code")
        if code_raw is None or str(code_raw).strip() == "":
            skipped += 1
            result_rows.append(MaterialImportRow(
                row_number=row_idx,
                code="",
                status="SKIPPED",
                message="Пустой код — строка пропущена",
            ))
            continue

        code = str(code_raw).strip()
        name = str(_get("name")).strip() if _get("name") else None
        category = str(_get("category")).strip().upper() if _get("category") else None
        unit = str(_get("unit")).strip() if _get("unit") else None

        try:
            qty = float(_get("qty")) if _get("qty") is not None else 0.0
            reserved = float(_get("reserved_qty")) if _get("reserved_qty") is not None else 0.0
        except (ValueError, TypeError) as e:
            errors += 1
            result_rows.append(MaterialImportRow(
                row_number=row_idx,
                code=code,
                status="ERROR",
                message=f"Некорректное число в qty/reserved_qty: {e}",
            ))
            continue

        if qty < 0 or reserved < 0:
            errors += 1
            result_rows.append(MaterialImportRow(
                row_number=row_idx,
                code=code,
                status="ERROR",
                message="qty/reserved_qty не могут быть отрицательными",
            ))
            continue

        if category and category not in _VALID_CATEGORIES:
            errors += 1
            result_rows.append(MaterialImportRow(
                row_number=row_idx,
                code=code,
                category=category,
                status="ERROR",
                message=f"Недопустимая категория '{category}'. Допустимо: {sorted(_VALID_CATEGORIES)}",
            ))
            continue

        # --- Ищем материал ---
        existing = await db.execute(
            text("""
                SELECT id FROM material
                WHERE organization_id = :org_id AND code = :code
            """),
            {"org_id": org_id, "code": code},
        )
        existing_row = existing.fetchone()

        if existing_row is None:
            # --- Создаём материал ---
            if not name:
                errors += 1
                result_rows.append(MaterialImportRow(
                    row_number=row_idx,
                    code=code,
                    status="ERROR",
                    message="Для нового материала обязательно поле 'Наименование'",
                ))
                continue

            new_id = uuid4()
            await db.execute(
                text("""
                    INSERT INTO material
                    (id, organization_id, code, name, unit, category, comment)
                    VALUES (:id, :org_id, :code, :name, :unit, :category, NULL)
                """),
                {
                    "id": new_id,
                    "org_id": org_id,
                    "code": code,
                    "name": name,
                    "unit": unit or "kg",
                    "category": category or "RAW",
                },
            )
            material_id = new_id
            status = "CREATED"
            created += 1
        else:
            material_id = existing_row.id
            # Обновляем справочные поля (если переданы)
            updates = {}
            if name:
                updates["name"] = name
            if category:
                updates["category"] = category
            if unit:
                updates["unit"] = unit

            if updates:
                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                await db.execute(
                    text(f"UPDATE material SET {set_clause} WHERE id = :mid"),
                    {**updates, "mid": material_id},
                )
            status = "UPDATED"
            updated += 1

        # --- Upsert остатков ---
        await db.execute(
            text("""
                INSERT INTO material_stock
                (organization_id, material_id, qty, reserved_qty)
                VALUES (:org_id, :mid, :qty, :reserved)
                ON CONFLICT (organization_id, material_id)
                DO UPDATE SET
                    qty = EXCLUDED.qty,
                    reserved_qty = EXCLUDED.reserved_qty,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "mid": material_id,
                "qty": qty,
                "reserved": reserved,
            },
        )

        result_rows.append(MaterialImportRow(
            row_number=row_idx,
            code=code,
            name=name,
            category=category,
            unit=unit,
            qty=qty,
            reserved_qty=reserved,
            status=status,
            message=f"Материал {status.lower()}, остаток={qty}",
        ))

    await db.commit()

    return MaterialImportResponse(
        total_rows=len(result_rows),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        rows=result_rows,
        message=(
            f"Импорт завершён: создано {created}, обновлено {updated}, "
            f"пропущено {skipped}, ошибок {errors}."
        ),
    )


# ==========================================
# ШАБЛОН ДЛЯ ИМПОРТА (Итерация 13.2)
# ==========================================

@router.get("/import-template")
async def download_import_template():
    """Скачать Excel-шаблон для импорта материалов."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Материалы"

    headers = ["Код", "Наименование", "Категория", "Ед.изм.", "Остаток", "Резерв"]
    ws.append(headers)

    header_fill = PatternFill(
        start_color="2C3E50", end_color="2C3E50", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Примеры строк
    examples = [
        ("WATER", "Вода", "RAW", "kg", 100000, 0),
        ("SALT", "Соль экстра", "RAW", "kg", 3000, 0),
        ("BTL1", "Бутылки 1 литр", "PACKAGING", "pc", 30000, 0),
        ("", "", "", "", "", ""),  # пустая строка для разделения
        ("# Допустимые категории: RAW, PACKAGING, LABEL", "", "", "", "", ""),
        ("# Ед.изм.: kg, pc, l", "", "", "", "", ""),
    ]
    for row in examples:
        ws.append(row)

    # Ширина колонок
    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 22

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = "materials_import_template.xlsx"
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ==========================================
# ЭКСПОРТ В EXCEL (Итерация 13.2)
# ==========================================

@router.get("/export-excel")
async def export_materials_to_excel(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Экспорт всех материалов с остатками в Excel."""
    result = await db.execute(
        text("""
            SELECT
                m.code, m.name, m.category, m.unit,
                COALESCE(ms.qty, 0) AS qty,
                COALESCE(ms.reserved_qty, 0) AS reserved_qty,
                ms.updated_at
            FROM material m
            LEFT JOIN material_stock ms
                ON ms.material_id = m.id
               AND ms.organization_id = m.organization_id
            WHERE m.organization_id = :org_id
            ORDER BY m.category, m.name
        """),
        {"org_id": org_id},
    )
    rows = result.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Материалы"

    headers = ["Код", "Наименование", "Категория", "Ед.изм.", "Остаток", "Резерв", "Обновлено"]
    ws.append(headers)

    header_fill = PatternFill(
        start_color="2C3E50", end_color="2C3E50", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row in rows:
        updated_str = (
            row.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if row.updated_at else ""
        )
        ws.append([
            row.code,
            row.name,
            row.category,
            row.unit,
            float(row.qty),
            float(row.reserved_qty),
            updated_str,
        ])

    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 22

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = f"materials_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

# ==========================================
# ROLLBACK ПОСЛЕДНЕГО ИЗМЕНЕНИЯ (Итерация 13.3)
# ==========================================

@router.post(
    "/stock-log/{log_id}/revert",
    response_model=MaterialStockLogRevertResponse,
)
async def revert_stock_log_entry(
        log_id: UUID,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Отменить изменение остатков по записи журнала.

    Логика:
      - Для UPDATE: возвращаем old_qty/old_reserved_qty.
      - Для INSERT: удаляем запись из material_stock (откат создания).
      - Для DELETE: восстанавливаем запись с old_qty/old_reserved_qty.
      - Каждый откат пишет НОВУЮ запись в журнал (source='MANUAL', reason='Откат').

    Требования:
      - Запись должна принадлежать организации.
      - Материал должен существовать.
    """
    # 1. Читаем запись журнала
    log_result = await db.execute(
        text("""
            SELECT
                l.id, l.organization_id, l.material_id, l.action,
                l.old_qty, l.new_qty,
                l.old_reserved_qty, l.new_reserved_qty,
                m.code AS material_code,
                m.name AS material_name
            FROM material_stock_log l
            LEFT JOIN material m ON m.id = l.material_id
            WHERE l.id = :log_id AND l.organization_id = :org_id
        """),
        {"log_id": log_id, "org_id": org_id},
    )
    log_row = log_result.fetchone()
    if not log_row:
        raise HTTPException(status_code=404, detail="Запись журнала не найдена")

    material_id = log_row.material_id
    action = log_row.action

    # 2. Проверяем, что материал ещё существует
    mat_check = await db.execute(
        text("""
            SELECT id FROM material
            WHERE id = :mid AND organization_id = :org_id
        """),
        {"mid": material_id, "org_id": org_id},
    )
    if not mat_check.fetchone():
        raise HTTPException(
            status_code=400,
            detail="Материал удалён — откат невозможен",
        )

    # 3. Контекст для триггера
    await _set_log_context(
        db,
        user_id=current_user.get("user_id"),
        source="MANUAL",
        reason=f"Откат изменения {str(log_id)[:8]}",
    )

    # 4. Восстанавливаем остатки
    if action == "UPDATE":
        if log_row.old_qty is None:
            raise HTTPException(
                status_code=400,
                detail="Нельзя откатить: нет old_qty",
            )
        await db.execute(
            text("""
                UPDATE material_stock
                SET qty = :qty,
                    reserved_qty = :reserved,
                    updated_at = NOW()
                WHERE material_id = :mid AND organization_id = :org_id
            """),
            {
                "qty": log_row.old_qty,
                "reserved": log_row.old_reserved_qty or 0,
                "mid": material_id,
                "org_id": org_id,
            },
        )
        message = (
            f"Откат UPDATE: qty {log_row.new_qty} → {log_row.old_qty}"
        )

    elif action == "INSERT":
        # Откат создания: удаляем запись
        await db.execute(
            text("""
                DELETE FROM material_stock
                WHERE material_id = :mid AND organization_id = :org_id
            """),
            {"mid": material_id, "org_id": org_id},
        )
        message = "Откат INSERT: запись остатков удалена"

    elif action == "DELETE":
        # Откат удаления: восстанавливаем запись
        if log_row.old_qty is None:
            raise HTTPException(
                status_code=400,
                detail="Нельзя откатить: нет old_qty",
            )
        await db.execute(
            text("""
                INSERT INTO material_stock
                (organization_id, material_id, qty, reserved_qty)
                VALUES (:org_id, :mid, :qty, :reserved)
                ON CONFLICT (organization_id, material_id)
                DO UPDATE SET
                    qty = EXCLUDED.qty,
                    reserved_qty = EXCLUDED.reserved_qty,
                    updated_at = NOW()
            """),
            {
                "org_id": org_id,
                "mid": material_id,
                "qty": log_row.old_qty,
                "reserved": log_row.old_reserved_qty or 0,
            },
        )
        message = f"Откат DELETE: восстановлено qty={log_row.old_qty}"

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестное действие: {action}",
        )

    await db.commit()

    return MaterialStockLogRevertResponse(
        log_id=log_id,
        material_id=material_id,
        material_code=log_row.material_code,
        material_name=log_row.material_name,
        reverted=True,
        old_qty=float(log_row.old_qty) if log_row.old_qty is not None else None,
        new_qty=float(log_row.new_qty) if log_row.new_qty is not None else None,
        message=message,
    )


# ==========================================
# ОЧИСТКА ЖУРНАЛА (Итерация 13.3)
# ==========================================

@router.delete(
    "/stock-log/cleanup",
    response_model=MaterialStockLogCleanupResponse,
)
async def cleanup_stock_log(
        older_than_days: int = Query(
            default=90,
            ge=1,
            le=3650,
            description="Удалить записи старше N дней",
        ),
        source: Optional[str] = Query(
            default=None,
            description="Ограничить удаление только этим source",
        ),
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Очистить старые записи журнала изменений остатков.

    Доступно только ADMIN. По умолчанию удаляет записи старше 90 дней.
    Опционально можно ограничить конкретным источником (MANUAL/IMPORT/SYSTEM).
    """
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён. Требуется роль ADMIN",
        )

    where_clauses = [
        "organization_id = :org_id",
        "changed_at < NOW() - (:days || ' days')::interval",
    ]
    params: dict = {"org_id": org_id, "days": older_than_days}

    if source:
        where_clauses.append("source = :source")
        params["source"] = source

    where_sql = " AND ".join(where_clauses)

    # Считаем до удаления
    count_before_result = await db.execute(
        text(f"SELECT COUNT(*) AS cnt FROM material_stock_log WHERE {where_sql}"),
        params,
    )
    to_delete = int(count_before_result.fetchone().cnt or 0)

    if to_delete == 0:
        count_all_result = await db.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM material_stock_log "
                "WHERE organization_id = :org_id"
            ),
            {"org_id": org_id},
        )
        total = int(count_all_result.fetchone().cnt or 0)
        return MaterialStockLogCleanupResponse(
            deleted=0,
            kept=total,
            message=f"Нечего удалять: записей старше {older_than_days} дней нет",
        )

    delete_result = await db.execute(
        text(f"DELETE FROM material_stock_log WHERE {where_sql}"),
        params,
    )
    deleted = delete_result.rowcount or 0

    # Сколько осталось
    count_after_result = await db.execute(
        text(
            "SELECT COUNT(*) AS cnt FROM material_stock_log "
            "WHERE organization_id = :org_id"
        ),
        {"org_id": org_id},
    )
    kept = int(count_after_result.fetchone().cnt or 0)

    await db.commit()

    return MaterialStockLogCleanupResponse(
        deleted=deleted,
        kept=kept,
        message=(
                f"Удалено записей: {deleted} "
                f"(старше {older_than_days} дней"
                + (f", source={source}" if source else "")
                + f"). Осталось: {kept}."
        ),
    )