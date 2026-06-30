"""Producer Report generator — creates SEO.pdf for a processed video.

Called by intake_agent when video status is GOOD (ready_to_post / ready_as_video).
Generates:
  1. 5 title options
  2. Thumbnail prompt + launches ChatGPT if available
  3. YouTube description (using seo_rules.yaml)
  4. Tags
  5. Shorts TZ (3 briefs)
  6. Packs everything into SEO.pdf
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from content_distribution.models.contracts import (
    ProducerReport,
    TimecodeEntry,
    TranscriptSegment,
    VideoStatus,
)

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "seo_rules.yaml"


def _load_rules() -> dict:
    if _RULES_PATH.exists():
        try:
            return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Context loaders
# ---------------------------------------------------------------------------

def _load_text_files(directory: Path, exts: tuple = (".md", ".txt"), max_chars: int = 6000) -> str:
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
                    if total >= max_chars:
                        break
            except Exception:
                continue
    return "\n\n".join(parts)


def _load_context(about_me_dir: str, research_dir: str) -> tuple[str, str]:
    about_me = _load_text_files(Path(about_me_dir))
    research = _load_text_files(Path(research_dir) / "DATA") + "\n\n" + _load_text_files(Path(research_dir) / "SCRIPTS")
    return about_me.strip(), research.strip()


# ---------------------------------------------------------------------------
# Photo from ABOUT ME — rotation (move used photos to USED/)
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _pick_author_photo(about_me_dir: str) -> Optional[Path]:
    """Return the first available photo from ABOUT ME/, skip USED/ subfolder."""
    base = Path(about_me_dir)
    if not base.exists():
        return None
    candidates = sorted(
        f for f in base.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
    )
    return candidates[0] if candidates else None


def _mark_photo_used(photo_path: Path) -> None:
    """Move used photo to ABOUT ME/USED/ so it won't be picked again."""
    used_dir = photo_path.parent / "USED"
    used_dir.mkdir(exist_ok=True)
    dest = used_dir / photo_path.name
    # If destination already exists, add suffix
    if dest.exists():
        dest = used_dir / (photo_path.stem + "_" + datetime.now().strftime("%Y%m%d%H%M%S") + photo_path.suffix)
    photo_path.rename(dest)


# ---------------------------------------------------------------------------
# LLM helper (same pattern as assessor.py)
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


def _call_llm(messages: list[dict], max_tokens: int = 2000) -> str | None:
    openai_key = os.getenv("OPENAI_API_KEY", "") or _get_secret("OPENAI_API_KEY")
    copilot_token = os.getenv("GITHUB_COPILOT_TOKEN", "") or _get_secret("GITHUB_COPILOT_TOKEN")
    local_url = os.getenv("LLM_BASE_URL", "") or _get_secret("LLM_BASE_URL")
    llm_model = os.getenv("LLM_MODEL", "") or _get_secret("LLM_MODEL") or "gpt-4o-mini"

    attempts: list[tuple[str, str, str]] = []
    if local_url:
        attempts.append((local_url.rstrip("/") + "/v1/chat/completions", openai_key or copilot_token or "local", llm_model))
    if openai_key:
        attempts.append(("https://api.openai.com/v1/chat/completions", openai_key, llm_model))
    if copilot_token:
        attempts.append(("https://models.inference.ai.azure.com/chat/completions", copilot_token, "gpt-4o-mini"))

    for url, key, model in attempts:
        if not key:
            continue
        try:
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": max_tokens,
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Content generators
# ---------------------------------------------------------------------------

def _transcript_sample(segments: list[TranscriptSegment], max_chars: int = 4000) -> str:
    text = " ".join(s.text for s in segments).strip()
    return text[:max_chars] if len(text) > max_chars else text


