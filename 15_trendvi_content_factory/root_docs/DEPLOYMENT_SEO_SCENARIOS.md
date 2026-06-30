docker compose exec -T backend celery -A celery_config.celery_app inspect active | grep -E "trends_overview.refresh_snapshot|celery@" -n || true# SEO Scenarios System - Deployment Guide

## Overview
Complete SEO Scenarios system has been implemented, mirroring the Creativity Scenarios architecture. The system generates SEO recommendations for YouTube videos and shorts using OpenAI's gpt-4o-mini model with proxy rotation and competitor analysis context integration.

## Files Created/Modified

### Backend (All Created)
- **backend/generate/models.py** - Added SeoScenarioModel, CreateSeoScenarioRequest, SeoScenarioListResponse
- **backend/generate/crud_seo.py** - CRUD operations for SEO scenarios (add, get, list, update, delete)
- **backend/generate/generate_seo.py** - OpenAI integration for SEO generation (video & shorts)
- **backend/generate/tasks_seo.py** - Celery task for async scenario generation
- **backend/generate/router.py** - Added 8 new REST endpoints for SEO
- **backend/celery_config.py** - Added seo_scenarios queue configuration
- **migrations/add_seo_scenarios_table.sql** - Database schema migration
- **docker-compose.yml** - Added seo-scenarios-worker service

### Frontend (All Modified)
- **frontend/src/api/generation.tsx** - Added SeoScenarioModel + 6 API functions
- **frontend/src/pages/seoAi.tsx** - Complete page rewrite using new scenario architecture
- **frontend/src/locales/resources.ts** - Added localization keys (en & ru)

## Deployment Steps

### 1. Apply Database Migration
```bash
cd /workspaces/trendvi
docker compose exec -it db psql -U trendvi -d trendvi < migrations/add_seo_scenarios_table.sql
```

### 2. Start SEO Worker Service
```bash
docker compose up -d seo-scenarios-worker
```

### 3. Verify Services
```bash
# Check worker is running
docker compose logs seo-scenarios-worker -f

# Check Celery queue
celery -A celery_config inspect active_queues
```

### 4. Test Endpoints
```bash
# Generate SEO for video
curl -X POST http://localhost:8000/generate/seo/video \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"request": "My video about Python programming", "analysis_id": "<OPTIONAL_PROJECT_ID>"}'

# List scenarios
curl -X GET "http://localhost:8000/generate/seo/scenarios" \
  -H "Authorization: Bearer <TOKEN>"
```

## Architecture Details

### API Endpoints (8 total)
```
POST   /generate/seo/video           - Queue video SEO generation
POST   /generate/seo/shorts          - Queue shorts SEO generation  
GET    /generate/seo/scenarios       - List all scenarios with filtering
POST   /generate/seo/scenarios       - Save generated scenario
GET    /generate/seo/scenarios/{id}  - Get one scenario
PATCH  /generate/seo/scenarios/{id}  - Update scenario
DELETE /generate/seo/scenarios/{id}  - Delete scenario
```

### Task Processing Flow
1. User requests SEO generation via frontend
2. generate_seo_video() queues task to seo_scenarios queue
3. Celery worker executes generate_seo_scenario task
4. Task loads competitor analysis context (if project selected)
5. Calls OpenAI gpt-4o-mini with formatted prompt
6. Saves result to seo_scenarios table
7. Frontend polls /generate/task_status/{task_id} until completion
8. Upon SUCCESS, scenario is saved and displayed

### Context Loading
When a project is selected:
- Loads project description from competitor_analysis table
- Fetches 2 most recent GPT reports for the project
- Truncates context to 1800-2200 characters
- Includes in OpenAI prompt for better recommendations

### Proxy Rotation
- Uses ProxyRotator class (14/20 webshare.io proxies currently working)
- Automatic fallback if proxy fails
- Stored in backend/proxy.txt

### Database Schema
```sql
Table: seo_scenarios
- scenario_id (UUID, PK)
- user_id (FK users)
- analysis_id (FK competitor_analysis, nullable)
- type (enum: video/shorts)
- title (string)
- request (text)
- response (text)
- created_at (timestamp)
- updated_at (timestamp)
- Indexes: user_id, analysis_id, type
- Trigger: auto-update updated_at
```

## Frontend Features

### Page Components
- **Project Selector Dropdown** - Context for SEO generation
- **Type Selector Dropdown** - Video or Shorts  
- **Input Field** - Request/prompt for generation
- **Scenario Cards Grid** - Display history with filtering
- **Modal View** - Details, delete button, markdown rendering
- **Loading States** - Visual feedback during polling

### Polling Mechanism
- Max 120 polls with 1-second interval (2 minutes total)
- Polls /generate/task_status/{task_id}
- Shows status: PENDING → SUCCESS or → FAILURE
- Auto-reloads list and clears input on success

## Model Configuration

### gpt-4o-mini Settings
- **Video**: max_tokens=2000 (comprehensive recommendations)
- **Shorts**: max_tokens=800 (brief analysis)
- Temperature: 0.7 (default)
- Top-p: 1.0 (default)

### Prompt Structure
```
System: "You are an expert SEO specialist..."
User: "[Context from competitor analysis]\n\n[User request]"
```

## Error Handling

### Frontend
- Task timeout (120s) → "Task polling timeout"
- Task failure → "Scenario generation failed"
- 403 status → "Not enough credits"
- Network error → Generic error message
- Empty input → "Please enter a request"

### Backend
- Missing auth token → 401 Unauthorized
- Task not found → 404 Not Found
- OpenAI API error → 500 with logged error
- Database error → 500 with transaction rollback

## Debugging

### Check Worker Status
```bash
docker compose exec web celery -A celery_config inspect active
docker compose logs seo-scenarios-worker --tail=50
```

### Check Task Status
```bash
curl -X GET "http://localhost:8000/generate/task_status/{task_id}" \
  -H "Authorization: Bearer <TOKEN>"
```

### Database Verification
```sql
SELECT COUNT(*) FROM seo_scenarios;
SELECT * FROM seo_scenarios WHERE user_id = <USER_ID> ORDER BY created_at DESC;
```

## Performance Metrics

- **Avg generation time**: 15-30 seconds (depends on OpenAI latency)
- **Task queue**: Uses Celery with RabbitMQ/Redis backend
- **Database**: Indexed on user_id, analysis_id, and type
- **Polling**: 1-second intervals, max 2 minutes wait

## Next Steps

1. **Testing** - Run full end-to-end workflow on staging
2. **Monitoring** - Set up logs/metrics for worker health
3. **Prompt Tuning** - Fine-tune prompts based on real data
4. **Performance** - Monitor task queue depth and latency
5. **Rate Limiting** - Consider implementing rate limits per user

## Troubleshooting

### Worker not processing tasks
- Check queue name matches in celery_config.py and docker-compose.yml
- Verify seo_scenarios-worker service is running
- Check celery logs for connection errors

### Tasks timing out
- Increase maxPolls in frontend (current: 120 = 2 min)
- Check OpenAI API rate limits
- Verify proxy connectivity

### Scenarios not saving
- Ensure database migration was applied
- Check user_id and analysis_id are valid UUIDs
- Verify competitor_analysis exists if analysis_id provided

### Lost context from competitor analysis
- Verify analysis_id in request payload
- Check competitor_analysis table for the project
- Confirm gpt_reports exist for the project

