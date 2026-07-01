# Video Workflow Index

This repo includes the reusable parts of Kirill's video-generation workflow.

## Shorts And Long-Form Planning

- `02_atlasrepo_youtube_shorts/`
  - topic banks;
  - Shorts scripts;
  - long-form strategy and scripts;
  - partner screencast briefs;
  - XLSX imports;
  - `generate_shorts_v4.py`.

## Avatar / Vertical Video Pipeline

- `04_vertical_video_avatar/`
  - avatar and voice planning docs;
  - script assets;
  - local caption/render scripts;
  - shell workflows for repo shorts;
  - proof/sample videos;
  - thumbnail and screencast templates.

Key scripts:

- `04_vertical_video_avatar/scripts/generate_short.sh`
- `04_vertical_video_avatar/scripts/generate_split_short.sh`
- `04_vertical_video_avatar/scripts/generate_repo_cta_short.sh`
- `04_vertical_video_avatar/scripts/generate_reference_short.sh`
- `04_vertical_video_avatar/scripts/render_local_captions.py`
- `04_vertical_video_avatar/scripts/kokoro_tts.py`

## Social Video / X Tooling

- `05_distribution_agents/X-ACTIONS-AGENT/docs/video.md`
- `05_distribution_agents/X-ACTIONS-AGENT/docs/video-generation.md`
- `05_distribution_agents/X-ACTIONS-AGENT/docs/video-downloader.md`
- `09_social_agents_extended/x-actions-docs/`
- `16_full_agent_sources/x_actions_src/videoCaptions.js`
- `16_full_agent_sources/x_actions_src/videoDownloaderBrowser.js`

## Trend And Data Layer

- `15_trendvi_content_factory/backend_collector_analytics/viral_shorts.py`
- `15_trendvi_content_factory/migrations_selected/add_format_structure_shorts_videos.sql`
- `15_trendvi_content_factory/migrations_selected/add_video_gpt_reports_table.sql`

These files are the bridge for future want2view-style data ingestion: video metadata, format structure, viral shorts analytics, and reports.

## Public Repo Exclusions

The public repo does not include full raw render output, local auth state, private API keys, browser/session files, or large generated caches. Keep those in local/private storage or Git LFS/private artifacts if the team needs full reproducibility.
