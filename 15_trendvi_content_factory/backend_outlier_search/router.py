import logging
import os
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException

from auth.utils import get_current_user
from generate.crud import get_user_subscription

from .celery_tasks import search_outlier_videos_task
from .quota import OutlierQuotaTracker
from .schemas import (
    OutlierSearchHistoryItem,
    OutlierSearchHistoryResponse,
    OutlierInsightsResponse,
    OutlierSearchRequest,
    OutlierSearchResponse,
    OutlierSearchStats,
    OutlierTaskStatusResponse,
    OutlierTopicInsight,
    OutlierVideoResult,
)
from .repository import get_run_videos, get_search_run_by_id, get_user_search_history, get_user_topic_insights

logger = logging.getLogger(__name__)

outlier_search_router = APIRouter(prefix="/api/v1/outliers", tags=["outlier-search"])


def get_weekly_outlier_limit_for_user(rate: str, is_active: bool) -> int:
    normalized_rate = str(rate or "").strip().lower()
    if is_active and normalized_rate in {"author", "author_week", "author_year", "тестер", "tester"}:
        return 30
    if is_active and normalized_rate in {"agency", "agency_year", "creator", "enterprise", "агентство", "создатель"}:
        return 60
    return 3


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _is_quota_disabled() -> bool:
    # Disabled means "do not block", but quota counters are still tracked and returned.
    return _bool_env("OUTLIER_SEARCH_DISABLE_QUOTA", False)


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://:trendvi@redis:6379/0")


async def _get_quota_context(user_id: str, owner_id: int) -> tuple[int, OutlierQuotaTracker, dict]:
    rate = "free"
    is_active = False
    try:
        subscription = await get_user_subscription(owner_id)
        if isinstance(subscription, (tuple, list)) and len(subscription) >= 2:
            rate = subscription[0] or "free"
            is_active = bool(subscription[1])
    except Exception as subscription_error:
        logger.warning("[Outlier API] Subscription lookup failed for user=%s: %s", owner_id, subscription_error)

    weekly_limit = get_weekly_outlier_limit_for_user(rate, is_active)
    quota_tracker = OutlierQuotaTracker(get_redis_url(), max_searches_per_week=weekly_limit)
    quota_info = quota_tracker.get_quota_info(user_id)
    return weekly_limit, quota_tracker, quota_info


