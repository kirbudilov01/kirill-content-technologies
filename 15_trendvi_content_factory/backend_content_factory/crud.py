from __future__ import annotations

import asyncio
import json
import os
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from db import get_conn
from .platforms import SOCIAL_NETWORKS_SQL
from .schemas import ContentFactoryVideoPayload


_SCHEMA_READY = False
_SCHEMA_LOCK = asyncio.Lock()
logger = logging.getLogger(__name__)


def _env_flag_enabled(name: str, default: str = "1") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_csv_set(name: str, default: str) -> set[str]:
    raw = str(os.getenv(name, default) or default)
    values: set[str] = set()
    for item in raw.split(","):
        token = str(item or "").strip().lower()
        if token:
            values.add(token)
    return values


def _sql_text_list(values: set[str]) -> str:
    if not values:
        return "('')"
    escaped = ["'" + value.replace("'", "''") + "'" for value in sorted(values)]
    return "(" + ", ".join(escaped) + ")"


# ---------------------------------------------------------------------------
# Snapshot tracking (historical per-sync measurements)
# Set CONTENT_FACTORY_SNAPSHOTS_ENABLED_OWNER_IDS to a comma-separated list
# of integer owner_ids that should have metric history recorded, e.g. "42,57".
# Set to "*" to enable for all users.
# ---------------------------------------------------------------------------
_SNAPSHOTS_OWNER_IDS: Optional[set[int]] = None
_SNAPSHOTS_ALL: bool = False


def _load_snapshots_config() -> None:
    global _SNAPSHOTS_OWNER_IDS, _SNAPSHOTS_ALL
    raw = os.getenv("CONTENT_FACTORY_SNAPSHOTS_ENABLED_OWNER_IDS", "").strip()
    if raw == "*":
        _SNAPSHOTS_ALL = True
        _SNAPSHOTS_OWNER_IDS = None
        return
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    _SNAPSHOTS_OWNER_IDS = ids or None
    _SNAPSHOTS_ALL = False


_load_snapshots_config()


def _snapshots_enabled_for(owner_id: int) -> bool:
    if _SNAPSHOTS_ALL:
        return True
    return bool(_SNAPSHOTS_OWNER_IDS and owner_id in _SNAPSHOTS_OWNER_IDS)


def _valid_youtube_video_sql(alias: str = "v") -> str:
    return (
        f"NOT ({alias}.social_network = 'youtube' AND ("
        f"{alias}.video_external_id IS NULL "
        f"OR {alias}.video_external_id !~ '^[A-Za-z0-9_-]{{11}}$' "
        f"OR {alias}.published_at IS NULL))"
    )


def _is_short_sql(alias: str = "v") -> str:
    # Networks where all content is inherently short-form.
    _always_short_networks = _sql_text_list(
        _env_csv_set("CONTENT_FACTORY_ALWAYS_SHORT_NETWORKS", "tiktok,likee,instagram")
    )
    # Networks where shorts should never be inferred.
    _no_short_networks = _sql_text_list(
        _env_csv_set("CONTENT_FACTORY_NO_SHORT_NETWORKS", "vk,ok")
    )
    # Networks where duration-only inference is unreliable or unsupported.
    _no_duration_short_networks = _sql_text_list(
        _env_csv_set("CONTENT_FACTORY_NO_DURATION_SHORT_NETWORKS", "instagram,rutube,dzen,vk,ok,x")
    )
    return (
        "(CASE WHEN "
        f"  {alias}.social_network IN {_no_short_networks} THEN FALSE "
        "ELSE ("
        # 1. Always-short platforms (TikTok, Likee)
        f"  {alias}.social_network IN {_always_short_networks} "
        # 2. Explicit flag stored in extra JSON
        f"  OR ({alias}.social_network NOT IN {_no_short_networks} AND COALESCE(({alias}.extra->>'is_short')::boolean, FALSE)) "
        # 3. YouTube Shorts URL
        f"  OR ({alias}.social_network NOT IN {_no_short_networks} AND {alias}.video_url ILIKE '%/shorts/%') "
        # 4. Instagram Reel URL
        f"  OR ({alias}.video_url ILIKE '%/reel/%' AND {alias}.social_network = 'instagram') "
        # 4.1 Explicit parser signal for short-form content
        f"  OR ({alias}.social_network NOT IN {_no_short_networks} AND COALESCE(({alias}.extra->>'short_format') IN ('short', 'reel', 'clip'), FALSE)) "
        # 4.2 Explicit Dzen short URL
        f"  OR ({alias}.social_network = 'dzen' AND {alias}.video_url ILIKE '%/short-video/%') "
        # 5. TikTok / Likee URL patterns
        f"  OR ({alias}.social_network NOT IN {_no_duration_short_networks} AND {alias}.video_url ILIKE '%tiktok.com/%') "
        f"  OR ({alias}.social_network NOT IN {_no_duration_short_networks} AND {alias}.video_url ILIKE '%likee.video/%') "
        # 6. Duration-based short detection — only for platforms where it is meaningful
        f"  OR ({alias}.social_network NOT IN {_no_duration_short_networks} "
        f"       AND {alias}.duration_seconds IS NOT NULL AND {alias}.duration_seconds > 0 AND {alias}.duration_seconds <= 180) "
        # 7. Hashtag in title (universal)
        f"  OR ({alias}.social_network NOT IN {_no_short_networks} AND {alias}.title ILIKE '%#shorts%') "
        f"  OR ({alias}.social_network NOT IN {_no_short_networks} AND {alias}.title ILIKE '%#short%') "
        ") END)"
    )


