import asyncio
import csv
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [
    "ff96abde-62ac-4e8d-8dec-32b925405e3c",
    "8c754dba-295b-48c4-b0c5-adb5358d9977",
    "cefc3d11-fa59-462f-8a6e-5f1d19e9e36a",
    "2b7ed73a-ca9b-4370-b552-7669c6f21ea9",
    "661bcd5e-7f38-4f0a-926a-cd1f6582061f",
    "d5c49a61-be5e-472a-850c-d1712aed3100",
    "ab5e6074-1c32-4780-8932-25de749ee43d",
    "6d3861cc-8c64-42e3-b6d6-e69f421fbed1",
    "d4c3022c-3ebd-4074-9c3e-ad2e6dfa1d00",
    "245034b4-ea12-4bcd-b08b-aaa3ffbedaa5",
    "641f25d0-1eeb-4d5b-a87e-0082c1a631aa",
    "9eddf5e5-4e78-4c09-a34f-65e78a523ab9",
    "c745ebf0-3afd-4f3f-84e9-1c4d2e210226",
    "c4b70cdf-985e-4dd5-b832-dc232a6fbb01",
    "6dde01a6-b0a1-4eff-8a7f-925b98a01044",
    "6661184e-bf8b-406d-8e4c-f7d194137de8",
]

CORE = ["ai", "artificial intelligence", "chatgpt", "openai", "claude", "anthropic", "codex", "cursor", "llm", "gpt", "gemini"]
AGENT = ["agent", "agents", "agentic", "autonomous"]
AUTO = ["automation", "automate", "workflow", "n8n", "zapier", "make.com", "make ", "no-code", "nocode", "low-code", "productivity"]
DEV = ["langchain", "crewai", "autogpt", "coding", "developer", "software", "build apps", "replit", "lovable", "tools", "saas", "rag"]
NEG = ["real estate", "realtor", "insurance", "travel agent", "agent 00", "fashion", "football", "soccer", "basketball", "nba", "gaming", "roblox", "gta", "valorant", "call of duty", "estate agent", "secret agent", "sports agent", "modeling agency", "news agents", "crime agents", "agents of sigmar", "football agents", "travel agents"]


def hits(text, terms):
    count = 0
    for term in terms:
        if re.fullmatch(r"[a-z0-9.+-]+", term):
            pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
            if re.search(pattern, text):
                count += 1
        elif term in text:
            count += 1
    return count


def score(row):
    title = (row["title"] or "").lower()
    desc = (row["description"] or "").lower()
    text = f"{title} {desc}"
    title_hits = hits(title, CORE) * 8 + hits(title, AGENT) * 6 + hits(title, AUTO) * 5 + hits(title, DEV) * 5
    text_hits = hits(text, CORE) * 4 + hits(text, AGENT) * 3 + hits(text, AUTO) * 3 + hits(text, DEV) * 3
    query_bonus = int(row["query_count"] or 0) * 7
    views_bonus = min(12, len(str(int(row["views"] or 0))))
    subs_bonus = min(10, len(str(int(row["subscribers"] or 0))))
    penalty = hits(text, NEG) * 25
    return title_hits + text_hits + query_bonus + views_bonus + subs_bonus - penalty


def tier(row, value):
    text = f"{row['title'] or ''} {row['description'] or ''}".lower()
    core = hits(text, CORE)
    ag = hits(text, AGENT)
    auto = hits(text, AUTO)
    dev = hits(text, DEV)
    neg = hits(text, NEG)
    if neg and not (core >= 2 or auto or dev):
        return "reject_review"
    if core and (ag or auto or dev) and value >= 45:
        return "strong"
    if core and value >= 35:
        return "good"
    if (auto or dev) and ag and value >= 35:
        return "good"
    if value >= 28 and (core or auto or dev):
        return "maybe"
    return "weak_review"


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT
              c.channel_id,
              c.title,
              c.description,
              c.url,
              c.subscribers,
              c.views,
              c.verified,
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
        item["description_snippet"] = re.sub(r"\s+", " ", (item.get("description") or "")).strip()[:260]
        items.append(item)

    tier_rank = {"strong": 4, "good": 3, "maybe": 2, "weak_review": 1, "reject_review": 0}
    items.sort(
        key=lambda item: (
            tier_rank.get(item["tier"], 0),
            item["score"],
            item["query_count"],
            item["views"] or 0,
        ),
        reverse=True,
    )

    writer = csv.writer(sys.stdout)
    writer.writerow([
        "rank",
        "suggested_status",
        "tier",
        "score",
        "query_count",
        "title",
        "url",
        "subscribers",
        "views",
        "verified",
        "matched_queries",
        "description_snippet",
    ])
    for index, item in enumerate(items, 1):
        suggested = "approve" if item["tier"] in {"strong", "good"} and index <= 120 else "review"
        if item["tier"] in {"weak_review", "reject_review"} or index > 180:
            suggested = "reject"
        writer.writerow([
            index,
            suggested,
            item["tier"],
            item["score"],
            item["query_count"],
            item["title"],
            item["url"],
            item["subscribers"],
            item["views"],
            item["verified"],
            item["matched_queries"],
            item["description_snippet"],
        ])


asyncio.run(main())
