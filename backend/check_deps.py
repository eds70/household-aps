# backend/check_deps.py
import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = UUID("00000000-0000-0000-0000-000000000001")

    async with maker() as session:
        # Активная версия
        v = await session.execute(
            text("""
                SELECT id FROM schedule_version
                WHERE organization_id = :org_id AND is_active = TRUE
                LIMIT 1
            """),
            {"org_id": org_id},
        )
        v_row = v.fetchone()
        if not v_row:
            print("Нет активной версии")
            return
        version_id = v_row.id
        print(f"Version: {version_id}")

        # Читаем 5 задач с deps
        result = await session.execute(
            text("""
                SELECT
                    st.id,
                    st.task_role,
                    st.operation_name,
                    st.depends_on_task_ids,
                    jsonb_typeof(st.depends_on_task_ids) AS json_type,
                    jsonb_array_length(st.depends_on_task_ids) AS deps_count
                FROM scheduled_task st
                WHERE st.schedule_version_id = :vid
                  AND st.organization_id = :org_id
                  AND jsonb_array_length(st.depends_on_task_ids) > 0
                LIMIT 5
            """),
            {"vid": version_id, "org_id": org_id},
        )

        rows = result.fetchall()
        print(f"\nНайдено задач с deps > 0: {len(rows)}\n")

        for row in rows:
            print(f"  id={str(row.id)[:8]}")
            print(f"    task_role: {row.task_role}")
            print(f"    operation_name: {row.operation_name}")
            print(f"    json_type: {row.json_type}")
            print(f"    deps_count: {row.deps_count}")
            print(f"    raw: {row.depends_on_task_ids!r}")
            print(f"    python type: {type(row.depends_on_task_ids).__name__}")
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())