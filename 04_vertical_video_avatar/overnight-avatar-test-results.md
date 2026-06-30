# Overnight Avatar Test Results

Date: 2026-06-27

Status: v0.1 initial inspection pass. No paid GPU tests yet.

## Short Answer

Start with **Duix/HeyGem** and **MuseTalk CUDA**.

Reason:

- Duix/HeyGem already has Docker images and a specific `docker-compose-5090.yml`.
- Duix exposes a headless-ish local API: `/easy/submit` and `/easy/query` on port `8383`.
- MuseTalk is already locally proven as the best baseline, and should be much faster on RunPod.
- AvatarAI is promising but is more of a full product platform around MuseTalk; it is useful, but may be slower to validate for pure batch output.
- InfiniteTalk is highly relevant for long-form but too heavy for the first cheap benchmark.

## Current Assets

Avatar/source images:

- `research/avatar-lab/identity/avatar/source/kirill-front.png`
- `research/avatar-lab/identity/avatar/source/kirill-purple-front-crop.png`
- `research/avatar-lab/identity/avatar/source/kirill-purple-front-full.png`
- `research/avatar-lab/identity/avatar/source/kirill-window-crop.png`
- `research/avatar-lab/identity/avatar/source/kirill-window-full.png`

Voice/audio:

- `research/avatar-lab/identity/voice/processed/kirill_001.wav`
- `research/avatar-lab/identity/voice/processed/kirill_002.wav`
- `research/avatar-lab/identity/voice/raw/about-telegram-mini-apps.wav`
- `research/avatar-lab/identity/voice/raw/web3-truth.wav`
- `research/avatar-lab/output/avatar-benchmark/musetalk-input/kirill-own-voice-10s.wav`

Known outputs:

- LivePortrait/JoyVASA: rejected.
- LivePortrait + Wav2Lip: rejected for large avatar shots.
- MuseTalk 10s Mac/MPS: best local baseline, but not final quality due bad source video.

## Repositories Cloned

Root: `/Users/kirill/Documents/Projects`

| Repo | Size | Status |
|---|---:|---|
| `Comfyui_HeyGem` | 904K | cloned |
| `ai-avatar-system` | 1.1M | cloned |
| `Audio2Face-3D` | 1.4M | cloned |
| `Sonic` | 9.0M | cloned |
| `LatentSync` | 19M | cloned |
| `hallo2` | 25M | already cloned |
| `lite-avatar` | 29M | cloned |
| `OpenAvatarChat` | 31M | cloned |
| `InfiniteTalk` | 44M | cloned |
| `Open-LLM-VTuber` | 44M | cloned |
| `echomimic` | 47M | already cloned |
| `SadTalker` | 139M | already cloned |
| `Linly-Talker` | 160M | cloned |
| `Duix-Avatar` | 392M | cloned |
| `Easy-Wav2Lip` | 2.9G | already cloned |
| `MuseTalk` | 5.0G | already cloned with local weights |

Disk after clone pass: about 8 GB free.

## Candidate Matrix

| Candidate | What It Is | Batch/API Readiness | GPU Fit | Current Verdict |
|---|---|---|---|---|
| Duix Avatar | Digital human toolkit with Docker services | Strong: API via `/easy/submit`, `/easy/query`; Electron client can be bypassed | Very strong: has `docker-compose-5090.yml` | **Test first on RunPod** |
| ComfyUI HeyGem | HeyGem-like digital human ComfyUI node | Medium: ComfyUI workflow/headless wrapper needed | Strong: Docker image `guiji2025/heygem.ai` | **Test first/second** |
| MuseTalk 1.5 | Fast lip-sync baseline | Strong: CLI/inference scripts already known | Strong: official real-time claims; already locally tested | **Test first on RunPod** |
| AvatarAI | Complete FastAPI/Next.js/MuseTalk/voice platform | Medium/strong: has Docker, API, Celery task, WebSocket chunks | Strong, but product-shaped | **Inspect deeper; likely useful worker skeleton** |
| LatentSync 1.6 | Quality diffusion lip-sync | Strong CLI, but slower | 18GB VRAM for v1.6 | **Quality lane, not first factory** |
| InfiniteTalk | Unlimited/long talking video | CLI exists, ComfyUI branch exists | Heavy: Wan2.1 14B, flash-attn, xformers | **Long-form lane, not first cheap test** |
| Hallo2 | Long-duration high-res portrait | CLI inference_long.py | Heavy CUDA | **RunPod-only, later** |
| EchoMimic | Expressive portrait animation | CLI scripts | Heavy CUDA | **Quality lane, later** |
| Sonic | Image+audio portrait animation | CLI likely, needs inspect | CUDA | **Satellite-avatar lane, later** |
| OpenAvatarChat | Modular interactive digital human chat | Docker, config-driven | GPU possible | **Architecture reference, not batch-first** |
| LiteAvatar | Realtime 2D audio2face | CLI, lightweight | Can run CPU/GPU | **Cheap fallback, likely not YouTube-quality** |
| Audio2Face-3D | NVIDIA 3D facial animation SDK/NIM | Strong SDK/NIM path | NVIDIA-native | **Strategic 3D lane, not first 2D video** |
| Open-LLM-VTuber | Live2D interactive avatar agent | App platform, Docker | Mixed | **Interactive/persona reference** |
| Linly-Talker | Gradio digital human conversation system | Demo/API dirs | mixed | **Reference/demo only for now** |

