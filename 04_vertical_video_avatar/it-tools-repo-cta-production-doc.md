# AtlasRepo Short Format: IT-Tools Repo CTA

## Purpose

This is the first repeatable AtlasRepo short-form template for a real open-source repository.

The format is designed for fast repo discovery content:

- top: real screencast / repo demo
- middle: kinetic topic captions
- center: strong value badge
- bottom: AtlasRepo CTA
- audio: generated English voiceover
- target platform: YouTube Shorts, TikTok, Reels

## Repo

- Name: IT-Tools
- GitHub: https://github.com/CorentinTh/it-tools
- Product angle: private developer toolbox with utilities for tokens, hashes, UUIDs, encoders, converters, and daily dev operations.
- AtlasRepo angle: this is the type of useful open-source repo AtlasRepo should find, launch, record, explain, and convert into a workflow.

## Rendered Output

- Final video: `research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-final.mp4`
- Preview frame: `research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-final-preview.png`
- Base video without local captions: `research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-base.mp4`
- Voiceover: `research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-voice.wav`
- Duration: 15.9s

## Source Assets

- Screencast: `research/avatar-lab/output/jobs/it-tools-demo/it-tools-screenshot-demo-8s.mp4`
- Script: `research/avatar-lab/assets/it-tools-repo-cta-script.txt`
- Renderer: `research/avatar-lab/scripts/generate_repo_cta_short.sh`
- Caption renderer: `research/avatar-lab/scripts/render_local_captions.py`

## Voiceover Script

```text
IT-Tools is one of those open source repos that instantly makes sense.
It gives developers a private local toolbox for tokens, hashes, UUIDs, encoders, converters, and everyday utilities.
This is exactly the kind of repo AtlasRepo should find, launch, record, and turn into a workflow.
```

## Visual Spec

- Canvas: 1080x1920
- Background: near-black
- Screencast: 960x540 top block with dark border
- Header: `IT-TOOLS // OPEN SOURCE`
- Accent colors:
  - teal: `#14f1b2`
  - yellow: `#fff200`
- Center badge: `THIS REPO SAVES DEV HOURS`
- CTA:
  - label: `OPEN-SOURCE REPO:`
  - URL: `atlasrepo.com`
  - small yellow down arrow
- Footer line: `Find it. Launch it. Turn it into a workflow.`

## Re-render Command

```bash
SCRIPT_FILE=/Users/kirill/Desktop/reposearchengine-main/research/avatar-lab/assets/it-tools-repo-cta-script.txt \
AUDIO_FILE=/Users/kirill/Desktop/reposearchengine-main/research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-voice.wav \
BASE_FILE=/Users/kirill/Desktop/reposearchengine-main/research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-base.mp4 \
OUT_FILE=/Users/kirill/Desktop/reposearchengine-main/research/avatar-lab/output/templates/repo-cta-short/it-tools-repo-cta-v2-final.mp4 \
HEADER_TEXT='IT-TOOLS // OPEN SOURCE' \
BADGE_TEXT='THIS REPO SAVES DEV HOURS' \
CTA_LABEL='OPEN-SOURCE REPO:' \
CTA_URL='atlasrepo.com' \
TAGLINE_TEXT='Find it. Launch it. Turn it into a workflow.' \
VOICE=am_liam \
SPEED=1.08 \
bash research/avatar-lab/scripts/generate_repo_cta_short.sh
```

## Current Quality Notes

- The layout is good enough for the first repeatable non-avatar short template.
- The CTA is clearer than the first version: less arrow pressure, more brand color, more structured bottom block.
- The repo is real, but the screencast is still a simple capture. The next iteration should use a richer app walkthrough with 2-3 visible feature changes.
- The voice is acceptable for testing the format, but not final creator-quality. Later versions should use cloned/local voice or a stronger paid/local TTS voice.
- The template can already be reused for daily repo shorts by changing `DEMO_FILE`, `SCRIPT_FILE`, `HEADER_TEXT`, `BADGE_TEXT`, and output paths.

## Next Improvements

- Add AtlasRepo logo/wordmark once the final brand asset is available.
- Replace `atlasrepo.com` with the final public URL if different.
- Generate per-repo CTA copy instead of one generic badge.
- Add a second CTA variant:
  - `OPEN-SOURCE REPO: atlasrepo.com`
  - one-line, no arrow, for cleaner A/B test.
- Add a stronger first 1.5-second hook in the script.
- Build a batch renderer that consumes a repo JSON object and produces:
  - script
  - voice
  - screencast
  - short video
  - title / description / tags
