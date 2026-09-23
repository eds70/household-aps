# backend/check_api_version.py
import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.api.v1.gantt import _resolve_version_id
from app.core.config import settings


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = UUID("00000000-0000-0000-0000-000000000001")

    async with maker() as session:
        # Что вернёт _resolve_version_id (то же, что API)
        resolved = await _resolve_version_id(session, org_id, None)
        print(f"_resolve_version_id → {resolved}")

        # Что в БД «активная»
        r = await session.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE organization_id = :org_id AND is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """),
            {"org_id": org_id},
        )
        row = r.fetchone()
        print(f"DB active          → {row.id if row else None}")

        # Что фактически читается для этой версии
        if resolved:
            r2 = await session.execute(
                text("""
                    SELECT COUNT(*) AS cnt
                    FROM scheduled_task
                    WHERE schedule_version_id = :vid
                      AND organization_id = :org_id
                      AND jsonb_array_length(depends_on_task_ids) > 0
                """),
                {"vid": resolved, "org_id": org_id},
            )
            row2 = r2.fetchone()
            print(f"Задач с deps > 0: {row2.cnt}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())