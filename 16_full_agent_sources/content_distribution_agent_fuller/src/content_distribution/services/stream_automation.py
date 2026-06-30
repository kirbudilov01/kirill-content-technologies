from __future__ import annotations

import base64
import json
import os
import re
import shutil
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from content_distribution.config import load_settings
from content_distribution.models.contracts import JobStatus, TranscriptSegment
from content_distribution.services.orchestrator import run_pipeline
from content_distribution.services.transcription import produce_transcript
from content_distribution.utils.srt import parse_srt


DEFAULT_PLATFORMS = [
    "YouTube (3 channels)",
    "X",
    "Instagram",
    "Facebook",
    "TikTok",
    "Pinterest",
    "Reddit",
    "Rumble",
    "Kick",
    "Twitch",
    "LinkedIn",
]

PLATFORM_FOLDERS = [
    "YOUTUBE",
    "X",
    "LINKEDIN",
    "TELEGRAM",
    "INSTAGRAM",
    "TIKTOK",
    "FACEBOOK",
    "DISCORD",
    "PINTEREST",
    "MEDIUM",
    "SUBSTACK",
]

DEFAULT_YOUTUBE_CHANNELS = [
    "https://www.youtube.com/@fabricbotecosystem",
    "https://www.youtube.com/@fabricbotshorts",
    "https://www.youtube.com/@kir.budilov/videos",
]

DEFAULT_CREATOR_X_URL = "https://x.com/"
SYSTEM_FILES_DIRNAME = "_SYSTEM"

_TITLE_BANNED_TERMS = {
    "revolutionary",
    "innovative",
    "next-gen",
    "comprehensive guide",
    "deep dive",
    "ultimate guide",
    "leveraging",
    "implementation",
    "infrastructure",
    "ecosystem",
    "transformation strategy",
}


@dataclass
class StreamWorkspaceResult:
    root: Path
    source_video_path: Path | None
    manifest_path: Path
    transcription_path: Path | None
    shorts_job_id: str | None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    slug = slug.strip("-")
    return slug or "stream"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _clip_text_budget(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "\n...[truncated]"


def _get_secret_from_local_env(key: str) -> str:
    """Read secret value from config/local.env if present."""
    env_path = Path(__file__).resolve().parents[3] / "config" / "local.env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() != key:
                continue
            value = v.strip().strip('"').strip("'")
            return value
    except Exception:
        return ""
    return ""


def _call_llm(messages: list[dict], model: str | None = None, max_tokens: int = 4200, temperature: float = 0.7) -> str:
    """Call LLM via OpenAI API or GitHub Models API (fallback when OpenAI key is empty or balance is exhausted).

    Priority:
    0. LLM_BASE_URL (local OpenWebUI / any OpenAI-compatible endpoint, e.g. http://localhost:3000/api)
    1. OPENAI_API_KEY → api.openai.com  (falls back on 429/402)
    2. GITHUB_COPILOT_TOKEN → models.inference.ai.azure.com (GitHub Models API, no token exchange needed)
    """
    openai_key = os.getenv("OPENAI_API_KEY", "").strip() or _get_secret_from_local_env("OPENAI_API_KEY")
    copilot_token = os.getenv("GITHUB_COPILOT_TOKEN", "").strip() or _get_secret_from_local_env("GITHUB_COPILOT_TOKEN")
    local_base_url = os.getenv("LLM_BASE_URL", "").strip() or _get_secret_from_local_env("LLM_BASE_URL")

    def _do_request(api_key: str, base_url: str, chat_model: str) -> str:
        payload = {
            "model": chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=240) as response:
            resp_body = json.loads(response.read().decode("utf-8"))
        return str(resp_body["choices"][0]["message"]["content"]).strip()

    # Priority 0: local OpenWebUI or any OpenAI-compatible endpoint (LLM_BASE_URL in local.env)
    if local_base_url:
        local_url = local_base_url.rstrip("/")
        if not local_url.endswith("/chat/completions"):
            local_url = local_url + "/v1/chat/completions"
        local_model = model or (
            os.getenv("LLM_MODEL", "").strip()
            or _get_secret_from_local_env("LLM_MODEL")
            or "gpt-4o-mini"
        )
        local_key = openai_key or "local"
        print(f"[llm] Using local LLM endpoint: {local_url} model={local_model}")
        return _do_request(local_key, local_url, local_model)

    # Try OpenAI first; fall back to GitHub Models on quota/billing errors (402, 429)
    if openai_key:
        chat_model = model or (
            os.getenv("OPENAI_CHAT_MODEL", "").strip()
            or _get_secret_from_local_env("OPENAI_CHAT_MODEL")
            or "gpt-4o-mini"
        )
        try:
            return _do_request(openai_key, "https://api.openai.com/v1/chat/completions", chat_model)
        except urllib.error.HTTPError as exc:
            if exc.code in (402, 429) and copilot_token:
                print(f"[llm] OpenAI returned {exc.code} (quota/billing), falling back to GitHub Models API")
            else:
                raise

    if copilot_token:
        return _do_request(
            copilot_token,
            "https://models.inference.ai.azure.com/chat/completions",
            model or "gpt-4o-mini",
        )

    raise RuntimeError(
        "No LLM API key available. Set OPENAI_API_KEY, LLM_BASE_URL, or GITHUB_COPILOT_TOKEN in env or config/local.env"
    )


def _creator_profile_links() -> tuple[str, str]:
    youtube_url = (
        os.getenv("CREATOR_YOUTUBE_URL", "").strip()
        or _get_secret_from_local_env("CREATOR_YOUTUBE_URL")
        or DEFAULT_YOUTUBE_CHANNELS[0]
    )
    x_url = (
        os.getenv("CREATOR_X_URL", "").strip()
        or _get_secret_from_local_env("CREATOR_X_URL")
        or DEFAULT_CREATOR_X_URL
    )
    return youtube_url, x_url


def _target_screenshot_count(duration_seconds: float) -> int:
    if duration_seconds <= 0:
        return 3
    if duration_seconds < 8 * 60:
        return 3
    if duration_seconds < 30 * 60:
        return 5
    return 7


def _extract_stream_screenshots(video_path: Path, photobank_dir: Path) -> list[Path]:
    import cv2

    photobank_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return []

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    count = _target_screenshot_count(duration)

    start = 0.0 if duration <= 10 else duration * 0.08
    end = duration if duration <= 10 else duration * 0.92
    if end <= start:
        end = start + max(1.0, duration)

    step = (end - start) / max(1, count - 1)
    timestamps = [start + step * i for i in range(count)]

    saved: list[Path] = []
    for index, ts in enumerate(timestamps, start=1):
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts) * 1000.0)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        out = photobank_dir / f"shot_{index:02d}_{int(ts)}s.jpg"
        if cv2.imwrite(str(out), frame):
            saved.append(out)

    capture.release()
    return saved


def _format_ts(seconds: float) -> str:
    sec = max(0, int(seconds))
    hh = sec // 3600
    mm = (sec % 3600) // 60
    ss = sec % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _transcript_to_text(segments: list[TranscriptSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        lines.append(f"[{_format_ts(segment.start)} - {_format_ts(segment.end)}] {text}")
    return "\n".join(lines)


def _top_phrases(text: str, limit: int = 12) -> list[str]:
    stopwords = {
        "this", "that", "with", "from", "have", "your", "about", "into", "after", "when", "they",
        "the", "and", "for", "you", "are", "was", "but", "not", "что", "это", "как", "для", "или",
        "чтобы", "только", "если", "когда", "всего", "очень", "потом", "просто", "можно", "будет",
    }
    tokens = re.findall(r"[A-Za-zА-Яа-я0-9_]{4,}", text.lower())
    freq = Counter(token for token in tokens if token not in stopwords)
    return [word for word, _ in freq.most_common(limit)]


def _top_sentences(segments: list[TranscriptSegment], limit: int = 8) -> list[str]:
    def _strip_time_prefix(text: str) -> str:
        return re.sub(r"^\[\d{2}:\d{2}:\d{2}\s*-\s*\d{2}:\d{2}:\d{2}\]\s*", "", text).strip()

    candidates = [_strip_time_prefix(seg.text.strip()) for seg in segments if len(seg.text.strip()) > 30]
    if not candidates:
        return []

    # Sample evenly from the full transcript (skip first 5% — usually intro chatter)
    skip_head = max(0, len(candidates) // 20)
    pool = candidates[skip_head:]
    if len(pool) > 120:
        step = len(pool) // 120
        pool = pool[::step][:120]

    # Try LLM-based semantic hook extraction first
    try:
        transcript_sample = "\n".join(f"- {s}" for s in pool)
        result = _call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a viral content strategist. "
                        "Your job is to pick the most marketing-powerful lines from a transcript — "
                        "moments that would stop someone scrolling, make them curious, or deliver a concrete insight. "
                        "Prefer lines with: specific numbers, surprising claims, clear mistakes/solutions, "
                        "strong opinions, actionable insights. Avoid filler, greetings, and vague statements."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"From this transcript, pick the {limit} best lines to use as marketing hooks.\n"
                        "Return ONLY the selected lines, one per line, no numbering, no commentary.\n\n"
                        f"{transcript_sample}"
                    ),
                },
            ],
            max_tokens=600,
            temperature=0.3,
        )
        hooks = [line.lstrip("•-– ").strip() for line in result.splitlines() if line.strip()]
        hooks = [h for h in hooks if len(h) > 20]
        if hooks:
            return hooks[:limit]
    except Exception:
        pass

    # Fallback: simple length-based sort (no keyword lists)
    ranked = sorted(candidates, key=len, reverse=True)
    unique: list[str] = []
    for s in ranked:
        low = s.lower()
        if any(low in o.lower() or o.lower() in low for o in unique):
            continue
        unique.append(s)
        if len(unique) >= limit:
            break
    return unique


def _build_marketing_takes(sentences: list[str]) -> str:
    items = "\n".join(f"- {line}" for line in sentences[:6]) if sentences else "- No transcript highlights extracted"
    return (
        "# MARKETING TAKES\n\n"
        "## High-Value Hooks\n"
        f"{items}\n\n"
        "## CTA Directions\n"
        "- Invite viewers to watch full replay for context\n"
        "- Pin one concrete takeaway in comments\n"
        "- Route traffic to your main channel funnel\n"
    )


def _read_stream_notes_context(workspace: Path) -> str:
    system_dir = workspace / SYSTEM_FILES_DIRNAME
    note_files = [
        workspace / "W2V INSIGHTS.md",
        workspace / "MARKETING TAKES.md",
        workspace / "INSTRUCTIONS FOR SYSTEM.md",
        workspace / "PUBLISHING INSTRUCTIONS.md",
        system_dir / "INSTRUCTIONS FOR SYSTEM.md",
        system_dir / "PUBLISHING INSTRUCTIONS.md",
    ]
    chunks: list[str] = []
    for path in note_files:
        if not path.exists() or not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if raw:
            chunks.append(raw[:2000])
    return "\n\n".join(chunks)


def _viewer_pain_from_signals(niche: str, phrases: list[str], hooks: list[str], notes_context: str = "") -> str:
    joined = " ".join([niche, *phrases[:12], *hooks[:3], notes_context]).lower()
    if any(token in joined for token in ["short", "clip", "editing", "subtitle"]):
        return "manual Shorts editing"
    if any(token in joined for token in ["post", "smm", "publish", "distribution"]):
        return "manual posting across platforms"
    if any(token in joined for token in ["telegram", "lead", "client", "sales"]):
        return "inconsistent lead generation"
    return "manual content workflow"


def _desired_result_from_signals(niche: str, phrases: list[str], hooks: list[str], notes_context: str = "") -> str:
    joined = " ".join([niche, *phrases[:12], *hooks[:3], notes_context]).lower()
    if any(token in joined for token in ["short", "clip"]):
        return "a repeatable shorts pipeline"
    if any(token in joined for token in ["post", "publish", "distribution", "smm"]):
        return "an automated posting system"
    if any(token in joined for token in ["telegram", "lead", "client"]):
        return "a content engine that brings leads"
    return "a scalable content machine"


def _main_object_from_signals(niche: str, phrases: list[str], hooks: list[str], notes_context: str = "") -> str:
    joined = " ".join([niche, *phrases[:12], *hooks[:3], notes_context]).lower()
    if "telegram" in joined:
        return "Telegram workflow"
    if any(token in joined for token in ["short", "clip"]):
        return "shorts system"
    if any(token in joined for token in ["agent", "ai", "automation"]):
        return "AI agent"
    return "content system"


def _novelty_from_hooks(hooks: list[str], niche: str) -> str:
    if hooks:
        return hooks[0].strip()
    return f"one practical shift in {niche}"


def _restore_brands(text: str) -> str:
    fixed = text
    replacements = {
        r"\bai\b": "AI",
        r"\byoutube\b": "YouTube",
        r"\btelegram\b": "Telegram",
        r"\bweb3\b": "Web3",
        r"\bfabricbot\b": "FabricBot",
        r"\bopenai\b": "OpenAI",
        r"\bx\b": "X",
        r"\blinkedin\b": "LinkedIn",
        r"\btiktok\b": "TikTok",
        r"\bshorts\b": "Shorts",
    }
    for pattern, replacement in replacements.items():
        fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)
    return fixed


def _to_sentence_case(title: str) -> str:
    base = re.sub(r"\s+", " ", title).strip()
    if not base:
        return base
    base = base[:1].upper() + base[1:]
    return _restore_brands(base)


def _contains_banned_term(title: str) -> bool:
    low = title.lower()
    return any(term in low for term in _TITLE_BANNED_TERMS)


def _title_quality_score(title: str, pain: str, result: str, obj: str) -> int:
    score = 30
    low = title.lower()

    # clarity
    words = re.findall(r"[A-Za-zА-Яа-я0-9_]+", title)
    if 5 <= len(words) <= 14:
        score += 15
    if obj.lower() in low:
        score += 12

    # pain + transformation
    if any(token in low for token in ["stop", "manual", "broken", "failed"]):
        score += 12
    if any(token in low for token in ["from", "turned", "built", "automated", "tested"]):
        score += 12
    if result.lower()[:12] in low or pain.lower()[:12] in low:
        score += 8

    # curiosity
    if any(token in low for token in ["how", "why", "here is what works"]):
        score += 8

    # penalties
    if _contains_banned_term(title):
        score -= 25
    if len(words) < 4 or len(words) > 16:
        score -= 6

    return max(0, min(100, score))


def _article_for(noun_phrase: str) -> str:
    first = noun_phrase.strip().lower()
    if first.startswith(("a", "e", "i", "o", "u")):
        return "an"
    return "a"


def _parse_hhmmss_to_seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        return 0
    try:
        hh, mm, ss = [int(x) for x in parts]
    except Exception:
        return 0
    return max(0, hh * 3600 + mm * 60 + ss)


def _format_mmss(total_seconds: int) -> str:
    sec = max(0, int(total_seconds))
    mm = sec // 60
    ss = sec % 60
    return f"{mm:02d}:{ss:02d}"


def _extract_timed_transcript_points(transcript_text: str, hooks: list[str]) -> list[tuple[int, str]]:
    points: list[tuple[int, str]] = []
    for raw in transcript_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^\[(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})\]\s*(.*)$", line)
        if not match:
            continue
        start_ts = _parse_hhmmss_to_seconds(match.group(1))
        text = match.group(3).strip()
        if not text:
            continue
        # Skip first 5 minutes (intro/testing chatter before real content starts)
        if start_ts < 300:
            continue
        points.append((start_ts, text))

    if not points and hooks:
        synthetic = [
            (95, hooks[0]),
            (190, hooks[min(1, len(hooks) - 1)]),
            (405, hooks[min(2, len(hooks) - 1)]),
        ]
        points.extend((ts, txt.strip()) for ts, txt in synthetic if txt.strip())

    return points