def _build_system_prompt(about_me: str, research: str, rules: dict) -> str:
    parts = [
        "Ты — опытный контент-продюсер и SEO-стратег для YouTube. "
        "Твоя задача — создавать контент, который максимально отражает личный бренд автора и выигрывает у конкурентов.",
    ]
    if about_me:
        parts.append(f"\nДАННЫЕ ОБ АВТОРЕ:\n{about_me}")
    if research:
        parts.append(f"\nАНАЛИЗ КОНКУРЕНТОВ:\n{research[:3000]}")
    parts.append(
        "\nПравило: отвечай ТОЛЬКО на русском языке, будь конкретным, избегай клише и воды."
    )
    return "\n".join(parts)


def _generate_titles(
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    video_filename: str,
    about_me: str,
    research: str,
    rules: dict,
) -> list[str]:
    rules_titles = rules.get("titles", {})
    count = rules_titles.get("count", 5)
    style = rules_titles.get("style", "")
    banned = ", ".join(rules_titles.get("banned_words", []))

    transcript = _transcript_sample(segments)
    tc_topics = "\n".join(f"- {tc.title}" for tc in timecodes[:10])

    system = _build_system_prompt(about_me, research, rules)
    user = (
        f"Видео: {video_filename}\n"
        f"Темы из таймкодов:\n{tc_topics or 'нет'}\n\n"
        f"Начало транскрипции:\n{transcript[:2000]}\n\n"
        f"Требования к заголовкам:\n{style}\n"
        f"Запрещённые слова: {banned}\n\n"
        f"Создай {count} вариантов заголовков для YouTube. "
        "Каждый заголовок — на отдельной строке. Только заголовки, без нумерации и пояснений."
    )

    result = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=400)

    if result:
        titles = [line.strip().lstrip("–-•123456789. ") for line in result.splitlines() if line.strip()]
        titles = [t for t in titles if len(t) > 5]
        if titles:
            return titles[:count]

    # Heuristic fallback
    filename_clean = Path(video_filename).stem.replace("_", " ").replace("-", " ")
    return [
        f"Как я {filename_clean.lower()[:40]}",
        f"Почему {filename_clean.lower()[:40]}",
        f"Что происходит когда {filename_clean.lower()[:35]}",
        f"{filename_clean[:50]} — разбор",
        f"Мой опыт: {filename_clean.lower()[:45]}",
    ][:count]


def _generate_thumbnail_prompt(
    titles: list[str],
    video_filename: str,
    about_me: str,
    rules: dict,
) -> str:
    style = rules.get("thumbnail", {}).get("style_description", "")
    main_title = titles[0] if titles else video_filename

    system = _build_system_prompt(about_me, "", rules)
    user = (
        f"Главный заголовок видео: {main_title}\n"
        f"Стиль превью канала:\n{style}\n\n"
        "Напиши промт для генерации превью YouTube на русском языке. "
        "Промт должен описывать: композицию, расположение лица автора, текст на превью (не более 5 слов), "
        "цветовую схему, настроение. Промт — 3-5 предложений. "
        "Обязательно явно укажи: НУЖНА ОДНА финальная картинка, без коллажа, без split-screen, "
        "без сетки из вариантов, без 2x2/3x1 панелей."
    )

    result = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=300)

    return result or (
        f"YouTube превью 1280×720px. Тёмный фон, синий/фиолетовый акцент. "
        f"Крупный план лица автора слева. Жирный белый текст справа: «{(titles[0] if titles else main_title)[:30]}». "
        "Высокий контраст, читаемо на мобильном. ОДНА финальная картинка, без коллажа и без нескольких вариантов в одном кадре."
    )


