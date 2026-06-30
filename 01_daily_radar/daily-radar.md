# AtlasRepo Daily Content Radar

Purpose: decide what to shoot, write, and distribute today using live signals, AtlasRepo data, want2view signals, and the user's current creative energy.

This is not a bulk backlog generator. The default output is a short daily slate that can be executed immediately.

## Target Cadence

Default operating rhythm unless the user changes it:

- 3 vertical videos per day minimum.
- 3-5 X/Threads posts per day.
- Forum/Reddit/articles can be handled with a partner or as supporting distribution.
- 5-10 long-form YouTube videos per week is the aggressive target; minimum should still preserve a daily long-form recording habit when possible.
- Daily volume may flex up/down, but rhythm matters more than a large preplanned backlog.

Practical interpretation:

- Each day should produce one executable package, not a giant idea dump.
- Vertical videos should usually be tied to either today's news, a hot repo/use case, or a pattern validated by want2view/YouTube data.
- Long-form videos should create follow-on Shorts and posts, but long-form planning should not block daily Shorts.
- Reuse existing AtlasRepo script/screencast assets when they fit today's pulse.

## Sources Of Truth

### 1. AtlasRepo

Use for:

- fresh open-source repositories
- repo categories and use cases
- demoable tools for Shorts and long-form videos
- AtlasRepo-native CTA and product positioning

Local repo data to inspect first when available:

- `data/repos/index.jsonl`
- `data/generated/llm-output.json`
- `data/generated/pending.json`
- `landing/backend/data/repo-catalog.json`
- `landing/public/data/scout-feed.json`
- `research/youtube/`

Google Sheet:

- Spreadsheet title: `ATLASREPO DATA`
- Spreadsheet id: `1SLP8oyJ-vnfrOo1fJsC1OcdfbwaWK_kErdOa2QQmPb4`
- Known tabs: `Repo`, `UseCases`

### 2. want2view.com

Use once the API/export exists.

Current public positioning checked on 2026-06-22:

- `want2view.com` describes itself as "Video Trend Research & Content Intelligence".
- It is relevant because it surfaces trending videos, audience demand, competitor patterns, SEO angles, and production briefs.
- In this workflow, want2view is the market/format validation layer between raw news and the final decision about what to shoot.

Expected fields:

- topic/title
- video URL or platform id
- platform
- views
- velocity
- publish time
- hook / opening line
- format
- niche
- creator/account
- engagement signals
- notes on why it worked

Until the API exists, ask the user for a CSV/JSON/sample export only when needed.

Current workbook example:

- Uploaded workbook: `FABRICBOT_ECOSYSTEM_4efc3be7_e639_4206_bfc4_4bd3af463705_general.xlsx`
- Project: `FABRICBOT ECOSYSTEM`
- Analysis id: `4efc3be7-e639-4206-bfc4-4bd3af463705`
- Important tabs: `Summary`, `Channels`, `Shorts_48h`, `Videos_7d`, `Viral_Shorts`, `Project_Reports`, `Strategy_Meta`, `Project_Metrics`, `Channel_Rankings`, `Format_Distribution`, `Formats_Shorts`, `Formats_Videos`, `Evergreen_Distribution`, `Duration_Distribution`, `Velocity_*`, `Dashboard_Summary`, `Raw_Details`.

Key insights from that workbook:

- Dataset size: 8,005 unique videos, including 1,959 Shorts and 6,046 long videos.
- Dashboard: 90d long-video views around 208.5M; 90d Shorts views around 161.9M; total channel audience around 74.6M.
- Format mix overall: education 41%, show 18%, expert 15%, podcast 11%, review 10%, news 3%, interview 1%, case 1%.
- Shorts mix: show 72%, review 14%, education 9%, news 3%, interview 2%, case 0%.
- Long-video mix: education 51%, expert 20%, podcast 15%, review 9%, news 3%, case 2%, interview 1%.
- Evergreen mix: hybrid 61%, trend 20%, stable 19%.
- Demand gaps: beginner 15%, case 15%, news 14%.
- Duration data: 21-60s is the main Shorts zone; 301-900s and 900s+ dominate long-form references.
- Practical implication: daily AtlasRepo content should be a hybrid of trend/news hooks plus evergreen education/proof. Cases, beginner explainers, and news-reactive formats are underfilled opportunities.

