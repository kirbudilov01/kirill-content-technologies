from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class OutlierSearchRequest(BaseModel):
    keyword: str = Field(min_length=1)
    language: str = Field(default="ru", min_length=2, max_length=8)
    region_code: str = Field(default="US", min_length=2, max_length=8)
    lookback_hours: int = Field(default=72, ge=6, le=720)
    max_results: int = Field(default=25, ge=5, le=120)
    content_type: Literal["all", "shorts", "long"] = "all"
    candidate_pool: int = Field(default=600, ge=120, le=1200)

    class Config:
        schema_extra = {
            "example": {
                "keyword": "ai tools",
                "language": "en",
                "region_code": "US",
                "lookback_hours": 72,
                "max_results": 25,
                "content_type": "all",
                "candidate_pool": 600,
            }
        }


class OutlierVideoResult(BaseModel):
    video_id: str
    title: str
    url: str
    channel_id: str
    channel_title: str
    published_at: str
    thumbnail: Optional[str] = None
    duration_seconds: int
    content_type: str
    views: int
    likes: int
    comments: int
    subscribers: int
    baseline_views: int
    outlier_score: float
    quality_score: float
    confidence_score: float
    engagement_rate: float
    topic_cluster: str
    relative_multiplier: float
    velocity_per_hour: float
    views_delta_24h: int = 0
    momentum_score: float = 0.0
    reason: str


class OutlierSearchResponse(BaseModel):
    videos: List[OutlierVideoResult]
    total_count: int
    searches_remaining: int
    searches_limit: int


class OutlierSearchStats(BaseModel):
    searches_remaining: int
    searches_limit: int
    reset_date: str


class OutlierTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    searches_remaining: int
    searches_limit: int


class OutlierTopicInsight(BaseModel):
    topic_cluster: str
    videos_count: int
    avg_outlier_score: float
    avg_quality_score: float
    avg_momentum: float
    last_seen_at: datetime


class OutlierInsightsResponse(BaseModel):
    insights: List[OutlierTopicInsight]


class OutlierSearchHistoryItem(BaseModel):
    run_id: int
    keyword: str
    status: str
    total_results: int
    language: Optional[str] = None
    region_code: Optional[str] = None
    created_at: datetime


class OutlierSearchHistoryResponse(BaseModel):
    history: List[OutlierSearchHistoryItem]
