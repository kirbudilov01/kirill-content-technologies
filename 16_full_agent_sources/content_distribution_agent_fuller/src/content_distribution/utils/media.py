from __future__ import annotations

import json
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode != 0:
        raise MediaError(
            f"Command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}"
        )
    return proc


def get_duration_seconds(video_path: str | Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    proc = run_checked(command)
    payload = json.loads(proc.stdout)
    duration = float(payload["format"]["duration"])
    return max(0.0, duration)


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def get_video_dimensions(video_path: str | Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(video_path),
    ]
    proc = run_checked(command)
    payload = json.loads(proc.stdout)
    stream = payload["streams"][0]
    return int(stream["width"]), int(stream["height"])
