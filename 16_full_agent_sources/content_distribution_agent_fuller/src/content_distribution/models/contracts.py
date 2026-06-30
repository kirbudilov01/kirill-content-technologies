from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    youtube = "youtube"
    local = "local"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float = 1.0


class HighlightCandidate(BaseModel):
    start: float
    end: float
    score: float
    reason: str


class ClipArtifact(BaseModel):
    id: str
    start: float
    end: float
    duration: float
    score: float
    reason: str
    output_path: str


class CostMetrics(BaseModel):
    llm_calls: int = 0
    transcription_calls: int = 0
    estimated_tokens: int = 0


class JobInput(BaseModel):
    source: str
    source_kind: SourceKind


class JobResult(BaseModel):
    clips: list[ClipArtifact] = Field(default_factory=list)
    highlights_path: Optional[str] = None
    subtitles_path: Optional[str] = None


class PipelineJob(BaseModel):
    id: str
    created_at: datetime
    status: JobStatus
    input: JobInput
    source_video_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    errors: list[str] = Field(default_factory=list)
    costs: CostMetrics = Field(default_factory=CostMetrics)
    result: JobResult = Field(default_factory=JobResult)

    def output_dir(self, root: str | Path) -> Path:
        return Path(root) / self.id


# ---------------------------------------------------------------------------
# Intake agent models
# ---------------------------------------------------------------------------

class VideoStatus(str, Enum):
    ready_to_post = "ГОТОВО_К_ПОСТИНГУ"
    cut_to_clips = "РЕЗАТЬ_НА_КЛИПЫ"
    ready_as_video = "ГОТОВО_КАК_ВИДЕО"
    weak_content = "СЛАБЫЙ_КОНТЕНТ"


class TimecodeEntry(BaseModel):
    timestamp: str   # "00:05:30"
    title: str
    description: str = ""


class IntakeResult(BaseModel):
    work_dir: str
    video_path: str
    timecodes_pdf_path: str
    status: VideoStatus
    rating: int          # 1–10
    assessment: str
    timecodes: list[TimecodeEntry] = Field(default_factory=list)
    producer_report_path: Optional[str] = None   # путь к SEO.pdf если сгенерирован


class ProducerReport(BaseModel):
    titles: list[str] = Field(default_factory=list)
    thumbnail_prompt: str = ""
    thumbnail_path: Optional[str] = None          # путь к файлу превью если сгенерировано
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    shorts_tz: list[str] = Field(default_factory=list)  # ТЗ на каждый шортс
    pdf_path: str = ""
