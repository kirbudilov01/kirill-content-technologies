# Thumbnail System

Date: 2026-06-27

Purpose: make YouTube thumbnails for AtlasRepo/FABRICBOT agent videos.

Thumbnails are not decoration. They are part of the conversion machine.

## Reference Pattern

The reference uses:

- 1280x720 horizontal frame.
- 2-4 huge words.
- one emotional face.
- one tool/repo icon or badge.
- intense contrast.
- very simple message.

Examples:

- `NEW & FREE`
- `ANOTHER BANGER`
- `DESTROYS FABLE 5?`
- `FINALLY`

## AtlasRepo Thumbnail Formula

```text
BIG CLAIM
+ TOOL / REPO BADGE
+ KIRILL FACE
+ SMALL CONTEXT LINE
```

Good claim types:

- `NEW & FREE`
- `AGENT IS INSANE`
- `CLAUDE KILLER?`
- `RUNS LOCALLY`
- `OPEN SOURCE`
- `NO SUBSCRIPTION`
- `CODEX READY`
- `THIS CHANGES SEO`
- `BUILDS APPS`
- `CONTROLS PC`

Small context line:

- repo name;
- tool name;
- version;
- workflow category;
- "AI Agent";
- "Open Source".

## Thumbnail Styles

### Style 1: Green Agent Shock

Use for:

- computer-use agents;
- open-source agents;
- "new/free" tools.

Visual:

- black/green electric background;
- big white/green text;
- face shocked;
- repo badge in the middle.

### Style 2: White Tool Card

Use for:

- Claude/Codex/tool updates;
- calmer explainer videos.

Visual:

- white background;
- app icon;
- red underline/arrow;
- face below.

### Style 3: Red Warning

Use for:

- "destroys X";
- "is this the end of X?";
- competitive comparisons.

Visual:

- red/black;
- big question;
- app badge;
- face pointing or shocked.

### Style 4: Orange Finally

Use for:

- major releases;
- "finally fixed";
- long-awaited updates.

Visual:

- orange app icon;
- giant FINALLY;
- crowd/repetition pattern or dramatic background.

## First Generator

Local MVP:

- ImageMagick;
- Kirill frame;
- generated colored background;
- text overlays;
- optional tool badge.

Script:

```bash
bash research/avatar-lab/scripts/generate_thumbnail.sh
```

Inputs:

- `FACE_FILE`
- `OUT_FILE`
- `TOP_TEXT`
- `BOTTOM_TEXT`
- `BADGE_TEXT`
- `STYLE`

## Agent Output Later

A thumbnail agent should output:

```json
{
  "style": "green_agent_shock",
  "top_text": "NEW & FREE",
  "badge_text": "HERMES AGENT",
  "bottom_text": "v0.17",
  "emotion": "shocked",
  "tool_icon": "optional path",
  "small_context": "AI agent update"
}
```

## Rules

- 2-4 words maximum for main text.
- Face must be large.
- Do not use tiny text.
- Tool name must be legible.
- One visual idea per thumbnail.
- Build 3 variants for every long video.
- Pick by click clarity, not taste alone.

