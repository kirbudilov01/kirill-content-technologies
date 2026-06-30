import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from celery_config import celery_app
from .crud import get_competitor_analysis_by_id, get_competitor_analysis_videos_with_latest_snapshots
from .strategy_prompts import build_strategy_prompts

logger = logging.getLogger(__name__)


def _classify_content_type(title: str) -> tuple[str, int]:
    value = (title or "").lower()

    def has_any(words: List[str]) -> bool:
        return any(word in value for word in words)

    if has_any(["новост", "news", "update", "обновлен", "breaking", "today", "сегодня"]):
        return "news", 78
    if has_any(["гайд", "guide", "how to", "туториал", "tutorial", "пошаг", "step by step"]):
        return "guide", 80
    if has_any(["для нович", "beginner", "с нуля", "for beginners", "основы", "basic"]):
        return "beginner", 76
    if has_any(["разбор", "breakdown", "обзор", "review", "анализ", "analysis"]):
        return "breakdown", 74
    if has_any(["кейс", "case", "опыт", "results", "результат", "история"]):
        return "case", 72
    return "other", 55


def _build_strategy_meta(analysis: Any, videos_data: Dict[str, Any]) -> Dict[str, Any]:
    videos = videos_data.get("videos", []) or []
    shorts = videos_data.get("shorts", []) or []

    unified = []
    for item in videos + shorts:
        metrics = item.get("metrics") or []
        latest = metrics[0] if metrics else None
        if not latest or latest.get("er") is None:
            continue

        ctype, conf = _classify_content_type(item.get("title") or "")
        unified.append({
            "video_id": item.get("video_id"),
            "content_type": ctype,
            "content_type_confidence": conf,
        })

    total = len(unified)
    by_type = {"news": 0, "guide": 0, "beginner": 0, "breakdown": 0, "case": 0, "other": 0}
    conf_sum = 0

    for item in unified:
        by_type[item["content_type"]] += 1
        conf_sum += item["content_type_confidence"]

    avg_conf = int(round(conf_sum / total)) if total else 0
    other_ratio = (by_type.get("other", 0) / total) if total else 1.0

    represented = [k for k, v in by_type.items() if v > 0]
    target_share = 1.0 / len(represented) if represented else 0
    demand_gaps = []

    for ctype, count in by_type.items():
        share = (count / total) if total else 0
        gap = target_share - share
        if gap > 0.03:
            demand_gaps.append({"type": ctype, "gap_pct": int(round(gap * 100))})

    demand_gaps = sorted(demand_gaps, key=lambda x: x["gap_pct"], reverse=True)[:3]

    strategy_status = "ready" if total >= 8 else "pending"
    demand_status = "ready" if len(demand_gaps) > 0 else "pending"
    classifier_status = "ready" if avg_conf >= 70 and other_ratio < 0.5 else "pending"

    freshness_status = "stale"
    updated = getattr(analysis, "updated_at", None)
    if updated:
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        freshness_status = "ready" if (datetime.now(timezone.utc) - updated) <= timedelta(hours=72) else "stale"

    readiness = int(round(
        (35 if strategy_status == "ready" else 15)
        + (25 if demand_status == "ready" else 10)
        + (20 if classifier_status == "ready" else 8)
        + (20 if freshness_status == "ready" else 5)
    ))

    return {
        "strategy_status": strategy_status,
        "demand_status": demand_status,
        "classifier_status": classifier_status,
        "freshness_status": freshness_status,
        "readiness": readiness,
        "classifier_confidence": avg_conf,
        "demand_gaps": demand_gaps,
        "last_computed_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="generate.strategy_workers.recompute_strategy_artifacts", bind=True, queue="strategy_recommender")
def recompute_strategy_artifacts(self, analysis_id: str, owner_id: int, mode: str = "trend"):
    """Compute strategy meta/prompts in worker context.

    This task is intentionally stateless now (returns payload). Persisting to DB can be added later.
    """
    import asyncio

    async def _run():
        analysis = await get_competitor_analysis_by_id(analysis_id, owner_id)
        if not analysis:
            return {"status": "not_found", "analysis_id": analysis_id}

        videos_data = await get_competitor_analysis_videos_with_latest_snapshots(analysis_id, owner_id, analytics_mode=True)
        strategy_meta = _build_strategy_meta(analysis, videos_data if isinstance(videos_data, dict) else {})
        prompts = build_strategy_prompts({
            "project_name": getattr(analysis, "name", "Untitled Project"),
            "mode": mode,
            "lang": getattr(analysis, "lang", "ru") or "ru",
            "readiness": strategy_meta.get("readiness", 0),
            "classifier_confidence": strategy_meta.get("classifier_confidence", 0),
            "demand_gaps": [g.get("type") for g in strategy_meta.get("demand_gaps", [])],
        })

        return {
            "status": "ready",
            "analysis_id": analysis_id,
            "mode": mode,
            "strategy_meta": strategy_meta,
            "strategy_prompts": prompts,
        }

    return asyncio.run(_run())


@celery_app.task(name="generate.strategy_workers.recompute_demand_gap", bind=True, queue="demand_gap")
def recompute_demand_gap(self, analysis_id: str, owner_id: int):
    """Compute demand-gap payload in worker context.

    Stateless v1 task that returns demand gaps and confidence; can be persisted later.
    """
    import asyncio

    async def _run():
        analysis = await get_competitor_analysis_by_id(analysis_id, owner_id)
        if not analysis:
            return {"status": "not_found", "analysis_id": analysis_id}

        videos_data = await get_competitor_analysis_videos_with_latest_snapshots(analysis_id, owner_id, analytics_mode=True)
        strategy_meta = _build_strategy_meta(analysis, videos_data if isinstance(videos_data, dict) else {})

        return {
            "status": "ready",
            "analysis_id": analysis_id,
            "demand_status": strategy_meta.get("demand_status", "pending"),
            "demand_gaps": strategy_meta.get("demand_gaps", []),
            "classifier_confidence": strategy_meta.get("classifier_confidence", 0),
            "last_computed_at": strategy_meta.get("last_computed_at"),
        }

    return asyncio.run(_run())
