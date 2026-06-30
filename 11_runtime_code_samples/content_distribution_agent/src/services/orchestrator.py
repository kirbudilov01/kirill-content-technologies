from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.models.contracts import (
    ClipArtifact,
    JobInput,
    JobStatus,
    PipelineJob,
    SourceKind,
)
from content_distribution.services.highlight_selector import select_highlights
from content_distribution.services.ingestion import ingest_source, infer_source_kind
from content_distribution.services.renderer import render_clip
from content_distribution.services.transcription import produce_transcript
from content_distribution.utils.media import get_duration_seconds


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_pipeline(settings: Settings, source: str) -> PipelineJob:
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    source_kind = infer_source_kind(source)

    job = PipelineJob(
        id=job_id,
        created_at=datetime.now(timezone.utc),
        status=JobStatus.running,
        input=JobInput(source=source, source_kind=SourceKind(source_kind.value)),
    )

    output_dir = job.output_dir(settings.app.output_dir)
    clips_dir = output_dir / "clips"
    output_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    try:
        ingested = ingest_source(source, settings.app.temp_dir, job_id)
        job.source_video_path = str(ingested.video_path)

        duration = get_duration_seconds(ingested.video_path)
        job.duration_seconds = duration

        subtitles_path = output_dir / "subtitles.srt"
        transcript = produce_transcript(
            settings=settings,
            video_path=ingested.video_path,
            subtitle_hint=ingested.subtitle_path,
            output_srt_path=subtitles_path,
        )
        job.costs.transcription_calls += 1

        highlights = select_highlights(settings, transcript, duration)
        highlights_json = [candidate.model_dump() for candidate in highlights]
        highlights_path = output_dir / "highlights.json"
        _write_json(highlights_path, {"highlights": highlights_json})

        artifacts: list[ClipArtifact] = []
        for index, candidate in enumerate(highlights, start=1):
            clip_name = f"clip_{index:02d}_{int(candidate.start)}_{int(candidate.end)}.mp4"
            clip_path = clips_dir / clip_name
            render_clip(
                settings=settings,
                input_video_path=ingested.video_path,
                output_clip_path=clip_path,
                subtitles_path=subtitles_path,
                start=candidate.start,
                end=candidate.end,
            )
            artifacts.append(
                ClipArtifact(
                    id=f"clip-{index:02d}",
                    start=candidate.start,
                    end=candidate.end,
                    duration=round(candidate.end - candidate.start, 3),
                    score=round(candidate.score, 4),
                    reason=candidate.reason,
                    output_path=str(clip_path),
                )
            )

        job.result.clips = artifacts
        job.result.highlights_path = str(highlights_path)
        job.result.subtitles_path = str(subtitles_path)
        job.status = JobStatus.completed
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.failed
        job.errors.append(str(exc))

    job_path = output_dir / "job.json"
    _write_json(job_path, job.model_dump(mode="json"))
    return job
