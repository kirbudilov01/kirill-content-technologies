from __future__ import annotations

from pathlib import Path


def extract_video_screenshots(video_path: Path, output_dir: Path, count: int = 4) -> list[str]:
    """Extract evenly spaced JPEG screenshots from a video into output_dir."""
    try:
        import cv2
    except Exception:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return []

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0

    if duration <= 1.0:
        timestamps = [0.0] * count
    else:
        start = duration * 0.10
        end = duration * 0.90
        if count == 1:
            timestamps = [(start + end) / 2]
        else:
            step = (end - start) / max(1, count - 1)
            timestamps = [start + i * step for i in range(count)]

    saved: list[str] = []
    for idx, ts in enumerate(timestamps, start=1):
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts) * 1000.0)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        out = output_dir / f"shot_{idx:02d}.jpg"
        if cv2.imwrite(str(out), frame):
            saved.append(str(out))

    capture.release()
    return saved
