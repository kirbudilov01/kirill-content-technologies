from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.models.contracts import HighlightCandidate, TranscriptSegment


@dataclass
class SelectorContext:
    min_clip_seconds: int
    max_clip_seconds: int
    max_clips: int
    max_candidates: int
    keyword_boost: list[str]
    intro_penalty_phrases: list[str]


_STOPWORDS = {
    "the", "and", "for", "you", "that", "this", "with", "from", "have", "your", "are", "was",
    "but", "not", "into", "about", "when", "then", "they", "what", "how", "why", "just", "can",
    "как", "что", "это", "для", "или", "чтобы", "когда", "потом", "очень", "просто", "можно", "будет",
    "если", "всего", "только", "вот", "там", "тут", "сейчас", "давайте", "короче", "типа", "значит",
}

_HOOK_WORDS = {
    "ошибка", "секрет", "важно", "результат", "метод", "система", "почему", "как", "лучше", "быстрее",
    "problem", "mistake", "result", "secret", "system", "method", "framework", "fix", "important",
}

_LOW_SIGNAL_PHRASES = {
    "всем привет", "в этом видео", "подпишись", "ставь лайк", "мы продолжаем", "ну что", "итак",
    "hello everyone", "in this video", "subscribe", "like this video",
}


def _tokenize(text: str) -> list[str]:
    return [
        tok for tok in re.findall(r"[A-Za-zА-Яа-я0-9_]{3,}", text.lower())
        if tok not in _STOPWORDS
    ]


def _text_score(text: str, keywords: list[str]) -> float:
    score = 0.0
    stripped = text.strip()
    length = len(stripped)
    score += min(1.0, length / 120)
    score += 0.25 * stripped.count("!")
    score += 0.2 * stripped.count("?")
    lowered = stripped.lower()
    for keyword in keywords:
        if keyword.lower() in lowered:
            score += 0.5
    return score


def _engagement_score(text: str, keywords: list[str], global_counts: Counter[str]) -> float:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0

    token_count = len(tokens)
    unique_ratio = len(set(tokens)) / token_count

    # Informative words are rarer across transcript and usually carry the point.
    rare_hits = sum(1 for t in tokens if global_counts.get(t, 0) <= 2)
    rare_ratio = rare_hits / token_count

    keyword_hits = 0
    lowered = text.lower()
    for word in keywords:
        if word.lower() in lowered:
            keyword_hits += 1
    for hook_word in _HOOK_WORDS:
        if hook_word in lowered:
            keyword_hits += 1

    score = 0.0
    score += min(1.0, token_count / 45.0) * 0.45
    score += min(1.0, unique_ratio / 0.75) * 0.35
    score += min(1.0, rare_ratio / 0.35) * 0.35
    score += min(1.0, keyword_hits / 4.0) * 0.7
    score += 0.12 * text.count("?")
    score += 0.10 * text.count("!")
    if re.search(r"\d", text):
        score += 0.15
    return score


def _penalty_score(text: str, intro_penalties: list[str]) -> float:
    lowered = text.lower()
    penalty = 0.0
    for phrase in intro_penalties:
        if phrase.lower() in lowered:
            penalty += 0.35

    words = [w for w in lowered.split() if w]
    if words:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.45:
            penalty += 0.25
    for phrase in _LOW_SIGNAL_PHRASES:
        if phrase in lowered:
            penalty += 0.25
    return penalty


def _build_windows(
    segments: list[TranscriptSegment],
    min_s: int,
    max_s: int,
) -> list[HighlightCandidate]:
    candidates: list[HighlightCandidate] = []

    for i, segment in enumerate(segments):
        start = segment.start
        text_parts = [segment.text]
        end = segment.end

        j = i + 1
        while j < len(segments) and end - start < min_s:
            text_parts.append(segments[j].text)
            end = segments[j].end
            j += 1

        while j < len(segments) and end - start < max_s:
            combined = " ".join(text_parts + [segments[j].text])
            projected_end = segments[j].end
            if projected_end - start > max_s:
                break
            text_parts.append(segments[j].text)
            end = projected_end
            j += 1

        duration = end - start
        if duration < min_s or duration > max_s:
            continue

        text = " ".join(text_parts)
        candidates.append(
            HighlightCandidate(
                start=start,
                end=end,
                score=0.0,
                reason=text,
            )
        )

    return candidates


def _non_overlapping_top(
    candidates: list[HighlightCandidate],
    max_clips: int,
    min_center_gap_seconds: float = 0.0,
) -> list[HighlightCandidate]:
    selected: list[HighlightCandidate] = []
    ranked = sorted(candidates, key=lambda x: x.score, reverse=True)

    # Pass 1: enforce overlap + temporal diversity to avoid near-duplicate moments.
    for candidate in ranked:
        has_overlap = any(
            not (candidate.end <= existing.start or candidate.start >= existing.end)
            for existing in selected
        )
        if has_overlap:
            continue
        if min_center_gap_seconds > 0:
            center = (candidate.start + candidate.end) * 0.5
            too_close = any(
                abs(center - ((existing.start + existing.end) * 0.5)) < min_center_gap_seconds
                for existing in selected
            )
            if too_close:
                continue
        selected.append(candidate)
        if len(selected) >= max_clips:
            break

    # Pass 2: if not enough clips, relax gap but keep non-overlap.
    if len(selected) < max_clips:
        for candidate in ranked:
            if candidate in selected:
                continue
            has_overlap = any(
                not (candidate.end <= existing.start or candidate.start >= existing.end)
                for existing in selected
            )
            if has_overlap:
                continue
            selected.append(candidate)
            if len(selected) >= max_clips:
                break

    return sorted(selected, key=lambda x: x.start)


