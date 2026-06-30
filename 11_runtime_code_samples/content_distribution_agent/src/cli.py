from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from content_distribution.config import load_settings
from content_distribution.models.contracts import JobStatus
from content_distribution.services.orchestrator import run_pipeline
from content_distribution.services.stream_automation import create_stream_workspace, generate_marketing_materials

app = typer.Typer(help="Content distribution pipeline: stream automation and marketing materials")
console = Console()

SOURCE_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


@app.command()
def run(
    source: str = typer.Option(..., help="YouTube URL or local video path"),
    config: str = typer.Option("config/default.yaml", help="Path to YAML config"),
) -> None:
    settings = load_settings(config)
    job = run_pipeline(settings, source)

    if job.status != JobStatus.completed:
        console.print("[red]Job failed[/red]")
        for error in job.errors:
            console.print(f" - {error}")
        raise typer.Exit(code=1)

    table = Table(title=f"Shorts job: {job.id}")
    table.add_column("Clip")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Duration")
    table.add_column("Score")
    table.add_column("Path")

    for clip in job.result.clips:
        table.add_row(
            clip.id,
            f"{clip.start:.2f}",
            f"{clip.end:.2f}",
            f"{clip.duration:.2f}",
            f"{clip.score:.3f}",
            clip.output_path,
        )

    console.print(table)
    console.print(f"[green]Done[/green]. Metadata: {Path(settings.app.output_dir) / job.id / 'job.json'}")


