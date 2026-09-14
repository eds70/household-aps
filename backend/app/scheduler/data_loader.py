import asyncio
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://aps:aps_secret@localhost:5432/household"
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

class DataLoader:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URL, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
    
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
            }
    
    async def _load_batches(self, session) -> List[Dict]:
        result = await session.execute(text("""
            SELECT b.id, b.product_id, b.volume_kg, b.assigned_equipment_id,
                   p.name as product_name, p.viscosity_coeff, p.requires_heating,
                   e.name as equipment_name, e.type as equipment_type,
                   e.volume_kg as equipment_volume, e.speed_coeff, e.mixer_type
            FROM batch b
            JOIN product p ON p.id = b.product_id
            LEFT JOIN equipment e ON e.id = b.assigned_equipment_id
            WHERE b.organization_id = :org_id
        """), {"org_id": ORG_ID})
        return [dict(row._mapping) for row in result.fetchall()]
    
    async def _load_equipment(self, session) -> Dict[str, Dict]:
        result = await session.execute(text("""
            SELECT id, name, type, volume_kg, speed_coeff, mixer_type
            FROM equipment WHERE organization_id = :org_id AND is_active = TRUE
        """), {"org_id": ORG_ID})
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}
    
    async def _load_products(self, session) -> Dict[str, Dict]:
        result = await session.execute(text("""
            SELECT id, code, name, type, viscosity_coeff, requires_heating
            FROM product WHERE organization_id = :org_id
        """), {"org_id": ORG_ID})
        return {str(row.id): dict(row._mapping) for row in result.fetchall()}
    
    async def _load_operations(self, session) -> Dict[str, List[Dict]]:
        result = await session.execute(text("""
            SELECT id, product_id, stage_order, name, base_duration_mins,
                   needs_boiler, needs_cooling_zone, needs_operator, needs_lab,
                   duration_formula, parallel_group_id
            FROM operation_template WHERE organization_id = :org_id ORDER BY product_id, stage_order
        """), {"org_id": ORG_ID})
        ops_by_product = {}
        for row in result.fetchall():
            row_dict = dict(row._mapping)
            prod_id = str(row_dict["product_id"])
            if prod_id not in ops_by_product: ops_by_product[prod_id] = []
            ops_by_product[prod_id].append(row_dict)
        return ops_by_product
    
    async def _load_setup_matrix(self, session) -> Dict[tuple, int]:
        result = await session.execute(text("""
            SELECT from_product_id, to_product_id, setup_mins FROM setup_matrix WHERE organization_id = :org_id
        """), {"org_id": ORG_ID})
        return {(str(row.from_product_id), str(row.to_product_id)): row.setup_mins for row in result.fetchall()}
    
    async def _load_calendar(self, session) -> List[Dict]:
        result = await session.execute(text("""
            SELECT id, equipment_id, event_type, starts_at, ends_at FROM calendar_event WHERE organization_id = :org_id
        """), {"org_id": ORG_ID})
        return [dict(row._mapping) for row in result.fetchall()]
    
    async def _load_resources(self, session) -> Dict[str, int]:
        result = await session.execute(text("""
            SELECT type, SUM(capacity) as total_capacity FROM resource_pool WHERE organization_id = :org_id GROUP BY type
        """), {"org_id": ORG_ID})
        return {row.type: row.total_capacity for row in result.fetchall()}
