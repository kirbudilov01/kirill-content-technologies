"""Assess a video: determine posting status and quality rating.

Reads ABOUT ME/ and RESEARCH/ for context.
Uses LLM if available (OPENAI_API_KEY / GITHUB_COPILOT_TOKEN / LLM_BASE_URL in local.env),
otherwise falls back to heuristics.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

from content_distribution.models.contracts import TimecodeEntry, TranscriptSegment, VideoStatus

# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------

def _load_text_files(directory: Path, exts: tuple[str, ...] = (".md", ".txt")) -> str:
    """Concatenate all text files in directory (non-recursive, max 8000 chars total)."""
    if not directory.exists():
        return ""
    parts: list[str] = []
    total = 0
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix.lower() in exts:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    parts.append(f"=== {f.name} ===\n{content}")
                    total += len(content)
                    if total > 8000:
                        break
            except Exception:
                continue
    return "\n\n".join(parts)


def _load_context(about_me_dir: str, research_dir: str) -> tuple[str, str]:
    about_me = _load_text_files(Path(about_me_dir))
    research_data = _load_text_files(Path(research_dir) / "DATA")
    research_scripts = _load_text_files(Path(research_dir) / "SCRIPTS")
    research = "\n\n".join(filter(None, [research_data, research_scripts]))
    return about_me, research


# ---------------------------------------------------------------------------
# Heuristic scorer
# ---------------------------------------------------------------------------

_HOOK_WORDS = {
    "ошибка", "секрет", "важно", "почему", "как", "лучше", "метод", "система",
    "результат", "совет", "инсайт", "кейс", "разбор", "проблема",
    "mistake", "secret", "important", "how", "why", "best", "result", "tip", "case",
}
_LOW_SIGNAL = {
    "всем привет", "привет ребята", "в этом видео", "подпишись", "ставь лайк",
    "мы продолжаем", "hello everyone", "subscribe", "like and subscribe",
}
_STOPWORDS = {
    "и", "в", "на", "что", "как", "это", "для", "не", "с", "по", "из", "или",
    "а", "же", "уже", "то", "так", "всё", "очень",
}


def _quality_score(segments: list[TranscriptSegment], duration: float) -> float:
    """Return a 0.0–1.0 quality score based on heuristics."""
    if not segments:
        return 0.1

    full_text = " ".join(s.text for s in segments).lower()
    word_tokens = [w for w in re.findall(r"[а-яёa-z]{3,}", full_text) if w not in _STOPWORDS]
    total_words = len(word_tokens) or 1

    # Hook word density
    hook_hits = sum(1 for w in word_tokens if w in _HOOK_WORDS)
    hook_ratio = min(hook_hits / total_words * 15, 1.0)

    # Low-signal penalty
    low_signal_hits = sum(1 for phrase in _LOW_SIGNAL if phrase in full_text)
    low_signal_penalty = min(low_signal_hits * 0.1, 0.4)

    # Vocabulary richness
    unique_ratio = len(set(word_tokens)) / total_words
    richness = min(unique_ratio * 1.5, 1.0)

    # Words-per-minute density (more content → higher score, up to a ceiling)
    words_per_min = (total_words / max(duration / 60, 1))
    density = min(words_per_min / 120, 1.0)

    # Average segment confidence
    avg_conf = sum(s.confidence for s in segments) / len(segments)

    score = (
        hook_ratio * 0.30
        + richness * 0.25
        + density * 0.20
        + avg_conf * 0.15
        - low_signal_penalty
        + 0.10  # base
    )
    return max(0.05, min(score, 1.0))


# ---------------------------------------------------------------------------
# LLM call (mirrors stream_automation._call_llm without importing private fn)
# ---------------------------------------------------------------------------

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


def _call_llm(messages: list[dict], max_tokens: int = 1200) -> str | None:
    openai_key = os.getenv("OPENAI_API_KEY", "") or _get_secret("OPENAI_API_KEY")
    copilot_token = os.getenv("GITHUB_COPILOT_TOKEN", "") or _get_secret("GITHUB_COPILOT_TOKEN")
    local_url = os.getenv("LLM_BASE_URL", "") or _get_secret("LLM_BASE_URL")

    attempts: list[tuple[str, str, str]] = []
    if local_url:
        attempts.append((local_url.rstrip("/") + "/v1/chat/completions", openai_key or copilot_token, "gpt-4o-mini"))
    if openai_key:
        attempts.append(("https://api.openai.com/v1/chat/completions", openai_key, "gpt-4o-mini"))
    if copilot_token:
        attempts.append(("https://models.inference.ai.azure.com/chat/completions", copilot_token, "gpt-4o-mini"))

    for url, key, model in attempts:
        if not key:
            continue
        try:
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": max_tokens,
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_video(
    segments: list[TranscriptSegment],
    duration_seconds: float,
    video_filename: str,
    timecodes: list[TimecodeEntry],
    about_me_dir: str,
    research_dir: str,
    stream_threshold: int = 1800,
    short_video_threshold: int = 300,
) -> tuple[VideoStatus, int, str]:
    """
    Return (status, rating_1_10, assessment_text).
    """
    about_me, research = _load_context(about_me_dir, research_dir)
    quality = _quality_score(segments, duration_seconds)

    # --- Determine base type by duration ---
    if duration_seconds >= stream_threshold:
        base_type = "stream"
    elif duration_seconds <= short_video_threshold:
        base_type = "short"
    else:
        base_type = "video"

    # --- Heuristic status ---
    if base_type == "stream":
        heuristic_status = VideoStatus.cut_to_clips
    elif quality < 0.25:
        heuristic_status = VideoStatus.weak_content
    elif base_type == "short":
        heuristic_status = VideoStatus.ready_as_video
    else:
        heuristic_status = VideoStatus.ready_to_post

    heuristic_rating = max(1, min(10, round(quality * 10)))

    # --- Try LLM assessment ---
    transcript_sample = " ".join(s.text for s in segments[:60])[:3000]
    tc_lines = "\n".join(f"{tc.timestamp} — {tc.title}" for tc in timecodes[:20])

    system_prompt = (
        "Ты — опытный SMM-продюсер и контент-стратег. "
        "Твоя задача: оценить видео и определить лучшую стратегию его распространения.\n\n"
        + (f"ДАННЫЕ ОБ АВТОРЕ:\n{about_me}\n\n" if about_me else "")
        + (f"АНАЛИЗ КОНКУРЕНТОВ:\n{research}\n\n" if research else "")
        + "Отвечай ТОЛЬКО на русском языке. Будь конкретным и практичным."
    )
    user_prompt = (
        f"Файл: {video_filename}\n"
        f"Длительность: {int(duration_seconds // 60)} мин {int(duration_seconds % 60)} сек\n"
        f"Тип (по длине): {base_type}\n\n"
        f"ТАЙМКОДЫ:\n{tc_lines or 'нет'}\n\n"
        f"НАЧАЛО ТРАНСКРИПЦИИ (первые 3000 символов):\n{transcript_sample}\n\n"
        "Дай оценку по следующему формату (строго JSON):\n"
        "{\n"
        '  "status": "ГОТОВО_К_ПОСТИНГУ" | "РЕЗАТЬ_НА_КЛИПЫ" | "ГОТОВО_КАК_ВИДЕО" | "СЛАБЫЙ_КОНТЕНТ",\n'
        '  "rating": <число от 1 до 10>,\n'
        '  "assessment": "<2-4 предложения: что хорошо, что слабо, почему такой статус>"\n'
        "}"
    )

    llm_result = _call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    if llm_result:
        try:
            # Extract JSON from response (sometimes wrapped in markdown)
            json_match = re.search(r"\{.*?\}", llm_result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                status_map = {
                    "ГОТОВО_К_ПОСТИНГУ": VideoStatus.ready_to_post,
                    "РЕЗАТЬ_НА_КЛИПЫ": VideoStatus.cut_to_clips,
                    "ГОТОВО_КАК_ВИДЕО": VideoStatus.ready_as_video,
                    "СЛАБЫЙ_КОНТЕНТ": VideoStatus.weak_content,
                }
                status = status_map.get(parsed.get("status", ""), heuristic_status)
                rating = max(1, min(10, int(parsed.get("rating", heuristic_rating))))
                assessment = str(parsed.get("assessment", "")).strip()
                if assessment:
                    return status, rating, assessment
        except Exception:
            pass

    # --- Heuristic fallback assessment text ---
    duration_fmt = f"{int(duration_seconds // 60)} мин"
    assessment_lines = [
        f"Тип контента: {'стрим' if base_type == 'stream' else 'короткое видео' if base_type == 'short' else 'видео'} ({duration_fmt}).",
    ]
    if quality >= 0.6:
        assessment_lines.append("Контент содержательный — хорошая плотность смысловых единиц и словарное разнообразие.")
    elif quality >= 0.35:
        assessment_lines.append("Контент среднего уровня — есть полезные фрагменты, но структура неровная.")
    else:
        assessment_lines.append("Контент слабый — мало конкретики, высокий процент вводных фраз.")

    if base_type == "stream":
        assessment_lines.append("Рекомендуется нарезать на клипы для публикации в социальных сетях.")
    elif base_type == "short" and quality >= 0.35:
        assessment_lines.append("Подходит для публикации как самостоятельное короткое видео.")
    elif quality < 0.25:
        assessment_lines.append("Рекомендуется доработать или не публиковать.")
    else:
        assessment_lines.append("Можно публиковать целиком или выбрать лучшие фрагменты.")

    return heuristic_status, heuristic_rating, " ".join(assessment_lines)
