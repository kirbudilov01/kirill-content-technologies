#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a FasterLivePortrait-MLX audio-driven avatar.")
    parser.add_argument("--repo", required=True, help="Path to fasterliveportrait-mlx checkout")
    parser.add_argument("--source", required=True, help="Source portrait image")
    parser.add_argument("--audio", required=True, help="Driving audio wav/mp3")
    parser.add_argument("--out", required=True, help="Output mp4 path")
    parser.add_argument("--profile", default="turbo", help="MLX profile: turbo, balanced, quality")
    parser.add_argument("--src-scale", type=float, default=2.25)
    parser.add_argument("--src-vy-ratio", type=float, default=-0.08)
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    audio = Path(args.audio).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    if not repo.exists():
        raise SystemExit(f"LivePortrait repo not found: {repo}")
    if not source.exists():
        raise SystemExit(f"Source image not found: {source}")
    if not audio.exists():
        raise SystemExit(f"Audio file not found: {audio}")

    os.chdir(repo)
    checkpoints = repo / "checkpoints"
    if checkpoints.exists():
        os.environ.setdefault("FLIP_CHECKPOINT_DIR", str(checkpoints))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    sys.path.insert(0, str(repo))

    from omegaconf import OmegaConf
    from src.runtime_assets import ensure_runtime_assets
    from src.pipelines.gradio_live_portrait_pipeline import GradioLivePortraitPipeline

    cfg = OmegaConf.load("configs/mlx_infer.yaml")
    ensure_runtime_assets(cfg)
    pipe = GradioLivePortraitPipeline(cfg)
    pipe.set_mlx_profile(args.profile)

    video_update, _concat_update, *_ = pipe.execute_video(
        input_source_image_path=str(source),
        input_driving_audio_path=str(audio),
        source_mode="Image",
        driving_mode="Audio",
        flag_relative_input=True,
        flag_do_crop_input=True,
        flag_remap_input=True,
        driving_multiplier=1.0,
        flag_stitching=True,
        flag_crop_driving_video_input=True,
        flag_video_editing_head_rotation=False,
        flag_is_animal=False,
        animation_region="all",
        scale=args.src_scale,
        vx_ratio=0.0,
        vy_ratio=args.src_vy_ratio,
        scale_crop_driving_video=2.2,
        vx_ratio_crop_driving_video=0.0,
        vy_ratio_crop_driving_video=-0.1,
        driving_smooth_observation_variance=1e-7,
        cfg_scale=1.2,
        mlx_profile=args.profile,
        progress=None,
    )

    rendered = video_update.get("value") if isinstance(video_update, dict) else getattr(video_update, "value", None)
    if not rendered:
        raise SystemExit(f"Pipeline did not return a rendered video: {video_update!r}")

    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rendered, out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
