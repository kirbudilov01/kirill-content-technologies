import logging
import os
import re
from collections import Counter
from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from celery import shared_task
from db import get_conn

from .crud import (
    get_channel_for_owner,
    list_channels_for_sync,
    list_videos,
    mark_project_collection,
    mark_channel_sync_result,
    mark_channel_sync_started,
    sync_channel_videos,
)
from .google_sheets import append_rows_to_google_sheets, export_rows_to_google_sheets, write_per_network_sheets
from .parsers import parse_channel

logger = logging.getLogger(__name__)
_YT_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _classify_failure_reason(status: str, message: Optional[str]) -> Optional[str]:
    if status not in {"partial", "error"}:
        return None

    text = str(message or "").lower()
    if not text:
        return "unknown"

    if "youtube api keys are not set" in text:
        return "youtube_api_keys_missing"
    if "apify_token не задан" in text or "apify token" in text:
        return "apify_token_missing"
    if "monthly usage hard limit exceeded" in text or "platform-feature-disabled" in text:
        return "external_quota_or_plan_limit"
    if "payment required" in text or "proxy" in text and "402" in text:
        return "proxy_billing_blocked"
    if "apify actor network error" in text or "apify недоступен" in text:
        return "apify_unavailable"
    if "network is unreachable" in text or "сетевая ошибка" in text or "timeout" in text:
        return "network_unreachable"
    if "anti-bot" in text or "captcha" in text or "не робот" in text or "проверка безопасности" in text:
        return "anti_bot_blocked"
    if "unable to extract data" in text or "изменилась структура страницы" in text or "изменилась верстка" in text:
        return "extractor_broken_or_page_changed"
    if "не удалось извлечь публикации" in text or "не нашли публикации" in text:
        return "empty_or_unreadable_channel"
    if "низкое покрытие метрик" in text:
        return "low_coverage"
    if "playwright" in text and "не установлен" in text:
        return "runtime_dependency_missing"
    return "unknown"


def _flag_enabled(name: str, default: str = "1") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _prune_allowed_for_network(network: str) -> bool:
    raw = str(
        os.getenv(
            "CONTENT_FACTORY_PRUNE_ALLOWED_NETWORKS",
            "youtube,vk,ok,rutube,dzen",
        )
    )
    allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return network.lower() in allowed


def _prune_allowed_for_partial(network: str) -> bool:
    raw = str(
        os.getenv(
            "CONTENT_FACTORY_PRUNE_PARTIAL_ALLOWED_NETWORKS",
            "rutube,dzen",
        )
    )
    allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return network.lower() in allowed


def _coverage_percent(total: int, filled: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, int(round((filled / total) * 100))))


def _build_sync_quality(network: str, videos: list) -> dict[str, int]:
    total = len(videos)
    return {
        "video_count": total,
        "coverage_published_at": _coverage_percent(total, sum(1 for video in videos if getattr(video, "published_at", None) is not None)),
        "coverage_views": _coverage_percent(total, sum(1 for video in videos if int(getattr(video, "views", 0) or 0) > 0)),
        "coverage_likes": _coverage_percent(total, sum(1 for video in videos if int(getattr(video, "likes", 0) or 0) > 0)),
        "coverage_comments": _coverage_percent(total, sum(1 for video in videos if int(getattr(video, "comments", 0) or 0) > 0)),
    }


def _apply_quality_gate(network: str, sync_status: str, quality: dict[str, int]) -> tuple[str, Optional[str]]:
    if sync_status == "error":
        return sync_status, None

    thresholds = {
        "youtube": {"coverage_views": 95, "coverage_published_at": 95},
        "instagram": {"coverage_views": 80, "coverage_published_at": 70},
        "tiktok": {"coverage_views": 80, "coverage_published_at": 70},
        # HTTP/browser-only parsers for VK/OK/Dzen can reliably extract links while
        # counters/dates are often hidden behind auth/anti-bot walls.
        "vk": {"coverage_views": 0, "coverage_published_at": 0},
        "ok": {"coverage_views": 0, "coverage_published_at": 0},
        "rutube": {"coverage_views": 60, "coverage_published_at": 40},
        "likee": {"coverage_views": 60, "coverage_published_at": 40},
        "dzen": {"coverage_views": 0, "coverage_published_at": 0},
    }
    required = thresholds.get(network, {"coverage_views": 70, "coverage_published_at": 50})
    failed = [
        f"{metric.replace('coverage_', '')} {quality.get(metric, 0)}% < {threshold}%"
        for metric, threshold in required.items()
        if quality.get(metric, 0) < threshold
    ]
    if not failed:
        return sync_status, None

    return "partial", "Низкое покрытие метрик: " + ", ".join(failed)


