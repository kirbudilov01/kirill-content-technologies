from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from content_distribution.models.contracts import TimecodeEntry, TranscriptSegment


def _get_secret(key: str) -> str:
    env_path = Path(__file__).resolve().parents[3] / "config" / "local.env"
    if not env_path.exists():
        return ""
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _call_llm(
    messages: list[dict],
    model: str,
    max_tokens: int = 1800,
    local_only: bool = True,
) -> str | None:
    openai_key = os.getenv("OPENAI_API_KEY", "") or _get_secret("OPENAI_API_KEY")
    copilot_token = os.getenv("GITHUB_COPILOT_TOKEN", "") or _get_secret("GITHUB_COPILOT_TOKEN")
    local_url = os.getenv("LLM_BASE_URL", "") or _get_secret("LLM_BASE_URL")

    attempts: list[tuple[str, str, str]] = []
    if local_url:
        attempts.append((local_url.rstrip("/") + "/v1/chat/completions", openai_key or copilot_token or "local", model))
    if (not local_only) and openai_key:
        attempts.append(("https://api.openai.com/v1/chat/completions", openai_key, model))
    if (not local_only) and copilot_token:
        attempts.append(("https://models.inference.ai.azure.com/chat/completions", copilot_token, "gpt-4o-mini"))

    for url, key, m in attempts:
        if not key:
            continue
        try:
            payload = json.dumps(
                {
                    "model": m,
                    "messages": messages,
                    "temperature": 0.35,
                    "max_tokens": max_tokens,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


def _fmt_ts(seconds: float) -> str:
    value = max(0, int(seconds))
    hh = value // 3600
    mm = (value % 3600) // 60
    ss = value % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _to_seconds(ts: str) -> float | None:
    parts = ts.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = [int(x) for x in parts]
    except ValueError:
        return None
    return float(h * 3600 + m * 60 + s)


def _prepare_transcript_chunks(segments: list[TranscriptSegment], max_lines: int = 220) -> str:
    lines: list[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        lines.append(f"[{_fmt_ts(seg.start)}-{_fmt_ts(seg.end)}] {text}")
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)


def _fallback_plans(
    timecodes: list[TimecodeEntry],
    shorts_count: int,
    target_seconds: int,
    fragment_min_seconds: int,
) -> list[dict]:
    plans: list[dict] = []
    for idx, tc in enumerate(timecodes[:shorts_count], start=1):
        start = _to_seconds(tc.timestamp)
        if start is None:
            continue
        plans.append(
            {
                "title": tc.title[:70] or f"Short {idx}",
                "fragments": [
                    {
                        "start": tc.timestamp,
                        "end": _fmt_ts(start + max(fragment_min_seconds, target_seconds // 2)),
                        "reason": tc.description[:100] if tc.description else "Strong chapter moment",
                    }
                ],
            }
        )
    return plans


def get_smart_shorts_plans(
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    shorts_tz: list[str],
    duration_seconds: float,
    about_me_context: str,
    research_context: str,
    model: str,
    local_only: bool,
    shorts_count: int,
    target_seconds: int,
    fragment_min_seconds: int,
    fragment_max_seconds: int,
) -> list[dict]:
    """Return list of short plans with multi-fragment structure.

    Output schema per item:
    {
      "title": "...",
      "fragments": [
         {"start":"HH:MM:SS","end":"HH:MM:SS","reason":"..."}
      ]
    }
    """
    transcript = _prepare_transcript_chunks(segments)
    tc_block = "\n".join(f"- {t.timestamp} | {t.title}" for t in timecodes[:20])
    tz_block = "\n\n".join(shorts_tz[:6])

    system_prompt = (
        "You are a senior viral shorts producer. "
        "You must select the best moments and stitch them into coherent shorts from multiple fragments. "
        "Return only valid JSON."
    )

    user_prompt = (
        f"Creator context:\n{about_me_context[:1800]}\n\n"
        f"Competitor context:\n{research_context[:1800]}\n\n"
        f"Duration: {int(duration_seconds)} sec\n"
        f"Need shorts: {shorts_count}\n"
        f"Target short length: ~{target_seconds} sec\n"
        f"Each fragment must be between {fragment_min_seconds} and {fragment_max_seconds} sec\n\n"
        f"Producer shorts hints:\n{tz_block or 'none'}\n\n"
        f"Timecodes:\n{tc_block or 'none'}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Return JSON with this exact schema:\n"
        "{\n"
        '  "shorts": [\n'
        "    {\n"
        '      "title": "...",\n'
        '      "fragments": [\n'
        '        {"start":"HH:MM:SS","end":"HH:MM:SS","reason":"..."}\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules: fragments in chronological order, no overlap, each short must have 2-4 fragments, "
        "total per short close to target length, avoid greetings/filler."
    )

    raw = _call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        max_tokens=2200,
        local_only=local_only,
    )

    if raw:
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            shorts = payload.get("shorts") if isinstance(payload, dict) else None
            if isinstance(shorts, list) and shorts:
                normalized: list[dict] = []
                for item in shorts[:shorts_count]:
                    title = str(item.get("title", "Short")).strip()[:90]
                    frags = item.get("fragments") or []
                    parsed_frags: list[dict] = []
                    for frag in frags:
                        s = str(frag.get("start", "")).strip()
                        e = str(frag.get("end", "")).strip()
                        if not _to_seconds(s) and _to_seconds(s) != 0:
                            continue
                        if _to_seconds(e) is None:
                            continue
                        parsed_frags.append(
                            {
                                "start": s,
                                "end": e,
                                "reason": str(frag.get("reason", "")).strip()[:160],
                            }
                        )
                    if parsed_frags:
                        normalized.append({"title": title or "Short", "fragments": parsed_frags})
                if normalized:
                    return normalized
        except Exception:
            pass

    return _fallback_plans(
        timecodes=timecodes,
        shorts_count=shorts_count,
        target_seconds=target_seconds,
        fragment_min_seconds=fragment_min_seconds,
    )
