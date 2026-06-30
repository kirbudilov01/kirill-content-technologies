# want2view API Future Integration

This folder describes the expected future role of `want2view.com` in the content system.

want2view should become the video trend and performance intelligence layer.

## Role In Pipeline

```text
want2view API
  -> trending videos
  -> hook patterns
  -> competitor velocity
  -> topic demand
  -> published performance history
  -> daily content radar
```

## Expected Endpoints

These endpoints are placeholders. Final naming can change when the service API is ready.

### `GET /api/v1/trends/videos`

Returns videos currently gaining traction.

Expected fields:

- `id`
- `platform`
- `url`
- `title`
- `creator`
- `published_at`
- `views`
- `views_velocity_24h`
- `likes`
- `comments`
- `shares`
- `duration_seconds`
- `language`
- `niche`
- `format`
- `hook_text`
- `topic_tags`
- `why_it_works`

### `GET /api/v1/trends/topics`

Returns rising topics.

Expected fields:

- `topic`
- `niche`
- `platforms`
- `trend_score`
- `velocity_score`
- `competition_score`
- `evergreen_score`
- `example_videos`
- `suggested_angles`

### `GET /api/v1/accounts/performance`

Returns performance by account and platform.

Expected fields:

- `account_id`
- `platform`
- `post_id`
- `url`
- `published_at`
- `content_type`
- `topic`
- `hook`
- `views`
- `watch_time`
- `retention`
- `likes`
- `comments`
- `shares`
- `saves`
- `followers_delta`

### `POST /api/v1/content/brief`

Optional endpoint for generating a content brief from current trends.

Input:

- `topic`
- `platforms`
- `language`
- `target_audience`
- `format`
- `constraints`

Output:

- `hook_options`
- `script_outline`
- `scene_plan`
- `caption`
- `hashtags`
- `repurpose_plan`

## Daily Use

Every day Codex should use want2view to answer:

1. What is rising now?
2. Which hooks are working?
3. Which topics match AtlasRepo/open-source proof?
4. What already worked on our accounts?
5. What should we repeat, remix, or avoid?

## Security

API keys must stay outside the repository.

Recommended local env names:

- `WANT2VIEW_API_BASE`
- `WANT2VIEW_API_KEY`

