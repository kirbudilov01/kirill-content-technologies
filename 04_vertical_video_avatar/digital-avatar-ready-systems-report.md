# Digital Avatar Systems For AtlasRepo Content Factory

Date: 2026-06-27

Purpose: collect ready-to-test open-source digital avatar systems for the AtlasRepo video factory. The focus is not only lip-sync models, but complete or semi-complete systems that can help us produce avatar-led Shorts, long-form videos, repo demos, and eventually batch content through RunPod.

## Executive Summary

We should not build a digital-avatar engine from scratch. There are enough ready repositories to test a practical stack:

1. **AvatarAI / ai-avatar-system** as the closest complete self-hosted pipeline.
2. **Duix Avatar** and **HeyGem / ComfyUI HeyGem** as the most promising "digital human" quality candidates.
3. **MuseTalk 1.5** as the first production baseline for fast GPU lip-sync.
4. **InfiniteTalk / LongCat-Video-Avatar** as an important new long-duration talking-video candidate.
5. **LatentSync, Hallo2, EchoMimic, Sonic** as quality lanes for better avatar output once the RunPod GPU benchmark starts.
6. **NVIDIA Audio2Face-3D** as a serious 3D-avatar/facial-animation lane if we later move beyond 2D presenter clips.
7. **OpenAvatarChat, Open-LLM-VTuber, LiteAvatar, Linly-Talker** as useful references for real-time/conversational avatar architecture, but not necessarily the first batch-video factory backend.

The immediate goal is to find one avatar backend that passes the user's quality bar: **"Avatar good"**. After that, we can build the wider batch pipeline around it: long-form rendering, Shorts rendering, clipping, captions, SEO, and Postiz publishing.

## Current Production Target

Near-term test target:

- 1 long-form video.
- 5-10 Shorts.
- Benchmark speed, cost, and quality on RunPod.

Future daily target:

- 12 horizontal long-form videos per day.
- 30 Shorts per day.
- Shorts cutdowns from long-form without re-rendering avatar where possible.

Daily video volume estimate:

| Component | Count | Duration | Total |
|---|---:|---:|---:|
| Long-form | 12 | 10 min | 120 min |
| Standalone Shorts | 30 | 40-60 sec | 20-30 min |
| Total avatar/video workload | - | - | 140-150 min/day |
| Operational buffer | - | ffmpeg, subtitles, retries, export | 180-220 min/day equivalent |

Budget thinking:

- RTX 5090 at about $0.99/hr means $3/day buys around 3 GPU hours.
- $10/day buys around 10 GPU hours.
- $300-500/month is a realistic serious-content budget if the avatar backend and content format work.

The key benchmark is not raw model beauty. The key benchmark is:

```text
minutes of acceptable finished avatar video per GPU hour
```

## Priority Repositories

### 1. AvatarAI / ai-avatar-system

Repository: https://github.com/PunithVT/ai-avatar-system

What it is:

- Self-hosted AI avatar / digital human platform.
- Upload a photo, clone a voice, talk to a face in real time.
- Uses a complete pipeline: Whisper STT, Claude/GPT/Ollama, Chatterbox TTS, MuseTalk lip-sync, FastAPI, Next.js.

Why it matters:

- It is not just a lip-sync repo. It is close to the full system shape we need.
- It already combines voice, LLM, avatar generation, API/backend, and frontend.
- It can become a reference architecture for a RunPod worker even if we do not adopt it directly.

Risks:

- It may be optimized for interactive response rather than batch video production.
- Need to verify whether it has clean CLI/API batch mode.
- Need to inspect Docker/requirements and GPU assumptions.

Test plan:

1. Clone and inspect.
2. Run the demo on RunPod.
3. Check whether we can send a script/audio/avatar and receive mp4 without UI.
4. Measure 40 sec, 2 min, and 10 min generation.

Priority: **highest complete-system candidate**.

### 2. Duix Avatar

Repository: https://github.com/duixcom/Duix-Avatar

What it is:

- Open-source AI avatar / digital human toolkit.
- Focused on offline video generation and digital human cloning.
- The project positions itself as a way to create AI avatars and produce videos without commercial SaaS costs.

