from __future__ import annotations

from statistics import median


def estimate_focus_x_ratio(
    video_path: str,
    start: float,
    end: float,
    sample_seconds: float,
    max_samples: int,
) -> float | None:
    try:
        import cv2  # type: ignore
    except Exception:
        return None

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        return None

    try:
        width = float(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if width <= 0.0 or fps <= 0.0:
            return None

        if end <= start:
            return None

        detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if detector.empty():
            return None

        span = end - start
        raw_step = max(0.6, sample_seconds)
        target_samples = min(max_samples, max(1, int(span / raw_step) + 1))
        step = span / max(1, target_samples)

        centers: list[float] = []
        t = start
        while t < end and len(centers) < max_samples:
            frame_idx = int(t * fps)
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = capture.read()
            if not ok or frame is None:
                t += step
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(40, 40),
            )
            if len(faces) > 0:
                x, _y, w, _h = max(faces, key=lambda box: box[2] * box[3])
                cx = x + w / 2
                centers.append(float(cx) / width)

            t += step

        if not centers:
            return None
        value = float(median(centers))
        return min(0.9, max(0.1, value))
    finally:
        capture.release()