async def _ensure_schema_ready() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    async with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return

        conn = await get_conn()
        try:
            # Cross-process lock: worker and backend can initialize schema concurrently.
            # Use a stable advisory key to serialize DDL and avoid duplicate constraint races.
            await conn.execute("SELECT pg_advisory_lock(792401230)")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_factory_projects (
                    project_id BIGSERIAL PRIMARY KEY,
                    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    social_network TEXT NOT NULL DEFAULT 'youtube' CHECK (social_network IN (""" + SOCIAL_NETWORKS_SQL + """)),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_collection_at TIMESTAMPTZ
                )
                """
            )

            # Backward-compatible schema sync for installations where the table
            # existed before newer columns were introduced.
            await conn.execute("ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS description TEXT")
            await conn.execute(
                "ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS social_network TEXT NOT NULL DEFAULT 'youtube'"
            )
            await conn.execute("ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
            await conn.execute("ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
            await conn.execute("ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
            await conn.execute("ALTER TABLE content_factory_projects ADD COLUMN IF NOT EXISTS last_collection_at TIMESTAMPTZ")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_factory_channels (
                    channel_id BIGSERIAL PRIMARY KEY,
                    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    social_network TEXT NOT NULL CHECK (social_network IN (""" + SOCIAL_NETWORKS_SQL + """)),
                    channel_url TEXT NOT NULL,
                    channel_external_id TEXT,
                    channel_title TEXT,
                    category TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_sync_at TIMESTAMPTZ,
                    last_sync_status TEXT,
                    last_sync_error TEXT,
                    last_sync_video_count INTEGER,
                    last_sync_coverage_published_at INTEGER,
                    last_sync_coverage_views INTEGER,
                    last_sync_coverage_likes INTEGER,
                    last_sync_coverage_comments INTEGER,
                    last_sync_retry_count INTEGER,
                    UNIQUE (owner_id, social_network, channel_url)
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_factory_video_stats (
                    video_id BIGSERIAL PRIMARY KEY,
                    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    channel_id BIGINT NOT NULL REFERENCES content_factory_channels(channel_id) ON DELETE CASCADE,
                    social_network TEXT NOT NULL CHECK (social_network IN (""" + SOCIAL_NETWORKS_SQL + """)),
                    video_external_id TEXT,
                    video_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    published_at TIMESTAMPTZ,
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    views BIGINT NOT NULL DEFAULT 0,
                    likes BIGINT NOT NULL DEFAULT 0,
                    comments BIGINT NOT NULL DEFAULT 0,
                    shares BIGINT NOT NULL DEFAULT 0,
                    saves BIGINT NOT NULL DEFAULT 0,
                    duration_seconds INTEGER,
                    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
                    moderation_status TEXT NOT NULL DEFAULT 'pending',
                    moderation_updated_at TIMESTAMPTZ,
                    UNIQUE (owner_id, social_network, video_url)
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_factory_report_history (
                    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    period_days INTEGER NOT NULL,
                    social_network TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS project_id BIGINT REFERENCES content_factory_projects(project_id) ON DELETE SET NULL")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS preferred_period_preset TEXT")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS preferred_period_days INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS preferred_start_date DATE")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS preferred_end_date DATE")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS subscribers_count INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_video_count INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_coverage_published_at INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_coverage_views INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_coverage_likes INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_coverage_comments INTEGER")
            await conn.execute("ALTER TABLE content_factory_channels ADD COLUMN IF NOT EXISTS last_sync_retry_count INTEGER")
            await conn.execute("ALTER TABLE content_factory_video_stats ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'pending'")
            await conn.execute("ALTER TABLE content_factory_video_stats ADD COLUMN IF NOT EXISTS moderation_updated_at TIMESTAMPTZ")

            await conn.execute("ALTER TABLE content_factory_projects DROP CONSTRAINT IF EXISTS content_factory_projects_social_network_check")
            await conn.execute("ALTER TABLE content_factory_projects DROP CONSTRAINT IF EXISTS content_factory_projects_social_network_allowed")
            await conn.execute(
                "ALTER TABLE content_factory_projects ADD CONSTRAINT content_factory_projects_social_network_allowed "
                f"CHECK (social_network IN ({SOCIAL_NETWORKS_SQL}))"
            )

            await conn.execute("ALTER TABLE content_factory_channels DROP CONSTRAINT IF EXISTS content_factory_channels_social_network_check")
            await conn.execute("ALTER TABLE content_factory_channels DROP CONSTRAINT IF EXISTS content_factory_channels_social_network_allowed")
            await conn.execute(
                "ALTER TABLE content_factory_channels ADD CONSTRAINT content_factory_channels_social_network_allowed "
                f"CHECK (social_network IN ({SOCIAL_NETWORKS_SQL}))"
            )

            await conn.execute("ALTER TABLE content_factory_video_stats DROP CONSTRAINT IF EXISTS content_factory_video_stats_social_network_check")
            await conn.execute("ALTER TABLE content_factory_video_stats DROP CONSTRAINT IF EXISTS content_factory_video_stats_social_network_allowed")
            await conn.execute(
                "ALTER TABLE content_factory_video_stats ADD CONSTRAINT content_factory_video_stats_social_network_allowed "
                f"CHECK (social_network IN ({SOCIAL_NETWORKS_SQL}))"
            )

            await conn.execute("ALTER TABLE content_factory_report_history DROP CONSTRAINT IF EXISTS content_factory_report_history_social_network_check")
            await conn.execute("ALTER TABLE content_factory_report_history DROP CONSTRAINT IF EXISTS content_factory_report_history_social_network_allowed")
            await conn.execute(
                "ALTER TABLE content_factory_report_history ADD CONSTRAINT content_factory_report_history_social_network_allowed "
                f"CHECK (social_network IN ({SOCIAL_NETWORKS_SQL}))"
            )

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_content_factory_projects_owner ON content_factory_projects (owner_id, created_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_content_factory_channels_project ON content_factory_channels (owner_id, project_id, created_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_content_factory_channels_owner ON content_factory_channels (owner_id, social_network, created_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_content_factory_video_stats_owner_time ON content_factory_video_stats (owner_id, captured_at DESC, social_network)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_content_factory_reports_owner_created ON content_factory_report_history (owner_id, created_at DESC)")

            # Historical metric snapshots — append-only, one row per sync per video.
            # Enabled selectively via CONTENT_FACTORY_SNAPSHOTS_ENABLED_OWNER_IDS env var.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_factory_video_snapshots (
                    snapshot_id BIGSERIAL PRIMARY KEY,
                    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    video_id BIGINT NOT NULL REFERENCES content_factory_video_stats(video_id) ON DELETE CASCADE,
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    views BIGINT NOT NULL DEFAULT 0,
                    likes BIGINT NOT NULL DEFAULT 0,
                    comments BIGINT NOT NULL DEFAULT 0,
                    shares BIGINT NOT NULL DEFAULT 0,
                    saves BIGINT NOT NULL DEFAULT 0
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_video_snapshots_video_time ON content_factory_video_snapshots (video_id, captured_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_video_snapshots_owner_time ON content_factory_video_snapshots (owner_id, captured_at DESC)")

            _SCHEMA_READY = True
        finally:
            try:
                await conn.execute("SELECT pg_advisory_unlock(792401230)")
            except Exception:
                pass
            await conn.close()


def _resolve_period_window(period_days: int, month: Optional[str]) -> tuple[datetime, datetime]:
    if month:
        try:
            month_start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError("month must be in YYYY-MM format") from exc

        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return month_start, month_end

    now_utc = datetime.now(timezone.utc)
    return now_utc - timedelta(days=period_days), now_utc


def _resolve_custom_window(
    period_days: int,
    month: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
) -> tuple[datetime, datetime]:
    if start_date or end_date:
        end_val = end_date or datetime.now(timezone.utc).date()
        start_val = start_date or (end_val - timedelta(days=max(period_days, 1) - 1))
        if start_val > end_val:
            raise ValueError("start_date must be less than or equal to end_date")

        start_dt = datetime.combine(start_val, time.min).replace(tzinfo=timezone.utc)
        # right-open interval [start, end+1day)
        end_dt = datetime.combine(end_val + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
        return start_dt, end_dt

    return _resolve_period_window(period_days=period_days, month=month)


def _is_short(
    duration_seconds: Optional[int],
    *,
    video_url: Optional[str] = None,
    title: Optional[str] = None,
    extra: Optional[dict] = None,
) -> bool:
    # Networks where all content is inherently short-form.
    _ALWAYS_SHORT = _env_csv_set("CONTENT_FACTORY_ALWAYS_SHORT_NETWORKS", "tiktok,likee,instagram")
    # Networks where shorts should never be inferred.
    _NO_SHORT = _env_csv_set("CONTENT_FACTORY_NO_SHORT_NETWORKS", "vk,ok")
    # Networks where duration-only inference is unreliable or unsupported.
    _NO_DURATION_SHORT = _env_csv_set("CONTENT_FACTORY_NO_DURATION_SHORT_NETWORKS", "instagram,rutube,dzen,vk,ok,x")

    network = ""
    if isinstance(extra, dict):
        network = str(extra.get("network") or "").lower()

    if network in _NO_SHORT:
        return False

    if network in _ALWAYS_SHORT:
        return True

    if isinstance(extra, dict):
        short_format = str(extra.get("short_format") or "").strip().lower()
        if short_format in {"short", "reel", "clip"}:
            return True

    if isinstance(extra, dict) and bool(extra.get("is_short")):
        return True

    url = (video_url or "").lower()
    if "/shorts/" in url:
        return True
    if "/reel/" in url:
        return True
    if network == "dzen" and "/short-video/" in url:
        return True
    if any(token in url for token in ("tiktok.com/", "likee.video/", "/clip/")):
        return True

    title_l = (title or "").lower()
    if "#shorts" in title_l or "#short" in title_l:
        return True

    # Duration-based short detection only for platforms that support the format
    # (YouTube and any unrecognised networks). Skip for Rutube, Dzen, VK, OK, X.
    if network not in _NO_DURATION_SHORT:
        if duration_seconds and duration_seconds > 0 and duration_seconds <= 180:
            return True

    return False


def _engagement_rate(views: int, likes: int, comments: int) -> float:
    base = max(int(views or 0), 1)
    return float((int(likes or 0) + int(comments or 0)) / base)


def _build_discussion_explanation(engagement_rate: float, likes: int, comments: int) -> str:
    if comments >= max(int(likes * 0.35), 50):
        return "Высокая доля комментариев к лайкам: видео вызвало активную дискуссию в аудитории."
    if engagement_rate >= 0.08:
        return "Высокий ER: аудитория не только смотрит, но и активно взаимодействует через лайки и комментарии."
    if engagement_rate >= 0.04:
        return "ER выше среднего: тема видео получила заметный отклик в комментариях и реакциях."
    return "Видео обсуждают стабильнее других роликов канала: комментарии и лайки выше фоновых значений периода."


def _normalize_video_provenance(extra: Optional[dict]) -> dict[str, object]:
    payload = dict(extra or {}) if isinstance(extra, dict) else {}
    recovered_fields = payload.get("recovered_fields")
    if not isinstance(recovered_fields, list):
        recovered_fields = []
    normalized_fields = [str(item) for item in recovered_fields if str(item).strip()]
    return {
        "source": str(payload.get("source") or "").strip() or None,
        "recovery_applied": bool(payload.get("recovery_applied")),
        "recovery_source": str(payload.get("recovery_source") or "").strip() or None,
        "recovered_fields": normalized_fields,
    }


async def create_channel(
    owner_id: int,
    project_id: Optional[int],
    social_network: str,
    channel_url: str,
    channel_title: Optional[str],
    category: Optional[str],
) -> dict:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
                        INSERT INTO content_factory_channels (owner_id, project_id, social_network, channel_url, channel_title, category)
                        VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (owner_id, social_network, channel_url)
            DO UPDATE SET
              project_id = COALESCE(EXCLUDED.project_id, content_factory_channels.project_id),
                            channel_title = COALESCE(EXCLUDED.channel_title, content_factory_channels.channel_title),
              category = EXCLUDED.category,
              updated_at = NOW()
            RETURNING *
            """,
            owner_id,
            project_id,
            social_network,
            channel_url,
                        channel_title,
            category,
        )
        return dict(row)
    finally:
        await conn.close()