Why it matters:

- Potentially closer to a HeyGen-style self-hosted digital human than simple lip-sync.
- Could be better for production-style avatar output.
- Might support "digital human cloning" workflows that fit our use case.

Risks:

- Need to verify language/docs friction.
- Need to verify exact GPU requirements and batch support.
- Some digital-human stacks are large and opinionated.

Test plan:

1. Inspect installation path and model downloads.
2. Confirm whether it supports command-line generation from video/image + audio.
3. Run a short avatar generation benchmark on RTX 5090/4090.
4. Compare quality against MuseTalk.

Priority: **top quality-system candidate**.

### 3. ComfyUI HeyGem

Repository: https://github.com/billwuhao/Comfyui_HeyGem

What it is:

- ComfyUI node for HeyGem-like digital human generation.
- Project claims full-body, dynamic, arbitrary-resolution digital human generation.

Why it matters:

- Could be a shortcut to better visual quality than raw MuseTalk.
- ComfyUI can make experimentation easier and may already have reusable workflows.
- Useful if we want multiple avatar styles and visual variations.

Risks:

- ComfyUI is not always ideal for production batch automation unless wrapped carefully.
- Need to check model size, speed, and whether it works reliably headlessly.
- May be slower than MuseTalk.

Test plan:

1. Run a known ComfyUI workflow on RunPod.
2. Test one clean avatar clip with user voice.
3. Measure render speed and output stability.
4. Decide if it is a quality lane or production lane.

Priority: **high quality experiment**.

### 4. MuseTalk 1.5

Repository: https://github.com/TMElyralab/MuseTalk

What it is:

- Real-time high-quality lip-sync model.
- Officially claims 30fps+ on NVIDIA Tesla V100.
- Works with input videos and is a strong candidate for production-style lip-sync.

Current status:

- Already tested locally on MacBook Pro M4.
- Local Mac CPU was too slow.
- MPS test worked and was better than the rejected LivePortrait/Wav2Lip hybrid.
- Best local candidate so far, but the source video had baked subtitles and was not a fair final-quality test.

Why it matters:

- It is probably the first production baseline for volume.
- It edits a real source video rather than generating a whole face from scratch, so it can be more stable.
- On CUDA/RunPod it should be much faster than local Mac.

Risks:

- Requires clean source-avatar video for best result.
- If the face crop/source is bad, output will still look bad.
- It solves lip-sync, not the entire content factory.

Test plan:

1. Run MuseTalk on RunPod with CUDA.
2. Use a clean avatar source clip without baked subtitles.
3. Benchmark 40 sec, 2 min, 10 min.
4. Measure speed, cost, quality, and failure rate.

Priority: **first production-speed benchmark**.

### 5. LatentSync

Repository: https://github.com/bytedance/LatentSync

What it is:

- ByteDance end-to-end lip-sync framework based on audio-conditioned latent diffusion.
- Focused on higher-quality lip synchronization.

Why it matters:

- Potential quality upgrade over older lip-sync methods.
- May be useful for flagship/main-channel videos or close-up shots.

Risks:

- Likely slower than MuseTalk.
- Community reports suggest 4090 can take roughly 100 seconds for 10 seconds in some setups, so it may be too slow for bulk.
- Might fit "premium lane" rather than daily mass production.

Test plan:

1. Run a 10-20 sec test after MuseTalk.
2. Compare mouth/face quality directly.
3. If much better, keep for flagship videos; otherwise skip for factory.

Priority: **quality lane, not first factory lane**.

### 6. Hallo2

Repository: https://github.com/fudan-generative-vision/hallo2

What it is:

- Long-duration and high-resolution audio-driven portrait image animation.
- ICLR 2025 project.

Why it matters:

- The positioning matches long-form avatar generation.
- It is designed around long-duration/high-resolution output, which is exactly the future pain point.

Risks:

- Heavy CUDA-first stack.
- Official examples and requirements are likely more demanding than MuseTalk.
- May need A100-class assumptions, though RTX 5090 should make testing practical.

Test plan:

1. Inspect Docker/requirements.
2. Run a short test on RunPod.
3. Only continue if speed and quality look acceptable.

