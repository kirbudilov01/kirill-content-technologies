# Postiz Integration Guide

## Quick Start

Postiz is now integrated into the content distribution pipeline for multi-platform publishing.

### 1. Configuration

Set your Postiz API key in environment:

```bash
export POSTIZ_API_KEY=your_postiz_api_key_here
```

Or add to `.env` file:

```
POSTIZ_API_KEY=your_postiz_api_key_here
POSTIZ_AUTO_PUBLISH=false  # Set to true for automatic publishing
```

### 2. Usage in Python Code

```python
from content_distribution.services.postiz_publisher import create_postiz_publisher

# Initialize publisher
publisher = create_postiz_publisher()

# Publish immediately
result = publisher.publish_now(
    content="Your content here",
    platforms=["twitter", "threads"],
    media_paths=["path/to/image.jpg"]
)

# Schedule for later
from datetime import datetime, timedelta
scheduled_time = datetime.now() + timedelta(hours=1)
publisher.schedule_publish(
    content="Scheduled post",
    platforms=["twitter", "threads"],
    publish_at=scheduled_time
)
```

### 3. Integration with Stream Automation

The publisher is ready to be integrated into stream processing:

```python
from content_distribution.services.postiz_publisher import PostizPublisher, PostizPublishConfig
from content_distribution.config import load_settings

settings = load_settings("config/default.yaml")
publisher = PostizPublisher(api_key=settings.postiz.api_key)

# After generating content, publish directly
config = PostizPublishConfig(
    content="Generated content",
    platforms=["twitter", "threads", "instagram"],
    media_paths=["output/shorts/clip_001.mp4"]
)
publisher.publish(config)
```

## Postiz API Reference

### Methods

- **`publish(config, platforms)`** — Publish content immediately
- **`publish_now(content, platforms, media_paths)`** — Convenience method for immediate publishing
- **`schedule_publish(content, platforms, publish_at, media_paths)`** — Schedule post for future time
- **`get_post_status(post_id)`** — Check status of published post
- **`list_posts(limit, offset, status)`** — List all published posts
- **`_upload_media(media_path)`** — Upload media file

### Configuration

```python
@dataclass
class PostizPublishConfig:
    content: str                          # Post text
    media_paths: list[str] = None        # File paths to upload
    platforms: list[str] = None          # ["twitter", "threads", "instagram", etc]
    scheduled_at: datetime = None        # Schedule for future
    tags: list[str] = None               # Post tags
    cta_text: str = None                 # Call-to-action text
    cta_link: str = None                 # CTA link
```

## Platform Support

- Twitter/X
- Threads
- Instagram
- LinkedIn
- TikTok
- Facebook
- YouTube Shorts
- (See Postiz docs for full list)

## Next Steps

1. Get your Postiz API key from https://postiz.com
2. Set `POSTIZ_API_KEY` environment variable
3. Test with `publish_now()` method
4. Integrate into pipeline for automatic publishing after content generation
5. Monitor posts via `get_post_status()` and analytics

## Error Handling

```python
try:
    result = publisher.publish_now(
        content="Test post",
        platforms=["twitter"]
    )
except requests.RequestException as e:
    print(f"API request failed: {e}")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Troubleshooting

- **"API key not configured"** — Set POSTIZ_API_KEY env var
- **Media upload fails** — Check file exists and is readable
- **API timeout** — Postiz may be slow, increase timeout or retry
- **Platform not supported** — Check platform name in Postiz docs

---

For more info: https://postiz.com/docs
