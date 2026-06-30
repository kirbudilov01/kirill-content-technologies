from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})"
)


@dataclass
class SrtItem:
    index: int
    start: float
    end: float
    text: str


def parse_timestamp(value: str) -> float:
    match = _TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    millis = int(match.group("ms"))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def to_timestamp(value: float) -> str:
    value = max(0.0, value)
    total_ms = int(round(value * 1000))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_srt(path: str | Path) -> list[SrtItem]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []

    items: list[SrtItem] = []
    blocks = re.split(r"\n\s*\n", raw)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0])
        except ValueError:
            continue

        range_parts = [part.strip() for part in lines[1].split("-->")]
        if len(range_parts) != 2:
            continue

        start = parse_timestamp(range_parts[0])
        end = parse_timestamp(range_parts[1])
        text = " ".join(lines[2:]).strip()
        items.append(SrtItem(index=index, start=start, end=end, text=text))

    return items


def write_srt(items: list[SrtItem], path: str | Path) -> None:
    out = []
    for i, item in enumerate(items, start=1):
        out.append(str(i))
        out.append(f"{to_timestamp(item.start)} --> {to_timestamp(item.end)}")
        out.append(item.text)
        out.append("")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def slice_srt(
    items: list[SrtItem],
    clip_start: float,
    clip_end: float,
) -> list[SrtItem]:
    sliced: list[SrtItem] = []
    for item in items:
        if item.end <= clip_start or item.start >= clip_end:
            continue
        new_start = max(item.start, clip_start) - clip_start
        new_end = min(item.end, clip_end) - clip_start
        if new_end - new_start < 0.1:
            continue
        sliced.append(
            SrtItem(index=len(sliced) + 1, start=new_start, end=new_end, text=item.text)
        )
    return sliced


def to_ass_timestamp(value: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.cc (centiseconds)."""
    value = max(0.0, value)
    total_cs = int(round(value * 100))
    hours, rem = divmod(total_cs, 360000)
    minutes, rem = divmod(rem, 6000)
    seconds, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


_ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def srt_to_ass(
    items: list[SrtItem],
    path: str | Path,
    font_name: str = "Arial",
    font_size: int = 76,
    outline: int = 4,
    shadow: int = 1,
    margin_v: int = 120,
) -> None:
    """Write ASS subtitle file with beautiful vertical-video styling.

    Items must already have clip-relative timestamps (start=0 at clip start).
    """
    header = _ASS_HEADER.format(
        font_name=font_name,
        font_size=font_size,
        outline=outline,
        shadow=shadow,
        margin_v=margin_v,
    )
    lines = [header]
    for item in items:
        start = to_ass_timestamp(item.start)
        end = to_ass_timestamp(item.end)
        text = item.text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
