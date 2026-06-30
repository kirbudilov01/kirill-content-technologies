import asyncio
import csv
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [
    "eceb8371-3c34-41dc-b1ab-44182b3b4f86",
    "cb3ab959-52e7-4553-bec4-a5e30cbfc442",
    "7ec7b793-6d32-42ba-9e7b-846a04df53a7",
    "5d32a6aa-fdf8-46d0-a48d-d6c579c64169",
    "5c52d9e5-cd25-47ee-96f1-08f40e222ba9",
    "80f916ee-b671-459d-90e0-1be18d9b8134",
    "d4fd642d-7a2b-4fe2-89c4-76642146db7b",
    "b247d282-a274-41c0-86d7-50265459c13a",
    "76aa38a9-0a29-42bd-9e78-978e86156f11",
    "822de3c7-6855-426b-8522-1e5df1c276ed",
    "ddf034f4-be29-4ffa-be13-06a99111bef4",
    "769acfb2-f3ea-4320-a65b-f7c193fc930d",
    "67df4574-162f-47e3-a081-74268e6cb368",
    "76cb30fc-e670-46e6-9b1c-b81d506c4875",
    "645208c5-f640-4d42-8dc8-8d2889d1b9a7",
    "f4b4c5b9-9533-4395-b611-a4ae578eaa39",
    "f96c2684-4453-404e-8335-2aa57c487b31",
    "8dd009be-992e-4256-9a77-796d2919f49c",
    "3d9a2bd0-8b13-4940-bea4-62e9bce54575",
    "88481d9d-eae2-4e92-bfea-dcc0fc5357df",
]

CORE = [
    "claude",
    "anthropic",
    "claude code",
    "codex",
    "openai codex",
    "chatgpt codex",
    "cursor",
    "windsurf",
    "replit",
    "lovable",
    "mcp",
]
DEV = [
    "coding",
    "developer",
    "software",
    "programming",
    "full stack",
    "build apps",
    "app builder",
    "devtools",
    "ide",
    "terminal",
]
AGENTIC = [
    "agent",
    "agents",
    "agentic",
    "automation",
    "workflow",
    "ai coding",
    "vibe coding",
]
AI = ["ai", "llm", "gpt", "chatgpt", "gemini", "artificial intelligence"]
NEG = [
    "minecraft",
    "roblox",
    "fortnite",
    "gaming",
    "music",
    "lyrics",
    "movie",
    "football",
    "basketball",
    "nba",
    "valorant",
    "real estate",
    "crypto trading",
    "forex",
    "dating",
]


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
    title_hits = hits(title, CORE) * 9 + hits(title, DEV) * 5 + hits(title, AGENTIC) * 5 + hits(title, AI) * 3
    text_hits = hits(text, CORE) * 5 + hits(text, DEV) * 3 + hits(text, AGENTIC) * 3 + hits(text, AI) * 2
    query_bonus = int(row["query_count"] or 0) * 8
    rank_bonus = max(0, 12 - int(row["best_worker_rank"] or 20))
    views_bonus = min(10, len(str(int(row["views"] or 0))))
    subs_bonus = min(10, len(str(int(row["subscribers"] or 0))))
    penalty = hits(text, NEG) * 30
    return title_hits + text_hits + query_bonus + rank_bonus + views_bonus + subs_bonus - penalty


def tier(row, value):
    text = f"{row['title'] or ''} {row['description'] or ''}".lower()
    core = hits(text, CORE)
    dev = hits(text, DEV)
    agentic = hits(text, AGENTIC)
    ai = hits(text, AI)
    neg = hits(text, NEG)
    if neg and not (core >= 2 or (dev and ai)):
        return "reject_review"
    if core and (dev or agentic) and value >= 50:
        return "strong"
    if (core or ai) and dev and value >= 40:
        return "good"
    if (core or agentic) and value >= 34:
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
        item["description_snippet"] = re.sub(r"\s+", " ", (item.get("description") or "")).strip()[:280]
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
        "best_worker_rank",
        "title",
        "url",
        "channel_id",
        "subscribers",
        "views",
        "verified",
        "matched_queries",
        "description_snippet",
    ])
    for index, item in enumerate(items, 1):
        suggested = "approve" if item["tier"] in {"strong", "good"} and index <= 140 else "review"
        if item["tier"] in {"weak_review", "reject_review"} or index > 220:
            suggested = "reject"
        writer.writerow([
            index,
            suggested,
            item["tier"],
            item["score"],
            item["query_count"],
            item["best_worker_rank"],
            item["title"],
            item["url"],
            item["channel_id"],
            item["subscribers"],
            item["views"],
            item["verified"],
            item["matched_queries"],
            item["description_snippet"],
        ])


asyncio.run(main())
