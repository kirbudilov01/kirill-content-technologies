"""Example: Integrating Postiz into content pipeline.

This module shows how to integrate Postiz publishing into the main pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from content_distribution.config import Settings
from content_distribution.models.contracts import JobResult
from content_distribution.services.postiz_publisher import (
    PostizPublisher,
    PostizPublishConfig,
)

logger = logging.getLogger(__name__)


def publish_pipeline_output(
    result: JobResult,
    settings: Settings,
    title: str = "New shorts available",
    description: Optional[str] = None,
) -> dict[str, str]:
    """Publish generated shorts to Postiz after pipeline completes.

    Args:
        result: Pipeline output (clips, metadata, etc.)
        settings: Configuration with Postiz settings
        title: Post title/first line
        description: Additional description for post

    Returns:
        Dictionary with post IDs for each platform
    """
    if not settings.postiz.enabled or not settings.postiz.api_key:
        logger.warning("Postiz publishing disabled or not configured")
        return {}

    publisher = PostizPublisher(api_key=settings.postiz.api_key)
    post_results = {}

    # Example: Publish first clip from the batch
    if not result.clips:
        logger.warning("No clips generated, skipping Postiz publish")
        return {}

    first_clip = result.clips[0]
    media_path = Path(first_clip.path)

    if not media_path.exists():
        logger.error(f"Media file not found: {media_path}")
        return {}

    # Build content
    content_lines = [title]
    if description:
        content_lines.append(description)

    content = "\n".join(content_lines)
    content += f"\n\n#shorts #content #automation"

    # Publish
    try:
        config = PostizPublishConfig(
            content=content,
            media_paths=[str(media_path)],
            platforms=["twitter", "threads", "instagram"],
        )

        result_dict = publisher.publish(config)
        post_id = result_dict.get("id", "unknown")
        logger.info(f"Published to Postiz: {post_id}")

        # Store for tracking
        post_results[settings.postiz.default_platform] = post_id

        return post_results

    except Exception as e:
        logger.error(f"Postiz publish failed: {e}")
        return {}


def publish_marketing_materials(
    materials_dir: Path,
    settings: Settings,
) -> list[str]:
    """Publish generated marketing materials (images, thumbnails, etc).

    Args:
        materials_dir: Directory containing generated materials
        settings: Configuration with Postiz settings

    Returns:
        List of published post IDs
    """
    if not settings.postiz.enabled or not settings.postiz.api_key:
        logger.warning("Postiz publishing disabled")
        return []

    publisher = PostizPublisher(api_key=settings.postiz.api_key)
    published_ids = []

    # Find all media files
    for media_file in materials_dir.glob("*.[jpgpng]"):
        try:
            config = PostizPublishConfig(
                content=f"📸 New visual content\n\n#marketing #design",
                media_paths=[str(media_file)],
                platforms=["instagram", "twitter"],
            )

            result = publisher.publish(config)
            post_id = result.get("id")
            if post_id:
                published_ids.append(post_id)
                logger.info(f"Published marketing material: {post_id}")

        except Exception as e:
            logger.error(f"Failed to publish {media_file}: {e}")
            continue

    return published_ids


def publish_scheduled(
    content: str,
    platforms: list[str],
    delay_hours: int = 1,
    media_paths: Optional[list[str]] = None,
    settings: Optional[Settings] = None,
) -> Optional[str]:
    """Schedule content for publishing.

    Args:
        content: Post content text
        platforms: List of platforms (twitter, threads, instagram, etc)
        delay_hours: Hours to delay before publishing
        media_paths: Optional media files to attach
        settings: Optional Settings (uses env var if not provided)

    Returns:
        Post ID from Postiz or None if failed
    """
    from datetime import datetime, timedelta

    if settings is None:
        settings = Settings()

    if not settings.postiz.api_key:
        logger.error("Postiz API key not configured")
        return None

    publisher = PostizPublisher(api_key=settings.postiz.api_key)
    scheduled_time = datetime.now() + timedelta(hours=delay_hours)

    try:
        result = publisher.schedule_publish(
            content=content,
            platforms=platforms,
            publish_at=scheduled_time,
            media_paths=media_paths,
        )
        post_id = result.get("id")
        logger.info(f"Scheduled publish: {post_id} at {scheduled_time}")
        return post_id

    except Exception as e:
        logger.error(f"Schedule publish failed: {e}")
        return None


# Example: Use in orchestrator.py
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Load settings
    from content_distribution.config import load_settings

    settings = load_settings("config/default.yaml")

    # Example 1: Publish generated shorts
    print("Example 1: Publishing shorts...")
    # result = JobResult(...)  # After pipeline run
    # publish_pipeline_output(result, settings, title="New shorts 🎬")

    # Example 2: Schedule content for later
    print("Example 2: Scheduling post...")
    post_id = publish_scheduled(
        content="Check out our latest content! #AI #content",
        platforms=["twitter", "threads"],
        delay_hours=2,
        settings=settings,
    )
    print(f"Scheduled post ID: {post_id}")

    # Example 3: List recent posts
    print("Example 3: Listing posts...")
    if settings.postiz.api_key:
        publisher = PostizPublisher(api_key=settings.postiz.api_key)
        posts = publisher.list_posts(limit=5)
        print(f"Recent posts: {posts}")
