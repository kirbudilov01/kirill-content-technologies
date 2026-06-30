#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class Word:
    text: str
    start: float
    end: float


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def probe(video: Path) -> tuple[float, int, int]:
    duration = float(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(video)
    ]))
    raw = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", str(video)
    ])
    stream = json.loads(raw)["streams"][0]
    return duration, int(stream["width"]), int(stream["height"])


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?|[^\sA-Za-z0-9]", text)


def words_only(tokens: list[str]) -> list[str]:
    return [t for t in tokens if re.search(r"[A-Za-z0-9]", t)]


def estimate_word_times(text: str, duration: float) -> list[Word]:
    tokens = tokenize(text)
    words = words_only(tokens)
    if not words:
        return []

    weights = []
    for word in words:
        weights.append(max(0.55, len(word) ** 0.72))
    total_pause = min(duration * 0.18, 0.16 * sum(1 for t in tokens if t in ".?!,;:"))
    speech_duration = max(duration - total_pause, duration * 0.75)
    unit = speech_duration / sum(weights)

    result = []
    t = 0.0
    word_i = 0
    for token in tokens:
        if re.search(r"[A-Za-z0-9]", token):
            dur = weights[word_i] * unit
            result.append(Word(token, t, min(duration, t + dur)))
            t += dur
            word_i += 1
        elif token in ".?!":
            t += 0.20
        elif token in ",;:":
            t += 0.10
    if result:
        stretch = duration / max(duration, result[-1].end)
        result = [Word(w.text, w.start * stretch, w.end * stretch) for w in result]
    return result


def group_words(words: list[Word], max_words: int = 5) -> list[list[Word]]:
    groups = []
    i = 0
    while i < len(words):
        group = words[i:i + max_words]
        groups.append(group)
        i += len(group)
    return groups


def active_group(groups: list[list[Word]], t: float) -> list[Word]:
    for group in groups:
        if group[0].start - 0.08 <= t <= group[-1].end + 0.14:
            return group
    if groups:
        return min(groups, key=lambda g: abs(g[0].start - t))
    return []


def split_lines(group: list[Word]) -> list[list[Word]]:
    if len(group) <= 3:
        return [group]
    mid = math.ceil(len(group) / 2)
    return [group[:mid], group[mid:]]


def fit_font(font_path: str, text: str, max_width: int, start_size: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= 34:
        font = ImageFont.truetype(font_path, size)
        bbox = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), text, font=font, stroke_width=4)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(font_path, size)


def draw_caption_frame(
    width: int,
    height: int,
    group: list[Word],
    now: float,
    font_path: str,
    y_ratio: float,
) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if not group:
        return img

    lines = split_lines(group)
    max_width = int(width * 0.86)
    base_size = int(height * 0.044)
    active_color = (255, 225, 34, 255)
    normal_color = (255, 255, 255, 255)
    outline = (0, 0, 0, 245)
    shadow = (0, 0, 0, 155)

    rendered_lines = []
    total_h = 0
    for line in lines:
        line_text = " ".join(w.text.upper() for w in line)
        font = fit_font(font_path, line_text, max_width, base_size)
        metrics = []
        total_w = 0
        space_w = int(draw.textlength(" ", font=font))
        for word in line:
            text = word.text.upper()
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=4)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            metrics.append((word, text, w, h, font))
            total_w += w
        total_w += space_w * (len(metrics) - 1)
        line_h = max(m[3] for m in metrics)
        rendered_lines.append((metrics, total_w, line_h, space_w))
        total_h += line_h
    total_h += int(base_size * 0.34) * (len(rendered_lines) - 1)

    y = int(height * y_ratio - total_h / 2)
    for metrics, total_w, line_h, space_w in rendered_lines:
        x = int((width - total_w) / 2)
        for word, text, word_w, _word_h, font in metrics:
            is_active = word.start <= now <= word.end
            # quick pop scale by using a slightly bigger font for the active word
            if is_active:
                font = ImageFont.truetype(font_path, int(font.size * 1.10))
                word_w = int(draw.textlength(text, font=font))
            color = active_color if is_active else normal_color
            draw.text((x + 3, y + 5), text, font=font, fill=shadow, stroke_width=5, stroke_fill=shadow)
            draw.text((x, y), text, font=font, fill=color, stroke_width=5, stroke_fill=outline)
            x += word_w + space_w
        y += line_h + int(base_size * 0.34)
    return img


def render_overlay(video: Path, text: str, out: Path, fps: int, y_ratio: float) -> None:
    duration, width, height = probe(video)
    font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    words = estimate_word_times(text, duration)
    groups = group_words(words, max_words=5)

    with tempfile.TemporaryDirectory(prefix="local-captions-") as tmp:
        tmp_path = Path(tmp)
        frame_count = math.ceil(duration * fps)
        for frame in range(frame_count):
            t = frame / fps
            group = active_group(groups, t)
            image = draw_caption_frame(width, height, group, t, font_path, y_ratio)
            image.save(tmp_path / f"frame_{frame:05d}.png")

        overlay_mov = tmp_path / "overlay.mov"
        subprocess.check_call([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps), "-i", str(tmp_path / "frame_%05d.png"),
            "-c:v", "qtrle", "-pix_fmt", "argb", str(overlay_mov)
        ])

        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-i", str(overlay_mov),
            "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[v]",
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
            str(out)
        ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Submagic-like kinetic caption renderer.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--text", help="Caption text")
    parser.add_argument("--text-file", help="Caption text file")
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--y-ratio", type=float, default=0.52, help="Vertical caption center, 0..1")
    args = parser.parse_args()

    if not args.text and not args.text_file:
        raise SystemExit("Pass --text or --text-file")
    text = args.text if args.text else Path(args.text_file).read_text(encoding="utf-8")
    text = " ".join(text.split())
    render_overlay(Path(args.video), text, Path(args.out), args.fps, args.y_ratio)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
