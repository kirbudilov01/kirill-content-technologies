# Repo Screencast Template

Date: 2026-06-27

Purpose: define the visual format for AtlasRepo Shorts and YouTube inserts when showing GitHub repos, app websites, docs, demos, and local launches.

This is separate from the avatar/voice work. The avatar is the host. The screencast template is the stage.

## Core Layout

Vertical 1080x1920.

```text
┌──────────────────────────────┐
│  TOP: repo / app / demo       │
│  GitHub, docs, browser, UI    │
│  badges: stars, stack, score  │
├──────────────────────────────┤
│  CENTER: kinetic subtitles    │
│  big words, highlighted terms │
│  icons, arrows, callouts      │
├──────────────────────────────┤
│  BOTTOM: avatar / CTA / logo  │
│  Kirill host, small but alive │
└──────────────────────────────┘
```

Default split:

- Top 48-55%: screencast/demo.
- Middle 25-30%: subtitles and key claim.
- Bottom 18-25%: avatar, channel identity, CTA.

The avatar should not fight the demo. It should frame the explanation.

## Scene Types

### 1. Hook Scene

Visual:

- Avatar visible.
- GitHub or website blurred/zoomed in background.
- Big subtitle in the center.

Example:

```text
THIS AI AGENT
CAN CONTROL YOUR COMPUTER
```

Use:

- first 1-3 seconds.

### 2. Repo Reveal Scene

Visual:

- GitHub repo page at top.
- GitHub icon.
- Repo owner/name badge.
- Stars/license/language badges if available.

Subtitle:

```text
I found this repo on GitHub.
It is not just a tool.
It can become a workflow.
```

### 3. Proof Scene

Visual:

- README section.
- Docs.
- Demo UI.
- Terminal/local app if available.

Callouts:

- arrows;
- circles;
- "watch this";
- "this is the important part";
- "works locally";
- "open-source".

### 4. Workflow Scene

Visual:

- 3-step mini diagram.

Example:

```text
Repo → Codex task → Working workflow
```

Use:

- after showing the repo/demo.

### 5. Limitation Scene

Visual:

- darker panel;
- warning icon;
- honest caveat.

Example:

```text
The setup is still rough.
But the direction is obvious.
```

This increases trust.

### 6. CTA Scene

Visual:

- avatar returns;
- AtlasRepo logo/domain;
- workflow pack name.

Example:

```text
Full setup prompts and workflow packs
live inside AtlasRepo.
```

## Subtitle Style

Subtitles are the center of the video, not an afterthought.

Rules:

- 3-7 words per line.
- 1-2 lines at once.
- Highlight one important word per beat.
- Use big readable type.
- No tiny captions at the bottom.
- Use color sparingly: white text, cyan/yellow highlights.

Example:

```text
AI TOOLS are everywhere.
WORKING SYSTEMS are rare.
```

Highlight words:

- AI AGENT
- OPEN-SOURCE
- CODEX
- CLAUDE
- WORKFLOW
- LOCAL
- FREE
- REPO
- LAUNCH

## Visual Assets

Reusable icons:

- GitHub icon.
- Stars icon.
- Terminal icon.
- Browser icon.
- Code icon.
- Warning icon.
- Workflow/arrow icon.
- AtlasRepo mark.

Reusable badges:

- `OPEN SOURCE`
- `GITHUB`
- `LOCAL`
- `CODEX`
- `CLAUDE`
- `WORKFLOW PACK`
- `TESTED`
- `ROUGH SETUP`
- `WORTH WATCHING`

## Motion

Keep animation clean and utility-first:

- quick zoom into repo name;
- pan over README;
- cursor highlight;
- subtitle word pop;
- arrow/circle callout;
- demo card slides up;
- avatar small idle motion;
- CTA slide-in.

Avoid:

- random flashy transitions;
- too many emojis;
- constant shake;
- unreadable moving text.

## Agent Inputs

A future screencast agent should output:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "website_url": "https://example.com",
  "hook": "This AI agent can control your browser",
  "screens": [
    {
      "type": "github_header",
      "duration": 3,
      "callout": "Open-source agent framework"
    },
    {
      "type": "readme_section",
      "duration": 5,
      "callout": "This is the workflow promise"
    },
    {
      "type": "demo_ui",
      "duration": 8,
      "callout": "Watch it run the task"
    }
  ],
  "subtitles": [
    { "text": "This is not just another AI tool.", "highlight": "AI tool" },
    { "text": "It can become a workflow.", "highlight": "workflow" }
  ],
  "cta": "Unlock the full workflow pack inside AtlasRepo"
}
```

## Relationship To `atlasrepo-launch-repo`

The `atlasrepo-launch-repo` workflow is the capture layer:

- inspect repo;
- run it locally if possible;
- record demo/screens;
- save screencast.

This template is the packaging layer:

- take that screencast;
- add avatar;
- add subtitles;
- add callouts;
- add CTA;
- export Shorts/YouTube inserts.

## First Implementation Target

Build one `repo_short` generator:

Inputs:

- `demo.mp4`
- `avatar.png` or animated avatar clip
- `audio.wav`
- `captions.json`
- `repo_name`
- `cta`

Output:

- `1080x1920` short mp4.

MVP layout:

```text
top: demo video
middle: large subtitle card
bottom: Kirill avatar + AtlasRepo CTA
```

Later:

- animated subtitle timing;
- highlighted words;
- GitHub badges;
- icon overlays;
- automatic caption timing from transcript.

