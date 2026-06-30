# 🏗️ Global Channel Catalog System

## Overview

The **Global Channel Catalog** (`yt_channel_catalog`) is a central repository for all YouTube channels used across the system. This enables:

1. **Persistent channel registry** — All channels from projects stored in one place
2. **Channel reuse** — Channels indexed and available for future searches
3. **Worker prioritization** — (future) Worker fetches channels from catalog first

## Architecture

### Tables

- **`yt_channel_catalog`** — One row per unique YouTube channel
  - `channel_id` (TEXT PRIMARY KEY) — YouTube channel ID (e.g., "UCX6OQ3DkcsbYNE6H8uQQuVA")
  - `title`, `description`, `url`, `thumbnail` — Channel metadata
  - `subscribers`, `views` — Metrics for ranking
  - `verified` — Whether verified channel
  - `updated_at` — Last update timestamp

- **`yt_channel_catalog_keywords`** — Keyword → channel mappings (for future search optimization)
  - `channel_id` → links to catalog
  - `keyword` — Search term that found this channel
  - `search_count` — How many times this keyword returned this channel
  - `last_found_at` — When last confirmed by API

### Population Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. STARTUP: ensure_catalog_schema()                     │
│    ├─ Creates tables (idempotent)                       │
│    └─ Bootstrap: Imports all YouTube channels from      │
│       content_factory_channels table                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 2. COLLECTOR RUN START (Orchestrator.start_run)         │
│                                                         │
│    When analysis run starts:                            │
│    ├─ get_channels_for_analysis(analysis_id)           │
│    ├─ Convert competitor_channels to catalog format    │
│    └─ add_project_channels_to_catalog(source="collector") │
│                                                         │
│    All project channels → global catalog                │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. SEARCH (trendvi_search) — FUTURE OPTIMIZATION        │
│    ├─ lookup_channels_by_keyword() checks catalog first │
│    ├─ If hits found: prioritize from cache              │
│    └─ Otherwise: query YouTube API, then upsert to      │
│       catalog for future queries                        │
└─────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YT_CATALOG_HIT_THRESHOLD` | 15 | Min hits required to skip API call (future) |
| `YT_CATALOG_STALE_DAYS` | 14 | Days before channel is considered stale (future) |

## Deployment Steps

### 1. Initial Setup & Migration

Run the migration script once to load all existing project channels:

```bash
# Show current stats (read-only)
docker compose -p arseniyu-dashboard exec -T backend \
  python /app/backend/scripts/migrate_channels_to_catalog.py --stats-only

# Actually perform migration (creates catalog tables and imports channels)
docker compose -p arseniyu-dashboard exec -T backend \
  python /app/backend/scripts/migrate_channels_to_catalog.py
```

Expected output:
```
============================================================
🔄 Channel Catalog Migration
============================================================

1️⃣  Ensuring catalog schema...
   ✅ Done

2️⃣  Current catalog stats:
   Total channels: 0
   Unique keywords: 0

3️⃣  Migrating content_factory_channels...
   ✅ 47 channels processed

4️⃣  Migrating competitor_channels...
   ✅ 12 channels processed

5️⃣  Final catalog stats:
   Total channels: 59
   Unique keywords: 0

============================================================
✅ Migration complete!
============================================================
```

### 2. Verify Setup

```sql
-- Check if bootstrap worked
docker compose -p arseniyu-dashboard exec -T db psql -U postgres -d trendvi -c \
  "SELECT COUNT(*) as total_channels FROM yt_channel_catalog;"

-- Check channels by platform/project
docker compose -p arseniyu-dashboard exec -T db psql -U postgres -d trendvi -c \
  "SELECT COUNT(*) as total_channels FROM yt_channel_catalog;"
```

## Daily Operations

### Automatic Population

After setup, **every collector run automatically adds all project channels to the catalog**:

1. User creates a competitor analysis project with YouTube channels
2. User starts a collector run (via API or dashboard)
3. **Immediately** in `Orchestrator.start_run()`:
   - Fetch channels from `competitor_channels` table
   - Convert to catalog format
   - Call `add_project_channels_to_catalog(source="collector_project")`
4. Channels are now in global catalog for future workers/searches

### Monitoring

Check catalog health:

```python
# Quick stats
from trendvi_search.catalog_sync import get_catalog_stats
stats = await get_catalog_stats()
print(f"Total channels: {stats['total_channels']}")
```

Or via database:

```sql
SELECT COUNT(*) as total_channels FROM yt_channel_catalog;
SELECT COUNT(DISTINCT channel_id) as unique_channels FROM yt_channel_catalog;
```

## Files

- **Catalog operations**: [backend/trendvi_search/catalog.py](backend/trendvi_search/catalog.py)
- **Sync integration**: [backend/trendvi_search/catalog_sync.py](backend/trendvi_search/catalog_sync.py)
- **Migration script**: [backend/scripts/migrate_channels_to_catalog.py](backend/scripts/migrate_channels_to_catalog.py)
- **Collector integration**: [backend/collector/orchestrator.py](backend/collector/orchestrator.py) (calls `add_project_channels_to_catalog` on run start)
