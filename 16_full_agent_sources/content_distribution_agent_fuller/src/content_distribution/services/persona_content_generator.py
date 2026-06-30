"""
Content Generator - Creates posts based on personal brand/persona
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PersonaContentGenerator:
    """Generates content based on personal brand/persona from about3.md"""
    
    def __init__(self, persona_file: str = "../ABOUT ME /about3.md"):
        """Initialize generator with persona file.
        
        Args:
            persona_file: Path to about3.md or similar persona file
        """
        self.persona_file = Path(persona_file)
        self.persona_text = self._load_persona()
        self.lm_client = self._init_lm()
    
    def _load_persona(self) -> str:
        """Load persona from file."""
        try:
            with open(self.persona_file, encoding="utf-8") as f:
                content = f.read()
            logger.info(f"✅ Loaded persona: {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"Failed to load persona: {e}")
            return ""
    
    def _init_lm(self):
        """Initialize LLM client (GitHub Models)."""
        try:
            import anthropic
            
            api_key = os.getenv("GITHUB_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("No LLM API key found")
                return None
            
            # Use GitHub Models
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url="https://models.inference.ai.azure.com",
            )
            logger.info("✅ LLM client initialized")
            return client
        except Exception as e:
            logger.warning(f"LLM not available: {e}")
            return None
    
    def generate_posts(
        self,
        topic: str,
        count: int = 3,
        platforms: Optional[list[str]] = None,
    ) -> list[dict]:
        """Generate content posts based on persona and topic.
        
        Args:
            topic: Topic or theme for posts
            count: Number of posts to generate
            platforms: Target platforms (affects format/length)
            
        Returns:
            List of generated posts with content and metadata
        """
        if not self.lm_client:
            logger.warning("LLM not configured")
            return self._generate_fallback_posts(topic, count, platforms)
        
        posts = []
        
        try:
            prompt = f"""Based on this personal brand profile:

{self.persona_text[:2000]}  # Use first 2000 chars to stay within limits

Generate {count} social media posts about: {topic}

Requirements:
- Write in the person's authentic voice and style
- Each post should be unique and engaging
- Include relevant hashtags
- Format: For Threads/Twitter posts, keep under 280 chars per tweet
- Make them shareable and thought-provoking
- Focus on value and insights

Return JSON array with posts. Each post should have:
{{
  "content": "post text",
  "platforms": ["twitter", "threads"],  // which platforms this fits best
  "hashtags": ["tag1", "tag2"],
  "style": "informative|story|question|tip|announcement"
}}

Output ONLY valid JSON array, no other text."""
            
            message = self.lm_client.messages.create(
                model="gpt-4o",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            response_text = message.content[0].text
            
            # Try to extract JSON
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "[" in response_text:
                json_str = response_text[response_text.find("["):response_text.rfind("]")+1]
            else:
                json_str = response_text
            
            posts = json.loads(json_str)
            logger.info(f"✅ Generated {len(posts)} posts")
            
            return posts
        
        except Exception as e:
            logger.error(f"Failed to generate with LLM: {e}")
            return self._generate_fallback_posts(topic, count, platforms)
    
    def _generate_fallback_posts(
        self,
        topic: str,
        count: int = 3,
        platforms: Optional[list[str]] = None,
    ) -> list[dict]:
        """Generate simple fallback posts without LLM."""
        
        templates = [
            {
                "content": f"🚀 Exploring {topic}. What's your biggest challenge here?",
                "style": "question",
            },
            {
                "content": f"Just learned something new about {topic}. Here's what stood out:\n• Key insight 1\n• Key insight 2\n• Key insight 3",
                "style": "informative",
            },
            {
                "content": f"The future of {topic} is here. How are you adapting? 🔮",
                "style": "story",
            },
            {
                "content": f"💡 Pro tip for {topic}: Focus on what matters most.",
                "style": "tip",
            },
        ]
        
        posts = []
        for i in range(min(count, len(templates))):
            template = templates[i % len(templates)]
            posts.append({
                "content": template["content"],
                "platforms": platforms or ["twitter", "threads"],
                "hashtags": [topic.lower().replace(" ", "")],
                "style": template["style"],
            })
        
        return posts


def main():
    """Example: Generate content based on persona."""
    
    logging.basicConfig(level=logging.INFO)
    
    # Initialize generator
    generator = PersonaContentGenerator(
        persona_file="/Users/kirill/Desktop/CONTENT DISTRIBUTION/ABOUT ME /about3.md"
    )
    
    # Generate posts
    print("📝 Generating content...\n")
    
    topics = [
        "AI and automation",
        "content distribution strategy",
        "personal branding",
    ]
    
    for topic in topics:
        print(f"Topic: {topic}")
        posts = generator.generate_posts(topic, count=2)
        
        for i, post in enumerate(posts, 1):
            print(f"\n  Post {i}:")
            print(f"    Content: {post['content'][:60]}...")
            print(f"    Platforms: {post['platforms']}")
            print(f"    Style: {post['style']}")
        
        print()


if __name__ == "__main__":
    main()
