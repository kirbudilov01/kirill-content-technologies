from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, ConfigDict

SocialNetwork = Literal["youtube", "instagram", "tiktok", "x", "vk", "ok", "rutube", "likee", "dzen"]
ModerationStatus = Literal["pending", "approved", "rejected"]
PlatformCollectionMethod = Literal["youtube_api", "external_api", "http_scraper", "browser_scraper"]
PlatformStatus = Literal["live", "credentials", "planned"]


class ContentFactoryChannelCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "project_id": 12,
            "social_network": "youtube",
            "channel_url": "https://www.youtube.com/@TrendVi",
            "channel_title": "TrendVi",
            "category": "education",
        }
    })
    
    project_id: Optional[int] = None
    social_network: SocialNetwork
    channel_url: HttpUrl
    channel_title: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=120)


class ContentFactoryChannelOut(BaseModel):
    channel_id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    owner_id: int
    social_network: SocialNetwork
    channel_url: str
    channel_title: Optional[str] = None
    channel_external_id: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    preferred_period_preset: Optional[str] = None
    preferred_period_days: Optional[int] = None
    preferred_start_date: Optional[date] = None
    preferred_end_date: Optional[date] = None
    subscribers_count: Optional[int] = None
    last_sync_video_count: Optional[int] = None
    last_sync_coverage_published_at: Optional[int] = None
    last_sync_coverage_views: Optional[int] = None
    last_sync_coverage_likes: Optional[int] = None
    last_sync_coverage_comments: Optional[int] = None
    last_sync_retry_count: Optional[int] = None


class ContentFactoryChannelListResponse(BaseModel):
    channels: list[ContentFactoryChannelOut]


class ContentFactoryProjectCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "US creator benchmark",
            "description": "Мониторинг конкурентных каналов в США",
            "social_network": "youtube",
        }
    })
    
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    social_network: SocialNetwork = "youtube"


class ContentFactoryProjectOut(BaseModel):
    project_id: int
    owner_id: int
    name: str
    description: Optional[str] = None
    social_network: SocialNetwork
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_collection_at: Optional[datetime] = None
    channels_count: int = 0


class ContentFactoryProjectListResponse(BaseModel):
    projects: list[ContentFactoryProjectOut]


class ContentFactoryPlatformOut(BaseModel):
    key: SocialNetwork
    label: str
    collection_method: PlatformCollectionMethod
    status: PlatformStatus
    parser_kind: str
    requires_credentials: bool = False
    notes: str = ""


class ContentFactoryPlatformListResponse(BaseModel):
    platforms: list[ContentFactoryPlatformOut]


class SyncRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "period_days": 30,
            "start_date": "2026-03-01",
            "end_date": "2026-03-24",
        }
    })
    
    period_days: int = Field(default=30, ge=1, le=3650)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ContentFactoryChannelPeriodSelection(BaseModel):
    channel_id: int = Field(ge=1)
    period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ContentFactoryChannelPeriodUpdateRequest(BaseModel):
    preset: Optional[Literal["7d", "30d", "custom"]] = None
    period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ContentFactoryOverallReportRequest(BaseModel):
    project_id: Optional[int] = Field(default=None, ge=1)
    period_days: int = Field(default=30, ge=1, le=3650)
    month: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    social_network: Optional[str] = None
    moderation_status: Optional[str] = "all"
    channel_periods: list[ContentFactoryChannelPeriodSelection] = Field(default_factory=list)


class ContentFactoryVideoRow(BaseModel):
    video_id: int
    channel_id: int
    social_network: SocialNetwork
    channel_title: Optional[str] = None
    channel_url: str
    video_external_id: Optional[str] = None
    video_url: str
    title: str
    published_at: Optional[datetime] = None
    captured_at: datetime
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    duration_seconds: Optional[int] = None
    is_short: bool = False
    source: Optional[str] = None
    recovery_applied: bool = False
    recovery_source: Optional[str] = None
    recovered_fields: list[str] = Field(default_factory=list)
    moderation_status: ModerationStatus = "pending"
    moderation_updated_at: Optional[datetime] = None


class ContentFactoryVideoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ContentFactoryVideoRow]


class ContentFactoryReportHistoryItem(BaseModel):
    report_id: str
    owner_id: int
    period_days: int = Field(ge=1, le=3650)
    social_network: Optional[SocialNetwork] = None
    created_at: datetime