def _chapter_title_from_text(text: str, fallback: str) -> str:
    """Generate a short YouTube chapter title from a transcript snippet using LLM."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return fallback
    # Try LLM to produce a short, punchy chapter title (max 6 words)
    try:
        result = _call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert transcript snippets into short YouTube chapter titles. "
                        "Rules: max 6 words, plain English or Russian (match the snippet language), "
                        "no quotes, no punctuation at end, be specific not vague."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Snippet: {normalized[:200]}\n\nChapter title:",
                },
            ],
            max_tokens=30,
            temperature=0.3,
        )
        title = result.strip().strip('"\'')
        if title and len(title) < 80:
            return title
    except Exception:
        pass
    short = normalized[:72].rstrip(" .,:;!?")
    return short or fallback


def _build_chapter_seeds(transcript_text: str, hooks: list[str], niche: str) -> list[str]:
    points = _extract_timed_transcript_points(transcript_text, hooks)
    chapters: list[tuple[int, str]] = [(0, "Intro")]

    # Important density rule: first meaningful chapter must be in first 1-3 minutes.
    first_early = next((item for item in points if 60 <= item[0] <= 180), None)
    if first_early is None:
        first_title = _chapter_title_from_text(
            hooks[0] if hooks else f"What this stream is about in {niche}",
            "What we are building today",
        )
        chapters.append((95, first_title))
    else:
        chapters.append((first_early[0], _chapter_title_from_text(first_early[1], "What we are building today")))

    min_gap = 90
    last_ts = chapters[-1][0]
    for ts, text in points:
        if ts <= last_ts + min_gap:
            continue
        title = _chapter_title_from_text(text, f"Section at {_format_mmss(ts)}")
        chapters.append((ts, title))
        last_ts = ts
        if len(chapters) >= 6:
            break

    if len(chapters) < 4:
        defaults = [
            (190, "Why this system matters"),
            (405, "The main workflow bottleneck"),
            (620, "How the SMM/producer loop works"),
        ]
        for ts, title in defaults:
            if ts > chapters[-1][0] + 60 and len(chapters) < 6:
                chapters.append((ts, title))

    rendered: list[str] = []
    for ts, title in chapters[:7]:
        rendered.append(f"- {_format_mmss(ts)} {title}")
    return rendered


def _infer_description_topic(niche: str, phrases: list[str], hooks: list[str], notes_context: str, transcript_text: str) -> str:
    joined = " ".join([niche, notes_context, transcript_text[:4000], *phrases[:20], *hooks[:6]]).lower()
    if any(token in joined for token in ["want2view", "youtube analytics", "video analytics", "content strategy"]):
        return "want2view"
    # Match 'ton', 'ico', 'fabricbot' only as whole words to avoid false positives from 'automation', 'factor', etc.
    if re.search(r'\bico\b|\bton\b|\bfabricbot\b', joined):
        return "fabricbot_ico"
    if any(token in joined for token in ["custom", "telegram bot", "dashboard", "client workflow", "services"]):
        return "services"
    if any(token in joined for token in ["open-source", "opensource", "repo", "repository", "scout"]):
        return "open_source_scout"
    return "ai_automation"


def _build_description_opening(topic: str, hook: str) -> str:
    clean_hook = re.sub(r"\s+", " ", hook).strip().rstrip(".")
    if topic == "open_source_scout":
        return (
            "AI automation is not just about generating more text. The real leverage starts when an agent can scout tools, understand what is useful, and turn open-source projects into working systems.\n\n"
            "In this stream, I am working through the logic of an AI agent scout for open-source projects: a system that can help discover useful repos, connect them to real workflows, and turn them into practical automation assets."
        )
    if topic == "fabricbot_ico":
        return (
            "Most crypto projects start with a token and hope the product catches up. We are doing the reverse on purpose: product first, coverage first, community first, and crowdfunding as a clean reality test before ICO narratives.\n\n"
            "What matters is real usage and distribution, not speculation. This stream focuses on how FabricBot decisions connect product execution with TON/Web3 direction."
        )
    if topic == "services":
        return (
            "Most businesses do not need another generic AI demo. They need a working system: an agent, dashboard, Telegram bot, or automation workflow that solves a real operational problem.\n\n"
            "In this stream, I break down how these systems can be designed, built, and packaged into practical tools for creators, agencies, and companies."
        )
    if topic == "want2view":
        return (
            "Most creators guess what to publish next. The better approach is to analyze what is already working: competitors, outliers, trends, formats, and audience behavior.\n\n"
            "In this stream, I show how video trend analytics can become a real content engine instead of another random list of ideas."
        )
    return (
        "AI automation is useful only when it moves from content volume to operational decisions. The main leverage starts when one stream can be transformed into reusable assets with clear next actions.\n\n"
        f"In this stream, I break down that system in practice, including what worked, what failed, and what changed around this core idea: {clean_hook or 'build reusable content workflows'}."
    )


def _build_description_summary(topic: str, stream_title: str, niche: str, hook: str) -> str:
    clean_hook = re.sub(r"\s+", " ", hook).strip().rstrip(".")
    if topic == "open_source_scout":
        return (
            "In this video, I explain the idea behind an AI agent scout for open-source projects: how it can search for useful repositories, evaluate them, connect them to real automation workflows, and help builders turn scattered tools into a practical system."
        )
    if topic == "fabricbot_ico":
        return (
            "In this video, I explain the FabricBot Web3 direction through product-first logic: why distribution and usage are the moat, why community quality matters, and why token layers only make sense when tied to real transactions and operating systems."
        )
    if topic == "services":
        return (
            "In this video, I break down how custom AI agents, Telegram bots, dashboards, and automation systems can be built around real business workflows, from content operations and analytics to lead generation and internal tooling."
        )
    if topic == "want2view":
        return (
            "In this video, I show how video trend analytics can help creators and teams detect outliers, understand working formats, and turn YouTube data into a practical content strategy."
        )
    return (
        f"In this video, I break down {stream_title} around a practical {niche} workflow: how to extract signal from the stream, package it into reusable assets, and turn the strongest moments into consistent output. Key stream shift: {clean_hook or 'operational decision-making over random generation'}."
    )


def _build_description_hashtags(topic: str) -> list[str]:
    tags = ["#AI", "#Telegram", "#Web3", "#TON", "#Blockchain"]
    if topic == "open_source_scout":
        tags.extend(["#AIAgents", "#Automation", "#OpenSource", "#AITools", "#AgenticWorkflows"])
    elif topic == "fabricbot_ico":
        tags.extend(["#TONCommunity", "#Crypto", "#FabricBot"])
    elif topic == "services":
        tags.extend(["#AIAutomation", "#TelegramBots", "#Dashboards", "#CustomDevelopment"])
    elif topic == "want2view":
        tags.extend(["#YouTube", "#YouTubeAutomation", "#ContentStrategy", "#CreatorTools", "#VideoAnalytics"])

    unique: list[str] = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
        if len(unique) >= 8:
            break
    return unique


def _clean_tag(tag: str) -> str:
    value = re.sub(r"\s+", " ", tag.strip().lower())
    value = value.replace("#", "")
    value = re.sub(r"[^a-z0-9а-яё+\- ]", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value


def _join_tags(tags: list[str]) -> str:
    return ", ".join(tags)


def _build_youtube_tags_line(
    stream_title: str,
    niche: str,
    phrases: list[str],
    hooks: list[str],
    transcript_text: str,
    notes_context: str,
    chapters: list[str],
    description_text: str,
) -> str:
    topic = _infer_description_topic(niche, phrases, hooks, notes_context, transcript_text)
    joined = " ".join([
        stream_title,
        niche,
        notes_context,
        transcript_text[:5000],
        description_text[:3000],
        " ".join(chapters[:6]),
        " ".join(phrases[:20]),
        " ".join(hooks[:8]),
    ]).lower()

    layer_1 = [
        "AI",
        "artificial intelligence",
        "AI tools",
        "AI agents",
        "automation",
        "workflow automation",
        "business automation",
        "productivity",
        "startups",
        "tech",
    ]

    layer_2: list[str] = []
    if any(token in joined for token in ["youtube", "shorts", "content", "video", "creator"]):
        layer_2.extend([
            "YouTube",
            "YouTube automation",
            "content creation",
            "content strategy",
            "video marketing",
            "YouTube Shorts",
            "creator economy",
            "content marketing",
        ])
    if any(token in joined for token in ["telegram", "web3", "ton", "blockchain", "crypto"]):
        layer_2.extend([
            "Telegram",
            "Telegram bot",
            "Web3",
            "blockchain",
            "crypto",
            "TON",
            "TON blockchain",
            "crypto startup",
        ])
    if any(token in joined for token in ["dashboard", "analytics", "custom", "service", "client"]):
        layer_2.extend([
            "dashboards",
            "data analytics",
            "custom software",
            "SaaS",
            "startup tools",
            "AI development",
        ])
    if topic == "open_source_scout" or any(token in joined for token in ["open source", "repository", "repo"]):
        layer_2.extend([
            "open source",
            "open source AI",
            "agentic AI",
            "automation tools",
            "AI productivity",
        ])

    if not layer_2:
        layer_2.extend([
            "AI automation",
            "AI workflow",
            "agentic AI",
            "automation tools",
            "creator tools",
        ])

    layer_3 = ["FabricBot", "want2view", "Telegram", "TON"]

    layer_4 = [
        "online business",
        "digital marketing",
        "social media",
        "automation software",
        "creator tools",
        "business tools",
        "AI business",
        "tech startup",
        "no code",
        "SaaS",
    ]

    merged = [*layer_1, *layer_2, *layer_3, *layer_4]

    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in merged:
        tag = _clean_tag(raw)
        if not tag:
            continue
        if len(tag) > 32:
            continue
        if "  " in tag:
            tag = re.sub(r"\s+", " ", tag)
        if tag in seen:
            continue
        seen.add(tag)
        cleaned.append(tag)

    # Maintain roughly 300-400 chars.
    picked: list[str] = []
    for tag in cleaned:
        candidate = _join_tags([*picked, tag])
        if len(candidate) > 400:
            continue
        picked.append(tag)

    # If too short, enrich from adjacent topics.
    if len(_join_tags(picked)) < 300:
        enrich = ["content creation", "YouTube", "Telegram", "Web3", "TON", "digital products", "video analytics"]
        for raw in enrich:
            tag = _clean_tag(raw)
            if not tag or tag in seen:
                continue
            candidate = _join_tags([*picked, tag])
            if len(candidate) > 400:
                continue
            picked.append(tag)
            seen.add(tag)
            if len(_join_tags(picked)) >= 300:
                break

    # Trim if somehow too long.
    while len(_join_tags(picked)) > 400 and picked:
        picked.pop()

    return _join_tags(picked)


def _render_chapters_for_description(chapters: list[str]) -> str:
    if chapters:
        return "\n".join(chapters)
    return "- 00:00 Intro\n- 01:35 What this stream is about\n- 03:10 Core topic\n- 06:45 Practical framework"


def _build_youtube_description(
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    transcript_text: str,
    notes_context: str,
    chapters: list[str],
) -> str:
    topic = _infer_description_topic(niche, phrases, hooks, notes_context, transcript_text)
    lead_hook = hooks[0] if hooks else stream_title
    opening = _build_description_opening(topic, lead_hook)
    summary = _build_description_summary(topic, stream_title, niche, lead_hook)
    hashtags = " ".join(_build_description_hashtags(topic))
    chapter_block = _render_chapters_for_description(chapters)

    return (
        f"{opening}\n\n"
        "🔗 Main links\n\n"
        "want2view — video trend analytics service:\n"
        "https://want2view.com\n\n"
        "AI automation community / open-source project scout:\n"
        "https://kirbudilov01.github.io/reposearchengine\n\n"
        "FabricBot ICO / Web3 product:\n"
        "https://ico.fabricbot.tech\n\n"
        "Custom AI agents, Telegram bots, dashboards, and automation development:\n"
        "http://t.me/fabricbotbot\n\n"
        f"{summary}\n\n"
        "⏱ Timestamps\n\n"
        f"{chapter_block}\n\n"
        "🌐 Socials\n\n"
        "X / Twitter:\n"
        "https://x.com/kirillfbc\n\n"
        "Telegram channel:\n"
        "https://t.me/kirilldigitalshamanism\n\n"
        "Direct contact:\n"
        "https://t.me/kirbudilov\n\n"
        "This channel is dedicated to Web3, Telegram technologies, AI agents, creator tools, automation systems, and future digital ecosystems. I’m an active part of the TON community, and here I share insights, experiments, and practical tools that combine blockchain, artificial intelligence, and real product building.\n\n"
        f"{hashtags}\n"
    )


def _build_youtube_title_candidates(
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    notes_context: str = "",
) -> list[str]:
    obj = _main_object_from_signals(niche, phrases, hooks, notes_context)
    pain = _viewer_pain_from_signals(niche, phrases, hooks, notes_context)
    result = _desired_result_from_signals(niche, phrases, hooks, notes_context)
    article = _article_for(obj)
    niche_clean = niche.strip()

    candidates = [
        f"I built {article} {obj} that removes {pain}",
        f"I automated my {niche_clean} workflow with AI agents",
        f"How I turned one stream into {result}",
        f"AI agents changed how I run {niche_clean}",
        f"{niche_clean} workflows are broken - here is what works",
        f"Stop doing {pain}",
        f"The system behind my {niche_clean} engine",
        f"From one stream to {result}",
        f"Why {obj} is the real opportunity now",
        f"I tested an AI content factory for 7 days",
    ]

    unique: list[str] = []
    for title in candidates:
        clean = re.sub(r"\s+", " ", title).strip()
        clean = _to_sentence_case(clean)
        if _contains_banned_term(clean):
            continue
        if clean and clean not in unique:
            unique.append(clean)
    return unique[:10]


def _build_seo_package(
    stream_title: str,
    niche: str,
    phrases: list[str],
    hooks: list[str],
    transcript_text: str = "",
    notes_context: str = "",
) -> str:
    keywords = ", ".join(phrases[:10]) if phrases else niche
    novelty = _novelty_from_hooks(hooks, niche)
    titles = _build_youtube_title_candidates(stream_title, niche, hooks, phrases, notes_context)
    top3 = titles[:3]
    obj = _main_object_from_signals(niche, phrases, hooks, notes_context)
    pain = _viewer_pain_from_signals(niche, phrases, hooks, notes_context)
    result = _desired_result_from_signals(niche, phrases, hooks, notes_context)
    expl: list[str] = []
    if top3:
        expl.append(f"- {top3[0]} -> clear topic + builder proof + practical transformation")
    if len(top3) > 1:
        expl.append(f"- {top3[1]} -> concrete automation angle and strong relevance for operators")
    if len(top3) > 2:
        expl.append(f"- {top3[2]} -> strong curiosity arc: from one input to scalable output")

    thumb_opts = [
        _short_thumbnail_text(top3[0] if top3 else novelty, max_words=5),
        _short_thumbnail_text(top3[1] if len(top3) > 1 else "Stop doing this manually", max_words=5),
        _short_thumbnail_text(novelty, max_words=5),
    ]

    novelty_clean = novelty.rstrip(". ")
    desc_hook = (
        f"I tested this live: {novelty_clean}. "
        "In this stream I show what failed, what worked, and how to turn one stream into repeatable output."
    )

    score_lines = "\n".join(
        f"- {title} -> {_title_quality_score(title, pain, result, obj)}"
        for title in titles
    ) or "- no scored titles"

    chapters = _build_chapter_seeds(transcript_text, hooks, niche)
    yt_description = _build_youtube_description(
        stream_title=stream_title,
        niche=niche,
        hooks=hooks,
        phrases=phrases,
        transcript_text=transcript_text,
        notes_context=notes_context,
        chapters=chapters,
    )
    yt_tags_line = _build_youtube_tags_line(
        stream_title=stream_title,
        niche=niche,
        phrases=phrases,
        hooks=hooks,
        transcript_text=transcript_text,
        notes_context=notes_context,
        chapters=chapters,
        description_text=yt_description,
    )

    return (
        "# SEO AND DATA FOR VIDEO\n\n"
        "## Source analyzed before title generation\n"
        "- transcript\n"
        "- stream notes (if available)\n"
        "- MARKETING TAKES / positioning file\n"
        "- prepared clips and timestamps (if available)\n\n"
        "## YouTube title options (10)\n"
        + "\n".join(f"- {title}" for title in titles)
        + "\n\n## Top 3 recommended titles\n"
        + "\n".join(f"- {title}" for title in top3)
        + "\n\n## Why top 3 work\n"
        + ("\n".join(expl) if expl else "- Not enough title signals yet")
        + "\n\n## Title quality score (0-100)\n"
        + score_lines
        + "\n\n## Thumbnail text options (3-5 words)\n"
        + "\n".join(f"- {text}" for text in thumb_opts)
        + "\n\n## Description hook (first 1-2 lines)\n"
        + f"{desc_hook}\n"
        + "\n\n## Description Draft\n"
        + f"In this stream we break down {niche}. Main points: {keywords}. "
        + "Use this replay as a practical reference and implementation checklist.\n\n"
        + "## YouTube description (ready to paste)\n"
        + yt_description
        + "\n"
        + "## YouTube tags (comma-separated)\n"
        + yt_tags_line
        + "\n\n"
        + "## Tags\n"
        + f"{keywords}\n\n"
        + "## Chapter Seeds\n"
        + "\n".join(chapters)
        + "\n"
    )


def _build_shorts_titles_package(
    stream_title: str,
    clips: list[Path],
    hooks: list[str],
    phrases: list[str],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    platforms_cycle = [
        "YouTube Shorts",
        "TikTok",
        "X",
        "LinkedIn",
        "Facebook",
        "Digital Shamanism",
        "FabricBotShorts",
    ]
    pain = _viewer_pain_from_signals("", phrases, hooks)
    keyword = _short_thumbnail_text(pain, max_words=2).lower() if pain else "automation"

    lines: list[str] = [
        f"Stream: {stream_title}",
        f"Date: {now}",
        "Source materials: transcript, marketing takes, prepared clips/timestamps when available",
        "",
    ]

    if not clips:
        lines.extend([
            "No shorts clips found yet.",
            "Generate clips first, then rerun materials generation.",
            "",
        ])
        return "\n".join(lines)

    for idx, clip in enumerate(clips, start=1):
        source_hook = hooks[(idx - 1) % len(hooks)] if hooks else f"One practical insight about {keyword}"
        main_title = _restore_brands(_short_thumbnail_text(source_hook, max_words=6).lower().capitalize())
        alt1 = f"Stop doing {keyword}"
        alt1 = re.sub(r"\bmanual\s+shorts\b", "Shorts manually", alt1, flags=re.IGNORECASE)
        alt1 = re.sub(r"\s+", " ", alt1).strip()
        alt2 = f"This changed my workflow"
        first_second_hook = source_hook[:96].strip()
        caption = f"From this stream: {source_hook.rstrip('. ')}."
        platform = platforms_cycle[(idx - 1) % len(platforms_cycle)]

        lines.extend([
            f"Short {idx}",
            f"Timestamp: n/a (source: {clip.name})",
            f"Main title: {main_title}",
            f"Alternative 1: {alt1}",
            f"Alternative 2: {alt2}",
            f"First-second hook: {first_second_hook}",
            f"Caption: {caption}",
            f"Recommended platforms: {platform}",
            "Notes: keep pacing fast, open with conflict, and put strongest sentence in first 2 seconds.",
            "",
        ])

    return "\n".join(lines)


def _shorts_title_from_hook(hook: str) -> str:
    title = _short_thumbnail_text(hook, max_words=8).lower().capitalize()
    title = _restore_brands(title)
    words = re.findall(r"[A-Za-zА-Яа-я0-9_]+", title)
    if len(words) < 3:
        title = "AI agents changed my workflow"
    return _to_sentence_case(title)


def _shorts_description_for_topic(topic: str, hook: str, niche: str, cta: str) -> str:
    line1 = f"{hook.rstrip('. ')}."
    if topic == "open_source_scout":
        line2 = "This clip is part of a bigger FabricBot direction around AI automation, open-source scouting, and practical creator workflows."
    elif topic == "fabricbot_ico":
        line2 = "It connects to FabricBot's product-first Web3 approach around Telegram-native tools, usage, and real ecosystem growth."
    elif topic == "want2view":
        line2 = "It is part of a broader system where YouTube analytics and trend signals are turned into repeatable content decisions."
    elif topic == "services":
        line2 = "This fits into a wider FabricBot stack of custom AI agents, Telegram bots, dashboards, and workflow automation systems."
    else:
        line2 = f"This idea is part of the broader FabricBot ecosystem around {niche}, AI automation, and creator tooling."
    return f"{line1} {line2} {cta}"


def _build_shorts_metadata_package(
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    clips: list[Path],
    notes_context: str,
    transcript_text: str,
) -> str:
    topic = _infer_description_topic(niche, phrases, hooks, notes_context, transcript_text)
    cta_options = [
        "More details are on my channel and inside my FabricBot mix.",
        "I break down the full system on my channel and inside my FabricBot mix.",
        "The full context is on my channel and more projects are inside my FabricBot mix.",
    ]
    lines: list[str] = [
        f"Stream: {stream_title}",
        f"Date: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    if not clips:
        lines.extend([
            "No Shorts clips found.",
            "Generate clips first, then regenerate shorts metadata.",
            "",
        ])
        return "\n".join(lines)

    for index, clip in enumerate(clips, start=1):
        hook = hooks[(index - 1) % len(hooks)] if hooks else f"One practical insight from {niche}"
        title = _shorts_title_from_hook(hook)
        cta = cta_options[(index - 1) % len(cta_options)]
        description = _shorts_description_for_topic(topic, hook, niche, cta)
        lines.extend([
            f"Short {index}",
            "",
            "Title:",
            title,
            "",
            "Description:",
            description,
            "",
            f"Source clip: {clip.name}",
            "",
        ])

    return "\n".join(lines)


def _read_text_if_exists(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _collect_smm_source_materials(workspace: Path) -> tuple[dict[str, str], list[str], list[Path], list[Path], list[Path]]:
    transcript = _read_text_if_exists(workspace / "TRANSCRIBATION.txt")
    if not transcript:
        transcript = _read_text_if_exists(workspace / "TRANSCRIBATION.srt")

    stream_notes = _read_stream_notes_context(workspace)
    marketing_takes = _read_text_if_exists(workspace / "MARKETING TAKES.md")
    producer_brief = _read_text_if_exists(workspace / "SEO AND DATA FOR VIDEO.md")
    if not producer_brief:
        producer_brief = _read_text_if_exists(workspace / SYSTEM_FILES_DIRNAME / "SEO AND DATA FOR VIDEO.md")
    article_package = _read_text_if_exists(workspace / "ARTICLES" / "article_package.md")
    if not article_package:
        article_package = _read_text_if_exists(workspace / "ARTICLES.md")
    shorts_titles = _read_text_if_exists(workspace / "shorts_titles.md")

    screenshots: list[Path] = []
    photobank = workspace / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"
    if photobank.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            screenshots.extend(sorted(photobank.glob(ext)))

    clips = sorted((workspace / "SHORTS").glob("*.mp4")) if (workspace / "SHORTS").exists() else []

    article_files: list[Path] = []
    articles_dir = workspace / "ARTICLES"
    if articles_dir.exists():
        article_files.extend(sorted(articles_dir.glob("article_*.md")))
        alias_article = articles_dir / "article.md"
        if alias_article.exists() and alias_article not in article_files:
            article_files.append(alias_article)

    used: list[str] = []
    if transcript:
        used.append("transcript")
    if stream_notes:
        used.append("stream notes")
    if marketing_takes:
        used.append("marketing takes / positioning")
    if producer_brief:
        used.append("Producer brief")
    if article_package or article_files:
        used.append("article package")
    if shorts_titles:
        used.append("Shorts titles package")
    if screenshots:
        used.append("screenshots / visual assets")

    source_map = {
        "transcript": transcript,
        "notes": stream_notes,
        "marketing": marketing_takes,
        "producer": producer_brief,
        "article": article_package,
        "shorts": shorts_titles,
    }
    return source_map, used, clips, screenshots, article_files


def _extract_source_moments_for_smm(
    transcript_text: str,
    hooks: list[str],
    fallback_niche: str,
    limit: int = 4,
) -> list[str]:
    moments = [line.strip() for line in hooks if line.strip()]
    if transcript_text:
        moments.extend(_pick_stream_quotes(transcript_text, limit=limit + 2))

    unique: list[str] = []
    for item in moments:
        clean = re.sub(r"\s+", " ", item).strip()
        if not clean:
            continue
        low = clean.lower()
        if any(low == existing.lower() for existing in unique):
            continue
        unique.append(clean)
        if len(unique) >= limit:
            break

    if not unique:
        unique = [
            f"One stream should not die after the live ends in {fallback_niche}",
            "The real bottleneck is decision-making, not content volume",
        ]
    return unique


def _build_medium_post_block(hook: str, body: str, cta: str) -> str:
    return (
        f"Hook:\n{hook}\n\n"
        f"Body:\n{body}\n\n"
        f"CTA/question:\n{cta}\n"
    )


def _adapt_medium_post(base_hook: str, base_body: str, base_cta: str, platform: str) -> str:
    if platform == "X":
        return (
            f"{base_hook}\n\n"
            f"{base_body.splitlines()[0]}\n\n"
            f"{base_cta}"
        )
    if platform == "LinkedIn":
        return (
            f"{base_hook}\n\n"
            f"{base_body}\n\n"
            f"{base_cta}"
        )
    if platform == "Facebook":
        return (
            f"{base_hook}\n\n"
            f"{base_body}\n\n"
            f"{base_cta}"
        )
    if platform == "Telegram":
        return (
            f"{base_hook}\n\n"
            f"{base_body}\n\n"
            "I am building this in public and sharing real workflow updates.\n\n"
            f"{base_cta}"
        )
    return (
        f"{base_hook}\n\n"
        f"{base_body}\n\n"
        "Would love quick feedback from the community.\n\n"
        f"{base_cta}"
    )


def _adapt_video_caption(base: str, platform: str) -> str:
    # Extract first line from base to use as platform-native hook
    first_line = (base.splitlines()[0].strip() if base else "").rstrip(".")
    if not first_line:
        first_line = "Key insight from this stream"

    if platform == "X":
        lines = [l.strip() for l in base.splitlines() if l.strip()]
        # For X: first line as hook, second line as context, last as CTA
        hook = lines[0] if lines else first_line
        context = lines[1] if len(lines) > 1 else ""
        cta = lines[-1] if len(lines) > 1 else "What part is still manual for you?"
        parts = [hook]
        if context and context != hook:
            parts.append(context)
        parts.append(cta)
        return "\n\n".join(parts)
    if platform == "LinkedIn":
        return (
            f"{base.rstrip()}\n\n"
            "Where does your process usually break: creation, adaptation, or publishing?"
        )
    if platform == "Facebook":
        return (
            f"Quick note from the stream:\n\n"
            f"{base.rstrip()}\n\n"
            "Would you use this setup in your routine?"
        )
    if platform == "TikTok":
        lines = [l.strip() for l in base.splitlines() if l.strip()]
        hook = lines[0] if lines else first_line
        return f"{hook}\n\nWould you automate this?"
    if platform == "YouTube Shorts":
        return (
            f"{base.rstrip()}\n\n"
            "Full replay and breakdown in channel content."
        )
    return base


def _adapt_article_announcement(base: str, platform: str) -> str:
    if platform == "Telegram":
        return base.replace("Link: [add link]", "Link: [add link]") + "\n\nIf useful, I can drop a short checklist version here too."
    if platform == "Facebook":
        return (
            "Published a new practical piece from this stream.\n\n"
            "It explains why content systems fail when every platform is treated separately.\n\n"
            "Link: [add link]\n\n"
            "Would this help your team workflow?"
        )
    if platform == "Discord":
        return (
            "New article is live.\n\n"
            "Focus: agents as operational workers, not only text generators.\n\n"
            "Link: [add link]\n\n"
            "Want me to post a condensed version in this channel?"
        )
    if platform == "X":
        return (
            "New article: AI agents should decide, not only generate.\n\n"
            "Operational decision logic > content volume.\n\n"
            "Read: [add link]"
        )
    if platform == "LinkedIn":
        return (
            "I published a new article based on this stream work.\n\n"
            "Main thesis: the bottleneck is distribution decisions, not text generation.\n\n"
            "Read here: [add link]\n\n"
            "Curious where this fails in your workflow today."
        )
    return base


def _adapt_visual_caption(base: str, platform: str) -> str:
    if platform == "X":
        return "One stream should be a source system, not a one-time event."
    if platform == "LinkedIn":
        return "Visual map: how one stream becomes a reusable multi-platform content pipeline."
    if platform == "Telegram":
        return base + "\n\nIf needed, I can share the same flow as a plain checklist."
    if platform == "Facebook":
        return "Simple visual: one stream can turn into many useful assets when packaging is done right."
    return base


def _derive_article_title(article_files: list[Path], stream_title: str, niche: str) -> str:
    for path in article_files:
        text = _read_text_if_exists(path)
        if not text:
            continue
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()
        if first_line.lower().startswith("title:"):
            return first_line.split(":", 1)[1].strip()
    return f"How one stream becomes a repeatable {niche} system ({stream_title})"


def _build_smm_posts_package(stream_title: str, niche: str, hooks: list[str], workspace: Path) -> str:
    source_map, used_sources, clips, screenshots, article_files = _collect_smm_source_materials(workspace)
    transcript_text = source_map.get("transcript", "")
    moments = _extract_source_moments_for_smm(transcript_text, hooks, niche, limit=6)
    today = datetime.now().strftime("%Y-%m-%d")

    # ── ALL ideas derived from actual transcript hooks — never hardcoded ──
    hook1 = hooks[0] if hooks else f"One practical insight from {niche}"
    hook2 = hooks[1] if len(hooks) > 1 else f"What I changed in my {niche} workflow"
    hook3 = hooks[2] if len(hooks) > 2 else f"The mistake I corrected while working on {niche}"
    hook4 = hooks[3] if len(hooks) > 3 else f"One thing worth testing in {niche}"

    moment1 = moments[0] if moments else hook1
    moment2 = moments[min(1, len(moments) - 1)] if moments else hook2
    moment3 = moments[min(2, len(moments) - 1)] if moments else hook3

    idea_1_hook = hook1.rstrip(".") + "."
    idea_1_body = (
        f"During the stream ({stream_title}), one specific moment stood out:\n"
        f"“{moment1}”\n\n"
        f"What this means practically: {hook2.rstrip('.')}."
    )
    idea_1_cta = f"What is your current approach to {niche}?"

    idea_2_hook = hook3.rstrip(".") + "."
    idea_2_body = (
        f"Another moment from the stream:\n"
        f"“{moment2}”\n\n"
        f"The practical implication: {hook4.rstrip('.')}."
    )
    idea_2_cta = f"Are you testing anything similar in your {niche} workflow?"

    medium_1 = _build_medium_post_block(idea_1_hook, idea_1_body, idea_1_cta)
    medium_2 = _build_medium_post_block(idea_2_hook, idea_2_body, idea_2_cta)

    clip_label = clips[0].name if clips else "n/a"
    # Caption built from actual stream hooks, not generic filler
    caption_base = (
        f"{hook1.rstrip('.')}\n\n"
        f"{hook2.rstrip('.')}\n\n"
        "Full breakdown in the stream replay.\n\n"
        f"What is your approach to {niche}?"
    )

    article_title = _derive_article_title(article_files, stream_title, niche)
    article_base = (
        f"New article from this stream: {article_title}\n\n"
        f"Main source moment: {moment3}\n"
        "Who should read it: founders, creators, and operators building repeatable content systems.\n"
        "Link: [add link]\n\n"
        f"What is still manual in your {niche} workflow today?"
    )

    visual_name = screenshots[0].name if screenshots else "n/a"
    visual_caption = (
        f"{hook1.rstrip('.')}. "
        f"This stream covered {niche} from a practical angle — one source becomes many reusable assets."
    )

    short_ask_1 = f"Quick question from today's stream on {niche}: {hook1.rstrip('.')}. How are you handling this right now?"
    short_ask_2 = f"What is the hardest part of {niche} for you — discovery, execution, or getting it distributed consistently?"

    short_status = "READY TO POST" if clips else "BLOCKED"
    article_status = "READY TO POST" if article_files else "PARTIAL"
    visual_status = "READY TO POST" if screenshots else "BLOCKED"

    return (
        f"Stream: {stream_title}\n"
        f"Date: {today}\n"
        "Source materials used:\n"
        + "\n".join(f"- {item}" for item in (used_sources or ["topic + hooks fallback only"]))
        + "\n\n"
        "Base post ideas:\n"
        "1. Idea: One stream is source material, not one post\n"
        f"   Source moment: {moments[0]}\n"
        "   Platforms: X, LinkedIn, Facebook, Telegram, Discord\n"
        "   Angle: old way vs new way\n"
        "2. Idea: Agents should decide, not only generate\n"
        f"   Source moment: {moments[min(1, len(moments) - 1)]}\n"
        "   Platforms: X, LinkedIn, Facebook, Telegram, Discord\n"
        "   Angle: strong opinion + practical workflow\n\n"
        "Medium posts:\n\n"
        "Base post 1:\n"
        f"{medium_1}\n"
        "X adaptation:\n"
        f"{_adapt_medium_post(idea_1_hook, idea_1_body, idea_1_cta, 'X')}\n\n"
        "LinkedIn adaptation:\n"
        f"{_adapt_medium_post(idea_1_hook, idea_1_body, idea_1_cta, 'LinkedIn')}\n\n"
        "Facebook adaptation:\n"
        f"{_adapt_medium_post(idea_1_hook, idea_1_body, idea_1_cta, 'Facebook')}\n\n"
        "Telegram adaptation:\n"
        f"{_adapt_medium_post(idea_1_hook, idea_1_body, idea_1_cta, 'Telegram')}\n\n"
        "Discord adaptation:\n"
        f"{_adapt_medium_post(idea_1_hook, idea_1_body, idea_1_cta, 'Discord')}\n\n"
        "Base post 2:\n"
        f"{medium_2}\n"
        "X adaptation:\n"
        f"{_adapt_medium_post(idea_2_hook, idea_2_body, idea_2_cta, 'X')}\n\n"
        "LinkedIn adaptation:\n"
        f"{_adapt_medium_post(idea_2_hook, idea_2_body, idea_2_cta, 'LinkedIn')}\n\n"
        "Facebook adaptation:\n"
        f"{_adapt_medium_post(idea_2_hook, idea_2_body, idea_2_cta, 'Facebook')}\n\n"
        "Telegram adaptation:\n"
        f"{_adapt_medium_post(idea_2_hook, idea_2_body, idea_2_cta, 'Telegram')}\n\n"
        "Discord adaptation:\n"
        f"{_adapt_medium_post(idea_2_hook, idea_2_body, idea_2_cta, 'Discord')}\n\n"
        "Short video captions:\n\n"
        "Short/video 1:\n"
        f"Source clip: {clip_label}\n"
        f"Base caption:\n{caption_base}\n\n"
        f"X caption:\n{_adapt_video_caption(caption_base, 'X')}\n\n"
        f"LinkedIn caption:\n{_adapt_video_caption(caption_base, 'LinkedIn')}\n\n"
        f"Facebook caption:\n{_adapt_video_caption(caption_base, 'Facebook')}\n\n"
        f"TikTok caption:\n{_adapt_video_caption(caption_base, 'TikTok')}\n\n"
        f"YouTube Shorts caption:\n{_adapt_video_caption(caption_base, 'YouTube Shorts')}\n\n"
        "Engagement asks:\n\n"
        "Ask 1:\n"
        f"Telegram version:\n{short_ask_1}\n\n"
        f"Discord version:\n{short_ask_1}\n\n"
        "Ask 2:\n"
        f"Telegram version:\n{short_ask_2}\n\n"
        f"Discord version:\n{short_ask_2}\n\n"
        "Article announcements:\n\n"
        f"Article: {article_title}\n"
        f"Base announcement:\n{article_base}\n\n"
        f"Telegram version:\n{_adapt_article_announcement(article_base, 'Telegram')}\n\n"
        f"Facebook version:\n{_adapt_article_announcement(article_base, 'Facebook')}\n\n"
        f"Discord version:\n{_adapt_article_announcement(article_base, 'Discord')}\n\n"
        f"X version:\n{_adapt_article_announcement(article_base, 'X')}\n\n"
        f"LinkedIn version:\n{_adapt_article_announcement(article_base, 'LinkedIn')}\n\n"
        "Visual insight posts:\n\n"
        "Visual 1:\n"
        f"Source screenshot: {visual_name}\n"
        f"Caption: {visual_caption}\n"
        "Pinterest title: One stream to many assets workflow\n"
        f"X version:\n{_adapt_visual_caption(visual_caption, 'X')}\n\n"
        f"LinkedIn version:\n{_adapt_visual_caption(visual_caption, 'LinkedIn')}\n\n"
        f"Telegram version:\n{_adapt_visual_caption(visual_caption, 'Telegram')}\n\n"
        f"Facebook version:\n{_adapt_visual_caption(visual_caption, 'Facebook')}\n\n"
        "Notes for SMM Head:\n"
        f"- Medium posts: READY TO POST\n"
        f"- Short video captions: {short_status}\n"
        f"- Article announcements: {article_status}\n"
        f"- Engagement asks: READY TO POST\n"
        f"- Visual insight posts: {visual_status}\n"
        "- Missing assets policy: request only base assets if BLOCKED (for example: missing Shorts clip, missing article link, missing screenshots).\n"
    )


def _build_smm_data(stream_title: str, niche: str, hooks: list[str]) -> str:
    best_hook = hooks[0] if hooks else f"One practical lesson from {niche}"
    second_hook = hooks[1] if len(hooks) > 1 else f"One mistake I corrected during this stream"
    return (
        "# SMM DATA\n\n"
        f"- Stream: {stream_title}\n"
        f"- Niche: {niche}\n"
        "- Role: SMM adapter and packager\n"
        "- Main rule: create base ideas first, then adapt per platform\n\n"
        "## Core reusable insights\n"
        f"- {best_hook}\n"
        f"- {second_hook}\n\n"
        "## Package output\n"
        "- Use smm_posts_package.md as the main posting pack for X, LinkedIn, Telegram, Facebook, and Discord.\n"
    )


def _safe_hook(hooks: list[str], index: int, fallback: str) -> str:
    if not hooks:
        return fallback
    return hooks[min(index, len(hooks) - 1)]


def _human_presence_templates(stream_title: str, niche: str, hooks: list[str]) -> dict[str, str]:
    h1 = _safe_hook(hooks, 0, f"One practical insight from {niche}")
    h2 = _safe_hook(hooks, 1, f"A mistake to avoid in {niche}")
    h3 = _safe_hook(hooks, 2, f"What changed in my approach to {niche}")

    return {
        "LINKEDIN": f"""# LinkedIn Human Presence

