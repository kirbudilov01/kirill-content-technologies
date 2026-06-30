from __future__ import annotations

from pathlib import Path

SMM_PLATFORMS = [
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


def ensure_local_workspace_folders(work_dir: Path) -> dict[str, str | list[str]]:
    """Create local content production folders for each work session."""
    screenshots_dir = work_dir / "SCREENSHOTS"
    smm_root = work_dir / "SMM"

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    smm_root.mkdir(parents=True, exist_ok=True)

    created_platforms: list[str] = []
    for platform in SMM_PLATFORMS:
        folder = smm_root / platform
        folder.mkdir(parents=True, exist_ok=True)
        created_platforms.append(str(folder))

    return {
        "screenshots_dir": str(screenshots_dir),
        "smm_root": str(smm_root),
        "smm_platforms": created_platforms,
    }