def _should_schedule_quality_retry(final_status: str, quality_message: Optional[str], retry_attempt: int) -> bool:
    if final_status != "partial":
        return False
    if not quality_message:
        return False
    if not _flag_enabled("CONTENT_FACTORY_LOW_COVERAGE_RETRY_ENABLED", "1"):
        return False
    max_attempts = max(0, int(os.getenv("CONTENT_FACTORY_LOW_COVERAGE_RETRY_MAX_ATTEMPTS", "3")))
    return retry_attempt < max_attempts


def _should_schedule_transient_retry(final_status: str, failure_reason: Optional[str], retry_attempt: int) -> bool:
    if final_status not in {"partial", "error"}:
        return False
    if not failure_reason:
        return False
    if not _flag_enabled("CONTENT_FACTORY_TRANSIENT_RETRY_ENABLED", "1"):
        return False

    transient_reasons = {
        "network_unreachable",
        "apify_unavailable",
        "unknown",
    }
    if failure_reason not in transient_reasons:
        return False

    max_attempts = max(0, int(os.getenv("CONTENT_FACTORY_TRANSIENT_RETRY_MAX_ATTEMPTS", "2")))
    return retry_attempt < max_attempts


def _retry_delay_seconds(failure_reason: Optional[str], retry_attempt: int) -> int:
    quality_base = max(30, int(os.getenv("CONTENT_FACTORY_LOW_COVERAGE_RETRY_DELAY_SECONDS", "180")))
    transient_base = max(30, int(os.getenv("CONTENT_FACTORY_TRANSIENT_RETRY_DELAY_SECONDS", "240")))

    reason = str(failure_reason or "")
    # For flaky network/external source issues, use stronger backoff than quality retries.
    if reason in {"network_unreachable", "apify_unavailable", "external_quota_or_plan_limit", "unknown"}:
        return transient_base * max(1, retry_attempt + 1)
    return quality_base * max(1, retry_attempt + 1)


def _is_valid_video_for_network(network: str, video) -> bool:
    if not video.video_url or not video.title:
        return False
    if network == "youtube":
        external_id = str(video.video_external_id or "").strip()
        if external_id and _YT_VIDEO_ID_RE.match(external_id):
            return True
        url = str(video.video_url or "").strip().lower()
        return "youtube.com/watch" in url or "youtu.be/" in url
    return True


async def _acquire_channel_sync_lock(owner_id: int, channel_id: int):
    conn = await get_conn()
    try:
        acquired = await conn.fetchval(
            "SELECT pg_try_advisory_lock($1, $2)",
            int(owner_id),
            int(channel_id),
        )
        if acquired:
            return conn
    except Exception:
        await conn.close()
        raise

    await conn.close()
    return None


async def _release_channel_sync_lock(lock_conn, owner_id: int, channel_id: int) -> None:
    if lock_conn is None:
        return
    try:
        await lock_conn.execute(
            "SELECT pg_advisory_unlock($1, $2)",
            int(owner_id),
            int(channel_id),
        )
    finally:
        await lock_conn.close()


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    return datetime.fromisoformat(raw).date()


def _resolve_effective_period(period_days: int, start_date: Optional[date], end_date: Optional[date]) -> int:
    effective_period_days = period_days
    if start_date or end_date:
        right = end_date or datetime.utcnow().date()
        left = start_date or right
        delta = (right - left).days + 1
        effective_period_days = max(1, min(delta, 3650))
    return effective_period_days


def _channel_sync_payload(channel: dict[str, Any], default_period_days: int) -> dict[str, Optional[str] | int]:
    start_date = channel.get("preferred_start_date")
    end_date = channel.get("preferred_end_date")
    preferred_days = channel.get("preferred_period_days")

    if isinstance(start_date, date):
        start_date = start_date.isoformat()
    elif start_date is not None:
        start_date = str(start_date)

    if isinstance(end_date, date):
        end_date = end_date.isoformat()
    elif end_date is not None:
        end_date = str(end_date)

    period_days = int(preferred_days or default_period_days or 30)
    return {
        "period_days": max(1, min(period_days, 3650)),
        "start_date": start_date,
        "end_date": end_date,
    }


