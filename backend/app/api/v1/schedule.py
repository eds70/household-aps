# backend/app/api/v1/schedule.py
"""
API планирования производства.

Итерация 13.15: POST /versions заполняет снапшоты справочников,
                GET /versions возвращает has_snapshot.
Итерация 13.21: GET /versions фильтрует архивные версии
                (параметр include_archived).
                Новый эндпоинт PUT /versions/{id}/unarchive.
"""

from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.snapshot import snapshot_all_catalogs
from .models import ScheduleBuildRequest, ScheduleBuildResponse
from .reschedule_models import UnarchiveVersionResponse

router = APIRouter(prefix="/api/v1/schedule", tags=["Планирование"])

_last_schedule_result: Dict[str, Any] = {}


@router.post("/build", response_model=ScheduleBuildResponse)
async def build_schedule(
        request: ScheduleBuildRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    try:
        from app.scheduler.core import ProductionScheduler
        from app.scheduler.saver import ScheduleSaver

        # ==========================================
        # Итерация 10 (fix #13): передаём timeout_seconds из запроса.
        # ==========================================
        scheduler = ProductionScheduler(
            horizon_hours=request.horizon_hours,
            timeout_seconds=request.timeout_seconds,
            org_id=org_id,
        )
        result = await scheduler.build_schedule()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        saver = ScheduleSaver(org_id=org_id)
        save_stats = await saver.save_schedule(result)

        _last_schedule_result.update({
            "tasks": result["tasks"],
            "makespan_minutes": result["makespan_minutes"],
            "version_id": save_stats["version_id"],
            "timestamp": datetime.now(),
        })

        return ScheduleBuildResponse(
            status="success",
            total_tasks=result["total_tasks"],
            makespan_minutes=result["makespan_minutes"],
            makespan_hours=result["makespan_minutes"] / 60,
            version_id=save_stats["version_id"],
            message=f"Построено {result['total_tasks']} задач",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/last-result")
async def get_last_result():
    if not _last_schedule_result:
        raise HTTPException(
            status_code=404,
            detail="Нет данных. Сначала запустите /build",
        )
    return {
        "status": "success",
        "total_tasks": len(_last_schedule_result.get("tasks", [])),
        "makespan_minutes": _last_schedule_result.get("makespan_minutes"),
        "version_id": str(_last_schedule_result.get("version_id")),
    }


@router.get("/versions", response_model=List[dict])
async def get_schedule_versions(
        include_archived: bool = Query(
            default=False,
            description=(
                    "Показывать ли архивные версии планов. "
                    "По умолчанию — только активные и неархивные."
            ),
        ),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Получить список всех версий планов.

    Итерация 13.15: добавлено поле has_snapshot — заполнены ли
    снапшот-таблицы для этой версии. UI использует это поле, чтобы
    понять, можно ли открывать план в readonly-режиме.

    Итерация 13.21: фильтр по архивным версиям. По умолчанию
    архивные не показываются (is_archived = FALSE). Параметр
    include_archived=true возвращает их все.

    Поля ответа:
      - id, name, version_type, is_active, created_at, comment
      - has_snapshot: bool
      - is_archived: bool (Итерация 13.21)
      - parent_version_id: Optional[str] (для построения иерархии)
    """
    # ==========================================
    # Проверяем наличие колонок (graceful для старых БД)
    # ==========================================
    col_check = await db.execute(
        text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'schedule_version'
              AND column_name IN ('is_archived', 'parent_version_id')
        """)
    )
    available_cols = {row.column_name for row in col_check.fetchall()}
    has_archived = "is_archived" in available_cols
    has_parent = "parent_version_id" in available_cols

    # ==========================================
    # Формируем SELECT с учётом доступных колонок
    # ==========================================
    archived_select = (
        "COALESCE(sv.is_archived, FALSE) AS is_archived,"
        if has_archived else
        "FALSE AS is_archived,"
    )
    parent_select = (
        "sv.parent_version_id,"
        if has_parent else
        "NULL::uuid AS parent_version_id,"
    )

    where_clauses = ["sv.organization_id = :org_id"]
    if has_archived and not include_archived:
        where_clauses.append("COALESCE(sv.is_archived, FALSE) = FALSE")

    where_sql = " AND ".join(where_clauses)

    query = text(f"""
        SELECT
            sv.id, sv.name, sv.version_type, sv.is_active,
            sv.created_at, sv.comment,
            {archived_select}
            {parent_select}
            EXISTS (
                SELECT 1 FROM equipment_snapshot
                WHERE version_id = sv.id LIMIT 1
            ) AS has_snapshot
        FROM schedule_version sv
        WHERE {where_sql}
        ORDER BY
            sv.is_active DESC,
            sv.created_at DESC
    """)

    result = await db.execute(query, {"org_id": org_id})

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "version_type": row.version_type,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "comment": row.comment,
            "has_snapshot": bool(row.has_snapshot),
            "is_archived": bool(row.is_archived),
            "parent_version_id": (
                str(row.parent_version_id)
                if row.parent_version_id else None
            ),
        }
        for row in result.fetchall()
    ]


