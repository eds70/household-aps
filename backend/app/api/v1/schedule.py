# backend/app/api/v1/schedule.py
"""
API планирования производства.

Итерация 13.15: POST /versions заполняет снапшоты справочников,
                GET /versions возвращает has_snapshot.
Итерация 13.21: GET /versions фильтрует архивные версии
                (параметр include_archived).
                Новый эндпоинт PUT /versions/{id}/unarchive.

Итерация 26 (advisor):
  - build_schedule сохраняет postprocess_result и skipped_batches
    в _last_schedule_result — их использует advisor.py для проверок
    OVER_HORIZON / SHIFTED_TASKS / SKIPPED_BATCHES / OVERLAPS_AFTER.
  - GET /versions возвращает has_advisor_notes — метка для UI.

Итерация 48 (drafts):
  - Повторное внедрение черновиков с защитой от дубликатов.
  - Добавлено копирование снапшотов (equipment, product, operation, calendar),
    чтобы Гант не считал черновик пустым.

Итерация 49 (plan-as-container):
  - POST /build принимает version_id из body (ScheduleBuildRequest).
    Если задан — ScheduleSaver перезаписывает этот план
    (is_active=TRUE, старые задачи и снапшоты чистятся).
    Если None — прежнее поведение (создать новую версию).
  - version_id больше не query-параметр.

Итерация 50 (edit-plan-copy):
  - POST /versions принимает parent_version_id (создание клона).
  - POST /versions/{id}/draft стал идемпотентным:
    если черновик уже есть — возвращает его, не пересоздавая.
    Копирует ТОЛЬКО снапшоты, без scheduled_task (клон настроек).
  - POST /versions/{id}/commit после утверждения удаляет draft
    (перенос задач не нужен, т.к. новый план создаётся через wizard).

Итерация 51 (fix plan_settings copy):
  - При копировании plan_settings из родителя передаются ВСЕ поля,
    а не только setting_key / setting_value. Иначе падает NOT NULL
    на value_type / category / display_order.

Итерация 21.3 (fix advisor_note):
  - После build_schedule сохраняем advisor_note в БД (SHIFTED_TASKS,
    OVER_HORIZON, SKIPPED_BATCHES, OVERLAPS_AFTER). Это нужно,
    чтобы «История сдвигов» на фронтенде показывала данные,
    а не пустую таблицу.
"""

import json
import logging
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

logger = logging.getLogger("app.api.schedule")

router = APIRouter(prefix="/api/v1/schedule", tags=["Планирование"])

_last_schedule_result: Dict[str, Any] = {}


# ==========================================
# Хелпер: копирование plan_settings из родителя
# ==========================================
async def _copy_plan_settings(
        db: AsyncSession,
        parent_version_id: UUID,
        new_version_id: UUID,
) -> int:
    """
    Копирует plan_settings из parent_version_id в new_version_id.
    Возвращает количество скопированных записей.

    ON CONFLICT DO NOTHING — для идемпотентности (если черновик
    уже был частично заполнен).
    """
    result = await db.execute(
        text("""
            INSERT INTO plan_settings (
                id, organization_id, schedule_version_id,
                setting_key, setting_value,
                category, value_type, label, description,
                min_value, max_value, options, display_order,
                is_system, updated_at
            )
            SELECT
                gen_random_uuid(), organization_id, :new_vid,
                setting_key, setting_value,
                category, value_type, label, description,
                min_value, max_value, options, display_order,
                is_system, NOW()
            FROM plan_settings
            WHERE schedule_version_id = :parent_vid
            ON CONFLICT (schedule_version_id, setting_key) DO NOTHING
        """),
        {"new_vid": new_version_id, "parent_vid": parent_version_id},
    )
    return result.rowcount or 0


