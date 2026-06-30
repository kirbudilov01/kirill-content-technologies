import asyncio
import csv
import os
import re
import sys

import asyncpg
from db import _get_dsn


CONFIGS = {
    "ai_agency": {
        "manual": [
            ("https://www.youtube.com/@liamottley", "agency_operator", 10, "Canonical AI Automation Agency creator/operator"),
            ("https://www.youtube.com/@daveebbelaar", "ai_consulting", 10, "AI engineering consultancy and B2B implementation signal"),
            ("https://www.youtube.com/@nateherk", "automation_creator", 10, "Business AI automations and implementation examples"),
            ("https://www.youtube.com/@derekcheungsa", "automation_creator", 9, "AI agents automation for non-technical operators"),
            ("https://www.youtube.com/@benai92", "ai_business", 9, "AI business/automation implementation education"),
            ("https://www.youtube.com/@alex.followell", "automation_creator", 9, "n8n/Claude automation systems and consulting-adjacent workflows"),
            ("https://www.youtube.com/@nicksaraev", "ai_business", 9, "Agency background, Claude/Codex/n8n business implementation"),
            ("https://www.youtube.com/@colemedin", "agent_builder", 9, "AI agents and coding assistants with practical builds"),
            ("https://www.youtube.com/@rileybrownai", "agent_builder", 9, "AI agents for business and building products"),
            ("https://www.youtube.com/@productivedude", "automation_creator", 8, "AI workflows/no-code productivity systems"),
            ("https://www.youtube.com/@automation-tribe", "automation_creator", 8, "No-code AI workflow automation and templates"),
            ("https://www.youtube.com/@codewithmuh", "automation_creator", 8, "n8n/Claude automation systems"),
            ("https://www.youtube.com/@syncbricks", "automation_creator", 8, "Real-world AI automation and IT workflows"),
            ("https://www.youtube.com/@ai-gptworkshop", "automation_creator", 8, "No-code AI agents and automation education"),
            ("https://www.youtube.com/@edhillai", "automation_creator", 8, "AI automation tutorials"),
            ("https://www.youtube.com/@mithunmohanai", "automation_creator", 8, "AI automation tutorials"),
            ("https://www.youtube.com/@aiautomationkit", "automation_creator", 8, "n8n/Make/Apify AI automation builds"),
            ("https://www.youtube.com/@zero2launchai", "automation_creator", 8, "AI/no-code automation blueprints"),
            ("https://www.youtube.com/@jay.ai.automation", "automation_creator", 8, "AI automation for solopreneurs"),
            ("https://www.youtube.com/@automatewithmarc", "automation_creator", 8, "Claude Code/n8n/business AI agents"),
            ("https://www.youtube.com/@sebastianhardyai", "automation_creator", 8, "Claude Code and AI automation workflows for business"),
            ("https://www.youtube.com/@tylerreedai", "agent_builder", 8, "AI agents and automation education"),
            ("https://www.youtube.com/@jessautomates", "agent_builder", 8, "AI agents education"),
            ("https://www.youtube.com/@aiagentsaz", "agent_builder", 8, "Practical AI agents builds"),
            ("https://www.youtube.com/@socialmediacompanynl", "automation_creator", 8, "AI agents for organizations"),
            ("https://www.youtube.com/@kunaalnaik", "automation_creator", 8, "AI agents for SMB automation"),
            ("https://www.youtube.com/@nicholaspuru", "automation_creator", 8, "AI automation systems for companies"),
            ("https://www.youtube.com/@brennan_wells5", "agency_operator", 8, "Runs/teaches AI agency and automation systems"),
            ("https://www.youtube.com/@lucaswalterai", "agency_operator", 8, "AI automation agency/business implementation"),
            ("https://www.youtube.com/@michtortiyt", "agency_operator", 8, "AI automation agency growth and offer education"),
            ("https://www.youtube.com/@yashica-jain", "agency_operator", 8, "Founder-led AI automation agency implementation content"),
            ("https://www.youtube.com/@sixflowautomations", "agency_operator", 8, "AI automation agency journey and client acquisition signal"),
            ("https://www.youtube.com/@automateaiconsulting", "ai_consulting", 8, "AI consultant/automation business positioning"),
            ("https://www.youtube.com/@altusai", "automation_creator", 8, "Business automation and intelligent systems for operators"),
            ("https://www.youtube.com/@lakshit-ukani", "automation_creator", 8, "AI voice, WhatsApp and Instagram automation for businesses"),
            ("https://www.youtube.com/@yohita005", "automation_creator", 8, "Real-world AI agents, voice systems and chatbots"),
            ("https://www.youtube.com/@botpress", "agent_builder", 8, "AI agent/chatbot platform used for agency deliverables"),
            ("https://www.youtube.com/@telnyx", "voice_agent_platform", 8, "Voice AI tutorials and telephony infrastructure for agent builds"),
            ("https://www.youtube.com/@salesforce", "enterprise_ai", 8, "Agentforce and enterprise AI agent adoption signal"),
            ("https://www.youtube.com/@fin-customer-agent", "enterprise_ai", 8, "Customer support AI agent platform and enterprise agent adoption signal"),
            ("https://www.youtube.com/@atefataya", "agent_builder", 8, "AI systems and agent-building education for builders"),
            ("https://www.youtube.com/@aiagentcommunity", "agent_builder", 7, "AI agent community and implementation signal"),
            ("https://www.youtube.com/@youraiworkflow", "automation_creator", 7, "AI workflow automation and practical systems"),
            ("https://www.youtube.com/@altexsoft", "ai_consulting", 7, "AI/software consulting and implementation agency signal"),
            ("https://www.youtube.com/@lyzrai", "agent_builder", 7, "Enterprise AI workflow automation and agent framework"),
            ("https://www.youtube.com/@walters954", "enterprise_ai", 7, "Salesforce and AI agent builds from an operator perspective"),
            ("https://www.youtube.com/@chetanagarwalll", "automation_creator", 7, "AI tools, SaaS, outreach and business automation"),
            ("https://www.youtube.com/@sanjeevjaincbx", "automation_creator", 7, "AI tools and business automation for entrepreneurs"),
            ("https://www.youtube.com/@zackstevenson", "automation_creator", 7, "Business automation, AI and custom app systems"),
            ("https://www.youtube.com/@digitalmartlab", "automation_creator", 7, "AI automation and marketing systems"),
            ("https://www.youtube.com/@aliaiautomation", "automation_creator", 7, "AI automation templates and services"),
            ("https://www.youtube.com/@futurepedia_io", "ai_tools_media", 7, "AI tools discovery for agency stack"),
            ("https://www.youtube.com/@skillleapai", "ai_tools_media", 7, "AI tools tutorials for business operators"),
            ("https://www.youtube.com/@mreflow", "ai_tools_media", 7, "AI tools/news useful for agency offer discovery"),
            ("https://www.youtube.com/@allaboutai", "ai_builder_media", 7, "AI automation/engineering tutorials"),
            ("https://www.youtube.com/@matthew_berman", "ai_builder_media", 7, "AI tools and model market signal"),
            ("https://www.youtube.com/@theaigrid", "ai_builder_media", 7, "AI market/news signal for agency offers"),
            ("https://www.youtube.com/@gregisenberg", "ai_business", 7, "AI startup ideas and business-building audience"),
            ("https://www.youtube.com/@danmartell", "ai_business", 7, "AI business/operator audience"),
            ("https://www.youtube.com/@alexberman", "ai_business", 7, "Lead generation and AI business signal"),
            ("https://www.youtube.com/@uipath", "enterprise_automation", 7, "Enterprise automation and agentic process automation"),
            ("https://www.youtube.com/@automationanywhere", "enterprise_automation", 7, "Enterprise automation/agentic process automation"),
            ("https://www.youtube.com/@ibmtechnology", "enterprise_ai", 7, "Enterprise AI/automation education"),
            ("https://www.youtube.com/@n8n-io", "automation_platform", 8, "Core AI workflow automation platform"),
            ("https://www.youtube.com/@itsmake", "automation_platform", 8, "Workflow automation platform used by agencies"),
            ("https://www.youtube.com/@zapier", "automation_platform", 8, "Workflow automation platform used by agencies"),
            ("https://www.youtube.com/@airtableapp", "automation_platform", 7, "AI app/workflow platform for business operations"),
            ("https://www.youtube.com/@gohighlevel", "agency_platform", 7, "Agency CRM/marketing automation platform"),
        ],
        "strong_terms": ["ai automation agency", "ai agency", "automation agency", "ai automation", "ai agents", "ai agent", "voice agent", "chatbot", "n8n", "make.com", "zapier", "gohighlevel", "consulting", "consultant", "agency", "business automation"],
        "must_any": ["ai", "automation", "agent", "n8n", "make.com", "zapier", "chatbot", "voice"],
        "negative": ["pie.agency", "linkto.agency", "exboso agency", "news agency", "space agency", "central intelligence agency", "video news agency", "advertising agency", "travel agency", "insurance agency", "media agency", "digital marketing services", "host agency", "agency performance partners", "real estate", "etiquette", "homebuilding", "sales training", "pre tutorials", "ai plus", "marc illy", "koen | ai content systems", "kognitos", "highlevel experience podcast", "ai founders", "aisensy", "the ai learning", "taskade", "ai profit consultant", "diet kundali", "academic agent", "learn ai with ritika", "ai with lena hall", "frank nillard", "music", "gaming", "minecraft", "roblox", "football", "industrial automation", "haas automation", "rockwell automation", "kuka", "emerson", "plc", "cnc machine"],
    },
    "open_source_projects": {
        "manual": [
            ("https://www.youtube.com/@awesomeopensource", "open_source_media", 10, "Dedicated open-source/free/self-hosted software reviews"),
            ("https://www.youtube.com/@techhut", "open_source_media", 9, "Open-source/Linux/self-hosting education"),
            ("https://www.youtube.com/@christianlempa", "self_hosted_devops", 9, "Self-hosting, automation, infra and dev tooling"),
            ("https://www.youtube.com/@technotim", "self_hosted_devops", 9, "Home lab/self-hosted infrastructure"),
            ("https://www.youtube.com/@dbtechyt", "self_hosted_devops", 9, "Docker/self-hosted app tutorials"),
            ("https://www.youtube.com/@learnlinuxtv", "linux_open_source", 9, "Linux/open-source education"),
            ("https://www.youtube.com/@christitustech", "linux_open_source", 9, "Linux/open-source desktop tooling"),
            ("https://www.youtube.com/@lawrencesystems", "self_hosted_devops", 8, "Open-source networking/security/self-hosting"),
            ("https://www.youtube.com/@wolfgangschannel", "linux_open_source", 8, "Linux/open-source tech culture"),
            ("https://www.youtube.com/@raidowl", "self_hosted_devops", 8, "Home lab/self-hosted tech"),
            ("https://www.youtube.com/@networkchuck", "devops_signal", 8, "Linux/Docker/cloud audience with open-source tooling"),
            ("https://www.youtube.com/@fireship", "dev_tools_media", 9, "Viral developer tools and GitHub projects signal"),
            ("https://www.youtube.com/@theprimetimeagen", "dev_tools_media", 9, "Developer culture/open-source/repos signal"),
            ("https://www.youtube.com/@freecodecamp", "dev_tools_media", 8, "Large developer education and open-source ecosystem"),
            ("https://www.youtube.com/@bytebytego", "dev_tools_media", 8, "Engineering/dev tools audience"),
            ("https://www.youtube.com/@t3dotgg", "dev_tools_media", 8, "Developer/open-source/startup tool commentary"),
            ("https://www.youtube.com/@devopstoolkit", "devops_signal", 8, "DevOps/open-source tooling reviews"),
            ("https://www.youtube.com/@techworldwithnana", "devops_signal", 8, "DevOps/Kubernetes/open-source infrastructure"),
            ("https://www.youtube.com/@kubesimplify", "devops_signal", 8, "Kubernetes/cloud-native open-source projects"),
            ("https://www.youtube.com/@cncf", "official_project", 8, "Cloud Native Computing Foundation projects"),
            ("https://www.youtube.com/@dockerinc", "official_project", 8, "Docker official developer platform"),
            ("https://www.youtube.com/@kubernetescommunity", "official_project", 8, "Kubernetes official community"),
            ("https://www.youtube.com/@supabase", "official_project", 9, "Open-source backend/Postgres platform"),
            ("https://www.youtube.com/@appwrite", "official_project", 9, "Open-source app backend"),
            ("https://www.youtube.com/@n8n-io", "official_project", 9, "Open-source workflow automation platform"),
            ("https://www.youtube.com/@posthog", "official_project", 9, "Open-source product analytics platform"),
            ("https://www.youtube.com/@grafana", "official_project", 9, "Open observability platform"),
            ("https://www.youtube.com/@nocodb", "official_project", 8, "Open-source Airtable alternative"),
            ("https://www.youtube.com/@strapi", "official_project", 8, "Open-source headless CMS"),
            ("https://www.youtube.com/@twentycrm", "official_project", 7, "Open-source CRM alternative"),
            ("https://www.youtube.com/@documenso", "official_project", 7, "Open-source signing/productivity tool"),
            ("https://www.youtube.com/@huggingface", "official_project", 9, "Open-source AI models/datasets/apps ecosystem"),
            ("https://www.youtube.com/@langchain", "official_project", 9, "Open-source LLM/agents framework"),
            ("https://www.youtube.com/@continuedev", "open_source_agent", 9, "Open-source AI code assistant"),
            ("https://www.youtube.com/@goose-oss", "open_source_agent", 8, "Open-source coding agent"),
            ("https://www.youtube.com/@sourcegraph", "dev_tools_media", 8, "Code search/AI dev tools"),
            ("https://www.youtube.com/@composio", "official_project", 7, "Agent tooling/integrations project"),
            ("https://www.youtube.com/@gitlab", "official_project", 9, "Open-source DevSecOps platform"),
            ("https://www.youtube.com/@godotengineofficial", "official_project", 9, "Free open-source game engine"),
            ("https://www.youtube.com/@wordpress", "official_project", 9, "Open-source publishing/CMS ecosystem"),
            ("https://www.youtube.com/@matrixdotorg", "official_project", 8, "Open messaging protocol/ecosystem"),
            ("https://www.youtube.com/@tailscale", "official_project", 8, "Developer infrastructure and networking tooling"),
            ("https://www.youtube.com/@penpot", "official_project", 8, "Open-source design platform"),
            ("https://www.youtube.com/@openprojectcommunity", "official_project", 8, "Open-source project management software"),
            ("https://www.youtube.com/@odoo", "official_project", 8, "Open-source business apps suite"),
            ("https://www.youtube.com/@hashicorp", "official_project", 8, "Infrastructure-as-code/open tooling ecosystem"),
            ("https://www.youtube.com/@elastic", "official_project", 8, "Search/observability open tooling ecosystem"),
            ("https://www.youtube.com/@postgresconference", "official_project", 7, "Postgres open-source database ecosystem"),
            ("https://www.youtube.com/@mariadbfoundation", "official_project", 7, "Open-source database foundation"),
            ("https://www.youtube.com/@obsproject", "official_project", 7, "Free open-source recording/streaming software"),
            ("https://www.youtube.com/@code", "official_project", 9, "VS Code open-source AI code editor"),
            ("https://www.youtube.com/@github", "dev_tools_media", 9, "GitHub developer/repository platform"),
            ("https://www.youtube.com/@githubawesome", "open_source_media", 8, "Daily GitHub trending repository summaries"),
            ("https://www.youtube.com/@githubtrendfeed", "open_source_media", 8, "Daily GitHub trend/repository feed"),
            ("https://www.youtube.com/@githubtrends", "open_source_media", 8, "GitHub repositories trend signal"),
            ("https://www.youtube.com/@tonyteachestech", "self_hosted", 8, "Self-hosted apps/websites/server tutorials"),
            ("https://www.youtube.com/@michaelnroh", "self_hosted", 8, "Linux/self-hosting education"),
            ("https://www.youtube.com/@warpdotdev", "official_project", 8, "Open-source agentic development environment"),
            ("https://www.youtube.com/@burkeholland", "dev_tools_media", 7, "GitHub Copilot/VS Code developer tooling"),
            ("https://www.youtube.com/@prohomelab", "self_hosted", 8, "Homelab, self-hosted apps and DevOps"),
            ("https://www.youtube.com/@codingentrepreneurs", "dev_tools_media", 7, "Build projects and developer tools education"),
            ("https://www.youtube.com/@it-connect", "self_hosted", 7, "Sysadmin, network and self-hosting education"),
            ("https://www.youtube.com/@evan_homelab", "self_hosted", 7, "Homelab/self-hosted tutorials"),
            ("https://www.youtube.com/@siderolabs", "official_project", 8, "Talos Linux and Kubernetes infrastructure"),
            ("https://www.youtube.com/@altinity", "official_project", 8, "Open-source ClickHouse ecosystem"),
            ("https://www.youtube.com/@netbirdio", "official_project", 8, "Open-source zero trust networking"),
            ("https://www.youtube.com/@opennebula", "official_project", 8, "Open-source cloud and virtualization platform"),
            ("https://www.youtube.com/@kilo-code", "open_source_agent", 8, "Open-source coding agent platform"),
            ("https://www.youtube.com/@destinationlinux", "linux_open_source", 8, "Linux/open-source podcast and news"),
            ("https://www.youtube.com/@elestio", "official_project", 8, "Managed platform for open-source software deployments"),
            ("https://www.youtube.com/@bretfisher", "devops_open_source", 8, "Docker, Kubernetes and cloud-native open-source education"),
            ("https://www.youtube.com/@nixiepixel", "linux_open_source", 8, "Open-source alternatives, Linux and geek culture"),
            ("https://www.youtube.com/@mozilladeveloper", "official_project", 8, "Mozilla developer/open web education"),
            ("https://www.youtube.com/@microsoftdeveloper", "dev_tools_media", 8, "Developer platform channel with VS Code/GitHub/open web relevance"),
            ("https://www.youtube.com/@changelog", "open_source_media", 8, "Developer podcast/news channel covering open-source projects"),
            ("https://www.youtube.com/@taylorwalton_socfortress", "self_hosted", 7, "Self-hosted security/SOC tooling and open-source adjacent infrastructure"),
            ("https://www.youtube.com/@arctutorials", "open_source_agent", 7, "LangChain, LLMOps and open-source AI architecture education"),
            ("https://www.youtube.com/@appsmith", "official_project", 8, "Open-source internal tools and app builder"),
            ("https://www.youtube.com/@budibase", "official_project", 8, "Open-source low-code/internal tools platform"),
            ("https://www.youtube.com/@nextcloud", "official_project", 8, "Open-source collaboration and self-hosted productivity platform"),
            ("https://www.youtube.com/@eclipsefdn", "official_project", 8, "Open-source foundation and project ecosystem"),
            ("https://www.youtube.com/@prometheusio", "official_project", 8, "Open-source monitoring system"),
            ("https://www.youtube.com/@mongodb", "official_project", 8, "Developer database platform with open-source ecosystem relevance"),
            ("https://www.youtube.com/@redisinc", "official_project", 8, "Redis database/platform and developer tooling ecosystem"),
        ],
        "strong_terms": ["open source", "open-source", "github", "self hosted", "self-hosted", "homelab", "linux", "docker", "kubernetes", "devops", "developer tools", "repository", "repositories", "free alternative", "source available", "llm", "ai agents"],
        "must_any": ["open", "github", "self", "linux", "docker", "kubernetes", "devops", "developer", "llm", "agent"],
        "negative": ["music", "gaming", "minecraft", "roblox", "football", "fashion", "movie", "kids", "crime", "osint", "ai-gptworkshop", "syncbricks", "nicholaspuru", "dmitrylambert", "itsmake", "theailearning", "taskade", "tylerreedai", "digitalmartlab"],
    },
    "video_data_service": {
        "manual": [
            ("https://www.youtube.com/@vidiq", "youtube_analytics_tool", 10, "Core YouTube analytics/SEO competitor"),
            ("https://www.youtube.com/@tubebuddy", "youtube_analytics_tool", 10, "Core YouTube optimization/analytics competitor"),
            ("https://www.youtube.com/@socialblade", "creator_data_tool", 10, "YouTube/social stats and channel data"),
            ("https://www.youtube.com/@morningfame", "youtube_analytics_tool", 9, "YouTube growth analytics/tool education"),
            ("https://www.youtube.com/@channelmakers", "youtube_strategy", 9, "YouTube experiments and channel growth analysis"),
            ("https://www.youtube.com/@thinkmediatv", "youtube_strategy", 9, "YouTube creator strategy and channel growth"),
            ("https://www.youtube.com/@primalvideo", "video_strategy", 9, "Video tools, AI and creator workflow strategy"),
            ("https://www.youtube.com/@filmbooth", "youtube_strategy", 9, "YouTube packaging and retention strategy"),
            ("https://www.youtube.com/@colinandsamir", "creator_economy", 8, "Creator economy and YouTube market signal"),
            ("https://www.youtube.com/@thinkmediapodcast", "creator_economy", 8, "Creator business and video strategy"),
            ("https://www.youtube.com/@semrush", "marketing_data_tool", 9, "Search/AI visibility and content research platform"),
            ("https://www.youtube.com/@ahrefscom", "marketing_data_tool", 9, "SEO/YouTube SEO/content research platform"),
            ("https://www.youtube.com/@similarweb", "market_intelligence_tool", 9, "Digital market/competitor intelligence platform"),
            ("https://www.youtube.com/@sparktoro", "audience_intelligence_tool", 9, "Audience research and influence-source discovery"),
            ("https://www.youtube.com/@explodingtopics", "trend_data_tool", 9, "Trend discovery and product/startup trend data"),
            ("https://www.youtube.com/@hubspotmarketing", "marketing_ops", 8, "Marketing analytics/workflow education"),
            ("https://www.youtube.com/@socialmediaexaminer", "social_media_strategy", 8, "Social media marketing trend and strategy signal"),
            ("https://www.youtube.com/@latermedia", "social_data_tool", 8, "Influencer/social marketing intelligence platform"),
            ("https://www.youtube.com/@hootsuite", "social_data_tool", 8, "Social media management and analytics platform"),
            ("https://www.youtube.com/@bufferapp", "social_data_tool", 8, "Social publishing and analytics platform"),
            ("https://www.youtube.com/@sproutsocial", "social_data_tool", 8, "Social media analytics and business intelligence"),
            ("https://www.youtube.com/@publer", "social_data_tool", 7, "Social scheduler and analytics"),
            ("https://www.youtube.com/@contentstudio", "social_data_tool", 7, "Content/social management analytics"),
            ("https://www.youtube.com/@planable", "social_data_tool", 7, "Content planning and social workflow"),
            ("https://www.youtube.com/@sendible", "social_data_tool", 7, "Social media management and reporting"),
            ("https://www.youtube.com/@planoly", "social_data_tool", 7, "Social planner for creators/brands"),
            ("https://www.youtube.com/@tailwindapp", "social_data_tool", 7, "Pinterest/social scheduling analytics"),
            ("https://www.youtube.com/@typefully", "social_data_tool", 7, "Writing/social distribution workflow"),
            ("https://www.youtube.com/@canva", "creator_tool", 7, "Creator/content platform with marketing workflows"),
            ("https://www.youtube.com/@neilpatel", "marketing_strategy", 7, "Digital marketing/SEO/content analytics signal"),
            ("https://www.youtube.com/@robertoblake", "creator_strategy", 8, "Creator business and growth systems"),
            ("https://www.youtube.com/@modernmillie", "creator_strategy", 8, "Creator/social growth strategy"),
            ("https://www.youtube.com/@ishansharma7390", "creator_strategy", 7, "Creator business/AI/content market signal"),
            ("https://www.youtube.com/@kevinstratvert", "tool_education", 7, "Software/AI productivity tools education"),
            ("https://www.youtube.com/@mreflow", "ai_tool_research", 7, "AI tools discovery and trend signal"),
            ("https://www.youtube.com/@futurepedia_io", "ai_tool_research", 7, "AI tools database/media signal"),
            ("https://www.youtube.com/@skillleapai", "ai_tool_research", 7, "AI tools tutorials and trend discovery"),
            ("https://www.youtube.com/@appsumo", "marketplace_signal", 7, "SaaS/tool marketplace signal"),
            ("https://www.youtube.com/@ycombinator", "startup_market_signal", 7, "Startup/product-market trend signal"),
            ("https://www.youtube.com/@a16z", "startup_market_signal", 7, "Tech/startup market trend signal"),
            ("https://www.youtube.com/@beehiiv", "creator_tool", 7, "Newsletter/media growth platform"),
            ("https://www.youtube.com/@substackinc", "creator_tool", 7, "Creator publishing platform"),
            ("https://www.youtube.com/@creatorinsider", "youtube_platform", 8, "YouTube creator/platform insights from YouTube team"),
            ("https://www.youtube.com/@youtubecreators", "youtube_platform", 8, "Official YouTube creator education"),
            ("https://www.youtube.com/@googlesearchcentral", "search_data_tool", 8, "Official Google Search/SEO education"),
            ("https://www.youtube.com/@googleanalytics", "analytics_tool", 8, "Official Google Analytics education"),
            ("https://www.youtube.com/@moz", "marketing_data_tool", 8, "SEO/data/content marketing education"),
            ("https://www.youtube.com/@searchenginejournal", "marketing_data_tool", 8, "Search/content marketing trend signal"),
            ("https://www.youtube.com/@backlinko", "marketing_data_tool", 8, "SEO/content research education"),
            ("https://www.youtube.com/@wistia", "video_data_tool", 8, "Video marketing platform and analytics education"),
            ("https://www.youtube.com/@descript", "creator_tool", 7, "Video/podcast workflow tool"),
            ("https://www.youtube.com/@opusclip", "creator_tool", 7, "AI clipping and Shorts repurposing tool"),
            ("https://www.youtube.com/@kapwing", "creator_tool", 7, "Video creation tool with AI/social content signal"),
            ("https://www.youtube.com/@veedstudio", "creator_tool", 7, "Video creation/editing platform"),
            ("https://www.youtube.com/@riversidefm", "creator_tool", 7, "Podcast/video creation and analytics workflow"),
            ("https://www.youtube.com/@creatortestlabs", "youtube_strategy", 7, "YouTube analytics testing and algorithm experiments"),
            ("https://www.youtube.com/@zohoanalytics", "analytics_tool", 8, "BI/analytics platform"),
            ("https://www.youtube.com/@databricks", "analytics_tool", 8, "Data intelligence and AI analytics platform"),
            ("https://www.youtube.com/@analyticsmania", "analytics_tool", 8, "Google Analytics and Tag Manager education"),
            ("https://www.youtube.com/@orangedatamining", "analytics_tool", 7, "Data mining and visual analytics tool"),
            ("https://www.youtube.com/@adobeanalytics3740", "analytics_tool", 8, "Adobe Analytics product education"),
            ("https://www.youtube.com/@pyramidanalytics", "analytics_tool", 7, "Decision intelligence/analytics platform"),
            ("https://www.youtube.com/@tableau", "analytics_tool", 8, "Business intelligence and data visualization platform"),
            ("https://www.youtube.com/@microsoftpowerbi", "analytics_tool", 8, "Business analytics and dashboard platform"),
            ("https://www.youtube.com/@googlecloudtech", "analytics_tool", 7, "Google Cloud data/AI tooling signal"),
            ("https://www.youtube.com/@thinkwithgoogle", "market_data_tool", 8, "Consumer data, marketing insights, and trend signal"),
            ("https://www.youtube.com/@creatorwizard", "creator_economy", 7, "Creator monetization and sponsorship market signal"),
            ("https://www.youtube.com/@nicknimmin", "youtube_strategy", 8, "YouTube tips/tools/updates for creators"),
            ("https://www.youtube.com/@tubefilter", "creator_economy", 7, "Creator platform news and digital entertainment data signal"),
            ("https://www.youtube.com/@klipfolio", "analytics_tool", 7, "Dashboard and reporting platform"),
            ("https://www.youtube.com/@thoughtspot", "analytics_tool", 7, "Agentic analytics platform"),
            ("https://www.youtube.com/@chartmogul", "analytics_tool", 7, "Subscription/SaaS analytics platform"),
            ("https://www.youtube.com/@baremetrics", "analytics_tool", 7, "Revenue analytics for subscription companies"),
            ("https://www.youtube.com/@brand24", "social_data_tool", 7, "Social listening and brand monitoring"),
            ("https://www.youtube.com/@mentionlytics", "social_data_tool", 7, "Social listening and sentiment/trend monitoring"),
            ("https://www.youtube.com/@briefcamvs", "video_data_tool", 7, "Video analytics software"),
            ("https://www.youtube.com/@teramindco", "analytics_tool", 7, "User behavior analytics platform"),
            ("https://www.youtube.com/@axxonsoftus", "video_data_tool", 7, "Video management and analytics software"),
            ("https://www.youtube.com/@cathexis-video-management", "video_data_tool", 7, "Video management and analytics platform"),
            ("https://www.youtube.com/@salesforce", "analytics_tool", 7, "CRM/customer data and AI analytics platform signal"),
            ("https://www.youtube.com/@ibmtechnology", "analytics_tool", 7, "Enterprise AI/data/analytics education"),
            ("https://www.youtube.com/@adobecreativecloud", "creator_tool", 7, "Creative/content tooling ecosystem"),
            ("https://www.youtube.com/@marketresearchinstitute", "market_data_tool", 7, "Market research education and standards"),
            ("https://www.youtube.com/@theaisearch", "ai_tool_research", 7, "AI trend/tool discovery signal"),
            ("https://www.youtube.com/@analyticswithnags", "analytics_tool", 7, "Power BI and analytics tutorials"),
            ("https://www.youtube.com/@geovisioninc", "video_data_tool", 7, "Video analytics and VMS platform"),
            ("https://www.youtube.com/@modeanalytics", "analytics_tool", 7, "Modern BI/analytics platform"),
            ("https://www.youtube.com/@sisense", "analytics_tool", 7, "Embedded analytics platform"),
            ("https://www.youtube.com/@rivaliq", "social_data_tool", 7, "Competitive social and search analytics"),
            ("https://www.youtube.com/@talkwalker", "social_data_tool", 7, "Consumer intelligence and social listening platform"),
            ("https://www.youtube.com/@iconosquare", "social_data_tool", 7, "Social media analytics-first management platform"),
            ("https://www.youtube.com/@dashthis", "analytics_tool", 7, "Marketing dashboards and reporting platform"),
            ("https://www.youtube.com/@whatagraph", "analytics_tool", 7, "Marketing intelligence and reporting platform"),
            ("https://www.youtube.com/@agencyanalytics", "analytics_tool", 7, "Agency reporting, SEO, and marketing dashboards"),
            ("https://www.youtube.com/@geckoboard", "analytics_tool", 7, "Dashboard and reporting platform"),
            ("https://www.youtube.com/@datapine", "analytics_tool", 7, "BI dashboard and reporting platform"),
            ("https://www.youtube.com/@cmicontent", "marketing_data_tool", 7, "Content marketing research and strategy education"),
            ("https://www.youtube.com/@matgpod", "marketing_data_tool", 7, "Marketing trends, growth tactics and AI-era distribution signal"),
            ("https://www.youtube.com/@the-developer-bi", "analytics_tool", 7, "Power BI, dashboard and data visualization education"),
            ("https://www.youtube.com/@office-productivity-hub", "analytics_tool", 7, "Excel, Google Sheets, Power BI and reporting tutorials"),
            ("https://www.youtube.com/@millieadrian", "creator_strategy", 7, "Creator/social growth channel with platform analytics and content strategy videos"),
        ],
        "strong_terms": ["youtube analytics", "youtube seo", "creator analytics", "social media analytics", "analytics", "trend", "trends", "content research", "competitor analysis", "market intelligence", "audience research", "social listening", "seo", "content strategy", "viral video", "growth tool", "data-driven", "reporting", "algorithm"],
        "must_any": ["analytics", "trend", "seo", "research", "audience", "market", "competitor", "data", "tool", "algorithm", "reporting"],
        "negative": ["music", "gaming", "minecraft", "roblox", "football", "fashion", "movie", "kids", "stock market", "crypto trading", "vlog", "crime", "fitness", "pilates", "knitting", "cooking", "tarot", "skincare", "motortrend", "parithabangal", "coding with sagar", "millieadrian", "zoco marketing", "prompt revolution", "marketingedgetamil"],
    },
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


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
    return any(term in text for term in cfg["strong_terms"]) and any(term in text for term in cfg["must_any"])


def category_for(niche: str, text: str) -> str:
    text = text.lower()
    if niche == "ai_agency":
        if any(x in text for x in ["n8n", "make.com", "zapier", "airtable", "gohighlevel"]):
            return "automation_stack"
        if any(x in text for x in ["agency", "consulting", "consultant"]):
            return "agency_operator"
        if any(x in text for x in ["agent", "chatbot", "voice"]):
            return "agent_builder"
        return "ai_business_signal"
    if niche == "open_source_projects":
        if any(x in text for x in ["supabase", "appwrite", "grafana", "strapi", "docker", "kubernetes", "n8n", "posthog", "langchain", "hugging face"]):
            return "official_project"
        if any(x in text for x in ["self-hosted", "self hosted", "homelab", "home lab"]):
            return "self_hosted"
        if any(x in text for x in ["linux", "devops", "docker", "kubernetes"]):
            return "devops_open_source"
        return "open_source_media"
    if any(x in text for x in ["vidiq", "tubebuddy", "social blade", "youtube seo", "youtube analytics"]):
        return "youtube_analytics"
    if any(x in text for x in ["semrush", "ahrefs", "similarweb", "sparktoro", "exploding topics"]):
        return "market_data_tool"
    if any(x in text for x in ["hootsuite", "buffer", "sprout", "social media", "later"]):
        return "social_analytics"
    return "creator_strategy"


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
    candidates_path = os.environ.get("CANDIDATES_PATH")
    cfg = CONFIGS[niche]
    candidate_rows = []
    if candidates_path:
        candidate_rows = list(csv.DictReader(open(candidates_path, newline="", encoding="utf-8")))
    manual_by_url = await fetch_manual_rows([url for url, _, _, _ in cfg["manual"]])

    final = []
    seen = set()
    for url, category, audit_score, reason in cfg["manual"]:
        key = url.rstrip("/").lower()
        row = manual_by_url.get(key)
        if not row or key in seen:
            continue
        desc = row["description"] or ""
        if int(row.get("subscribers") or 0) < 50 and len(desc) < 40:
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
            "description_snippet": desc[:280],
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
        audit_score = 8 if row.get("tier") in {"strong", "good"} and score >= 55 else 7 if score >= 40 else 6
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