def _env_int(name: str, default: int, *, min_value: int = 0, max_value: Optional[int] = None) -> int:
    try:
        value = int(str(os.getenv(name, str(default))).strip())
    except Exception:
        value = int(default)
    if value < min_value:
        value = min_value
    if max_value is not None and value > max_value:
        value = max_value
    return value


def _weekly_export_defaults() -> dict[str, Any]:
    spreadsheet_id = str(
        os.getenv("CONTENT_FACTORY_GOOGLE_DEFAULT_SPREADSHEET_ID")
        or os.getenv("GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID")
        or ""
    ).strip()
    default_sheet = str(
        os.getenv("CONTENT_FACTORY_GOOGLE_DEFAULT_SHEET_NAME")
        or os.getenv("GOOGLE_SHEETS_DEFAULT_SHEET_NAME")
        or "Content Factory Export"
    ).strip() or "Content Factory Export"
    write_mode = str(os.getenv("CONTENT_FACTORY_WEEKLY_EXPORT_WRITE_MODE", "append")).strip().lower()
    if write_mode not in {"append", "replace"}:
        write_mode = "append"
    return {
        "spreadsheet_id": spreadsheet_id,
        "default_sheet_name": default_sheet,
        "sheet_template": str(
            os.getenv("CONTENT_FACTORY_WEEKLY_EXPORT_SHEET_TEMPLATE")
            or "{default_sheet_name} / {project_name}"
        ).strip(),
        "period_days": _env_int("CONTENT_FACTORY_WEEKLY_SYNC_PERIOD_DAYS", 3650, min_value=1, max_value=3650),
        "header_row": _env_int("CONTENT_FACTORY_GOOGLE_DEFAULT_HEADER_ROW", 1, min_value=1, max_value=10000),
        "page_size": _env_int("CONTENT_FACTORY_WEEKLY_EXPORT_PAGE_SIZE", 1000, min_value=100, max_value=5000),
        "max_rows": _env_int("CONTENT_FACTORY_WEEKLY_EXPORT_MAX_ROWS", 20000, min_value=1000, max_value=200000),
        "write_mode": write_mode,
    }


def _weekly_moscow_schedule() -> dict[str, int | str]:
    return {
        "minute": _env_int("CONTENT_FACTORY_WEEKLY_BEAT_MINUTE", 0, min_value=0, max_value=59),
        "hour": _env_int("CONTENT_FACTORY_WEEKLY_BEAT_HOUR", 5, min_value=0, max_value=23),
        "day_of_week": str(os.getenv("CONTENT_FACTORY_WEEKLY_BEAT_DAY_OF_WEEK", "1")).strip() or "1",
    }


def _matches_moscow_weekly_window(now_moscow: datetime) -> bool:
    schedule = _weekly_moscow_schedule()
    target_day = str(schedule["day_of_week"])
    weekday = now_moscow.weekday()  # Monday=0
    cron_day = "0" if weekday == 6 else str(weekday + 1)  # Celery style: Sunday=0, Monday=1
    return (
        cron_day == target_day
        and now_moscow.hour == int(schedule["hour"])
        and now_moscow.minute == int(schedule["minute"])
    )


def _render_weekly_sheet_name(template: str, project: dict[str, Any], default_sheet_name: str) -> str:
    project_name = str(project.get("name") or "").strip() or f"Project {int(project.get('project_id') or 0)}"
    try:
        rendered = template.format(
            default_sheet_name=default_sheet_name,
            project_id=int(project.get("project_id") or 0),
            owner_id=int(project.get("owner_id") or 0),
            project_name=project_name,
            social_network=str(project.get("social_network") or "").strip() or "all",
        )
    except Exception:
        rendered = f"{default_sheet_name} / {project_name}"
    value = str(rendered).strip() or f"{default_sheet_name} / {project_name}"
    return value[:100]


