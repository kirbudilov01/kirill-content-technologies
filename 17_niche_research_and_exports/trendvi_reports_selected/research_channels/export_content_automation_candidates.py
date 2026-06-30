import asyncio
import csv
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [
    "6dd327b3-e37a-44d1-b759-5f56bd185506",
    "7268f280-8c30-4611-a0f7-83caae5ac625",
    "587ca628-7344-4628-89f2-ae033f60d641",
    "b68a8c9d-04d2-4707-9def-0336996c7e26",
    "f98e7ac5-f094-4c68-983b-20c8eb83c32a",
    "c2064eea-be83-40b1-bbdb-9ae44f6e5337",
    "3a405824-4ba6-46b2-9cee-773dea31e2c6",
    "34fe41a2-0305-4669-bb9d-ff15f6b93ee1",
    "c0dd4b80-8804-43af-8082-3ed7a7fcf18d",
    "ad599463-2d93-4802-9ac3-95d2da3cb612",
    "8b8664f5-49b0-42c8-8855-4e7a570d9fc5",
    "80f1f25e-4d51-46af-8eb5-3f0eb7956390",
    "d4e9e37c-b353-4681-984e-8562a2a3aa19",
    "b68930b5-7f5d-4cc2-818c-509742cf0669",
    "576dded1-8381-4828-8f93-efc9ad839605",
    "aa7a5b61-ad9b-4c06-8536-0d942bb25856",
    "6fd23451-ba58-4b97-90be-0456d179f045",
    "9b01494a-c804-4ce5-a886-a7aa0bb48cff",
    "d591077b-d4e9-4054-95d7-09e6f1e6b70c",
    "acf3bf24-cff9-410f-a659-cb2cbfe0997e",
]

CORE = ["content", "creator", "creators", "shorts", "video", "podcast", "newsletter", "social media"]
AUTO = ["automation", "automate", "autopost", "auto post", "workflow", "repurposing", "repurpose", "distribution"]
TOOLS = ["ai", "agent", "agents", "n8n", "zapier", "make.com", "postiz", "buffer", "hootsuite", "metricool", "opus", "vidyo", "descript"]
FORMAT = ["faceless", "shorts generator", "clips", "clip", "reels", "tiktok", "youtube shorts", "content machine"]
NEG = ["minecraft", "roblox", "football", "nba", "music", "movie", "lyrics", "factory automation", "industrial automation", "plc", "scada"]


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
        hits(title, CORE) * 6
        + hits(title, AUTO) * 8
        + hits(title, TOOLS) * 5
        + hits(title, FORMAT) * 7
        + hits(text, CORE) * 3
        + hits(text, AUTO) * 5
        + hits(text, TOOLS) * 3
        + hits(text, FORMAT) * 4
        + int(row["query_count"] or 0) * 8
        + max(0, 12 - int(row["best_worker_rank"] or 20))
        + min(10, len(str(int(row["subscribers"] or 0))))
        + min(10, len(str(int(row["views"] or 0))))
        - hits(text, NEG) * 30
    )


def tier(row, value):
    text = f"{row['title'] or ''} {row['description'] or ''}".lower()
    core = hits(text, CORE)
    auto = hits(text, AUTO)
    tools = hits(text, TOOLS)
    fmt = hits(text, FORMAT)
    neg = hits(text, NEG)
    if neg and not (core and auto):
        return "reject_review"
    if auto and (core or fmt) and (tools or fmt) and value >= 50:
        return "strong"
    if (auto or tools) and (core or fmt) and value >= 38:
        return "good"
    if (core or auto or tools or fmt) and value >= 30:
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
