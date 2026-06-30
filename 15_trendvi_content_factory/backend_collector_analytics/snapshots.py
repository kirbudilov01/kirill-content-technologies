from typing import List, Dict, Any
from datetime import datetime, timezone


def build_video_snapshots(
    videos: List[Dict[str, Any]],
    channel_id: str,
    owner_id: int,
    subscribers: int,
) -> List[Dict[str, Any]]:
    """
    Приводит видео к формату snapshot'ов.
    Совместимо со старой БД-логикой.
    """
    snapshots: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for v in videos:
        snapshots.append(
            {
                "channel_id": channel_id,
                "owner_id": owner_id,
                "video_id": v["video_id"],
                "url": v.get("url"),
                "title": v.get("title"),
                "published_at": v.get("published_at"),
                "duration_seconds": v.get("duration_seconds"),
                "is_short": v.get("is_short", False),
                "views": v.get("views", 0),
                "likes": v.get("likes", 0),
                "comments": v.get("comments", 0),
                "subscribers": subscribers,
                "er": v.get("er", 0),
                "thumbnail": v.get("thumbnail"),
                "created_at": now,
            }
        )

    return snapshots
