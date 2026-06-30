import asyncio
import csv
import os
import re
import sys

import asyncpg
from db import _get_dsn


CONFIGS = {
    "content_automation": {
        "manual": [
            ("https://www.youtube.com/@opusclip", "official_tool", 10, "AI clipping/repurposing tool for Shorts, TikTok, Reels"),
            ("https://www.youtube.com/@kapwing", "official_tool", 10, "AI video editing and repurposing workflow tool"),
            ("https://www.youtube.com/@invideoofficial", "official_tool", 10, "Prompt-to-video and AI video creation for creators"),
            ("https://www.youtube.com/@veedstudio", "official_tool", 9, "Video creation/editing tutorials for social teams"),
            ("https://www.youtube.com/@riversidefm", "official_tool", 9, "Podcast/video recording, AI editing, and distribution workflows"),
            ("https://www.youtube.com/@repurposeio", "official_tool", 9, "Automated content repurposing and cross-posting"),
            ("https://www.youtube.com/@castmagicai", "official_tool", 9, "Turns media into AI-generated content assets"),
            ("https://www.youtube.com/@zapier", "automation_platform", 9, "Workflow automation platform for content operations"),
            ("https://www.youtube.com/@n8n-io", "automation_platform", 9, "Workflow automation and AI agents for content pipelines"),
            ("https://www.youtube.com/@itsmake", "automation_platform", 9, "Visual AI automation and workflow orchestration"),
            ("https://www.youtube.com/@hootsuite", "social_scheduler", 8, "Social media management and publishing platform"),
            ("https://www.youtube.com/@latermedia", "social_scheduler", 8, "Creator/influencer marketing and social scheduling"),
            ("https://www.youtube.com/@canva", "creative_tool", 8, "Design/video creation platform for content teams"),
            ("https://www.youtube.com/@adobecreativecloud", "creative_tool", 8, "Creative suite and AI content creation ecosystem"),
            ("https://www.youtube.com/@vidiq", "creator_growth", 9, "YouTube growth and creator analytics platform"),
            ("https://www.youtube.com/@tubebuddy", "creator_growth", 9, "YouTube optimization and productivity tooling"),
            ("https://www.youtube.com/@socialblade", "creator_growth", 9, "YouTube/social data and competitor stats for creators"),
            ("https://www.youtube.com/@morningfame", "creator_growth", 9, "YouTube growth analytics and packaging education"),
            ("https://www.youtube.com/@thinkmediatv", "creator_growth", 9, "YouTube creator strategy and content business education"),
            ("https://www.youtube.com/@primalvideo", "creator_growth", 9, "Video tools, AI strategies, and creator workflow education"),
            ("https://www.youtube.com/@filmbooth", "creator_growth", 8, "YouTube packaging/content strategy for education creators"),
            ("https://www.youtube.com/@colinandsamir", "creator_growth", 8, "Creator economy and creator operations signal"),
            ("https://www.youtube.com/@channelmakers", "creator_growth", 8, "YouTube growth experiments and creator systems"),
            ("https://www.youtube.com/@nicknimmin", "creator_growth", 8, "YouTube tips, tools, and creator productivity"),
            ("https://www.youtube.com/@creatorinsider", "creator_growth", 8, "Official YouTube creator/product updates and platform insights"),
            ("https://www.youtube.com/@youtubecreators", "creator_growth", 8, "Official YouTube creator education and growth workflows"),
            ("https://www.youtube.com/@socialmediaexaminer", "marketing_ops", 8, "Social media marketing workflows and platform changes"),
            ("https://www.youtube.com/@hubspotmarketing", "marketing_ops", 8, "Marketing systems, social media, email and content operations"),
            ("https://www.youtube.com/@ahrefscom", "marketing_ops", 8, "SEO, YouTube SEO, content marketing workflows"),
            ("https://www.youtube.com/@semrush", "marketing_ops", 8, "Digital visibility and content marketing systems"),
            ("https://www.youtube.com/@moz", "marketing_ops", 8, "SEO/content analytics and inbound marketing education"),
            ("https://www.youtube.com/@backlinko", "marketing_ops", 8, "SEO and content research education"),
            ("https://www.youtube.com/@thinkwithgoogle", "marketing_ops", 8, "Consumer insight, marketing research and trend education"),
            ("https://www.youtube.com/@wistia", "official_tool", 7, "Video marketing and analytics platform"),
            ("https://www.youtube.com/@googlesearchcentral", "marketing_ops", 8, "Official search/content discovery education"),
            ("https://www.youtube.com/@searchenginejournal", "marketing_ops", 8, "Search/content marketing trend and strategy signal"),
            ("https://www.youtube.com/@cmicontent", "marketing_ops", 8, "Content marketing strategy and operations education"),
            ("https://www.youtube.com/@matgpod", "marketing_ops", 8, "Marketing trends, growth tactics and AI-era content distribution"),
            ("https://www.youtube.com/@neilpatel", "marketing_ops", 7, "Digital marketing and content distribution signal"),
            ("https://www.youtube.com/@descript", "official_tool", 9, "AI video/podcast editing and repurposing"),
            ("https://www.youtube.com/@bufferapp", "social_scheduler", 8, "Social publishing and content scheduling"),
            ("https://www.youtube.com/@metricool_en", "social_scheduler", 8, "Social media planning, analytics, and scheduling"),
            ("https://www.youtube.com/@publer", "social_scheduler", 8, "Social media scheduler and content publishing workflow"),
            ("https://www.youtube.com/@socialbeehq", "social_scheduler", 8, "Social media automation and publishing"),
            ("https://www.youtube.com/@planable", "social_scheduler", 8, "Content collaboration and social scheduling"),
            ("https://www.youtube.com/@sproutsocial", "social_scheduler", 8, "Social media management for teams"),
            ("https://www.youtube.com/@agorapulse", "social_scheduler", 8, "Social media management and publishing workflows"),
            ("https://www.youtube.com/@contentstudio", "social_scheduler", 8, "Content marketing and social media management platform"),
            ("https://www.youtube.com/@restreamio", "official_tool", 8, "Live video distribution and repurposing workflow"),
            ("https://www.youtube.com/@streamyard", "official_tool", 8, "Live/video content production workflow"),
            ("https://www.youtube.com/@goldcast-video", "official_tool", 8, "AI-powered B2B video content platform for repurposing webinars/events"),
            ("https://www.youtube.com/@heygen_official", "ai_video_tool", 8, "AI video/avatar creation for content workflows"),
            ("https://www.youtube.com/@synthesia", "ai_video_tool", 8, "AI video generation for teams and content ops"),
            ("https://www.youtube.com/@pictoryai", "ai_video_tool", 8, "AI video creation and repurposing"),
            ("https://www.youtube.com/@lumen5", "ai_video_tool", 8, "AI/social video creation platform"),
            ("https://www.youtube.com/@runwayml", "ai_video_tool", 8, "Generative AI video creation platform"),
            ("https://www.youtube.com/@elevenlabsio", "ai_video_tool", 8, "Voice/AI audio content creation platform"),
            ("https://www.youtube.com/@captionsapp", "ai_video_tool", 8, "AI video creation, editing, and social content tool"),
            ("https://www.youtube.com/@predisai", "ai_creator_workflow", 8, "AI social media content creation and scheduling"),
            ("https://www.youtube.com/@pallyy", "social_scheduler", 7, "Social media scheduling and content planning platform"),
            ("https://www.youtube.com/@sendible", "social_scheduler", 7, "Social media management and publishing workflows"),
            ("https://www.youtube.com/@planoly", "social_scheduler", 7, "Social content planner and scheduler"),
            ("https://www.youtube.com/@tailwindapp", "social_scheduler", 7, "Social content scheduling for visual creators"),
            ("https://www.youtube.com/@typefully", "social_scheduler", 7, "Writing and distribution workflow for social content"),
            ("https://www.youtube.com/@beehiiv", "newsletter_tool", 7, "Newsletter/media business publishing workflow"),
            ("https://www.youtube.com/@substackinc", "newsletter_tool", 7, "Creator publishing and newsletter distribution"),
            ("https://www.youtube.com/@creatormagicai", "ai_creator_workflow", 8, "AI tools, workflow automation, and creator productivity"),
            ("https://www.youtube.com/@sabrina_ramonov", "ai_creator_workflow", 8, "AI prompts, playbooks, agents, and creator workflows"),
            ("https://www.youtube.com/@productivedude", "ai_creator_workflow", 8, "AI productivity and content workflows"),
            ("https://www.youtube.com/@alex.followell", "ai_creator_workflow", 8, "Claude/n8n automation workflows and creator systems"),
            ("https://www.youtube.com/@nicksaraev", "ai_creator_workflow", 8, "Claude, Codex, n8n and creator-facing AI tools"),
            ("https://www.youtube.com/@nateherk", "automation_creator", 8, "Business AI automations and workflow examples"),
            ("https://www.youtube.com/@derekcheungsa", "automation_creator", 7, "AI agents automation and no-code systems"),
            ("https://www.youtube.com/@automation-tribe", "automation_creator", 7, "No-code and AI workflow automation"),
            ("https://www.youtube.com/@codewithmuh", "automation_creator", 7, "n8n and Claude automation systems"),
            ("https://www.youtube.com/@syncbricks", "automation_creator", 7, "AI automation and workflow builds"),
            ("https://www.youtube.com/@ai-gptworkshop", "ai_creator_workflow", 7, "No-code AI tools and content-adjacent agents"),
            ("https://www.youtube.com/@edhillai", "ai_creator_workflow", 7, "AI automation tutorials"),
            ("https://www.youtube.com/@benai92", "ai_creator_workflow", 7, "Practical AI tools and business workflows"),
            ("https://www.youtube.com/@mithunmohanai", "ai_creator_workflow", 7, "AI automation tutorials"),
            ("https://www.youtube.com/@aiautomationkit", "automation_creator", 7, "AI automation kits and tutorials"),
            ("https://www.youtube.com/@zero2launchai", "automation_creator", 7, "AI/no-code automation blueprints"),
            ("https://www.youtube.com/@jay.ai.automation", "automation_creator", 7, "AI automation for solopreneurs"),
            ("https://www.youtube.com/@automatewithmarc", "automation_creator", 7, "Business AI agents and automation workflows"),
            ("https://www.youtube.com/@modernmillie", "creator_growth", 8, "Creator strategy and social content workflow education"),
            ("https://www.youtube.com/@robertoblake", "creator_growth", 8, "Creator business, production systems, and channel growth"),
            ("https://www.youtube.com/@calebboxxmedia", "youtube_automation", 8, "Faceless AI YouTube channel automation market signal"),
            ("https://www.youtube.com/@ytadanny", "youtube_automation", 7, "Faceless YouTube channel systems and scaling"),
            ("https://www.youtube.com/@victorcatrina_", "youtube_automation", 7, "YouTube automation and faceless-channel operator signal"),
            ("https://www.youtube.com/@nicorojass", "youtube_automation", 7, "Faceless YouTube automation and AI-assisted scaling"),
            ("https://www.youtube.com/@tubesenseiofficial", "creator_growth", 7, "Content creation business education with AI/tools angle"),
            ("https://www.youtube.com/@stewartgauld", "marketing_ops", 7, "Small-business digital marketing and creator-tool tutorials"),
            ("https://www.youtube.com/@littlebitbetter7", "youtube_automation", 7, "Faceless educational channel operator signal"),
            ("https://www.youtube.com/@ishansharma7390", "creator_growth", 7, "Creator business, AI, and content operations signal"),
            ("https://www.youtube.com/@kevinstratvert", "tool_education", 7, "AI/productivity software tutorials relevant to creator workflows"),
            ("https://www.youtube.com/@logicallyanswered", "content_strategy", 7, "Tech/social media economics and platform pattern signal"),
            ("https://www.youtube.com/@airevolutionx", "ai_media", 7, "AI news/tools channel for content automation trend signal"),
            ("https://www.youtube.com/@thinkmediapodcast", "creator_growth", 7, "Creator business and YouTube operations conversations"),
            ("https://www.youtube.com/@zoeunlimited", "marketing_ops", 7, "Creator/marketer signal around social growth and content systems"),
            ("https://www.youtube.com/@pauljlipsky", "ai_creator_workflow", 7, "Non-technical AI workflow and business-tool education"),
            ("https://www.youtube.com/@mreflow", "ai_media", 7, "AI tools and creator workflow trend signal"),
            ("https://www.youtube.com/@futurepedia_io", "ai_media", 7, "AI tools discovery and workflow signal"),
            ("https://www.youtube.com/@skillleapai", "ai_creator_workflow", 7, "AI tools tutorials for creators and operators"),
        ],
        "positive": ["content", "creator", "shorts", "video", "repurpos", "automation", "workflow", "social media", "youtube", "faceless", "podcast", "newsletter", "postiz", "n8n", "zapier", "make"],
        "negative": ["agent 00", "movie", "music", "kids", "gaming", "roblox", "minecraft", "football", "basketball", "workout", "news channel", "industrial automation", "haas automation", "plc", "scada", "unknown", "brawl stars", "emma chamberlain", "flotrack", "lavendaire", "blush with me", "shemaroo", "goldmines", "markiplier", "kids roma", "top gear", "tonight show", "saturday night live", "netflix", "mark rober", "mr. indian hacker", "be amazed", "nilered", "fashion", "vlog", "comedy", "prank", "puzzle", "rubik", "chemistry", "cnbc", "extra history", "linus tech tips", "doctor", "toy", "cartoon", "carl faceless", "moqautomation", "warikoo", "garyvee", "self made millennial"],
    },
    "vibe_coding": {
        "manual": [
            ("https://www.youtube.com/@openai", "official_platform", 10, "Codex and AI coding platform source"),
            ("https://www.youtube.com/@anthropic-ai", "official_platform", 10, "Claude/Claude Code platform source"),
            ("https://www.youtube.com/@claude", "official_platform", 10, "Claude product channel"),
            ("https://www.youtube.com/@cursor_ai", "official_platform", 10, "Core AI coding IDE"),
            ("https://www.youtube.com/@replit", "official_platform", 10, "Replit Agent and prompt-to-app platform"),
            ("https://www.youtube.com/@lovable", "official_platform", 10, "Core vibe-coding/product builder platform"),
            ("https://www.youtube.com/@boltdotnew", "official_platform", 9, "Prompt-to-full-stack app builder"),
            ("https://www.youtube.com/@vercelhq", "official_platform", 9, "v0/Vercel AI app building ecosystem"),
            ("https://www.youtube.com/@windsurf", "official_platform", 9, "Agentic IDE platform"),
            ("https://www.youtube.com/@cline-bot", "official_platform", 9, "Autonomous coding agent in IDE"),
            ("https://www.youtube.com/@googleantigravity", "official_platform", 9, "Agentic development platform signal"),
            ("https://www.youtube.com/@bubbleio", "no_code_platform", 9, "Visual AI app builder / no-code app building"),
            ("https://www.youtube.com/@flutterflow", "no_code_platform", 9, "Visual app builder and AI app creation"),
            ("https://www.youtube.com/@airtableapp", "no_code_platform", 8, "No-code app/workflow builder platform"),
            ("https://www.youtube.com/@leonvanzyl", "creator_builder", 10, "Practical AI app/agent builds"),
            ("https://www.youtube.com/@alexfinnofficial", "creator_builder", 10, "Dedicated vibe coding, Claude Code, Codex creator"),
            ("https://www.youtube.com/@alex.followell", "creator_builder", 10, "Claude Code and AI automation builds"),
            ("https://www.youtube.com/@ai-luke", "creator_builder", 10, "Claude Code/Codex apps and automations"),
            ("https://www.youtube.com/@nicksaraev", "creator_builder", 9, "Claude Code, Codex, n8n and AI tools"),
            ("https://www.youtube.com/@avtharai", "creator_builder", 9, "AI coding tool reviews and workflows"),
            ("https://www.youtube.com/@mikeynocode", "creator_builder", 9, "No-code/AI app builder tutorials"),
            ("https://www.youtube.com/@rileybrownai", "creator_builder", 9, "AI agents and vibe-coding market signal"),
            ("https://www.youtube.com/@colemedin", "creator_builder", 9, "AI agents and coding assistants"),
            ("https://www.youtube.com/@adriantwarog", "creator_builder", 8, "AI websites/apps and app builder content"),
            ("https://www.youtube.com/@theaiuniversity", "creator_builder", 8, "AI tool tutorials with Claude/Codex coverage"),
            ("https://www.youtube.com/@openai", "official_platform", 10, "Codex and AI coding platform source"),
            ("https://www.youtube.com/@anthropic-ai", "official_platform", 10, "Claude/Claude Code platform source"),
            ("https://www.youtube.com/@warpdotdev", "official_platform", 9, "Agentic terminal/development environment"),
            ("https://www.youtube.com/@github", "official_platform", 9, "GitHub/Copilot developer platform signal"),
            ("https://www.youtube.com/@sourcegraph", "official_platform", 8, "Enterprise code assistant and agent context"),
            ("https://www.youtube.com/@continuedev", "official_platform", 8, "Open-source AI code assistant"),
            ("https://www.youtube.com/@framer", "no_code_platform", 8, "AI website/prototype builder ecosystem"),
            ("https://www.youtube.com/@webflow", "no_code_platform", 8, "No-code web app and AI website building"),
            ("https://www.youtube.com/@softr", "no_code_platform", 8, "No-code app builder for fast product assembly"),
            ("https://www.youtube.com/@glideapps", "no_code_platform", 8, "No-code app builder and AI app workflow"),
            ("https://www.youtube.com/@buildshipapp", "no_code_platform", 8, "AI backend/workflow builder for apps"),
            ("https://www.youtube.com/@createxyz", "official_platform", 8, "AI app creation from prompts"),
            ("https://www.youtube.com/@nategoldai", "creator_builder", 8, "AI app builder and prompt-to-product tutorials"),
            ("https://www.youtube.com/@mobileappmogul", "creator_builder", 8, "Mobile app and AI app-builder market signal"),
            ("https://www.youtube.com/@nocodeaibuilders", "no_code_platform", 8, "No-code AI builders and app tutorials"),
            ("https://www.youtube.com/@aioriented", "creator_builder", 8, "Codex, Claude Code, Cursor and practical AI dev"),
            ("https://www.youtube.com/@ayyaztech", "creator_builder", 8, "AI developer tools and coding workflows"),
            ("https://www.youtube.com/@codingtechnyks", "creator_builder", 8, "Agentic AI, MCP, RAG and full-stack builds"),
            ("https://www.youtube.com/@masyntech", "creator_builder", 8, "Vibe coding and AI-powered full-stack development"),
            ("https://www.youtube.com/@iamnamangupta22", "creator_builder", 8, "Vibe coding and AI software development"),
            ("https://www.youtube.com/@seanmatthewai", "creator_builder", 8, "Build apps with Claude Code, v0 and Cursor"),
            ("https://www.youtube.com/@hustlinglabs", "creator_builder", 8, "Tests Cursor, Lovable, Claude MCP and no-code tools"),
            ("https://www.youtube.com/@nicekateai", "creator_builder", 8, "AI programming, Claude Code, Codex, Cursor and agents"),
            ("https://www.youtube.com/@frontierailabs", "creator_builder", 8, "Builds products with Claude"),
            ("https://www.youtube.com/@duncanrogoff", "creator_builder", 8, "Focused Claude Code education"),
            ("https://www.youtube.com/@goose-oss", "open_source_agent", 8, "Open-source coding agent"),
            ("https://www.youtube.com/@hustlinglabs", "creator_builder", 8, "AI/no-code tool tests including Cursor, Lovable, Claude MCP"),
            ("https://www.youtube.com/@nicekateai", "creator_builder", 8, "AI programming, Claude Code, Codex, Cursor and agents"),
            ("https://www.youtube.com/@mehulmpt", "dev_influencer", 8, "Software, AI and builder audience"),
            ("https://www.youtube.com/@internetmadecoder", "dev_influencer", 8, "Coding, startups, AI and product builder audience"),
            ("https://www.youtube.com/@t3dotgg", "dev_influencer", 8, "Developer audience tracking AI coding and product shipping"),
            ("https://www.youtube.com/@seanmatthewai", "creator_builder", 8, "Build apps with Claude Code, v0, and Cursor"),
            ("https://www.youtube.com/@clouddevengineering", "agentic_dev", 8, "Agentic development, MCP and AI tooling"),
            ("https://www.youtube.com/@subhankaladi", "agentic_dev", 8, "AI agents, modern dev workflows, real-world software"),
            ("https://www.youtube.com/@thecodebear", "agentic_dev", 8, "Coding and AI/data projects"),
            ("https://www.youtube.com/@codingwithroby", "agentic_dev", 8, "AI coding and AI engineering for backend developers"),
            ("https://www.youtube.com/@arctutorials", "agentic_dev", 8, "Agentic AI architecture and LLMOps"),
            ("https://www.youtube.com/@franknillard", "agentic_dev", 8, "Agentic coding and AI product builds"),
            ("https://www.youtube.com/@programadorhumilde3", "creator_builder", 8, "Vibe coding education in Portuguese"),
            ("https://www.youtube.com/@rodrigodelatorre-ai", "creator_builder", 8, "Vibe Coding and SaaS builder education"),
            ("https://www.youtube.com/@leopereira.lovable", "no_code_platform", 7, "Lovable-focused no-code SaaS education"),
            ("https://www.youtube.com/@johnelderai", "ai_tools_signal", 7, "Claude/OpenClaw/AI tool signal"),
            ("https://www.youtube.com/@diysmartcode", "agentic_dev", 7, "AI IDEs and coding tool workflows"),
            ("https://www.youtube.com/@tommyyipxyz", "creator_builder", 7, "Claude Code + Replit client-build signal"),
            ("https://www.youtube.com/@aicoding2010", "agentic_dev", 7, "AI coding education"),
            ("https://www.youtube.com/@enterproai", "no_code_platform", 7, "No-code AI dev agent and prompt-to-dev positioning"),
            ("https://www.youtube.com/@syncbricks", "automation_builder", 7, "AI automation and practical agent builds"),
            ("https://www.youtube.com/@davidsonnocode", "automation_builder", 7, "AI automation, agents, SaaS and no-code development"),
            ("https://www.youtube.com/@flutteragentic", "agentic_dev", 7, "Flutter and AI agent coding examples"),
            ("https://www.youtube.com/@elie2222", "open_source_agent", 7, "Open-source Cursor/AI builder signal"),
            ("https://www.youtube.com/@pavanadhav", "dev_influencer", 7, "Short-form AI/dev/system design signal"),
            ("https://www.youtube.com/@codewithclinton", "agentic_dev", 7, "AI-assisted coding and full-stack development"),
            ("https://www.youtube.com/@sebastianhardyai", "automation_builder", 7, "Claude Code and AI automation workflows"),
            ("https://www.youtube.com/@tylerreedai", "creator_builder", 7, "Software engineer building with AI"),
            ("https://www.youtube.com/@markshust", "agentic_dev", 7, "Production apps with Claude Code and AI coding"),
            ("https://www.youtube.com/@videv9858", "creator_builder", 7, "Claude Code agent workflow/app-building education"),
            ("https://www.youtube.com/@jessautomates", "automation_builder", 7, "AI agents and automation education"),
            ("https://www.youtube.com/@conormartinai", "creator_builder", 7, "AI app builder and monetization signal"),
            ("https://www.youtube.com/@nateherk", "automation_builder", 7, "AI automation builder audience adjacent to vibe coding"),
            ("https://www.youtube.com/@derekcheungsa", "automation_builder", 7, "No-code AI agents and automation for builders"),
            ("https://www.youtube.com/@automation-tribe", "automation_builder", 7, "No-code AI workflow and automation blueprints"),
            ("https://www.youtube.com/@benai92", "automation_builder", 7, "Practical non-technical AI automation systems"),
            ("https://www.youtube.com/@aiautomationkit", "automation_builder", 7, "n8n, Make, Apify and AI automation builds"),
            ("https://www.youtube.com/@zero2launchai", "automation_builder", 7, "AI/no-code automation and SaaS workflow blueprints"),
            ("https://www.youtube.com/@automatewithmarc", "automation_builder", 7, "Claude Code, n8n and business AI agent workflows"),
            ("https://www.youtube.com/@devexpert_io", "creator_builder", 7, "AI for developers and real engineering workflows"),
            ("https://www.youtube.com/@bmadcode", "creator_builder", 7, "Production software leadership with Claude Code/AI coding"),
            ("https://www.youtube.com/@markshust", "creator_builder", 7, "Production apps with Claude Code and AI coding"),
            ("https://www.youtube.com/@mattpalmer", "creator_builder", 7, "Vibe coding and AI tools"),
            ("https://www.youtube.com/@aidrivencoder", "creator_builder", 7, "Turns ideas into deployed apps using AI dev tools"),
            ("https://www.youtube.com/@mikeyvibecoding", "creator_builder", 7, "Dedicated vibe-coding tutorials"),
            ("https://www.youtube.com/@enterproai", "no_code_platform", 7, "No-code AI dev agent and prompt-to-dev positioning"),
            ("https://www.youtube.com/@bravostudioapp", "no_code_platform", 7, "No-code mobile app builder signal"),
            ("https://www.youtube.com/@jwestdigital", "creator_builder", 7, "AI app and no-code business builder signal"),
            ("https://www.youtube.com/@gregisenberg", "creator_builder", 7, "AI startup/product builder audience"),
            ("https://www.youtube.com/@saasclub", "creator_builder", 7, "SaaS founder/building products audience"),
            ("https://www.youtube.com/@nocodedevs", "creator_builder", 7, "No-code and AI app builder education"),
            ("https://www.youtube.com/@coachingnocodeapps", "creator_builder", 7, "Bubble/no-code app builder education"),
            ("https://www.youtube.com/@weweb", "no_code_platform", 7, "No-code front-end web app builder"),
        ],
        "positive": ["vibe coding", "ai coding", "claude code", "codex", "cursor", "lovable", "replit", "bolt", "v0", "windsurf", "app builder", "build apps", "prompt to app", "saas", "startup", "full stack", "agentic"],
        "negative": ["music", "lyrics", "minecraft", "roblox", "gaming", "football", "fashion", "real estate", "unknown", "lovable cat", "lovable islam", "pokemon", "cocomelon", "sports cursor", "lovable reunion", "car builds", "automotive", "cad", "machining", "video editor", "de-masculinizing", "saas bahu", "tools", "workshop"],
    },
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def category_for(niche: str, text: str) -> str:
    text = text.lower()
    if niche == "content_automation":
        if any(x in text for x in ["opus", "kapwing", "veed", "invideo", "descript", "riverside", "repurpose", "castmagic"]):
            return "official_tool"
        if any(x in text for x in ["n8n", "zapier", "make", "automation"]):
            return "automation_platform"
        if any(x in text for x in ["youtube", "creator", "vidiq", "tubebuddy", "shorts"]):
            return "creator_growth"
        if any(x in text for x in ["social media", "post", "scheduler", "marketing"]):
            return "marketing_ops"
        return "content_signal"
    if any(x in text for x in ["cursor", "lovable", "replit", "bolt", "vercel", "claude", "openai", "windsurf", "cline"]):
        return "official_or_tool"
    if any(x in text for x in ["bubble", "flutterflow", "no-code", "nocode"]):
        return "no_code_platform"
    if any(x in text for x in ["app builder", "build apps", "saas", "startup", "prototype"]):
        return "app_builder"
    return "creator_builder"


def relevant(row: dict, cfg: dict) -> bool:
    title = clean(row.get("title"))
    url = clean(row.get("url"))
    if not title or title.lower() == "unknown" or not url:
        return False
    text = f"{title} {row.get('description_snippet') or ''}".lower()
    if "fabricbotecosystem" in text:
        return False
    if any(term in text for term in cfg["negative"]):
        return False
    if cfg is CONFIGS["content_automation"]:
        strong_tools = ["postiz", "opus", "vidyo", "kapwing", "invideo", "veed", "riverside", "descript", "castmagic", "repurpose.io", "buffer", "publer", "metricool", "hootsuite", "sprout social", "contentstudio", "pictory", "lumen5", "heygen", "runway", "submagic", "captions", "predis"]
        creator_ops = ["content automation", "content repurpos", "creator workflow", "content workflow", "social media automation", "youtube automation", "faceless", "shorts generator", "ai video", "ai content", "ai clips", "auto post", "autopost", "scheduler"]
        automation = ["n8n", "zapier", "make.com", "postiz", "automation", "automate", "workflow", "repurpos"]
        content_terms = ["content", "creator", "shorts", "video", "podcast", "social media", "youtube", "faceless", "reels", "tiktok"]
        return any(term in text for term in strong_tools) or (
            any(term in text for term in creator_ops)
            and any(term in text for term in automation)
            and any(term in text for term in content_terms)
        )
    tool_terms = ["claude code", "codex", "cursor", "lovable ai", "replit agent", "bolt.new", "v0", "windsurf", "cline", "mcp", "bubble", "flutterflow", "weweb", "softr", "glide"]
    build_terms = ["vibe coding", "ai coding", "app builder", "build apps", "prompt to app", "ai app", "agentic coding"]
    weak_build_terms = ["saas", "prototype", "full stack"]
    return any(term in text for term in tool_terms) or any(term in text for term in build_terms) or (
        any(term in text for term in weak_build_terms)
        and any(term in text for term in ["ai", "agent", "claude", "cursor", "codex", "lovable", "replit"])
    )


async def fetch_manual_rows(urls):
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT channel_id, title, url, subscribers, views, verified,
                   regexp_replace(coalesce(description,''), '[[:space:]]+', ' ', 'g') AS description
            FROM yt_channel_catalog
            WHERE lower(trim(trailing '/' from url)) = ANY($1::text[])
            """,
            [url.rstrip("/").lower() for url in urls],
        )
    finally:
        await conn.close()
    return {row["url"].rstrip("/").lower(): dict(row) for row in rows}


async def main():
    niche = os.environ["NICHE"]
    candidates_path = os.environ["CANDIDATES_PATH"]
    cfg = CONFIGS[niche]
    candidate_rows = list(csv.DictReader(open(candidates_path, newline="", encoding="utf-8")))
    manual_by_url = await fetch_manual_rows([url for url, _, _, _ in cfg["manual"]])

    final = []
    seen = set()
    for url, category, audit_score, reason in cfg["manual"]:
        key = url.rstrip("/").lower()
        row = manual_by_url.get(key)
        if not row or key in seen:
            continue
        seen.add(key)
        final.append({
            "audit_score": audit_score,
            "category": category,
            "title": row["title"],
            "url": row["url"],
            "channel_id": row["channel_id"],
            "subscribers": row["subscribers"],
            "views": row["views"],
            "verified": row["verified"],
            "selection_reason": reason,
            "description_snippet": row["description"][:280],
        })

    for row in candidate_rows:
        if len(final) >= 100:
            break
        if not relevant(row, cfg):
            continue
        key = row["url"].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        score = int(row.get("score") or 0)
        audit_score = 8 if row.get("tier") in {"strong", "good"} and score >= 50 else 7 if score >= 35 else 6
        text = f"{row.get('title')} {row.get('description_snippet')} {row.get('matched_queries')}"
        final.append({
            "audit_score": audit_score,
            "category": category_for(niche, text),
            "title": row["title"],
            "url": row["url"],
            "channel_id": row["channel_id"],
            "subscribers": row["subscribers"],
            "views": row["views"],
            "verified": row["verified"],
            "selection_reason": f"Candidate matched: {row.get('matched_queries') or ''}"[:240],
            "description_snippet": row.get("description_snippet") or "",
        })

    fields = ["rank", "audit_score", "category", "title", "url", "channel_id", "subscribers", "views", "verified", "selection_reason", "description_snippet"]
    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    for idx, row in enumerate(final[:100], 1):
        out = dict(row)
        out["rank"] = idx
        writer.writerow(out)
    if len(final) < 100:
        print(f"WARNING only {len(final)} rows", file=sys.stderr)


asyncio.run(main())
