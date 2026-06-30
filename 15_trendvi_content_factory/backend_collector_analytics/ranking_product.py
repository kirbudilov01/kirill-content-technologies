# collector/analytics/ranking_product.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    # YouTube отдаёт ISO вроде "2025-12-31T16:15:03Z"
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _days_old(published_at: Optional[str]) -> float:
    dt = _parse_dt(published_at)
    if not dt:
        return 10**9
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


def _hours_old(published_at: Optional[str]) -> float:
    dt = _parse_dt(published_at)
    if not dt:
        return 10**9
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def _calc_er_percent(item: Dict[str, Any], subs: int) -> float:
    subs = max(int(subs or 0), 1)
    likes = int(item.get("likes") or 0)
    comments = int(item.get("comments") or 0)
    return round(((likes + comments) / subs) * 100.0, 2)


def _top20(items: List[Dict[str, Any]], subs: int, min_views: int = 2000, top_n: int = 20) -> List[Dict[str, Any]]:
    out = []
    for x in items:
        views = int(x.get("views") or 0)
        if views <= min_views:
            continue
        xx = dict(x)
        xx["er"] = _calc_er_percent(xx, subs=subs)
        out.append(xx)

    out.sort(key=lambda t: t.get("er", 0.0), reverse=True)
    return out[:top_n]


def _group_videos_by_age(videos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    g = {"7d": [], "30d": [], "90d": []}
    for v in videos:
        days = _days_old(v.get("published_at"))
        if days <= 7:
            g["7d"].append(v)
        if days <= 30:
            g["30d"].append(v)
        if days <= 90:
            g["90d"].append(v)
    return g


def _group_shorts_by_age(shorts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    g = {"48h": [], "7d": [], "30d": []}
    for v in shorts:
        days = _days_old(v.get("published_at"))
        hours = _hours_old(v.get("published_at"))
        if hours <= 48:
            g["48h"].append(v)
        if days <= 7:
            g["7d"].append(v)
        if days <= 30:
            g["30d"].append(v)
    return g


def rank_channel_like_legacy(videos: List[Dict[str, Any]], subs: int) -> Dict[str, Any]:
    """
    1:1 по старому продукту:
    - long: окна 7/30/90 дней
    - shorts: окна 48h/7d/30d
    - top20 по ER% = (likes+comments)/subs*100
    - отсечка: views > 2000
    """
    shorts = [v for v in videos if v.get("is_short") is True]
    longs = [v for v in videos if v.get("is_short") is False]

    long_groups = _group_videos_by_age(longs)
    short_groups = _group_shorts_by_age(shorts)

    return {
        "subs": int(subs or 0),
        "videos": {
            "7d": _top20(long_groups["7d"], subs=subs),
            "30d": _top20(long_groups["30d"], subs=subs),
            "90d": _top20(long_groups["90d"], subs=subs),
        },
        "shorts": {
            "48h": _top20(short_groups["48h"], subs=subs),
            "7d": _top20(short_groups["7d"], subs=subs),
            "30d": _top20(short_groups["30d"], subs=subs),
        },
    }