## Stream Announcement
Going live today: {stream_title}
Focus: {niche}
Bring one real problem and we can deconstruct it live.

## Personal Recap
Today from the stream:
- {h1}
- {h2}
- {h3}

What are you currently testing in your workflow?
""",
        "X": f"""# X Human Presence

## Pre-stream Tweet
Going live soon: {stream_title}
Topic: {niche}

## Recap Tweet
Main takeaway: {h1}

## Reflection Tweet
I changed my mind about one thing today:
{h2}
""",
        "DISCORD": f"""# Discord Human Presence

## Announcement
New stream session: {stream_title}

## Quick Notes
- {h1}
- {h2}

Drop your blocker and I will include it in the next stream.
""",
        "FACEBOOK": f"""# Facebook Human Presence

## Replay Post
Replay is available: {stream_title}

If you are building in {niche}, this stream is practical and focused.

## Behind-the-scenes Post
One unexpected thing from today:
{h3}
""",
        "TELEGRAM": f"""# Telegram Human Presence

## Announcement
New stream is live: {stream_title}

## Short voice-note script
Main point: {h1}
If useful, I will share a compact 5-step checklist here.
""",
        "INSTAGRAM": f"""# Instagram Human Presence

## Caption Draft
Stream in one line: {h1}

## Story Sequence
1) Topic card
2) Key lesson: {h2}
3) CTA to replay
""",
        "PINTEREST": f"""# Pinterest Human Presence

## Pin Copy
Title: Stream insights: {stream_title}
Description: {h1}. Practical {niche} ideas from a live session.
""",
    }


def _build_presence_schedule() -> str:
    return """# SOCIAL PRESENCE SCHEDULE

Goal: make accounts feel active and human, not robotic.

## Daily cadence

1. Pre-stream short announcement
2. Immediate post-stream key insight
3. End-of-day personal recap

## Recommended ratio

- 40% personal observations
- 35% practical tips/checklists
- 25% direct promotion

## Human behavior rules

- Write in first person from real stream context.
- Include at least one uncertainty, correction, or lesson.
- Ask one audience question daily on at least one platform.
- Vary CTA type (reply, comment, watch replay, share blocker).
"""


def _write_social_presence_files(workspace: Path, stream_title: str, niche: str, hooks: list[str]) -> list[str]:
    templates = _human_presence_templates(stream_title, niche, hooks)
    written: list[str] = []
    for platform, content in templates.items():
        path = workspace / platform / "HUMAN_POSTS.md"
        _write_text(path, content)
        written.append(str(path))

    schedule_path = workspace / "SMM" / "SOCIAL PRESENCE SCHEDULE.md"
    _write_text(schedule_path, _build_presence_schedule())
    written.append(str(schedule_path))
    return written


def _build_articles(stream_title: str, niche: str, hooks: list[str], phrases: list[str]) -> str:
    key_points = "\n".join(f"- {line}" for line in hooks[:5]) if hooks else "- Key points will be filled from transcript"
    keywords = ", ".join(phrases[:12]) if phrases else niche
    return f"""# ARTICLES

## Medium Draft
Title: What This Live Stream Taught Me About {niche}

Intro:
In this session ({stream_title}), I focused on actionable decisions, not theory.

Core points:
{key_points}

Conclusion:
Use this stream as a baseline, then adapt each step to your context.

## Substack Draft
Working title: Weekly Field Notes on {niche}

Angle:
- What changed since last approach
- What failed and why
- What to test next week

