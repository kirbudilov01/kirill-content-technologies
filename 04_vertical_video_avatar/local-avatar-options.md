# Local Avatar Options For MacBook Pro M4

Date: 2026-06-27

Machine checked:

- MacBook Pro
- Apple M4
- 10 CPU cores
- 16 GB RAM
- Python 3.14.6 system install
- ffmpeg 8.1 installed
- Homebrew installed

## Goal

Build a local avatar pipeline for Shorts and later long-form YouTube inserts without SaaS subscriptions.

Best initial format:

```text
avatar hook 5-15 sec
screen/demo/b-roll 20-45 sec
avatar close 5-10 sec
captions + CTA
```

Do not start with a 10-minute full talking-head avatar. Use avatar as host, not as the whole video.

## Ranked Options

### 1. LivePortrait / FasterLivePortrait MLX

Best first candidate.

Why:

- LivePortrait officially has macOS Apple Silicon support.
- There is an MLX-oriented Apple Silicon port: `fasterliveportrait-mlx`.
- Good for bringing one portrait to life with head motion.
- Better fit for Mac than heavy CUDA-first pipelines.

Use:

- animated host intros;
- avatar reactions;
- short talking inserts;
- stylized presenter.

Risk:

- lip sync may not be perfect by itself depending on workflow;
- needs testing with our portrait style and voice.

Verdict:

> Start here.

### 2. Wav2Lip / Easy-Wav2Lip

Good baseline for mouth sync.

Why:

- Wav2Lip is old but stable.
- Easy-Wav2Lip mentions Apple Silicon/MPS support.
- Useful when the main goal is accurate mouth movement.

Use:

- lip-syncing a still or lightly animated face;
- fallback if LivePortrait lips are not convincing.

Risk:

- face/head can feel static;
- visual quality can look older;
- may need enhancement or compositing.

Verdict:

> Test as fallback or combine with animated portrait footage.

### 3. MuseTalk

Potentially stronger lip sync, but not first on Mac.

Why:

- Better lip-sync reputation than old Wav2Lip/SadTalker in many workflows.
- Good for audio-driven face animation when it works.

Risk:

- Mac compatibility is known to be painful.
- Many setups assume CUDA/NVIDIA.
- On M4/16GB this may cost too much setup time for phase 1.

Verdict:

> Keep for phase 2 or cloud/NVIDIA machine, not first local bet.

### 4. SadTalker

Older full talking-head option.

Why:

- Known project, many tutorials.

Risk:

- Mac performance and dependency issues are common.
- Quality can feel dated compared to newer approaches.

Verdict:

> Low priority unless LivePortrait/Wav2Lip fail.

## Supporting Stack

Voice:

- Kokoro TTS for better local voice experiments.
- Piper for fast/light fallback.

Subtitles:

- whisper.cpp.

Assembly:

- ffmpeg first.
- Remotion later for reusable templates.

Screen capture:

- OBS.

## Test Protocol

Run the same 40-second test through each avatar option:

```text
0-5 sec: avatar hook
5-30 sec: screen/demo segment
30-40 sec: avatar close + CTA
```

Score each option from 1 to 5:

- install friction;
- render speed;
- face quality;
- lip-sync quality;
- stability;
- "would I publish this?" feeling.

## First Test Assets Needed

Minimum:

- 1 portrait image, 1024x1024 or higher.
- 1 short audio file, 10-20 seconds.
- 1 short screen recording, 20-30 seconds.

Portrait advice:

- front-facing;
- clean lighting;
- no extreme expression;
- no hands over face;
- simple background;
- slightly stylized is better than trying to pass as perfectly real.

## Recommended First Experiment

1. Generate or choose one stylized presenter portrait.
2. Generate 15 seconds of voice with Kokoro or Piper.
3. Test LivePortrait/fasterliveportrait-mlx.
4. If lips are weak, test Wav2Lip/Easy-Wav2Lip.
5. Assemble one vertical 40-second Short with ffmpeg.

Success condition:

> If the 40-second test is watchable twice in a row without feeling embarrassing, the pipeline is good enough for phase 1.

