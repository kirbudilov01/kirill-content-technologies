"""Watch OBS/ folder for new video files and trigger the intake agent."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from content_distribution.config import Settings
from content_distribution.services.intake_agent import VIDEO_SUFFIXES, run_intake

logger = logging.getLogger(__name__)

# How long to wait after the last write event before considering a file "stable"
_STABILITY_WAIT_SECONDS = 5.0
# Poll interval for checking file size stability
_POLL_INTERVAL_SECONDS = 2.0


def _is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES


def _wait_until_stable(path: Path, timeout: float = 300.0) -> bool:
    """Wait until file size stops changing (copy/write finished). Returns True if stable."""
    deadline = time.monotonic() + timeout
    prev_size = -1
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            time.sleep(_POLL_INTERVAL_SECONDS)
            continue
        if size == prev_size and size > 0:
            stable_count += 1
            if stable_count >= 3:
                return True
        else:
            stable_count = 0
        prev_size = size
        time.sleep(_POLL_INTERVAL_SECONDS)
    return False


def _already_processed(video_path: Path, work_root: Path) -> bool:
    """Check if any work session already references this video filename."""
    if not work_root.exists():
        return False
    for session_dir in work_root.iterdir():
        if not session_dir.is_dir():
            continue
        intake_json = session_dir / "intake.json"
        if intake_json.exists():
            try:
                import json
                data = json.loads(intake_json.read_text(encoding="utf-8"))
                if data.get("video") == video_path.name:
                    return True
            except Exception:
                continue
    return False


class OBSWatcher:
    """Watches OBS/ directory and runs intake_agent for each new video."""

    def __init__(self, settings: Settings, on_complete=None) -> None:
        self._settings = settings
        self._cfg = settings.intake
        self._obs_dir = Path(self._cfg.obs_dir)
        self._work_root = Path(self._cfg.work_dir)
        self._on_complete = on_complete  # optional callback(IntakeResult)
        self._stop_event = threading.Event()
        self._processing: set[str] = set()

    def _process(self, video_path: Path) -> None:
        key = str(video_path)
        if key in self._processing:
            return
        self._processing.add(key)
        try:
            logger.info("📥 Новый файл: %s — ожидаю завершения записи…", video_path.name)
            if not _wait_until_stable(video_path):
                logger.warning("⚠️  Файл нестабилен, пропускаю: %s", video_path.name)
                return
            logger.info("🚀 Запускаю intake для: %s", video_path.name)
            result = run_intake(video_path, self._settings)
            status_label = result.status.value
            logger.info(
                "✅ Готово: %s | Статус: %s | Оценка: %d/10 | Папка: %s",
                video_path.name, status_label, result.rating, result.work_dir,
            )
            if self._on_complete:
                try:
                    self._on_complete(result)
                except Exception:
                    pass
        except Exception as exc:
            logger.error("❌ Ошибка при обработке %s: %s", video_path.name, exc, exc_info=True)
        finally:
            self._processing.discard(key)

    def _scan_existing(self) -> None:
        """On startup, process any videos already in OBS/ that haven't been handled."""
        if not self._obs_dir.exists():
            return
        for f in sorted(self._obs_dir.iterdir()):
            if _is_video_file(f) and not _already_processed(f, self._work_root):
                t = threading.Thread(target=self._process, args=(f,), daemon=True)
                t.start()

    def run(self) -> None:
        """Start watching. Blocks until stop() is called."""
        try:
            from watchdog.observers import Observer  # type: ignore
            from watchdog.events import FileSystemEventHandler  # type: ignore
            self._run_watchdog()
        except ImportError:
            logger.warning("watchdog не установлен — использую polling-режим")
            self._run_polling()

    def _run_watchdog(self) -> None:
        from watchdog.observers import Observer  # type: ignore
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent  # type: ignore

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event: FileCreatedEvent) -> None:
                path = Path(event.src_path)
                if _is_video_file(path):
                    t = threading.Thread(target=watcher._process, args=(path,), daemon=True)
                    t.start()

            def on_moved(self, event: FileMovedEvent) -> None:
                path = Path(event.dest_path)
                if _is_video_file(path):
                    t = threading.Thread(target=watcher._process, args=(path,), daemon=True)
                    t.start()

        self._obs_dir.mkdir(parents=True, exist_ok=True)
        observer = Observer()
        observer.schedule(_Handler(), str(self._obs_dir), recursive=False)
        observer.start()
        logger.info("👀 Слежу за папкой: %s", self._obs_dir)
        self._scan_existing()
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        finally:
            observer.stop()
            observer.join()

    def _run_polling(self) -> None:
        """Fallback: poll directory every 10 seconds."""
        self._obs_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        logger.info("👀 Polling папки: %s (каждые 10 сек)", self._obs_dir)
        self._scan_existing()
        # seed seen with already-processed
        for f in self._obs_dir.iterdir():
            if _is_video_file(f) and _already_processed(f, self._work_root):
                seen.add(str(f))

        while not self._stop_event.is_set():
            time.sleep(10)
            if not self._obs_dir.exists():
                continue
            for f in sorted(self._obs_dir.iterdir()):
                key = str(f)
                if _is_video_file(f) and key not in seen:
                    seen.add(key)
                    t = threading.Thread(target=self._process, args=(f,), daemon=True)
                    t.start()

    def stop(self) -> None:
        self._stop_event.set()
