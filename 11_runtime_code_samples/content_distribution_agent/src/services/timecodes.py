"""Generate structured timecode entries from a transcript."""
from __future__ import annotations

import re
from collections import Counter

from content_distribution.models.contracts import TimecodeEntry, TranscriptSegment

# Phrases that signal a topic transition / new chapter
_TRANSITION_PHRASES = [
    "теперь", "итак", "следующий", "следующая", "перейдем", "перейдём",
    "поговорим", "давайте", "далее", "продолжим", "важно отметить",
    "хочу рассказать", "хочу показать", "расскажу", "покажу",
    "now let's", "next", "let me", "moving on", "so,", "alright",
]

_STOPWORDS = {
    "и", "в", "на", "что", "как", "это", "для", "не", "с", "по", "из",
    "или", "но", "а", "же", "уже", "то", "так", "всё", "всего", "очень",
    "the", "and", "for", "that", "this", "with", "from", "you", "are",
}


def _seconds_to_ts(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _extract_title(segments: list[TranscriptSegment]) -> str:
    """Extract a short title from a group of segments using keyword frequency."""
    if not segments:
        return "Фрагмент"
    full_text = " ".join(s.text for s in segments)
    # take the first sentence-like chunk as title hint
    first_sentence = re.split(r"[.!?]", full_text.strip())[0].strip()
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77].rsplit(" ", 1)[0] + "…"
    return first_sentence or "Фрагмент"


def _is_transition(text: str) -> bool:
    lower = text.lower().strip()
    for phrase in _TRANSITION_PHRASES:
        if lower.startswith(phrase):
            return True
    return False


def build_timecodes(
    segments: list[TranscriptSegment],
    interval_seconds: int = 300,
    duration_seconds: float = 0.0,
) -> list[TimecodeEntry]:
    """
    Build timecode entries from transcript segments.

    Strategy:
    - Group segments into blocks of roughly `interval_seconds`.
    - Also split on strong topic-transition phrases.
    - Each block → one TimecodeEntry.
    """
    if not segments:
        return []

    entries: list[TimecodeEntry] = []
    current_block: list[TranscriptSegment] = []
    block_start = segments[0].start

    for seg in segments:
        is_new_block = (
            current_block
            and (seg.start - block_start >= interval_seconds)
        )
        is_transition = current_block and _is_transition(seg.text)

        if is_new_block or is_transition:
            title = _extract_title(current_block)
            desc_text = " ".join(s.text for s in current_block)
            if len(desc_text) > 200:
                desc_text = desc_text[:197] + "…"
            entries.append(TimecodeEntry(
                timestamp=_seconds_to_ts(block_start),
                title=title,
                description=desc_text,
            ))
            current_block = [seg]
            block_start = seg.start
        else:
            current_block.append(seg)

    # Flush last block
    if current_block:
        title = _extract_title(current_block)
        desc_text = " ".join(s.text for s in current_block)
        if len(desc_text) > 200:
            desc_text = desc_text[:197] + "…"
        entries.append(TimecodeEntry(
            timestamp=_seconds_to_ts(block_start),
            title=title,
            description=desc_text,
        ))

    return entries
