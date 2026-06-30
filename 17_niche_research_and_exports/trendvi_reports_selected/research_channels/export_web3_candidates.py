import asyncio
import csv
import re
import sys

import asyncpg
from db import _get_dsn


TASK_IDS = [
    "d79bff7d-39c4-4d23-8f6b-0812ca7b16c5",
    "ce3661ed-359c-425e-9c46-07b6182dc918",
    "d4967cde-441f-44a6-a064-42aa101b07bf",
    "ddecf102-2765-4404-9a74-b089cb722b59",
    "99ce7730-c28a-4e26-b9db-49630a4b102e",
    "21bed488-ee63-4573-85fe-337e5a19e092",
    "3322544b-f0a7-444d-a06f-cabf8956e158",
    "754e0da7-7fc7-42d9-81d8-6a9a85fc1ffe",
    "12eb83ab-00df-49ee-a7d5-06da85dd9cff",
    "6ab4ec14-1ff2-4528-8916-00650cb539b0",
    "437570a0-911d-4533-8af4-727641e1b444",
    "70cfe737-0801-4aaf-a115-62eb4a2034d6",
    "cfedfb60-2604-4e15-9928-46324d9fa8cc",
    "62337cca-b30e-4a4f-828c-3b0ed1b7ba77",
    "df1ae32b-c740-472c-b1a6-73ce67171db1",
    "c4deb18e-846b-477b-870d-5d05bff8ed8a",
    "483f6fba-ba75-478d-9c6d-b040a11b84fb",
    "41713dc3-8cf4-4963-8bf6-cf3ead58f6ee",
    "0f3e0986-d5d2-49a6-aaa5-b8a8bab582b6",
    "3230bd2f-fff8-4f20-abae-3151687b170e",
    "314420ff-7dd9-41d8-a35e-805810dca694",
    "40f6d94d-996e-479b-a335-519d4e9ae739",
    "9e28fe0d-cd22-49f0-9657-10008a059097",
    "20c34dca-db38-415b-bcad-a609d77a1b6f",
    "e306c8b2-a159-4b1f-9da9-ff8be6ad42bc",
    "1026b35f-b8cd-43d7-b84b-d4df4493dd15",
    "6b4dd556-cee0-4140-ac50-87fadfda55ec",
    "09f37760-10f5-4d50-9040-66f5f1f29192",
    "7a5a9eaa-6435-4353-992f-e689026adb3c",
    "76f22901-196f-4b07-982e-949e76cfa256",
    "43e0d5b9-d7eb-4421-af05-7e57b4b54ed6",
    "87f60a25-234f-4a99-b4b1-33bfc4dfcf0f",
    "afce39a7-e033-4263-b6e0-ca1d911fdaef",
    "36691177-1fc7-4a2b-b007-08c818031a82",
    "6759d621-3d60-4602-ae6b-00f0b1eb6006",
    "ae5648c6-8ca8-4bba-b624-00a07648bb75",
]

CORE = ["web3", "crypto", "blockchain", "decentralized", "defi", "wallet"]
TELEGRAM_TON = ["telegram", "ton", "toncoin", "mini app", "mini apps", "bot", "wallet"]
PRODUCT = ["payments", "payment", "rewards", "airdrop", "mini app", "startup", "builders", "developer", "ecosystem", "app"]
MARKETS = ["prediction market", "prediction markets", "polymarket", "kalshi", "betting", "forecast"]
NEG = [
    "price prediction",
    "technical analysis",
    "chart",
    "trading signals",
    "forex",
    "meme coin",
    "memecoin",
    "casino",
    "giveaway",
    "pump",
    "moon",
    "football",
    "gaming highlights",
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
    title_hits = hits(title, CORE) * 6 + hits(title, TELEGRAM_TON) * 9 + hits(title, PRODUCT) * 5 + hits(title, MARKETS) * 8
    text_hits = hits(text, CORE) * 3 + hits(text, TELEGRAM_TON) * 5 + hits(text, PRODUCT) * 3 + hits(text, MARKETS) * 5
    query_bonus = int(row["query_count"] or 0) * 8
    rank_bonus = max(0, 12 - int(row["best_worker_rank"] or 20))
    views_bonus = min(10, len(str(int(row["views"] or 0))))
    subs_bonus = min(10, len(str(int(row["subscribers"] or 0))))
    penalty = hits(text, NEG) * 28
    return title_hits + text_hits + query_bonus + rank_bonus + views_bonus + subs_bonus - penalty


def tier(row, value):
    text = f"{row['title'] or ''} {row['description'] or ''}".lower()
    core = hits(text, CORE)
    tg = hits(text, TELEGRAM_TON)
    product = hits(text, PRODUCT)
    markets = hits(text, MARKETS)
    neg = hits(text, NEG)
    if neg and not (tg or markets or product >= 2):
        return "reject_review"
    if (tg or markets) and (core or product) and value >= 48:
        return "strong"
    if core and product and value >= 38:
        return "good"
    if (core or tg or markets) and value >= 30:
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
        suggested = "approve" if item["tier"] in {"strong", "good"} and index <= 160 else "review"
        if item["tier"] in {"weak_review", "reject_review"} or index > 260:
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