async def create_project(owner_id: int, name: str, description: Optional[str], social_network: str) -> dict:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO content_factory_projects (owner_id, name, description, social_network)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            owner_id,
            name,
            description,
            social_network,
        )
        return dict(row)
    finally:
        await conn.close()


async def list_projects(owner_id: int) -> list[dict]:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT p.*, COALESCE(c.channel_count, 0) AS channels_count
            FROM content_factory_projects p
            LEFT JOIN (
                SELECT project_id, COUNT(*) AS channel_count
                FROM content_factory_channels
                WHERE owner_id = $1 AND project_id IS NOT NULL
                GROUP BY project_id
            ) c ON c.project_id = p.project_id
            WHERE p.owner_id = $1 AND p.is_active = TRUE
            ORDER BY p.created_at DESC
            """,
            owner_id,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_project_for_owner(project_id: int, owner_id: int) -> Optional[dict]:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM content_factory_projects
            WHERE project_id = $1 AND owner_id = $2 AND is_active = TRUE
            """,
            project_id,
            owner_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def mark_project_collection(owner_id: int, project_id: int) -> None:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        await conn.execute(
            """
            UPDATE content_factory_projects
            SET last_collection_at = NOW(),
                updated_at = NOW()
            WHERE owner_id = $1 AND project_id = $2
            """,
            owner_id,
            project_id,
        )
    finally:
        await conn.close()


async def delete_project_for_owner(project_id: int, owner_id: int) -> bool:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        async with conn.transaction():
            channel_rows = await conn.fetch(
                """
                SELECT channel_id
                FROM content_factory_channels
                WHERE owner_id = $1 AND project_id = $2
                """,
                owner_id,
                project_id,
            )
            channel_ids = [int(row["channel_id"]) for row in channel_rows]

            if channel_ids:
                await conn.execute(
                    """
                    DELETE FROM content_factory_video_stats
                    WHERE owner_id = $1 AND channel_id = ANY($2::bigint[])
                    """,
                    owner_id,
                    channel_ids,
                )

            await conn.execute(
                """
                DELETE FROM content_factory_channels
                WHERE owner_id = $1 AND project_id = $2
                """,
                owner_id,
                project_id,
            )

            result = await conn.execute(
                """
                DELETE FROM content_factory_projects
                WHERE owner_id = $1 AND project_id = $2
                """,
                owner_id,
                project_id,
            )

        return result != "DELETE 0"
    finally:
        await conn.close()


