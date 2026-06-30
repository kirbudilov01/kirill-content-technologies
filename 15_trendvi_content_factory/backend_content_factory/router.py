import io
import os
from datetime import date, datetime
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import xlsxwriter
from celery.result import AsyncResult

from auth.models import AuthUserModel
from auth.utils import enterprise_dependency

_get_user = enterprise_dependency()
from celery_config import celery_app

from . import crud
from .google_sheets import (
    GoogleSheetsExportError,
    append_rows_to_google_sheets,
    export_rows_to_google_sheets,
)
from .platforms import list_platforms
from .schemas import (
    ContentFactoryChannelCreate,
    ContentFactoryChannelListResponse,
    ContentFactoryChannelInsightsResponse,
    ContentFactoryChannelPeriodUpdateRequest,
    ContentFactoryPlatformListResponse,
    ContentFactoryPlatformOut,
    ContentFactoryChannelStatsResponse,
    ContentFactoryChannelOut,
    ContentFactoryOverviewStats,
    ContentFactoryOverallInsightsResponse,
    ContentFactoryOverallReportRequest,
    ContentFactoryGoogleSheetsExportRequest,
    ContentFactoryGoogleSheetsExportResponse,
    ContentFactoryProjectCreate,
    ContentFactoryProjectListResponse,
    ContentFactoryProjectOut,
    ContentFactoryProjectSyncExportRequest,
    ContentFactoryReportHistoryResponse,
    ContentFactorySyncResponse,
    ContentFactoryTaskStatusResponse,
    ContentFactoryVideoModerationRequest,
    ContentFactoryVideoListResponse,
    SyncRequest,
)

content_factory_router = APIRouter(prefix="/content-factory", tags=["Content Factory"])


@content_factory_router.get("/platforms", response_model=ContentFactoryPlatformListResponse)
async def get_supported_platforms(user: AuthUserModel = Depends(_get_user)):
    _ = user
    return ContentFactoryPlatformListResponse(
        platforms=[ContentFactoryPlatformOut(**platform.to_dict()) for platform in list_platforms()]
    )


def _channel_sync_payload(channel: dict, default_period_days: int) -> dict:
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


def _shape_task_status(task_id: str) -> ContentFactoryTaskStatusResponse:
    result = AsyncResult(task_id)
    if result.state == "PENDING":
        return ContentFactoryTaskStatusResponse(task_id=task_id, status="PENDING", result=None)
    if result.state == "SUCCESS":
        payload = result.result if isinstance(result.result, dict) else {"value": result.result}
        return ContentFactoryTaskStatusResponse(task_id=task_id, status="SUCCESS", result=payload)
    if result.state == "FAILURE":
        return ContentFactoryTaskStatusResponse(
            task_id=task_id,
            status="FAILURE",
            result={"error": str(result.info) if result.info else "Unknown error"},
        )
    payload = result.info if isinstance(result.info, dict) else None
    return ContentFactoryTaskStatusResponse(task_id=task_id, status=result.state, result=payload)