## SEO Keyword Pool
{keywords}
"""


_ARTICLE_SYSTEM_PROMPT = (
    "You are an expert long-form content writer. "
    "Write a single comprehensive article that is detailed, engaging, and publication-ready. "
    "The article must be at least 1500 characters. "
    "Structure it as follows:\n"
    "1. SEO-optimised title (H1)\n"
    "2. Meta description (1-2 sentences, ≤155 chars, labelled 'Meta:')\n"
    "3. Introduction (strong hook, 2-3 paragraphs)\n"
    "4. At least 4 main sections with H2 headings and rich body text\n"
    "5. Inside the body, insert exactly 3 image placeholders at natural breakpoints "
    "using the exact syntax: [IMAGE_1], [IMAGE_2], [IMAGE_3]\n"
    "6. FAQ section with 3-4 questions and detailed answers\n"
    "7. Conclusion with a strong call-to-action\n"
    "8. Final section 'Where to follow' with links to YouTube and X\n\n"
    "Rules: write in first person, use only facts from the transcript, "
    "no fabricated statistics, keep language clear and direct, and format in clean Markdown."
)


def _pick_stream_quotes(transcript_text: str, limit: int = 3) -> list[str]:
    quotes: list[str] = []
    for raw in transcript_text.splitlines():
        line = re.sub(r"^\[\d{2}:\d{2}:\d{2}\s*-\s*\d{2}:\d{2}:\d{2}\]\s*", "", raw).strip()
        if len(line) < 50:
            continue
        if len(line) > 260:
            line = line[:257].rstrip() + "..."
        if line and line not in quotes:
            quotes.append(line)
        if len(quotes) >= limit:
            break
    return quotes


def _ensure_min_article_size(article_text: str, stream_title: str, niche: str, hooks: list[str], phrases: list[str]) -> str:
    if len(article_text) >= 1500:
        return article_text
    checklist = "\n".join(f"- {h}" for h in (hooks[:5] or [f"Apply one tactic from {niche} today"]))
    keyword_tail = ", ".join(phrases[:10]) if phrases else niche
    result = article_text
    extension = (
        "\n\n## Practical Checklist From This Stream\n"
        f"Use this short checklist right after watching {stream_title}:\n"
        f"{checklist}\n\n"
        "## Implementation Notes\n"
        f"Start from one decision, test it for 7 days, then iterate. Focus area: {niche}.\n"
        f"Keywords to keep in your publishing loop: {keyword_tail}.\n"
    )
    result += extension

    pad_index = 1
    while len(result) < 1500:
        result += (
            f"\n\n## Extended Notes {pad_index}\n"
            f"During this stream I focused on practical execution in {niche}, not theory. "
            "The key is to ship one small improvement, measure the result, and keep iteration speed high. "
            f"If you apply this to {stream_title}, you can build a repeatable process instead of random attempts."
        )
        pad_index += 1

    return result


def _append_stream_inserts_and_links(article_text: str, transcript_text: str) -> str:
    youtube_url, x_url = _creator_profile_links()
    quotes = _pick_stream_quotes(transcript_text, limit=3)
    parts = [article_text.strip()]

    if quotes and "## Inserts from stream" not in article_text:
        quote_block = "\n".join(f"> {quote}" for quote in quotes)
        parts.append("## Inserts from stream\n" + quote_block)

    if "## Where to follow" not in article_text:
        parts.append(
            "## Where to follow\n"
            f"- YouTube: {youtube_url}\n"
            f"- X: {x_url}\n\n"
            "If this article helped, share one key insight and tag me so I can respond with a deeper breakdown."
        )

    return "\n\n".join(parts).strip() + "\n"


def _build_article_idea_map(
    stream_title: str,
    niche: str,
    hooks: list[str],
    notes_context: str,
) -> list[dict[str, object]]:
    h1 = hooks[0] if hooks else f"One strong shift in {niche}"
    h2 = hooks[1] if len(hooks) > 1 else f"One practical system lesson from {niche}"
    h3 = hooks[2] if len(hooks) > 2 else f"What broke in the old way of {niche}"

    candidates: list[dict[str, object]] = [
        {
            "title": "AI agents are operational workers, not content toys",
            "thesis": "The biggest value of AI agents is decision-making and execution, not text generation.",
            "target_reader": "Founder or creator building repeatable content systems",
            "why": "Directly addresses why most automation stacks still fail in practice.",
            "source_moment": h1,
            "article_type": "Opinion / thesis article",
            "priority": 10,
        },
        {
            "title": "How one stream becomes a full content distribution system",
            "thesis": "A stream should be treated as source material that feeds a full asset pipeline.",
            "target_reader": "Creator, agency owner, or SMM operator",
            "why": "Provides clear practical model from source to publishing queue.",
            "source_moment": h2,
            "article_type": "System breakdown",
            "priority": 10,
        },
        {
            "title": "The future SMM manager is an agent workflow operator",
            "thesis": "Manual posting is being replaced by orchestration and decision systems.",
            "target_reader": "SMM manager and small marketing teams",
            "why": "Shows role shift and gives practical operational framework.",
            "source_moment": h3,
            "article_type": "Market insight",
            "priority": 9,
        },
        {
            "title": "The biggest mistake in content automation is generating too much",
            "thesis": "Without editorial decision logic, automation creates noise instead of growth.",
            "target_reader": "Anyone overwhelmed by content operations",
            "why": "Strong pain point with tactical fixes and quality-control lens.",
            "source_moment": h1,
            "article_type": "Mistake / lesson article",
            "priority": 9,
        },
        {
            "title": "What building FabricBot taught me about creator leverage",
            "thesis": "Small teams can compete with larger teams using specialized agents and shared base assets.",
            "target_reader": "Builder, founder, solo creator",
            "why": "Personal founder angle with reusable system insights.",
            "source_moment": h2,
            "article_type": "Founder note",
            "priority": 8,
        },
        {
            "title": "Why content automation breaks when every platform is treated separately",
            "thesis": "Platform-native adaptation works best after creating common base assets.",
            "target_reader": "Multi-platform operator",
            "why": "Solves duplicated work and improves distribution consistency.",
            "source_moment": h3,
            "article_type": "Case study",
            "priority": 8,
        },
    ]

    note_low = notes_context.lower()
    if "telegram" in note_low:
        candidates.append(
            {
                "title": "Why Telegram can become the operational layer for creator businesses",
                "thesis": "Telegram can act as the action layer where decisions and audience loops converge.",
                "target_reader": "Founder using Telegram for growth",
                "why": "High practical relevance for audience and automation stack.",
                "source_moment": h1,
                "article_type": "Market insight",
                "priority": 9,
            }
        )

    return candidates


def _select_article_ideas(ideas: list[dict[str, object]], min_count: int = 2, max_count: int = 5) -> list[dict[str, object]]:
    ordered = sorted(ideas, key=lambda item: int(item.get("priority") or 0), reverse=True)
    take = max(min_count, min(max_count, len(ordered), 3 if len(ordered) >= 3 else len(ordered)))
    return ordered[:take]


def _build_article_fallback(
    stream_title: str,
    niche: str,
    transcript_text: str,
    hooks: list[str],
    phrases: list[str],
    idea: dict[str, object],
) -> str:
    title = str(idea.get("title") or f"Practical lessons from {stream_title}")
    thesis = str(idea.get("thesis") or f"One stream can build a complete {niche} system")
    target_reader = str(idea.get("target_reader") or "Creators and founders")
    source_moment = str(idea.get("source_moment") or (hooks[0] if hooks else "Core workflow insight"))
    keywords = ", ".join(phrases[:10]) if phrases else niche

    body = (
        f"Title: {title}\n"
        f"Subtitle: a builder-level breakdown from {stream_title}\n"
        f"Source stream: {stream_title}\n"
        f"Core thesis: {thesis}\n"
        f"Target reader: {target_reader}\n"
        "Suggested platforms: Medium, LinkedIn, X, Telegram, Facebook, Discord\n"
        f"Suggested tags: {keywords}\n\n"
        "Article body:\n\n"
        f"Most people approach {niche} as a generation problem. I think that is the wrong starting point. "
        "The real bottleneck is decision quality: what to publish, where to publish it, and how to adapt one core idea across platforms without duplicating work. "
        "That was the central pattern I kept seeing while building and testing the FabricBot workflow.\n\n"
        "The problem is concrete. Teams and creators spend hours writing posts manually, reformatting the same points again and again, and still lose the strongest moments from streams. "
        "You can generate more text with AI, but if you do not have a system for asset reuse and posting decisions, output volume just becomes noise.\n\n"
        f"The stream moment that captured this best was: {source_moment}. "
        "That line is important because it reframes automation from content quantity to operational leverage. "
        "When the source material is strong, one stream can power multiple downstream assets with consistent positioning.\n\n"
        "In FabricBot, I treat a stream as source material, not as one isolated piece of content. "
        "The system first extracts key moments and phrases, then cuts Shorts, then builds long-form pieces, then prepares adapted social formats. "
        "The key shift is that agents are specialized by role: producer logic for titles and packaging, SMM logic for distribution, and article logic for long-form depth.\n\n"
        "A practical framework looks like this: source material, base assets, role-specific agents, platform adaptation, posting queue, and quality loop. "
        "Source material is transcript plus notes. Base assets are clips, hooks, and one clear thesis per piece. Agent roles prevent random generic output. "
        "Adaptation ensures each platform keeps native tone while sharing the same core argument.\n\n"
        "Here is a concrete example. One stream can become one long YouTube video, several Shorts, several long-form article angles, short-form posts for multiple channels, and announcement variants for community platforms. "
        "This only works if each output points back to a shared thesis instead of splitting into disconnected messages.\n\n"
        "Why this matters is simple: creator leverage. Small teams do not need to out-hire bigger teams if they can out-operate them. "
        "Operational agents can reduce repetitive execution and keep strategic decisions visible. That means more consistency, faster publishing cycles, and better reuse of strong source material.\n\n"
        "There are risks. Over-automation can create bland writing. Weak editorial taste can produce safe but forgettable content. "
        "If every generated piece sounds the same, trust drops. The fix is to keep one sharp thesis per article, include concrete examples, and always run a quality gate before publishing.\n\n"
        f"The final insight is this: the advantage is not generating more about {niche}; it is building a system that knows what to do next with every strong idea. "
        "The hard part is not writing. The hard part is operational decision-making.\n\n"
        "CTA:\n"
        "I am building this in public with FabricBot. Follow if you want real examples of how specialized agents change content operations.\n\n"
        "LinkedIn adaptation:\n"
        f"Most automation stacks in {niche} fail at decision-making, not generation. I broke down a practical system from source stream to multi-platform outputs.\n\n"
        "X adaptation:\n"
        f"The real bottleneck in {niche} is decision logic, not text generation. One stream can become a full asset system if roles are specialized.\n\n"
        "Telegram announcement:\n"
        f"New long-form breakdown: {title}. I shared the exact model I use to turn one stream into multiple high-quality assets.\n\n"
        "Facebook announcement:\n"
        f"Published a practical article on {niche} systems. Focus: how to stop manual duplication and keep one thesis across platforms.\n\n"
        "Discord announcement:\n"
        "Dropped a new long-form article with framework + mistakes + practical next steps. I can share a checklist if useful.\n\n"
        "Quote card ideas:\n"
        "- The real advantage is not generation. It is decision-making.\n"
        "- One stream is source material for a whole system, not one post.\n"
        "- A good content agent should decide, not just write.\n\n"
        "Visual/screenshot ideas:\n"
        "- Pipeline map: stream -> clips -> articles -> posting queue.\n"
        "- Agent roles board: producer / SMM / article creator.\n"
        "- Before vs after: manual workflow vs agentic workflow.\n\n"
        "Editor self-review:\n"
        "- Thesis check: clear and specific.\n"
        "- Hook check: concrete and non-generic.\n"
        "- Specificity check: includes FabricBot workflow examples.\n"
        "- Depth check: practical framework + risks + strategic shift.\n"
        "- Repetition check: limited repetition, each section adds value.\n"
        "- Generic language check: uses builder voice, avoids corporate filler.\n"
        "- Platform check: publishable as Medium long-form piece.\n"
        "- FabricBot check: explicitly connected to FabricBot positioning.\n"
        "- Reader value check: gives an actionable operating model.\n"
        "- Final line check: ends with strong operational insight.\n"
    )

    body = _ensure_min_article_size(body, stream_title, niche, hooks, phrases)
    body = _append_stream_inserts_and_links(body, transcript_text)
    return body


def _generate_article_package(
    workspace: Path,
    stream_title: str,
    niche: str,
    transcript_text: str,
    hooks: list[str],
    phrases: list[str],
) -> tuple[list[str], list[dict[str, object]], list[dict[str, object]]]:
    notes_context = _read_stream_notes_context(workspace)
    idea_map = _build_article_idea_map(stream_title, niche, hooks, notes_context)
    selected = _select_article_ideas(idea_map, min_count=2, max_count=5)

    articles_dir = workspace / "ARTICLES"
    articles_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY", "").strip() or _get_secret_from_local_env("OPENAI_API_KEY")
    chat_model = (
        os.getenv("OPENAI_CHAT_MODEL", "").strip()
        or _get_secret_from_local_env("OPENAI_CHAT_MODEL")
        or "gpt-4o-mini"
    )

    transcript_excerpt = _clip_text_budget(transcript_text, 9000)
    screenshots = _pick_article_screenshots(workspace, count=3)
    generated_files: list[str] = []
    selected_rows: list[dict[str, object]] = []

    for idx, idea in enumerate(selected, start=1):
        title = str(idea.get("title") or f"Article {idx}")
        article_path = articles_dir / f"article_{idx:02d}.md"
        status = "template"
        article_text = ""

        llm_available = bool(
            api_key
            or os.getenv("GITHUB_COPILOT_TOKEN", "").strip()
            or _get_secret_from_local_env("GITHUB_COPILOT_TOKEN")
        )
        if llm_available:
            prompt = (
                "Create one long-form article package from this idea. "
                "Use sentence case and builder language. Avoid banned corporate words like revolutionary, innovative, next-gen, deep dive, leveraging.\n\n"
                f"Stream title: {stream_title}\n"
                f"Niche: {niche}\n"
                f"Idea title: {title}\n"
                f"Core thesis: {idea.get('thesis')}\n"
                f"Target reader: {idea.get('target_reader')}\n"
                f"Source moment: {idea.get('source_moment')}\n"
                "Required output sections exactly: Title, Subtitle, Source stream, Core thesis, Target reader, Suggested platforms, Suggested tags, Article body, CTA, LinkedIn adaptation, X adaptation, Telegram announcement, Facebook announcement, Discord announcement, Quote card ideas, Visual/screenshot ideas, Editor self-review.\n"
                "Article body target: 1200-2500 words, minimum 900 words only if very narrow.\n"
                "Include practical framework, one risk/mistake section, and one strong final insight.\n\n"
                f"Notes context:\n{_clip_text_budget(notes_context, 2500)}\n\n"
                f"Transcript excerpt:\n{transcript_excerpt}\n"
            )
            try:
                article_text = _call_llm(
                    messages=[
                        {"role": "system", "content": "You are a founder-level long-form editor for FabricBot."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=4200,
                )
                status = "ai"
            except Exception:
                article_text = ""

        if not article_text:
            article_text = _build_article_fallback(stream_title, niche, transcript_text, hooks, phrases, idea)
            status = "template"

        if screenshots:
            article_text = _embed_screenshots_in_article(article_text, screenshots, articles_dir)

        article_text = _ensure_min_article_size(article_text, stream_title, niche, hooks, phrases)
        article_text = _append_stream_inserts_and_links(article_text, transcript_text)
        _write_text(article_path, article_text)
        generated_files.append(str(article_path))
        selected_rows.append(
            {
                "file": article_path.name,
                "title": title,
                "thesis": str(idea.get("thesis") or ""),
                "platforms": "Medium, LinkedIn, X, Telegram, Facebook, Discord",
                "status": status,
            }
        )

    # Backward compatibility with previous single-article consumers.
    if generated_files:
        first = Path(generated_files[0])
        _write_text(articles_dir / "article.md", first.read_text(encoding="utf-8"))
        generated_files.append(str(articles_dir / "article.md"))

    return generated_files, idea_map, selected_rows


def _build_articles_index(
    stream_title: str,
    idea_map: list[dict[str, object]],
    selected_rows: list[dict[str, object]],
) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [
        f"Stream: {stream_title}",
        f"Date: {date}",
        "Source materials used: transcript, stream notes, marketing takes, producer brief (if present), screenshots/context files (if present)",
        "",
        "Article idea map:",
        "",
    ]

    for idx, item in enumerate(idea_map, start=1):
        lines.extend(
            [
                f"{idx}. Title: {item.get('title')}",
                f"   Thesis: {item.get('thesis')}",
                f"   Target reader: {item.get('target_reader')}",
                f"   Why it is interesting: {item.get('why')}",
                f"   Source moment: {item.get('source_moment')}",
                f"   Priority score: {item.get('priority')}",
                "",
            ]
        )

    lines.extend(["Selected articles:", ""])
    for idx, row in enumerate(selected_rows, start=1):
        lines.extend(
            [
                f"{idx}. File: {row.get('file')}",
                f"   Title: {row.get('title')}",
                f"   Thesis: {row.get('thesis')}",
                f"   Platforms: {row.get('platforms')}",
                f"   Status: {row.get('status')}",
                "",
            ]
        )

    lines.extend(
        [
            "Notes for SMM Manager:",
            "- Prioritize top-2 article angles for Medium and LinkedIn first.",
            "- Reuse quote-card lines for Telegram, X, and Facebook announcements.",
            "- Keep one thesis per post to avoid message dilution.",
            "",
        ]
    )

    return "\n".join(lines)


def _pick_article_screenshots(workspace: Path, count: int = 3) -> list[Path]:
    """Return up to `count` screenshot paths from the photobank, evenly spread."""
    photobank = workspace / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"
    candidates: list[Path] = []
    if photobank.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            candidates.extend(sorted(photobank.glob(ext)))
    # exclude PHOTOBANK_INDEX.md and non-images just in case
    candidates = [p for p in candidates if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if not candidates:
        return []
    if len(candidates) <= count:
        return candidates
    # pick evenly spaced
    step = len(candidates) / count
    return [candidates[int(i * step)] for i in range(count)]


def _embed_screenshots_in_article(article_text: str, screenshots: list[Path], articles_dir: Path) -> str:
    """Copy screenshots into ARTICLES/ and replace [IMAGE_N] placeholders with relative Markdown image links."""
    for i, src_path in enumerate(screenshots, start=1):
        dest_name = f"screenshot_{i:02d}{src_path.suffix}"
        dest_path = articles_dir / dest_name
        if not dest_path.exists():
            shutil.copy2(src_path, dest_path)
        placeholder = f"[IMAGE_{i}]"
        md_image = f"\n![Stream screenshot {i}]({dest_name})\n"
        article_text = article_text.replace(placeholder, md_image, 1)
    # Remove any unused placeholders (e.g. if fewer than 3 screenshots exist)
    article_text = re.sub(r"\[IMAGE_\d+\]", "", article_text)
    return article_text


def _generate_ai_articles(
    workspace: Path,
    stream_title: str,
    niche: str,
    transcript_text: str,
    hooks: list[str],
    phrases: list[str],
    count: int = 1,
) -> list[str]:
    """Generate one long-form AI article with embedded screenshots via OpenAI Chat Completions."""
    copilot_token = os.getenv("GITHUB_COPILOT_TOKEN", "").strip() or _get_secret_from_local_env("GITHUB_COPILOT_TOKEN")
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or _get_secret_from_local_env("OPENAI_API_KEY")
    if not api_key and not copilot_token:
        return []

    articles_dir = workspace / "ARTICLES"
    articles_dir.mkdir(parents=True, exist_ok=True)

    screenshots = _pick_article_screenshots(workspace, count=3)

    # Truncate transcript to ~12000 chars for a richer long-form article
    transcript_excerpt = _clip_text_budget(transcript_text, 8000)
    hooks_text = "\n".join(f"- {h}" for h in hooks[:8]) if hooks else f"- {niche} insights"
    keywords = ", ".join(phrases[:14]) if phrases else niche

    screenshot_note = (
        "The article body must contain exactly 3 image placeholders: [IMAGE_1], [IMAGE_2], [IMAGE_3]. "
        "Place them at natural section breaks (after introductory section, in the middle, near the conclusion)."
        if screenshots
        else "Do not include any image placeholders."
    )

    user_prompt = (
        f"Stream title: {stream_title}\n"
        f"Content niche: {niche}\n"
        f"Key hooks from the stream:\n{hooks_text}\n"
        f"SEO keyword pool: {keywords}\n\n"
        f"Transcript:\n{transcript_excerpt}\n\n"
        f"{screenshot_note}\n\n"
        "Write a comprehensive formatted article (minimum 1500 characters) based strictly on the content above. "
        "In the end, include a beautiful 'Where to follow' section with YouTube and X links."
    )

    try:
        print(f"[articles] Generating long-form article via LLM…")
        article_text = _call_llm(
            messages=[
                {"role": "system", "content": _ARTICLE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3200,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[articles] Generation failed: {exc}")
        return []

    if screenshots:
        article_text = _embed_screenshots_in_article(article_text, screenshots, articles_dir)

    article_text = _ensure_min_article_size(article_text, stream_title, niche, hooks, phrases)
    article_text = _append_stream_inserts_and_links(article_text, transcript_text)

    out_path = articles_dir / "article.md"
    _write_text(out_path, article_text + "\n")
    print(f"[articles] Saved: {out_path} ({len(article_text)} chars, {len(screenshots)} screenshots embedded)")

    return [str(out_path)]


def _short_thumbnail_text(text: str, max_words: int = 5) -> str:
    # strip pure-digit or timestamp tokens (e.g. "00", "02", "10")
    words = [
        w for w in re.findall(r"[A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9_]*", text.upper())
        if len(w) > 1
    ]
    if not words:
        return "REAL SYSTEM"
    clipped = words[:max_words]
    return " ".join(clipped)


def _fit_cover(image, target_w: int, target_h: int):
    import cv2

    h, w = image.shape[:2]
    if h <= 0 or w <= 0:
        return cv2.resize(image, (target_w, target_h))
    scale = max(target_w / w, target_h / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    x1 = max(0, (nw - target_w) // 2)
    y1 = max(0, (nh - target_h) // 2)
    return resized[y1:y1 + target_h, x1:x1 + target_w]


def _draw_text_with_outline(image, text: str, x: int, y: int, scale: float, color, thickness: int) -> None:
    import cv2

    outline = max(2, thickness + 2)
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, scale, (0, 0, 0), outline, cv2.LINE_AA)
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, scale, color, thickness, cv2.LINE_AA)


def _draw_icon_badge(image, center_x: int, center_y: int, style: str = "arrow") -> None:
    import cv2
    import numpy as np

    r = 44
    overlay = image.copy()
    cv2.circle(overlay, (center_x, center_y), r, (30, 30, 220), -1)
    cv2.addWeighted(overlay, 0.85, image, 0.15, 0, image)

    if style == "bolt":
        pts = np.array([
            [center_x - 8, center_y - 20],
            [center_x + 6, center_y - 20],
            [center_x - 2, center_y - 2],
            [center_x + 10, center_y - 2],
            [center_x - 10, center_y + 22],
            [center_x - 2, center_y + 4],
            [center_x - 14, center_y + 4],
        ], dtype=np.int32)
        cv2.fillPoly(image, [pts], (255, 255, 255))
        return

    pts = np.array([
        [center_x - 16, center_y - 8],
        [center_x + 6, center_y - 8],
        [center_x + 6, center_y - 16],
        [center_x + 24, center_y],
        [center_x + 6, center_y + 16],
        [center_x + 6, center_y + 8],
        [center_x - 16, center_y + 8],
    ], dtype=np.int32)
    cv2.fillPoly(image, [pts], (255, 255, 255))


def _generate_local_thumbnails(
    workspace: Path,
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    count: int = 3,
) -> list[str]:
    import cv2
    import numpy as np

    thumb_dir = workspace / "THUMBNAILS"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    photobank_dir = workspace / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"
    candidates = sorted(photobank_dir.glob("*.jpg")) + sorted(photobank_dir.glob("*.png"))

    if not candidates:
        base = np.zeros((720, 1280, 3), dtype=np.uint8)
        for y in range(720):
            t = y / 720.0
            base[y, :, 0] = int(28 + 40 * t)
            base[y, :, 1] = int(18 + 18 * t)
            base[y, :, 2] = int(62 + 36 * t)
    else:
        raw = cv2.imread(str(candidates[0]))
        base = _fit_cover(raw, 1280, 720) if raw is not None else np.zeros((720, 1280, 3), dtype=np.uint8)

    headline_pool = [
        _short_thumbnail_text(hooks[0], 4) if hooks else "DAILY SYSTEM",
        _short_thumbnail_text(hooks[1], 4) if len(hooks) > 1 else "REAL WORKFLOW",
        _short_thumbnail_text(f"{niche} {stream_title}", 4),
    ]

    saved: list[str] = []
    for idx in range(max(1, count)):
        canvas = base.copy()

        # Darken lower zone to keep text readable.
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 390), (1280, 720), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.56, canvas, 0.44, 0, canvas)

        # Accent ribbon for title.
        ribbon = canvas.copy()
        cv2.rectangle(ribbon, (46, 430), (980, 620), (35, 20, 170), -1)
        cv2.addWeighted(ribbon, 0.82, canvas, 0.18, 0, canvas)

        head = headline_pool[idx % len(headline_pool)]
        sub = " ".join([w.upper() for w in phrases[:3]]) if phrases else "STREAM INSIGHTS"
        sub = _short_thumbnail_text(sub, 5)

        _draw_text_with_outline(canvas, head, 80, 520, 1.7, (255, 255, 255), 3)
        _draw_text_with_outline(canvas, sub, 82, 580, 0.95, (250, 220, 255), 2)

        icon_style = "bolt" if idx % 2 else "arrow"
        _draw_icon_badge(canvas, 1105, 515, style=icon_style)

        out = thumb_dir / f"thumbnail_{idx + 1:02d}.png"
        cv2.imwrite(str(out), canvas)
        saved.append(str(out))

    seo_title = [
        f"{stream_title}: {_short_thumbnail_text(hooks[0], 5) if hooks else niche}",
        f"{_short_thumbnail_text(niche, 4)} - Daily Stream Breakdown",
        f"How to Build {_short_thumbnail_text(niche, 3)} Workflow",
    ]
    seo_text = (
        "# THUMBNAIL SEO NOTES\n\n"
        "## Suggested Video Titles\n"
        + "\n".join(f"- {line}" for line in seo_title)
        + "\n\n## Suggested Alt Text\n"
        + "- High-contrast stream thumbnail with expressive face, bold headline, and icon accent.\n"
        + "- Visual summary of stream insights with strong mobile readability.\n"
    )
    _write_text(thumb_dir / "SEO_NOTES.md", seo_text)
    saved.append(str(thumb_dir / "SEO_NOTES.md"))

    return saved


def _build_openai_thumbnail_prompt(stream_title: str, niche: str, head: str, sub: str, variant: int) -> str:
    _CHANNEL_STYLE = (
        "Channel visual identity: dark cinematic background (deep navy or near-black), "
        "electric blue or neon accent color, bold white uppercase headline with subtle outer glow, "
        "high-contrast layout, expressive close-up face of the presenter on one side. "
        "Mobile-first — readable at 200px thumbnail width. FabricBot / AI automation creator aesthetic."
    )
    layout = ["face right, text left", "face left, text right", "face center, text overlay at top"][
        (variant - 1) % 3
    ]
    return (
        f"Design a high-CTR YouTube thumbnail in 16:9 format (1280×720px). "
        f"{_CHANNEL_STYLE} "
        f"Stream: '{stream_title}'. Niche: '{niche}'. "
        f"Headline text on image: '{head}'. Sub-text: '{sub}'. "
        f"Layout variant {variant}: {layout}. "
        "Max 6 words total on image. No clutter. No tiny text. "
        "If a presenter photo is provided, use the real face prominently."
    )


_FONT_HEADLINE = "/System/Library/Fonts/Supplemental/Impact.ttf"
_FONT_SUB = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
_FONT_FALLBACK = "/System/Library/Fonts/HelveticaNeue.ttc"

_THUMB_PALETTES = [
    # (gradient_top, gradient_bottom, accent, text_color)
    ((10, 10, 30), (0, 0, 80), (0, 180, 255), (255, 255, 255)),       # electric blue
    ((80, 20, 0), (180, 60, 0), (255, 200, 0), (255, 255, 255)),       # warm orange/gold
    ((20, 0, 50), (60, 0, 100), (50, 255, 120), (255, 255, 255)),      # purple/neon green
]


def _make_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Any:
    from PIL import Image
    img = Image.new("RGB", (w, h))
    pix = img.load()
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            pix[x, y] = (r, g, b)
    return img


def _load_font(path: str, size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_FONT_FALLBACK, size)
        except Exception:
            return ImageFont.load_default()


def _draw_text_with_shadow(draw, xy, text, font, fill, shadow=(0, 0, 0, 180), offset=4):
    from PIL import Image, ImageDraw
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def _compose_thumbnail(
    w: int,
    h: int,
    headline: str,
    subtext: str,
    niche: str,
    palette_index: int,
    bg_image_path: str | None,
) -> Any:
    from PIL import Image, ImageDraw, ImageFilter
    import textwrap

    gt, gb, accent, tc = _THUMB_PALETTES[palette_index % len(_THUMB_PALETTES)]

    # Background
    if bg_image_path:
        try:
            bg = Image.open(bg_image_path).convert("RGB").resize((w, h), Image.LANCZOS)
            # Darken significantly so text is readable
            overlay = _make_gradient(w, h, gt + (0,), gb + (0,))  # type: ignore[arg-type]
            # Blend: 55% bg photo, 45% solid gradient
            bg = Image.blend(bg, overlay, alpha=0.55)
            # Extra darkening pass
            dark = Image.new("RGB", (w, h), (0, 0, 0))
            bg = Image.blend(bg, dark, alpha=0.3)
        except Exception:
            bg = _make_gradient(w, h, gt, gb)
    else:
        bg = _make_gradient(w, h, gt, gb)

    draw = ImageDraw.Draw(bg)

    # Accent bar at bottom
    bar_h = max(8, h // 40)
    draw.rectangle([(0, h - bar_h), (w, h)], fill=accent)

    # Headline text — wrap to 2 lines max
    font_size = max(60, w // 9)
    font_h = _load_font(_FONT_HEADLINE, font_size)
    lines = textwrap.wrap(headline.upper(), width=12)[:2]
    y_cursor = h // 4
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_h)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        _draw_text_with_shadow(draw, (x, y_cursor), line, font_h, fill=tc, offset=max(3, font_size // 20))
        y_cursor += bbox[3] - bbox[1] + int(font_size * 0.15)

    # Sub-text
    font_size_sub = max(30, w // 20)
    font_s = _load_font(_FONT_SUB, font_size_sub)
    sub_lines = textwrap.wrap(subtext.upper(), width=20)[:2]
    for line in sub_lines:
        bbox = draw.textbbox((0, 0), line, font=font_s)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        _draw_text_with_shadow(draw, (x, y_cursor + 20), line, font_s,
                               fill=accent, offset=max(2, font_size_sub // 18))
        y_cursor += bbox[3] - bbox[1] + int(font_size_sub * 0.2) + 20

    # Niche tag bottom-left
    font_tag = _load_font(_FONT_SUB, max(18, w // 50))
    draw.text((20, h - bar_h - 36), niche.upper(), font=font_tag, fill=accent)

    return bg


def _generate_pillow_thumbnails(
    workspace: Path,
    stream_title: str,
    niche: str,
    hooks: list[str],
    count: int = 3,
) -> list[str]:
    """Fully automated local thumbnail compositor using Pillow. No API needed."""
    thumb_dir = workspace / "THUMBNAILS"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    headline = _short_thumbnail_text(hooks[0], 4) if hooks else stream_title
    subtext = _short_thumbnail_text(hooks[1], 5) if len(hooks) > 1 else niche

    # Find best photobank image
    photobank_dir = workspace / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"
    bg_image: str | None = None
    if photobank_dir.exists():
        for ext in ("*.jpg", "*.png", "*.jpeg"):
            candidates = sorted(photobank_dir.glob(ext))
            if candidates:
                bg_image = str(candidates[0])
                break

    saved: list[str] = []
    for i in range(min(count, len(_THUMB_PALETTES))):
        img = _compose_thumbnail(
            w=1280, h=720,
            headline=headline,
            subtext=subtext,
            niche=niche,
            palette_index=i,
            bg_image_path=bg_image,
        )
        out_path = thumb_dir / f"thumbnail_{i + 1:02d}.png"
        img.save(str(out_path))
        saved.append(str(out_path))

    return saved


def _set_clipboard_image(photo_path: str) -> bool:
    """Put an image file on the macOS clipboard using osascript."""
    import subprocess

    photo_path = photo_path.replace('"', '\\"')
    # Try JPEG first, then PNG
    for file_type in ("JPEG picture", "PNG picture"):
        script = f'set the clipboard to (read POSIX file "{photo_path}" as {file_type})'
        r = subprocess.run(["osascript", "-e", script], capture_output=True)
        if r.returncode == 0:
            return True
    return False


def _chatgpt_get_window_bounds() -> tuple[int, int, int, int] | None:
    """Return (x, y, w, h) of the ChatGPT window, or None on error."""
    import subprocess

    r = subprocess.run(
        ["osascript", "-e", """