class ContentFactoryReportHistoryResponse(BaseModel):
    reports: list[ContentFactoryReportHistoryItem]


class ContentFactoryOverviewStats(BaseModel):
    total_channels: int
    total_videos: int
    total_views: int
    by_social_network: dict[str, dict[str, int]]


class ContentFactorySyncResponse(BaseModel):
    status: str
    task_id: str


class ContentFactoryTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict[str, Any]] = None


class ContentFactoryProjectSyncExportRequest(BaseModel):
    spreadsheet_id: str = Field(min_length=10, max_length=255)
    sheet_name: str = Field(default="Content Factory Export", min_length=1, max_length=120)
    period_days: int = Field(default=30, ge=1, le=3650)
    social_network: Optional[str] = None
    moderation_status: Optional[str] = "all"
    include_provenance: bool = True
    clear_sheet: bool = False
    write_mode: Literal["replace", "append"] = "append"
    header_row: int = Field(default=38, ge=1, le=10000)
    prevent_duplicates: bool = True
    duplicate_key: str = Field(default="video_url", min_length=2, max_length=80)
    page_size: int = Field(default=1000, ge=100, le=5000)
    max_rows: int = Field(default=20000, ge=100, le=100000)


class ContentFactoryChannelPeriodStat(BaseModel):
    channel_id: int
    channel_title: Optional[str] = None
    channel_url: str
    total_videos: int = 0
    total_shorts: int = 0
    total_views: int = 0
    last_published_at: Optional[datetime] = None


class ContentFactoryChannelStatsResponse(BaseModel):
    period_days: Optional[int] = None
    month: Optional[str] = None
    items: list[ContentFactoryChannelPeriodStat]


class ContentFactoryInsightVideo(BaseModel):
    video_id: int
    title: str
    video_url: str
    views: int
    likes: int
    comments: int
    is_short: bool
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    recovery_applied: bool = False
    recovery_source: Optional[str] = None
    recovered_fields: list[str] = Field(default_factory=list)
    engagement_rate: float = 0.0
    outlier_score: float = 0.0
    explanation: Optional[str] = None


class ContentFactoryChannelInsightsResponse(BaseModel):
    channel_id: int
    channel_title: Optional[str] = None
    channel_url: str
    subscribers_count: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_videos: int = 0
    total_shorts: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    top_outlier_video: Optional[ContentFactoryInsightVideo] = None
    most_discussed_video: Optional[ContentFactoryInsightVideo] = None
    videos: list[ContentFactoryInsightVideo] = Field(default_factory=list)


class ContentFactoryOverallInsightsResponse(BaseModel):
    total_channels: int = 0
    total_videos: int = 0
    total_shorts: int = 0
    total_views: int = 0
    most_effective_channel_id: Optional[int] = None
    most_effective_channel_title: Optional[str] = None
    most_effective_channel_url: Optional[str] = None
    most_effective_channel_successful_outliers: int = 0
    channels: list[dict[str, Any]] = Field(default_factory=list)


class ContentFactoryVideoModerationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "moderation_status": "approved",
        }
    })
    
    moderation_status: ModerationStatus


class ContentFactoryGoogleSheetsExportRequest(BaseModel):
    spreadsheet_id: str = Field(min_length=10, max_length=255)
    sheet_name: str = Field(default="Content Factory Export", min_length=1, max_length=120)
    period_days: int = Field(default=30, ge=1, le=3650)
    month: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    social_network: Optional[str] = None
    project_id: Optional[int] = Field(default=None, ge=1)
    moderation_status: Optional[str] = "all"
    include_provenance: bool = True
    clear_sheet: bool = False
    write_mode: Literal["replace", "append"] = "append"
    header_row: int = Field(default=38, ge=1, le=10000)
    prevent_duplicates: bool = True
    duplicate_key: str = Field(default="video_url", min_length=2, max_length=80)
    page_size: int = Field(default=1000, ge=100, le=5000)
    max_rows: int = Field(default=20000, ge=100, le=100000)


class ContentFactoryGoogleSheetsExportResponse(BaseModel):
    status: str
    spreadsheet_id: str
    sheet_name: str
    rows_written: int
    updated_range: str
    updated_rows: int
    duplicates_skipped: int = 0
    note: Optional[str] = None


class ContentFactoryVideoPayload(BaseModel):
    video_external_id: Optional[str] = None
    video_url: str
    title: str
    published_at: Optional[datetime] = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    duration_seconds: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)
