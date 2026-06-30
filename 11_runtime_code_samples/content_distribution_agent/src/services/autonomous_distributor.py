"""
Autonomous Content Distribution Pipeline
Fully automated publishing to multiple platforms based on personal brand
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContentQueue:
    """Queue item for autonomous publishing."""
    
    content: str
    platforms: list[str]
    scheduled_at: datetime
    priority: int = 5  # 1-10, higher = more important
    persona_style: str = "default"  # Which persona variant to use
    hashtags: Optional[list[str]] = None
    media_paths: Optional[list[str]] = None
    is_published: bool = False
    post_id: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AutonomousContentDistributor:
    """Manages autonomous content distribution across platforms."""
    
    def __init__(
        self,
        queue_dir: str = "content_queue",
        postiz_api_key: Optional[str] = None,
    ):
        """Initialize autonomous distributor.
        
        Args:
            queue_dir: Directory to store content queue
            postiz_api_key: Postiz API key for publishing
        """
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
        
        self.postiz_api_key = postiz_api_key or os.getenv("POSTIZ_API_KEY")
        self.queue_file = self.queue_dir / "queue.json"
        self.published_log = self.queue_dir / "published.json"
        
        # Load existing queue
        self.queue: list[ContentQueue] = self._load_queue()
        
        # Initialize Postiz publisher
        self._init_publisher()
    
    def _init_publisher(self):
        """Initialize Postiz publisher."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from services.postiz_publisher import create_postiz_publisher
            self.publisher = create_postiz_publisher(api_key=self.postiz_api_key)
            logger.info("✅ Postiz publisher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Postiz: {e}")
            self.publisher = None
    
    def schedule_content(
        self,
        content: str,
        platforms: list[str],
        schedule_minutes: int = 60,
        priority: int = 5,
        hashtags: Optional[list[str]] = None,
    ) -> ContentQueue:
        """Schedule content for autonomous publishing.
        
        Args:
            content: Post content
            platforms: List of platforms
            schedule_minutes: Minutes until publish (default 1 hour)
            priority: 1-10 priority level
            hashtags: Optional hashtags to add
            
        Returns:
            ContentQueue item
        """
        scheduled_at = datetime.now() + timedelta(minutes=schedule_minutes)
        
        item = ContentQueue(
            content=content,
            platforms=platforms,
            scheduled_at=scheduled_at,
            priority=priority,
            hashtags=hashtags,
        )
        
        self.queue.append(item)
        self._save_queue()
        
        logger.info(f"📝 Scheduled content: {len(self.queue)} items in queue")
        return item
    
    def process_queue(self) -> int:
        """Process all due items in queue and publish.
        
        Returns:
            Number of items published
        """
        if not self.publisher:
            logger.warning("Postiz not configured, skipping publish")
            return 0
        
        now = datetime.now()
        published_count = 0
        
        # Process items sorted by priority and schedule
        for item in sorted(self.queue, key=lambda x: (-x.priority, x.scheduled_at)):
            if item.is_published:
                continue
            
            if item.scheduled_at > now:
                continue
            
            # Try to publish
            try:
                # Add hashtags to content if provided
                content = item.content
                if item.hashtags:
                    content += "\n\n" + " ".join(f"#{tag}" for tag in item.hashtags)
                
                result = self.publisher.publish_now(
                    content=content,
                    platforms=item.platforms,
                    media_paths=item.media_paths,
                )
                
                # Mark as published
                item.is_published = True
                item.post_id = result.get("id")
                published_count += 1
                
                logger.info(f"✅ Published: {item.post_id}")
                
            except Exception as e:
                logger.error(f"Failed to publish: {e}")
                # Keep in queue for retry
                continue
        
        self._save_queue()
        return published_count
    
    def add_batch(self, items: list[dict]) -> int:
        """Add multiple content items to queue.
        
        Args:
            items: List of dicts with content/platforms/etc
            
        Returns:
            Number of items added
        """
        added = 0
        for item_dict in items:
            try:
                item = ContentQueue(
                    content=item_dict["content"],
                    platforms=item_dict.get("platforms", ["twitter", "threads"]),
                    scheduled_at=item_dict.get(
                        "scheduled_at",
                        datetime.now() + timedelta(hours=1)
                    ),
                    priority=item_dict.get("priority", 5),
                    hashtags=item_dict.get("hashtags"),
                )
                self.queue.append(item)
                added += 1
            except Exception as e:
                logger.error(f"Failed to add item: {e}")
        
        self._save_queue()
        return added
    
    def get_queue_status(self) -> dict:
        """Get queue statistics."""
        pending = sum(1 for item in self.queue if not item.is_published)
        published = sum(1 for item in self.queue if item.is_published)
        
        return {
            "total_items": len(self.queue),
            "pending": pending,
            "published": published,
            "next_publish": min(
                (item.scheduled_at for item in self.queue if not item.is_published),
                default=None
            ),
        }
    
    def _load_queue(self) -> list[ContentQueue]:
        """Load queue from file."""
        if not self.queue_file.exists():
            return []
        
        try:
            with open(self.queue_file) as f:
                data = json.load(f)
            
            items = []
            for item_dict in data:
                item = ContentQueue(
                    content=item_dict["content"],
                    platforms=item_dict["platforms"],
                    scheduled_at=datetime.fromisoformat(item_dict["scheduled_at"]),
                    priority=item_dict.get("priority", 5),
                    persona_style=item_dict.get("persona_style", "default"),
                    hashtags=item_dict.get("hashtags"),
                    media_paths=item_dict.get("media_paths"),
                    is_published=item_dict.get("is_published", False),
                    post_id=item_dict.get("post_id"),
                    created_at=datetime.fromisoformat(item_dict.get("created_at", datetime.now().isoformat())),
                )
                items.append(item)
            
            return items
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            return []
    
    def _save_queue(self):
        """Save queue to file."""
        try:
            data = []
            for item in self.queue:
                data.append({
                    "content": item.content,
                    "platforms": item.platforms,
                    "scheduled_at": item.scheduled_at.isoformat(),
                    "priority": item.priority,
                    "persona_style": item.persona_style,
                    "hashtags": item.hashtags,
                    "media_paths": item.media_paths,
                    "is_published": item.is_published,
                    "post_id": item.post_id,
                    "created_at": item.created_at.isoformat(),
                })
            
            with open(self.queue_file, "w") as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")