async def _list_active_projects_for_weekly(limit: int = 0) -> list[dict[str, Any]]:
    conn = await get_conn()
    try:
        if limit > 0:
            rows = await conn.fetch(
                """
                SELECT project_id, owner_id, name, social_network, is_active, updated_at, last_collection_at
                FROM content_factory_projects
                WHERE is_active = TRUE
                ORDER BY COALESCE(last_collection_at, TO_TIMESTAMP(0)) ASC, updated_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT project_id, owner_id, name, social_network, is_active, updated_at, last_collection_at
                FROM content_factory_projects
                WHERE is_active = TRUE
                ORDER BY COALESCE(last_collection_at, TO_TIMESTAMP(0)) ASC, updated_at DESC
                """
            )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def _sync_channel_impl(
    *,
    owner_id: int,
    channel_id: int,
    period_days: int,
    start_date: Optional[str],
    end_date: Optional[str],
    quality_retry_attempt: int,
    sync_run_id: Optional[str],
    task=None,
    schedule_quality_retry: bool,
) -> dict[str, Any]:
    selected_start = _parse_date(start_date)
    selected_end = _parse_date(end_date)
    effective_period_days = _resolve_effective_period(period_days, selected_start, selected_end)

    lock_conn = await _acquire_channel_sync_lock(owner_id=owner_id, channel_id=channel_id)
    if lock_conn is None:
        logger.info(
            "[content_factory] duplicate sync skipped owner_id=%s channel_id=%s",
            owner_id,
            channel_id,
        )
        return {"status": "skipped", "videos_synced": 0}

    try:
        channel = await get_channel_for_owner(channel_id=channel_id, owner_id=owner_id)
        if not channel:
            raise ValueError(f"Channel not found: {channel_id}")

        await mark_channel_sync_started(channel_id)

        try:
            result = await parse_channel(
                network=channel["social_network"],
                channel_url=channel["channel_url"],
                owner_id=owner_id,
                period_days=effective_period_days,
                start_date=selected_start,
                end_date=selected_end,
            )
        except Exception as exc:
            logger.exception(
                "[content_factory] parse_channel failed owner_id=%s channel_id=%s network=%s",
                owner_id,
                channel_id,
                channel.get("social_network"),
            )
            quality = {
                "video_count": 0,
                "coverage_published_at": 0,
                "coverage_views": 0,
                "coverage_likes": 0,
                "coverage_comments": 0,
            }
            message = f"Ошибка парсинга канала: {exc}"
            failure_reason = _classify_failure_reason("error", message)
            await mark_channel_sync_result(
                channel_id,
                status="error",
                error_text=message,
                sync_video_count=0,
                coverage_published_at=0,
                coverage_views=0,
                coverage_likes=0,
                coverage_comments=0,
                retry_count=quality_retry_attempt,
            )
            return {
                "status": "error",
                "videos_synced": 0,
                "quality": quality,
                "quality_message": message,
                "failure_reason": failure_reason,
                "sync_run_id": sync_run_id,
            }

        effective_network = str(result.resolved_network or channel["social_network"])
        quality = _build_sync_quality(effective_network, result.videos)
        valid_videos = [
            video
            for video in result.videos
            if _is_valid_video_for_network(effective_network, video)
        ]

        if not valid_videos:
            status = "partial" if result.sync_status != "error" else "error"
            message = result.sync_message or (
                "Не удалось получить публикации за выбранный период, но источник сохранен для последующей повторной синхронизации."
            )
            failure_reason = _classify_failure_reason(status, message)
            await mark_channel_sync_result(
                channel_id,
                status=status,
                error_text=message,
                social_network=effective_network,
                channel_external_id=result.channel_external_id,
                channel_title=result.channel_title,
                subscribers_count=int(result.subscribers_count or 0),
                sync_video_count=quality["video_count"],
                coverage_published_at=quality["coverage_published_at"],
                coverage_views=quality["coverage_views"],
                coverage_likes=quality["coverage_likes"],
                coverage_comments=quality["coverage_comments"],
                retry_count=quality_retry_attempt,
            )
            return {
                "status": status,
                "videos_synced": 0,
                "quality": quality,
                "quality_message": message,
                "failure_reason": failure_reason,
                "sync_run_id": sync_run_id,
            }

        final_status = "partial" if result.sync_status == "partial" else "ok"
        quality_status, quality_message = _apply_quality_gate(effective_network, final_status, quality)
        final_status = quality_status
        prune_missing = (
            _flag_enabled("CONTENT_FACTORY_PRUNE_STALE_ON_OK", "1")
            and _prune_allowed_for_network(effective_network)
            and (
                final_status == "ok"
                or (
                    final_status == "partial"
                    and quality.get("video_count", 0) > 0
                    and _prune_allowed_for_partial(effective_network)
                )
            )
        )
        channel_for_sync = dict(channel)
        channel_for_sync["social_network"] = effective_network
        synced_count = await sync_channel_videos(
            owner_id=owner_id,
            channel=channel_for_sync,
            videos=valid_videos,
            prune_missing=prune_missing,
        )

        retry_scheduled = False
        retry_count_to_store = quality_retry_attempt
        error_text = quality_message or result.sync_message if final_status == "partial" else None
        failure_reason = _classify_failure_reason(final_status, error_text or quality_message)
        if schedule_quality_retry and task is not None:
            retry_scheduled = _should_schedule_quality_retry(final_status, quality_message, quality_retry_attempt)
            if not retry_scheduled:
                retry_scheduled = _should_schedule_transient_retry(final_status, failure_reason, quality_retry_attempt)
            if retry_scheduled:
                retry_delay_seconds = _retry_delay_seconds(failure_reason, quality_retry_attempt)
                next_attempt = quality_retry_attempt + 1
                task.apply_async(
                    kwargs={
                        "owner_id": owner_id,
                        "channel_id": channel_id,
                        "period_days": period_days,
                        "start_date": start_date,
                        "end_date": end_date,
                        "quality_retry_attempt": next_attempt,
                        "sync_run_id": sync_run_id,
                    },
                    countdown=retry_delay_seconds,
                )
                retry_count_to_store = next_attempt
                suffix = f" Автоповтор #{next_attempt} запланирован через {retry_delay_seconds}с."
                error_text = (error_text or "Низкое покрытие метрик.") + suffix

        await mark_channel_sync_result(
            channel_id,
            status=final_status,
            error_text=error_text,
            social_network=effective_network,
            channel_external_id=result.channel_external_id,
            channel_title=result.channel_title,
            subscribers_count=int(result.subscribers_count or 0),
            sync_video_count=quality["video_count"],
            coverage_published_at=quality["coverage_published_at"],
            coverage_views=quality["coverage_views"],
            coverage_likes=quality["coverage_likes"],
            coverage_comments=quality["coverage_comments"],
            retry_count=retry_count_to_store,
        )
        return {
            "status": final_status,
            "videos_synced": synced_count,
            "quality": quality,
            "quality_message": quality_message,
            "retry_scheduled": retry_scheduled,
            "failure_reason": failure_reason,
            "sync_run_id": sync_run_id,
        }
    finally:
        await _release_channel_sync_lock(lock_conn, owner_id=owner_id, channel_id=channel_id)