@outlier_search_router.post("/search/videos", response_model=OutlierTaskStatusResponse)
async def search_outliers(request: OutlierSearchRequest, current_user=Depends(get_current_user)):
    user_id = str(current_user.user_id)
    try:
        quota_limit, quota_tracker, _ = await _get_quota_context(user_id, current_user.user_id)

        # Soft-disable mode: keep counters real, but do not enforce 429.
        if (not _is_quota_disabled()) and (not quota_tracker.can_search(user_id)):
            remaining = quota_tracker.get_remaining_searches(user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Лимит outlier-поисков исчерпан. Доступно: {remaining}/{quota_limit} запросов в неделю.",
            )

        quota_tracker.increment_search_count(user_id)
        quota_info = quota_tracker.get_quota_info(user_id)

        task = search_outlier_videos_task.apply_async(
            args=[
                user_id,
                request.keyword,
                request.language,
                request.region_code,
                request.lookback_hours,
                request.max_results,
                request.content_type,
                request.candidate_pool,
            ],
            queue="outlier_search",
        )

        return OutlierTaskStatusResponse(
            task_id=task.id,
            status="pending",
            message="Поиск аутлаеров запущен. Опрашивайте /search/status/{task_id}.",
            searches_remaining=quota_info["searches_remaining"],
            searches_limit=quota_info["searches_limit"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Outlier API] Failed to start task: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось запустить поиск аутлаеров")


@outlier_search_router.get("/search/status/{task_id}", response_model=OutlierSearchResponse)
async def get_outlier_status(task_id: str, current_user=Depends(get_current_user)):
    user_id = str(current_user.user_id)
    try:
        try:
            task_result = AsyncResult(task_id)
            task_state = task_result.state
        except Exception as celery_err:
            logger.warning("[Outlier API] Celery backend unavailable for task=%s: %s", task_id, celery_err)
            raise HTTPException(status_code=202, detail="Задача в обработке. Статус временно недоступен.")
        if task_state == "PENDING":
            raise HTTPException(status_code=202, detail="Задача в обработке. Попробуйте позже.")
        if task_state == "FAILURE":
            raise HTTPException(status_code=500, detail=f"Поиск не удался: {str(task_result.info)}")
        if task_state != "SUCCESS":
            raise HTTPException(status_code=202, detail=f"Задача в состоянии: {task_state}")

        result = task_result.result
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=f"Ошибка поиска: {result.get('error', 'Unknown error')}")

        videos = [OutlierVideoResult(**video) for video in (result.get("videos") or [])]
        videos.sort(key=lambda item: item.outlier_score, reverse=True)

        _, _, quota_info = await _get_quota_context(user_id, current_user.user_id)

        return OutlierSearchResponse(
            videos=videos,
            total_count=len(videos),
            searches_remaining=quota_info["searches_remaining"],
            searches_limit=quota_info["searches_limit"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Outlier API] Failed to get task status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось получить статус поиска аутлаеров")


@outlier_search_router.get("/search/stats", response_model=OutlierSearchStats)
async def get_outlier_stats(current_user=Depends(get_current_user)):
    user_id = str(current_user.user_id)
    try:
        _, _, quota_info = await _get_quota_context(user_id, current_user.user_id)

        return OutlierSearchStats(
            searches_remaining=quota_info["searches_remaining"],
            searches_limit=quota_info["searches_limit"],
            reset_date=quota_info["reset_date"],
        )
    except Exception as e:
        logger.error("[Outlier API] Failed to get stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось получить статистику аутлаер-поиска")


@outlier_search_router.get("/search/insights", response_model=OutlierInsightsResponse)
async def get_outlier_insights(days: int = 7, current_user=Depends(get_current_user)):
    try:
        insights = await get_user_topic_insights(current_user.user_id, days=days)
        return OutlierInsightsResponse(insights=[OutlierTopicInsight(**item) for item in insights])
    except Exception as e:
        logger.warning("[Outlier API] Insights unavailable: %s", e)
        return OutlierInsightsResponse(insights=[])


@outlier_search_router.get("/search/history", response_model=OutlierSearchHistoryResponse)
async def get_outlier_history(limit: int = 20, language: Optional[str] = None, current_user=Depends(get_current_user)):
    try:
        rows = await get_user_search_history(current_user.user_id, limit=limit, language=language)
        return OutlierSearchHistoryResponse(history=[OutlierSearchHistoryItem(**row) for row in rows])
    except Exception as e:
        logger.warning("[Outlier API] History unavailable: %s", e)
        return OutlierSearchHistoryResponse(history=[])


@outlier_search_router.get("/search/history/{run_id}", response_model=OutlierSearchResponse)
async def get_outlier_history_run(run_id: int, current_user=Depends(get_current_user)):
    user_id = str(current_user.user_id)
    try:
        run = await get_search_run_by_id(current_user.user_id, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Запуск поиска не найден")

        saved_rows = await get_run_videos(current_user.user_id, run_id)
        if not saved_rows:
            raise HTTPException(
                status_code=404,
                detail="Сохраненные результаты для этого запуска недоступны",
            )

        videos = []
        for row in saved_rows:
            video_id = str(row.get("video_id") or "")
            published_at = row.get("published_at")
            if hasattr(published_at, "isoformat"):
                published_at = published_at.isoformat()

            videos.append(
                OutlierVideoResult(
                    video_id=video_id,
                    title=str(row.get("title") or ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    channel_id=str(row.get("channel_id") or ""),
                    channel_title=str(row.get("channel_title") or ""),
                    published_at=str(published_at or ""),
                    thumbnail=(f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None),
                    duration_seconds=0,
                    content_type=str(row.get("content_type") or "long"),
                    views=int(row.get("views") or 0),
                    likes=int(row.get("likes") or 0),
                    comments=int(row.get("comments") or 0),
                    subscribers=int(row.get("subscribers") or 0),
                    baseline_views=int(row.get("baseline_views") or 0),
                    outlier_score=float(row.get("outlier_score") or 0.0),
                    quality_score=float(row.get("quality_score") or 0.0),
                    confidence_score=float(row.get("confidence_score") or 0.0),
                    engagement_rate=float(row.get("engagement_rate") or 0.0),
                    topic_cluster=str(row.get("topic_cluster") or "misc"),
                    relative_multiplier=float(row.get("relative_multiplier") or 0.0),
                    velocity_per_hour=float(row.get("velocity_per_hour") or 0.0),
                    views_delta_24h=int(row.get("views_delta_24h") or 0),
                    momentum_score=float(row.get("momentum_score") or 0.0),
                    reason="Saved outlier search run",
                )
            )

        _, _, quota_info = await _get_quota_context(user_id, current_user.user_id)

        return OutlierSearchResponse(
            videos=videos,
            total_count=len(videos),
            searches_remaining=quota_info["searches_remaining"],
            searches_limit=quota_info["searches_limit"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Outlier API] Failed to get history run %s: %s", run_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось загрузить сохраненные результаты поиска")