@app.command("stream-bootstrap")
def stream_bootstrap(
    workspace_root: str = typer.Option(
        "~/Desktop/STREAMING interface",
        help="Root folder for stream automation workspaces",
    ),
    video: str | None = typer.Option(
        None,
        help="Optional path to OBS stream recording",
    ),
    stream_title: str = typer.Option(
        "my-stream",
        help="Stream title used in folder naming and instruction templates",
    ),
    niche: str = typer.Option(
        "content marketing",
        help="Content category for research and SEO materials",
    ),
    config: str = typer.Option(
        "config/default.yaml",
        help="Path to pipeline config used for transcription and shorts rendering",
    ),
    auto_transcribe: bool = typer.Option(
        True,
        "--auto-transcribe/--no-auto-transcribe",
        help="Generate TRANSCRIBATION.txt from source video",
    ),
    auto_shorts: bool = typer.Option(
        True,
        "--auto-shorts/--no-auto-shorts",
        help="Run existing shorts engine and write report into SHORTS CREATION",
    ),
    auto_marketing: bool = typer.Option(
        True,
        "--auto-marketing/--no-auto-marketing",
        help="Build marketing drafts (SMM, SEO, articles) from transcript",
    ),
    thumbnail_provider: str = typer.Option(
        "chatgpt",
        help="Thumbnail generation provider: chatgpt (default), pillow (auto), openai (GPT Image API), local, or both (openai+local)",
    ),
    youtube_channel: list[str] = typer.Option(
        None,
        "--youtube-channel",
        help="YouTube channel name (repeat 3 times for 3 channels)",
    ),
) -> None:
    try:
        result = create_stream_workspace(
            workspace_root=workspace_root,
            source_video=video,
            stream_title=stream_title,
            niche=niche,
            config_path=config,
            auto_transcribe=auto_transcribe,
            auto_shorts=auto_shorts,
            auto_marketing=auto_marketing,
            thumbnail_provider=thumbnail_provider,
            youtube_channels=youtube_channel,
        )
    except FileNotFoundError as error:
        console.print(f"[red]Source video missing:[/red] {error}")
        raise typer.Exit(code=1)

    payload = {
        "status": "completed",
        "workspace": str(result.root),
        "source_video": str(result.source_video_path) if result.source_video_path else None,
        "transcription": str(result.transcription_path) if result.transcription_path else None,
        "shorts_job_id": result.shorts_job_id,
        "manifest": str(result.manifest_path),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("stream-from-latest-obs")
def stream_from_latest_obs(
    workspace_root: str = typer.Option(
        "~/Desktop/STREAMING interface",
        help="Root folder for stream automation workspaces",
    ),
    obs_folder: str = typer.Option(
        "~/Desktop/STREAMING interface/OBS",
        help="Folder with OBS recordings",
    ),
    stream_title: str = typer.Option(
        "latest-obs-stream",
        help="Stream title used in folder naming and instruction templates",
    ),
    niche: str = typer.Option(
        "content marketing",
        help="Content category for research and SEO materials",
    ),
    config: str = typer.Option(
        "config/templates/streaming.yaml",
        help="Path to pipeline config used for transcription and shorts rendering",
    ),
    auto_transcribe: bool = typer.Option(
        True,
        "--auto-transcribe/--no-auto-transcribe",
        help="Generate TRANSCRIBATION.txt from source video",
    ),
    auto_shorts: bool = typer.Option(
        True,
        "--auto-shorts/--no-auto-shorts",
        help="Run existing shorts engine and write report into SHORTS CREATION",
    ),
    auto_marketing: bool = typer.Option(
        True,
        "--auto-marketing/--no-auto-marketing",
        help="Build marketing drafts (SMM, SEO, articles) from transcript",
    ),
    thumbnail_provider: str = typer.Option(
        "chatgpt",
        help="Thumbnail generation provider: chatgpt (default), pillow (auto), openai (GPT Image API), local, or both (openai+local)",
    ),
    youtube_channel: list[str] = typer.Option(
        None,
        "--youtube-channel",
        help="YouTube channel name (repeat 3 times for 3 channels)",
    ),
) -> None:
    obs_path = Path(obs_folder).expanduser().resolve()
    if not obs_path.exists() or not obs_path.is_dir():
        console.print(f"[red]OBS folder missing:[/red] {obs_path}")
        raise typer.Exit(code=1)

    candidates = [
        file
        for file in obs_path.iterdir()
        if file.is_file() and file.suffix.lower() in SOURCE_VIDEO_SUFFIXES
    ]
    if not candidates:
        console.print(f"[red]No video files found in OBS folder:[/red] {obs_path}")
        raise typer.Exit(code=1)

    latest_video = max(candidates, key=lambda file: file.stat().st_mtime)

    try:
        result = create_stream_workspace(
            workspace_root=workspace_root,
            source_video=str(latest_video),
            stream_title=stream_title,
            niche=niche,
            config_path=config,
            auto_transcribe=auto_transcribe,
            auto_shorts=auto_shorts,
            auto_marketing=auto_marketing,
            thumbnail_provider=thumbnail_provider,
            youtube_channels=youtube_channel,
        )
    except FileNotFoundError as error:
        console.print(f"[red]Source video missing:[/red] {error}")
        raise typer.Exit(code=1)

    payload = {
        "status": "completed",
        "latest_obs_video": str(latest_video),
        "workspace": str(result.root),
        "source_video": str(result.source_video_path) if result.source_video_path else None,
        "transcription": str(result.transcription_path) if result.transcription_path else None,
        "shorts_job_id": result.shorts_job_id,
        "manifest": str(result.manifest_path),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("stream-materials")
def stream_materials(
    workspace: str = typer.Option(..., help="Path to existing stream workspace folder"),
    transcript: str = typer.Option(..., help="Path to transcript file (.txt or .srt)"),
    stream_title: str = typer.Option("my-stream", help="Stream title for generated materials"),
    niche: str = typer.Option("content marketing", help="Content niche for SEO and positioning"),
    thumbnail_provider: str = typer.Option(
        "chatgpt",
        help="Thumbnail generation provider: chatgpt (default), pillow (auto), openai (GPT Image API), local, or both (openai+local)",
    ),
) -> None:
    try:
        result = generate_marketing_materials(
            workspace_dir=workspace,
            transcript_path=transcript,
            stream_title=stream_title,
            niche=niche,
            thumbnail_provider=thumbnail_provider,
        )
    except FileNotFoundError as error:
        console.print(f"[red]Input missing:[/red] {error}")
        raise typer.Exit(code=1)

    payload = {
        "status": "completed",
        **result,
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("watch")
def watch(
    config: str = typer.Option("config/default.yaml", help="Path to YAML config"),
) -> None:
    """Watch OBS/ folder and auto-process new videos (transcribe → timecodes → PDF → assess)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = load_settings(config)
    from content_distribution.services.watcher import OBSWatcher

    def _on_complete(result) -> None:
        status_colors = {
            "ГОТОВО_К_ПОСТИНГУ":  "green",
            "РЕЗАТЬ_НА_КЛИПЫ":    "yellow",
            "ГОТОВО_КАК_ВИДЕО":   "cyan",
            "СЛАБЫЙ_КОНТЕНТ":     "red",
        }
        color = status_colors.get(result.status.value, "white")
        console.print(
            f"\n[bold {color}]{result.status.value}[/bold {color}]  "
            f"[white]Оценка: {result.rating}/10[/white]\n"
            f"[dim]{result.assessment}[/dim]\n"
            f"📂 {result.work_dir}\n"
            f"📄 {result.timecodes_pdf_path}\n"
        )

    obs_path = settings.intake.obs_dir
    work_path = settings.intake.work_dir
    console.print(f"[bold green]OBS Watcher запущен[/bold green]")
    console.print(f"  Слежу за:  [cyan]{obs_path}[/cyan]")
    console.print(f"  Сессии в:  [cyan]{work_path}[/cyan]")
    console.print(f"  Модель:    [cyan]Whisper {settings.intake.whisper_model}[/cyan]")
    console.print("  [dim]Ctrl+C для остановки[/dim]\n")

    watcher = OBSWatcher(settings, on_complete=_on_complete)
    try:
        watcher.run()
    except KeyboardInterrupt:
        watcher.stop()
        console.print("\n[yellow]Watcher остановлен.[/yellow]")


if __name__ == "__main__":
    app()