def _generate_description(
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    titles: list[str],
    about_me: str,
    research: str,
    rules: dict,
) -> str:
    rules_desc = rules.get("description", {})
    structure = rules_desc.get("structure", "")
    cta = rules_desc.get("cta_template", "")
    max_chars = rules_desc.get("max_chars", 2500)

    transcript = _transcript_sample(segments)
    tc_lines = "\n".join(f"{tc.timestamp} — {tc.title}" for tc in timecodes)
    main_title = titles[0] if titles else "Видео"

    system = _build_system_prompt(about_me, research, rules)
    user = (
        f"Заголовок видео: {main_title}\n"
        f"Таймкоды:\n{tc_lines or 'нет'}\n\n"
        f"Начало транскрипции:\n{transcript[:2000]}\n\n"
        f"Структура описания:\n{structure}\n\n"
        f"Призыв к действию:\n{cta}\n\n"
        f"Напиши описание к видео YouTube (максимум {max_chars} символов). "
        "Добавь таймкоды в тело описания. Закончи хэштегами."
    )

    result = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=900)

    if result:
        return result[:max_chars]

    # Fallback
    lines = [main_title, "", "В этом видео я рассказываю о своём опыте.", ""]
    if tc_lines:
        lines += ["ГЛАВЫ:", tc_lines, ""]
    lines += [cta, "", "#видео #контент #ютуб"]
    return "\n".join(lines)[:max_chars]


def _generate_tags(
    segments: list[TranscriptSegment],
    titles: list[str],
    about_me: str,
    rules: dict,
) -> list[str]:
    rules_tags = rules.get("tags", {})
    count = rules_tags.get("count", 15)
    channel_tags = rules_tags.get("channel_tags") or []
    transcript = _transcript_sample(segments, max_chars=2000)
    main_title = titles[0] if titles else ""

    system = _build_system_prompt(about_me, "", rules)
    user = (
        f"Заголовок видео: {main_title}\n"
        f"Транскрипция (фрагмент):\n{transcript}\n\n"
        f"Создай {count} тегов для YouTube. "
        "Теги через запятую, без # и без кавычек. Только теги, никакого лишнего текста."
    )

    result = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=200)

    tags = channel_tags[:]
    if result:
        parsed = [t.strip().lstrip("#") for t in re.split(r"[,\n]", result) if t.strip()]
        tags += [t for t in parsed if 2 <= len(t) <= 50]

    # Fallback heuristic tags from title
    if not tags:
        words = re.findall(r"[А-Яа-яA-Za-z]{4,}", main_title)
        tags = list(dict.fromkeys(words))[:count]

    return list(dict.fromkeys(tags))[:count]


def _generate_shorts_tz(
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    titles: list[str],
    about_me: str,
    rules: dict,
) -> list[str]:
    rules_shorts = rules.get("shorts_tz", {})
    count = rules_shorts.get("count", 3)
    duration = rules_shorts.get("duration_seconds", 60)
    style = rules_shorts.get("style", "")
    transcript = _transcript_sample(segments)
    tc_lines = "\n".join(f"{tc.timestamp} — {tc.title}" for tc in timecodes[:15])
    main_title = titles[0] if titles else "видео"

    system = _build_system_prompt(about_me, "", rules)
    user = (
        f"Видео: {main_title}\n"
        f"Таймкоды:\n{tc_lines or 'нет'}\n\n"
        f"Транскрипция (начало):\n{transcript[:2000]}\n\n"
        f"Требования к шортс:\n{style}\n\n"
        f"Создай ТЗ для {count} шортс видео (по {duration} сек каждое). "
        "Для каждого шортс дай:\n"
        "- ХУУК (первые 3 сек — цепляющая фраза)\n"
        "- ТАЙМИНГ (какой момент из оригинального видео использовать)\n"
        "- СУТЬ (одна главная мысль)\n"
        "- ФИНАЛ (последние 5 сек — вывод и призыв)\n\n"
        f"Оформи {count} блоков. Разделяй блоки строкой '---'."
    )

    result = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=1200)

    if result:
        blocks = [b.strip() for b in result.split("---") if b.strip()]
        if blocks:
            return blocks[:count]

    # Fallback
    fallback = []
    for i, tc in enumerate(timecodes[:count], 1):
        fallback.append(
            f"ШОРТС #{i}\n"
            f"ХУУК: «{tc.title[:60]}»\n"
            f"ТАЙМИНГ: {tc.timestamp}\n"
            f"СУТЬ: {tc.description[:100] if tc.description else tc.title}\n"
            f"ФИНАЛ: Подпишись чтобы не пропустить следующее видео."
        )
    return fallback or [f"ШОРТС #1\nТайминг: 00:00:00\nСуть: {main_title}"]