def main():
    """Example: Autonomous content distribution."""
    
    logging.basicConfig(level=logging.INFO)
    
    # Initialize distributor
    distributor = AutonomousContentDistributor(
        queue_dir="/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT/content_queue",
        postiz_api_key=os.getenv("POSTIZ_API_KEY"),
    )
    
    # Schedule some content
    print("📝 Scheduling content...\n")
    
    content_batch = [
        {
            "content": "🧠 AI is changing how we work. What's your biggest challenge with automation?",
            "platforms": ["twitter", "threads"],
            "priority": 8,
            "scheduled_at": datetime.now() + timedelta(minutes=5),
            "hashtags": ["ai", "automation", "future"],
        },
        {
            "content": "Just launched my new content distribution system. It's fully automated and runs 24/7 📊",
            "platforms": ["twitter", "threads", "linkedin"],
            "priority": 9,
            "scheduled_at": datetime.now() + timedelta(minutes=15),
            "hashtags": ["contentdistribution", "automation"],
        },
        {
            "content": "Pro tip: Automate your social media strategy using your personal brand. Save hours every week ⏰",
            "platforms": ["threads", "instagram"],
            "priority": 6,
            "scheduled_at": datetime.now() + timedelta(hours=1),
            "hashtags": ["socialmedia", "tips", "productivity"],
        },
    ]
    
    added = distributor.add_batch(content_batch)
    print(f"✅ Added {added} items to queue\n")
    
    # Show queue status
    status = distributor.get_queue_status()
    print("📊 Queue Status:")
    print(f"   Total items: {status['total_items']}")
    print(f"   Pending: {status['pending']}")
    print(f"   Published: {status['published']}")
    print(f"   Next publish: {status['next_publish']}\n")
    
    # Process queue
    print("📤 Processing queue...")
    published = distributor.process_queue()
    print(f"✅ Published {published} items\n")
    
    # Show final status
    status = distributor.get_queue_status()
    print("📊 Final Queue Status:")
    print(f"   Total items: {status['total_items']}")
    print(f"   Pending: {status['pending']}")
    print(f"   Published: {status['published']}\n")


if __name__ == "__main__":
    main()
