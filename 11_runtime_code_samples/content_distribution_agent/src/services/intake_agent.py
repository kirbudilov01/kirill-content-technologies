"""Intake agent: process a new video from OBS/ and create a WORK session."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.models.contracts import IntakeResult, VideoStatus
from content_distribution.services.assessor import assess_video
from content_distribution.services.pdf_generator import generate_timecodes_pdf
from content_distribution.services.screenshots import extract_video_screenshots
from content_distribution.services.smm_local_pack import generate_local_smm_materials
from content_distribution.services.timecodes import build_timecodes
from content_distribution.services.workspace_setup import ensure_local_workspace_folders
from content_distribution.utils.media import get_duration_seconds

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}

_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _ru_date(dt: datetime) -> str:
    return f"{dt.day} {_MONTHS_RU[dt.month - 1]}"


def _make_work_dir(work_root: Path, dt: datetime) -> Path:
    """Create and return a unique session folder like 'WORK/4 мая'."""
    base_name = _ru_date(dt)
    candidate = work_root / base_name
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate
    # Same-day collision → add HH-MM
    candidate = work_root / f"{base_name} {dt.strftime('%H-%M')}"
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _transcribe(video_path: Path, settings: Settings) -> list:
    """Transcribe video with Whisper medium. Returns list[TranscriptSegment]."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return []

    cfg = settings.intake
    device = cfg.device if cfg.device != "auto" else "cpu"
    model = WhisperModel(
        cfg.whisper_model,
        device=device,
        compute_type=cfg.compute_type,
    )

    from content_distribution.models.contracts import TranscriptSegment
    try:
        language = cfg.language.strip() or None
        segments_iter, _ = model.transcribe(
            str(video_path),
            language=language,
            beam_size=3,
            vad_filter=True,
            word_timestamps=False,
        )
        result: list[TranscriptSegment] = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if text:
                result.append(TranscriptSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=text,
                    confidence=1.0,
                ))
        return result
    except Exception:
        return []


def run_intake(video_source: Path, settings: Settings) -> IntakeResult:
    """
    Full intake pipeline for a single video file:
    1. Create WORK/<date> folder
    2. Copy video there
    3. Transcribe (Whisper medium)
    4. Generate timecodes
    5. Assess (status + rating)
    6. Write Timecodes.pdf
    7. Write intake.json summary
    """
    cfg = settings.intake
    now = datetime.now()
    work_root = Path(cfg.work_dir)
    work_dir = _make_work_dir(work_root, now)

    # 1. Copy video
    dest_video = work_dir / video_source.name
    if not dest_video.exists():
        shutil.copy2(video_source, dest_video)

    # 2. Duration
    try:
        duration = get_duration_seconds(dest_video)
    except Exception:
        duration = 0.0

    # 2.1 Local workspace folders (SCREENSHOTS + SMM/<platform>)
    workspace_info = ensure_local_workspace_folders(work_dir)
    screenshots_dir = Path(str(workspace_info["screenshots_dir"]))
    screenshot_files = extract_video_screenshots(dest_video, screenshots_dir, count=4)

    # 3. Transcribe
    segments = _transcribe(dest_video, settings)

    # 4. Timecodes
    timecodes = build_timecodes(
        segments,
        interval_seconds=cfg.timecode_interval_seconds,
        duration_seconds=duration,
    )

    # 5. Assess
    status, rating, assessment = assess_video(
        segments=segments,
        duration_seconds=duration,
        video_filename=video_source.name,
        timecodes=timecodes,
        about_me_dir=cfg.about_me_dir,
        research_dir=cfg.research_dir,
        stream_threshold=cfg.stream_threshold_seconds,
        short_video_threshold=cfg.short_video_threshold_seconds,
    )

    result = IntakeResult(
        work_dir=str(work_dir),
        video_path=str(dest_video),
        timecodes_pdf_path=str(work_dir / "Timecodes.pdf"),
        status=status,
        rating=rating,
        assessment=assessment,
        timecodes=timecodes,
    )

    summary = {
        "video": video_source.name,
        "processed_at": now.isoformat(),
        "duration_seconds": duration,
        "status": status.value,
        "rating": rating,
        "assessment": assessment,
        "timecodes": [tc.model_dump() for tc in timecodes],
        "work_dir": str(work_dir),
        "screenshots": {
            "folder": str(screenshots_dir),
            "count": len(screenshot_files),
            "files": screenshot_files,
        },
        "smm": {
            "root": str(workspace_info["smm_root"]),
            "platform_folders": workspace_info["smm_platforms"],
        },
    }

    # ── Producer Report (SEO.pdf) ────────────────────────────────────────────
    # Генерируем для всего, кроме слабого контента. Для cut_to_clips дополнительно
    # оставляем флаг следующего пайплайна.
    if status != VideoStatus.weak_content:
        try:
            from content_distribution.services.producer_report import generate_producer_report
            from content_distribution.services.shorts_executor import generate_clips_from_plan
            report = generate_producer_report(
                work_dir=work_dir,
                video_filename=video_source.name,
                duration_seconds=duration,
                status=status,
                rating=rating,
                assessment=assessment,
                segments=segments,
                timecodes=timecodes,
                about_me_dir=cfg.about_me_dir,
                research_dir=cfg.research_dir,
                created_at=now,
            )
            result.producer_report_path = report.pdf_path
            # Save producer report data into JSON too
            summary["producer_report"] = {
                "pdf": report.pdf_path,
                "titles": report.titles,
                "tags": report.tags,
                "thumbnail_prompt": report.thumbnail_prompt,
                "thumbnail_path": report.thumbnail_path,
                "shorts_tz_count": len(report.shorts_tz),
            }

            smm_files = generate_local_smm_materials(
                work_dir=work_dir,
                video_filename=video_source.name,
                rating=rating,
                assessment=assessment,
                timecodes=timecodes,
                titles=report.titles,
                description=report.description,
                tags=report.tags,
            )
            summary["smm"]["generated_files"] = smm_files

            # Step 5: create clips in WORK/data/Клипы using shorts TЗ first.
            clips = generate_clips_from_plan(
                settings=settings,
                work_dir=work_dir,
                input_video_path=dest_video,
                duration_seconds=duration,
                segments=segments,
                timecodes=timecodes,
                shorts_tz=report.shorts_tz,
            )
            summary["clips"] = {
                "status": "completed",
                "count": len(clips),
                "folder": str(work_dir / "data" / "Клипы"),
                "files": clips,
            }
        except Exception as exc:
            # Producer report is non-blocking — log and continue
            summary["producer_report_error"] = str(exc)

    # Always create baseline local SMM drafts if producer report did not fill them.
    if not summary["smm"].get("generated_files"):
        baseline_files = generate_local_smm_materials(
            work_dir=work_dir,
            video_filename=video_source.name,
            rating=rating,
            assessment=assessment,
            timecodes=timecodes,
            titles=None,
            description=None,
            tags=None,
        )
        summary["smm"]["generated_files"] = baseline_files

    if status == VideoStatus.cut_to_clips:
        # Помечаем в JSON — этот стрим ждёт пайплайна нарезки на видео
        summary["next_pipeline"] = "cut_to_video"

    # 6. Generate PDF
    generate_timecodes_pdf(
        output_path=work_dir / "Timecodes.pdf",
        video_filename=video_source.name,
        duration_seconds=duration,
        result=result,
        created_at=now,
    )

    # 7. Save JSON summary
    (work_dir / "intake.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return result
