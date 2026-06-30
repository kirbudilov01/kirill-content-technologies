from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from content_distribution.models.contracts import SourceKind
from content_distribution.utils.media import MediaError


@dataclass
class IngestedSource:
    video_path: Path
    subtitle_path: Path | None


def infer_source_kind(source: str) -> SourceKind:
    if source.startswith("http://") or source.startswith("https://"):
        return SourceKind.youtube
    return SourceKind.local


def ingest_source(source: str, temp_dir: str, job_id: str) -> IngestedSource:
    kind = infer_source_kind(source)
    temp_root = Path(temp_dir) / job_id
    temp_root.mkdir(parents=True, exist_ok=True)

    if kind == SourceKind.local:
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            raise MediaError(f"Input file not found: {source_path}")
        video_copy = temp_root / f"input{source_path.suffix or '.mp4'}"
        shutil.copy2(source_path, video_copy)
        sidecar_srt = source_path.with_suffix(".srt")
        subtitle_path = sidecar_srt if sidecar_srt.exists() else None
        return IngestedSource(video_path=video_copy, subtitle_path=subtitle_path)

    output_template = str(temp_root / "source.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "--write-auto-sub",
        "--convert-subs",
        "srt",
        "--sub-langs",
        "ru.*,en.*",
        "-o",
        output_template,
        source,
    ]

    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode != 0:
        raise MediaError(
            f"yt-dlp failed ({proc.returncode})\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
        )

    mp4_files = sorted(temp_root.glob("source*.mp4"))
    if not mp4_files:
        raise MediaError("yt-dlp finished but no video file was produced")
    subtitle_candidates = sorted(temp_root.glob("source*.srt"))
    subtitle_path = subtitle_candidates[0] if subtitle_candidates else None
    return IngestedSource(video_path=mp4_files[0], subtitle_path=subtitle_path)
