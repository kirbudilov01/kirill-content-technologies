# Avatar Lab

Local first-phase pipeline for AtlasRepo/FABRICBOT Shorts.

This folder starts with the most reliable Mac-local MVP:

```text
text script
  -> macOS local voice via `say`
  -> vertical video through `ffmpeg`
  -> optional avatar image slot
  -> output .mp4
```

It is intentionally simple. The goal is to make the production loop run before adding heavier avatar models like LivePortrait, Wav2Lip, MuseTalk, Kokoro, or Piper.

## Quick Start

From the repo root:

```bash
bash research/avatar-lab/scripts/generate_short.sh
```

Output:

```text
research/avatar-lab/output/atlasrepo-short.mp4
```

## Optional Avatar Image

Put a portrait image here:

```text
research/avatar-lab/assets/avatar.png
```

Then rerun the script. The generated Short will place the avatar in the frame.

Good avatar image:

- square or portrait;
- 1024px or larger;
- front-facing;
- clean lighting;
- simple background;
- neutral expression.

## Voice

Default voice is `Daniel`, a local macOS English voice.

List available voices:

```bash
say -v "?"
```

Run with another voice:

```bash
VOICE="Eddy (English (US))" bash research/avatar-lab/scripts/generate_short.sh
```

## Better Local Neural Voice: Kokoro

Setup:

```bash
bash research/avatar-lab/scripts/setup_kokoro.sh
```

Generate a Kokoro WAV:

```bash
research/avatar-lab/.venv-kokoro/bin/python \
  research/avatar-lab/scripts/kokoro_tts.py \
  --text-file research/avatar-lab/assets/sample-short.txt \
  --out research/avatar-lab/output/kokoro.wav
```

Then use that audio in the video template:

```bash
AUDIO_FILE=research/avatar-lab/output/kokoro.wav \
  bash research/avatar-lab/scripts/generate_short.sh
```

## Custom Script Text

Create a text file and pass it:

```bash
SCRIPT_FILE=research/avatar-lab/assets/my-short.txt bash research/avatar-lab/scripts/generate_short.sh
```

## Split Layout: Demo Top, Avatar Bottom

This layout is better for Shorts where the viewer needs to see a product, GitHub repo, browser, or demo while the avatar acts as the host.

```bash
bash research/avatar-lab/scripts/generate_split_short.sh
```

With Kokoro audio:

```bash
AUDIO_FILE=research/avatar-lab/output/kokoro.wav \
  bash research/avatar-lab/scripts/generate_split_short.sh
```

With a real demo video:

```bash
DEMO_FILE=/path/to/demo.mp4 \
AUDIO_FILE=research/avatar-lab/output/kokoro.wav \
OUT_FILE=research/avatar-lab/output/demo-split.mp4 \
  bash research/avatar-lab/scripts/generate_split_short.sh
```

Layout:

```text
top: demo/browser/screencast
bottom left: avatar
bottom right: title + CTA
```

Later we can add a `demo_focus` mode:

```text
0-5 sec: avatar hook
5-45 sec: demo expands over most of the frame
45-60 sec: avatar returns for CTA
```

## Reference Layout: Demo + Punchline + Human Card

This layout follows the Shorts reference: demo at top, big punchline in the center, avatar/human card below.

```bash
AUDIO_FILE=research/avatar-lab/output/kokoro.wav \
OUT_FILE=research/avatar-lab/output/reference-test.mp4 \
bash research/avatar-lab/scripts/generate_reference_short.sh
```

## Thumbnails

Generate a first local thumbnail:

```bash
TOP_TEXT="NEW & FREE" \
BADGE_TEXT="HERMES AGENT" \
BOTTOM_TEXT="v0.17" \
STYLE=green \
OUT_FILE=research/avatar-lab/output/thumbnails/hermes-test.png \
bash research/avatar-lab/scripts/generate_thumbnail.sh
```

More notes:

```text
research/avatar-lab/thumbnail-system.md
```

With a demo:

```bash
DEMO_FILE=/path/to/demo.mp4 \
AUDIO_FILE=research/avatar-lab/output/kokoro.wav \
PUNCH_LEFT="AGENT IS" \
PUNCH_RIGHT="INSANE" \
VIDEO_TITLE="This AI agent can control your browser" \
bash research/avatar-lab/scripts/generate_reference_short.sh
```

## Next Quality Layers

After this MVP works:

1. Replace macOS `say` with Kokoro/Piper.
2. Generate avatar intro/outro with LivePortrait or fasterliveportrait-mlx.
3. Add real screencast/B-roll segments.
4. Add Remotion templates for cleaner captions and layouts.
5. Use Postiz for X and social reposting.

## Kirill Voice And Avatar

For using Kirill's own voice and face, start here:

```text
research/avatar-lab/identity-intake.md
```

Prepare folders and normalize voice samples:

```bash
mkdir -p research/avatar-lab/identity/voice/raw
# put Kirill voice files into that folder, then:
bash research/avatar-lab/scripts/prepare_voice_samples.sh
```

Set up the first serious local voice-clone candidate:

```bash
bash research/avatar-lab/scripts/setup_f5_tts.sh
```