def _env_flag(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _auto_export_defaults() -> tuple[bool, str, str]:
    enabled = _env_flag("CONTENT_FACTORY_GOOGLE_AUTO_EXPORT_ENABLED", "0")
    spreadsheet_id = str(
        os.getenv("CONTENT_FACTORY_GOOGLE_DEFAULT_SPREADSHEET_ID")
        or os.getenv("GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID")
        or ""
    ).strip()
    sheet_name = str(
        os.getenv("CONTENT_FACTORY_GOOGLE_DEFAULT_SHEET_NAME")
        or os.getenv("GOOGLE_SHEETS_DEFAULT_SHEET_NAME")
        or "Content Factory Export"
    ).strip() or "Content Factory Export"
    return enabled, spreadsheet_id, sheet_name


def _auto_export_header_row_default() -> int:
    try:
        value = int(str(os.getenv("CONTENT_FACTORY_GOOGLE_DEFAULT_HEADER_ROW", "1")).strip())
    except Exception:
        value = 1
    return max(1, min(value, 10000))


def _queue_project_auto_export(
    *,
    owner_id: int,
    project_id: int,
    period_days: int,
    spreadsheet_id: str,
    sheet_name: str,
) -> Optional[ContentFactorySyncResponse]:
    if not str(spreadsheet_id or "").strip():
        return None

    header_row = _auto_export_header_row_default()

    export_task = celery_app.send_task(
        "content_factory.tasks.export_project_google_sheets",
        kwargs={
            "owner_id": owner_id,
            "project_id": project_id,
            "spreadsheet_id": str(spreadsheet_id).strip(),
            "sheet_name": str(sheet_name or "Content Factory Export").strip(),
            "period_days": int(max(1, min(period_days, 3650))),
            "social_network": None,
            "moderation_status": "all",
            "include_provenance": True,
            "clear_sheet": False,
            "write_mode": "append",
            "header_row": header_row,
            "prevent_duplicates": True,
            "duplicate_key": "video_url",
            "page_size": 1000,
            "max_rows": 20000,
        },
        queue="content_factory",
    )
    return ContentFactorySyncResponse(status="queued", task_id=export_task.id)


async def _assert_project_exists(project_id: Optional[int], owner_id: int) -> None:
    if project_id is None:
        return
    project = await crud.get_project_for_owner(project_id=project_id, owner_id=owner_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")


@content_factory_router.post("/projects", response_model=ContentFactoryProjectOut)
async def create_project(payload: ContentFactoryProjectCreate, user: AuthUserModel = Depends(_get_user)):
    project = await crud.create_project(
        owner_id=user.user_id,
        name=payload.name,
        description=payload.description,
        social_network=payload.social_network,
    )
    return ContentFactoryProjectOut(**project)


@content_factory_router.get("/projects", response_model=ContentFactoryProjectListResponse)
async def get_projects(user: AuthUserModel = Depends(_get_user)):
    projects = await crud.list_projects(owner_id=user.user_id)
    return ContentFactoryProjectListResponse(projects=[ContentFactoryProjectOut(**row) for row in projects])


@content_factory_router.delete("/projects/{project_id}")
async def delete_project(project_id: int, user: AuthUserModel = Depends(_get_user)):
    deleted = await crud.delete_project_for_owner(project_id=project_id, owner_id=user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok"}


@content_factory_router.post("/channels", response_model=ContentFactoryChannelOut)
async def add_channel(payload: ContentFactoryChannelCreate, user: AuthUserModel = Depends(_get_user)):
    await _assert_project_exists(project_id=payload.project_id, owner_id=user.user_id)

    channel = await crud.create_channel(
        owner_id=user.user_id,
        project_id=payload.project_id,
        social_network=payload.social_network,
        channel_url=str(payload.channel_url),
        channel_title=payload.channel_title,
        category=payload.category,
    )
    return ContentFactoryChannelOut(**channel)


@content_factory_router.get("/channels", response_model=ContentFactoryChannelListResponse)
async def get_channels(
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    user: AuthUserModel = Depends(_get_user),
):
    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)
    channels = await crud.list_channels(owner_id=user.user_id, social_network=social_network, project_id=project_id)
    return ContentFactoryChannelListResponse(channels=[ContentFactoryChannelOut(**row) for row in channels])


@content_factory_router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, user: AuthUserModel = Depends(_get_user)):
    deleted = await crud.delete_channel_for_owner(channel_id=channel_id, owner_id=user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"status": "ok"}


@content_factory_router.patch("/channels/{channel_id}/period", response_model=ContentFactoryChannelOut)
async def update_channel_period(
    channel_id: int,
    payload: ContentFactoryChannelPeriodUpdateRequest,
    user: AuthUserModel = Depends(_get_user),
):
    if payload.start_date and payload.end_date and payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be less than or equal to end_date")

    channel = await crud.update_channel_period_preferences(
        channel_id=channel_id,
        owner_id=user.user_id,
        preset=payload.preset,
        period_days=payload.period_days,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return ContentFactoryChannelOut(**channel)


@content_factory_router.post("/channels/{channel_id}/sync", response_model=ContentFactorySyncResponse)
async def sync_channel(channel_id: int, payload: SyncRequest, user: AuthUserModel = Depends(_get_user)):
    channel = await crud.get_channel_for_owner(channel_id=channel_id, owner_id=user.user_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await crud.mark_channel_sync_queued(channel_id)

    task = celery_app.send_task(
        "content_factory.tasks.sync_channel",
        kwargs={
            "owner_id": user.user_id,
            "channel_id": channel_id,
            "period_days": payload.period_days,
            "start_date": payload.start_date.isoformat() if payload.start_date else None,
            "end_date": payload.end_date.isoformat() if payload.end_date else None,
        },
        queue="content_factory",
    )

    auto_enabled, default_spreadsheet_id, default_sheet_name = _auto_export_defaults()
    project_id = int(channel.get("project_id") or 0)
    if auto_enabled and project_id > 0:
        _queue_project_auto_export(
            owner_id=user.user_id,
            project_id=project_id,
            period_days=payload.period_days,
            spreadsheet_id=default_spreadsheet_id,
            sheet_name=default_sheet_name,
        )

    return ContentFactorySyncResponse(status="queued", task_id=task.id)


@content_factory_router.post("/sync-all", response_model=list[ContentFactorySyncResponse])
async def sync_all_channels(
    payload: SyncRequest,
    project_id: Optional[int] = Query(default=None, ge=1),
    user: AuthUserModel = Depends(_get_user),
):
    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    channels = await crud.list_channels_for_sync(owner_id=user.user_id, project_id=project_id)
    out: list[ContentFactorySyncResponse] = []

    for channel in channels:
        await crud.mark_channel_sync_queued(int(channel["channel_id"]))
        channel_payload = _channel_sync_payload(channel, payload.period_days)
        task = celery_app.send_task(
            "content_factory.tasks.sync_channel",
            kwargs={
                "owner_id": user.user_id,
                "channel_id": int(channel["channel_id"]),
                "period_days": channel_payload["period_days"],
                "start_date": channel_payload["start_date"],
                "end_date": channel_payload["end_date"],
            },
            queue="content_factory",
        )
        out.append(ContentFactorySyncResponse(status="queued", task_id=task.id))

    if project_id is not None:
        await crud.mark_project_collection(owner_id=user.user_id, project_id=project_id)

        auto_enabled, default_spreadsheet_id, default_sheet_name = _auto_export_defaults()
        if auto_enabled:
            export_payload = _queue_project_auto_export(
                owner_id=user.user_id,
                project_id=project_id,
                period_days=payload.period_days,
                spreadsheet_id=default_spreadsheet_id,
                sheet_name=default_sheet_name,
            )
            if export_payload:
                out.append(export_payload)

    return out


@content_factory_router.post("/projects/{project_id}/sync", response_model=list[ContentFactorySyncResponse])
async def sync_project_channels(
    project_id: int,
    payload: SyncRequest,
    spreadsheet_id: Optional[str] = Query(default=None),
    sheet_name: Optional[str] = Query(default=None),
    auto_export: Optional[bool] = Query(default=None),
    user: AuthUserModel = Depends(_get_user),
):
    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    channels = await crud.list_channels_for_sync(owner_id=user.user_id, project_id=project_id)
    out: list[ContentFactorySyncResponse] = []

    for channel in channels:
        await crud.mark_channel_sync_queued(int(channel["channel_id"]))
        channel_payload = _channel_sync_payload(channel, payload.period_days)
        task = celery_app.send_task(
            "content_factory.tasks.sync_channel",
            kwargs={
                "owner_id": user.user_id,
                "channel_id": int(channel["channel_id"]),
                "period_days": channel_payload["period_days"],
                "start_date": channel_payload["start_date"],
                "end_date": channel_payload["end_date"],
            },
            queue="content_factory",
        )
        out.append(ContentFactorySyncResponse(status="queued", task_id=task.id))

    await crud.mark_project_collection(owner_id=user.user_id, project_id=project_id)

    env_enabled, env_spreadsheet_id, env_sheet_name = _auto_export_defaults()
    effective_auto_export = env_enabled if auto_export is None else bool(auto_export)
    effective_spreadsheet_id = str(spreadsheet_id or env_spreadsheet_id or "").strip()
    effective_sheet_name = str(sheet_name or env_sheet_name or "Content Factory Export").strip() or "Content Factory Export"

    if effective_auto_export:
        export_payload = _queue_project_auto_export(
            owner_id=user.user_id,
            project_id=project_id,
            period_days=payload.period_days,
            spreadsheet_id=effective_spreadsheet_id,
            sheet_name=effective_sheet_name,
        )
        if export_payload:
            out.append(export_payload)
    
    return out


@content_factory_router.post("/projects/{project_id}/sync-and-export/google-sheets", response_model=ContentFactorySyncResponse)
async def sync_project_and_export_google_sheets(
    project_id: int,
    payload: ContentFactoryProjectSyncExportRequest,
    user: AuthUserModel = Depends(_get_user),
):
    if payload.moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    task = celery_app.send_task(
        "content_factory.tasks.sync_project_and_export_google_sheets",
        kwargs={
            "owner_id": user.user_id,
            "project_id": project_id,
            "spreadsheet_id": payload.spreadsheet_id,
            "sheet_name": payload.sheet_name,
            "period_days": payload.period_days,
            "social_network": payload.social_network,
            "moderation_status": payload.moderation_status,
            "include_provenance": payload.include_provenance,
            "clear_sheet": payload.clear_sheet,
            "write_mode": payload.write_mode,
            "header_row": payload.header_row,
            "prevent_duplicates": payload.prevent_duplicates,
            "duplicate_key": payload.duplicate_key,
            "page_size": payload.page_size,
            "max_rows": payload.max_rows,
        },
        queue="content_factory",
    )
    return ContentFactorySyncResponse(status="queued", task_id=task.id)


@content_factory_router.get("/tasks/{task_id}", response_model=ContentFactoryTaskStatusResponse)
async def get_content_factory_task_status(task_id: str, user: AuthUserModel = Depends(_get_user)):
    _ = user
    return _shape_task_status(task_id)


@content_factory_router.get("/overview", response_model=ContentFactoryOverviewStats)
async def overview(
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    user: AuthUserModel = Depends(_get_user),
):
    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    data = await crud.get_overview(
        owner_id=user.user_id,
        period_days=period_days,
        month=month,
        social_network=social_network,
        project_id=project_id,
    )
    return ContentFactoryOverviewStats(**data)


@content_factory_router.get("/channels/stats", response_model=ContentFactoryChannelStatsResponse)
async def get_channel_stats(
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    moderation_status: Optional[str] = Query(default="approved"),
    user: AuthUserModel = Depends(_get_user),
):
    if moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    items = await crud.list_channel_period_stats(
        owner_id=user.user_id,
        project_id=project_id,
        period_days=period_days,
        month=month,
        social_network=social_network,
        moderation_status=moderation_status,
    )
    return ContentFactoryChannelStatsResponse(period_days=period_days, month=month, items=items)


@content_factory_router.get("/videos", response_model=ContentFactoryVideoListResponse)
async def list_videos(
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    moderation_status: Optional[str] = Query(default="all"),
    sort_by: str = Query(default="views"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    user: AuthUserModel = Depends(_get_user),
):
    if moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    total, rows = await crud.list_videos(
        owner_id=user.user_id,
        project_id=project_id,
        period_days=period_days,
        month=month,
        social_network=social_network,
        moderation_status=moderation_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return ContentFactoryVideoListResponse(total=total, page=page, page_size=page_size, items=rows)


@content_factory_router.patch("/videos/{video_id}")
async def moderate_video(
    video_id: int,
    payload: ContentFactoryVideoModerationRequest,
    user: AuthUserModel = Depends(_get_user),
):
    ok = await crud.set_video_moderation_for_owner(
        video_id=video_id,
        owner_id=user.user_id,
        moderation_status=payload.moderation_status,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "ok"}


@content_factory_router.delete("/videos/{video_id}")
async def delete_video(video_id: int, user: AuthUserModel = Depends(_get_user)):
    ok = await crud.delete_video_for_owner(video_id=video_id, owner_id=user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "ok"}


def _build_excel(rows: list[dict]) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    sheet = workbook.add_worksheet("Content Factory")

    title_fmt = workbook.add_format({"bold": True, "font_size": 13, "bg_color": "#E7F0FF", "border": 1})
    channel_fmt = workbook.add_format({"bold": True, "bg_color": "#F5F9FF", "border": 1})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#DCEBFF", "border": 1})
    link_fmt = workbook.add_format({"font_color": "#0563C1", "underline": 1, "border": 1})
    cell_fmt = workbook.add_format({"border": 1})
    short_fmt = workbook.add_format({"border": 1, "bg_color": "#FFF4E6"})
    total_fmt = workbook.add_format({"bold": True, "border": 1, "bg_color": "#EAFBEA"})

    sheet.set_column(0, 0, 36)
    sheet.set_column(1, 1, 11)
    sheet.set_column(2, 2, 60)
    sheet.set_column(3, 3, 52)
    sheet.set_column(4, 6, 14)

    row_idx = 0
    sheet.write(row_idx, 0, "Отчет контент-завода по каналам", title_fmt)
    row_idx += 2

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in rows:
        key = ((item.get("channel_title") or "—"), (item.get("channel_url") or ""))
        grouped[key].append(item)

    headers = [
        "Название видео",
        "Тип",
        "Ссылка на видео",
        "Дата публикации",
        "Просмотры",
        "Лайки",
        "Комментарии",
    ]

    for (channel_title, channel_url), channel_rows in grouped.items():
        sheet.write(row_idx, 0, f"Канал: {channel_title}", channel_fmt)
        if channel_url:
            sheet.write_url(row_idx, 2, channel_url, link_fmt, string=channel_url)
        row_idx += 1

        for col_idx, header in enumerate(headers):
            sheet.write(row_idx, col_idx, header, header_fmt)
        row_idx += 1

        total_videos = 0
        total_shorts = 0

        for item in channel_rows:
            is_short = bool(item.get("is_short"))
            row_fmt = short_fmt if is_short else cell_fmt
            video_type = "Шортс" if is_short else "Видео"
            total_shorts += 1 if is_short else 0
            total_videos += 0 if is_short else 1

            sheet.write(row_idx, 0, item.get("title") or "", row_fmt)
            sheet.write(row_idx, 1, video_type, row_fmt)
            if item.get("video_url"):
                sheet.write_url(row_idx, 2, item.get("video_url"), link_fmt, string=item.get("video_url"))
            else:
                sheet.write(row_idx, 2, "", row_fmt)
            sheet.write(row_idx, 3, str(item.get("published_at") or ""), row_fmt)
            sheet.write_number(row_idx, 4, int(item.get("views") or 0), row_fmt)
            sheet.write_number(row_idx, 5, int(item.get("likes") or 0), row_fmt)
            sheet.write_number(row_idx, 6, int(item.get("comments") or 0), row_fmt)
            row_idx += 1

        sheet.write(row_idx, 0, "Итого по каналу", total_fmt)
        sheet.write(row_idx, 1, f"Видео: {total_videos} | Шортс: {total_shorts}", total_fmt)
        row_idx += 2

    workbook.close()
    output.seek(0)
    return output.read()


@content_factory_router.get("/channels/{channel_id}/insights", response_model=ContentFactoryChannelInsightsResponse)
async def get_channel_insights(
    channel_id: int,
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    user: AuthUserModel = Depends(_get_user),
):
    channel = await crud.get_channel_for_owner(channel_id=channel_id, owner_id=user.user_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    data = await crud.get_channel_insights(
        owner_id=user.user_id,
        channel_id=channel_id,
        period_days=period_days,
        month=month,
        start_date=start_date,
        end_date=end_date,
    )
    if not data:
        raise HTTPException(status_code=404, detail="Channel not found")

    return ContentFactoryChannelInsightsResponse(**data)


@content_factory_router.get("/overall-insights", response_model=ContentFactoryOverallInsightsResponse)
async def get_overall_insights_legacy(
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    user: AuthUserModel = Depends(_get_user),
):
    # Backward-compatible endpoint for older frontend builds.
    await _assert_project_exists(project_id=project_id, owner_id=user.user_id)

    data = await crud.get_overall_insights(
        owner_id=user.user_id,
        project_id=project_id,
        period_days=period_days,
        month=month,
        social_network=social_network,
        channel_periods=[],
    )
    return ContentFactoryOverallInsightsResponse(**data)


@content_factory_router.post("/reports/overall-insights", response_model=ContentFactoryOverallInsightsResponse)
async def get_overall_insights(
    payload: ContentFactoryOverallReportRequest,
    user: AuthUserModel = Depends(_get_user),
):
    await _assert_project_exists(project_id=payload.project_id, owner_id=user.user_id)

    data = await crud.get_overall_insights(
        owner_id=user.user_id,
        project_id=payload.project_id,
        period_days=payload.period_days,
        month=payload.month,
        social_network=payload.social_network,
        channel_periods=[item.dict() for item in payload.channel_periods],
    )
    return ContentFactoryOverallInsightsResponse(**data)


@content_factory_router.post("/reports/download")
async def download_report(
    period_days: int = Query(default=30, ge=1, le=3650),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    social_network: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None, ge=1),
    moderation_status: Optional[str] = Query(default="all"),
    payload: Optional[ContentFactoryOverallReportRequest] = None,
    user: AuthUserModel = Depends(_get_user),
):
    effective_period_days = payload.period_days if payload else period_days
    effective_month = payload.month if payload else month
    effective_social_network = payload.social_network if payload else social_network
    effective_project_id = payload.project_id if payload else project_id
    effective_moderation_status = payload.moderation_status if payload else moderation_status

    if moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    if effective_moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    await _assert_project_exists(project_id=effective_project_id, owner_id=user.user_id)

    rows: list[dict] = []
    channel_periods = payload.channel_periods if payload else []
    if channel_periods:
        for item in channel_periods:
            channel = await crud.get_channel_for_owner(channel_id=item.channel_id, owner_id=user.user_id)
            if not channel:
                continue

            _, channel_rows = await crud.list_videos(
                owner_id=user.user_id,
                project_id=effective_project_id,
                period_days=int(item.period_days or effective_period_days),
                month=effective_month,
                social_network=effective_social_network,
                moderation_status=effective_moderation_status,
                sort_by="views",
                sort_order="desc",
                page=1,
                page_size=50000,
            )
            rows.extend([row for row in channel_rows if int(row.get("channel_id") or 0) == item.channel_id])
    else:
        _, rows = await crud.list_videos(
            owner_id=user.user_id,
            project_id=effective_project_id,
            period_days=effective_period_days,
            month=effective_month,
            social_network=effective_social_network,
            moderation_status=effective_moderation_status,
            sort_by="views",
            sort_order="desc",
            page=1,
            page_size=50000,
        )

    report = await crud.create_report_history(
        owner_id=user.user_id,
        period_days=effective_period_days,
        social_network=effective_social_network,
    )

    file_bytes = _build_excel(rows)
    report_id = report["report_id"]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"content_factory_{report_id}_{timestamp}.xlsx"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@content_factory_router.get("/reports/history", response_model=ContentFactoryReportHistoryResponse)
async def report_history(user: AuthUserModel = Depends(_get_user)):
    rows = await crud.list_report_history(owner_id=user.user_id)
    return ContentFactoryReportHistoryResponse(reports=rows)


@content_factory_router.get("/reports/{report_id}/download")
async def download_historical_report(report_id: str, user: AuthUserModel = Depends(_get_user)):
    report = await crud.get_report_for_owner(report_id=report_id, owner_id=user.user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    _, rows = await crud.list_videos(
        owner_id=user.user_id,
        project_id=None,
        period_days=int(report["period_days"]),
        month=None,
        social_network=report.get("social_network"),
        moderation_status="all",
        sort_by="views",
        sort_order="desc",
        page=1,
        page_size=50000,
    )

    file_bytes = _build_excel(rows)
    filename = f"content_factory_report_{report_id}.xlsx"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@content_factory_router.post("/reports/google-sheets/export", response_model=ContentFactoryGoogleSheetsExportResponse)
async def export_report_to_google_sheets(
    payload: ContentFactoryGoogleSheetsExportRequest,
    user: AuthUserModel = Depends(_get_user),
):
    if payload.moderation_status not in {"all", "pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="moderation_status must be one of: all, pending, approved, rejected")

    await _assert_project_exists(project_id=payload.project_id, owner_id=user.user_id)

    collected_rows: list[dict] = []
    page = 1
    remaining = payload.max_rows

    while remaining > 0:
        current_page_size = min(payload.page_size, remaining)
        _, rows = await crud.list_videos(
            owner_id=user.user_id,
            project_id=payload.project_id,
            period_days=payload.period_days,
            month=payload.month,
            social_network=payload.social_network,
            moderation_status=payload.moderation_status,
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

    try:
        if payload.write_mode == "append":
            export_result = append_rows_to_google_sheets(
                spreadsheet_id=payload.spreadsheet_id,
                sheet_name=payload.sheet_name,
                rows=collected_rows,
                header_row=payload.header_row,
                include_provenance=payload.include_provenance,
                prevent_duplicates=payload.prevent_duplicates,
                duplicate_key=payload.duplicate_key,
            )
        else:
            export_result = export_rows_to_google_sheets(
                spreadsheet_id=payload.spreadsheet_id,
                sheet_name=payload.sheet_name,
                rows=collected_rows,
                include_provenance=payload.include_provenance,
                clear_sheet=payload.clear_sheet,
            )
    except GoogleSheetsExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Google Sheets export failed: {exc}") from exc

    note = None
    if len(collected_rows) >= payload.max_rows:
        note = f"Row limit reached: wrote first {payload.max_rows} rows. Increase max_rows to export more."

    return ContentFactoryGoogleSheetsExportResponse(
        status="ok",
        spreadsheet_id=payload.spreadsheet_id,
        sheet_name=payload.sheet_name,
        rows_written=int(export_result["rows_written"]),
        updated_range=str(export_result["updated_range"]),
        updated_rows=int(export_result["updated_rows"]),
        duplicates_skipped=int(export_result.get("duplicates_skipped") or 0),
        note=note,
    )