### 3. Live News And Developer Pulse

Always browse live for current news. Suggested source layers:

- Official: GitHub Blog/Changelog, OpenAI News, Anthropic, Google AI/Developers, Hugging Face Blog, Vercel, Supabase, Cloudflare, Docker, NVIDIA developer, Ollama, LangChain.
- Developer pulse: Hacker News Algolia, GitHub Search/API, GitHub releases Atom feeds, Reddit communities.
- Product pulse: Product Hunt API/site, Show HN, Indie Hackers.
- Trend validation: YouTube Data API/search, Google Trends alternatives if configured, want2view once available.

Expanded source map:

1. Official release layer:
   - OpenAI News / RSS: model, product, API, Codex, Sora, agent updates.
   - Anthropic News / Engineering: Claude, Claude Code, MCP, enterprise/developer updates.
   - Google AI / Google Developers / Gemini: Gemini, agent platforms, AI Studio, developer tooling.
   - GitHub Blog and GitHub Changelog: Copilot, Actions, Codespaces, security, platform changes.
   - Hugging Face Blog and Papers: open models, agents, MCP, evaluation, datasets, Spaces.
   - Vercel, Supabase, Cloudflare, Docker, NVIDIA Developer, Ollama, LangChain, LlamaIndex, n8n, Dify.

2. Developer discussion layer:
   - Hacker News Algolia search and official HN API.
   - Reddit communities: `LocalLLaMA`, `OpenAI`, `ClaudeAI`, `MachineLearning`, `programming`, `webdev`, `selfhosted`, `SaaS`, `SideProject`, `indiehackers`, `n8n`, `automation`.
   - GitHub Discussions/Issues in watched repos.
   - Lobsters for developer-heavy links.

3. Repo and release layer:
   - GitHub Search API for newly created or recently pushed repos.
   - GitHub releases Atom feeds: `https://github.com/:owner/:repo/releases.atom`.
   - GitHub commits Atom feeds for selected repos when release cadence is slow.
   - Watchlists for agent frameworks, MCP servers, local LLM tools, AI IDEs, automation tools, content tools.

4. Product/startup layer:
   - Product Hunt API/site for launches.
   - Show HN for builder launches.
   - Indie Hackers for monetization and micro-SaaS stories.
   - BetaList / launch directories if a specific product category needs broader coverage.

5. Research layer:
   - arXiv API/RSS for `cs.AI`, `cs.LG`, `cs.CL`, `cs.SE`, `cs.HC`, `cs.CY`.
   - Hugging Face Papers / daily paper summaries.
   - Papers With Code trends when available.
   - Use research only when it can be translated into a practical creator/dev/founder angle.

6. Video and creator layer:
   - want2view API/export/workbooks as primary video trend intelligence.
   - YouTube search/API for recency and competitor validation.
   - Existing YouTube reference workbook tabs: `Viral_Shorts`, `Videos_7d`, `Project_Reports`, `Channel_Rankings`, `Velocity_*`.
   - Manual competitor watchlist for channels like Fireship, The PrimeTime, Dan Martell, AI automation channels, Cursor/Claude/Codex tutorial channels.

7. Broad tech news layer:
   - The Verge, TechCrunch, VentureBeat AI, MIT Technology Review AI, Wired AI, The Decoder, Ars Technica, The Register.
   - Use for narrative/context, not as sole proof. Prefer primary sources for factual claims.

8. Search/trend layer:
   - Google Trends alternatives when configured: SerpApi, Glimpse, Apify, or other stable provider.
   - Google News / web search for 24-72h freshness checks.
   - Use this layer to validate whether a topic is rising, not to decide alone.

Source weighting:

