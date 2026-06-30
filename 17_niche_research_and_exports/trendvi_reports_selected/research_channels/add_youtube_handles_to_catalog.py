import asyncio
import json
import sys

from collector.yt_client import get_shared_yt_client
from trendvi_search.catalog import upsert_channels


OWNER_ID = 1


async def resolve_handle(handle: str) -> dict:
    normalized = handle.strip().lstrip("@")
    if not normalized:
        raise ValueError("empty handle")

    client = await get_shared_yt_client()
    handle_result = await client.get_channel_by_handle(OWNER_ID, normalized)
    items = handle_result.get("items", [])
    if not items:
        raise RuntimeError(f"Channel handle not found: @{normalized}")

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
    custom = snippet.get("customUrl") or f"@{normalized}"
    url_handle = custom if str(custom).startswith("@") else f"@{normalized}"

    return {
        "id": channel_id,
        "title": snippet.get("title") or normalized,
        "description": snippet.get("description") or "",
        "url": f"https://www.youtube.com/{url_handle}",
        "thumbnail": (((snippet.get("thumbnails") or {}).get("high") or {}).get("url") or ""),
        "subscribers": int(stats.get("subscriberCount") or 0),
        "views": int(stats.get("viewCount") or 0),
        "verified": True,
    }


async def main():
    handles = sys.argv[1:]
    if not handles:
        raise SystemExit("usage: python add_youtube_handles_to_catalog.py handle [handle...]")

    channels = []
    for handle in handles:
        try:
            channel = await resolve_handle(handle)
            channels.append(channel)
            print(json.dumps({"ok": True, **channel}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"ok": False, "handle": handle, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)

    if channels:
        keywords = ["Claude Code", "Codex AI coding", "AI coding agents", "vibe coding"]
        for keyword in keywords:
            await upsert_channels(channels, keyword, "en")


asyncio.run(main())
