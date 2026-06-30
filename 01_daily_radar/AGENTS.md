# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Repo layout — two independent apps

This is a monorepo with two apps that share a name but are otherwise standalone. Always note which one you are working in before running commands:

1. **Root (`/`) — RepoSearchEngine scout** (Node/TypeScript). A 24/7 background scout that pulls open-source candidates from GitHub / Hacker News / Reddit / Product Hunt, scores them, and generates a static site in `docs/` for GitHub Pages. Deployed via `docker-compose.yml`.
2. **`landing/` — AtlasRepo MVP** (React + Vite + its own Node backend). Paid community landing page (`#/`, `#/access`, `#/member` hash routes) with an independent hourly Scout + Hermes cron stack under `landing/backend/`. Has its own payments integration (Cryptomus + Stripe widgets in the paywall modal).

The two apps do not import each other. They even duplicate some "Scout" concepts. When a task mentions the landing page, pricing, auth, or payments, work in `landing/`. When it mentions discovery cycles, source connectors, or the GitHub Pages site, work in the root.

## Commands

### Root scout (from repo root)

- `npm run start` — start the forever-scheduler (`src/main.ts`). Runs one cycle immediately, then every `SCOUT_INTERVAL_MINUTES` (default 30).
- `npm run discover` — run one discovery cycle (`src/jobs/discover-once.ts`).
- `npm run build-site` — regenerate `docs/index.html` + `docs/data/search.json` from current `data/`.
- `npm run check` — `tsc --noEmit` typecheck.
- `npm run health` — healthcheck used by the Docker container.
- `docker compose up -d --build` — run scout + python LLM worker + Ollama together. `docker compose logs -f scout` to tail.

### Landing frontend (from `landing/`)

- `npm run dev` — Vite dev server.
- `npm run build` — production build into `landing/dist/`.
- `npm run lint` — ESLint 9 flat config (`eslint.config.js`).
- `npm run preview` — serve the prod build locally.
- `npm run check` — runs `scripts/run-quality-gates.sh` (lint + build across frontend and backend if present).
- `npm run prepush:check` — full pre-push diagnostic script.

### Landing backend workers (from `landing/`, delegates into `landing/backend/`)

- `npm run workers:install` — install backend deps.
- `npm run workers:start` — long-running cron process (`backend/src/index.js`) that runs Scout and Hermes hourly.
- `npm run scout:once` / `npm run hermes:once` — one-shot runs.
- `node backend/src/api/server.js` (from `landing/`) — HTTP API on port `API_PORT` (default 8787). Exposes `/api/health`, `/api/access/session`, `/api/payments/cryptomus/invoice`.

## Gotchas when setting up landing

- `npm install` in `landing/` has a `prepare` script that calls `bash scripts/install-git-hooks.sh`, which expects a `.githooks/` directory at the **repo root**. That directory does not exist, so a plain `npm install` will fail. Use `npm install --ignore-scripts` inside `landing/` until the hooks folder is added.
- Vite `base` is set to `/reposearchengine/` in `landing/vite.config.js` (the landing README still mentions `/agents-society/`). The GitHub Pages URL path depends on this — do not change casually.
- `landing/src/main.jsx` mounts `App.jsx`, a **single-file** implementation of landing + access + member. There are also files under `landing/src/pages/` (`AccessPage.jsx`, `MemberPage.jsx`, `LandingPage.jsx`) that are **not wired up**. When editing routes, edit `App.jsx` unless you're intentionally migrating to the split files.
- Vite env vars must be prefixed `VITE_` and require a dev-server restart after editing `landing/.env.local`. Templates are in `landing/.env.frontend.example` and `landing/.env.backend.example`.

## Root scout — architecture

Entry `src/main.ts` → pipeline `src/core/pipeline.ts` drives each cycle:

1. Enabled connectors in `src/connectors/` (`github.ts`, `hackernews.ts`, `reddit.ts`, `producthunt.ts`) produce raw candidates. Flags `ENABLE_GITHUB`, `ENABLE_HACKERNEWS`, `ENABLE_REDDIT`, `ENABLE_PRODUCTHUNT` gate each one (see `src/config.ts`).
2. `src/core/dedup.ts` collapses duplicates across sources; `storage.loadExistingRepoIds()` filters out repos already persisted.
3. For each new candidate: `scoring.ts` → numeric score + breakdown, `categorize.ts` → tags, `moderation.ts` → `active | blocked | quarantine`. A simple fallback RU/EN summary is generated inline.
4. Top N (`SCOUT_MAX_GENERATE_PER_CYCLE`, default 40) are appended to `data/` via `core/storage.ts` and enqueued for LLM post-processing in `data/generated/pending.json` via `core/llm-queue.ts`.
5. After each cycle, `src/site/generator.ts` re-renders `docs/index.html` + `docs/data/search.json` (this is what GitHub Pages serves; `docs/` is a build artefact committed to the repo).
6. `worker/worker.py` (Python, runs in its own container) polls `data/generated/pending.json` every 30s and calls Ollama (`llama3.1:8b` by default) to produce better RU/EN summaries into `data/generated/llm-output.json`. The Node pipeline does not block on this — LLM output is decoupled and merged by the site generator on later cycles.

