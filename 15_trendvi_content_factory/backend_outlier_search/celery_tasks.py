import asyncio
import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="outlier_search.search_videos", bind=True)
def search_outlier_videos_task(
    self,
    user_id: str,
    keyword: str,
    language: str = "ru",
    region_code: str = "US",
    lookback_hours: int = 72,
    max_results: int = 25,
    content_type: str = "all",
    candidate_pool: int = 600,
):
    logger.info(
        "[OUTLIER WORKER] Task %s started: user=%s keyword=%s",
        self.request.id,
        user_id,
        keyword,
    )
    try:
        from .yt_outlier_parser import YouTubeOutlierParser, collect_youtube_api_keys
        from .repository import enrich_with_24h_deltas, save_search_run, save_video_snapshots

        api_keys = collect_youtube_api_keys(
            os.getenv("YT_API_KEYS", ""),
            os.getenv("GOOGLE_API_KEYS", ""),
            os.getenv("YOUTUBE_API_KEYS", ""),
        )
        if not api_keys:
            return {
                "status": "error",
                "error": "YouTube API keys not configured",
                "videos": [],
                "total": 0,
            }

        logger.info("[OUTLIER WORKER] Parsed %s YouTube API key(s)", len(api_keys))
        if len(api_keys) <= 1:
            logger.warning("[OUTLIER WORKER] Only one API key available; rotation cannot mitigate quota limits")

        parser = YouTubeOutlierParser(api_keys=api_keys)

        videos = asyncio.run(
            parser.search_outliers(
                keyword=keyword,
                language=language,
                region_code=region_code,
                lookback_hours=lookback_hours,
                max_results=max_results,
                content_type=content_type,
                candidate_pool=candidate_pool,
            )
        )
        
        logger.info("[OUTLIER WORKER] Search returned %d videos for keyword: %s", len(videos), keyword)

        try:
            videos = asyncio.run(enrich_with_24h_deltas(videos))
            run_id = asyncio.run(
                save_search_run(
                    user_id=int(user_id),
                    keyword=keyword,
                    task_id=str(self.request.id),
                    total_results=len(videos),
                    params={
                        "language": language,
                        "region_code": region_code,
                        "lookback_hours": lookback_hours,
                        "max_results": max_results,
                        "content_type": content_type,
                        "candidate_pool": candidate_pool,
                    },
                    status="success",
                )
            )
            asyncio.run(
                save_video_snapshots(
                    user_id=int(user_id),
                    keyword=keyword,
                    videos=videos,
                    run_id=run_id,
                )
            )
        except Exception as persistence_error:
            logger.warning("[OUTLIER WORKER] Persistence layer skipped: %s", persistence_error)

        return {
            "status": "success",
            "videos": videos,
            "total": len(videos),
            "keyword": keyword,
            "user_id": user_id,
        }
    except Exception as e:
        logger.error("[OUTLIER WORKER] Task %s failed: %s", self.request.id, e, exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "videos": [],
            "total": 0,
        }


@shared_task(name="outlier_search.prune_snapshots")
def prune_outlier_snapshots_task():
    """
    Periodic maintenance task:
    1. Delete snapshots older than 90 days (stale runs).
    2. Delete snapshots with very low view counts that slipped through
       earlier (views < 3000 and captured more than 7 days ago).
    """
    try:
        from .repository import prune_low_quality_snapshots

        deleted = asyncio.run(prune_low_quality_snapshots())
        logger.info("[OUTLIER PRUNE] Deleted %d low-quality snapshot rows", deleted)
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        logger.error("[OUTLIER PRUNE] Failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}