# ---------------------------------------------------------------------------
# Thumbnail via ChatGPT desktop (reuses stream_automation logic)
# ---------------------------------------------------------------------------

def _try_chatgpt_thumbnail(
    work_dir: Path,
    titles: list[str],
    thumbnail_prompt: str,
    photo_path: Optional[Path],
    thumbnail_index: int = 1,
) -> Optional[str]:
    """
    Try to generate a thumbnail via the ChatGPT desktop app.
    Returns path to saved thumbnail file, or None.
    """
    try:
        # Reuse the automation module's clipboard + AppleScript approach
        from content_distribution.services.stream_automation import (  # type: ignore
            _set_clipboard_image,
            _chatgpt_prepare_window,
            _short_thumbnail_text,
        )
    except ImportError:
        return None

    try:
        import subprocess, time
        thumb_dir = work_dir / "THUMBNAILS"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        # Put author photo on clipboard
        if photo_path and photo_path.exists():
            _set_clipboard_image(photo_path)

        bounds = _chatgpt_prepare_window()
        if not bounds:
            return None

        bx, by, bw, bh = bounds
        input_x = bx + int(bw * 0.60)
        input_y = by + bh - 40

        hard_constraints = (
            " IMPORTANT: Generate exactly ONE final thumbnail image only."
            " No collage, no split-screen, no grid, no multiple variants in one frame."
        )
        prompt_to_send = (thumbnail_prompt + hard_constraints)[:500]

        # Paste image then send prompt
        paste_script = f"""
tell application "System Events"
    tell process "ChatGPT"
        set frontmost to true
        delay 0.5
        click at {{{input_x}, {input_y}}}
        delay 0.3
        keystroke "v" using {{command down}}
        delay 1.5
    end tell
end tell
"""
        subprocess.run(["osascript", "-e", paste_script], capture_output=True)
        time.sleep(1.5)

        # Type prompt
        type_script = f"""
tell application "System Events"
    tell process "ChatGPT"
        keystroke "{prompt_to_send.replace(chr(34), chr(39)).replace(chr(10), ' ')}"
        delay 0.5
        key code 36
    end tell
end tell
"""
        subprocess.run(["osascript", "-e", type_script], capture_output=True)

        # Wait for generation (up to 120s) + grab from Downloads
        downloads = Path.home() / "Downloads"
        before = {
            f.name for f in downloads.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        } if downloads.exists() else set()

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            time.sleep(4)
            if not downloads.exists():
                continue
            new_files = [
                f for f in downloads.iterdir()
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                and f.name not in before
            ]
            if new_files:
                src = max(new_files, key=lambda f: f.stat().st_mtime)
                dest = thumb_dir / f"thumbnail_{thumbnail_index}{src.suffix}"
                import shutil
                shutil.copy2(src, dest)
                return str(dest)

        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PDF Generation
# ---------------------------------------------------------------------------

