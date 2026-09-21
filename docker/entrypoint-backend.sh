#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL..."

python - <<'PY'
import asyncio
import os
import sys

import asyncpg

dsn = os.environ.get("DATABASE_URL", "postgresql://aps:aps_secret@postgres:5432/household")
dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")


async def main():
    for attempt in range(60):
        try:
            conn = await asyncpg.connect(dsn, timeout=3)
            await conn.close()
            print("PostgreSQL is ready")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"  attempt {attempt + 1}/60: {exc}")
            await asyncio.sleep(2)
    print("PostgreSQL is not available, aborting")
    sys.exit(1)


asyncio.run(main())
PY

echo "==> Ensuring admin user..."
python -X utf8 -m scripts.create_admin_user || true

echo "==> Starting uvicorn..."
exec python -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8000