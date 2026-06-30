from __future__ import annotations

from pathlib import Path

from content_distribution.models.contracts import TimecodeEntry


def _timecodes_block(timecodes: list[TimecodeEntry], limit: int = 8) -> str:
    lines = [f"{tc.timestamp} — {tc.title}" for tc in timecodes[:limit]]
    return "\n".join(lines) if lines else "Таймкоды будут добавлены позже."


def generate_local_smm_materials(
    work_dir: Path,
    video_filename: str,
    rating: int,
    assessment: str,
    timecodes: list[TimecodeEntry],
    titles: list[str] | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> list[str]:
    """Create local post drafts inside SMM/<PLATFORM>/ without external APIs."""
    smm_root = work_dir / "SMM"
    if not smm_root.exists():
        return []

    title = (titles or [Path(video_filename).stem])[0]
    desc = (description or assessment or "Новый материал готов.").strip()
    tags_line = ", ".join(tags or [])
    chapters = _timecodes_block(timecodes)

    outputs: list[tuple[Path, str]] = []

    outputs.append((smm_root / "YOUTUBE" / "post.md", f"""# YouTube Package

Title: {title}

Description:
{desc}

Chapters:
{chapters}

Tags:
{tags_line or 'будут добавлены'}
"""))

    outputs.append((smm_root / "X" / "thread.txt", f"""1) Вышел новый разбор: {title}
2) Главный вывод: {assessment}
3) Что внутри: рейтинг материала {rating}/10
4) Смотри полный выпуск и делись мнением.
"""))

    outputs.append((smm_root / "TELEGRAM" / "post.md", f"""Новый выпуск: {title}

{assessment}

Что внутри:
{chapters}

Если полезно — оставь реакцию и комментарий.
"""))

    outputs.append((smm_root / "INSTAGRAM" / "caption.txt", f"""{title}

{assessment}

Сохрани, чтобы пересмотреть ключевые моменты.
"""))

    outputs.append((smm_root / "LINKEDIN" / "post.md", f"""{title}

Контекст: {assessment}

Ключевые главы:
{chapters}

Готов обсудить выводы и практическое применение.
"""))

    outputs.append((smm_root / "TIKTOK" / "caption.txt", f"""{title}

Коротко: {assessment}
"""))

    outputs.append((smm_root / "FACEBOOK" / "post.txt", f"""{title}

{assessment}

Главы:
{chapters}
"""))

    outputs.append((smm_root / "DISCORD" / "announcement.txt", f"""Новый выпуск: {title}
Оценка: {rating}/10
{assessment}
"""))

    outputs.append((smm_root / "PINTEREST" / "pin.txt", f"""{title}

{assessment}
"""))

    outputs.append((smm_root / "MEDIUM" / "article_draft.md", f"""# {title}

{desc}

## Главы
{chapters}
"""))

    outputs.append((smm_root / "SUBSTACK" / "newsletter_draft.md", f"""# {title}

{desc}

## Ключевые блоки
{chapters}
"""))

    saved: list[str] = []
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip() + "\n", encoding="utf-8")
        saved.append(str(path))

    return saved
