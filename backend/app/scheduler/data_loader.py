# backend/app/scheduler/data_loader.py
"""
Загрузчик данных для планировщика.

Итерация 2:
- Читает material, material_stock, material_supply, recipe, recipe_item
  для расчёта потребности в сырье и подсказок Advisor.
"""

import asyncio
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


class DataLoader:
    def __init__(self, org_id: UUID):
        self.org_id = org_id
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def load_all(self) -> Dict[str, Any]:
        async with self.async_session() as session:
            return {
                "batches": await self._load_batches(session),
                "equipment": await self._load_equipment(session),
                "products": await self._load_products(session),
                "operation_templates": await self._load_operations(session),
                "setup_matrix": await self._load_setup_matrix(session),
                "calendar_events": await self._load_calendar(session),
                "resource_pools": await self._load_resources(session),
                "org_settings": await self._load_org_settings(session),
                "equipment_links": await self._load_equipment_links(session),
                "gp_products": await self._load_gp_products(session),
                # NEW в итерации 2
                "materials": await self._load_materials(session),
                "material_stocks": await self._load_material_stocks(session),
                "material_supplies": await self._load_material_supplies(session),
                "recipes": await self._load_recipes(session),
            }

    async def _load_batches(self, session) -> List[Dict]:
        result = await session.execute(
            text("""
                SELECT b.id, b.product_id, b.volume_kg, b.assigned_equipment_id,
                p.name as product_name, p.viscosity_coeff, p.requires_heating,
                e.name as equipment_name, e.type as equipment_type,
                e.volume_kg as equipment_volume, e.speed_coeff, e.mixer_type,
                po.product_id AS gp_product_id
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

    async def _load_resources(self, session) -> Dict[str, int]:
        result = await session.execute(
            text("""
                SELECT type, SUM(capacity) as total_capacity
                FROM resource_pool WHERE organization_id = :org_id
                GROUP BY type
            """),
            {"org_id": self.org_id},
        )
        return {row.type: row.total_capacity for row in result.fetchall()}

    async def _load_org_settings(self, session) -> Dict[str, Any]:
        result = await session.execute(
            text("""
                SELECT setting_key, setting_value
                FROM organization_settings
                WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {row.setting_key: row.setting_value for row in result.fetchall()}

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

    # ==========================================
    # НОВОЕ В ИТЕРАЦИИ 2: МАТЕРИАЛЫ
    # ==========================================

    async def _load_materials(self, session) -> Dict[str, Dict]:
        """Справочник материалов {material_id: {...}}."""
        result = await session.execute(
            text("""
                SELECT id, code, name, unit, category
                FROM material WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}

    async def _load_material_stocks(self, session) -> Dict[str, Dict]:
        """Остатки {material_id: {qty, reserved_qty}}."""
        result = await session.execute(
            text("""
                SELECT material_id, qty, reserved_qty
                FROM material_stock WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return {str(row.material_id): dict(row._mapping) for row in result.fetchall()}

    async def _load_material_supplies(self, session) -> List[Dict]:
        """График поставок."""
        result = await session.execute(
            text("""
                SELECT id, material_id, expected_at, qty, status
                FROM material_supply WHERE organization_id = :org_id
            """),
            {"org_id": self.org_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def _load_recipes(self, session) -> Dict[str, Dict]:
        """
        Рецептуры {pf_product_id: {base_volume_kg, items: [...]}}.
        Ключ — product_id (ПФ), потому что рецептура относится к ПФ.
        """
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
                    "base_volume_kg": float(row.base_volume_kg) if row.base_volume_kg else 100.0,
                    "items": [],
                }
            if row.material_id is not None:
                recipes[pf_id]["items"].append({
                    "material_id": str(row.material_id),
                    "qty_per_base": float(row.qty_per_base) if row.qty_per_base else 0.0,
                })
        return recipes