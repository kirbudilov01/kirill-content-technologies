import asyncio
import os

import asyncpg
from db import _get_dsn


TASK_IDS = [x.strip() for x in os.environ["TASK_IDS"].split(",") if x.strip()]


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            "SELECT status, count(*) c FROM yt_search_queries WHERE task_id = ANY($1::text[]) GROUP BY status ORDER BY status",
            TASK_IDS,
        )
        print({row["status"]: row["c"] for row in rows})
        pending = await conn.fetch(
            """
            SELECT task_id, status, query_text, error_message
            FROM yt_search_queries
            WHERE task_id = ANY($1::text[]) AND status <> 'success'
            ORDER BY created_at
            LIMIT 30
            """,
            TASK_IDS,
        )
        for row in pending:
            print(dict(row))
    finally:
        await conn.close()


asyncio.run(main())