@router.post("/build", response_model=ScheduleBuildResponse)
async def build_schedule(
        request: ScheduleBuildRequest,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    try:
        from app.scheduler.core import ProductionScheduler
        from app.scheduler.saver import ScheduleSaver

        if request.version_id is not None:
            check = await db.execute(
                text("""
                    SELECT name, is_active, is_archived, is_draft
                    FROM schedule_version
                    WHERE id = :vid AND organization_id = :org_id
                """),
                {"vid": request.version_id, "org_id": org_id},
            )
            row = check.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"План {request.version_id} не найден",
                )
            if getattr(row, "is_draft", False):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Нельзя строить в черновик. "
                        "Утвердите или отмените черновик."
                    ),
                )
            if getattr(row, "is_archived", False):
                raise HTTPException(
                    status_code=400,
                    detail="Нельзя строить в архивный план.",
                )

        scheduler = ProductionScheduler(
            horizon_hours=request.horizon_hours,
            timeout_seconds=request.timeout_seconds,
            org_id=org_id,
        )
        result = await scheduler.build_schedule()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        saver = ScheduleSaver(
            org_id=org_id,
            version_id=request.version_id,
        )
        save_stats = await saver.save_schedule(result)

        _last_schedule_result.update({
            "tasks": result["tasks"],
            "makespan_minutes": result["makespan_minutes"],
            "version_id": save_stats["version_id"],
            "timestamp": datetime.now(),
            "postprocess_result": result.get("calendar_postprocess"),
            "skipped_batches": result.get("skipped_batches", []),
        })

        # ==========================================
        # Итерация 21.3 (fix): сохранение Advisor в БД
        # (только те проверки, которые зависят от result)
        # ==========================================
        try:
            from app.scheduler.advisor import (
                check_shifted_tasks, check_over_horizon,
                check_skipped_batches, check_overlaps_after,
            )

            postprocess_result = result.get("calendar_postprocess")
            skipped_batches = result.get("skipped_batches", [])
            horizon_minutes = int(request.horizon_hours * 60) if request.horizon_hours else 30 * 24 * 60

            advisor_tips: list = []
            advisor_tips.extend(check_over_horizon(result, horizon_minutes))
            advisor_tips.extend(check_shifted_tasks(postprocess_result))
            advisor_tips.extend(check_skipped_batches(skipped_batches))
            advisor_tips.extend(check_overlaps_after(postprocess_result))

            # Удаляем старые заметки для этой версии
            await db.execute(
                text("DELETE FROM advisor_note WHERE schedule_version_id = :vid"),
                {"vid": save_stats["version_id"]},
            )

            # Вставляем новые
            for tip in advisor_tips:
                await db.execute(
                    text("""
                        INSERT INTO advisor_note
                            (organization_id, schedule_version_id, severity, code, title, message, details)
                        VALUES
                            (:org_id, :vid, :severity, :code, :title, :message, CAST(:details AS jsonb))
                    """),
                    {
                        "org_id": org_id,
                        "vid": save_stats["version_id"],
                        "severity": tip.severity,
                        "code": tip.code,
                        "title": tip.title,
                        "message": tip.message,
                        "details": json.dumps(tip.details, default=str),
                    },
                )

            await db.commit()
            logger.info(f"[build_schedule] Сохранено advisor_note: {len(advisor_tips)}")
        except Exception as adv_err:
            logger.warning(f"[build_schedule] Не удалось сохранить advisor_note: {adv_err}")
            await db.rollback()

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
        include_archived: bool = Query(default=False),
        include_drafts: bool = Query(default=False),
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    col_check = await db.execute(
        text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'schedule_version'
              AND column_name IN (
                  'is_archived',
                  'parent_version_id',
                  'has_advisor_notes',
                  'is_draft'
              )
        """)
    )
    available_cols = {row.column_name for row in col_check.fetchall()}
    has_archived = "is_archived" in available_cols
    has_parent = "parent_version_id" in available_cols
    has_advisor = "has_advisor_notes" in available_cols
    has_draft = "is_draft" in available_cols

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
    advisor_select = (
        "COALESCE(sv.has_advisor_notes, FALSE) AS has_advisor_notes,"
        if has_advisor else
        "FALSE AS has_advisor_notes,"
    )
    draft_select = (
        "COALESCE(sv.is_draft, FALSE) AS is_draft,"
        if has_draft else
        "FALSE AS is_draft,"
    )

    where_clauses = ["sv.organization_id = :org_id"]
    if has_archived and not include_archived:
        where_clauses.append("COALESCE(sv.is_archived, FALSE) = FALSE")
    if has_draft and not include_drafts:
        where_clauses.append("COALESCE(sv.is_draft, FALSE) = FALSE")

    where_sql = " AND ".join(where_clauses)

    query = text(f"""
        SELECT
            sv.id, sv.name, sv.version_type, sv.is_active,
            sv.created_at, sv.comment,
            {archived_select}
            {parent_select}
            {advisor_select}
            {draft_select}
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
            "has_advisor_notes": bool(row.has_advisor_notes),
            "is_draft": bool(row.is_draft),
        }
        for row in result.fetchall()
    ]


