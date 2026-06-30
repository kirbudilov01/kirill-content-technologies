# RunPod Test Recipe: MuseTalk CUDA

Date: 2026-06-27

Goal: benchmark MuseTalk on NVIDIA GPU as the first production-speed baseline.

## Why This Is Test #2

MuseTalk is already the best candidate tested locally:

- Mac CPU was too slow.
- Mac MPS worked and was visibly more stable than LivePortrait/Wav2Lip hybrid.
- Output quality was limited mainly by bad source footage, not only the engine.

Local repo:

- `/Users/kirill/Documents/Projects/MuseTalk`

Local outputs:

- `research/avatar-lab/output/avatar-benchmark/musetalk-results-10s/v15/kirill-musetalk-own-voice-10s.mp4`

## Input Assets

Initial technical test:

- video: `research/avatar-lab/output/avatar-benchmark/musetalk-input/kirill-source-10s.mp4`
- audio: `research/avatar-lab/output/avatar-benchmark/musetalk-input/kirill-own-voice-10s.wav`

Better final test:

- clean 20-60s Kirill source-avatar video;
- no baked subtitles;
- front-facing;
- steady light;
- no hands over mouth;
- 1080p or 4K.

## RunPod Setup Draft

Preferred GPU:

- RTX 5090
- fallback RTX 4090

Base image:

- RunPod PyTorch CUDA image or custom image.

Expected setup:

```bash
git clone https://github.com/TMElyralab/MuseTalk.git /workspace/MuseTalk
cd /workspace/MuseTalk
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Need download weights:

- MuseTalk V1.5 UNet
- SD VAE
- Whisper
- face-parse-bisent
- any mmpose/dwpose dependencies required by CUDA setup

We already have local knowledge from Mac patches, but CUDA should be closer to official path.

## Benchmark Commands

Use 25 fps and V1.5:

```bash
python -m scripts.inference \
  --inference_config /workspace/inputs/test-kirill-10s.yaml \
  --result_dir /workspace/outputs/musetalk-results-10s \
  --unet_model_path models/musetalkV15/unet.pth \
  --unet_config models/musetalkV15/musetalk.json \
  --vae_type sd-vae \
  --version v15 \
  --batch_size 8 \
  --fps 25 \
  --extra_margin 10 \
  --use_saved_coord \
  --saved_coord
```

Test durations:

1. 10 sec.
2. 40 sec.
3. 2-3 min if quality holds.
4. 10 min probe only after speed is understood.

## Metrics To Record

- cold setup time;
- model download size;
- model load time;
- landmark/bbox time;
- inference fps;
- full wall time;
- output quality;
- output size;
- GPU VRAM use;
- batch size tested;
- cost per finished minute.

## Pass / Fail

Pass:

- 40 sec output is publishable;
- 2-3 min output does not drift;
- speed is at least near realtime all-in;
- can use saved face coordinates / cache per avatar;
- output can be composed into Shorts and long-form.

Fail:

- mouth sync still weak;
- face/eyes drift;
- speed is far below realtime on 5090;
- setup too fragile.

## Production Notes If Passes

Build a persistent worker:

- load models once;
- cache avatar face coordinates;
- accept JSON jobs;
- write mp4 outputs;
- expose simple HTTP or queue endpoint;
- run inside RunPod pod/serverless.

Job shape:

```json
{
  "job_id": "kirill-postiz-short-001",
  "avatar_video": "/workspace/inputs/kirill-clean-source.mp4",
  "audio": "/workspace/inputs/postiz-short.wav",
  "output": "/workspace/outputs/kirill-postiz-short-001.mp4",
  "fps": 25,
  "version": "v15"
}
```