tell application "System Events"
    tell process "ChatGPT"
        set chosenWindow to missing value
        repeat with w in windows
            try
                set wn to name of w as string
                if wn does not contain "Quick Look" then
                    set chosenWindow to w
                    exit repeat
                end if
            on error
            end try
        end repeat
        if chosenWindow is missing value then
            set chosenWindow to window 1
        end if
        set {x, y} to position of chosenWindow
        set {wd, ht} to size of chosenWindow
        return (x as string) & "," & (y as string) & "," & (wd as string) & "," & (ht as string)
    end tell
end tell
"""],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    parts = r.stdout.strip().split(",")
    if len(parts) != 4:
        return None
    return tuple(int(p.strip()) for p in parts)  # type: ignore[return-value]


def _chatgpt_prepare_window() -> tuple[int, int, int, int] | None:
    """Activate ChatGPT, open a fresh chat, normalize window geometry, and return bounds."""
    import subprocess

    script = """
tell application "ChatGPT" to activate
delay 1.5
tell application "System Events"
    tell process "ChatGPT"
        try
            click menu item "New Chat" of menu "File" of menu bar 1
        on error
            keystroke "n" using command down
        end try
        delay 1.5
        try
            set position of window 1 to {220, 60}
            set size of window 1 to {1160, 900}
            perform action "AXRaise" of window 1
        on error
        end try
        delay 0.5
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", script], check=False)
    return _chatgpt_get_window_bounds()


def _chatgpt_force_front() -> None:
    """Force ChatGPT process and its first window to foreground."""
    import subprocess

    script = """
tell application "ChatGPT" to activate
delay 0.2
tell application "System Events"
    tell process "ChatGPT"
        set frontmost to true
        try
            perform action "AXRaise" of window 1
        on error
        end try
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", script], check=False)


def _chatgpt_close_quicklook() -> None:
    """Close Quick Look window if opened by accidental clicks."""
    import subprocess

    script = """
tell application "System Events"
    tell process "ChatGPT"
        try
            key code 53
        on error
        end try
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", script], check=False)


def _chatgpt_scroll_to_bottom_and_click_downloads(thumb_dir: Path, count: int) -> int:
    """
    Scroll ChatGPT conversation to the bottom, then try to click
    every download button that appears on hover over generated images.
    Returns the number of download clicks attempted.
    """
    import subprocess

    script = f"""
tell application "System Events"
    tell process "ChatGPT"
        -- Scroll conversation to bottom via Cmd+End
        set sa to scroll area 1 of group 2 of splitter group 1 of group 1 of window 1
        set focused of sa to true
        key code 119 using command down
        delay 0.5
        -- Get conversation area position/size for hover scanning
        set saPos to position of sa
        set saSize to size of sa
        set saX to item 1 of saPos
        set saY to item 2 of saPos
        set saW to item 1 of saSize
        set saH to item 2 of saSize
        return (saX as string) & "," & (saY as string) & "," & (saW as string) & "," & (saH as string)
    end tell
end tell
"""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return 0

    parts = r.stdout.strip().split(",")
    if len(parts) != 4:
        return 0
    sa_x, sa_y, sa_w, sa_h = [int(p.strip()) for p in parts]

    # Generated images appear as wide blocks. We scan likely download button
    # spots from bottom to top on the right edge of the conversation panel.
    import time

    attempts = 0
    click_x = sa_x + sa_w - 44
    y = sa_y + sa_h - 90
    min_y = sa_y + 110
    while y > min_y and attempts < max(6, count * 3):
        click_script = f"""
tell application "System Events"
    tell process "ChatGPT"
        click at {{{click_x}, {y}}}
    end tell
end tell
"""
        subprocess.run(["osascript", "-e", click_script], capture_output=True)
        time.sleep(0.45)
        attempts += 1
        y -= 180

    return attempts


def _chatgpt_screenshot_extract_images(thumb_dir: Path, count: int, bounds: tuple[int, int, int, int]) -> list[str]:
    """
    Screenshot the ChatGPT conversation area and extract image regions
    using pixel-variance detection. Generated images have high variance;
    text/background areas have low variance.
    """
    import subprocess
    import tempfile

    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return []

    x, y, w, h = bounds
    # Conversation panel is right ~74% of window
    conv_x = x + int(w * 0.26)
    conv_w = w - int(w * 0.26)
    conv_y = y
    conv_h = h

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        cap_path = f.name

    subprocess.run(
        ["screencapture", "-R", f"{conv_x},{conv_y},{conv_w},{conv_h}", "-x", cap_path],
        check=False,
    )

    try:
        screenshot = Image.open(cap_path).convert("RGB")
    except Exception:
        return []

    arr = np.array(screenshot)
    sh, sw = arr.shape[:2]

    # Compute per-row color variance (high variance = image content)
    # Slice into horizontal bands and score each
    band_h = 4  # pixels per band
    scores = []
    for row_start in range(0, sh, band_h):
        band = arr[row_start : row_start + band_h, int(sw * 0.05) : int(sw * 0.95)]
        variance = float(np.var(band))
        scores.append(variance)

    # Smooth scores
    kernel = 5
    smoothed = []
    for i in range(len(scores)):
        window = scores[max(0, i - kernel) : i + kernel + 1]
        smoothed.append(sum(window) / len(window))

    # Find high-variance regions (threshold: > 300)
    threshold = 300
    in_region = False
    regions: list[tuple[int, int]] = []
    region_start = 0
    for i, s in enumerate(smoothed):
        if s > threshold and not in_region:
            in_region = True
            region_start = i * band_h
        elif s <= threshold and in_region:
            in_region = False
            region_end = i * band_h
            if region_end - region_start > 80:  # minimum 80px tall
                regions.append((region_start, region_end))
    if in_region:
        regions.append((region_start, sh))

    # Keep the `count` largest regions
    regions.sort(key=lambda r: r[1] - r[0], reverse=True)
    regions = regions[:count]
    regions.sort(key=lambda r: r[0])  # sort top-to-bottom

    saved = []
    for i, (r_start, r_end) in enumerate(regions):
        # Add small padding
        y0 = max(0, r_start - 5)
        y1 = min(sh, r_end + 5)
        region_img = screenshot.crop((0, y0, sw, y1))
        region_resized = region_img.resize((1280, 720), Image.LANCZOS)
        out_path = thumb_dir / f"thumbnail_{i + 1:02d}.png"
        region_resized.save(str(out_path))
        saved.append(str(out_path))

    return saved


def _launch_chatgpt_for_thumbnail(
    workspace: Path,
    stream_title: str,
    niche: str,
    hooks: list[str],
    count: int = 3,
) -> list[str]:
    """
    Fully automated thumbnail generation via ChatGPT desktop app:
    1. Activate ChatGPT, open a fresh chat, normalize window position
    2. Paste user photo from clipboard into input
    3. Paste prompt text, press Enter
    4. Wait up to 180s for ChatGPT to generate images
    5. Try to click download button on each image (via hover + click)
    6. Watch ~/Downloads for new files → copy to THUMBNAILS/
    7. Fallback: screenshot conversation + pixel-variance extraction
    """
    import subprocess
    import time

    thumb_dir = workspace / "THUMBNAILS"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    head = _short_thumbnail_text(hooks[0], 4) if hooks else "STREAM INSIGHT"
    sub = _short_thumbnail_text(hooks[1], 5) if len(hooks) > 1 else "CONTENT AUTOMATION"

    # ── Find photo ──────────────────────────────────────────────────────────
    photo_path = _find_workspace_photo(workspace)
    print(f"[chatgpt] Selected source photo: {photo_path or 'none'}")

    style_note = (
        "Channel style: dark cinematic background, deep purple/navy tones, electric blue or neon accents, "
        "bold white uppercase text with subtle glow, expressive close-up face on one side, "
        "high contrast for mobile readability. This is FabricBot / AI automation creator style."
    )

    # ── Build prompt ─────────────────────────────────────────────────────────
    style_variants = (
        [
            f"Variant 1: closest match to reference style — face prominent, headline '{head}'",
            f"Variant 2: same palette, different layout — face on other side, headline '{head}'",
            f"Variant 3: same palette, more abstract background, headline '{head}'",
        ]
        if count >= 3
        else [f"One thumbnail — match channel style exactly — headline '{head}', sub-text '{sub}'"]
    )

    prompt_lines = [
        f"Create {count} YouTube thumbnail image{'s' if count > 1 else ''}, 16:9 format (1280×720px).",
        "",
        style_note,
        "",
        "The already attached image in this chat is the real presenter photo.",
        "Use that exact person as the face in the thumbnail. Do not replace the face with a different person.",
        "Keep the identity recognizable and realistic.",
        "",
        f"Stream topic: {stream_title}",
        f"Niche: {niche}",
        f"Main headline: {head}",
        f"Sub-text: {sub}",
        "",
    ]
    if count > 1:
        prompt_lines += ["Variants:"] + [f"  {v}" for v in style_variants] + [""]
    prompt_lines += [
        "Rules:",
        "- Use the already attached presenter photo as the source face in every generated thumbnail",
        "- Feature the face prominently and keep it realistic",
        "- Max 6 words of text total on the image",
        "- High contrast — thumbnail must be readable at 200px width",
        "- No fake logos, no fabricated brand marks",
        "- YouTube-style: expressive, bold, clickable",
        "- Generate ONE final thumbnail only (single composition)",
        "- NO collage, NO split-screen of options, NO grid/multi-panel layout",
        "- Do not place multiple alternative designs in one image",
        "",
        f"Output: {count} separate 1280×720 PNG image{'s' if count > 1 else ''}.",
    ]
    if count == 1:
        prompt_lines.append("Output must be exactly 1 image file, one design only.")
    prompt_text = "\n".join(prompt_lines)

    prompt_file = thumb_dir / "CHATGPT_PROMPT.txt"
    _write_text(prompt_file, prompt_text)
    saved: list[str] = []

    # ── Snapshot Downloads before sending ────────────────────────────────────
    downloads = Path.home() / "Downloads"
    downloads_before: set[str] = set()
    try:
        downloads_before = {
            f.name
            for f in downloads.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        }
    except Exception:
        pass

    # ── Step 1: Put photo on clipboard (prefer my photo, fallback Downloads) ─
    photo_on_clipboard = False
    if photo_path:
        photo_on_clipboard = _set_clipboard_image(photo_path)
        print(f"[chatgpt] Photo on clipboard: {photo_on_clipboard} ({photo_path})")

    # ── Step 2: Open ChatGPT and normalize window ────────────────────────────
    bounds = _chatgpt_prepare_window()
    if not bounds:
        if str(prompt_file) not in saved:
            return [str(prompt_file)]
        return saved

    bx, by, bw, bh = bounds
    input_x = bx + int(bw * 0.60)
    input_y = by + bh - 40

    focus_script = f"""
tell application "System Events"
    tell process "ChatGPT"
        click at {{{input_x}, {input_y}}}
        delay 0.25
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", focus_script], check=False)

    # ── Step 3: Paste photo ──────────────────────────────────────────────────
    if photo_on_clipboard:
        _chatgpt_force_front()
        paste_photo_script = """