Source policy (`config/source-policy.json`, loaded via `src/core/source-policy.ts`): `allow` / `allowRestricted` / `deny` lists. Respect this when adding connectors — e.g. arbitrary scraping, Discord/Telegram/Twitter/Medium are explicitly in `deny`.

Typed shapes live in `src/types/models.ts` (`CycleReport`, `ScoutedRepo`, candidate types). ESM `.js` import suffixes are required (see how pipeline imports `./pipeline.js` from a `.ts` source) — this is intentional for Node ESM.

## Landing architecture

- **Frontend (`landing/src/App.jsx`)**: hash router with three states — landing, access, member. Language (`ru` / `en` / `zh`) is held in component state; all copy lives in the `COPY` constant. Selected plan / auth provider / payment method are persisted in `localStorage` under `agents_society_*` keys. `trackEvent` pushes to `window.dataLayer` for analytics.
- **Paywall modal**: the access route opens a modal listing 5 payment methods. When `card` is selected, `StripeWidget` renders. When `cryptomus` is selected, `CryptomusWidget` renders. The other methods (`ton`, `cis-card`, `paynexus`) are UI-only stubs.
- **Cryptomus widget** (`src/components/CryptomusWidget.jsx`): two modes — **static UUID** (env `VITE_CRYPTOMUS_PAYMENT_UUID_MONTHLY` / `_LIFETIME` → iframe of `https://pay.cryptomus.com/pay/{UUID}`), or **invoice API** (calls `${VITE_API_BASE}/api/payments/cryptomus/invoice`, which in `landing/backend/src/api/server.js` signs a payload with MD5(base64(json) + api_key) and POSTs to `api.cryptomus.com/v1/payment`). Backend requires `CRYPTOMUS_MERCHANT_ID` + `CRYPTOMUS_PAYMENT_API_KEY`; returns 503 if missing.
- **Stripe widget** (`src/components/StripeWidget.jsx`): prefers `<stripe-pricing-table>` (loads `https://js.stripe.com/v3/pricing-table.js` lazily) when `VITE_STRIPE_PUBLISHABLE_KEY` + `VITE_STRIPE_PRICING_TABLE_ID` are set; otherwise falls back to iframing `VITE_STRIPE_PAYMENT_LINK_MONTHLY` / `_LIFETIME`.
- **Landing backend**: `backend/src/index.js` kicks Scout + Hermes on boot then schedules them with `node-cron` (`0 * * * *`). Scout (`backend/src/scout/runScoutCycle.js`) writes `backend/data/repo-catalog.json` (up to 500) and the public-facing `landing/public/data/scout-feed.json` (top 12). The React landing fetches `scout-feed.json` first from GitHub raw, then from the local build as fallback, every 60s.

## Deploy

- **Root**: Docker Compose is the long-running deploy (`scout` + `worker` + `ollama`). macOS LaunchAgent plist in `ops/com.reposearchengine.plist` wraps `docker compose up`. GitHub Pages serves `docs/` from `main` (published as part of normal commits — no separate publish step needed unless a workflow in `.github/` rebuilds it).
- **Landing**: GitHub Pages via `landing/.github/workflows/deploy-pages.yml` on push to `main` — runs `npm run build` and publishes `landing/dist/`. Validate locally with `npm run build && npm run preview`.

## Content distribution / daily radar mode

When the user asks about daily content, Shorts, long-form videos, carousels, articles, Reddit/X/Threads angles, news, viral topics, or "what should we shoot today", work as a daily content radar for AtlasRepo rather than as a static batch generator.

Core context:

- AtlasRepo is one source of truth for repos, tools, use cases, and open-source project discovery.
- The user's `want2view.com` service is expected to become another source of truth for video performance, viral topics, hooks, and trend signals once its API/export exists.
- Google Sheet `ATLASREPO DATA` (`1SLP8oyJ-vnfrOo1fJsC1OcdfbwaWK_kErdOa2QQmPb4`) is available through the Google Sheets connector. Current tabs seen: `Repo`, `UseCases`.
- Local content-distribution context lives outside this repo at `/Users/kirill/Desktop/CONTENT DISTRIBUTION`. Treat it as reference material for persona, publishing, Postiz, Threads/X agents, and existing content operations.
- Do not read or quote secrets from that external folder. Avoid `.env`, `local.env`, browser/session storage, API keys, tokens, Telegram sessions, and generated auth state files. Several markdown/yaml files in that folder may contain leaked keys; do not repeat them in responses.

Daily operating principle:

- Do not generate 100 videos far ahead by default.
- Prefer a live daily loop: what was already published, what worked, what is happening now, what the user has energy to record today, and what can become a long-form video today.
- For current news or "today's pulse", browse live sources every time. Do not rely on model memory for latest AI/devtools/news facts.

Use `research/content-distribution/daily-radar.md` as the working reference for source lists, scoring, and the expected output shape.
