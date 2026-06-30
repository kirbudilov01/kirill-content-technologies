# Overnight Avatar Test Queue

Date: 2026-06-27

Goal: prepare and run as much avatar-system testing as possible before the RunPod GPU benchmark. The pass should identify which repositories are worth spending GPU money on and which ones are dead ends.

## Operating Rule

Do not treat a repo as useful because the README looks good. Every candidate must be scored on:

- install friction;
- GPU requirement;
- Mac-local feasibility;
- RunPod feasibility;
- batch/API/headless readiness;
- avatar quality potential;
- expected speed;
- fit for Shorts;
- fit for 10 minute long-form;
- whether it can become part of the AtlasRepo production pipeline.

## Assets Available

Avatar images:

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

Known comparison outputs:

- rejected LivePortrait/JoyVASA output;
- rejected LivePortrait + Wav2Lip hybrid;
- MuseTalk 10s Mac/MPS output.

## Test Priority

### Tier 0: Already Tested Locally

1. MuseTalk 1.5
   - Status: local Mac test passed technically.
   - Current verdict: best local candidate so far.
   - Next action: RunPod CUDA benchmark.

2. FasterLivePortrait / Wav2Lip hybrid
   - Status: tested and rejected for large avatar shots.
   - Current verdict: keep only as fallback / small insert.

### Tier 1: Complete or Semi-Complete Ready Systems

3. `PunithVT/ai-avatar-system`
   - Why: closest full pipeline: photo, voice clone, Whisper, LLM, Chatterbox, MuseTalk, FastAPI, Next.js.
   - Night task: clone, inspect Docker/README/API, determine batch-video path.

4. `duixcom/Duix-Avatar`
   - Why: open-source digital human toolkit, possible HeyGen-like self-hosted route.
   - Night task: clone, inspect setup and whether CLI/API generation exists.

5. `billwuhao/Comfyui_HeyGem`
   - Why: HeyGem-like digital human via ComfyUI, potentially stronger quality.
   - Night task: clone, inspect model requirements/workflow files, decide RunPod ComfyUI path.

6. `MeiGen-AI/InfiniteTalk`
   - Why: long-duration talking-video candidate; important for long-form.
   - Night task: clone, inspect dependencies, estimate GPU speed risk.

### Tier 2: Quality / Long-Form Candidates

7. `bytedance/LatentSync`
   - Why: quality lip-sync lane.
   - Night task: clone/inspect; likely slow, classify premium vs factory.

8. `fudan-generative-vision/hallo2`
   - Status: already cloned.
   - Why: long-duration high-resolution talking portrait.
   - Night task: inspect if install has Docker/RunPod path; summarize blockers.

9. `antgroup/echomimic`
   - Status: already cloned.
   - Why: expressive portrait animation.
   - Night task: inspect requirements and output path.

10. `jixiaozhong/Sonic`
    - Why: image+audio portrait animation; useful for satellite avatars.
    - Night task: clone/inspect.

### Tier 3: Architecture References

11. `HumanAIGC-Engineering/OpenAvatarChat`
    - Why: real-time digital avatar architecture.
    - Night task: clone/inspect; classify components reusable for our API.

12. `HumanAIGC/lite-avatar`
    - Why: realtime 2D avatar, possible cheap lane.
    - Night task: clone/inspect; check if output quality category is relevant.

13. `Open-LLM-VTuber/Open-LLM-VTuber`
    - Why: interactive avatar/agent architecture.
    - Night task: inspect only, probably not production-video backend.

14. `NVIDIA/Audio2Face-3D`
    - Why: future 3D-avatar lane.
    - Night task: inspect docs, model availability, and rendering requirements.

15. `Kedreamix/Linly-Talker`
    - Why: integrated digital-human conversation demo.
    - Night task: inspect only.

## Night Work Plan

1. Clone missing repositories under `/Users/kirill/Documents/Projects`.
2. For each repository, save a short inspection note:
   - README summary;
   - install commands;
   - Docker availability;
   - model weight size;
   - GPU requirement;
   - batch/API path;
   - expected test difficulty;
   - initial verdict.
3. Do not spend hours compiling impossible Mac-local stacks.
4. Prefer finding the fastest RunPod test path.
5. Produce a final matrix:
   - `test on RunPod first`;
   - `test later`;
   - `reference only`;
   - `reject`.

## Expected First RunPod Order

1. MuseTalk CUDA benchmark.
2. AvatarAI if batch path is clean.
3. ComfyUI HeyGem if workflow/model path is clear.
4. InfiniteTalk if setup looks practical.
5. LatentSync only if time/budget remains.

