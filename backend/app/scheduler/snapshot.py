# backend/app/scheduler/snapshot.py
"""
Заполнение снапшот-таблиц для конкретной версии плана.

Итерация 13.15.

Проблема, которую решает модуль:
    Раньше снапшоты (equipment_snapshot, product_snapshot,
    operation_snapshot, calendar_snapshot) заполнялись ТОЛЬКО внутри
    ScheduleSaver._do_save — то есть при сохранении РАССЧИТАННОГО плана.

    Если план создавался «пустым» через POST /api/v1/schedule/versions
    (например, из мастера PlanSettingsWizard в режиме create), то
    снапшоты не заполнялись. UI переключался в readonly-режим и показывал
    пустые справочники, потому что все API-эндпоинты читают из снапшотов
    (см. products.py, equipment.py, operations.py, calendar.py).

Решение:
    Единая функция snapshot_all_catalogs(session, org_id, version_id),
    которая заполняет все 4 снапшот-таблицы из актуальных справочников.

    Вызывается из:
      1. schedule.py::create_schedule_version — при создании плана.
      2. saver.py::_do_save — при сохранении рассчитанного плана.

Идемпотентность:
    Используем ON CONFLICT DO NOTHING — повторный вызов безопасен.
    Снапшот-таблицы имеют PK (id, version_id), поэтому дубликатов не будет.

ВАЖНО:
    - Снапшоты — это «слепок» справочников на момент создания/расчёта плана.
    - Если после создания плана справочник изменился, снапшот НЕ обновляется
      автоматически. Это by design (см. ADR 0002).
    - Для «пересборки» снапшота нужно создать новый план или вручную
      вызвать snapshot_all_catalogs с force=True (не реализовано, но
      возможно в будущих итерациях).
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .logging_config import setup_scheduler_logging, log_with_context

logger = setup_scheduler_logging(level=logging.INFO)


# ==========================================
# ОСНОВНАЯ ФУНКЦИЯ
# ==========================================

async def snapshot_all_catalogs(
        session: AsyncSession,
        org_id: UUID,
        version_id: UUID,
) -> dict:
    """
    Заполняет все снапшот-таблицы для указанной версии плана.

    Копирует актуальные данные из:
      - equipment          → equipment_snapshot
      - product            → product_snapshot
      - operation_template → operation_snapshot
      - calendar_event     → calendar_snapshot

    Args:
        session: Async-сессия SQLAlchemy.
        org_id: UUID организации.
        version_id: UUID версии плана (schedule_version.id).

    Returns:
        Статистика: {equipment, products, operations, calendar_events}.
    """
    log_with_context(
        logger, logging.INFO,
        f"[snapshot] Старт заполнения снапшотов для version={str(version_id)[:8]}",
        stage="snapshot", org_id=str(org_id),
    )

    # ==========================================
    # 1. EQUIPMENT → equipment_snapshot
    # ==========================================
    equipment_result = await session.execute(
        text("""
            INSERT INTO equipment_snapshot
                (id, organization_id, code, name, type, volume_kg,
                 speed_coeff, mixer_type, is_active, version_id)
            SELECT
                id, organization_id, code, name, type, volume_kg,
                speed_coeff, mixer_type, is_active, :version_id
            FROM equipment
            WHERE organization_id = :org_id
            ON CONFLICT (id, version_id) DO NOTHING
        """),
        {"version_id": version_id, "org_id": org_id},
    )
    equipment_count = equipment_result.rowcount or 0

    # ==========================================
    # 2. PRODUCT → product_snapshot
    # ==========================================
    products_result = await session.execute(
        text("""
            INSERT INTO product_snapshot
                (id, organization_id, code, name, type, viscosity_coeff,
                 requires_heating, bottle_volume_l, fill_speed_per_min,
                 parent_pf_id, route_type, version_id)
            SELECT
                id, organization_id, code, name, type, viscosity_coeff,
                requires_heating, bottle_volume_l, fill_speed_per_min,
                parent_pf_id, route_type, :version_id
            FROM product
            WHERE organization_id = :org_id
            ON CONFLICT (id, version_id) DO NOTHING
        """),
        {"version_id": version_id, "org_id": org_id},
    )
    products_count = products_result.rowcount or 0

    # ==========================================
    # 3. OPERATION_TEMPLATE → operation_snapshot
    # ==========================================
    # ВАЖНО: колонка operator_pool добавлена в add_09.sql.
    # Если её нет в БД (старая схема) — INSERT упадёт.
    # Поэтому проверяем наличие колонки.
    has_operator_pool = await _has_column(
        session, "operation_template", "operator_pool"
    )

    if has_operator_pool:
        operations_result = await session.execute(
            text("""
                INSERT INTO operation_snapshot
                    (id, organization_id, product_id, stage_order, name,
                     base_duration_mins, is_setup, is_parallel_group,
                     parallel_group_id, needs_boiler, needs_cooling_zone,
                     needs_operator, needs_lab, duration_formula,
                     operator_pool, comment, version_id)
                SELECT
                    id, organization_id, product_id, stage_order, name,
                    base_duration_mins, is_setup, is_parallel_group,
                    parallel_group_id, needs_boiler, needs_cooling_zone,
                    needs_operator, needs_lab, duration_formula,
                    operator_pool, comment, :version_id
                FROM operation_template
                WHERE organization_id = :org_id
                ON CONFLICT (id, version_id) DO NOTHING
            """),
            {"version_id": version_id, "org_id": org_id},
        )
    else:
        # Fallback: старая схема без operator_pool
        operations_result = await session.execute(
            text("""
                INSERT INTO operation_snapshot
                    (id, organization_id, product_id, stage_order, name,
                     base_duration_mins, is_setup, is_parallel_group,
                     parallel_group_id, needs_boiler, needs_cooling_zone,
                     needs_operator, needs_lab, duration_formula,
                     comment, version_id)
                SELECT
                    id, organization_id, product_id, stage_order, name,
                    base_duration_mins, is_setup, is_parallel_group,
                    parallel_group_id, needs_boiler, needs_cooling_zone,
                    needs_operator, needs_lab, duration_formula,
                    comment, :version_id
                FROM operation_template
                WHERE organization_id = :org_id
                ON CONFLICT (id, version_id) DO NOTHING
            """),
            {"version_id": version_id, "org_id": org_id},
        )
    operations_count = operations_result.rowcount or 0

    # ==========================================
    # 4. CALENDAR_EVENT → calendar_snapshot
    # ==========================================
    calendar_result = await session.execute(
        text("""
            INSERT INTO calendar_snapshot
                (id, organization_id, equipment_id, event_type,
                 starts_at, ends_at, comment, version_id)
            SELECT
                id, organization_id, equipment_id, event_type,
                starts_at, ends_at, comment, :version_id
            FROM calendar_event
            WHERE organization_id = :org_id
            ON CONFLICT (id, version_id) DO NOTHING
        """),
        {"version_id": version_id, "org_id": org_id},
    )
    calendar_count = calendar_result.rowcount or 0

    stats = {
        "equipment": equipment_count,
        "products": products_count,
        "operations": operations_count,
        "calendar_events": calendar_count,
    }

    log_with_context(
        logger, logging.INFO,
        f"[snapshot] Готово для version={str(version_id)[:8]}: "
        f"equipment={equipment_count}, products={products_count}, "
        f"operations={operations_count}, calendar={calendar_count}",
        stage="snapshot", org_id=str(org_id),
    )

    return stats


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

async def _has_column(
        session: AsyncSession,
        table: str,
        column: str,
) -> bool:
    """
    Проверяет, существует ли колонка в таблице.

    Нужно для graceful-совместимости со старыми схемами БД,
    где ещё не применены некоторые миграции.
    """
    result = await session.execute(
        text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
        """),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


async def snapshot_exists(
        session: AsyncSession,
        version_id: UUID,
) -> bool:
    """
    Проверяет, есть ли хотя бы один снапшот для указанной версии.

    Используется UI/API для определения, является ли план «пустым»
    (создан, но не рассчитан) или «реальным» (есть снапшоты).
    """
    result = await session.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM equipment_snapshot WHERE version_id = :vid
                UNION ALL
                SELECT 1 FROM product_snapshot WHERE version_id = :vid
                UNION ALL
                SELECT 1 FROM operation_snapshot WHERE version_id = :vid
            ) AS has_snapshot
        """),
        {"vid": version_id},
    )
    row = result.fetchone()
    return bool(row.has_snapshot) if row else False