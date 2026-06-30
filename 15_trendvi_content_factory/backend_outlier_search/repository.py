import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from db import get_conn

logger = logging.getLogger(__name__)


async def save_search_run(
    user_id: int,
    keyword: str,
    task_id: str,
    total_results: int,
    params: Dict,
    status: str = "success",
) -> int:
    """Inserts a search run record and returns the new run_id."""
    conn = await get_conn()
    try:
        run_id = await conn.fetchval(
            """
            INSERT INTO outlier_search_runs (
                owner_id,
                keyword,
                task_id,
                status,
                total_results,
                language,
                region_code,
                lookback_hours,
                max_results,
                content_type,
                candidate_pool,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW())
            RETURNING run_id
            """,
            user_id,
            keyword,
            task_id,
            status,
            total_results,
            params.get("language"),
            params.get("region_code"),
            int(params.get("lookback_hours") or 72),
            int(params.get("max_results") or 25),
            params.get("content_type") or "all",
            int(params.get("candidate_pool") or 600),
        )
        return run_id
    finally:
        await conn.close()


async def enrich_with_24h_deltas(videos: List[Dict]) -> List[Dict]:
    if not videos:
        return videos

    conn = await get_conn()
    try:
        video_ids = [v.get("video_id") for v in videos if v.get("video_id")]
        if not video_ids:
            return videos

        now = datetime.now(timezone.utc)
        older_than = now - timedelta(hours=18)

        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (video_id)
                video_id,
                views,
                captured_at,
                outlier_score
            FROM outlier_video_snapshots
            WHERE video_id = ANY($1::text[])
              AND captured_at <= $2
            ORDER BY video_id, captured_at DESC
            """,
            video_ids,
            older_than,
        )
        prev_map = {row["video_id"]: row for row in rows}

        enriched = []
        for item in videos:
            prev = prev_map.get(item.get("video_id"))
            current_views = int(item.get("views") or 0)
            if prev:
                prev_views = int(prev["views"] or 0)
                delta_24h = current_views - prev_views
                base = max(prev_views, 1)
                momentum_score = max(-1.0, min(5.0, delta_24h / base))
            else:
                delta_24h = 0
                momentum_score = 0.0

            enriched_item = dict(item)
            enriched_item["views_delta_24h"] = int(delta_24h)
            enriched_item["momentum_score"] = round(momentum_score, 4)
            enriched.append(enriched_item)

        return enriched
    finally:
        await conn.close()


async def save_video_snapshots(user_id: int, keyword: str, videos: List[Dict], run_id: int = None):
    if not videos:
        return

    conn = await get_conn()
    try:
        for item in videos:
            await conn.execute(
                """
                INSERT INTO outlier_video_snapshots (
                    owner_id,
                    keyword,
                    run_id,
                    video_id,
                    channel_id,
                    channel_title,
                    video_title,
                    content_type,
                    topic_cluster,
                    views,
                    likes,
                    comments,
                    subscribers,
                    baseline_views,
                    outlier_score,
                    quality_score,
                    confidence_score,
                    engagement_rate,
                    relative_multiplier,
                    velocity_per_hour,
                    views_delta_24h,
                    momentum_score,
                    captured_at
                )
                VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                    $14,$15,$16,$17,$18,$19,$20,$21,$22,NOW()
                )
                """,
                user_id,
                keyword,
                run_id,
                item.get("video_id"),
                item.get("channel_id"),
                item.get("channel_title"),
                item.get("title"),
                item.get("content_type") or "long",
                item.get("topic_cluster") or "misc",
                int(item.get("views") or 0),
                int(item.get("likes") or 0),
                int(item.get("comments") or 0),
                int(item.get("subscribers") or 0),
                int(item.get("baseline_views") or 0),
                float(item.get("outlier_score") or 0.0),
                float(item.get("quality_score") or 0.0),
                float(item.get("confidence_score") or 0.0),
                float(item.get("engagement_rate") or 0.0),
                float(item.get("relative_multiplier") or 0.0),
                float(item.get("velocity_per_hour") or 0.0),
                int(item.get("views_delta_24h") or 0),
                float(item.get("momentum_score") or 0.0),
            )
    finally:
        await conn.close()


async def get_run_videos(user_id: int, run_id: int) -> List[Dict]:
    """Return the saved video snapshots for a specific search run."""
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                video_id,
                video_title        AS title,
                channel_id,
                channel_title,
                content_type,
                topic_cluster,
                views,
                likes,
                comments,
                subscribers,
                baseline_views,
                outlier_score,
                quality_score,
                confidence_score,
                engagement_rate,
                relative_multiplier,
                velocity_per_hour,
                views_delta_24h,
                momentum_score,
                captured_at        AS published_at
            FROM outlier_video_snapshots
            WHERE run_id = $1
              AND owner_id = $2
            ORDER BY outlier_score DESC
            """,
            run_id,
            user_id,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_user_topic_insights(user_id: int, days: int = 7) -> List[Dict]:
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT
                topic_cluster,
                COUNT(*)::int AS videos_count,
                ROUND(AVG(outlier_score)::numeric, 4) AS avg_outlier_score,
                ROUND(AVG(quality_score)::numeric, 4) AS avg_quality_score,
                ROUND(AVG(momentum_score)::numeric, 4) AS avg_momentum,
                MAX(captured_at) AS last_seen_at
            FROM outlier_video_snapshots
            WHERE owner_id = $1
              AND captured_at >= NOW() - ($2::int || ' days')::interval
              AND topic_cluster IS NOT NULL
              AND topic_cluster <> ''
            GROUP BY topic_cluster
            HAVING COUNT(*) >= 2
            ORDER BY avg_outlier_score DESC, avg_quality_score DESC, videos_count DESC
            LIMIT 20
            """,
            user_id,
            max(1, min(days, 30)),
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_user_search_history(user_id: int, limit: int = 20, language: Optional[str] = None) -> List[Dict]:
    conn = await get_conn()
    try:
        normalized_language = (language or "").strip().lower()
        normalized_language = normalized_language.split("-")[0].split("_")[0]

        if normalized_language:
            rows = await conn.fetch(
                """
                SELECT
                    run_id,
                    keyword,
                    status,
                    total_results,
                    language,
                    region_code,
                    created_at
                FROM outlier_search_runs
                WHERE owner_id = $1
                  AND split_part(split_part(lower(COALESCE(language, '')), '-', 1), '_', 1) = $3
                                    AND EXISTS (
                                        SELECT 1
                                        FROM outlier_video_snapshots ovs
                                        WHERE ovs.owner_id = outlier_search_runs.owner_id
                                            AND ovs.run_id = outlier_search_runs.run_id
                                    )
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                max(1, min(limit, 100)),
                normalized_language,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    run_id,
                    keyword,
                    status,
                    total_results,
                    language,
                    region_code,
                    created_at
                FROM outlier_search_runs
                WHERE owner_id = $1
                                    AND EXISTS (
                                        SELECT 1
                                        FROM outlier_video_snapshots ovs
                                        WHERE ovs.owner_id = outlier_search_runs.owner_id
                                            AND ovs.run_id = outlier_search_runs.run_id
                                    )
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                max(1, min(limit, 100)),
            )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_search_run_by_id(user_id: int, run_id: int) -> Optional[Dict]:
    """Return one search run owned by user or None if it does not exist."""
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT
                run_id,
                keyword,
                status,
                total_results,
                language,
                region_code,
                created_at
            FROM outlier_search_runs
            WHERE owner_id = $1
              AND run_id = $2
            """,
            user_id,
            run_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def prune_low_quality_snapshots() -> int:
    """
    Remove outlier_video_snapshots rows that pollute the table and slow queries:
      - Any row older than 90 days (runs are stale by then).
      - Rows with views < 3 000 captured more than 7 days ago
        (low-view videos that passed an old, permissive filter).
    Returns the total number of deleted rows.
    """
    conn = await get_conn()
    try:
        deleted_old = await conn.fetchval(
            """
            WITH deleted AS (
                DELETE FROM outlier_video_snapshots
                WHERE captured_at < NOW() - INTERVAL '90 days'
                RETURNING 1
            )
            SELECT COUNT(*) FROM deleted
            """
        )
        deleted_lowviews = await conn.fetchval(
            """
            WITH deleted AS (
                DELETE FROM outlier_video_snapshots
                WHERE views < 3000
                  AND captured_at < NOW() - INTERVAL '7 days'
                RETURNING 1
            )
            SELECT COUNT(*) FROM deleted
            """
        )
        return int(deleted_old or 0) + int(deleted_lowviews or 0)
    finally:
        await conn.close()
