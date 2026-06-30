# collector/analytics/viral_shorts.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List


def viral_shorts_efficiency(views: List[float], subscribers: int, eps: float = 1e-9) -> float:
    """
    1-в-1 как в старом backend:
      views: [V1, V2, ..., VT] cumulative просмотры по дням/снапшотам
      subscribers: подписчики канала
    G = growth * reach
    growth = (VT/V1)^(1/(T-1)), reach = VT/S
    """
    if not views:
        return 0.0

    V1 = max(float(views[0]), eps)
    VT = max(float(views[-1]), eps)
    S = max(float(subscribers), eps)
    T = len(views)

    growth = (VT / V1) ** (1.0 / max(T - 1, 1))
    reach = VT / S
    return float(growth * reach)


@dataclass
class ViralCandidate:
    video_id: str
    score: float
    views_series: List[int]
    points: int  # сколько снапшотов в серии