async def _collect_export_rows(
    *,
    owner_id: int,
    project_id: int,
    period_days: int,
    social_network: Optional[str],
    moderation_status: Optional[str],
    page_size: int,
    max_rows: int,
) -> list[dict[str, Any]]:
    collected_rows: list[dict[str, Any]] = []
    page = 1
    remaining = max_rows

    while remaining > 0:
        current_page_size = min(page_size, remaining)
        _, rows = await list_videos(
            owner_id=owner_id,
            project_id=project_id,
            period_days=period_days,
            month=None,
            social_network=social_network,
            moderation_status=moderation_status,
            sort_by="views",
            sort_order="desc",
            page=page,
            page_size=current_page_size,
        )
        if not rows:
            break
        collected_rows.extend(rows)
        remaining -= len(rows)
        page += 1
        if len(rows) < current_page_size:
            break

    return collected_rows


@shared_task(name="content_factory.tasks.sync_channel", bind=True)
def sync_channel(
    self,
    owner_id: int,
    channel_id: int,
    period_days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quality_retry_attempt: int = 0,
    sync_run_id: Optional[str] = None,
):
    """Celery task: sync one content-factory channel and upsert videos into DB."""

    async def _run():
        return await _sync_channel_impl(
            owner_id=owner_id,
            channel_id=channel_id,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
            quality_retry_attempt=quality_retry_attempt,
            sync_run_id=sync_run_id,
            task=self,
            schedule_quality_retry=True,
        )

    try:
        import asyncio

        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("[content_factory] sync_channel failed channel_id=%s", channel_id)

        async def _mark_failed():
            await mark_channel_sync_result(
                channel_id,
                status="error",
                error_text=f"Ошибка парсинга канала: {exc}",
            )

        try:
            import asyncio

            asyncio.run(_mark_failed())
        except Exception:
            pass
        raise


