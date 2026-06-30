import asyncio
import sys

import asyncpg
from db import _get_dsn


PATTERNS = sys.argv[1:]


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        for pattern in PATTERNS:
            rows = await conn.fetch(
                """
                SELECT title, url, subscribers,
                       left(regexp_replace(coalesce(description,''), '[[:space:]]+', ' ', 'g'), 180) AS description
                FROM yt_channel_catalog
                WHERE lower(coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || coalesce(url,'')) LIKE $1
                ORDER BY subscribers DESC NULLS LAST
                LIMIT 8
                """,
                f"%{pattern.lower()}%",
            )
            if rows:
                print(f"\nPATTERN {pattern}")
                for row in rows:
                    print(f"{row['subscribers']}\t{row['title']}\t{row['url']}\t{row['description']}")
    finally:
        await conn.close()


asyncio.run(main())