async def list_channels(owner_id: int, social_network: Optional[str] = None, project_id: Optional[int] = None) -> list[dict]:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        conditions = ["c.owner_id = $1"]
        params: list[object] = [owner_id]

        if social_network:
            conditions.append(f"c.social_network = ${len(params) + 1}")
            params.append(social_network)

        if project_id is not None:
            conditions.append(f"c.project_id = ${len(params) + 1}")
            params.append(project_id)

        where_sql = " AND ".join(conditions)
        rows = await conn.fetch(
            f"""
            SELECT
                c.*,
                p.name AS project_name
            FROM content_factory_channels c
            LEFT JOIN content_factory_projects p ON p.project_id = c.project_id
            WHERE {where_sql}
            ORDER BY c.social_network, c.created_at DESC
            """,
            *params,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_channel_for_owner(channel_id: int, owner_id: int) -> Optional[dict]:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM content_factory_channels WHERE channel_id = $1 AND owner_id = $2",
            channel_id,
            owner_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def delete_channel_for_owner(channel_id: int, owner_id: int) -> bool:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        result = await conn.execute(
            "DELETE FROM content_factory_channels WHERE channel_id = $1 AND owner_id = $2",
            channel_id,
            owner_id,
        )
        return result != "DELETE 0"
    finally:
        await conn.close()


async def list_channels_for_sync(owner_id: int, project_id: Optional[int] = None) -> list[dict]:
    await _ensure_schema_ready()
    conn = await get_conn()
    try:
        if project_id is None:
            rows = await conn.fetch(
                """
                SELECT *
                FROM content_factory_channels
                WHERE owner_id = $1
                ORDER BY created_at DESC
                """,
                owner_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *
                FROM content_factory_channels
                WHERE owner_id = $1 AND project_id = $2
                ORDER BY created_at DESC
                """,
                owner_id,
                project_id,
            )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def mark_channel_sync_started(channel_id: int) -> None:
    conn = await get_conn()
    try:
        await conn.execute(
            """
            UPDATE content_factory_channels
            SET last_sync_status = 'processing',
                last_sync_error = NULL,
                updated_at = NOW()
            WHERE channel_id = $1
            """,
            channel_id,
        )
    finally:
        await conn.close()


async def mark_channel_sync_queued(channel_id: int) -> None:
    conn = await get_conn()
    try:
        await conn.execute(
            """
            UPDATE content_factory_channels
            SET last_sync_status = 'queued',
                last_sync_error = NULL,
                updated_at = NOW()
            WHERE channel_id = $1
            """,
            channel_id,
        )
    finally:
        await conn.close()


async def mark_channel_sync_result(
    channel_id: int,
    *,
    status: str,
    error_text: Optional[str] = None,
    social_network: Optional[str] = None,
    channel_external_id: Optional[str] = None,
    channel_title: Optional[str] = None,
    subscribers_count: Optional[int] = None,
    sync_video_count: Optional[int] = None,
    coverage_published_at: Optional[int] = None,
    coverage_views: Optional[int] = None,
    coverage_likes: Optional[int] = None,
    coverage_comments: Optional[int] = None,
    retry_count: Optional[int] = None,
) -> None:
    conn = await get_conn()
    try:
        await conn.execute(
            """
            UPDATE content_factory_channels
            SET last_sync_status = $2,
                last_sync_error = $3,
                last_sync_at = NOW(),
                updated_at = NOW(),
                social_network = COALESCE($4, social_network),
                channel_external_id = COALESCE($5, channel_external_id),
                channel_title = COALESCE($6, channel_title),
                subscribers_count = COALESCE($7, subscribers_count),
                last_sync_video_count = COALESCE($8, last_sync_video_count),
                last_sync_coverage_published_at = COALESCE($9, last_sync_coverage_published_at),
                last_sync_coverage_views = COALESCE($10, last_sync_coverage_views),
                last_sync_coverage_likes = COALESCE($11, last_sync_coverage_likes),
                last_sync_coverage_comments = COALESCE($12, last_sync_coverage_comments),
                last_sync_retry_count = COALESCE($13, last_sync_retry_count)
            WHERE channel_id = $1
            """,
            channel_id,
            status,
            error_text,
            social_network,
            channel_external_id,
            channel_title,
            subscribers_count,
            sync_video_count,
            coverage_published_at,
            coverage_views,
            coverage_likes,
            coverage_comments,
            retry_count,
        )
    finally:
        await conn.close()


async def update_channel_period_preferences(
    channel_id: int,
    owner_id: int,
    *,
    preset: Optional[str],
    period_days: Optional[int],
    start_date: Optional[date],
    end_date: Optional[date],
) -> Optional[dict]:
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            UPDATE content_factory_channels
            SET preferred_period_preset = COALESCE($3, preferred_period_preset),
                preferred_period_days = COALESCE($4, preferred_period_days),
                preferred_start_date = COALESCE($5, preferred_start_date),
                preferred_end_date = COALESCE($6, preferred_end_date),
                updated_at = NOW()
            WHERE channel_id = $1 AND owner_id = $2
            RETURNING *
            """,
            channel_id,
            owner_id,
            preset,
            period_days,
            start_date,
            end_date,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


def _days_since(published_at: Optional[datetime]) -> float:
    if not published_at:
        return 365.0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    diff = now - published_at
    return max(diff.total_seconds() / 86400.0, 1.0)


def _velocity_per_day(views: int, published_at: Optional[datetime]) -> float:
    return float(int(views or 0) / _days_since(published_at))


def _calc_outlier_score(
    views: int,
    published_at: Optional[datetime],
    engagement_rate: float,
    baseline_views: float,
    baseline_velocity: float,
    subscribers_count: int,
) -> float:
    views_factor = max(float(views) / max(baseline_views, 1.0), 0.0)
    velocity = _velocity_per_day(views, published_at)
    velocity_factor = max(velocity / max(baseline_velocity, 1.0), 0.0)

    # relative to subscriber base: >1 means views above channel audience size
    subs_base = max(int(subscribers_count or 0), 1)
    subs_factor = float(views) / float(subs_base)

    er_boost = 1.0 + min(max(engagement_rate, 0.0), 0.25) * 1.6
    subs_boost = 1.0 + min(max(subs_factor, 0.0), 3.0) * 0.18

    # weighted blend makes score stable for both new and old videos
    blended = (0.52 * views_factor) + (0.33 * velocity_factor) + (0.15 * subs_factor)
    return max(blended * er_boost * subs_boost, 0.0)


async def upsert_channel_video(
    owner_id: int,
    channel: dict,
    video: ContentFactoryVideoPayload,
    *,
    conn=None,
) -> None:
    owns_conn = conn is None
    if owns_conn:
        conn = await get_conn()
    try:
        monotonic_upsert = _env_flag_enabled("CONTENT_FACTORY_MONOTONIC_UPSERT_ENABLED", "1")
        video_external_id = str(video.video_external_id or "").strip()
        if video_external_id:
            await conn.execute(
                """
                DELETE FROM content_factory_video_stats
                WHERE owner_id = $1
                  AND channel_id = $2
                  AND social_network = $3
                  AND video_external_id = $4
                  AND video_url <> $5
                """,
                owner_id,
                channel["channel_id"],
                channel["social_network"],
                video_external_id,
                video.video_url,
            )
        await conn.execute(
            """
            INSERT INTO content_factory_video_stats (
                owner_id,
                channel_id,
                social_network,
                video_external_id,
                video_url,
                title,
                published_at,
                captured_at,
                views,
                likes,
                comments,
                shares,
                saves,
                duration_seconds,
                extra
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, NOW(), $8, $9, $10, $11, $12, $13, $14
            )
            ON CONFLICT (owner_id, social_network, video_url)
            DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                video_external_id = COALESCE(EXCLUDED.video_external_id, content_factory_video_stats.video_external_id),
                title = CASE
                    WHEN EXCLUDED.title IS NOT NULL AND EXCLUDED.title <> '' THEN EXCLUDED.title
                    ELSE content_factory_video_stats.title
                END,
                published_at = COALESCE(EXCLUDED.published_at, content_factory_video_stats.published_at),
                captured_at = NOW(),
                views = CASE
                    WHEN $15 THEN GREATEST(EXCLUDED.views, content_factory_video_stats.views)
                    ELSE EXCLUDED.views
                END,
                likes = CASE
                    WHEN $15 THEN GREATEST(EXCLUDED.likes, content_factory_video_stats.likes)
                    ELSE EXCLUDED.likes
                END,
                comments = CASE
                    WHEN $15 THEN GREATEST(EXCLUDED.comments, content_factory_video_stats.comments)
                    ELSE EXCLUDED.comments
                END,
                shares = CASE
                    WHEN $15 THEN GREATEST(EXCLUDED.shares, content_factory_video_stats.shares)
                    ELSE EXCLUDED.shares
                END,
                saves = CASE
                    WHEN $15 THEN GREATEST(EXCLUDED.saves, content_factory_video_stats.saves)
                    ELSE EXCLUDED.saves
                END,
                duration_seconds = COALESCE(EXCLUDED.duration_seconds, content_factory_video_stats.duration_seconds),
                extra = COALESCE(content_factory_video_stats.extra, '{}'::jsonb) || COALESCE(EXCLUDED.extra, '{}'::jsonb)
            """,
            owner_id,
            channel["channel_id"],
            channel["social_network"],
            video_external_id or video.video_external_id,
            video.video_url,
            video.title,
            video.published_at,
            int(video.views or 0),
            int(video.likes or 0),
            int(video.comments or 0),
            int(video.shares or 0),
            int(video.saves or 0),
            video.duration_seconds,
            json.dumps(video.extra or {}),
            monotonic_upsert,
        )
        # Append a historical snapshot for owners that have snapshot tracking enabled.
        if _snapshots_enabled_for(owner_id):
            video_id_row = await conn.fetchrow(
                "SELECT video_id FROM content_factory_video_stats WHERE owner_id=$1 AND social_network=$2 AND video_url=$3",
                owner_id,
                channel["social_network"],
                video.video_url,
            )
            if video_id_row:
                await conn.execute(
                    """
                    INSERT INTO content_factory_video_snapshots
                        (owner_id, video_id, captured_at, views, likes, comments, shares, saves)
                    VALUES ($1, $2, NOW(), $3, $4, $5, $6, $7)
                    """,
                    owner_id,
                    video_id_row["video_id"],
                    int(video.views or 0),
                    int(video.likes or 0),
                    int(video.comments or 0),
                    int(video.shares or 0),
                    int(video.saves or 0),
                )
    finally:
        if owns_conn:
            await conn.close()


async def sync_channel_videos(
    owner_id: int,
    channel: dict,
    videos: list[ContentFactoryVideoPayload],
    *,
    prune_missing: bool,
) -> int:
    conn = await get_conn()
    try:
        unique_videos: list[ContentFactoryVideoPayload] = []
        seen_urls: set[str] = set()
        for video in videos:
            video_url = str(video.video_url or "").strip()
            if not video_url or video_url in seen_urls:
                continue
            seen_urls.add(video_url)
            unique_videos.append(video)

        async with conn.transaction():
            for video in unique_videos:
                await upsert_channel_video(owner_id=owner_id, channel=channel, video=video, conn=conn)

            if prune_missing and seen_urls:
                existing_count = int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)::int
                        FROM content_factory_video_stats
                        WHERE owner_id = $1
                          AND channel_id = $2
                        """,
                        owner_id,
                        channel["channel_id"],
                    )
                    or 0
                )
                min_ratio = float(os.getenv("CONTENT_FACTORY_PRUNE_MIN_SAFETY_RATIO", "0.80"))
                min_ratio = max(0.0, min(1.0, min_ratio))
                safe_floor = int(existing_count * min_ratio)
                can_prune = existing_count == 0 or len(seen_urls) >= max(1, safe_floor)

                if can_prune:
                    await conn.execute(
                        """
                        DELETE FROM content_factory_video_stats
                        WHERE owner_id = $1
                          AND channel_id = $2
                          AND NOT (video_url = ANY($3::text[]))
                        """,
                        owner_id,
                        channel["channel_id"],
                        list(seen_urls),
                    )
                else:
                    logger.warning(
                        "[content_factory] prune skipped for safety owner_id=%s channel_id=%s existing_count=%s current_seen=%s min_ratio=%.2f",
                        owner_id,
                        channel["channel_id"],
                        existing_count,
                        len(seen_urls),
                        min_ratio,
                    )

        return len(unique_videos)
    finally:
        await conn.close()


async def list_videos(
    owner_id: int,
    *,
    project_id: Optional[int],
    period_days: int,
    month: Optional[str],
    social_network: Optional[str],
    moderation_status: Optional[str],
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> tuple[int, list[dict]]:
    await _ensure_schema_ready()
    allowed_sort = {
        "social_network": "v.social_network",
        "published_at": "v.published_at",
        "views": "v.views",
        "likes": "v.likes",
        "comments": "v.comments",
        "captured_at": "v.captured_at",
        "moderation_status": "v.moderation_status",
    }
    order_col = allowed_sort.get(sort_by, "v.views")
    order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    window_start, window_end = _resolve_period_window(period_days=period_days, month=month)

    conn = await get_conn()
    try:
        window_field = "COALESCE(v.published_at, v.captured_at)"
        conditions = ["v.owner_id = $1", f"{window_field} >= $2", f"{window_field} < $3", _valid_youtube_video_sql("v")]
        params = [owner_id, window_start, window_end]

        if social_network:
            conditions.append(f"v.social_network = ${len(params) + 1}")
            params.append(social_network)

        if moderation_status and moderation_status != "all":
            conditions.append(f"v.moderation_status = ${len(params) + 1}")
            params.append(moderation_status)

        if project_id is not None:
            conditions.append(f"c.project_id = ${len(params) + 1}")
            params.append(project_id)

        where_sql = " AND ".join(conditions)

        total_row = await conn.fetchrow(
            f"""
            SELECT COUNT(*)::int AS total
            FROM content_factory_video_stats v
            JOIN content_factory_channels c ON c.channel_id = v.channel_id
            WHERE {where_sql}
            """,
            *params,
        )
        total = int(total_row["total"] if total_row else 0)

        offset = (page - 1) * page_size
        rows = await conn.fetch(
            f"""
            SELECT
                v.video_id,
                v.channel_id,
                c.project_id,
                p.name AS project_name,
                v.social_network,
                c.channel_title,
                c.channel_url,
                v.video_external_id,
                v.video_url,
                v.title,
                v.published_at,
                v.captured_at,
                v.views,
                v.likes,
                v.comments,
                v.shares,
                v.saves,
                v.duration_seconds,
                v.extra,
                {_is_short_sql("v")} AS is_short,
                v.moderation_status,
                v.moderation_updated_at
            FROM content_factory_video_stats v
            JOIN content_factory_channels c ON c.channel_id = v.channel_id
            LEFT JOIN content_factory_projects p ON p.project_id = c.project_id
            WHERE {where_sql}
            ORDER BY {order_col} {order_dir}, v.video_id DESC
            LIMIT ${len(params) + 1}
            OFFSET ${len(params) + 2}
            """,
            *params,
            page_size,
            offset,
        )
        items: list[dict] = []
        for row in rows:
            item = dict(row)
            item.update(_normalize_video_provenance(item.get("extra")))
            item.pop("extra", None)
            items.append(item)
        return total, items
    finally:
        await conn.close()


async def get_overview(
    owner_id: int,
    period_days: int,
    month: Optional[str] = None,
    social_network: Optional[str] = None,
    project_id: Optional[int] = None,
) -> dict:
    await _ensure_schema_ready()
    window_start, window_end = _resolve_period_window(period_days=period_days, month=month)
    conn = await get_conn()
    try:
        video_conditions = [
            "v.owner_id = $1",
            "COALESCE(v.published_at, v.captured_at) >= $2",
            "COALESCE(v.published_at, v.captured_at) < $3",
            _valid_youtube_video_sql("v"),
        ]
        video_params: list[object] = [owner_id, window_start, window_end]

        channel_conditions = ["owner_id = $1"]
        channel_params: list[object] = [owner_id]

        if social_network:
            video_conditions.append(f"v.social_network = ${len(video_params) + 1}")
            video_params.append(social_network)
            channel_conditions.append(f"social_network = ${len(channel_params) + 1}")
            channel_params.append(social_network)

        if project_id is not None:
            video_conditions.append(f"c.project_id = ${len(video_params) + 1}")
            video_params.append(project_id)
            channel_conditions.append(f"project_id = ${len(channel_params) + 1}")
            channel_params.append(project_id)

        video_where_sql = " AND ".join(video_conditions)
        channel_where_sql = " AND ".join(channel_conditions)

        total_channels = await conn.fetchval(
            f"""
            SELECT COUNT(*)::int
            FROM content_factory_channels
            WHERE {channel_where_sql}
            """,
            *channel_params,
        )

        base = await conn.fetchrow(
            f"""
            SELECT
              COUNT(*)::int AS total_videos,
              COALESCE(SUM(views), 0)::bigint AS total_views
                        FROM content_factory_video_stats v
                        JOIN content_factory_channels c ON c.channel_id = v.channel_id
            WHERE {video_where_sql}
            """,
            *video_params,
        )

        by_social_rows = await conn.fetch(
            f"""
            SELECT v.social_network,
                   COUNT(*)::int AS total_videos,
                   COALESCE(SUM(views), 0)::bigint AS total_views
                 FROM content_factory_video_stats v
                 JOIN content_factory_channels c ON c.channel_id = v.channel_id
            WHERE {video_where_sql}
            GROUP BY v.social_network
            ORDER BY v.social_network
            """,
            *video_params,
        )

        by_social_network = {
            row["social_network"]: {
                "total_videos": int(row["total_videos"]),
                "total_views": int(row["total_views"]),
            }
            for row in by_social_rows
        }

        return {
            "total_channels": int(total_channels or 0),
            "total_videos": int(base["total_videos"] if base else 0),
            "total_views": int(base["total_views"] if base else 0),
            "by_social_network": by_social_network,
        }
    finally:
        await conn.close()


async def list_channel_period_stats(
    owner_id: int,
    *,
    project_id: Optional[int],
    period_days: int,
    month: Optional[str],
    social_network: Optional[str],
    moderation_status: Optional[str],
) -> list[dict]:
    await _ensure_schema_ready()
    window_start, window_end = _resolve_period_window(period_days=period_days, month=month)

    conn = await get_conn()
    try:
        params: list[object] = [owner_id, window_start, window_end]

        channel_conditions = ["c.owner_id = $1"]
        video_join_conditions = [
            "v.channel_id = c.channel_id",
            "v.owner_id = $1",
            "COALESCE(v.published_at, v.captured_at) >= $2",
            "COALESCE(v.published_at, v.captured_at) < $3",
            _valid_youtube_video_sql("v"),
        ]

        if social_network:
            channel_conditions.append(f"c.social_network = ${len(params) + 1}")
            params.append(social_network)

        if moderation_status and moderation_status != "all":
            video_join_conditions.append(f"v.moderation_status = ${len(params) + 1}")
            params.append(moderation_status)

        if project_id is not None:
            channel_conditions.append(f"c.project_id = ${len(params) + 1}")
            params.append(project_id)

        channel_where_sql = " AND ".join(channel_conditions)
        video_join_sql = " AND ".join(video_join_conditions)

        rows = await conn.fetch(
            f"""
            SELECT
                c.channel_id,
                c.channel_title,
                c.channel_url,
                COALESCE(COUNT(v.video_id), 0)::int AS total_videos,
                COALESCE(
                    SUM(
                        CASE
                            WHEN {_is_short_sql("v")} THEN 1
                            ELSE 0
                        END
                    ),
                    0
                )::int AS total_shorts,
                COALESCE(SUM(v.views), 0)::bigint AS total_views,
                MAX(v.published_at) AS last_published_at
            FROM content_factory_channels c
            LEFT JOIN content_factory_video_stats v ON {video_join_sql}
            WHERE {channel_where_sql}
            GROUP BY c.channel_id, c.channel_title, c.channel_url
            ORDER BY total_views DESC, total_videos DESC, c.channel_id DESC
            """,
            *params,
        )

        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def set_video_moderation_for_owner(video_id: int, owner_id: int, moderation_status: str) -> bool:
    conn = await get_conn()
    try:
        result = await conn.execute(
            """
            UPDATE content_factory_video_stats
            SET moderation_status = $3,
                moderation_updated_at = NOW()
            WHERE video_id = $1 AND owner_id = $2
            """,
            video_id,
            owner_id,
            moderation_status,
        )
        return result != "UPDATE 0"
    finally:
        await conn.close()


async def delete_video_for_owner(video_id: int, owner_id: int) -> bool:
    conn = await get_conn()
    try:
        result = await conn.execute(
            "DELETE FROM content_factory_video_stats WHERE video_id = $1 AND owner_id = $2",
            video_id,
            owner_id,
        )
        return result != "DELETE 0"
    finally:
        await conn.close()


async def create_report_history(owner_id: int, period_days: int, social_network: Optional[str]) -> dict:
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO content_factory_report_history (owner_id, period_days, social_network)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            owner_id,
            period_days,
            social_network,
        )
        return dict(row)
    finally:
        await conn.close()


async def list_report_history(owner_id: int, limit: int = 50) -> list[dict]:
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT *
            FROM content_factory_report_history
            WHERE owner_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            owner_id,
            limit,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_report_for_owner(report_id: str, owner_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM content_factory_report_history
            WHERE report_id = $1 AND owner_id = $2
            """,
            report_id,
            owner_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def delete_project_videos(owner_id: int, project_id: int) -> int:
    """Delete all videos for a project before re-syncing to prevent duplicates."""
    conn = await get_conn()
    try:
        result = await conn.execute(
            """
            DELETE FROM content_factory_video_stats v
            USING content_factory_channels c
            WHERE v.channel_id = c.channel_id
              AND c.owner_id = $1
              AND c.project_id = $2
            """,
            owner_id,
            project_id,
        )
        # Parse delete count from result like "DELETE n"
        if isinstance(result, str):
            count_str = result.split()[-1]
            try:
                return int(count_str)
            except ValueError:
                return 0
        return 0
    finally:
        await conn.close()


async def delete_channel_videos(owner_id: int, channel_id: int) -> int:
    """Delete all collected videos for a specific channel before re-syncing it."""
    conn = await get_conn()
    try:
        result = await conn.execute(
            """
            DELETE FROM content_factory_video_stats
            WHERE owner_id = $1
              AND channel_id = $2
            """,
            owner_id,
            channel_id,
        )
        if isinstance(result, str):
            count_str = result.split()[-1]
            try:
                return int(count_str)
            except ValueError:
                return 0
        return 0
    finally:
        await conn.close()


async def get_channel_insights(
    owner_id: int,
    channel_id: int,
    *,
    period_days: int,
    month: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
) -> Optional[dict]:
    window_start, window_end = _resolve_custom_window(
        period_days=period_days,
        month=month,
        start_date=start_date,
        end_date=end_date,
    )

    conn = await get_conn()
    try:
        channel = await conn.fetchrow(
            """
            SELECT channel_id, channel_title, channel_url, subscribers_count
            FROM content_factory_channels
            WHERE owner_id = $1 AND channel_id = $2
            """,
            owner_id,
            channel_id,
        )
        if not channel:
            return None

        videos = await conn.fetch(
            """
            SELECT
                v.video_id,
                v.title,
                v.video_url,
                v.views,
                v.likes,
                v.comments,
                v.duration_seconds,
                v.extra,
                v.published_at,
                COALESCE(v.published_at, v.captured_at) AS rank_ts
            FROM content_factory_video_stats v
            WHERE v.owner_id = $1
              AND v.channel_id = $2
              AND COALESCE(v.published_at, v.captured_at) >= $3
              AND COALESCE(v.published_at, v.captured_at) < $4
                            AND NOT (v.social_network = 'youtube' AND (v.video_external_id IS NULL OR v.video_external_id !~ '^[A-Za-z0-9_-]{11}$' OR v.published_at IS NULL))
            ORDER BY rank_ts DESC, v.video_id DESC
            """,
            owner_id,
            channel_id,
            window_start,
            window_end,
        )

        rows = [dict(row) for row in videos]
        subscribers_count = int(channel.get("subscribers_count") or 0)
        total_views = sum(int(item.get("views") or 0) for item in rows)
        total_likes = sum(int(item.get("likes") or 0) for item in rows)
        total_comments = sum(int(item.get("comments") or 0) for item in rows)
        total_shorts = sum(
            1
            for item in rows
            if _is_short(
                item.get("duration_seconds"),
                video_url=item.get("video_url"),
                title=item.get("title"),
                extra=item.get("extra"),
            )
        )
        total_videos = len(rows) - total_shorts
        avg_views = float(total_views / len(rows)) if rows else 0.0

        views_sorted = sorted(int(item.get("views") or 0) for item in rows)
        velocity_sorted = sorted(_velocity_per_day(int(item.get("views") or 0), item.get("published_at")) for item in rows)

        def median(values: list[float]) -> float:
            if not values:
                return 0.0
            mid = len(values) // 2
            if len(values) % 2 == 0:
                return float((values[mid - 1] + values[mid]) / 2)
            return float(values[mid])

        median_views = median([float(v) for v in views_sorted])
        median_velocity = median(velocity_sorted)

        def to_insight_video(item: dict, outlier_score: float, explanation: Optional[str] = None) -> dict:
            item_views = int(item.get("views") or 0)
            item_likes = int(item.get("likes") or 0)
            item_comments = int(item.get("comments") or 0)
            item_er = _engagement_rate(item_views, item_likes, item_comments)
            provenance = _normalize_video_provenance(item.get("extra"))
            return {
                "video_id": int(item.get("video_id") or 0),
                "title": item.get("title") or "Untitled",
                "video_url": item.get("video_url") or "",
                "views": item_views,
                "likes": item_likes,
                "comments": item_comments,
                "is_short": _is_short(
                    item.get("duration_seconds"),
                    video_url=item.get("video_url"),
                    title=item.get("title"),
                    extra=item.get("extra"),
                ),
                "published_at": item.get("published_at"),
                "source": provenance["source"],
                "recovery_applied": provenance["recovery_applied"],
                "recovery_source": provenance["recovery_source"],
                "recovered_fields": provenance["recovered_fields"],
                "engagement_rate": item_er,
                "outlier_score": float(outlier_score),
                "explanation": explanation,
            }

        def simple_outlier_score(item: dict) -> float:
            views = float(int(item.get("views") or 0))
            avg_factor = views / max(avg_views, 1.0)
            if subscribers_count > 0:
                subs_factor = views / float(max(subscribers_count, 1))
                return (0.8 * avg_factor) + (0.2 * subs_factor)
            return avg_factor

        top_outlier_video = None
        most_discussed_video = None

        if rows:
            scored_rows = []
            for item in rows:
                item_views = int(item.get("views") or 0)
                item_likes = int(item.get("likes") or 0)
                item_comments = int(item.get("comments") or 0)
                er = _engagement_rate(item_views, item_likes, item_comments)
                score = simple_outlier_score(item)
                scored_rows.append((score, item))

            outlier_row = max(
                scored_rows,
                key=lambda x: (x[0], int(x[1].get("views") or 0)),
            )
            outlier_score = float(outlier_row[0])
            top_outlier_video = to_insight_video(
                outlier_row[1],
                outlier_score=outlier_score,
                explanation="Видео показывает сильное отклонение от нормы канала по просмотрам, скорости набора и вовлечению.",
            )

            discussed_row = max(
                rows,
                key=lambda item: (
                    _engagement_rate(
                        int(item.get("views") or 0),
                        int(item.get("likes") or 0),
                        int(item.get("comments") or 0),
                    ),
                    int(item.get("comments") or 0),
                    int(item.get("likes") or 0),
                ),
            )
            discussed_er = _engagement_rate(
                int(discussed_row.get("views") or 0),
                int(discussed_row.get("likes") or 0),
                int(discussed_row.get("comments") or 0),
            )
            most_discussed_video = to_insight_video(
                discussed_row,
                outlier_score=simple_outlier_score(discussed_row),
                explanation=_build_discussion_explanation(
                    engagement_rate=discussed_er,
                    likes=int(discussed_row.get("likes") or 0),
                    comments=int(discussed_row.get("comments") or 0),
                ),
            )

        videos_list = [
            to_insight_video(item, outlier_score=simple_outlier_score(item))
            for item in sorted(
                rows,
                key=lambda item: (
                    int(item.get("views") or 0),
                    int(item.get("likes") or 0),
                    int(item.get("comments") or 0),
                ),
                reverse=True,
            )
        ]

        return {
            "channel_id": int(channel["channel_id"]),
            "channel_title": channel.get("channel_title"),
            "channel_url": channel.get("channel_url"),
            "subscribers_count": subscribers_count,
            "start_date": window_start.date(),
            "end_date": (window_end - timedelta(days=1)).date(),
            "total_videos": int(total_videos),
            "total_shorts": int(total_shorts),
            "total_views": int(total_views),
            "total_likes": int(total_likes),
            "total_comments": int(total_comments),
            "top_outlier_video": top_outlier_video,
            "most_discussed_video": most_discussed_video,
            "videos": videos_list,
        }
    finally:
        await conn.close()


async def get_overall_insights(
    owner_id: int,
    *,
    project_id: Optional[int],
    period_days: int,
    month: Optional[str],
    social_network: Optional[str],
    channel_periods: list[dict],
) -> dict:
    conn = await get_conn()
    try:
        params: list[object] = [owner_id]
        conditions = ["owner_id = $1"]

        if project_id is not None:
            conditions.append(f"project_id = ${len(params) + 1}")
            params.append(project_id)

        if social_network:
            conditions.append(f"social_network = ${len(params) + 1}")
            params.append(social_network)

        where_sql = " AND ".join(conditions)
        channel_rows = await conn.fetch(
            f"""
            SELECT channel_id, channel_title, channel_url
            FROM content_factory_channels
            WHERE {where_sql}
            ORDER BY created_at DESC
            """,
            *params,
        )
    finally:
        await conn.close()

    period_map = {
        int(item.get("channel_id")): item
        for item in (channel_periods or [])
        if item.get("channel_id")
    }

    total_videos = 0
    total_shorts = 0
    total_views = 0
    channel_summaries: list[dict] = []
    best_channel: Optional[dict] = None

    for channel in channel_rows:
        channel_id = int(channel["channel_id"])
        selected_period = period_map.get(channel_id, {})

        insight = await get_channel_insights(
            owner_id=owner_id,
            channel_id=channel_id,
            period_days=int(selected_period.get("period_days") or period_days),
            month=month,
            start_date=selected_period.get("start_date"),
            end_date=selected_period.get("end_date"),
        )
        if not insight:
            continue

        channel_total = int(insight.get("total_videos") or 0) + int(insight.get("total_shorts") or 0)
        if channel_total <= 0:
            successful_outliers = 0
        else:
            outlier_video = insight.get("top_outlier_video") or {}
            successful_outliers = 1 if float(outlier_video.get("outlier_score") or 0.0) >= 1.35 else 0

        channel_summary = {
            "channel_id": channel_id,
            "channel_title": insight.get("channel_title"),
            "channel_url": insight.get("channel_url"),
            "total_videos": int(insight.get("total_videos") or 0),
            "total_shorts": int(insight.get("total_shorts") or 0),
            "total_views": int(insight.get("total_views") or 0),
            "successful_outliers": successful_outliers,
            "top_outlier_video": insight.get("top_outlier_video"),
        }
        channel_summaries.append(channel_summary)

        total_videos += int(insight.get("total_videos") or 0)
        total_shorts += int(insight.get("total_shorts") or 0)
        total_views += int(insight.get("total_views") or 0)

        if not best_channel:
            best_channel = channel_summary
            continue

        current_key = (
            int(channel_summary.get("successful_outliers") or 0),
            int(channel_summary.get("total_views") or 0),
            int(channel_summary.get("total_videos") or 0) + int(channel_summary.get("total_shorts") or 0),
        )
        best_key = (
            int(best_channel.get("successful_outliers") or 0),
            int(best_channel.get("total_views") or 0),
            int(best_channel.get("total_videos") or 0) + int(best_channel.get("total_shorts") or 0),
        )
        if current_key > best_key:
            best_channel = channel_summary

    return {
        "total_channels": len(channel_summaries),
        "total_videos": int(total_videos),
        "total_shorts": int(total_shorts),
        "total_views": int(total_views),
        "most_effective_channel_id": best_channel.get("channel_id") if best_channel else None,
        "most_effective_channel_title": best_channel.get("channel_title") if best_channel else None,
        "most_effective_channel_url": best_channel.get("channel_url") if best_channel else None,
        "most_effective_channel_successful_outliers": int(best_channel.get("successful_outliers") or 0) if best_channel else 0,
        "channels": channel_summaries,
    }