tell application "System Events"
    tell process "ChatGPT"
        keystroke "v" using command down
        delay 2.2
    end tell
end tell
"""
        subprocess.run(["osascript", "-e", paste_photo_script], check=False)

    # ── Step 4: Paste prompt text and send ───────────────────────────────────
    subprocess.run(["pbcopy"], input=prompt_text.encode("utf-8"), check=False)
    time.sleep(0.3)
    _chatgpt_force_front()

    paste_and_send_script = f"""
tell application "System Events"
    tell process "ChatGPT"
        click at {{{input_x}, {input_y}}}
        delay 0.3
        keystroke "v" using command down
        delay 1
        key code 36
        delay 0.25
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", paste_and_send_script], check=False)
    print("[chatgpt] Prompt + photo sent — waiting for image generation (~150s)…")

    # ── Step 5: Wait + try to automate download button clicks ─────────────────
    wait_total = 150
    wait_start = time.time()
    attempted_downloads = False

    while time.time() - wait_start < wait_total:
        time.sleep(5)

        # Check Downloads for new images
        current = {
            f.name
            for f in downloads.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        }
        new_files = sorted(current - downloads_before)
        for fname in new_files:
            src = downloads / fname
            idx = len(saved) + 1
            dst = thumb_dir / f"thumbnail_{idx:02d}.png"
            try:
                shutil.copy2(str(src), str(dst))
                saved.append(str(dst))
                downloads_before.add(fname)
                print(f"[chatgpt] Saved image {idx}: {fname}")
            except Exception:
                pass

        if len(saved) >= count:
            break

        # After 90s — if no downloads yet, try to click download buttons
        elapsed = time.time() - wait_start
        if elapsed > 90 and not attempted_downloads and not saved:
            print("[chatgpt] Attempting to click download buttons…")
            _chatgpt_force_front()
            _chatgpt_close_quicklook()
            bounds = _chatgpt_get_window_bounds()
            if bounds:
                _chatgpt_scroll_to_bottom_and_click_downloads(thumb_dir, count)
            attempted_downloads = True
            time.sleep(10)

    # ── Step 6: If still no images — try a second download click pass ─────────
    if not saved:
        _chatgpt_force_front()
        _chatgpt_close_quicklook()
        bounds = _chatgpt_get_window_bounds()
        if bounds:
            _chatgpt_scroll_to_bottom_and_click_downloads(thumb_dir, count)
            time.sleep(10)
            # Check Downloads one more time
            current = {
                f.name
                for f in downloads.iterdir()
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            }
            new_files = sorted(current - downloads_before)
            for fname in new_files:
                src = downloads / fname
                idx = len(saved) + 1
                dst = thumb_dir / f"thumbnail_{idx:02d}.png"
                try:
                    shutil.copy2(str(src), str(dst))
                    saved.append(str(dst))
                    print(f"[chatgpt] Late-saved image {idx}: {fname}")
                except Exception:
                    pass

    # ── Step 7: Screenshot fallback using pixel-variance detection ─────────────
    if not saved:
        print("[chatgpt] Using screenshot+variance fallback…")
        _chatgpt_force_front()
        _chatgpt_close_quicklook()
        bounds = _chatgpt_get_window_bounds()
        if bounds:
            saved = _chatgpt_screenshot_extract_images(thumb_dir, count, bounds)
            print(f"[chatgpt] Extracted {len(saved)} image regions via variance scan")

    if str(prompt_file) not in saved:
        saved.insert(0, str(prompt_file))

    return saved


