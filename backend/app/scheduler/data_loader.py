# backend/app/scheduler/data_loader.py
"""
Загрузчик данных для планировщика.

Итерация 2: material, material_stock, material_supply, recipe, recipe_item.
Итерация 5: batch.is_lab_blocked, batch.lab_status.
Итерация 6: resource_pool с полным списком типов.
Итерация 9 (fix): equipment_capability.
Итерация 11 (Шаг 6): shift, shift_settings.
Итерация 11 (Шаг 5): _load_org_settings → _load_app_settings.
Итерация 12: order_due_date в batch (для tardiness).
Итерация 12 (fix): опциональная session — для what-if сценариев
  (чтобы DataLoader видел незакоммиченные изменения).
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


class DataLoader:
    def __init__(
            self,
            org_id: UUID,
            session: Optional[AsyncSession] = None,
    ):
        """
        Итерация 12 (fix): опциональная session.

        Args:
            org_id: UUID организации.
            session: если передана — используем её (для what-if).
                     Если None — создаём свою (обратная совместимость).
        """
        self.org_id = org_id

        if session is not None:
            # Итерация 12 (fix): используем переданную сессию.
            # Это позволяет what-if сценариям видеть незакоммиченные
            # изменения из транзакции №1.
            self.session = session
            self.engine = None
            self._session_maker = None
            self._owns_session = False
        else:
            # Обратная совместимость: создаём свою сессию.
            self.engine = create_async_engine(
                settings.DATABASE_URL, echo=False
            )
            self._session_maker = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self.session = None
            self._owns_session = True

    async def load_all(self) -> Dict[str, Any]:
        """
        Загружает все данные.

        Итерация 12 (fix): если session передана извне — используем её.
        Иначе — открываем свою.
        """
        if self._owns_session:
            async with self._session_maker() as session:
                return await self._load_all_with_session(session)
        else:
            return await self._load_all_with_session(self.session)

    async def _load_all_with_session(
            self, session: AsyncSession
    ) -> Dict[str, Any]:
        """Внутренняя логика загрузки с переданной сессией."""
        return {
            # ==========================================
            # Основные справочники
            # ==========================================
            "batches": await self._load_batches(session),
            "equipment": await self._load_equipment(session),
            "products": await self._load_products(session),
            "operation_templates": await self._load_operations(session),
            "setup_matrix": await self._load_setup_matrix(session),
            "calendar_events": await self._load_calendar(session),
            "resource_pools": await self._load_resource_pools(session),
            "org_settings": await self._load_app_settings(session),
            "equipment_links": await self._load_equipment_links(session),
            "gp_products": await self._load_gp_products(session),
            "equipment_capability": await self._load_equipment_capability(session),
            "shifts": await self._load_shifts(session),
            "shift_settings": await self._load_shift_settings(session),
            "materials": await self._load_materials(session),
            "material_stocks": await self._load_material_stocks(session),
            "material_supplies": await self._load_material_supplies(session),
            "recipes": await self._load_recipes(session),
        }

    # ==========================================
    # БАЗОВЫЕ СПРАВОЧНИКИ
    # ==========================================

    async def _load_batches(self, session) -> List[Dict]:
        """
        Загружает партии.

        Итерация 5: + lab_status, is_lab_blocked.
        Итерация 12: + order_due_date.
        """
        result = await session.execute(
            text("""
                SELECT b.id, b.product_id, b.volume_kg, b.assigned_equipment_id,
                p.name as product_name, p.viscosity_coeff, p.requires_heating,
                e.name as equipment_name, e.type as equipment_type,
                e.volume_kg as equipment_volume, e.speed_coeff, e.mixer_type,
                po.product_id AS gp_product_id,
                po.due_date AS order_due_date,
                COALESCE(b.is_lab_blocked, FALSE) AS is_lab_blocked,
                COALESCE(b.lab_status, 'NOT_REQUIRED') AS lab_status,
                b.lab_block_reason
                FROM batch b
                JOIN product p ON p.id = b.product_id
                LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
                LEFT JOIN production_order po ON po.id = b.order_id
                WHERE b.organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_equipment(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT id, code, name, type, volume_kg, speed_coeff, mixer_type
                FROM equipment WHERE organization_id = :org_id AND is_active = TRUE
            """),
            {"org_id": self.org_id},
        )
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}

    async def _load_products(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT id, code, name, type, viscosity_coeff, requires_heating,
                       bottle_volume_l, fill_speed_per_min, route_type
                FROM product WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}

    async def _load_gp_products(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT id, code, name, type, bottle_volume_l, fill_speed_per_min
                FROM product
                WHERE organization_id = :org_id AND type = 'GP'
            """),
            {"org_id": self.org_id},
        )
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}

    async def _load_operations(self, session) -> Dict[str, List[Dict]]:
        result = await session.execute(
            text("""
                SELECT id, product_id, stage_order, name, base_duration_mins,
                needs_boiler, needs_cooling_zone, needs_operator, needs_lab,
                duration_formula, parallel_group_id, operator_pool
                FROM operation_template
                WHERE organization_id = :org_id
                ORDER BY product_id, stage_order
            """),
            {"org_id": self.org_id},
        )
        ops_by_product: Dict[str, List[Dict]] = {}
        for row in result.fetchall():
            d = dict(row._mapping)
            prod_id = str(d["product_id"])
            ops_by_product.setdefault(prod_id, []).append(d)
        return ops_by_product

    async def _load_setup_matrix(self, session) -> Dict[tuple, int]:
        result = await session.execute(
            text("""
                SELECT from_product_id, to_product_id, setup_mins
                FROM setup_matrix WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {
            (str(row.from_product_id), str(row.to_product_id)): row.setup_mins
            for row in result.fetchall()
        }

    async def _load_calendar(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id, equipment_id, event_type, starts_at, ends_at
                FROM calendar_event WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_resource_pools(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id, name, type, capacity, comment
                FROM resource_pool
                WHERE organization_id = :org_id
                ORDER BY type
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_app_settings(self, session) -> Dict[str, Any]:
        result = await session.execute(
            text("""
                SELECT setting_key, setting_value
                FROM app_settings
                WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {
            row.setting_key: row.setting_value
            for row in result.fetchall()
        }

    async def _load_equipment_links(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT from_equipment_id, to_equipment_id, is_direct
                FROM equipment_link
                WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_equipment_capability(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT equipment_id, product_id, max_fill_percent
                FROM equipment_capability
                WHERE organization_id = :org_id
                ORDER BY equipment_id, product_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_shifts(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id, name, starts_at, ends_at, is_working, comment
                FROM shift
                WHERE organization_id = :org_id
                ORDER BY starts_at
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_shift_settings(self, session) -> Dict[str, Any]:
        """Загружает настройки режима смен из app_settings."""
        result = await session.execute(
            text("""
                SELECT setting_key, setting_value
                FROM app_settings
                WHERE organization_id = :org_id
                  AND setting_key IN (
                    'shift_mode',
                    'shift_intervals',
                    'shift_duration_hours',
                    'allow_weekend_work'
                  )
            """),
            {"org_id": self.org_id},
        )
        rows = {row.setting_key: row.setting_value for row in result.fetchall()}

        shift_mode = "2x12"
        if rows.get("shift_mode") is not None:
            raw = rows["shift_mode"]
            if isinstance(raw, str):
                shift_mode = raw.strip().strip('"').strip("'")
            else:
                shift_mode = str(raw)

        shift_intervals: List[Dict[str, str]] = [
            {"start": "08:00", "end": "20:00"},
            {"start": "20:00", "end": "08:00"},
        ]
        if rows.get("shift_intervals") is not None:
            raw = rows["shift_intervals"]
            try:
                if isinstance(raw, str):
                    import json
                    shift_intervals = json.loads(raw)
                elif isinstance(raw, list):
                    shift_intervals = raw
            except (ValueError, TypeError):
                pass

        shift_duration_hours = 12
        if rows.get("shift_duration_hours") is not None:
            raw = rows["shift_duration_hours"]
            try:
                if isinstance(raw, str):
                    shift_duration_hours = int(raw.strip().strip('"').strip("'"))
                elif isinstance(raw, (int, float)):
                    shift_duration_hours = int(raw)
            except (ValueError, TypeError):
                pass

        allow_weekend_work = False
        if rows.get("allow_weekend_work") is not None:
            raw = rows["allow_weekend_work"]
            if isinstance(raw, bool):
                allow_weekend_work = raw
            elif isinstance(raw, str):
                allow_weekend_work = raw.strip().lower() in (
                    "true", "1", "yes", "on",
                )
            elif isinstance(raw, (int, float)):
                allow_weekend_work = bool(raw)

        return {
            "shift_mode": shift_mode,
            "shift_intervals": shift_intervals,
            "shift_duration_hours": shift_duration_hours,
            "allow_weekend_work": allow_weekend_work,
        }

    # ==========================================
    # МАТЕРИАЛЫ
    # ==========================================

    async def _load_materials(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT id, code, name, unit, category
                FROM material WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}

    async def _load_material_stocks(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT material_id, qty, reserved_qty
                FROM material_stock WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {str(row.material_id): dict(row._mapping) for row in result.fetchall()}

    async def _load_material_supplies(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT id, material_id, expected_at, qty, status
                FROM material_supply WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_recipes(self, session) -> Dict[str, Dict]:
        result = await session.execute(
            text("""
                SELECT r.id, r.product_id, r.base_volume_kg,
                       ri.material_id, ri.qty_per_base
                FROM recipe r
                LEFT JOIN recipe_item ri ON ri.recipe_id = r.id
                WHERE r.organization_id = :org_id
                ORDER BY r.product_id, ri.material_id
            """),
            {"org_id": self.org_id},
        )

        recipes: Dict[str, Dict] = {}
        for row in result.fetchall():
            pf_id = str(row.product_id)
            if pf_id not in recipes:
                recipes[pf_id] = {
                    "base_volume_kg": (
                        float(row.base_volume_kg) if row.base_volume_kg else 100.0
                    ),
                    "items": [],
                }
            if row.material_id is not None:
                recipes[pf_id]["items"].append({
                    "material_id": str(row.material_id),
                    "qty_per_base": (
                        float(row.qty_per_base) if row.qty_per_base else 0.0
                    ),
                })
        return recipes