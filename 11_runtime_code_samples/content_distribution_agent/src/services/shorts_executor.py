from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.models.contracts import TimecodeEntry, TranscriptSegment
from content_distribution.services.renderer import render_clip
from content_distribution.services.smart_moments_agent import get_smart_shorts_plans
from content_distribution.utils.srt import SrtItem, write_srt

_CLIP_DIR_REL = Path("data") / "Клипы"


def _to_seconds(value: str) -> float | None:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = [int(p) for p in parts]
    except ValueError:
        return None
    return float(h * 3600 + m * 60 + s)


def _segments_to_srt_items(segments: list[TranscriptSegment]) -> list[SrtItem]:
    items: list[SrtItem] = []
    for idx, seg in enumerate(segments, start=1):
        text = (seg.text or "").strip()
        if not text:
            continue
        items.append(SrtItem(index=idx, start=seg.start, end=seg.end, text=text))
    return items


def _extract_ranges_from_shorts_tz(shorts_tz: list[str], default_len: float = 60.0) -> list[tuple[float, float, str]]:
    ranges: list[tuple[float, float, str]] = []
    for idx, block in enumerate(shorts_tz, start=1):
        ts = re.findall(r"\b\d{2}:\d{2}:\d{2}\b", block)
        if not ts:
            continue
        start = _to_seconds(ts[0])
        if start is None:
            continue
        if len(ts) >= 2:
            end = _to_seconds(ts[1]) or (start + default_len)
        else:
            end = start + default_len
        if end <= start:
            end = start + default_len
        ranges.append((start, end, f"shorts_tz_{idx:02d}"))
    return ranges


def _extract_ranges_from_timecodes(timecodes: list[TimecodeEntry], default_len: float = 60.0) -> list[tuple[float, float, str]]:
    ranges: list[tuple[float, float, str]] = []
    for idx, tc in enumerate(timecodes, start=1):
        start = _to_seconds(tc.timestamp)
        if start is None:
            continue
        ranges.append((start, start + default_len, f"timecode_{idx:02d}"))
    return ranges


def _load_context_text(directory: Path, max_chars: int = 2400) -> str:
    if not directory.exists() or not directory.is_dir():
        return ""
    chunks: list[str] = []
    total = 0
    for f in sorted(directory.iterdir()):
        if not f.is_file() or f.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not txt:
            continue
        chunks.append(txt)
        total += len(txt)
        if total >= max_chars:
            break
    return "\n\n".join(chunks)[:max_chars]


def _normalize_fragment(
    start: float,
    end: float,
    duration_seconds: float,
    min_len: float,
    max_len: float,
) -> tuple[float, float] | None:
    clip_start = max(0.0, start)
    clip_end = min(duration_seconds, end)
    clip_len = clip_end - clip_start
    if clip_len < min_len:
        clip_end = min(duration_seconds, clip_start + min_len)
        clip_len = clip_end - clip_start
    if clip_len > max_len:
        clip_end = clip_start + max_len
    if clip_end <= clip_start:
        return None
    return clip_start, clip_end


def _concat_segments(segment_paths: list[Path], output_path: Path, settings: Settings) -> None:
    if not segment_paths:
        raise ValueError("No segments to concatenate")
    if len(segment_paths) == 1:
        shutil.copy2(segment_paths[0], output_path)
        return

    list_path = output_path.with_suffix(".concat.txt")
    list_path.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in segment_paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c:v",
        settings.render.video_codec,
        "-c:a",
        settings.render.audio_codec,
        "-preset",
        settings.render.preset,
        "-crf",
        str(settings.render.crf),
        str(output_path),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {proc.stderr[-800:]}")


def _dedupe_and_limit(
    ranges: list[tuple[float, float, str]],
    max_items: int,
    min_len: float,
    max_len: float,
    duration_seconds: float,
) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    seen: set[tuple[int, int]] = set()
    for start, end, label in ranges:
        clip_start = max(0.0, start)
        clip_end = min(duration_seconds, end)
        clip_len = clip_end - clip_start
        if clip_len < min_len:
            clip_end = min(duration_seconds, clip_start + min_len)
            clip_len = clip_end - clip_start
        if clip_len > max_len:
            clip_end = clip_start + max_len
        if clip_end <= clip_start:
            continue
        key = (int(clip_start), int(clip_end))
        if key in seen:
            continue
        seen.add(key)
        out.append((clip_start, clip_end, label))
        if len(out) >= max_items:
            break
    return out