Priority: **long-form quality candidate**.

### 7. EchoMimic / EchoMimicV2

Repository: https://github.com/antgroup/echomimic

What it is:

- Audio-driven portrait animation through editable landmark conditioning.
- AAAI 2025 project.

Why it matters:

- Can produce more expressive portrait animation.
- Useful if we need a more alive host than pure lip-sync.

Risks:

- Heavier than MuseTalk.
- May be less deterministic for production.
- Need to check exact VRAM and speed.

Test plan:

1. Run one short portrait+audio test.
2. Compare "alive" feeling against MuseTalk.
3. If high quality but slow, reserve for special videos.

Priority: **quality/expressiveness lane**.

### 8. Sonic

Repository: https://github.com/jixiaozhong/Sonic

What it is:

- Audio-driven portrait animation focused on global audio perception.
- Can animate portrait images from audio.

Why it matters:

- Useful if we want many avatar/persona variants from still images.
- Could support satellite-channel presenters without recording many source videos.

Risks:

- May be heavy.
- May have more "AI portrait" artifacts than video-source methods.

Test plan:

1. Test image+audio output on RunPod.
2. Compare against HeyGem/Duix.
3. Decide if it is a satellite-channel avatar generator.

Priority: **persona-variant candidate**.

### 9. OpenAvatarChat

Repository: https://github.com/HumanAIGC-Engineering/OpenAvatarChat

What it is:

- Open-source real-time digital avatar chat platform.
- Supports avatar conversation, TTS, LLM, ASR, and digital human integrations.

Why it matters:

- Useful architecture reference for future interactive agents.
- Can teach us how to structure modules, handlers, and real-time avatar flows.

Risks:

- More chat/conversation product than batch video factory.
- May be overkill for YouTube rendering.

Priority: **architecture reference, not first batch backend**.

### 10. InfiniteTalk / LongCat-Video-Avatar

Repository: https://github.com/MeiGen-AI/InfiniteTalk

What it is:

- Unlimited-length talking video generation / sparse-frame video dubbing framework.
- Designed to align lip sync, head movement, body posture, and facial expressions with audio.
- The repo notes a 2026 update releasing LongCat-Video-Avatar-1.5 as an upgraded open-source framework for audio-driven human video generation.

Why it matters:

- This is directly relevant to long-form avatar video, not just short lip-sync.
- It may be a stronger candidate for "avatar host speaks for many minutes" than older lip-sync-only models.
- It has ComfyUI tutorial/workflow ecosystem around it, which may make RunPod testing easier.

Risks:

- Likely heavier than MuseTalk.
- Some community workflows report slow generation on consumer GPUs; must benchmark.
- Identity preservation and long output stability must be checked carefully.

Test plan:

1. Try a ComfyUI workflow first if standalone install is slow.
2. Run 10-20 sec quality test.
3. If quality is strong, run 2-3 min continuity test.
4. Only then consider a 10 min long-form probe.

Priority: **important long-form avatar candidate**.

### 11. NVIDIA Audio2Face-3D

Repository: https://github.com/NVIDIA/Audio2Face-3D

Hugging Face collection: https://huggingface.co/collections/nvidia/audio2face-3d

What it is:

- NVIDIA open-weight/open-source audio-driven facial animation stack.
- Generates facial animation data from audio for 3D avatars.
- Includes SDK/runtime, training framework, pretrained models, and Audio2Emotion components.

Why it matters:

- This is not a normal 2D talking-head pipeline. It is a 3D-avatar route.
- If we later want a stable branded avatar that does not depend on video-source artifacts, this may be strategically important.
- It is NVIDIA-native, so RunPod GPUs are a natural fit.

Risks:

- Requires a 3D avatar pipeline and rendering layer.
- More setup complexity than 2D video-based systems.
- Better as a second-stage "premium avatar identity" path, not first Shorts factory path.

Test plan:

1. Keep as research lane for 3D presenter.
2. Test only after 2D avatar path is working.
3. Evaluate whether 3D avatar consistency beats video-source realism for our content.

Priority: **strategic 3D-avatar lane**.