@router.post("/versions", response_model=dict)
async def create_schedule_version(
        request: dict,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Создать новую версию плана (пустую, без задач).

    Итерация 13.15:
        Раньше при создании пустого плана снапшот-таблицы НЕ заполнялись,
        из-за чего UI в readonly-режиме показывал пустые справочники.

        Теперь:
          1. Создаём schedule_version.
          2. Триггер copy_app_settings_to_plan копирует app_settings
             в plan_settings (работает на уровне БД, add_21.sql).
          3. Явно вызываем snapshot_all_catalogs — заполняем
             equipment/product/operation/calendar снапшоты.

        Это делает план «полноценным» с точки зрения UI: справочники
        открываются, настройки видны, можно пересчитать план.

    Итерация 13.21: новая версия создаётся с is_archived = FALSE.
    """
    version_id = uuid4()
    name = request.get("name", "Без названия")
    version_type = request.get("version_type", "MONTHLY")
    comment = request.get("comment", "")

    # ==========================================
    # Проверяем наличие колонки is_archived
    # ==========================================
    col_check = await db.execute(
        text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'schedule_version'
              AND column_name = 'is_archived'
        """)
    )
    has_archived = col_check.fetchone() is not None

    # ==========================================
    # 1. Создаём версию плана.
    # ==========================================
    if has_archived:
        await db.execute(
            text("""
                INSERT INTO schedule_version
                    (id, organization_id, name, version_type,
                     is_active, is_archived, created_at, comment)
                VALUES
                    (:id, :org_id, :name, :version_type,
                     FALSE, FALSE, NOW(), :comment)
            """),
            {
                "id": version_id,
                "org_id": org_id,
                "name": name,
                "version_type": version_type,
                "comment": comment,
            },
        )
    else:
        await db.execute(
            text("""
                INSERT INTO schedule_version
                    (id, organization_id, name, version_type,
                     is_active, created_at, comment)
                VALUES
                    (:id, :org_id, :name, :version_type,
                     FALSE, NOW(), :comment)
            """),
            {
                "id": version_id,
                "org_id": org_id,
                "name": name,
                "version_type": version_type,
                "comment": comment,
            },
        )

    # ==========================================
    # 2. Заполняем снапшоты.
    # ==========================================
    # Триггер copy_app_settings_to_plan уже сработал на INSERT
    # (см. add_21.sql) — plan_settings заполнены.
    #
    # Теперь заполняем снапшоты справочников.
    snapshot_stats = await snapshot_all_catalogs(
        session=db,
        org_id=org_id,
        version_id=version_id,
    )

    await db.commit()

    return {
        "id": str(version_id),
        "name": name,
        "version_type": version_type,
        "is_active": False,
        "is_archived": False,
        "created_at": datetime.now().isoformat(),
        "comment": comment,
        "has_snapshot": True,
        "snapshot_stats": snapshot_stats,
    }


@router.post("/save", response_model=dict)
async def save_current_schedule(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Сохранить текущий рассчитанный план как версию."""
    if not _last_schedule_result:
        raise HTTPException(
            status_code=400,
            detail="Нет рассчитанного плана для сохранения",
        )

    if "version_id" in _last_schedule_result and _last_schedule_result["version_id"]:
        return {
            "status": "success",
            "message": "План уже был сохранен при построении",
            "version_id": str(_last_schedule_result["version_id"]),
        }

    from app.scheduler.saver import ScheduleSaver

    saver = ScheduleSaver(org_id=org_id)
    result = await saver.save_schedule(_last_schedule_result)

    _last_schedule_result["version_id"] = result["version_id"]

    return {
        "status": "success",
        "message": f"План '{result['name']}' успешно сохранен",
        "version_id": str(result["version_id"]),
    }


@router.delete("/versions/{version_id}")
async def delete_schedule_version(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Удалить версию плана и все связанные данные (CASCADE)."""
    result = await db.execute(
        text(
            "DELETE FROM schedule_version "
            "WHERE id = :version_id AND organization_id = :org_id"
        ),
        {"version_id": version_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Версия плана не найдена")
    await db.commit()
    return {"message": "Версия плана удалена"}


# ==========================================
# ИТЕРАЦИЯ 13.21: РАЗАРХИВАЦИЯ ВЕРСИИ
# ==========================================

@router.put(
    "/versions/{version_id}/unarchive",
    response_model=UnarchiveVersionResponse,
)
async def unarchive_schedule_version(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Разархивировать версию плана.

    Итерация 13.21: архивированные версии скрыты из списка по умолчанию.
    Этот эндпоинт возвращает их в список (is_archived = FALSE).
    Версия НЕ становится активной автоматически — нужно явно
    открыть её через UI.

    Используется кнопкой «↩ Разархивировать» в «Истории планов».
    """
    # 1. Проверяем наличие колонки is_archived
    col_check = await db.execute(
        text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'schedule_version'
              AND column_name = 'is_archived'
        """)
    )
    if col_check.fetchone() is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Колонка is_archived не найдена. "
                "Примените миграцию add_23.sql"
            ),
        )

    # 2. Проверяем, что версия существует
    check = await db.execute(
        text("""
            SELECT id, name, is_archived, is_active
            FROM schedule_version
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": org_id},
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Версия плана не найдена")

    if not row.is_archived:
        raise HTTPException(
            status_code=400,
            detail=f"Версия «{row.name}» не находится в архиве",
        )

    # 3. Разархивируем
    await db.execute(
        text("""
            UPDATE schedule_version
            SET is_archived = FALSE
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": org_id},
    )
    await db.commit()

    return UnarchiveVersionResponse(
        status="success",
        version_id=str(version_id),
        name=row.name,
        is_archived=False,
        is_active=bool(row.is_active),
        message=f"Версия «{row.name}» разархивирована",
    )