## Key Findings

### 1. Duix/HeyGem is the strongest "ready system" lead

Duix has Docker deployment and even a dedicated 5090 compose file:

- `deploy/docker-compose-5090.yml`
- `guiji2025/fish-speech-5090`
- `guiji2025/duix.avatar-5090`
- port `8383`

The Electron app calls:

- `POST http://127.0.0.1:8383/easy/submit`
- `GET http://127.0.0.1:8383/easy/query?code=...`

This means we should be able to bypass the desktop UI and build a batch worker.

Important source files:

- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/api/f2f.js`
- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/service/video.js`
- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/config/config.js`

### 2. ComfyUI HeyGem is probably the same engine in workflow form

`Comfyui_HeyGem` uses Docker image:

```yaml
image: guiji2025/heygem.ai
ports:
  - '8383:8383'
command: python /code/app_local.py
```

It claims:

- full-body;
- dynamic;
- arbitrary resolution;
- long videos can repeat/ping-pong to match audio duration.

This is worth testing before heavier research models.

### 3. AvatarAI is a real system, but more app than batch renderer

AvatarAI has:

- FastAPI backend;
- Next.js frontend;
- Docker Compose;
- MuseTalk worker;
- voice cloning;
- WebSocket video chunks;
- Celery task `generate_video_task`.

Useful source:

- `/Users/kirill/Documents/Projects/ai-avatar-system/backend/app/services/animator.py`
- `/Users/kirill/Documents/Projects/ai-avatar-system/backend/app/celery_app.py`
- `/Users/kirill/Documents/Projects/ai-avatar-system/backend/app/websocket.py`

Verdict:

- Excellent architecture reference.
- Could become our backend skeleton.
- Not the shortest path to "is avatar quality good?" because it adds product/platform layers.

### 4. InfiniteTalk is important but heavy

InfiniteTalk supports:

- video-to-video;
- image-to-video;
- streaming/long generation;
- 480p/720p;
- low VRAM mode;
- ComfyUI support.

But it uses:

- Wan2.1-I2V-14B-480P;
- flash-attn;
- xformers;
- large Hugging Face weights.

Verdict:

- Very relevant for long-form future.
- Not first $10 smoke test unless Duix/MuseTalk fail.

### 5. LatentSync is a quality lane

LatentSync gives CLI inference and clear setup. VRAM:

- 8GB for v1.5;
- 18GB for v1.6.

Verdict:

- Good quality test on 5090.
- Likely slower than MuseTalk.
- Use for flagship/premium output if quality is visibly better.

### 6. OpenAvatarChat confirms modular digital-human direction

OpenAvatarChat supports:

- LiteAvatar;
- LAM;
- MuseTalk;
- FlashHead;
- ASR/LLM/TTS/avatar modularity;
- Docker Compose.

Verdict:

- Great architecture reference for future interactive AtlasRepo agent.
- Not first batch renderer.

### 7. Audio2Face-3D is a future strategic lane

NVIDIA Audio2Face-3D is serious:

- SDK;
- training framework;
- Unreal/Maya plugins;
- NIM microservice;
- pretrained models on Hugging Face.

Verdict:

- Future 3D branded-avatar route.
- Not first YouTube Shorts/long-form 2D avatar route.

## Recommended First RunPod Benchmark

Budget: $10.

GPU: RTX 5090 if available.

### Test A: Duix/HeyGem

Goal: fastest route to "digital human quality".

Steps:

1. Start RunPod 5090.
2. Run Duix/HeyGem Docker service.
3. Mount input/output volume.
4. Use a clean Kirill video source + audio.
5. Call `/easy/submit`.
6. Poll `/easy/query`.
7. Download output.
8. Measure speed and quality.

Output targets:

- 20-40 sec short.
- 2-3 min if first output is good.

### Test B: MuseTalk CUDA

Goal: production baseline speed.

Steps:

1. Use current MuseTalk setup knowledge.
2. Run 40 sec.
3. Run 2-3 min.
4. Optional 10 min probe if quality holds.

Output targets:

- speed in video-minutes per GPU-hour;
- compare quality against Mac/MPS output.

### Test C: LatentSync 1.6

Goal: premium mouth quality comparison.

Only run if A/B leave budget.

### Test D: InfiniteTalk

Goal: long-form possibility check.

Only run if setup is not slow. Otherwise defer.

## Answer To "Can Codex Test Overnight?"

Yes, with boundaries:

- I can clone, inspect, classify, prepare recipes, run lightweight local checks, and build test scripts.
- I can run long jobs while this Codex session stays alive and the machine does not sleep.
- I cannot honestly validate heavy avatar quality locally without NVIDIA GPU.
- For final quality/speed, RunPod is required.

Best overnight work:

1. Finish repository inspections.
2. Write RunPod launch recipes.
3. Build Duix/HeyGem batch client draft.
4. Build MuseTalk RunPod command recipe.
5. Prepare a scoring sheet.

## Next Actions

1. Create `runpod-duix-heygem-test.md`.
2. Create `runpod-musetalk-test.md`.
3. Extract a clean source-avatar candidate or list exact requirements if no clean source exists.
4. Build a small `curl`/Python client for Duix `/easy/submit` and `/easy/query`.
5. Wait for RunPod API key / $10 budget / "go".