@shared_task(name="content_factory.tasks.sync_project_and_export_google_sheets", bind=True)
def sync_project_and_export_google_sheets(
    self,
    owner_id: int,
    project_id: int,
    spreadsheet_id: str,
    sheet_name: str,
    period_days: int = 30,
    social_network: Optional[str] = None,
    moderation_status: Optional[str] = "all",
    include_provenance: bool = True,
    clear_sheet: bool = False,
    write_mode: str = "append",
    header_row: int = 38,
    prevent_duplicates: bool = True,
    duplicate_key: str = "video_url",
    update_existing_rows: bool = True,
    page_size: int = 1000,
    max_rows: int = 20000,
):
    """Sync all project channels, then export the collected rows to Google Sheets."""

    async def _run():
        sync_run_id = str(uuid4())
        channels = await list_channels_for_sync(owner_id=owner_id, project_id=project_id)
        channel_results: list[dict[str, Any]] = []

        if not channels:
            logger.info("[content_factory] sync_project_and_export_google_sheets: no channels found for project %s", project_id)
        else:
            inline_retry_max = max(0, int(os.getenv("CONTENT_FACTORY_INLINE_PROJECT_SYNC_RETRY_MAX_ATTEMPTS", "1")))

            for channel in channels:
                payload = _channel_sync_payload(channel, period_days)
                attempt = 0
                current = await _sync_channel_impl(
                    owner_id=owner_id,
                    channel_id=int(channel["channel_id"]),
                    period_days=int(payload["period_days"]),
                    start_date=payload["start_date"] if isinstance(payload["start_date"], str) else None,
                    end_date=payload["end_date"] if isinstance(payload["end_date"], str) else None,
                    quality_retry_attempt=0,
                    sync_run_id=sync_run_id,
                    task=None,
                    schedule_quality_retry=False,
                )

                while current.get("status") == "partial" and current.get("quality_message") and attempt < inline_retry_max:
                    attempt += 1
                    current = await _sync_channel_impl(
                        owner_id=owner_id,
                        channel_id=int(channel["channel_id"]),
                        period_days=int(payload["period_days"]),
                        start_date=payload["start_date"] if isinstance(payload["start_date"], str) else None,
                        end_date=payload["end_date"] if isinstance(payload["end_date"], str) else None,
                        quality_retry_attempt=attempt,
                        sync_run_id=sync_run_id,
                        task=None,
                        schedule_quality_retry=False,
                    )

                channel_results.append(
                    {
                        "channel_id": int(channel["channel_id"]),
                        "social_network": str(channel["social_network"]),
                        "status": str(current.get("status") or "unknown"),
                        "videos_synced": int(current.get("videos_synced") or 0),
                        "quality": current.get("quality"),
                        "quality_message": current.get("quality_message"),
                        "inline_retry_attempts": attempt,
                        "failure_reason": current.get("failure_reason"),
                        "sync_run_id": current.get("sync_run_id") or sync_run_id,
                    }
                )

        reason_counter = Counter(
            str(item.get("failure_reason"))
            for item in channel_results
            if item.get("failure_reason")
        )

        await mark_project_collection(owner_id=owner_id, project_id=project_id)

        rows = await _collect_export_rows(
            owner_id=owner_id,
            project_id=project_id,
            period_days=period_days,
            social_network=social_network,
            moderation_status=moderation_status,
            page_size=page_size,
            max_rows=max_rows,
        )

        if write_mode == "append":
            export_result = append_rows_to_google_sheets(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=rows,
                header_row=header_row,
                include_provenance=include_provenance,
                prevent_duplicates=prevent_duplicates,
                duplicate_key=duplicate_key,
                update_existing=update_existing_rows,
            )
        else:
            export_result = export_rows_to_google_sheets(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=rows,
                include_provenance=include_provenance,
                clear_sheet=clear_sheet,
            )

        # Write compact per-network sheets (B-E from row 27) when enabled.
        per_network_result: dict = {}
        if str(os.getenv("CONTENT_FACTORY_GOOGLE_PER_NETWORK_SHEETS_ENABLED", "1")).strip() in {"1", "true", "yes", "on"}:
            try:
                per_network_result = write_per_network_sheets(
                    spreadsheet_id=spreadsheet_id,
                    rows=rows,
                )
            except Exception as _pn_exc:
                logger.warning("[content_factory] per-network sheet write failed: %s", _pn_exc)

        return {
            "sync_run_id": sync_run_id,
            "channels_total": len(channel_results),
            "channels_ok": sum(1 for item in channel_results if item["status"] == "ok"),
            "channels_partial": sum(1 for item in channel_results if item["status"] == "partial"),
            "channels_error": sum(1 for item in channel_results if item["status"] == "error"),
            "channels_skipped": sum(1 for item in channel_results if item["status"] == "skipped"),
            "failure_reason_counts": dict(reason_counter),
            "videos_export_candidates": len(rows),
            "rows_written": int(export_result.get("rows_written") or 0),
            "updated_rows": int(export_result.get("updated_rows") or 0),
            "rows_appended": int(export_result.get("rows_appended") or 0),
            "rows_updated": int(export_result.get("rows_updated") or 0),
            "duplicates_skipped": int(export_result.get("duplicates_skipped") or 0),
            "updated_range": str(export_result.get("updated_range") or ""),
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "per_network_sheets": per_network_result,
            "channel_results": channel_results,
        }

    try:
        import asyncio

        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("[content_factory] sync_project_and_export_google_sheets failed project_id=%s", project_id)
        raise RuntimeError(f"Project sync/export failed: {exc}") from exc


