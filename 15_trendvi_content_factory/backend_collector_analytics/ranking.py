# collector/analytics/ranking.py
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_dt(value: Any) -> Optional[datetime]:
    """
    Accepts:
      - ISO string "2025-12-31T16:15:03Z"
      - datetime
      - None
    Returns timezone-aware UTC datetime or None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            # support 'Z'
            s = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _age_days(published_at: Optional[datetime]) -> Optional[int]:
    if not published_at:
        return None
    try:
        now_utc = datetime.now(timezone.utc)
        return max(0, (now_utc - published_at).days)
    except Exception:
        return None


def product_score_views_per_sub_time_adjusted(
    *,
    views: int,
    subs: int,
    published_at: Optional[datetime],
) -> float:
    """
    1-в-1 как в старом backend/generate/competitor_analysis.py:

      er_base = views / subs
      if age_days <= 7:  er = er_base / log(max(1, age_days) + 1)
      elif age_days <= 30: er = er_base / log(age_days + 1)
      else: er = er_base / sqrt(age_days + 1)

    Возвращаем float (не округляем тут — округлим в финальном payload).
    """
    if subs <= 0:
        subs = 1
    er_base = (views / subs) if views > 0 else 0.0

    ad = _age_days(published_at)
    if ad is None:
        return er_base

    try:
        if ad <= 7:
            return er_base / (math.log(max(1, ad) + 1))
        if ad <= 30:
            return er_base / (math.log(ad + 1))
        return er_base / (math.sqrt(ad + 1))
    except Exception:
        return er_base


def rank_videos_by_product_logic(
    videos: List[Dict[str, Any]],
    *,
    subscribers: int,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Ранжирование 1-в-1 по продуктовой логике (time-adjusted views/subs).
    Возвращает список dict как и раньше, но гарантирует поле `er`.
    """
    subs = int(subscribers or 0)
    if subs <= 0:
        subs = 1

    scored: List[Dict[str, Any]] = []
    for v in videos:
        views = int(v.get("views") or 0)
        if views <= 0:
            continue

        published_at = _parse_dt(v.get("published_at"))
        score = product_score_views_per_sub_time_adjusted(
            views=views,
            subs=subs,
            published_at=published_at,
        )

        vv = dict(v)
        vv["er"] = round(float(score), 4)  # оставляем имя `er` для совместимости
        scored.append(vv)

    scored.sort(key=lambda x: float(x.get("er") or 0.0), reverse=True)
    return scored[: int(top_n)]


# --- Backward compatibility (чтобы imports не ломались) ---
def rank_videos_by_er(
    videos: List[Dict[str, Any]],
    *,
    subscribers: int,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    return rank_videos_by_product_logic(videos, subscribers=subscribers, top_n=top_n)