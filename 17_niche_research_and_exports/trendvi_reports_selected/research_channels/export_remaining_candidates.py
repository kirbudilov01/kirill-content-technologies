import asyncio
import csv
import os
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [x.strip() for x in os.environ["TASK_IDS"].split(",") if x.strip()]
NICHE = os.environ["NICHE"]


CONFIGS = {
    "ai_agency": {
        "core": ["ai agency", "automation agency", "ai automation", "ai consultant", "ai consulting", "ai agents", "voice agent", "chatbot", "workflow automation", "n8n", "make.com", "zapier", "gohighlevel"],
        "negative": ["music", "gaming", "minecraft", "roblox", "football", "fashion", "movie", "kids", "crypto price", "plc", "industrial automation"],
    },
    "open_source_projects": {
        "core": ["open source", "github", "self hosted", "self-hosted", "repository", "repositories", "developer tools", "dev tools", "homelab", "linux", "llm", "ai agents", "free alternatives", "open-source"],
        "negative": ["music", "gaming", "minecraft", "roblox", "football", "fashion", "movie", "kids", "open source intelligence", "osint crime"],
    },
    "video_data_service": {
        "core": ["youtube analytics", "youtube seo", "creator analytics", "social media analytics", "content research", "trend research", "competitor analysis", "vidiq", "tubebuddy", "viral", "audience intelligence", "social listening", "market research", "content strategy"],
        "negative": ["music", "gaming", "minecraft", "roblox", "football", "fashion", "movie", "kids", "stock market", "crypto trading"],
    },
}


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
    cfg = CONFIGS[NICHE]
    title = (row["title"] or "").lower()
    desc = (row["description"] or "").lower()
    queries = (row["matched_queries"] or "").lower()
    text = f"{title} {desc} {queries}"
    return (
        hits(title, cfg["core"]) * 12
        + hits(desc, cfg["core"]) * 5
        + hits(queries, cfg["core"]) * 6
        + int(row["query_count"] or 0) * 8
        + max(0, 12 - int(row["best_worker_rank"] or 20))
        + min(10, len(str(int(row["subscribers"] or 0))))
        + min(10, len(str(int(row["views"] or 0))))
        - hits(text, cfg["negative"]) * 40
    )


def tier(row, value):
    cfg = CONFIGS[NICHE]
    text = f"{row['title'] or ''} {row['description'] or ''} {row['matched_queries'] or ''}".lower()
    core = hits(text, cfg["core"])
    neg = hits(text, cfg["negative"])
    if neg and core < 2:
        return "reject_review"
    if core >= 3 and value >= 55:
        return "strong"
    if core >= 2 and value >= 40:
        return "good"
    if core >= 1 and value >= 30:
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
        suggested = "approve" if item["tier"] in {"strong", "good"} and idx <= 180 else "review"
        if item["tier"] in {"weak_review", "reject_review"} or idx > 300:
            suggested = "reject"
        writer.writerow([idx, suggested, item["tier"], item["score"], item["query_count"], item["best_worker_rank"], item["title"], item["url"], item["channel_id"], item["subscribers"], item["views"], item["verified"], item["matched_queries"], item["description_snippet"]])


asyncio.run(main())
