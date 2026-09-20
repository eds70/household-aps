# backend/app/api/v1/whatif.py
"""
API What-if сценариев (Итерация 12).

Эндпоинты:
  POST   /api/v1/whatif/scenarios              — создать сценарий
  GET    /api/v1/whatif/scenarios              — список сценариев
  GET    /api/v1/whatif/scenarios/{id}         — один сценарий
  PUT    /api/v1/whatif/scenarios/{id}         — обновить (только DRAFT)
  DELETE /api/v1/whatif/scenarios/{id}         — удалить (DRAFT/FAILED)
  POST   /api/v1/whatif/scenarios/{id}/run     — запустить расчёт (async)
  GET    /api/v1/whatif/scenarios/{id}/compare — сравнить с базовым

Права:
  - Создание/обновление/удаление: ADMIN, PLANNER
  - Запуск: ADMIN, PLANNER
  - Просмотр: все авторизованные роли

Итерация 12 (async):
  - POST /run возвращает 202 Accepted сразу.
  - Расчёт идёт в BackgroundTasks (отдельная сессия БД).
  - Frontend поллит статус через GET /scenarios/{id}.
  - Статусы: DRAFT → RUNNING → DONE/FAILED.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    _async_session,
    get_current_org_id,
    get_current_user,
    get_db_session,
)
from app.scheduler.logging_config import setup_scheduler_logging, log_with_context
from app.scheduler.whatif import WhatIfRunner
from .whatif_models import (
    WhatIfScenarioCreate,
    WhatIfScenarioUpdate,
    WhatIfScenarioResponse,
    WhatIfScenarioListItem,
    WhatIfRunRequest,
    WhatIfRunResponse,
    WhatIfCompareResponse,
    WhatIfMetrics,
)

router = APIRouter(prefix="/api/v1/whatif", tags=["What-if сценарии"])
logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ПРАВА ДОСТУПА
# ==========================================

EDIT_ALLOWED_ROLES = {"ADMIN", "PLANNER"}
RUN_ALLOWED_ROLES = {"ADMIN", "PLANNER"}


def _check_edit_role(current_user: dict) -> None:
    role = current_user.get("role")
    if role not in EDIT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: "
                   f"{sorted(EDIT_ALLOWED_ROLES)}",
        )


def _check_run_role(current_user: dict) -> None:
    role = current_user.get("role")
    if role not in RUN_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Доступ запрещён. Разрешённые роли: "
                   f"{sorted(RUN_ALLOWED_ROLES)}",
        )


# ==========================================
# POST /scenarios — создать сценарий
# ==========================================

@router.post("/scenarios", response_model=WhatIfScenarioResponse, status_code=201)
async def create_scenario(
        payload: WhatIfScenarioCreate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Создаёт what-if сценарий.

    Сценарий создаётся в статусе DRAFT. Для расчёта используйте
    POST /scenarios/{id}/run.
    """
    _check_edit_role(current_user)

    runner = WhatIfRunner(org_id=org_id, session=db)

    try:
        scenario_id = await runner.create_scenario(
            name=payload.name,
            base_version_id=payload.base_version_id,
            changes=payload.changes,
            comment=payload.comment,
            created_by=(
                UUID(current_user["user_id"])
                if current_user.get("user_id") else None
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_with_context(
        logger, logging.INFO,
        f"Создан what-if сценарий {str(scenario_id)[:8]} "
        f"'{payload.name}' (user={current_user.get('email')})",
        stage="whatif_api", org_id=str(org_id),
    )

    scenario = await runner.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=500,
            detail="Сценарий создан, но не найден",
        )

    return WhatIfScenarioResponse(**scenario)


# ==========================================
# GET /scenarios — список сценариев
# ==========================================

@router.get("/scenarios", response_model=List[WhatIfScenarioListItem])
async def list_scenarios(
        status_filter: Optional[str] = Query(
            default=None,
            alias="status",
            description="Фильтр по статусу: DRAFT | RUNNING | DONE | FAILED",
        ),
        limit: int = Query(default=100, ge=1, le=500),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Список сценариев организации (свежие — первыми).

    Доступно всем авторизованным пользователям.
    """
    if status_filter is not None and status_filter not in (
            "DRAFT", "RUNNING", "DONE", "FAILED"
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый статус: {status_filter}",
        )

    runner = WhatIfRunner(org_id=org_id, session=db)
    scenarios = await runner.list_scenarios(
        status=status_filter, limit=limit
    )

    return [WhatIfScenarioListItem(**s) for s in scenarios]


# ==========================================
# GET /scenarios/{id} — один сценарий
# ==========================================

@router.get("/scenarios/{scenario_id}", response_model=WhatIfScenarioResponse)
async def get_scenario(
        scenario_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """Возвращает сценарий по ID."""
    runner = WhatIfRunner(org_id=org_id, session=db)
    scenario = await runner.get_scenario(scenario_id)

    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден")

    return WhatIfScenarioResponse(**scenario)


# ==========================================
# PUT /scenarios/{id} — обновить
# ==========================================

@router.put("/scenarios/{scenario_id}", response_model=WhatIfScenarioResponse)
async def update_scenario(
        scenario_id: UUID,
        payload: WhatIfScenarioUpdate,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Обновляет сценарий. Только в статусе DRAFT.

    Все поля опциональны — передавайте только изменяемые.
    """
    _check_edit_role(current_user)

    runner = WhatIfRunner(org_id=org_id, session=db)

    try:
        ok = await runner.update_scenario(
            scenario_id=scenario_id,
            name=payload.name,
            comment=payload.comment,
            changes=payload.changes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(status_code=404, detail="Сценарий не найден")

    scenario = await runner.get_scenario(scenario_id)
    return WhatIfScenarioResponse(**scenario)


# ==========================================
# DELETE /scenarios/{id} — удалить
# ==========================================

@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
        scenario_id: UUID,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Удаляет сценарий. Только в статусе DRAFT или FAILED.

    Результирующая schedule_version НЕ удаляется —
    она остаётся в истории планов.
    """
    _check_edit_role(current_user)

    runner = WhatIfRunner(org_id=org_id, session=db)

    try:
        ok = await runner.delete_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(status_code=404, detail="Сценарий не найден")

    log_with_context(
        logger, logging.INFO,
        f"Удалён what-if сценарий {str(scenario_id)[:8]} "
        f"(user={current_user.get('email')})",
        stage="whatif_api", org_id=str(org_id),
    )

    return {"message": "Сценарий удалён"}


# ==========================================
# POST /scenarios/{id}/run — запустить (ASYNC)
# ==========================================

@router.post(
    "/scenarios/{scenario_id}/run",
    response_model=WhatIfRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_scenario(
        scenario_id: UUID,
        payload: WhatIfRunRequest,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(get_current_user),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Запускает what-if сценарий АСИНХРОННО.

    Логика:
      1. Проверяет, что сценарий существует и в статусе DRAFT/FAILED.
      2. Ставит статус RUNNING немедленно.
      3. Отправляет расчёт в BackgroundTasks.
      4. Возвращает 202 Accepted сразу.

    Frontend должен поллить GET /scenarios/{id} каждые 3 сек,
    пока status не станет DONE или FAILED.
    """
    _check_run_role(current_user)

    # Проверяем существование и статус
    runner = WhatIfRunner(org_id=org_id, session=db)
    scenario = await runner.get_scenario(scenario_id)

    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден")

    if scenario["status"] not in ("DRAFT", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Нельзя запустить сценарий в статусе "
                f"{scenario['status']} (только DRAFT или FAILED)"
            ),
        )

    # Ставим статус RUNNING немедленно (чтобы frontend увидел)
    await db.execute(
        text("""
            UPDATE whatif_scenario
            SET status = 'RUNNING', updated_at = NOW()
            WHERE id = :sid AND organization_id = :org_id
        """),
        {"sid": scenario_id, "org_id": org_id},
    )
    await db.commit()

    log_with_context(
        logger, logging.INFO,
        f"Запуск what-if {str(scenario_id)[:8]} в фоне "
        f"(user={current_user.get('email')})",
        stage="whatif_api", org_id=str(org_id),
    )

    # Запускаем расчёт в фоне
    background_tasks.add_task(
        _run_scenario_background,
        scenario_id=scenario_id,
        org_id=org_id,
        horizon_hours=payload.horizon_hours,
        timeout_seconds=payload.timeout_seconds,
    )

    return WhatIfRunResponse(
        scenario_id=scenario_id,
        status="RUNNING",
        message=(
            "Расчёт запущен в фоне. "
            "Опрашивайте GET /scenarios/{id} каждые 3 сек до DONE/FAILED."
        ),
    )


async def _run_scenario_background(
        scenario_id: UUID,
        org_id: UUID,
        horizon_hours: Optional[int],
        timeout_seconds: Optional[int],
) -> None:
    """
    Фоновая задача: запуск what-if в отдельной сессии БД.

    Создаёт свежую AsyncSession, чтобы не пересекаться с HTTP-запросом.
    """
    log_with_context(
        logger, logging.INFO,
        f"[BG] what-if {str(scenario_id)[:8]}: старт",
        stage="whatif_bg", org_id=str(org_id),
    )

    try:
        async with _async_session() as session:
            runner = WhatIfRunner(org_id=org_id, session=session)
            result = await runner.run_scenario(
                scenario_id=scenario_id,
                horizon_hours=horizon_hours,
                timeout_seconds=timeout_seconds,
            )

            log_with_context(
                logger, logging.INFO,
                f"[BG] what-if {str(scenario_id)[:8]}: завершён, "
                f"status={result.status}, "
                f"wall_time={result.wall_time_seconds}s",
                stage="whatif_bg", org_id=str(org_id),
            )
    except Exception as e:
        log_with_context(
            logger, logging.ERROR,
            f"[BG] Ошибка what-if {str(scenario_id)[:8]}: "
            f"{type(e).__name__}: {e}",
            stage="whatif_bg", org_id=str(org_id),
        )

        # Пытаемся пометить статус FAILED.
        try:
            async with _async_session() as session:
                await session.execute(
                    text("""
                        UPDATE whatif_scenario
                        SET status = 'FAILED',
                            comment = COALESCE(comment, '') || :err,
                            updated_at = NOW()
                        WHERE id = :sid AND organization_id = :org_id
                    """),
                    {
                        "sid": scenario_id,
                        "org_id": org_id,
                        "err": f"\n[bg error] {type(e).__name__}: {str(e)[:500]}",
                    },
                )
                await session.commit()
        except Exception as e2:
            log_with_context(
                logger, logging.ERROR,
                f"[BG] Не удалось пометить статус FAILED для "
                f"{str(scenario_id)[:8]}: {e2}",
                stage="whatif_bg", org_id=str(org_id),
            )


# ==========================================
# GET /scenarios/{id}/compare — сравнить
# ==========================================

@router.get("/scenarios/{scenario_id}/compare", response_model=WhatIfCompareResponse)
async def compare_scenario(
        scenario_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    """
    Сравнивает базовый и результирующий планы.

    Если сценарий ещё не запущен — result_metrics = None.
    """
    runner = WhatIfRunner(org_id=org_id, session=db)
    compare_data = await runner.compare(scenario_id)

    if not compare_data:
        raise HTTPException(status_code=404, detail="Сценарий не найден")

    return _build_compare_response(compare_data)


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ
# ==========================================

def _build_compare_response(data: dict) -> WhatIfCompareResponse:
    """
    Собирает WhatIfCompareResponse из dict от WhatIfRunner.compare().
    """
    base_metrics_data = data.get("base_metrics") or {}
    result_metrics_data = data.get("result_metrics")

    base_metrics = WhatIfMetrics(
        makespan_minutes=base_metrics_data.get("makespan_minutes", 0.0),
        makespan_hours=base_metrics_data.get("makespan_hours", 0.0),
        total_tasks=base_metrics_data.get("total_tasks", 0),
        blocked_tasks=base_metrics_data.get("blocked_tasks", 0),
        cooling_slow_tasks=base_metrics_data.get("cooling_slow_tasks", 0),
        cz_incomplete_tasks=base_metrics_data.get("cz_incomplete_tasks", 0),
    )

    result_metrics = None
    if result_metrics_data:
        result_metrics = WhatIfMetrics(
            makespan_minutes=result_metrics_data.get("makespan_minutes", 0.0),
            makespan_hours=result_metrics_data.get("makespan_hours", 0.0),
            total_tasks=result_metrics_data.get("total_tasks", 0),
            blocked_tasks=result_metrics_data.get("blocked_tasks", 0),
            cooling_slow_tasks=result_metrics_data.get("cooling_slow_tasks", 0),
            cz_incomplete_tasks=result_metrics_data.get("cz_incomplete_tasks", 0),
        )

    return WhatIfCompareResponse(
        scenario_id=data["scenario_id"],
        scenario_name=data["scenario_name"],
        scenario_status=data["scenario_status"],
        base_version_id=data["base_version_id"],
        result_version_id=data.get("result_version_id"),
        base_metrics=base_metrics,
        result_metrics=result_metrics,
        makespan_delta_minutes=data.get("makespan_delta_minutes"),
        makespan_delta_percent=data.get("makespan_delta_percent"),
        total_tasks_delta=data.get("total_tasks_delta"),
        blocked_tasks_delta=data.get("blocked_tasks_delta"),
        cooling_slow_tasks_delta=data.get("cooling_slow_tasks_delta"),
        cz_incomplete_tasks_delta=data.get("cz_incomplete_tasks_delta"),
        error_message=None,
        run_at=None,
    )