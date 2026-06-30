"""Postiz API integration for publishing content to multiple platforms."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


@dataclass
class PostizPublishConfig:
    """Configuration for a single publish request."""
    content: str
    media_paths: Optional[list[str]] = None  # List of file paths to upload
    platforms: Optional[list[str]] = None  # ["twitter", "threads", "instagram", etc]
    scheduled_at: Optional[datetime] = None  # Schedule for future publishing
    tags: Optional[list[str]] = None
    cta_text: Optional[str] = None  # Call-to-action text
    cta_link: Optional[str] = None  # CTA link (for some platforms)


class PostizPublisher:
    """Client for Postiz API - manages multi-platform content publishing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: str = "https://api.postiz.com",
    ):
        """Initialize Postiz publisher.
        
        Args:
            api_key: Postiz API key. If None, tries env var POSTIZ_API_KEY.
            api_base_url: Postiz API base URL.
        """
        self.api_key = api_key or os.getenv("POSTIZ_API_KEY")
        self.api_base_url = api_base_url.rstrip("/")
        self.session = requests.Session()

        if not self.api_key:
            logger.warning(
                "Postiz API key not configured. "
                "Set POSTIZ_API_KEY env var or pass api_key parameter."
            )

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def publish(
        self,
        config: PostizPublishConfig,
        platforms: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Publish content to Postiz.

        Args:
            config: PostizPublishConfig with content and options.
            platforms: Override platforms list if needed.

        Returns:
            Response from Postiz API with post IDs and status.

        Raises:
            requests.RequestException: If API request fails.
            ValueError: If configuration is invalid.
        """
        if not self.api_key:
            raise ValueError(
                "Postiz API key not configured. "
                "Set POSTIZ_API_KEY env var or pass api_key to __init__."
            )

        platforms = platforms or config.platforms or ["twitter", "threads"]

        # Build request payload
        payload = {
            "content": config.content,
            "platforms": platforms,
        }

        if config.scheduled_at:
            payload["scheduledAt"] = config.scheduled_at.isoformat()

        if config.tags:
            payload["tags"] = config.tags

        if config.cta_text:
            payload["cta"] = {
                "text": config.cta_text,
                "link": config.cta_link or "",
            }

        # Handle media uploads
        if config.media_paths:
            media_ids = []
            for media_path in config.media_paths:
                media_id = self._upload_media(media_path)
                if media_id:
                    media_ids.append(media_id)

            if media_ids:
                payload["mediaIds"] = media_ids

        # Send publish request - Try multiple endpoints and auth methods
        endpoints = [
            "/posts",           # Main endpoint
            "/api/posts",       # Legacy endpoint
            "/api/v1/posts",    # V1 endpoint
        ]
        
        headers = self._build_headers()

        logger.info(f"Publishing to Postiz: platforms={platforms}, content_len={len(config.content)}")

        # Try each endpoint
        for endpoint in endpoints:
            url = urljoin(self.api_base_url, endpoint)
            logger.debug(f"Trying endpoint: {url}")
            
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=30)
                
                if response.status_code == 404:
                    logger.debug(f"Endpoint {endpoint} not found, trying next...")
                    continue
                elif response.status_code == 401:
                    logger.debug(f"Endpoint {endpoint} auth failed, trying next...")
                    continue
                    
                response.raise_for_status()
                result = response.json()
                logger.info(f"Published successfully to {endpoint}: {result.get('id', 'unknown')}")
                return result
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"Error with {endpoint}: {e}")
                continue
        
        # If all endpoints failed, raise error
        raise requests.RequestException(
            f"Failed to publish to any Postiz endpoint. "
            f"Tried: {', '.join(endpoints)}. "
            f"Last error: {response.status_code} from {url}"
        )

    def _upload_media(self, media_path: str) -> Optional[str]:
        """Upload media file to Postiz.

        Args:
            media_path: Path to media file.

        Returns:
            Media ID from Postiz or None if upload failed.
        """
        path = Path(media_path)
        if not path.exists():
            logger.warning(f"Media file not found: {media_path}")
            return None

        try:
            url = urljoin(self.api_base_url, "/api/media/upload")
            headers = self._build_headers()
            # Remove Content-Type for multipart form
            headers.pop("Content-Type", None)

            with open(path, "rb") as f:
                files = {"file": (path.name, f)}
                response = self.session.post(
                    url, files=files, headers=headers, timeout=60
                )
                response.raise_for_status()

            result = response.json()
            media_id = result.get("id")
            logger.info(f"Uploaded media: {path.name} → {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Media upload failed for {media_path}: {e}")
            return None

    def schedule_publish(
        self,
        content: str,
        platforms: list[str],
        publish_at: datetime,
        media_paths: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Schedule content for future publishing.

        Args:
            content: Content text.
            platforms: List of platforms.
            publish_at: When to publish.
            media_paths: Optional media files.

        Returns:
            Scheduled post response from API.
        """
        config = PostizPublishConfig(
            content=content,
            platforms=platforms,
            media_paths=media_paths,
            scheduled_at=publish_at,
        )
        return self.publish(config)

    def publish_now(
        self,
        content: str,
        platforms: Optional[list[str]] = None,
        media_paths: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Publish content immediately.

        Args:
            content: Content text.
            platforms: List of platforms (default: ["twitter", "threads"]).
            media_paths: Optional media files.

        Returns:
            Published post response from API.
        """
        config = PostizPublishConfig(
            content=content,
            platforms=platforms,
            media_paths=media_paths,
        )
        return self.publish(config)

    def get_post_status(self, post_id: str) -> dict[str, Any]:
        """Get status of published post.

        Args:
            post_id: Postiz post ID.

        Returns:
            Post status and metadata.

        Raises:
            requests.RequestException: If API request fails.
        """
        url = urljoin(self.api_base_url, f"/api/posts/{post_id}")
        headers = self._build_headers()

        response = self.session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        return response.json()

    def list_posts(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        """List published posts.

        Args:
            limit: Number of posts to return.
            offset: Pagination offset.
            status: Filter by status (published, scheduled, draft).

        Returns:
            List of posts with metadata.

        Raises:
            requests.RequestException: If API request fails.
        """
        url = urljoin(self.api_base_url, "/api/posts")
        headers = self._build_headers()
        params = {
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status

        response = self.session.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        return response.json()


def create_postiz_publisher(api_key: Optional[str] = None) -> PostizPublisher:
    """Factory function to create PostizPublisher instance.

    Args:
        api_key: Optional API key override.

    Returns:
        Configured PostizPublisher instance.
    """
    return PostizPublisher(api_key=api_key)
