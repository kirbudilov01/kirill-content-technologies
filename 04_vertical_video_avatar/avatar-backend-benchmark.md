# Avatar backend benchmark

Date: 2026-06-27

Machine:
- MacBook Pro M4
- 16 GB RAM
- macOS 15.5
- No CUDA/NVIDIA

Goal:
- Find a usable backend for AtlasRepo talking-avatar Shorts.
- Local-first is preferred, but output quality matters more than ideology.

## Tested

### FasterLivePortrait-MLX + JoyVASA audio driving

Status: ran locally.

Output:
- `research/avatar-lab/output/liveportrait/kirill-front-liveportrait-audio-drive-8s.mp4`

Verdict: reject.

Reason:
- Audio-driven motion is too weak.
- Mouth only moves slightly.
- Face does not feel alive.

### FasterLivePortrait-MLX video driving + Easy-Wav2Lip

Status: ran locally.

Output:
- `research/avatar-lab/output/liveportrait/hybrid/liveportrait-driving-8s_postiz-voice-8s_hybrid720.mp4`

Verdict: reject for large/avatar-first shots.

Reason:
- Eyes drift and desync.
- Face shape swims between frames.
- Wav2Lip improves mouth sync but cannot fix the unstable base.

### MuseTalk 1.5

Status: ran locally with patches.

Local clone:
- `/Users/kirill/Documents/Projects/MuseTalk`

Patches:
- `musetalk/utils/preprocessing.py`: make DWPose/MMPose optional and fall back to face bbox.
- `musetalk/utils/face_parsing/resnet.py`: use `torch.load(..., weights_only=False)` for legacy trusted ResNet checkpoint.
- `scripts/inference.py`: add Apple MPS device selection and allow explicit `coord_path` in an inference config.

Output:
- `research/avatar-lab/output/avatar-benchmark/musetalk-results-1s/v15/kirill-musetalk-1s.mp4`
- `research/avatar-lab/output/avatar-benchmark/musetalk-results-10s/v15/kirill-musetalk-own-voice-10s.mp4`

Runtime:
- CPU inference about 4 seconds per video frame.
- 1 second at 25 fps took about 2 minutes for inference plus setup.
- MPS inference for 10 seconds / 250 frames ran at roughly 2 fps after setup.
- The 10-second MPS test used a saved manual bbox cache, so it skipped slow/unstable landmark extraction.

Verdict: best quality candidate so far for Mac-local testing, but still not enough for full production volume on this machine.

Reason:
- Much more stable than LivePortrait hybrid because it edits a real source video instead of generating the whole face.
- No obvious eye drift in the 1-second sample.
- CPU runtime is far too slow for a content factory; MPS is usable for short experiments.
- Need a clean source video without baked subtitles for a fair visual test.

## Feasibility checked

### Hallo2

Status: not run locally.

Reason:
- Official requirements target Ubuntu 20.04/22.04, CUDA 11.8, tested on A100.
- Requires CUDA-specific packages such as `onnxruntime-gpu`, `xformers`, `bitsandbytes`.

Verdict: CUDA/RunPod candidate, not Mac-local candidate.

### EchoMimic

Status: not run locally.

Reason:
- Official tested GPUs: A100 80GB, RTX 4090D 24GB, V100 16GB.
- Requires heavier diffusion/video stack.

Verdict: CUDA/RunPod candidate, not Mac-local candidate.

### SadTalker

Status: inspected, not run yet.

Reason:
- Current disk free space after MuseTalk install is about 1.8 GB.
- SadTalker checkpoints plus GFPGAN/enhancer weights exceed the safe remaining space.

Verdict:
- Can be tested after freeing disk space, but expected quality is likely below MuseTalk.

## Current recommendation

Use MuseTalk as the next serious backend, but do not run it as the production renderer on this Mac CPU.

Best practical architecture:
1. MacBook:
   - scripts
   - screen recordings
   - local subtitles
   - edit assembly
   - QC
2. CUDA backend:
   - MuseTalk first
   - then EchoMimic / Hallo2
3. Output style:
   - avoid large full-face avatar until backend is stable
   - use small talking-head window or presenter strip
   - make demo + subtitles carry retention

## Next test assets needed

Clean source-avatar video:
- 20-60 seconds
- front-facing
- no baked subtitles
- no hands over mouth
- steady light
- 1080p or 4K

Disk:
- free at least 20 GB before testing SadTalker/EchoMimic/Hallo2 locally.
- Hugging Face cache was removed after this run; current free space was about 7.3 GB.
