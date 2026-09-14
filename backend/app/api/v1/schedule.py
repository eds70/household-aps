# backend/app/api/v1/schedule.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime
from .models import ScheduleBuildRequest, ScheduleBuildResponse

router = APIRouter(prefix="/api/v1/schedule", tags=["Планирование"])

_last_schedule_result: Dict[str, Any] = {}

# Настройка БД для эндпоинтов версий (можно вынести в зависимости, но для простоты оставим здесь)
DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

@router.post("/build", response_model=ScheduleBuildResponse)
async def build_schedule(request: ScheduleBuildRequest):
    try:
        from app.scheduler.core import ProductionScheduler
        from app.scheduler.saver import ScheduleSaver

        scheduler = ProductionScheduler(horizon_hours=request.horizon_hours)
        result = await scheduler.build_schedule()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        saver = ScheduleSaver()
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
            message=f"Построено {result['total_tasks']} задач"
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
async def get_schedule_versions(db: AsyncSession = Depends(get_db)):
    """Получить список всех версий планов"""
    result = await db.execute(text("""
        SELECT id, name, version_type, is_active, created_at, comment
        FROM schedule_version
        ORDER BY created_at DESC
    """))
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

@router.post("/save", response_model=dict)
async def save_current_schedule(db: AsyncSession = Depends(get_db)):
    """Сохранить текущий рассчитанный план как версию (если он еще не сохранен)"""
    if not _last_schedule_result:
        raise HTTPException(status_code=400, detail="Нет рассчитанного плана для сохранения")

    # Проверяем, не сохранен ли он уже (по наличию version_id в результате)
    if "version_id" in _last_schedule_result and _last_schedule_result["version_id"]:
        return {
            "status": "success",
            "message": "План уже был сохранен при построении",
            "version_id": str(_last_schedule_result["version_id"]),
        }

    from app.scheduler.saver import ScheduleSaver
    saver = ScheduleSaver()
    result = await saver.save_schedule(_last_schedule_result)

    # Обновляем глобальную переменную, чтобы знать, что план сохранен
    _last_schedule_result["version_id"] = result["version_id"]

    return {
        "status": "success",
        "message": f"План '{result['name']}' успешно сохранен",
        "version_id": str(result["version_id"]),
    }

@router.delete("/versions/{version_id}")
async def delete_schedule_version(
        version_id: UUID,
        db: AsyncSession = Depends(get_db)
):
    """Удалить версию плана и все связанные данные (CASCADE сработает на уровне БД)"""
    result = await db.execute(
        text("DELETE FROM schedule_version WHERE id = :version_id"),
        {"version_id": version_id}
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Версия плана не найдена")
    await db.commit()
    return {"message": "Версия плана удалена"}