def generate_clips_from_plan(
    settings: Settings,
    work_dir: Path,
    input_video_path: Path,
    duration_seconds: float,
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    shorts_tz: list[str],
    max_items: int = 8,
) -> list[str]:
    """Render smart multi-fragment shorts into WORK/data/Клипы."""
    clips_dir = work_dir / _CLIP_DIR_REL
    clips_dir.mkdir(parents=True, exist_ok=True)

    srt_path = work_dir / "data" / "transcript.srt"
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    write_srt(_segments_to_srt_items(segments), srt_path)

    intake_cfg = settings.intake
    about_ctx = _load_context_text(Path(intake_cfg.about_me_dir))
    research_ctx = _load_context_text(Path(intake_cfg.research_dir) / "DATA") + "\n\n" + _load_context_text(Path(intake_cfg.research_dir) / "SCRIPTS")

    smart_plans: list[dict] = []
    if intake_cfg.smart_moments_enabled:
        smart_plans = get_smart_shorts_plans(
            segments=segments,
            timecodes=timecodes,
            shorts_tz=shorts_tz,
            duration_seconds=duration_seconds,
            about_me_context=about_ctx,
            research_context=research_ctx,
            model=intake_cfg.smart_moments_model,
            local_only=bool(intake_cfg.smart_moments_local_only),
            shorts_count=min(max_items, max(1, intake_cfg.smart_shorts_count)),
            target_seconds=max(20, intake_cfg.smart_short_target_seconds),
            fragment_min_seconds=max(3, intake_cfg.smart_fragment_min_seconds),
            fragment_max_seconds=max(intake_cfg.smart_fragment_min_seconds + 1, intake_cfg.smart_fragment_max_seconds),
        )

    if not smart_plans:
        # fallback to older single-range logic
        prioritized = _extract_ranges_from_shorts_tz(shorts_tz)
        fallback = _extract_ranges_from_timecodes(timecodes)
        ranges = _dedupe_and_limit(
            prioritized + fallback,
            max_items=max_items,
            min_len=float(settings.app.min_clip_seconds),
            max_len=float(settings.app.max_clip_seconds),
            duration_seconds=duration_seconds,
        )
        smart_plans = [
            {
                "title": label,
                "fragments": [
                    {
                        "start": f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{int(start % 60):02d}",
                        "end": f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{int(end % 60):02d}",
                        "reason": label,
                    }
                ],
            }
            for (start, end, label) in ranges
        ]

    temp_dir = clips_dir / "_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    manifest_shorts: list[dict] = []

    for idx, plan in enumerate(smart_plans[:max_items], start=1):
        title = str(plan.get("title") or f"short_{idx:02d}")
        fragments = plan.get("fragments") or []
        segment_files: list[Path] = []
        segment_meta: list[dict] = []

        for frag_idx, frag in enumerate(fragments, start=1):
            start = _to_seconds(str(frag.get("start", "")))
            end = _to_seconds(str(frag.get("end", "")))
            if start is None or end is None:
                continue
            normalized = _normalize_fragment(
                start=start,
                end=end,
                duration_seconds=duration_seconds,
                min_len=float(settings.intake.smart_fragment_min_seconds),
                max_len=float(settings.intake.smart_fragment_max_seconds),
            )
            if not normalized:
                continue
            clip_start, clip_end = normalized
            seg_path = temp_dir / f"short_{idx:02d}_seg_{frag_idx:02d}.mp4"
            render_clip(
                settings=settings,
                input_video_path=input_video_path,
                output_clip_path=seg_path,
                subtitles_path=srt_path,
                start=clip_start,
                end=clip_end,
            )
            segment_files.append(seg_path)
            segment_meta.append(
                {
                    "start": clip_start,
                    "end": clip_end,
                    "reason": str(frag.get("reason", "")),
                }
            )

        if not segment_files:
            continue

        out_path = clips_dir / f"short_{idx:02d}.mp4"
        _concat_segments(segment_files, out_path, settings)
        created.append(str(out_path))
        manifest_shorts.append(
            {
                "title": title,
                "output": str(out_path),
                "fragments": segment_meta,
            }
        )

    manifest_path = clips_dir / "clips_manifest.json"
    manifest_path.write_text(
        json.dumps({"clips": created, "shorts": manifest_shorts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    return created