@router.post("/versions", response_model=dict)
async def create_schedule_version(
        request: dict,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    version_id = uuid4()
    name = request.get("name", "Без названия")
    version_type = request.get("version_type", "MONTHLY")
    comment = request.get("comment", "")
    parent_version_id_str = request.get("parent_version_id")
    parent_version_id = UUID(parent_version_id_str) if parent_version_id_str else None

    col_check = await db.execute(
        text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'schedule_version'
              AND column_name IN ('is_archived', 'is_draft', 'parent_version_id')
        """)
    )
    available_cols = {row.column_name for row in col_check.fetchall()}
    has_archived = "is_archived" in available_cols
    has_draft = "is_draft" in available_cols
    has_parent = "parent_version_id" in available_cols

    columns = ["id", "organization_id", "name", "version_type", "is_active", "created_at", "comment"]
    values = [":id", ":org_id", ":name", ":version_type", "FALSE", "NOW()", ":comment"]
    params = {
        "id": version_id, "org_id": org_id, "name": name,
        "version_type": version_type, "comment": comment,
    }

    if has_archived:
        columns.append("is_archived")
        values.append("FALSE")
    if has_draft:
        columns.append("is_draft")
        values.append("FALSE")
    if has_parent and parent_version_id:
        columns.append("parent_version_id")
        values.append(":parent_version_id")
        params["parent_version_id"] = parent_version_id

    await db.execute(
        text(f"""
            INSERT INTO schedule_version ({', '.join(columns)})
            VALUES ({', '.join(values)})
        """),
        params,
    )

    if parent_version_id:
        for table, cols in [
            ("equipment_snapshot", "id, organization_id, code, name, type, volume_kg, speed_coeff, mixer_type, is_active"),
            ("product_snapshot", "id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type"),
            ("operation_snapshot", "id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, operator_pool, comment"),
            ("calendar_snapshot", "id, organization_id, equipment_id, event_type, starts_at, ends_at, comment"),
            ("recipe_snapshot", "id, organization_id, product_id, base_volume_kg, comment"),
        ]:
            await db.execute(
                text(f"""
                    INSERT INTO {table} ({cols}, version_id)
                    SELECT {cols}, :new_vid FROM {table}
                    WHERE version_id = :parent_vid
                """),
                {"new_vid": version_id, "parent_vid": parent_version_id}
            )
        await db.execute(
            text("""
                INSERT INTO recipe_item_snapshot (id, recipe_id, material_id, qty_per_base, version_id)
                SELECT id, recipe_id, material_id, qty_per_base, :new_vid
                FROM recipe_item_snapshot WHERE version_id = :parent_vid
            """),
            {"new_vid": version_id, "parent_vid": parent_version_id}
        )
        # Итерация 51: копируем plan_settings (все поля!)
        await _copy_plan_settings(db, parent_version_id, version_id)
    else:
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
        "is_draft": False,
        "created_at": datetime.now().isoformat(),
        "comment": comment,
        "has_snapshot": True,
        "has_advisor_notes": False,
        "parent_version_id": str(parent_version_id) if parent_version_id else None,
    }


@router.post("/save", response_model=dict)
async def save_current_schedule(
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
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


@router.put(
    "/versions/{version_id}/unarchive",
    response_model=UnarchiveVersionResponse,
)
async def unarchive_schedule_version(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
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


@router.put("/versions/{version_id}/archive", response_model=dict)
async def archive_schedule_version(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
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

    if row.is_archived:
        raise HTTPException(
            status_code=400,
            detail=f"Версия «{row.name}» уже находится в архиве",
        )

    if row.is_active:
        raise HTTPException(
            status_code=400,
            detail="Нельзя архивировать активный план. Сначала откройте другой план.",
        )

    await db.execute(
        text("""
            UPDATE schedule_version
            SET is_archived = TRUE
            WHERE id = :vid AND organization_id = :org_id
        """),
        {"vid": version_id, "org_id": org_id},
    )
    await db.commit()

    return {
        "status": "success",
        "version_id": str(version_id),
        "name": row.name,
        "message": f"Версия «{row.name}» архивирована"
    }


# ==========================================
# ЧЕРНОВИКИ (DRAFTS)
# ==========================================

@router.post("/versions/{version_id}/draft", response_model=dict)
async def create_draft_from_version(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    # 1. Проверяем, есть ли уже черновик для этого плана
    existing = await db.execute(
        text("""
            SELECT id, name FROM schedule_version
            WHERE parent_version_id = :vid AND is_draft = TRUE AND organization_id = :org_id
            ORDER BY created_at DESC LIMIT 1
        """),
        {"vid": version_id, "org_id": org_id}
    )
    existing_row = existing.fetchone()
    if existing_row:
        return {
            "id": str(existing_row.id),
            "name": existing_row.name,
            "is_draft": True,
            "parent_version_id": str(version_id),
            "message": "Существующий черновик"
        }

    # 2. Проверяем исходную версию
    check = await db.execute(
        text("SELECT name, version_type FROM schedule_version WHERE id = :vid AND organization_id = :org_id"),
        {"vid": version_id, "org_id": org_id}
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Исходная версия плана не найдена")

    # 3. Создаем новый черновик
    draft_id = uuid4()
    draft_name = f"📝 Черновик: {row.name}"

    await db.execute(
        text("""
            INSERT INTO schedule_version 
                (id, organization_id, name, version_type, is_active, is_archived, is_draft, parent_version_id, created_at)
            VALUES 
                (:id, :org_id, :name, :vtype, FALSE, FALSE, TRUE, :parent_id, NOW())
        """),
        {
            "id": draft_id, "org_id": org_id, "name": draft_name,
            "vtype": row.version_type, "parent_id": version_id
        }
    )

    # 4. Копируем ТОЛЬКО снапшоты (без scheduled_task)
    for table, cols in [
        ("equipment_snapshot", "id, organization_id, code, name, type, volume_kg, speed_coeff, mixer_type, is_active"),
        ("product_snapshot", "id, organization_id, code, name, type, viscosity_coeff, requires_heating, bottle_volume_l, fill_speed_per_min, parent_pf_id, route_type"),
        ("operation_snapshot", "id, organization_id, product_id, stage_order, name, base_duration_mins, is_setup, is_parallel_group, parallel_group_id, needs_boiler, needs_cooling_zone, needs_operator, needs_lab, duration_formula, operator_pool, comment"),
        ("calendar_snapshot", "id, organization_id, equipment_id, event_type, starts_at, ends_at, comment"),
        ("recipe_snapshot", "id, organization_id, product_id, base_volume_kg, comment"),
    ]:
        await db.execute(
            text(f"""
                INSERT INTO {table} ({cols}, version_id)
                SELECT {cols}, :draft_id FROM {table}
                WHERE version_id = :parent_id
            """),
            {"draft_id": draft_id, "parent_id": version_id}
        )
    await db.execute(
        text("""
            INSERT INTO recipe_item_snapshot (id, recipe_id, material_id, qty_per_base, version_id)
            SELECT id, recipe_id, material_id, qty_per_base, :draft_id
            FROM recipe_item_snapshot WHERE version_id = :parent_id
        """),
        {"draft_id": draft_id, "parent_id": version_id}
    )

    # Итерация 51: копируем plan_settings
    await _copy_plan_settings(db, version_id, draft_id)

    await db.commit()

    return {
        "id": str(draft_id),
        "name": draft_name,
        "is_draft": True,
        "parent_version_id": str(version_id),
        "message": "Черновик создан"
    }


@router.post("/versions/{version_id}/commit", response_model=dict)
async def commit_draft(
        version_id: UUID,
        org_id: UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db_session),
):
    check = await db.execute(
        text("SELECT parent_version_id, name FROM schedule_version WHERE id = :vid AND is_draft = TRUE AND organization_id = :org_id"),
        {"vid": version_id, "org_id": org_id}
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Это не черновик или черновик не найден")

    parent_id = row.parent_version_id
    draft_name = row.name

    clean_name = draft_name.replace("📝 Черновик: ", "")
    await db.execute(
        text("UPDATE schedule_version SET is_draft = FALSE, is_active = TRUE, name = :name WHERE id = :vid"),
        {"vid": version_id, "name": clean_name}
    )

    if parent_id:
        await db.execute(
            text("UPDATE schedule_version SET is_archived = TRUE, is_active = FALSE WHERE id = :parent_id"),
            {"parent_id": parent_id}
        )

    await db.commit()
    return {
        "status": "success",
        "version_id": str(version_id),
        "name": clean_name,
        "parent_archived": True if parent_id else False,
        "message": f"Черновик «{clean_name}» утвержден"
    }