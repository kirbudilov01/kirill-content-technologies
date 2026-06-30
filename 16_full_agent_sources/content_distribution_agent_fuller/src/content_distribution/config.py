from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    project_name: str = "shorts-mvp"
    output_dir: str = "./output"
    temp_dir: str = "./tmp"
    max_clips: int = 18
    min_clip_seconds: int = 20
    max_clip_seconds: int = 50
    max_candidates: int = 120
    telegram_bot_token: Optional[str] = None


class TranscriptionConfig(BaseModel):
    mode: str = "faster_whisper_with_fallback"
    cache_enabled: bool = True
    language: Optional[str] = "ru"
    model_size: str = "small"
    device: str = "auto"
    compute_type: str = "int8"
    beam_size: int = 3
    vad_filter: bool = True
    fallback_srt_path: Optional[str] = None


class HighlightConfig(BaseModel):
    use_llm_rerank: bool = False
    keyword_boost: list[str] = Field(default_factory=list)
    intro_penalty_phrases: list[str] = Field(default_factory=list)


class RenderConfig(BaseModel):
    target_width: int = 1080
    target_height: int = 1920
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 20
    preset: str = "medium"
    blur_sigma: int = 25
    subtitle_font_name: str = "Arial"
    subtitle_font_size: int = 82
    subtitle_outline: int = 4
    subtitle_shadow: int = 1
    subtitle_margin_v: int = 360
    subtitle_max_lines: int = 1
    subtitle_max_chars_per_line: int = 28
    subtitle_max_words_per_line: int = 2
    subtitle_footer_enabled: bool = True
    subtitle_footer_text: str = "Название фильма в описании"
    subtitle_footer_font_scale: float = 0.9
    subtitle_footer_bottom_margin: int = 92
    # Subtitle visual style (BGR values for OpenCV)
    subtitle_font_style: str = "complex"  # complex | duplex | simplex | triplex
    subtitle_color_bgr: list[int] = Field(default_factory=lambda: [245, 236, 255])
    subtitle_outline_color_bgr: list[int] = Field(default_factory=lambda: [84, 36, 132])
    subtitle_shadow_color_bgr: list[int] = Field(default_factory=lambda: [58, 26, 92])
    loudnorm: bool = True
    loudnorm_target_lufs: int = -13
    smart_crop_enabled: bool = True
    smart_crop_sample_seconds: float = 1.8
    smart_crop_max_samples: int = 20
    reframe_mode: str = "auto"
    auto_crop_min_keep_ratio: float = 0.42
    background_music_path: Optional[str] = None
    background_music_volume: float = 0.12
    promo_overlay_image_path: Optional[str] = None
    promo_enabled: bool = True
    promo_text: str = "Лучший VPN"
    promo_title_line2: str = "для ТВОЕГО устройства"
    promo_title_highlight_word: str = "ТВОЕГО"
    promo_subtext: str = ""
    promo_cta_enabled: bool = True
    promo_cta_primary: str = "Использовать"
    promo_cta_secondary: str = "@lids_up_bot"
    promo_start_seconds: float = 3.0
    promo_anim_seconds: float = 0.6
    promo_duration_seconds: float = 0.0
    promo_top_margin: int = 220
    promo_height: int = 128
    promo_icon_path: Optional[str] = None
    promo_icon_size: int = 72


class PostizConfig(BaseModel):
    """Configuration for Postiz publishing service."""
    enabled: bool = False
    api_key: Optional[str] = None
    api_base_url: str = "https://api.postiz.com"
    default_platform: str = "twitter"  # twitter | threads | linkedin | instagram | tiktok
    auto_publish: bool = False
    publish_delay_minutes: int = 0


class AutomationConfig(BaseModel):
    queue_root: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    autopilot_interval_seconds: int = 300


class IntakeConfig(BaseModel):
    obs_dir: str = "../OBS"                  # папка с исходными видео
    work_dir: str = "../WORK"                # папка для сессий обработки
    whisper_model: str = "medium"            # whisper medium для таймкодов
    device: str = "auto"
    compute_type: str = "int8"
    language: str = "ru"
    timecode_interval_seconds: int = 300     # таймкод каждые N секунд
    stream_threshold_seconds: int = 1800     # > 30 мин → стрим
    short_video_threshold_seconds: int = 300 # < 5 мин → короткое видео
    about_me_dir: str = "../ABOUT ME "       # папка с данными об авторе
    research_dir: str = "../RESEARCH"        # папка с аналитикой конкурентов
    smart_moments_enabled: bool = True
    smart_moments_model: str = "gpt-5"
    smart_moments_local_only: bool = True
    smart_shorts_count: int = 3
    smart_short_target_seconds: int = 55
    smart_fragment_min_seconds: int = 6
    smart_fragment_max_seconds: int = 22


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    highlight: HighlightConfig = Field(default_factory=HighlightConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    intake: IntakeConfig = Field(default_factory=IntakeConfig)
    postiz: PostizConfig = Field(default_factory=PostizConfig)


def _resolve_optional_path(base_dir: Path, value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    base_dir = config_path.resolve().parent
    app = raw.setdefault("app", {})
    transcription = raw.setdefault("transcription", {})
    render = raw.setdefault("render", {})
    automation = raw.setdefault("automation", {})

    app["output_dir"] = _resolve_optional_path(base_dir, app.get("output_dir"))
    app["temp_dir"] = _resolve_optional_path(base_dir, app.get("temp_dir"))
    transcription["fallback_srt_path"] = _resolve_optional_path(
        base_dir, transcription.get("fallback_srt_path")
    )
    render["background_music_path"] = _resolve_optional_path(
        base_dir, render.get("background_music_path")
    )
    render["promo_overlay_image_path"] = _resolve_optional_path(
        base_dir, render.get("promo_overlay_image_path")
    )
    render["promo_icon_path"] = _resolve_optional_path(
        base_dir, render.get("promo_icon_path")
    )
    automation["queue_root"] = _resolve_optional_path(base_dir, automation.get("queue_root"))
    intake = raw.setdefault("intake", {})
    intake["obs_dir"] = _resolve_optional_path(base_dir, intake.get("obs_dir", "../OBS"))
    intake["work_dir"] = _resolve_optional_path(base_dir, intake.get("work_dir", "../WORK"))
    intake["about_me_dir"] = _resolve_optional_path(base_dir, intake.get("about_me_dir", "../ABOUT ME "))
    intake["research_dir"] = _resolve_optional_path(base_dir, intake.get("research_dir", "../RESEARCH"))
    return Settings.model_validate(raw)
