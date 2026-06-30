"""Postiz action tool for Hermes Agent.

This tool enables Hermes agents to publish content through Postiz
to Twitter, Threads, Instagram, and other platforms.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# This would be added to hermes-agent/tools/ or similar
# For now, it serves as a reference implementation

logger = logging.getLogger(__name__)


class PostizAction:
    """Hermes-compatible action for Postiz publishing."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Postiz action.
        
        Args:
            api_key: Postiz API key (uses env if not provided)
        """
        try:
            from content_distribution.services.postiz_publisher import (
                create_postiz_publisher,
            )

            self.publisher = create_postiz_publisher(api_key=api_key)
            self.enabled = True
        except ImportError:
            logger.warning("Postiz publisher not available")
            self.enabled = False

    def publish_now(
        self,
        content: str,
        platforms: Optional[list[str]] = None,
        media_paths: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Publish content immediately to Postiz.

        Args:
            content: Post content text
            platforms: List of platforms (default: ["twitter", "threads"])
            media_paths: Optional list of file paths to upload
            tags: Optional tags to add to post

        Returns:
            Response with post ID and status
        """
        if not self.enabled:
            return {"error": "Postiz publisher not configured"}

        try:
            result = self.publisher.publish_now(
                content=content,
                platforms=platforms,
                media_paths=media_paths,
            )
            return {
                "success": True,
                "post_id": result.get("id"),
                "status": result.get("status", "published"),
                "platforms": platforms or ["twitter", "threads"],
            }
        except Exception as e:
            logger.error(f"Postiz publish failed: {e}")
            return {"success": False, "error": str(e)}

    def schedule(
        self,
        content: str,
        platforms: list[str],
        publish_in_hours: int = 1,
        media_paths: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Schedule content for publishing at a future time.

        Args:
            content: Post content
            platforms: Publishing platforms
            publish_in_hours: Hours to delay before publishing
            media_paths: Optional media files

        Returns:
            Response with scheduled post ID
        """
        if not self.enabled:
            return {"error": "Postiz publisher not configured"}

        try:
            publish_at = datetime.now() + timedelta(hours=publish_in_hours)
            result = self.publisher.schedule_publish(
                content=content,
                platforms=platforms,
                publish_at=publish_at,
                media_paths=media_paths,
            )
            return {
                "success": True,
                "post_id": result.get("id"),
                "scheduled_for": publish_at.isoformat(),
                "platforms": platforms,
            }
        except Exception as e:
            logger.error(f"Schedule failed: {e}")
            return {"success": False, "error": str(e)}

    def list_posts(self, limit: int = 10) -> dict[str, Any]:
        """List recently published posts.

        Args:
            limit: Number of posts to retrieve

        Returns:
            List of posts with metadata
        """
        if not self.enabled:
            return {"error": "Postiz publisher not configured"}

        try:
            result = self.publisher.list_posts(limit=limit)
            return {
                "success": True,
                "posts": result.get("posts", []),
                "total": result.get("total", 0),
            }
        except Exception as e:
            logger.error(f"List posts failed: {e}")
            return {"success": False, "error": str(e)}

    def get_post_status(self, post_id: str) -> dict[str, Any]:
        """Get status and analytics of a published post.

        Args:
            post_id: Postiz post ID

        Returns:
            Post status, metrics, and metadata
        """
        if not self.enabled:
            return {"error": "Postiz publisher not configured"}

        try:
            result = self.publisher.get_post_status(post_id)
            return {
                "success": True,
                "post_id": post_id,
                "status": result.get("status"),
                "platforms": result.get("platforms"),
                "created_at": result.get("createdAt"),
                "metrics": result.get("metrics", {}),
            }
        except Exception as e:
            logger.error(f"Get status failed: {e}")
            return {"success": False, "error": str(e)}


# Hermes integration example:
"""
To use this in hermes-agent, add to agent/tools.py or similar:

def register_postiz_tools(agent):
    postiz = PostizAction()
    
    agent.register_tool(
        name="postiz_publish",
        description="Publish content to Twitter, Threads, Instagram, etc.",
        handler=postiz.publish_now,
        schema={
            "content": str,
            "platforms": list[str],
            "media_paths": list[str],
            "tags": list[str]
        }
    )
    
    agent.register_tool(
        name="postiz_schedule",
        description="Schedule content for future publishing",
        handler=postiz.schedule,
        schema={
            "content": str,
            "platforms": list[str],
            "publish_in_hours": int,
            "media_paths": list[str]
        }
    )
    
    return agent
"""

if __name__ == "__main__":
    # Test the action
    logging.basicConfig(level=logging.INFO)

    action = PostizAction()

    # Test publish
    result = action.publish_now(
        content="🚀 Testing Postiz integration with Hermes! #automation",
        platforms=["twitter", "threads"],
    )
    print(f"Publish result: {json.dumps(result, indent=2)}")

    # Test schedule
    scheduled = action.schedule(
        content="Scheduled from Hermes 📅",
        platforms=["twitter"],
        publish_in_hours=2,
    )
    print(f"Schedule result: {json.dumps(scheduled, indent=2)}")

    # Test list
    posts = action.list_posts(limit=5)
    print(f"Posts result: {json.dumps(posts, indent=2)}")