- Primary official release: high fact trust, medium virality.
- HN/Reddit/X-style discussion: medium fact trust, high angle discovery.
- GitHub repos/releases: high proof value, high AtlasRepo fit.
- want2view/YouTube: high format validation, high daily production value.
- Broad media: medium fact trust, high narrative framing.
- arXiv/research: high novelty, variable shoot-today value.

Target topics:

- AI agents
- coding agents and IDEs
- Codex, Claude Code, Cursor, Gemini/Antigravity-style tools
- MCP
- local LLMs
- open-source AI apps
- automation and content systems
- self-hosted alternatives
- devtools
- creator tools
- practical AI business workflows

### 4. Existing Content Operations

Reference folder:

- `/Users/kirill/Desktop/CONTENT DISTRIBUTION`

Relevant areas:

- `AGENT/` for local content pipeline, intake, shorts, SMM generation, Postiz integration.
- `X-ACTIONS-AGENT/` for X/Twitter monitoring, RSS, calendar, engagement, and distribution docs.
- `TELEGRAM : THREADS AGENT/` for Threads automation context.
- `ABOUT ME /` for persona and voice.
- `RESEARCH/`, `STRATEGY/`, `POSTING/`, `VIDEOS/`, `OBS/` for assets and prior work.

Safety:

- Do not read `.env`, `local.env`, auth/session storage, browser state, tokens, API keys, Telegram credentials, or generated MTProto/session strings.
- If secrets appear in markdown/yaml while reading docs, do not repeat them.

## Daily Workflow

1. Establish today's intent:
   - energy level
   - recording capacity
   - target language
   - priority: growth, product traffic, authority, community, revenue, or experimentation

2. Pull current signals:
   - live news from the last 24-72 hours
   - AtlasRepo fresh repos/use cases
   - want2view viral/video signals when available
   - existing content/published history when available

3. Score each candidate:
   - `hype_score`: is the topic currently hot?
   - `atlasrepo_fit`: does it naturally connect to AtlasRepo?
   - `proof_score`: is there a concrete repo/demo/news source?
   - `shoot_today_score`: can it be recorded today without heavy prep?
   - `longform_score`: can it support a 10-20 minute video?
   - `shorts_score`: can it become a 30-60 second Short/Reel/TikTok?
   - `discussion_score`: will it trigger comments on Reddit/X/Threads?
   - `novelty_score`: is the angle non-obvious?

4. Select a small slate:
   - 3-5 Shorts/Reels/TikToks
   - 1 long-form video
   - 1 carousel
   - 1 Reddit/X/Threads discussion angle
   - optional article/newsletter only if the topic has enough depth

Suggested daily vertical slots:

- Morning: conflict/news hook.
- Midday: micro-demo or repo proof.
- Evening: hot take, safety/drama, or market implication.

Suggested daily X/Threads slots:

- 1 news/reactive post.
- 1 practical build/use-case post.
- 1 contrarian/hot-take post.
- 1 repo/tool discovery post.
- 1 optional thread turning the long-form topic into a framework.

5. For each selected item, produce:
   - title/topic
   - source evidence URLs
   - hook
   - talking points
   - visual proof / screencast plan
   - AtlasRepo angle
   - CTA
   - risk/caveat
   - expected asset requirements

## Output Shape

Default response for "what do we do today":

1. Top pulse: 3-5 facts/signals from live sources.
2. Recommended daily slate.
3. Exact Shorts scripts or bullet beats.
4. Long-form concept with first 30 seconds, structure, and screen capture plan.
5. Carousel outline.
6. Reddit/X/Threads angle.
7. What to skip today and why.

Keep the slate executable. Prefer fewer items with stronger evidence.

## Decision Rules

- A news item alone is not a content idea. It needs an AtlasRepo/product/use-case angle.
- A repo alone is not a content idea. It needs a human problem, proof, and a visual demo.
- Do not over-plan far ahead unless the user explicitly asks for a backlog.
- Prioritize today's usable energy over theoretical completeness.
- If the user asks for current context, browse live and cite sources.
- If the user asks to publish or schedule, inspect the content distribution system first and avoid exposing secrets.