### 12. Open-LLM-VTuber

Repository: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber

What it is:

- Open-source voice-interactive AI companion with Live2D avatar.
- Supports swappable LLM, ASR, TTS, and avatar components.
- Designed for local/offline interaction as well as online backends.

Why it matters:

- Useful for interactive agents and personality/avatar UX.
- Could inspire a lightweight avatar assistant for AtlasRepo or internal content ops.

Risks:

- Live2D/VTuber style is probably not the right default for AtlasRepo YouTube authority content.
- Not a direct long-form video production backend.

Priority: **interactive/persona reference**.

### 13. LiteAvatar

Repository: https://github.com/HumanAIGC/lite-avatar

What it is:

- Realtime 2D chat avatar/audio2face model.
- Claims 30fps even on CPU devices.

Why it matters:

- Could be the cheap/fast avatar lane.
- Could support lower-fidelity channels or UI agents.

Risks:

- Visual quality may not be enough for YouTube avatar-led content.
- More suitable for chat avatar than polished video.

Priority: **cheap fallback / interactive lane**.

### 14. Linly-Talker

Repository: https://github.com/Kedreamix/Linly-Talker

What it is:

- Digital human conversation system using Gradio.
- Integrates LLM, ASR, TTS, and voice cloning.

Why it matters:

- Useful as a reference for end-to-end digital human app design.
- May have components we can reuse or learn from.

Risks:

- Likely demo-oriented.
- Need to inspect code quality and batch-video suitability.

Priority: **reference / possible quick demo**.

## Model-Only Repositories To Keep In The Stack

These are not full platforms, but they are important engine components:

| Repository | Role | Use |
|---|---|---|
| https://github.com/Rudrabha/Wav2Lip | Old stable lip-sync baseline | emergency fallback |
| https://github.com/OpenTalker/SadTalker | classic talking head | compare only if easy |
| https://github.com/ShmuelRonen/ComfyUI-LatentSyncWrapper | ComfyUI wrapper for LatentSync | faster quality experiments |
| https://github.com/smthemex/ComfyUI_Sonic | ComfyUI wrapper for Sonic | fast workflow experiments |
| https://github.com/MeiGen-AI/InfiniteTalk | long-duration talking video | long-form quality candidate |
| https://github.com/NVIDIA/Audio2Face-3D | 3D avatar facial animation | future branded avatar path |
| https://github.com/Open-LLM-VTuber/Open-LLM-VTuber | Live2D interactive avatar | agent/persona UX reference |
| https://github.com/harlanhong/awesome-talking-head-generation | curated research list | discovery source |
| https://github.com/weihaox/awesome-digital-human | curated digital human list | discovery source |

## Recommended Test Order

RunPod $10 test should not try everything deeply. It should find whether we have a publishable avatar path.

### Phase 1: Fast production baseline

1. MuseTalk CUDA
2. AvatarAI / ai-avatar-system if setup is quick

Success criteria:

- 40 sec test is publishable.
- 2-3 min test is stable.
- 10 min probe does not drift badly.
- All-in speed is close to realtime or better.

### Phase 2: Ready systems / quality

1. Duix Avatar
2. ComfyUI HeyGem
3. LatentSync

Success criteria:

- Better face/mouth quality than MuseTalk.
- Speed still acceptable.
- Can be scripted without manual UI clicks.

### Phase 3: Long-form and persona variants

1. InfiniteTalk / LongCat-Video-Avatar
2. Hallo2
3. EchoMimic
4. Sonic
5. NVIDIA Audio2Face-3D as a 3D-avatar lane
6. LiteAvatar / OpenAvatarChat / Open-LLM-VTuber reference check

Success criteria:

- Better long-form stability or better visual expressiveness.
- Fits either flagship videos or satellite-channel avatar variations.

## Production Architecture We Want

Local Mac:

- Research repo/topic.
- Generate script and SEO.
- Generate or select voice/audio.
- Prepare screencast or repo demo.
- Build job manifest.
- Start RunPod via API/CLI.
- Receive outputs.
- QC.
- Publish through Postiz / YouTube / TikTok / Instagram.

RunPod:

- Avatar render.
- Lip-sync / digital human generation.
- Video assembly.
- Captions burn-in.
- Horizontal and vertical exports.
- Long-form cutdowns into Shorts.
- Upload results to storage.
- Shut down when batch is complete.

Preferred job flow:

```text
local agent prepares manifest
-> upload inputs to storage
-> start RunPod pod or serverless worker
-> process batch
-> upload results
-> local agent verifies outputs
-> stop/delete pod
```

## How I Searched

I searched in two layers: local AtlasRepo/project data and live GitHub/web.

### Local AtlasRepo/project search

I searched the current project with `rg` for:

```text
avatar
talking
lip-sync
musetalk
hallo
echomimic
sadtalker
wav2lip
sonic
digital human
portrait
```

Places checked:

- `research/avatar-lab`
- `research/marketing`
- `research/youtube`
- `landing/backend/data/repo-catalog.json`
- `data/generated/pending.json`
- `data/generated/llm-output.json`

Result:

- The project already has strong internal notes and benchmark results.
- The local AtlasRepo catalog did not yet contain a strong saved list of avatar/digital-human repos.
- This means we should add an AtlasRepo category for `AI Avatar Factory`.

### Live GitHub/web discovery

I searched for complete systems, not just lip-sync:

```text
open source self hosted AI avatar system MuseTalk voice clone GitHub
open source digital human platform talking avatar self hosted GitHub 2025
HeyGem AI avatar open source GitHub digital human
OpenAvatarChat GitHub digital human avatar
InfiniteTalk GitHub audio driven talking avatar
NVIDIA Audio2Face open source GitHub
Open-LLM-VTuber GitHub avatar
```

Then I searched for model-level and quality candidates:

```text
open source talking avatar model 2025 MuseTalk EchoMimic Hallo2 LatentSync Sonic official GitHub
LatentSync lip sync model GitHub 2025 inference speed
Sonic talking avatar GitHub 2025 official
Hallo2 long duration talking avatar GitHub official
```

Selection criteria:

1. Open-source or self-hostable.
2. Can plausibly run on NVIDIA GPU / RunPod.
3. Has enough system surface to help a batch video factory.
4. Supports audio-driven avatar, digital human, or lip-sync.
5. Has direct GitHub repo or official project page.
6. Can plausibly be scripted through CLI/API/Docker/ComfyUI workflow.

## AtlasRepo Category To Add

Category name:

```text
AI Avatar Factory
```

Subcategories:

- Digital human systems
- Talking avatar platforms
- Lip-sync engines
- Long-form avatar generation
- Portrait animation
- Voice + avatar pipelines
- ComfyUI avatar workflows
- Real-time avatar chat

Seed repositories:

```text
PunithVT/ai-avatar-system
duixcom/Duix-Avatar
billwuhao/Comfyui_HeyGem
TMElyralab/MuseTalk
bytedance/LatentSync
fudan-generative-vision/hallo2
antgroup/echomimic
jixiaozhong/Sonic
HumanAIGC-Engineering/OpenAvatarChat
HumanAIGC/lite-avatar
Kedreamix/Linly-Talker
MeiGen-AI/InfiniteTalk
NVIDIA/Audio2Face-3D
Open-LLM-VTuber/Open-LLM-VTuber
Rudrabha/Wav2Lip
OpenTalker/SadTalker
ShmuelRonen/ComfyUI-LatentSyncWrapper
smthemex/ComfyUI_Sonic
harlanhong/awesome-talking-head-generation
weihaox/awesome-digital-human
```

## Partner Comment

Коротко: нашли не только lip-sync модели, а несколько готовых self-hosted digital-avatar систем. Самые важные для нас: AvatarAI/ai-avatar-system, Duix Avatar, ComfyUI HeyGem, MuseTalk, LatentSync, Hallo2, EchoMimic, Sonic. Логика такая: в понедельник на RunPod тестируем не красоту ради красоты, а производственный benchmark: качество лица, скорость, стоимость за минуту и возможность батчить. Если получаем "Avatar good", вокруг этого можно строить весь контент-завод: long-form, Shorts, нарезки, субтитры и автопостинг.
