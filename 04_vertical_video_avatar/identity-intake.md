# Kirill Identity Intake

Date: 2026-06-27

Goal: build a local "Kirill digital host" with Kirill's own voice and avatar.

Important rule:

> Use only Kirill's own voice/photo/video assets or assets he explicitly owns and approves.

## Stage 1: Voice

We need clean voice samples first. Voice quality matters more than avatar quality.

### Minimum Voice Sample

For a first clone test:

- 30-60 seconds of clean speech can be enough for zero-shot tests.
- Better: 5-10 minutes.
- Best for a reliable channel voice: 15-30 minutes across several takes.

Record:

- quiet room;
- no music;
- no reverb if possible;
- same microphone position;
- speak naturally, not like an audiobook robot;
- leave 1 second of silence before and after each take.

Recommended language split:

- 5 minutes Russian natural speech;
- 5 minutes English tech script if the channel is English;
- 2 minutes energetic Shorts style;
- 2 minutes calm explainer style.

### Voice Folder

Put raw recordings here:

```text
research/avatar-lab/identity/voice/raw/
```

Preferred format:

```text
.wav, .m4a, .mp3
```

Then normalize:

```bash
bash research/avatar-lab/scripts/prepare_voice_samples.sh
```

Output:

```text
research/avatar-lab/identity/voice/processed/
```

## Stage 2: Avatar

We need both a clean portrait and, later, a short real face video.

### Minimum Avatar Assets

For still avatar tests:

- 1 front-facing portrait image;
- 1024x1024 or larger;
- clean light;
- neutral expression;
- no sunglasses;
- no hands covering face;
- simple background.

Put it here:

```text
research/avatar-lab/identity/avatar/source/kirill-front.png
```

### Better Avatar Assets

For animation/lip-sync tests:

- 10-20 seconds of front-facing video;
- look into camera;
- natural blinking;
- neutral/light smile;
- no fast head movement;
- 1080p or 4K;
- good light.

Put it here:

```text
research/avatar-lab/identity/avatar/source/kirill-face-video.mp4
```

## Stage 3: First Local Clone Candidates

### Voice Engines

1. F5-TTS

- Good first serious local voice-cloning candidate.
- Official repo documents Apple Silicon installation.
- Can do voice cloning from a short reference clip.

2. GPT-SoVITS

- Stronger few-shot/training direction.
- More complex, but useful if F5 is not close enough.

3. OpenVoice

- Good tone-color cloning idea.
- Useful to compare, but not first if setup gets heavy.

4. Chatterbox

- Promising local voice cloning direction.
- Could be tested after F5.

### Avatar Engines

1. LivePortrait / fasterliveportrait-mlx

- First avatar animation candidate for Mac.

2. Wav2Lip / Easy-Wav2Lip

- First lip-sync fallback.

3. MuseTalk

- Quality candidate, but likely heavier on Mac.

## Stage 4: First Test

Create:

```text
20-second script
  -> Kirill voice clone
  -> Kirill still portrait
  -> simple vertical test video
```

Success criteria:

- voice sounds recognizably like Kirill enough to continue;
- pronunciation is not painful;
- avatar image feels credible;
- no uncanny "trying too hard to be real" effect;
- Kirill himself can watch it twice without hating it.