def _download_binary(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def _find_workspace_photo(workspace: Path) -> str | None:
    """Return path to best candidate photo for thumbnail generation."""
    photobank = workspace / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"
    candidates: list[Path] = []
    preferred_tokens = ("me", "my", "profile", "avatar", "face", "portrait", "host", "speaker")
    if photobank.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            candidates.extend(photobank.glob(ext))
    if candidates:
        preferred = [
            p for p in candidates if any(token in p.stem.lower() for token in preferred_tokens)
        ]
        if preferred:
            return str(max(preferred, key=lambda p: p.stat().st_mtime))
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    dl = Path.home() / "Downloads"
    dl_photos = sorted(
        [p for ext in ("*.jpg", "*.jpeg", "*.png") for p in dl.glob(ext)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(dl_photos[0]) if dl_photos else None


def _stash_thumbnail_outputs(workspace: Path, files: list[str], bucket: str) -> list[str]:
    """Copy generated thumbnail artifacts into THUMBNAILS/<bucket>/ and return copied paths."""
    out_dir = workspace / "THUMBNAILS" / bucket
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for file_path in files:
        src = Path(file_path)
        if not src.exists() or not src.is_file():
            continue
        dst = out_dir / src.name
        if src.resolve() == dst.resolve():
            copied.append(str(dst))
            continue
        shutil.copy2(str(src), str(dst))
        copied.append(str(dst))
    return copied


def _promote_primary_thumbnail_to_workspace_root(workspace: Path, files: list[str]) -> str | None:
    """Copy the first generated thumbnail image into stream root as thumbnail_01.png."""
    for file_path in files:
        src = Path(file_path)
        if not src.exists() or not src.is_file():
            continue
        if src.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        dst = workspace / "thumbnail_01.png"
        shutil.copy2(str(src), str(dst))
        return str(dst)
    return None


def _generate_openai_thumbnails(
    workspace: Path,
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    count: int = 3,
) -> list[str]:
    """
    Generate thumbnails using gpt-image-1 via OpenAI API.
    - If a user photo is available: uses /v1/images/edits (image input → AI edits with face composited in)
    - Otherwise: uses /v1/images/generations (text-only, still high quality)
    Requires OPENAI_API_KEY env var.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or _get_secret_from_local_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in env or config/local.env")
    image_model = (
        os.getenv("OPENAI_IMAGE_MODEL", "").strip()
        or _get_secret_from_local_env("OPENAI_IMAGE_MODEL")
        or "gpt-image-1"
    )

    thumb_dir = workspace / "THUMBNAILS"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    head = _short_thumbnail_text(hooks[0], 4) if hooks else "DAILY SYSTEM"
    sub = _short_thumbnail_text(hooks[1], 5) if len(hooks) > 1 else "STREAM INSIGHTS"

    photo_path = _find_workspace_photo(workspace)
    use_edit = photo_path is not None
    print(f"[openai] Model: {image_model}")
    print(f"[openai] Photo: {photo_path or 'none — using text-only generation'}")

    prompt_log: list[str] = []
    saved: list[str] = []

    for index in range(1, max(1, count) + 1):
        prompt = _build_openai_thumbnail_prompt(stream_title, niche, head, sub, index)
        prompt_log.append(f"## Variant {index}\n\n{prompt}\n")

        print(f"[openai] Generating variant {index}/{count}…")

        if use_edit:
            # Use edits endpoint: model can see and use the person's actual face
            boundary = "----FormBoundary" + os.urandom(8).hex()
            parts: list[bytes] = []

            def _field(name: str, value: str) -> bytes:
                return (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")

            def _file_field(name: str, filename: str, content: bytes, mime: str) -> bytes:
                header = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                    f"Content-Type: {mime}\r\n\r\n"
                ).encode("utf-8")
                return header + content + b"\r\n"

            photo_bytes = Path(photo_path).read_bytes()
            photo_mime = "image/jpeg" if photo_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

            parts.append(_file_field("image[]", "photo.jpg", photo_bytes, photo_mime))
            parts.append(_field("model", image_model))
            parts.append(_field("prompt", prompt))
            parts.append(_field("size", "1536x1024"))
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))

            body_bytes = b"".join(parts)
            req = urllib.request.Request(
                "https://api.openai.com/v1/images/edits",
                data=body_bytes,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                method="POST",
            )
        else:
            payload = {
                "model": image_model,
                "prompt": prompt,
                "size": "1536x1024",
                "quality": "high",
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/images/generations",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                resp_body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error (variant {index}): {e.code} {err[:400]}") from e

        data = resp_body.get("data") or []
        if not data:
            raise RuntimeError(f"OpenAI response missing image data for variant {index}: {resp_body}")

        item = data[0]
        if item.get("b64_json"):
            image_bytes = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            image_bytes = _download_binary(item["url"])
        else:
            raise RuntimeError(f"OpenAI response has no image payload for variant {index}")

        out_path = thumb_dir / f"thumbnail_{index:02d}.png"
        out_path.write_bytes(image_bytes)
        saved.append(str(out_path))
        print(f"[openai] Saved variant {index}: {out_path}")

    seo_title = [
        f"{stream_title}: {_short_thumbnail_text(hooks[0], 5) if hooks else niche}",
        f"{_short_thumbnail_text(niche, 4)} - Daily Stream Breakdown",
        f"How to Build {_short_thumbnail_text(niche, 3)} Workflow",
    ]
    seo_text = (
        "# THUMBNAIL SEO NOTES\n\n"
        "## Suggested Video Titles\n"
        + "\n".join(f"- {line}" for line in seo_title)
        + "\n\n## Suggested Alt Text\n"
        + "- AI-generated high-contrast thumbnail with expressive face and bold headline.\n"
        + "- Stream concept visual with icon accent and strong mobile readability.\n"
    )
    _write_text(thumb_dir / "SEO_NOTES.md", seo_text)
    _write_text(thumb_dir / "OPENAI_PROMPTS_USED.md", "\n".join(prompt_log))
    saved.append(str(thumb_dir / "SEO_NOTES.md"))
    saved.append(str(thumb_dir / "OPENAI_PROMPTS_USED.md"))

    return saved


def _build_thumbnail_creation(stream_title: str, niche: str, hooks: list[str]) -> str:
    hook_raw = hooks[0] if hooks else f"Biggest insight from {niche}"
    support_raw = hooks[1] if len(hooks) > 1 else f"Practical system for {niche}"
    hook = _short_thumbnail_text(hook_raw, max_words=4)
    support = _short_thumbnail_text(support_raw, max_words=5)
    return f"""# THUMBNAIL CREATION

## Objective

Build thumbnails in your recognizable signature style: expressive face, strong short text, icon accents, clear hierarchy, and high CTR readability on mobile.

## Required Inputs Before Generation

1. 2-4 reference screenshots of your existing style.
2. 1 face screenshot from this stream with strong emotion.
3. Optional icons (arrow, warning, growth, AI, chart, lightning).

## Prompt Template (copy to your image generator)

SYSTEM / STYLE LOCK:
You are a senior YouTube thumbnail designer.
Your task is to recreate the exact visual language from the provided reference thumbnails, not a generic style.
Respect composition DNA: face prominence, short high-contrast headline, icon support, directional cues, and bold focal hierarchy.
Design for 16:9 thumbnail format with aggressive mobile readability.

USER PROMPT:
Create a high-CTR YouTube thumbnail for stream title: "{stream_title}".
Topic niche: {niche}.
Primary hook text on thumbnail: "{hook}".
Secondary support text (small): "{support}".

Composition rules:
- Face occupies 35-55% of frame, emotionally expressive.
- Main headline is 2-5 words, very large, thick, and readable at small size.
- Add 1-2 relevant icons near headline (not decorative noise).
- Add depth layers: foreground subject, mid text, subtle background context.
- Use contrast blocks behind text if needed.
- Keep strong edge separation around face and text.

Style constraints:
- Match reference style color logic and typography mood.
- No generic corporate look, no stock-template look.
- No visual clutter; every element must support the message.

Technical constraints:
- Aspect ratio 16:9.
- Export target: 1280x720.
- Safe readable center composition for mobile crop tolerance.

NEGATIVE PROMPT:
small unreadable text, too many words, bland pastel palette, low contrast, over-detailed background, stock-photo look, generic clickbait collage, distorted face, extra fingers, broken anatomy, watermark, logo spam.

## 5 Fast Variants To Test

1. Face Left + Text Right + One arrow icon.
2. Face Right + Shock headline center-left + warning icon.
3. Big central text + smaller face cutout + chart icon.
4. Dark dramatic background + neon text stroke + lightning icon.
5. Minimal clean layout + one dominant expression + one badge.

## Thumbnail Text Bank (short)

- {hook}
- {support}
- STOP DOING THIS
- REAL WORKFLOW
- DAILY SYSTEM

## QA Checklist (must pass)

- Readable at 120px width preview.
- Message understood in less than 1 second.
- Face + text + icon have clear priority order.
- Looks like your existing brand style, not a random new one.
- Works even without reading stream title metadata.
"""


def _build_shorts_report(job_id: str | None, clips: list[str], job_dir: str | None) -> str:
    if not job_id:
        if clips:
            clip_lines = "\n".join(f"- {path}" for path in clips)
            return (
                "# SHORTS CREATION\n\n"
                "- Shorts pipeline was skipped because clips already exist in SHORTS/.\n"
                f"- Reused clips: {len(clips)}\n\n"
                "## Clip Files\n"
                f"{clip_lines}\n"
            )
        return "# SHORTS CREATION\n\n- Shorts pipeline was not executed.\n"
    clip_lines = "\n".join(f"- {path}" for path in clips) if clips else "- No clips rendered"
    return (
        "# SHORTS CREATION\n\n"
        f"- Job ID: {job_id}\n"
        f"- Job directory: {job_dir or 'n/a'}\n"
        f"- Clips generated: {len(clips)}\n\n"
        "## Clip Files\n"
        f"{clip_lines}\n"
    )


def _build_shorts_seo(stream_title: str, niche: str, hooks: list[str], phrases: list[str], clips: list[Path]) -> str:
    lines: list[str] = ["# SHORTS SEO", "", "Use these names and descriptions for short clips.", ""]
    keywords = ", ".join(phrases[:8]) if phrases else niche

    if not clips:
        lines.extend([
            "## No shorts found yet",
            "",
            "- Shorts pipeline output is missing.",
            "- Generate or copy clips to SHORTS/ and rerun materials generation.",
        ])
        return "\n".join(lines) + "\n"

    for index, clip in enumerate(clips, start=1):
        hook = hooks[(index - 1) % len(hooks)] if hooks else f"One practical insight about {niche}"
        short_hook = _short_thumbnail_text(hook, max_words=6).capitalize()
        title = f"{short_hook} | {stream_title}"[:98]
        description = (
            f"Clip from {stream_title}. Focus: {hook}. "
            f"Niche: {niche}. Keywords: {keywords}."
        )
        lines.extend([
            f"## Clip {index}: {clip.name}",
            f"- Title: {title}",
            f"- Description: {description}",
            "",
        ])

    return "\n".join(lines)


def _producer_launch_shorts_if_needed(workspace: Path) -> tuple[list[Path], str]:
    """
    Ensure shorts exist for producer tasks.
    - Reuse existing clips if present.
    - Otherwise run shorts pipeline using VIDEO source and workspace config.
    Returns (shorts_paths, status_message).
    """
    shorts_dir = workspace / "SHORTS"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(shorts_dir.glob("*.mp4"))
    if existing:
        _write_text(workspace / "SHORTS CREATION.md", _build_shorts_report(None, [str(p) for p in existing], None))
        return existing, f"completed (reused {len(existing)} clips)"

    video_dir = workspace / "VIDEO"
    video_candidates: list[Path] = []
    if video_dir.exists():
        for ext in ("*.mp4", "*.mov", "*.mkv", "*.webm"):
            video_candidates.extend(video_dir.glob(ext))
    if not video_candidates:
        _write_text(workspace / "SHORTS CREATION.md", "# SHORTS CREATION\n\n- Source video not found in VIDEO/.\n")
        return [], "failed: source video missing"

    source_video = max(video_candidates, key=lambda p: p.stat().st_mtime)
    config_path = "config/default.yaml"
    manifest_path = workspace / "workflow_manifest.json"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            candidate = str(payload.get("config_path") or "").strip()
            if candidate:
                config_path = candidate
        except Exception:
            pass

    try:
        settings = load_settings(config_path)
        job = run_pipeline(settings, str(source_video))
    except Exception as exc:  # noqa: BLE001
        _write_text(workspace / "SHORTS CREATION.md", f"# SHORTS CREATION\n\n- Shorts pipeline failed: {exc}\n")
        return [], f"failed: {exc}"

    if job.status != JobStatus.completed:
        message = "; ".join(job.errors) if job.errors else "shorts pipeline failed"
        _write_text(workspace / "SHORTS CREATION.md", f"# SHORTS CREATION\n\n- Shorts pipeline failed: {message}\n")
        return [], f"failed: {message}"

    clips: list[str] = []
    for clip in job.result.clips:
        clip_src = Path(clip.output_path)
        if not clip_src.exists():
            continue
        dst = shorts_dir / clip_src.name
        shutil.copy2(clip_src, dst)
        clips.append(str(dst))

    _write_text(
        workspace / "SHORTS CREATION.md",
        _build_shorts_report(job.id, clips, str(Path(settings.app.output_dir) / job.id)),
    )
    return [Path(p) for p in clips], f"completed ({len(clips)} clips)"


def _build_producer_agent_instructions() -> str:
    return """# PRODUCER AGENT

Role: Producer (SEO, titles, descriptions, thumbnails, shorts SEO)

Primary responsibility:
- Prepare discoverability and packaging assets, not generic social copy.

Required outputs:
- SEO AND DATA FOR VIDEO.md
- YOUTUBE DESCRIPTION.md
- YOUTUBE TAGS.txt (single comma-separated line, 300-400 chars)
- THUMBNAIL CREATION.md
- SHORTS SEO.md (short names and descriptions)
- shorts_titles.md (per-short title package with alternatives and hooks)
- shorts_metadata.md (one title + one 2-3 sentence description per Short)
- Thumbnails in THUMBNAILS/

Execution rules:
- Before creating titles, always analyze transcript, stream notes (if present), MARKETING TAKES, and clips/timestamps (if present).
- Never generate titles from generic topic alone; extract strongest real ideas from stream material.
- Reuse transcript hooks and phrases.
- Keep titles concise and high-clarity.
- Keep descriptions factual and aligned with transcript content.
- Build YouTube tags as one comma-separated line with broad high-frequency search terms.
- Keep tags around 300-400 characters; no hashtags, no bullet points, no explanations, no long sentence-like tags.
- For each Short produce exactly one short title (3-8 words, sentence case) and one 2-3 sentence description with a soft CTA to the channel and FabricBot ecosystem.
- Keep shorts naming consistent and non-duplicative.
- Produce only one primary thumbnail unless explicitly requested otherwise.
- Keep metadata and thumbnail message aligned to one central promise.

YouTube title rule:
- Use sentence case, not title case.
- Capitalize only proper names/acronyms/platform names (AI, YouTube, Telegram, Web3, FabricBot, OpenAI, X, LinkedIn, TikTok).
- Avoid corporate buzzwords and generic phrasing.
- Prefer builder language: I built, I tested, I automated, I broke, I fixed, this worked, stop doing this manually.
- Enforce blacklist words: revolutionary, innovative, next-gen, comprehensive guide, deep dive, ultimate guide, leveraging, implementation, infrastructure, ecosystem, transformation strategy.
- Score each candidate title (0-100) by clarity, pain, transformation, and curiosity.

Long video output requirements:
- Generate 10 title options.
- Select top 3 recommendations.
- Add short explanation for each top-3 choice.
- Add 3 thumbnail text options (3-5 words).
- Add 1 description hook for first 1-2 lines.

Shorts output requirements:
- For each short clip provide: main title, 2 alternatives, first-second hook, caption, recommended platform, editor notes.
- Keep Shorts titles sharp and short (usually 3-8 words).
- Keep sentence case for Shorts titles as well.

Thumbnail direction (must follow):
- Style: expressive face, short bold text, icon accents, strong visual hierarchy.
- Mobile-first readability: message understandable in <1 second at small preview size.
- Text constraints: 2-5 words main headline, high contrast, no clutter.
- Composition: face prominence, clear edge separation around face and text.
- Output format: 16:9, target 1280x720.

Thumbnail QA checklist:
- Readable at 120px preview width.
- Priority order is clear: face -> text -> icon.
- Visual matches channel style (not generic template look).
- Works even if user does not read metadata/title.

Packaging quality gate:
- No duplicate ideas between title, description, and first pinned comment.
- The first 120 description characters must communicate concrete value.
- Shorts SEO names must be distinct and not near-duplicates.

Note:
- This file is intentionally editable. Instructions can be changed later.
"""


def _build_smm_manager_agent_instructions() -> str:
    return """# SMM MANAGER AGENT

Role: SMM post creator (adapter and packager)

Primary responsibility:
- Turn existing stream materials into platform-ready posts.
- Create reusable base posts first, then adapt them per platform.

Required outputs:
- SMM DATA.md
- smm_posts_package.md
- Platform HUMAN_POSTS.md files
- SOCIAL PRESENCE SCHEDULE.md

Execution rules:
- Always read and analyze before writing posts:
    - transcript
    - stream notes (if present)
    - marketing takes / positioning file
    - Producer brief (if present)
    - article package (if present)
    - Shorts titles package (if present)
    - screenshots/visual assets (if present)
- Do not generate from the general topic only.
- Do not invent fake claims, fake numbers, fake results, or fake product features.
- Build base post ideas first, then adapt each to X, LinkedIn, Facebook, Telegram, Discord.
- Use platform-native tone and format; do not duplicate wording everywhere.
- Keep medium post structure: hook -> context -> insight -> practical angle -> CTA/question.
- Include short video captions, engagement asks, article announcements, and visual insight captions.
- Save full package in smm_posts_package.md inside the same stream folder.

Quality bar:
- One clear idea per post.
- Strong first line.
- Native platform tone.
- FabricBot positioning should be explicit where relevant.
- If assets are missing, mark them and request only base assets.

Note:
- This file is intentionally editable. Instructions can be changed later.
"""


def _build_article_creator_agent_instructions() -> str:
    return """# ARTICLE CREATOR AGENT

Role: Article creator (long-form articles)

Primary responsibility:
- Create or update long-form publication-ready article assets.

Required outputs:
- ARTICLES/article_01.md ... article_N.md for selected article angles
- ARTICLES/articles_index.md with idea map, selected list, status and platform notes
- ARTICLES/article.md as compatibility alias to the strongest article
- ARTICLES.md template fallback only when package generation is unavailable

Execution rules:
- Always analyze transcript, stream notes, marketing takes, producer brief, and available screenshots/context files.
- Do not summarize stream only; extract multiple strong theses and turn them into separate articles.
- Build an article idea map first, then select strongest 2-5 angles.
- Use transcript facts only.
- Keep structure clear and publication-ready.
- Reuse available screenshots when possible.
- Target each full article at 1200-2500 words (minimum 900 for narrow angles).
- Keep clean Markdown formatting and strong section transitions.
- Insert stream quotes as blockquotes where they strengthen the narrative.
- End each article with a polished "Where to follow" section linking YouTube and X.
- Close each article with a concrete call to action tied to the stream topic.
- Include cross-platform adaptations: LinkedIn, X, Telegram, Facebook, Discord.
- Include editor self-review checkpoints for thesis, hook, specificity, depth, repetition, tone, platform fit, FabricBot fit, reader value, final line.

Formatting quality gate:
- No giant text walls; split into digestible sections.
- Keep transitions logical: insight leads to practical action.
- Ensure final paragraph sounds human and confident.
- Keep sentence case titles, not title case.
- Avoid generic AI/corporate language and banned buzzword phrasing.

Note:
- This file is intentionally editable. Instructions can be changed later.
"""


def _run_producer_agent(
    workspace: Path,
    stream_title: str,
    niche: str,
    hooks: list[str],
    phrases: list[str],
    transcript_text: str,
    thumbnail_provider: str,
) -> dict:
    _write_text(workspace / "MARKETING TAKES.md", _build_marketing_takes(hooks))
    _write_text(workspace / "THUMBNAIL CREATION.md", _build_thumbnail_creation(stream_title, niche, hooks))
    notes_context = _read_stream_notes_context(workspace)
    _write_text(
        workspace / "SEO AND DATA FOR VIDEO.md",
        _build_seo_package(stream_title, niche, phrases, hooks, transcript_text=transcript_text, notes_context=notes_context),
    )
    description_chapters = _build_chapter_seeds(transcript_text, hooks, niche)
    _write_text(
        workspace / "YOUTUBE DESCRIPTION.md",
        _build_youtube_description(
            stream_title=stream_title,
            niche=niche,
            hooks=hooks,
            phrases=phrases,
            transcript_text=transcript_text,
            notes_context=notes_context,
            chapters=description_chapters,
        ),
    )
    _write_text(
        workspace / "YOUTUBE TAGS.txt",
        _build_youtube_tags_line(
            stream_title=stream_title,
            niche=niche,
            phrases=phrases,
            hooks=hooks,
            transcript_text=transcript_text,
            notes_context=notes_context,
            chapters=description_chapters,
            description_text=_read_text_if_exists(workspace / "YOUTUBE DESCRIPTION.md"),
        ) + "\n",
    )

    shorts_files, shorts_status = _producer_launch_shorts_if_needed(workspace)
    shorts_seo_path = workspace / "SHORTS SEO.md"
    _write_text(shorts_seo_path, _build_shorts_seo(stream_title, niche, hooks, phrases, shorts_files))
    shorts_titles_path = workspace / "shorts_titles.md"
    _write_text(shorts_titles_path, _build_shorts_titles_package(stream_title, shorts_files, hooks, phrases))
    shorts_metadata_path = workspace / "shorts_metadata.md"
    _write_text(
        shorts_metadata_path,
        _build_shorts_metadata_package(
            stream_title=stream_title,
            niche=niche,
            hooks=hooks,
            phrases=phrases,
            clips=shorts_files,
            notes_context=notes_context,
            transcript_text=transcript_text,
        ),
    )

    provider = thumbnail_provider.strip().lower()
    thumbnail_count = 1
    thumbnail_status = "pending"
    if provider == "chatgpt":
        thumbnail_files = _launch_chatgpt_for_thumbnail(workspace, stream_title, niche, hooks, count=thumbnail_count)
        thumbnail_status = "completed (chatgpt-automated)"
    elif provider in {"openai", "api", "gpt-image", "gptimage"}:
        try:
            thumbnail_files = _generate_openai_thumbnails(workspace, stream_title, niche, hooks, phrases, count=thumbnail_count)
            thumbnail_status = "completed (openai)"
        except Exception as exc:  # noqa: BLE001
            thumbnail_files = _generate_pillow_thumbnails(workspace, stream_title, niche, hooks, count=thumbnail_count)
            _write_text(workspace / "THUMBNAILS" / "OPENAI_ERROR.txt",
                        f"OpenAI failed ({exc}). Pillow fallback was used.\n")
            thumbnail_status = f"completed (pillow fallback — openai error: {exc})"
    elif provider == "local":
        thumbnail_files = _generate_local_thumbnails(workspace, stream_title, niche, hooks, phrases, count=thumbnail_count)
        thumbnail_status = "completed (local/opencv)"
    elif provider in {"both", "openai+local", "local+openai", "api+local", "local+api"}:
        api_files: list[str] = []
        local_files: list[str] = []
        issues: list[str] = []

        try:
            api_generated = _generate_openai_thumbnails(workspace, stream_title, niche, hooks, phrases, count=thumbnail_count)
            api_files = _stash_thumbnail_outputs(workspace, api_generated, "API")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"openai_failed: {exc}")
            _write_text(workspace / "THUMBNAILS" / "OPENAI_ERROR.txt", f"OpenAI failed: {exc}\n")

        try:
            local_generated = _generate_local_thumbnails(workspace, stream_title, niche, hooks, phrases, count=thumbnail_count)
            local_files = _stash_thumbnail_outputs(workspace, local_generated, "LOCAL")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"local_failed: {exc}")
            _write_text(workspace / "THUMBNAILS" / "LOCAL_ERROR.txt", f"Local generator failed: {exc}\n")

        thumbnail_files = [*api_files, *local_files]
        if thumbnail_files:
            if issues:
                thumbnail_status = f"completed (both with warnings: {'; '.join(issues)})"
            else:
                thumbnail_status = "completed (both: openai + local)"
        else:
            thumbnail_files = _generate_pillow_thumbnails(workspace, stream_title, niche, hooks, count=thumbnail_count)
            thumbnail_status = f"completed (pillow fallback — both failed: {'; '.join(issues) or 'unknown'})"
    else:
        thumbnail_files = _generate_pillow_thumbnails(workspace, stream_title, niche, hooks, count=thumbnail_count)
        thumbnail_status = "completed (pillow)"

    return {
        "files": [
            str(workspace / "MARKETING TAKES.md"),
            str(workspace / "THUMBNAIL CREATION.md"),
            str(workspace / "SEO AND DATA FOR VIDEO.md"),
            str(workspace / "YOUTUBE DESCRIPTION.md"),
            str(workspace / "YOUTUBE TAGS.txt"),
            str(workspace / "SHORTS CREATION.md"),
            str(shorts_seo_path),
            str(shorts_titles_path),
            str(shorts_metadata_path),
            *thumbnail_files,
        ],
        "thumbnail_files": thumbnail_files,
        "status": {
            "producer_agent": "completed",
            "marketing_takes": "completed",
            "thumbnail_creation": thumbnail_status,
            "seo_package": "completed",
            "shorts_creation": shorts_status,
            "shorts_seo": "completed",
            "shorts_titles": "completed",
            "shorts_metadata": "completed",
            "thumbnails_auto": thumbnail_status,
        },
    }


def _run_smm_manager_agent(workspace: Path, stream_title: str, niche: str, hooks: list[str]) -> dict:
    _write_text(workspace / "SMM DATA.md", _build_smm_data(stream_title, niche, hooks))
    smm_package_path = workspace / "smm_posts_package.md"
    _write_text(smm_package_path, _build_smm_posts_package(stream_title, niche, hooks, workspace))
    social_files = _write_social_presence_files(workspace, stream_title, niche, hooks)
    return {
        "files": [str(workspace / "SMM DATA.md"), str(smm_package_path), *social_files],
        "status": {
            "smm_manager_agent": "completed",
            "smm_package": "completed",
            "human_social_presence": "completed",
        },
    }


def _run_article_creator_agent(
    workspace: Path,
    stream_title: str,
    niche: str,
    transcript_text: str,
    hooks: list[str],
    phrases: list[str],
) -> dict:
    try:
        article_files, idea_map, selected_rows = _generate_article_package(
            workspace=workspace,
            stream_title=stream_title,
            niche=niche,
            transcript_text=transcript_text,
            hooks=hooks,
            phrases=phrases,
        )
        if article_files:
            index_path = workspace / "ARTICLES" / "articles_index.md"
            _write_text(index_path, _build_articles_index(stream_title, idea_map, selected_rows))
            package_path = workspace / "ARTICLES" / "article_package.md"
            package_text = [
                f"# Article package for {stream_title}",
                "",
                "Generated article files:",
                *[f"- {Path(path).name}" for path in article_files if Path(path).suffix == ".md"],
                "",
                "See articles_index.md for idea map, selection rationale, and SMM notes.",
                "",
            ]
            _write_text(package_path, "\n".join(package_text))
            return {
                "files": [*article_files, str(index_path), str(package_path)],
                "status": {
                    "article_creator_agent": "completed (package)",
                    "articles": f"completed ({len(selected_rows)} long-form articles)",
                },
            }
    except Exception:
        pass

    _write_text(workspace / "ARTICLES.md", _build_articles(stream_title, niche, hooks, phrases))
    return {
        "files": [str(workspace / "ARTICLES.md")],
        "status": {
            "article_creator_agent": "completed (template fallback)",
            "articles": "completed (template fallback — article package generation failed)",
        },
    }


def _build_publishing_instructions(youtube_channels: list[str]) -> str:
    channels = (youtube_channels or DEFAULT_YOUTUBE_CHANNELS)[:]
    channels += [f"Channel {i}" for i in range(len(channels) + 1, 4)]
    channels = channels[:3]

    return f"""# PUBLISHING INSTRUCTIONS

## Daily Stream Output Model

- One stream per day produces one content package.
- All deliverables are stored in this workspace folder.
- Reuse core ideas, but format per platform.

## YouTube Shorts Allocation (3 channels)

- {channels[0]}: publish exactly 2 best shorts per day.
- {channels[1]}: publish 2 to 3 strong shorts per day.
- {channels[2]}: publish remaining lower-priority shorts (backlog channel).

Selection order:

1. Highest hook strength and retention potential.
2. Clear standalone context in first 2-3 seconds.
3. Clean subtitle readability and no clipping issues.

## TikTok Strategy

- TikTok uses the same core shortlist as Shorts.
- Prioritize vertical clips with immediate hook.
- Allow caption and CTA adaptation per platform voice.

## Article Reuse Strategy

- Base article can be shared across LinkedIn, X, Medium, and Substack.
- Keep one canonical long-form draft, then publish adapted variants:
  - LinkedIn: concise professional framing.
  - X: thread or compact key points.
  - Medium/Substack: full long-form version.

## Social Post Reuse Strategy

- LinkedIn, Facebook, and Instagram can reuse the same base post.
- Pinterest uses short text + image/card from stream assets.
- Telegram and Discord use concise announcement + key takeaway + CTA.

## Folder Usage Rules

- Place final ready-to-publish assets in corresponding platform folder.
- Keep draft variants in root files (`SMM DATA.md`, `ARTICLES.md`, `SEO AND DATA FOR VIDEO.md`).
- Move used assets to dated subfolders if you need historical traceability.

## Local-Only Constraint

- This workflow is local-first and API-free by default.
- Do not require cloud generation for baseline daily publishing.
"""


def _build_smm_head_agent_instructions() -> str:
    return """# SMM-HEAD-AGENT INSIDE APP

## ROLE: THE SMM HEAD

You are the SMM Head agent.
You do not generate final content from scratch.
You manage posting logic, platform distribution, priorities, and decisions.

## MAIN GOAL

Keep all FabricBot-related social channels active according to daily posting volume,
while avoiding duplicate generation and repeated work.

## MANDATORY EXECUTION ORDER

1. Check current posting situation.
2. Check what is already posted today on each platform/channel.
3. Check what is scheduled or pending.
4. Inspect materials inside the new stream folder.
5. Identify which materials are ready to post.
6. Identify which assets are missing.
7. Decide what should be posted next on each platform.
8. If content is missing, request it from the content generation agent.
9. If content is ready, prepare posting plan and execute posting tasks.

## WORKSPACE ADAPTATION (THIS APP)

### Where to find stream runs

- App output root: `output/`
- New stream workspace folders: `output/<run-id>/`
- Run metadata: `output/<run-id>/workflow_manifest.json`

### Primary files to inspect in each stream workspace

- `INSTRUCTIONS FOR SYSTEM.md`
- `W2V INSIGHTS.md`
- `TRANSCRIBATION.txt` or `TRANSCRIBATION.srt`
- `MARKETING TAKES.md`
- `SEO AND DATA FOR VIDEO.md`
- `SMM DATA.md`
- `ARTICLES.md` or `ARTICLES/article.md`
- `SHORTS CREATION.md`
- `THUMBNAIL CREATION.md`
- `PUBLISHING PLAN.md`
- `PUBLISHING INSTRUCTIONS.md`

### Asset folders to inspect

- `VIDEO/` for full stream recordings
- `SHORTS/` for ready vertical clips
- `THUMBNAILS/` for thumbnail variants and SEO notes
- `PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)/` for screenshot/visual assets
- Platform folders:
    - `YOUTUBE/`
    - `X/`
    - `LINKEDIN/`
    - `TELEGRAM/`
    - `INSTAGRAM/`
    - `TIKTOK/`
    - `FACEBOOK/`
    - `DISCORD/`
    - `PINTEREST/`
    - `MEDIUM/`
    - `SUBSTACK/`

### Status source of truth

Read status from `workflow_manifest.json` -> `status` object.
Use available flags such as:
- `transcription`
- `shorts_creation`
- `marketing_takes`
- `seo_package`
- `smm_package`
- `articles`
- `thumbnail_creation`

## DAILY POSTING PLAN

### YOUTUBE

Channel: FabricBot
- Long streams and long videos.
- Main channel for best long-form content.
- Also post 2 best Shorts per day.

Channel: FabricBotShorts
- Post 2-3 next-level Shorts per day.
- Use strongest vertical clips by hook/retention/visual quality.

Channel: Digital Shamanism
- Post 2-3 other Shorts per day.
- More experimental/philosophical/spiritual/AI/Web3/creator-vibe clips.

### X / TWITTER

- 1-2 medium posts per day.
- 1 good Short per day with text.
- 1 article every 1-2 days.

### MEDIUM

- 1 article per day.

### LINKEDIN

- 1-2 medium posts per day.
- 1 good Short per day with text.
- 1 article every 1-2 days.

### TELEGRAM

- 3-4 medium posts per day (include YouTube stream links when relevant).
- 1-2 short engagement asks/questions.
- 1 short post with Medium article link.

### TIKTOK

- 3 best TikToks per day.

### FACEBOOK

- 1-2 medium posts per day.
- 1 good Short per day with text.
- 1 short post with Medium article link.

### DISCORD

- 3-4 medium posts per day (include YouTube stream links when relevant).
- 1-2 short engagement asks/questions.
- 1 short post with Medium article link.

### PINTEREST

- 2 screenshot/visual-insight posts per day when quality assets exist.
- If no good visuals: mark as `missing visual assets` and request from generation/design agent.

## CONTENT REUSE RULES

Do not request separate content from scratch for each platform when format repeats.
Use one base asset and adapt.

1. Medium posts: one base medium post adapted for X, LinkedIn, Facebook, Telegram, Discord.
2. Shorts with text: one base Short + one base caption adapted for X, LinkedIn, Facebook, TikTok, YouTube Shorts.
3. Articles: one base article for Medium, X, LinkedIn; share link adapts for Telegram, Facebook, Discord.
4. Article-link small post: one base announcement adapted for Telegram, Facebook, Discord.
5. Stream announcement/recap: one base stream post adapted for Telegram, Discord, and optionally X/LinkedIn/Facebook.
6. Engagement asks: 1-2 base asks reused across Telegram and Discord.
7. Screenshots/visual insights: one visual concept reused across Pinterest, X, LinkedIn, Telegram, Facebook.

## DECISION LOGIC

For each platform/channel classify status as:
- `DONE`
- `PARTIAL`
- `EMPTY`
- `BLOCKED`
- `READY TO POST`

Priority order for what to post next:

1. Already prepared materials from newest stream folder.
2. Best-performing/highest-quality Shorts.
3. Long-form YouTube streams/videos.
4. Medium posts adapted from existing stream/article ideas.
5. Medium article + article-link announcements.
6. Engagement asks for Telegram/Discord.
7. Screenshot/visual insight posts.

## NEW STREAM FOLDER ASSET CLASSIFICATION

When inspecting assets, classify into:
- Long-form YouTube content
- Best Shorts
- Next-level Shorts
- Other Shorts / Digital Shamanism Shorts
- Text post material
- Article material
- Stream announcement/recap material
- Visual screenshot material
- Missing/incomplete material

## REQUIRED REPORT FORMAT

1. Current posting status
2. Available materials
3. What should be posted now
4. What should not be generated again
5. Missing assets
6. Tasks for the generation agent (base assets only)
7. Final posting plan (ordered queue)

## FINAL RULE

Always check posting status first, then stream folder assets, then identify missing assets,
request only missing base assets, and prepare posting queue.

Use the same posting technologies and integrations already used in this app stack.
"""


def _write_platform_templates(run_dir: Path, youtube_channels: list[str]) -> None:
    (run_dir / "SMM").mkdir(parents=True, exist_ok=True)

    for folder in PLATFORM_FOLDERS:
        platform_dir = run_dir / folder
        platform_dir.mkdir(parents=True, exist_ok=True)
        _write_text(
            platform_dir / "README.md",
            (
                f"# {folder}\n\n"
                "Use this folder for final publication-ready assets for this platform.\n"
            ),
        )

    youtube_dir = run_dir / "YOUTUBE"
    channel_names = youtube_channels or DEFAULT_YOUTUBE_CHANNELS
    for index, name in enumerate(channel_names[:3], start=1):
        channel_dir = youtube_dir / f"channel_{index}_{_slugify(name)}"
        channel_dir.mkdir(parents=True, exist_ok=True)
        _write_text(
            channel_dir / "plan.md",
            (
                f"# {name}\n\n"
                "- Daily slots: fill according to PUBLISHING INSTRUCTIONS\n"
                "- Paste chosen clip filenames and publish times here\n"
            ),
        )


def _segments_from_plain_text(text: str) -> list[TranscriptSegment]:
    chunks = [line.strip() for line in text.splitlines() if line.strip()]
    segments: list[TranscriptSegment] = []
    cursor = 0.0
    for chunk in chunks:
        duration = max(2.0, min(12.0, len(chunk) / 16.0))
        segments.append(
            TranscriptSegment(
                start=cursor,
                end=cursor + duration,
                text=chunk,
                confidence=0.8,
            )
        )
        cursor += duration
    return segments


def _pdf_safe_text(text: str) -> str:
    # ReportLab standard fonts are safer with latin-1 range.
    return text.encode("latin-1", "replace").decode("latin-1")


def _extract_title_from_seo(seo_text: str, fallback: str) -> str:
    in_titles = False
    for raw in seo_text.splitlines():
        line = raw.strip()
        if line.startswith("## YouTube title options"):
            in_titles = True
            continue
        if in_titles and line.startswith("## "):
            break
        if in_titles and line.startswith("-"):
            title = line.lstrip("-").strip()
            if title:
                return title
    return fallback


def _pick_preview_image(workspace: Path) -> Path | None:
    candidates = [
        workspace / "thumbnail_01.png",
        workspace / "THUMBNAILS" / "thumbnail_01.png",
        workspace / "THUMBNAILS" / "thumbnail_1.png",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _generate_workspace_pdf_report(
    workspace: Path,
    stream_title: str,
    niche: str,
    materials: list[str],
    status: dict,
) -> tuple[str | None, str]:
    report_path = workspace / "FINAL_REPORT.pdf"
    error_path = workspace / "FINAL_REPORT_ERROR.txt"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except Exception as exc:  # noqa: BLE001
        _write_text(error_path, f"PDF generation skipped: missing reportlab dependency ({exc})\n")
        return None, "failed: reportlab missing"

    try:
        seo_text = _read_text_if_exists(workspace / "SEO AND DATA FOR VIDEO.md")
        description = _read_text_if_exists(workspace / "YOUTUBE DESCRIPTION.md")
        tags_line = _read_text_if_exists(workspace / "YOUTUBE TAGS.txt")
        top_title = _extract_title_from_seo(seo_text, stream_title)
        preview = _pick_preview_image(workspace)

        page_w, page_h = A4
        left = 42
        right = page_w - 42
        y = page_h - 44

        pdf = canvas.Canvas(str(report_path), pagesize=A4)

        def new_page() -> None:
            nonlocal y
            pdf.showPage()
            y = page_h - 44

        def draw_heading(text: str, size: int = 14) -> None:
            nonlocal y
            if y < 72:
                new_page()
            pdf.setFont("Helvetica-Bold", size)
            pdf.drawString(left, y, _pdf_safe_text(text))
            y -= size + 6

        def draw_paragraph(text: str, size: int = 10, leading: int = 14) -> None:
            nonlocal y
            words = _pdf_safe_text(text).split()
            if not words:
                y -= leading
                return
            line = ""
            pdf.setFont("Helvetica", size)
            for word in words:
                test = f"{line} {word}".strip()
                width = pdf.stringWidth(test, "Helvetica", size)
                if width <= (right - left):
                    line = test
                else:
                    if y < 60:
                        new_page()
                        pdf.setFont("Helvetica", size)
                    pdf.drawString(left, y, line)
                    y -= leading
                    line = word
            if line:
                if y < 60:
                    new_page()
                    pdf.setFont("Helvetica", size)
                pdf.drawString(left, y, line)
                y -= leading

        draw_heading("FabricBot stream final report", 18)
        draw_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        draw_paragraph(f"Stream: {stream_title}")
        draw_paragraph(f"Niche: {niche}")
        y -= 6

        draw_heading("Primary packaging")
        draw_paragraph(f"Recommended YouTube title: {top_title}")
        if tags_line:
            draw_paragraph(f"YouTube tags: {tags_line}")

        if preview:
            try:
                image = ImageReader(str(preview))
                iw, ih = image.getSize()
                max_w = right - left
                max_h = 220
                scale = min(max_w / iw, max_h / ih)
                w = iw * scale
                h = ih * scale
                if y - h < 50:
                    new_page()
                pdf.drawImage(image, left, y - h, width=w, height=h, preserveAspectRatio=True, mask="auto")
                y -= h + 12
            except Exception:
                pass

        draw_heading("Description excerpt")
        excerpt = description[:1800] if description else "No YouTube description file was generated."
        draw_paragraph(excerpt)

        draw_heading("Status summary")
        for key, value in sorted(status.items()):
            draw_paragraph(f"- {key}: {value}")

        draw_heading("Generated materials")
        for path in materials[:30]:
            draw_paragraph(f"- {Path(path).name}")

        pdf.save()
        if error_path.exists():
            error_path.unlink(missing_ok=True)
        return str(report_path), "completed"
    except Exception as exc:  # noqa: BLE001
        _write_text(error_path, f"PDF generation failed: {exc}\n")
        return None, f"failed: {exc}"


def _organize_system_files(workspace: Path) -> list[str]:
    """Move internal/system files into _SYSTEM folder to keep workspace root cleaner."""
    system_dir = workspace / SYSTEM_FILES_DIRNAME
    system_dir.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    internal_names = [
        "INSTRUCTIONS FOR SYSTEM.md",
        "PUBLISHING INSTRUCTIONS.md",
        "SMM-HEAD-AGENT.md",
        "PRODUCER-AGENT.md",
        "SMM-MANAGER-AGENT.md",
        "ARTICLE-CREATOR-AGENT.md",
        "PUBLISHING PLAN.md",
        "X DEVELOPMENT BACKLOG.md",
    ]

    for name in internal_names:
        src = workspace / name
        if not src.exists() or not src.is_file():
            continue
        dst = system_dir / name
        try:
            shutil.move(str(src), str(dst))
            moved.append(name)
        except Exception:
            continue
    return moved


def generate_marketing_materials(
    workspace_dir: str | Path,
    transcript_path: str | Path,
    stream_title: str,
    niche: str,
    thumbnail_provider: str = "chatgpt",
) -> dict:
    workspace = Path(workspace_dir).expanduser().resolve()
    transcript_file = Path(transcript_path).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(f"Workspace folder not found: {workspace}")
    if not transcript_file.exists() or not transcript_file.is_file():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

    if transcript_file.suffix.lower() == ".srt":
        items = parse_srt(transcript_file)
        segments = [
            TranscriptSegment(start=item.start, end=item.end, text=item.text, confidence=1.0)
            for item in items
            if item.text.strip()
        ]
        transcript_text = _transcript_to_text(segments)
    else:
        transcript_text = transcript_file.read_text(encoding="utf-8").strip()
        segments = _segments_from_plain_text(transcript_text)

    hooks = _top_sentences(segments, limit=8)
    phrases = _top_phrases(transcript_text, limit=14)

    producer_result = _run_producer_agent(
        workspace=workspace,
        stream_title=stream_title,
        niche=niche,
        hooks=hooks,
        phrases=phrases,
        transcript_text=transcript_text,
        thumbnail_provider=thumbnail_provider,
    )
    smm_result = _run_smm_manager_agent(
        workspace=workspace,
        stream_title=stream_title,
        niche=niche,
        hooks=hooks,
    )
    article_result = _run_article_creator_agent(
        workspace=workspace,
        stream_title=stream_title,
        niche=niche,
        transcript_text=transcript_text,
        hooks=hooks,
        phrases=phrases,
    )

    thumbnail_files = producer_result.get("thumbnail_files", [])
    primary_thumbnail_root = _promote_primary_thumbnail_to_workspace_root(workspace, thumbnail_files)

    status = {
        **(producer_result.get("status") or {}),
        **(smm_result.get("status") or {}),
        **(article_result.get("status") or {}),
    }

    materials = [
        *(producer_result.get("files") or []),
        *(smm_result.get("files") or []),
        *(article_result.get("files") or []),
        *([primary_thumbnail_root] if primary_thumbnail_root else []),
    ]

    pdf_path, pdf_status = _generate_workspace_pdf_report(
        workspace=workspace,
        stream_title=stream_title,
        niche=niche,
        materials=materials,
        status=status,
    )
    status["pdf_report"] = pdf_status
    if pdf_path:
        materials.append(pdf_path)

    moved_internal = _organize_system_files(workspace)
    if moved_internal:
        status["system_files_organized"] = f"completed ({len(moved_internal)} moved to {SYSTEM_FILES_DIRNAME}/)"

    manifest_path = workspace / "workflow_manifest.json"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload_status = payload.get("status", {})
            if isinstance(payload_status, dict):
                payload_status.update(status)
            else:
                payload["status"] = status
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {
        "workspace": str(workspace),
        "transcript": str(transcript_file),
        "materials": materials,
        "status_updates": status,
    }


def _base_instructions(
    stream_title: str,
    niche: str,
    youtube_channels: list[str],
    platforms: list[str],
) -> str:
    channel_lines = "\n".join(f"- {name}" for name in youtube_channels) if youtube_channels else "- Channel 1\n- Channel 2\n- Channel 3"
    platform_lines = "\n".join(f"- {name}" for name in platforms)
    return f"""# INSTRUCTIONS FOR SYSTEM

This folder is a complete distribution package generated from one stream recording.

## Goal

Convert one stream recording into marketing assets and publication-ready content across all channels.

## Stream Context

- Stream title: {stream_title}
- Content niche: {niche}

## Distribution Targets

{platform_lines}

## YouTube Targets

{channel_lines}

## Deliverables In This Folder

1. INSTRUCTIONS FOR SYSTEM: main execution prompt and workflow rules.
2. W2V INSIGHTS: market research based on YouTube content in this niche.
3. VIDEO: original stream recording.
4. TRANSCRIBATION: plain text transcript.
5. MARKETING TAKES: strongest hooks, points, and opportunities from transcript.
6. PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK): reusable visual assets.
7. THUMBNAIL CREATION: prompt pack and thumbnail drafts.
8. SEO AND DATA FOR VIDEO: titles, descriptions, tags, chapters.
9. SHORTS CREATION: short clip plan and rendering notes.
10. SMM DATA: platform-specific social posts.
11. ARTICLES: long-form SEO articles for Medium/Substack.
12. PUBLISHING PLAN: OAuth and scheduler integration plan (Postiz or alternative).
13. X DEVELOPMENT BACKLOG: future dedicated X growth and automation agent.

## Execution Rules

- Preserve factual correctness from transcript and avoid adding fabricated claims.
- Keep content platform-native; do not publish one generic text everywhere.
- Keep a clear call to action per platform.
- Add language variants when relevant (RU and EN).
- Respect policy and copyright constraints for visuals and clips.

## Publishing Stack

- Primary target: Postiz with OAuth publishing.
- Fallback: direct API integrations per platform.
- Required outcome: queue-ready posts for all listed channels.
"""


def create_stream_workspace(
    workspace_root: str | Path,
    source_video: str | Path | None,
    stream_title: str,
    niche: str,
    config_path: str = "config/default.yaml",
    auto_transcribe: bool = True,
    auto_shorts: bool = True,
    auto_marketing: bool = True,
    thumbnail_provider: str = "chatgpt",
    youtube_channels: list[str] | None = None,
    platforms: list[str] | None = None,
) -> StreamWorkspaceResult:
    root = Path(workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%d %B").lower()
    folder_name = f"{date_str}-{_slugify(stream_title)}"
    run_dir = root / folder_name
    run_dir.mkdir(parents=True, exist_ok=True)

    effective_channels = youtube_channels or DEFAULT_YOUTUBE_CHANNELS
    effective_platforms = platforms or DEFAULT_PLATFORMS

    system_dir = run_dir / SYSTEM_FILES_DIRNAME
    system_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "W2V INSIGHTS.md": "# W2V INSIGHTS\n\n- Niche landscape\n- Competitor formats\n- High-performing hooks\n- Keyword clusters\n",
        "TRANSCRIBATION.txt": "",
        "MARKETING TAKES.md": "# MARKETING TAKES\n\n- Hook 1\n- Hook 2\n- Topic clusters\n- CTA options\n",
        "THUMBNAIL CREATION.md": "# THUMBNAIL CREATION\n\n- Concepts\n- Prompt drafts\n- Style variants\n",
        "SEO AND DATA FOR VIDEO.md": "# SEO AND DATA FOR VIDEO\n\n- Title variants\n- Description\n- Tags\n- Chapters\n",
        "SHORTS SEO.md": "# SHORTS SEO\n\n- Clip names and descriptions will be generated by Producer agent.\n",
        "SHORTS CREATION.md": "# SHORTS CREATION\n\n- Shorts candidates\n- Visual style notes\n- Render status\n",
        "SMM DATA.md": "# SMM DATA\n\n- Facebook post\n- Discord post\n- LinkedIn post\n- Optional variants\n",
        "ARTICLES.md": "# ARTICLES\n\n- Medium draft\n- Substack draft\n- SEO keyword map\n",
    }

    system_files = {
        "INSTRUCTIONS FOR SYSTEM.md": _base_instructions(
            stream_title=stream_title,
            niche=niche,
            youtube_channels=effective_channels,
            platforms=effective_platforms,
        ),
        "SMM-HEAD-AGENT.md": _build_smm_head_agent_instructions(),
        "PRODUCER-AGENT.md": _build_producer_agent_instructions(),
        "SMM-MANAGER-AGENT.md": _build_smm_manager_agent_instructions(),
        "ARTICLE-CREATOR-AGENT.md": _build_article_creator_agent_instructions(),
        "PUBLISHING PLAN.md": "# PUBLISHING PLAN\n\n- OAuth credentials status\n- Postiz mapping\n- Queue and schedule\n",
        "X DEVELOPMENT BACKLOG.md": "# X DEVELOPMENT BACKLOG\n\n- Agent scope\n- Growth experiments\n- Posting automation\n",
    }

    for filename, content in files.items():
        _write_text(run_dir / filename, content)

    for filename, content in system_files.items():
        _write_text(system_dir / filename, content)

    _write_text(system_dir / "PUBLISHING INSTRUCTIONS.md", _build_publishing_instructions(effective_channels))

    video_dir = run_dir / "VIDEO"
    photobank_dir = run_dir / "PHOTOS AND MATERIALS FOR PREVIEWS (PHOTOBANK)"

    video_dir.mkdir(parents=True, exist_ok=True)
    photobank_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "SHORTS").mkdir(parents=True, exist_ok=True)
    (run_dir / "THUMBNAILS").mkdir(parents=True, exist_ok=True)
    _write_platform_templates(run_dir, effective_channels)

    copied_video_path: Path | None = None
    transcription_path: Path | None = None
    shorts_job_id: str | None = None
    shorts_clips: list[str] = []
    shorts_job_dir: str | None = None
    photobank_files: list[str] = []
    statuses = {
        "transcription": "pending",
        "photobank": "pending",
        "marketing_takes": "pending",
        "thumbnail_creation": "pending",
        "seo_package": "pending",
        "shorts_creation": "pending",
        "smm_package": "pending",
        "articles": "pending",
        "publishing": "pending",
    }
    transcript_segments: list[TranscriptSegment] = []
    transcript_text = ""

    if source_video:
        source_path = Path(source_video).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Source video not found: {source_path}")
        copied_video_path = video_dir / source_path.name
        if not copied_video_path.exists() or not copied_video_path.is_symlink():
            # Remove partial copy left by a failed previous run
            if copied_video_path.exists() and not copied_video_path.is_symlink():
                copied_video_path.unlink()
            try:
                copied_video_path.symlink_to(source_path)
            except OSError:
                copied_video_path = source_path

        try:
            extracted = _extract_stream_screenshots(copied_video_path, photobank_dir)
            photobank_files = [str(path) for path in extracted]
            if extracted:
                index_content = "# PHOTOBANK INDEX\n\n" + "\n".join(f"- {path.name}" for path in extracted) + "\n"
                _write_text(photobank_dir / "PHOTOBANK_INDEX.md", index_content)
                statuses["photobank"] = f"completed ({len(extracted)} screenshots)"
            else:
                statuses["photobank"] = "failed: no screenshots extracted"
        except Exception as exc:  # noqa: BLE001
            statuses["photobank"] = f"failed: {exc}"

        settings = load_settings(config_path)

        if auto_transcribe:
            transcription_path = run_dir / "TRANSCRIBATION.txt"
            try:
                transcript_segments = produce_transcript(
                    settings=settings,
                    video_path=copied_video_path,
                    subtitle_hint=None,
                    output_srt_path=run_dir / "TRANSCRIBATION.srt",
                )
                transcript_text = _transcript_to_text(transcript_segments)
                _write_text(transcription_path, transcript_text)
                statuses["transcription"] = "completed"
            except Exception as exc:  # noqa: BLE001
                statuses["transcription"] = f"failed: {exc}"

    if auto_marketing and transcript_segments:
        result = generate_marketing_materials(
            workspace_dir=run_dir,
            transcript_path=run_dir / "TRANSCRIBATION.txt",
            stream_title=stream_title,
            niche=niche,
            thumbnail_provider=thumbnail_provider,
        )
        for key, value in (result.get("status_updates") or {}).items():
            statuses[key] = value

    if auto_shorts:
        try:
            job = run_pipeline(settings, str(copied_video_path))
            if job.status == JobStatus.completed:
                shorts_job_id = job.id
                shorts_job_dir = str(Path(settings.app.output_dir) / job.id)
                shorts_clips = [clip.output_path for clip in job.result.clips]
                for clip_path in shorts_clips:
                    clip_src = Path(clip_path)
                    if clip_src.exists():
                        shutil.copy2(clip_src, run_dir / "SHORTS" / clip_src.name)
                statuses["shorts_creation"] = "completed"
            else:
                message = "; ".join(job.errors) if job.errors else "shorts pipeline failed"
                statuses["shorts_creation"] = f"failed: {message}"
        except Exception as exc:  # noqa: BLE001
            statuses["shorts_creation"] = f"failed: {exc}"

    _write_text(
        run_dir / "SHORTS CREATION.md",
        _build_shorts_report(shorts_job_id, shorts_clips, shorts_job_dir),
    )

    manifest_path = run_dir / "workflow_manifest.json"
    manifest_payload = {
        "created_at": datetime.now().isoformat(),
        "stream_title": stream_title,
        "niche": niche,
        "youtube_channels": effective_channels,
        "platforms": effective_platforms,
        "config_path": config_path,
        "auto_transcribe": auto_transcribe,
        "auto_shorts": auto_shorts,
        "auto_marketing": auto_marketing,
        "thumbnail_provider": thumbnail_provider,
        "source_video": str(copied_video_path) if copied_video_path else None,
        "photobank_files": photobank_files,
        "transcription_output": str(transcription_path) if transcription_path else None,
        "shorts_job_id": shorts_job_id,
        "status": statuses,
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Keep root cleaner even for freshly created workspaces.
    _organize_system_files(run_dir)

    return StreamWorkspaceResult(
        root=run_dir,
        source_video_path=copied_video_path,
        manifest_path=manifest_path,
        transcription_path=transcription_path,
        shorts_job_id=shorts_job_id,
    )