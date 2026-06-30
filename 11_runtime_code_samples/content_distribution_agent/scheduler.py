#!/usr/bin/env python3
"""
Autonomous Content Distribution Scheduler
Runs in background, automatically publishes content to social media
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=str(env_path))
except ImportError:
    pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from content_distribution.services.autonomous_distributor import AutonomousContentDistributor
from content_distribution.services.persona_content_generator import PersonaContentGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Manages autonomous content distribution schedule."""
    
    def __init__(
        self,
        queue_dir: str = "content_queue",
        check_interval_minutes: int = 15,
    ):
        """Initialize scheduler.
        
        Args:
            queue_dir: Directory for content queue
            check_interval_minutes: How often to check for due items
        """
        self.queue_dir = queue_dir
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        
        self.distributor = AutonomousContentDistributor(queue_dir=queue_dir)
        self.generator = PersonaContentGenerator()
        
        logger.info(f"✅ Scheduler initialized (check every {check_interval_minutes} min)")
    
    def run_once(self) -> dict:
        """Run one cycle: process queue and potentially generate new content."""
        
        logger.info("🔄 Running automation cycle...")
        
        stats = {
            "timestamp": datetime.now().isoformat(),
            "published": 0,
            "queue_status": {},
        }
        
        # Process existing queue
        try:
            published = self.distributor.process_queue()
            stats["published"] = published
            logger.info(f"✅ Published {published} items")
        except Exception as e:
            logger.error(f"Failed to process queue: {e}")
        
        # Get queue status
        try:
            status = self.distributor.get_queue_status()
            stats["queue_status"] = status
            logger.info(f"📊 Queue: {status['pending']} pending, {status['published']} published")
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
        
        return stats
    
    def run_continuous(self, duration_hours: int = 24):
        """Run scheduler continuously.
        
        Args:
            duration_hours: How many hours to run (None = infinite)
        """
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours) if duration_hours else None
        
        logger.info(f"🚀 Starting continuous scheduler...")
        logger.info(f"   Running for: {duration_hours} hours" if duration_hours else "   Running indefinitely")
        
        cycle = 0
        
        try:
            while True:
                cycle += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Cycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")
                
                # Run one cycle
                stats = self.run_once()
                
                # Check if we should stop
                if end_time and datetime.now() > end_time:
                    logger.info(f"⏱️  Reached time limit, stopping scheduler")
                    break
                
                # Wait before next check
                logger.info(f"⏸️  Waiting {self.check_interval//60} minutes until next check...")
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("⏹️  Scheduler stopped by user")
        except Exception as e:
            logger.error(f"💥 Scheduler error: {e}")
            raise


def setup_automation():
    """Setup automation with initial content."""
    
    logger.info("🔧 Setting up automation...\n")
    
    distributor = AutonomousContentDistributor()
    
    # Add initial content batch
    initial_content = [
        {
            "content": "🧠 Just set up my autonomous content distribution system. Now publishing 24/7 to multiple platforms automatically! 📊",
            "platforms": ["twitter", "threads", "linkedin"],
            "priority": 9,
            "scheduled_at": datetime.now() + timedelta(minutes=5),
            "hashtags": ["automation", "contentdistribution", "ai"],
        },
        {
            "content": "Automation is the future of content strategy. Why post manually when you can go autonomous? 🤖",
            "platforms": ["twitter", "threads"],
            "priority": 7,
            "scheduled_at": datetime.now() + timedelta(hours=1),
            "hashtags": ["automation", "socialmedia", "strategy"],
        },
        {
            "content": "💡 Tips for autonomous content distribution:\n1. Know your audience\n2. Maintain consistency\n3. Track metrics\n4. Adapt based on performance",
            "platforms": ["threads", "linkedin"],
            "priority": 6,
            "scheduled_at": datetime.now() + timedelta(hours=2),
            "hashtags": ["tips", "content", "marketing"],
        },
    ]
    
    added = distributor.add_batch(initial_content)
    logger.info(f"✅ Added {added} initial content items\n")
    
    return distributor


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Autonomous content scheduler")
    parser.add_argument(
        "--mode",
        choices=["setup", "once", "continuous"],
        default="once",
        help="Run mode: setup (initial), once (single cycle), continuous (24/7)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Check interval in minutes (default 15)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=24,
        help="Duration in hours for continuous mode (default 24)"
    )
    parser.add_argument(
        "--queue-dir",
        type=str,
        default="content_queue",
        help="Queue directory path"
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info(" AUTONOMOUS CONTENT SCHEDULER")
    logger.info("="*60)
    
    # Change to AGENT directory
    agent_dir = Path("/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT")
    if agent_dir.exists():
        os.chdir(agent_dir)
    
    if args.mode == "setup":
        distributor = setup_automation()
        logger.info("✅ Automation setup complete!")
        logger.info("   Next: Run with --mode=continuous to start publishing")
    
    elif args.mode == "once":
        scheduler = AutomationScheduler(
            queue_dir=args.queue_dir,
            check_interval_minutes=args.interval,
        )
        stats = scheduler.run_once()
        logger.info(f"✅ Cycle complete: {stats['published']} published")
    
    elif args.mode == "continuous":
        scheduler = AutomationScheduler(
            queue_dir=args.queue_dir,
            check_interval_minutes=args.interval,
        )
        scheduler.run_continuous(duration_hours=args.duration)
