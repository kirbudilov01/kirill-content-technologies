import math
from datetime import datetime, timezone
from typing import Dict, Any


def calculate_er(video: Dict[str, Any], subscribers: int) -> float:
    """
    ER = views / subscribers с временной нормализацией.
    Формула полностью повторяет старую логику.
    """
    views = int(video.get("views", 0))
    if subscribers <= 0 or views <= 0:
        return 0.0

    er_base = views / subscribers

    published_at_raw = video.get("published_at")
    if not published_at_raw:
        return round(er_base, 4)

    try:
        published_at = datetime.fromisoformat(
            published_at_raw.replace("Z", "+00:00")
        )
    except Exception:
        return round(er_base, 4)

    age_days = max((datetime.now(timezone.utc) - published_at).days, 1)

    # 🔴 ВАЖНО: формулы 1 в 1 как у тебя
    if age_days <= 7:
        er = er_base / math.log(age_days + 1)
    elif age_days <= 30:
        er = er_base / math.log(age_days + 1)
    else:
        er = er_base / math.sqrt(age_days + 1)

    return round(er, 4)