@shared_task(name="content_factory.tasks.export_project_google_sheets", bind=True)
def export_project_google_sheets(
    self,
    owner_id: int,
    project_id: int,
    spreadsheet_id: str,
    sheet_name: str,
    period_days: int = 30,
    social_network: Optional[str] = None,
    moderation_status: Optional[str] = "all",
    include_provenance: bool = True,
    clear_sheet: bool = False,
    write_mode: str = "append",
    header_row: int = 1,
    prevent_duplicates: bool = True,
    duplicate_key: str = "video_url",
    update_existing_rows: bool = True,
    page_size: int = 1000,
    max_rows: int = 20000,
):
    """Export already-collected project rows to Google Sheets without running sync."""

    async def _run():
        rows = await _collect_export_rows(
            owner_id=owner_id,
            project_id=project_id,
            period_days=period_days,
            social_network=social_network,
            moderation_status=moderation_status,
            page_size=page_size,
            max_rows=max_rows,
        )

        if write_mode == "append":
            export_result = append_rows_to_google_sheets(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=rows,
                header_row=header_row,
                include_provenance=include_provenance,
                prevent_duplicates=prevent_duplicates,
                duplicate_key=duplicate_key,
                update_existing=update_existing_rows,
            )
        else:
            export_result = export_rows_to_google_sheets(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=rows,
                include_provenance=include_provenance,
                clear_sheet=clear_sheet,
            )

        per_network_result: dict = {}
        if str(os.getenv("CONTENT_FACTORY_GOOGLE_PER_NETWORK_SHEETS_ENABLED", "1")).strip() in {"1", "true", "yes", "on"}:
            try:
                per_network_result = write_per_network_sheets(
                    spreadsheet_id=spreadsheet_id,
                    rows=rows,
                )
            except Exception as _pn_exc:
                logger.warning("[content_factory] per-network sheet write failed: %s", _pn_exc)

        return {
            "project_id": int(project_id),
            "videos_export_candidates": len(rows),
            "rows_written": int(export_result.get("rows_written") or 0),
            "updated_rows": int(export_result.get("updated_rows") or 0),
            "rows_appended": int(export_result.get("rows_appended") or 0),
            "rows_updated": int(export_result.get("rows_updated") or 0),
            "duplicates_skipped": int(export_result.get("duplicates_skipped") or 0),
            "updated_range": str(export_result.get("updated_range") or ""),
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "per_network_sheets": per_network_result,
        }

    try:
        import asyncio

        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("[content_factory] export_project_google_sheets failed project_id=%s", project_id)
        raise RuntimeError(f"Project export failed: {exc}") from exc


