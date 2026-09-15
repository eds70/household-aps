# backend/app/api/v1/schedule.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from .models import ScheduleBuildRequest, ScheduleBuildResponse
from app.auth.dependencies import get_current_org_id, get_db_session

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

        # Передаём org_id в планировщик
        scheduler = ProductionScheduler(
            horizon_hours=request.horizon_hours,
            org_id=org_id,
        )
        result = await scheduler.build_schedule()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # Передаём org_id в сохранитель
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
        raise HTTPException(status_code=404, detail="Нет данных. Сначала запустите /build")
    return {
        "status": "success",
        "total_tasks": len(_last_schedule_result.get("tasks", [])),
        "makespan_minutes": _last_schedule_result.get("makespan_minutes"),
        "version_id": str(_last_schedule_result.get("version_id")),
    }


@router.get("/versions", response_model=List[dict])
async def get_schedule_versions(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Получить список всех версий планов"""
    result = await db.execute(
        text("""
            SELECT id, name, version_type, is_active, created_at, comment
            FROM schedule_version
            WHERE organization_id = :org_id
            ORDER BY created_at DESC
        """),
        {"org_id": org_id},
    )
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "version_type": row.version_type,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "comment": row.comment,
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
    """
    version_id = uuid4()
    name = request.get("name", "Без названия")
    version_type = request.get("version_type", "MONTHLY")
    comment = request.get("comment", "")

    # Создаем версию плана
    await db.execute(
        text("""
            INSERT INTO schedule_version (id, organization_id, name, version_type, is_active, created_at, comment)
            VALUES (:id, :org_id, :name, :version_type, FALSE, NOW(), :comment)
        """),
        {
            "id": version_id,
            "org_id": org_id,
            "name": name,
            "version_type": version_type,
            "comment": comment,
        },
    )
    await db.commit()

    return {
        "id": str(version_id),
        "name": name,
        "version_type": version_type,
        "is_active": False,
        "created_at": datetime.now().isoformat(),
        "comment": comment,
    }


@router.post("/save", response_model=dict)
async def save_current_schedule(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Сохранить текущий рассчитанный план как версию"""
    if not _last_schedule_result:
        raise HTTPException(status_code=400, detail="Нет рассчитанного плана для сохранения")

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
    """Удалить версию плана и все связанные данные (CASCADE)"""
    result = await db.execute(
        text("DELETE FROM schedule_version WHERE id = :version_id AND organization_id = :org_id"),
        {"version_id": version_id, "org_id": org_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Версия плана не найдена")
    await db.commit()
    return {"message": "Версия плана удалена"}