def _seconds_to_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _generate_seo_pdf(
    output_path: Path,
    video_filename: str,
    duration_seconds: float,
    status: VideoStatus,
    rating: int,
    assessment: str,
    report: ProducerReport,
    created_at: datetime,
) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, Image as RLImage, KeepTogether,
        )
        from reportlab.lib.enums import TA_LEFT
    except ImportError:
        _seo_txt_fallback(output_path, report, video_filename)
        return

    W, H = A4
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    S = {
        "h1":    style("H1",   fontSize=18, leading=22, fontName="Helvetica-Bold",
                       textColor=colors.HexColor("#1a1a2e"), spaceAfter=6),
        "h2":    style("H2",   fontSize=13, leading=17, fontName="Helvetica-Bold",
                       textColor=colors.HexColor("#1a3a6e"), spaceAfter=4, spaceBefore=12),
        "meta":  style("Meta", fontSize=9,  textColor=colors.HexColor("#666666"), spaceAfter=3),
        "body":  style("Body", fontSize=10, leading=15, textColor=colors.HexColor("#333333"), spaceAfter=6),
        "tag":   style("Tag",  fontSize=9,  textColor=colors.HexColor("#1a6fb5")),
        "num":   style("Num",  fontSize=11, fontName="Helvetica-Bold",
                       textColor=colors.HexColor("#222222"), spaceAfter=5),
        "small": style("Sm",   fontSize=8,  textColor=colors.HexColor("#888888")),
        "status_good":   style("SG",  fontSize=14, fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#1a8c3e")),
        "status_clips":  style("SC",  fontSize=14, fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#cc7700")),
        "status_video":  style("SV",  fontSize=14, fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#1a6fb5")),
        "status_weak":   style("SW",  fontSize=14, fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#c01010")),
    }

    _STATUS_STYLES = {
        VideoStatus.ready_to_post:  ("✅ ГОТОВО К ПОСТИНГУ",  "status_good"),
        VideoStatus.cut_to_clips:   ("✂️  РЕЗАТЬ НА КЛИПЫ",   "status_clips"),
        VideoStatus.ready_as_video: ("🎬 ГОТОВО КАК ВИДЕО",   "status_video"),
        VideoStatus.weak_content:   ("⚠️  СЛАБЫЙ КОНТЕНТ",     "status_weak"),
    }

    label, sstyle = _STATUS_STYLES.get(status, ("НЕИЗВЕСТНО", "body"))
    dur_h, dur_rem = divmod(int(duration_seconds), 3600)
    dur_m, dur_s = divmod(dur_rem, 60)
    dur_str = f"{dur_h}ч {dur_m}мин" if dur_h else f"{dur_m}мин {dur_s}сек"

    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("SEO-ОТЧЁТ ПРОДЮСЕРА", S["h1"]))
    story.append(Paragraph(f"Файл: <b>{video_filename}</b>", S["meta"]))
    story.append(Paragraph(
        f"Дата: {created_at.strftime('%d.%m.%Y %H:%M')}  |  Длительность: {dur_str}", S["meta"]
    ))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"{label}   •   Оценка: <b>{rating}/10</b>", S[sstyle]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(assessment.replace("\n", "<br/>"), S["body"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.3 * cm))

    # ── Thumbnail ────────────────────────────────────────────────────────────
    story.append(Paragraph("1. ПРЕВЬЮ (THUMBNAIL)", S["h2"]))
    if report.thumbnail_path and Path(report.thumbnail_path).exists():
        try:
            thumb_img = RLImage(
                report.thumbnail_path,
                width=10 * cm,
                height=5.6 * cm,
                kind="proportional",
            )
            story.append(thumb_img)
            story.append(Spacer(1, 0.2 * cm))
        except Exception:
            pass
    story.append(Paragraph("<b>Промт для генерации превью:</b>", S["body"]))
    story.append(Paragraph(report.thumbnail_prompt.replace("\n", "<br/>"), S["body"]))
    story.append(Spacer(1, 0.3 * cm))

    # ── Titles ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#eeeeee")))
    story.append(Paragraph("2. ВАРИАНТЫ НАЗВАНИЙ", S["h2"]))
    for i, title in enumerate(report.titles, 1):
        story.append(Paragraph(f"<b>{i}.</b>  {title}", S["num"]))
    story.append(Spacer(1, 0.3 * cm))

    # ── Description ──────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#eeeeee")))
    story.append(Paragraph("3. ОПИСАНИЕ К ВИДЕО", S["h2"]))
    desc_lines = report.description.replace("\n", "<br/>")
    story.append(Paragraph(desc_lines, S["body"]))
    story.append(Spacer(1, 0.3 * cm))

    # ── Tags ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#eeeeee")))
    story.append(Paragraph("4. ТЕГИ", S["h2"]))
    tags_line = ",  ".join(report.tags)
    story.append(Paragraph(tags_line, S["tag"]))
    story.append(Spacer(1, 0.3 * cm))

    # ── Shorts TZ ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#eeeeee")))
    story.append(Paragraph("5. ТЗ НА ШОРТС", S["h2"]))
    for i, tz in enumerate(report.shorts_tz, 1):
        story.append(Paragraph(f"<b>Шортс #{i}</b>", S["body"]))
        story.append(Paragraph(tz.replace("\n", "<br/>"), S["body"]))
        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)


def _seo_txt_fallback(output_path: Path, report: ProducerReport, video_filename: str) -> None:
    txt_path = output_path.with_suffix(".txt")
    lines = [
        f"SEO-ОТЧЁТ: {video_filename}", "",
        "=== НАЗВАНИЯ ===",
        *[f"{i}. {t}" for i, t in enumerate(report.titles, 1)],
        "",
        "=== ПРОМТ ДЛЯ ПРЕВЬЮ ===",
        report.thumbnail_prompt, "",
        "=== ОПИСАНИЕ ===",
        report.description, "",
        "=== ТЕГИ ===",
        ", ".join(report.tags), "",
        "=== ТЗ НА ШОРТС ===",
        *[f"\n--- Шортс #{i} ---\n{tz}" for i, tz in enumerate(report.shorts_tz, 1)],
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_producer_report(
    work_dir: Path,
    video_filename: str,
    duration_seconds: float,
    status: VideoStatus,
    rating: int,
    assessment: str,
    segments: list[TranscriptSegment],
    timecodes: list[TimecodeEntry],
    about_me_dir: str,
    research_dir: str,
    created_at: datetime | None = None,
) -> ProducerReport:
    """Generate SEO.pdf and return ProducerReport with all generated content."""
    now = created_at or datetime.now()
    rules = _load_rules()
    about_me, research = _load_context(about_me_dir, research_dir)

    # 1. Generate titles
    titles = _generate_titles(segments, timecodes, video_filename, about_me, research, rules)

    # 2. Pick author photo from ABOUT ME/
    photo_path = _pick_author_photo(about_me_dir)

    # 3. Thumbnail prompt
    thumbnail_prompt = _generate_thumbnail_prompt(titles, video_filename, about_me, rules)

    # 4. Try to generate actual thumbnail via ChatGPT
    thumbnail_file: Optional[str] = None
    existing_thumbs = list((work_dir / "THUMBNAILS").glob("thumbnail_*")) if (work_dir / "THUMBNAILS").exists() else []
    thumb_index = len(existing_thumbs) + 1
    thumbnail_file = _try_chatgpt_thumbnail(work_dir, titles, thumbnail_prompt, photo_path, thumb_index)

    # Mark photo as used only if thumbnail was generated
    if thumbnail_file and photo_path:
        try:
            _mark_photo_used(photo_path)
        except Exception:
            pass

    # 5. Description
    description = _generate_description(segments, timecodes, titles, about_me, research, rules)

    # 6. Tags
    tags = _generate_tags(segments, titles, about_me, rules)

    # 7. Shorts TZ
    shorts_tz = _generate_shorts_tz(segments, timecodes, titles, about_me, rules)

    # 8. Assemble report model
    report = ProducerReport(
        titles=titles,
        thumbnail_prompt=thumbnail_prompt,
        thumbnail_path=thumbnail_file,
        description=description,
        tags=tags,
        shorts_tz=shorts_tz,
    )

    # 9. Generate PDF
    pdf_path = work_dir / "SEO.pdf"
    _generate_seo_pdf(
        output_path=pdf_path,
        video_filename=video_filename,
        duration_seconds=duration_seconds,
        status=status,
        rating=rating,
        assessment=assessment,
        report=report,
        created_at=now,
    )
    report.pdf_path = str(pdf_path)

    return report