@shared_task(name="content_factory.tasks.sync_all_projects_weekly", bind=True)
def sync_all_projects_weekly(
    self,
    max_projects: Optional[int] = None,
):
    """Dispatch weekly sync+export tasks for all active content-factory projects."""

    async def _run() -> dict[str, Any]:
        if not _flag_enabled("CONTENT_FACTORY_WEEKLY_SYNC_ENABLED", "0"):
            return {
                "status": "skipped",
                "reason": "weekly_sync_disabled",
                "queued": 0,
                "projects_total": 0,
            }

        defaults = _weekly_export_defaults()
        spreadsheet_id = str(defaults["spreadsheet_id"])
        if not spreadsheet_id:
            return {
                "status": "skipped",
                "reason": "google_default_spreadsheet_not_configured",
                "queued": 0,
                "projects_total": 0,
            }

        limit_env = _env_int("CONTENT_FACTORY_WEEKLY_SYNC_MAX_PROJECTS", 0, min_value=0)
        effective_limit = int(max_projects or 0) if max_projects is not None else limit_env
        projects = await _list_active_projects_for_weekly(limit=max(0, effective_limit))
        if not projects:
            return {
                "status": "success",
                "reason": "no_active_projects",
                "queued": 0,
                "projects_total": 0,
            }

        queued_items: list[dict[str, Any]] = []
        for project in projects:
            project_id = int(project["project_id"])
            owner_id = int(project["owner_id"])
            sheet_name = _render_weekly_sheet_name(
                str(defaults["sheet_template"]),
                project,
                str(defaults["default_sheet_name"]),
            )
            task = self.app.send_task(
                "content_factory.tasks.sync_project_and_export_google_sheets",
                kwargs={
                    "owner_id": owner_id,
                    "project_id": project_id,
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "period_days": int(defaults["period_days"]),
                    "social_network": None,
                    "moderation_status": "all",
                    "include_provenance": True,
                    "clear_sheet": False,
                    "write_mode": str(defaults["write_mode"]),
                    "header_row": int(defaults["header_row"]),
                    "prevent_duplicates": True,
                    "duplicate_key": "video_url",
                    "update_existing_rows": True,
                    "page_size": int(defaults["page_size"]),
                    "max_rows": int(defaults["max_rows"]),
                },
                queue="content_factory",
            )
            queued_items.append(
                {
                    "owner_id": owner_id,
                    "project_id": project_id,
                    "project_name": str(project.get("name") or ""),
                    "task_id": task.id,
                    "sheet_name": sheet_name,
                }
            )

        return {
            "status": "success",
            "projects_total": len(projects),
            "queued": len(queued_items),
            "spreadsheet_id": spreadsheet_id,
            "period_days": int(defaults["period_days"]),
            "write_mode": str(defaults["write_mode"]),
            "items": queued_items,
        }

    try:
        import asyncio

        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("[content_factory] sync_all_projects_weekly failed")
        raise RuntimeError(f"Weekly sync dispatch failed: {exc}") from exc


@shared_task(name="content_factory.tasks.dispatch_weekly_sync_if_due", bind=True)
def dispatch_weekly_sync_if_due(self):
    """Guard task: dispatch weekly project sync exactly at Monday 05:00 Moscow time."""
    if not _flag_enabled("CONTENT_FACTORY_WEEKLY_SYNC_ENABLED", "0"):
        return {
            "status": "skipped",
            "reason": "weekly_sync_disabled",
        }

    now_moscow = datetime.now(ZoneInfo("Europe/Moscow"))
    if not _matches_moscow_weekly_window(now_moscow):
        return {
            "status": "skipped",
            "reason": "outside_moscow_schedule_window",
            "now_moscow": now_moscow.isoformat(),
        }

    task = self.app.send_task(
        "content_factory.tasks.sync_all_projects_weekly",
        kwargs={},
        queue="content_factory",
    )
    return {
        "status": "queued",
        "task_id": task.id,
        "now_moscow": now_moscow.isoformat(),
    }
