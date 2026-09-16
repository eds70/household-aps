# backend/app/api/v1/advisor.py
"""
API для Advisor — подсказки планировщика и оценка исполнимости.

Итерация 2.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID
from typing import Optional

from app.auth.dependencies import get_current_org_id, get_db_session
from app.scheduler.data_loader import DataLoader
from app.scheduler.feature_flags import FeatureFlags
from app.scheduler.advisor import analyze as advisor_analyze
from app.scheduler.feasibility import check_feasibility
from .models import (
    AdvisorResponse,
    AdvisorTipModel,
    FeasibilityResponse,
    FeasibilityIssueModel,
)


router = APIRouter(prefix="/api/v1/schedule", tags=["Advisor"])


@router.get("/advice", response_model=AdvisorResponse)
async def get_advice(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Возвращает подсказки Advisor'а:
      - Дефицит сырья
      - Неполная загрузка реактора
      - Несоответствие маршрута (VIA_TANK без танка)
      - Простои оборудования
    """
    loader = DataLoader(org_id=org_id)
    data = await loader.load_all()

    flags = FeatureFlags(data.get("org_settings", {}))

    # Читаем max_fill_percent из настроек
    max_fill = 0.70
    raw_fill = data["org_settings"].get("max_fill_percent")
    if raw_fill is not None:
        try:
            if isinstance(raw_fill, str):
                max_fill = float(raw_fill.strip().strip('"'))
            else:
                max_fill = float(raw_fill)
        except (ValueError, TypeError):
            pass

    # Получаем последний результат планирования (если был)
    from .schedule import _last_schedule_result
    schedule_result = _last_schedule_result if _last_schedule_result else None

    result = advisor_analyze(
        batches=data["batches"],
        products_map=data["products"],
        equipment_map=data["equipment"],
        equipment_links=data["equipment_links"],
        recipes=data["recipes"],
        materials=data["materials"],
        material_stocks=data["material_stocks"],
        material_supplies=data["material_supplies"],
        schedule_result=schedule_result,
        max_fill_percent=max_fill,
        enable_material_constraints=flags.enable_material_constraints,
        enable_advisor=flags.enable_advisor,
    )

    return AdvisorResponse(
        tips=[
            AdvisorTipModel(
                code=t.code,
                severity=t.severity,
                title=t.title,
                message=t.message,
                details=t.details,
            )
            for t in result.tips
        ],
        critical_count=result.critical_count,
        warning_count=result.warning_count,
        info_count=result.info_count,
        generated_at=datetime.now(),
    )


@router.post("/feasibility", response_model=FeasibilityResponse)
async def check_plan_feasibility(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Проверяет исполнимость текущего плана:
      - Хватает ли сырья
      - Нет ли блокирующих проблем
    """
    loader = DataLoader(org_id=org_id)
    data = await loader.load_all()

    result = check_feasibility(
        batches=data["batches"],
        recipes=data["recipes"],
        materials=data["materials"],
        material_stocks=data["material_stocks"],
        material_supplies=data["material_supplies"],
    )

    return FeasibilityResponse(
        feasible=result.feasible,
        issues=[
            FeasibilityIssueModel(
                code=i.code, severity=i.severity, message=i.message, details=i.details
            )
            for i in result.issues
        ],
        warnings=[
            FeasibilityIssueModel(
                code=i.code, severity=i.severity, message=i.message, details=i.details
            )
            for i in result.warnings
        ],
    )