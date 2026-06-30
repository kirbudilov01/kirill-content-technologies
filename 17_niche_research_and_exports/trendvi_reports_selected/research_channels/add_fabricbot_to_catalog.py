import asyncio
import json

from collector.yt_client import get_shared_yt_client
from trendvi_search.catalog import upsert_channels


OWNER_ID = 1
HANDLE = "fabricbotecosystem"


async def main():
    client = await get_shared_yt_client()
    handle_result = await client.get_channel_by_handle(OWNER_ID, HANDLE)
    items = handle_result.get("items", [])
    if not items:
        raise RuntimeError(f"Channel handle not found: @{HANDLE}")

    channel_id = items[0]["id"]

    def call(youtube, **kwargs):
        return youtube.channels().list(**kwargs).execute()

    full = await client.safe_execute(
        owner_id=OWNER_ID,
        func=call,
        part="snippet,statistics,brandingSettings",
        id=channel_id,
        maxResults=1,
    )
    item = full["items"][0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    custom = snippet.get("customUrl") or f"@{HANDLE}"
    url_handle = custom if str(custom).startswith("@") else f"@{HANDLE}"

    channel = {
        "id": channel_id,
        "title": snippet.get("title") or "Fabric Bot Ecosystem",
        "description": snippet.get("description") or "",
        "url": f"https://www.youtube.com/{url_handle}",
        "thumbnail": (((snippet.get("thumbnails") or {}).get("high") or {}).get("url") or ""),
        "subscribers": int(stats.get("subscriberCount") or 0),
        "views": int(stats.get("viewCount") or 0),
        "verified": True,
    }

    await upsert_channels([channel], "fabricbot ecosystem", "en")
    await upsert_channels([channel], "AI agents", "en")
    await upsert_channels([channel], "AI bot ecosystem", "en")
    print(json.dumps(channel, ensure_ascii=False))


asyncio.run(main())