def _read_local_env_key(key: str) -> str:
    """Read a key from config/local.env."""
    env_path = Path(__file__).resolve().parents[3] / "config" / "local.env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _llm_rerank(
    candidates: list[HighlightCandidate],
    niche_hint: str = "tech/AI content",
) -> list[HighlightCandidate]:
    """Re-rank candidates using GPT-4o-mini by virality/engagement potential."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or _read_local_env_key("OPENAI_API_KEY")
    if not api_key:
        return candidates

    model = (
        os.getenv("OPENAI_CHAT_MODEL", "").strip()
        or _read_local_env_key("OPENAI_CHAT_MODEL")
        or "gpt-4o-mini"
    )

    items_text = []
    for i, c in enumerate(candidates):
        duration = c.end - c.start
        items_text.append(f"{i + 1}. [{c.start:.0f}s–{c.end:.0f}s, {duration:.0f}s] {c.reason[:350]}")

    prompt = (
        f"You are a YouTube Shorts editor for {niche_hint}. "
        "Below are transcript fragments from a live stream. "
        "For each fragment assign a virality score 1-10 for YouTube Shorts "
        "(10=bold claim, concrete result/number, teaches a specific method, hooks viewer instantly; "
        "5=average educational moment; 1=intro filler, greetings, off-topic chatter). "
        "IMPORTANT: only return a JSON array like [{\"index\":1,\"score\":8}, ...]. No other text.\n\n"
        + "\n".join(items_text)
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a viral content scoring engine. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 600,
    }
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            resp = json.loads(response.read().decode("utf-8"))
        content = resp["choices"][0]["message"]["content"].strip()
        # Strip markdown code fence if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]).rstrip("`").strip()
        score_map: dict[int, float] = {item["index"]: float(item["score"]) for item in json.loads(content)}
        for i, c in enumerate(candidates):
            llm_score = score_map.get(i + 1, 5.0)
            # Blend: 30% heuristic (captures duration/density), 70% LLM (captures content quality)
            c.score = c.score * 0.30 + (llm_score / 10.0) * 0.70
    except Exception:
        pass  # Keep original scores on any error

    return candidates


def select_highlights(
    settings: Settings,
    transcript: list[TranscriptSegment],
    duration_seconds: float,
) -> list[HighlightCandidate]:
    context = SelectorContext(
        min_clip_seconds=settings.app.min_clip_seconds,
        max_clip_seconds=settings.app.max_clip_seconds,
        max_clips=settings.app.max_clips,
        max_candidates=settings.app.max_candidates,
        keyword_boost=settings.highlight.keyword_boost,
        intro_penalty_phrases=settings.highlight.intro_penalty_phrases,
    )

    candidates = _build_windows(
        transcript,
        min_s=context.min_clip_seconds,
        max_s=context.max_clip_seconds,
    )

    global_counts = Counter()
    for segment in transcript:
        global_counts.update(_tokenize(segment.text))

    for candidate in candidates:
        duration_score = 1.0 - abs((candidate.end - candidate.start) - 35.0) / 35.0
        text_score = _text_score(candidate.reason, context.keyword_boost)
        engagement = _engagement_score(candidate.reason, context.keyword_boost, global_counts)
        penalty = _penalty_score(candidate.reason, context.intro_penalty_phrases)
        candidate.score = max(
            0.0,
            duration_score * 0.35 + text_score * 0.25 + engagement * 0.40 - penalty,
        )

    if not candidates:
        # Fallback to evenly distributed windows when transcript quality is poor.
        clips = []
        segment_len = min(context.max_clip_seconds, 35)
        if duration_seconds <= segment_len:
            return [
                HighlightCandidate(
                    start=0.0,
                    end=max(1.0, duration_seconds),
                    score=0.1,
                    reason="Fallback full-duration clip",
                )
            ]

        step = max(1.0, (duration_seconds - segment_len) / max(1, context.max_clips))
        start = 0.0
        while start + context.min_clip_seconds <= duration_seconds and len(clips) < context.max_clips:
            end = min(duration_seconds, start + segment_len)
            clips.append(
                HighlightCandidate(
                    start=start,
                    end=end,
                    score=0.1,
                    reason="Fallback evenly spaced window",
                )
            )
            start += step
        return clips

    top = sorted(candidates, key=lambda x: x.score, reverse=True)[: context.max_candidates]

    if settings.highlight.use_llm_rerank:
        # Pre-select top 20 by heuristic, send to LLM, then re-sort
        llm_pool = top[:20]
        llm_pool = _llm_rerank(llm_pool)
        # Merge back: LLM-scored pool replaces the head, rest keeps heuristic order
        scored_ids = {id(c) for c in llm_pool}
        remainder = [c for c in top if id(c) not in scored_ids]
        top = sorted(llm_pool, key=lambda x: x.score, reverse=True) + remainder

    # Keep selected moments spread across the source rather than clustered in one section.
    min_center_gap = max(20.0, duration_seconds / max(1, context.max_clips) * 0.28)
    return _non_overlapping_top(top, context.max_clips, min_center_gap_seconds=min_center_gap)
