import asyncio
import csv
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [
    "e5856a22-d9f5-40d7-951c-4489e9ce136c",
    "9aa7d0c2-55bd-478b-90f5-a5af3c1b226d",
    "e1210a5e-9d20-4ceb-bddf-2414b709bcc3",
    "dc0c4e0a-fa2b-4f64-b8fb-df7a2efc20fb",
    "a405c20d-b21f-40a5-ad94-af129a1ad707",
    "3ce583d9-96f7-4b3d-89e5-29a021f96a75",
    "f59e222f-d7db-4e25-98c4-b5c79b02ba5b",
    "ae7e833f-c382-4cff-b667-a25341540973",
    "98ee5f18-6720-4752-a239-9b15fe205d62",
    "93fece52-efa0-4076-96f2-9beb5d5f6982",
    "38eb54a8-abe4-458a-b9a1-1d0b100a72cc",
    "c4c38599-c570-45e2-a9c8-2dee1dfff3c0",
    "b4156c0a-5a7c-4dd4-b2af-44616d8828d9",
    "5b7972d2-df6d-4eb3-9688-bbde24c021cb",
    "30dad24d-2077-40b7-a30e-23dba0854d0f",
    "025766c6-556d-42e8-b0fb-c3c0311bcd9a",
    "b265d1f4-905d-4851-b7b3-8c9d4440aabb",
    "83be5897-8423-4cd9-b988-cc4904da1361",
    "85ef2029-9c4a-4339-a9e9-87ef1c2ac736",
    "faad1360-c993-4fd9-a91e-31f454dd19fa",
]

CORE = ["vibe coding", "ai coding", "prompt to app", "build apps", "app builder", "prototype", "ship apps"]
TOOLS = ["claude code", "codex", "cursor", "lovable", "replit", "bolt", "v0", "windsurf", "cline", "mcp"]
DEV = ["developer", "coding", "software", "full stack", "saas", "startup", "build", "app", "web app"]
AGENTIC = ["agentic", "agent", "agents", "ai", "llm"]
NEG = ["music", "lyrics", "minecraft", "roblox", "gaming", "football", "basketball", "fashion", "real estate"]


def hits(text, terms):
    total = 0
    for term in terms:
        if re.fullmatch(r"[a-z0-9.+-]+", term):
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
                total += 1
        elif term in text:
            total += 1
    return total


def score(row):
    title = (row["title"] or "").lower()
    desc = (row["description"] or "").lower()
    text = f"{title} {desc}"
    return (
        hits(title, CORE) * 9
        + hits(title, TOOLS) * 8
        + hits(title, DEV) * 4
        + hits(title, AGENTIC) * 4
        + hits(text, CORE) * 5
        + hits(text, TOOLS) * 5
        + hits(text, DEV) * 3
        + hits(text, AGENTIC) * 3
        + int(row["query_count"] or 0) * 8
        + max(0, 12 - int(row["best_worker_rank"] or 20))
        + min(10, len(str(int(row["subscribers"] or 0))))
        + min(10, len(str(int(row["views"] or 0))))
        - hits(text, NEG) * 30
    )


def tier(row, value):
    text = f"{row['title'] or ''} {row['description'] or ''}".lower()
    core = hits(text, CORE)
    tools = hits(text, TOOLS)
    dev = hits(text, DEV)
    ai = hits(text, AGENTIC)
    neg = hits(text, NEG)
    if neg and not (core or tools):
        return "reject_review"
    if (core or tools >= 2) and dev and value >= 50:
        return "strong"
    if (core or tools) and (dev or ai) and value >= 38:
        return "good"
    if (core or tools or (dev and ai)) and value >= 30:
        return "maybe"
    return "weak_review"


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT c.channel_id, c.title, c.description, c.url, c.subscribers, c.views, c.verified,
                   COUNT(DISTINCT q.task_id)::int AS query_count,
                   string_agg(DISTINCT q.query_text, '; ' ORDER BY q.query_text) AS matched_queries,
                   MIN(qc.rank_order)::int AS best_worker_rank
            FROM yt_search_query_channels qc
            JOIN yt_search_queries q ON q.task_id = qc.task_id
            JOIN yt_channel_catalog c ON c.channel_id = qc.channel_id
            WHERE q.task_id = ANY($1::text[]) AND q.status = 'success'
            GROUP BY c.channel_id, c.title, c.description, c.url, c.subscribers, c.views, c.verified
            """,
            TASK_IDS,
        )
    finally:
        await conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["score"] = score(item)
        item["tier"] = tier(item, item["score"])
        item["description_snippet"] = re.sub(r"\s+", " ", (item.get("description") or "")).strip()[:280]
        items.append(item)

    rank = {"strong": 4, "good": 3, "maybe": 2, "weak_review": 1, "reject_review": 0}
    items.sort(key=lambda x: (rank[x["tier"]], x["score"], x["query_count"], x["views"] or 0), reverse=True)
    writer = csv.writer(sys.stdout)
    writer.writerow(["rank", "suggested_status", "tier", "score", "query_count", "best_worker_rank", "title", "url", "channel_id", "subscribers", "views", "verified", "matched_queries", "description_snippet"])
    for idx, item in enumerate(items, 1):
        suggested = "approve" if item["tier"] in {"strong", "good"} and idx <= 160 else "review"
        if item["tier"] in {"weak_review", "reject_review"} or idx > 260:
            suggested = "reject"
        writer.writerow([idx, suggested, item["tier"], item["score"], item["query_count"], item["best_worker_rank"], item["title"], item["url"], item["channel_id"], item["subscribers"], item["views"], item["verified"], item["matched_queries"], item["description_snippet"]])


asyncio.run(main())
