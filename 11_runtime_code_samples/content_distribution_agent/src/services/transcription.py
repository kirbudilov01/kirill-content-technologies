from __future__ import annotations

from pathlib import Path

from content_distribution.config import Settings
from content_distribution.models.contracts import TranscriptSegment
from content_distribution.utils.media import get_duration_seconds
from content_distribution.utils.srt import SrtItem, parse_srt, write_srt


def _srt_to_segments(items: list[SrtItem]) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(start=item.start, end=item.end, text=item.text, confidence=1.0)
        for item in items
        if item.text.strip()
    ]


def _build_fallback_transcript(duration: float) -> list[TranscriptSegment]:
    # Fallback guarantees pipeline continuity if transcription is unavailable.
    step = 6.0
    segments: list[TranscriptSegment] = []
    current = 0.0
    i = 1
    while current < duration:
        end = min(duration, current + step)
        segments.append(
            TranscriptSegment(
                start=current,
                end=end,
                text=f"Сегмент {i}: ключевая мысль фрагмента",
                confidence=0.4,
            )
        )
        i += 1
        current = end
    return segments


def _transcribe_with_faster_whisper(
    settings: Settings,
    video_path: str | Path,
) -> list[TranscriptSegment] | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None

    model = WhisperModel(
        settings.transcription.model_size,
        device=settings.transcription.device,
        compute_type=settings.transcription.compute_type,
    )

    try:
        language = settings.transcription.language
        if isinstance(language, str):
            language = language.strip() or None
        segments, _info = model.transcribe(
            str(video_path),
            language=language,
            beam_size=max(1, settings.transcription.beam_size),
            vad_filter=settings.transcription.vad_filter,
            word_timestamps=True,
        )
    except Exception:
        return None

    parsed: list[TranscriptSegment] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        parsed.append(
            TranscriptSegment(
                start=float(segment.start),
                end=float(segment.end),
                text=text,
                confidence=1.0,
            )
        )

    if not parsed:
        return None
    return parsed


def produce_transcript(
    settings: Settings,
    video_path: str | Path,
    subtitle_hint: str | Path | None,
    output_srt_path: str | Path,
) -> list[TranscriptSegment]:
    if subtitle_hint:
        subtitle_path = Path(subtitle_hint)
        if subtitle_path.exists():
            items = parse_srt(subtitle_path)
            write_srt(items, output_srt_path)
            return _srt_to_segments(items)

    if settings.transcription.fallback_srt_path:
        fallback_path = Path(settings.transcription.fallback_srt_path)
        if fallback_path.exists():
            items = parse_srt(fallback_path)
            write_srt(items, output_srt_path)
            return _srt_to_segments(items)

    if settings.transcription.mode in {"faster_whisper", "faster_whisper_with_fallback"}:
        fw_segments = _transcribe_with_faster_whisper(settings, video_path)
        if fw_segments:
            fw_items = [
                SrtItem(index=i + 1, start=seg.start, end=seg.end, text=seg.text)
                for i, seg in enumerate(fw_segments)
            ]
            write_srt(fw_items, output_srt_path)
            return fw_segments

    duration = get_duration_seconds(video_path)
    segments = _build_fallback_transcript(duration)
    items = [
        SrtItem(index=i + 1, start=seg.start, end=seg.end, text=seg.text)
        for i, seg in enumerate(segments)
    ]
    write_srt(items, output_srt_path)
    return segments
