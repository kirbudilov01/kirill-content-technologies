# 🏗️ Global Projects Registry

## Overview

The **Global Projects Registry** (`global_projects_registry`) is a central repository for all competitor analysis projects. This enables:

1. **Persistent project tracking** — All projects stored in one place with metadata
2. **Project reuse** — Projects indexed by language, keywords, and active status  
3. **Worker automation** — (future) Background workers can access popular/recent projects to re-run collection

## Architecture

### Tables

- **`global_projects_registry`** — One row per unique competitor analysis project
  - `project_id` (BIGSERIAL PRIMARY KEY) — Internal project registry ID
  - `analysis_id` (TEXT UNIQUE) — Linked to original `competitor_analysis.competitor_analysis_id`
  - `owner_id` — User ID (foreign key to users)
  - `name`, `description` — Project metadata
  - `keywords` — Comma-separated search terms for the project
  - `language` — Project language (ru, en, zh, etc.)
  - `channel_count` — Number of YouTube channels in this project
  - `is_active` — Whether project is currently active
  - `last_run_at`, `last_run_id` — When project was last collected and by which collector run
  - `created_at`, `updated_at` — Timestamps

### Population Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. STARTUP: Ensure schema (sync at app start)           │
│    └─ Create global_projects_registry table             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 2. COLLECTOR RUN START (Orchestrator.start_run)         │
│                                                         │
│    When analysis run starts:                            │
│    ├─ Fetch project info from competitor_analysis      │
│    ├─ Call add_or_update_project_in_registry()         │
│    ├─ Call link_project_channels()                      │
│    └─ Project is now in global registry with metadata   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. BACKGROUND AUTOMATION (FUTURE)                       │
│    ├─ External agent queries registry by language       │
│    ├─ Picks popular/active projects                     │
│    └─ Auto-runs collection (via Orchestrator API)       │
└─────────────────────────────────────────────────────────┘
```

## Deployment Steps

### 1. Initial Setup & Migration

Run the migration script once to load all existing projects:

```bash
# Show current stats (read-only)
docker compose -p arseniyu-dashboard exec -T backend \
  python /app/backend/scripts/migrate_projects_to_registry.py --stats-only

# Actually perform migration
docker compose -p arseniyu-dashboard exec -T backend \
  python /app/backend/scripts/migrate_projects_to_registry.py
```

Expected output:
```
============================================================
🔄 Projects Registry Migration
============================================================

1️⃣  Ensuring projects registry schema...
   ✅ Done

2️⃣  Current registry stats:
   Total projects: 0
   Active projects: 0

3️⃣  Migrating competitor_analysis projects...
   ✅ 24 projects processed

4️⃣  Final registry stats:
   Total projects: 24
   Active projects: 18
   - ru: 12
   - en: 12

============================================================
✅ Migration complete!
============================================================
```

### 2. Verify Setup

```sql
-- Check if migration worked
docker compose -p arseniyu-dashboard exec -T db psql -U postgres -d trendvi -c \
  "SELECT COUNT(*) as total_projects, COUNT(CASE WHEN is_active THEN 1 END) as active FROM global_projects_registry;"

-- Check projects by language
docker compose -p arseniyu-dashboard exec -T db psql -U postgres -d trendvi -c \
  "SELECT language, COUNT(*) as count FROM global_projects_registry GROUP BY language;"

-- Check project with most channels
docker compose -p arseniyu-dashboard exec -T db psql -U postgres -d trendvi -c \
  "SELECT name, language, channel_count FROM global_projects_registry ORDER BY channel_count DESC LIMIT 5;"
```

## Daily Operations

### Automatic Population

After setup, **every collector run automatically adds/updates the project in registry**:

1. User creates a competitor analysis in their dashboard
2. User starts a collector run (via API or dashboard)  
3. **Immediately** in `Orchestrator.start_run()`:
   - Fetch project metadata from `competitor_analysis`
   - Call `add_or_update_project_in_registry()` with project info
   - Call `link_project_channels()` to sync channel count
4. Project is now in global registry for background workers

### Monitoring

Check registry health:

```python
# Quick stats
from collector.projects_registry import get_registry_stats
stats = await get_registry_stats()
print(f"Total projects: {stats['total_projects']}")
print(f"Active: {stats['active_projects']}")
```

Or via database:

```sql
SELECT 
    COUNT(*) as total_projects,
    COUNT(CASE WHEN is_active THEN 1 END) as active,
    language,
    AVG(channel_count) as avg_channels
FROM global_projects_registry
GROUP BY language;
```

## Future: Background Worker Automation

Once registry is stable, background agents can:

```python
# Example future implementation
from collector.projects_registry import get_registry_stats
from collector.orchestrator import Orchestrator

# Query registry for active projects
registry = await get_registry_stats()

# Pick popular projects to re-scan
projects = await get_active_projects_for_rerun(language="ru")

# Spawn background collection runs
for project in projects:
    orch = Orchestrator()
    await orch.start_run(
        analysis_id=project["analysis_id"],
        owner_id=project["owner_id"],
        channel_inputs=[],  # Use existing channels from project
    )
```

## Files

- **Registry operations**: [backend/collector/projects_registry.py](backend/collector/projects_registry.py)
- **Migration script**: [backend/scripts/migrate_projects_to_registry.py](backend/scripts/migrate_projects_to_registry.py)
- **Migration SQL**: [migrations/add_global_projects_registry.sql](migrations/add_global_projects_registry.sql)
- **Collector integration**: [backend/collector/orchestrator.py](backend/collector/orchestrator.py)

## Related Systems

- **Global Channel Catalog**: [GLOBAL_CHANNEL_CATALOG.md](GLOBAL_CHANNEL_CATALOG.md) — Companion system for channel-level registry
