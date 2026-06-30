import asyncio
import csv
from pathlib import Path

import asyncpg
from db import _get_dsn


SELECTION = [
    ("https://www.youtube.com/@openai", "official_platform", "OpenAI source: agents, Codex, platform narrative"),
    ("https://www.youtube.com/@anthropic-ai", "official_platform", "Anthropic/Claude source and agent positioning"),
    ("https://www.youtube.com/@claude", "official_platform", "Claude product channel"),
    ("https://www.youtube.com/@langchain", "dev_framework", "Core agent framework/channel"),
    ("https://www.youtube.com/@n8n-io", "workflow_builder", "Core workflow automation + AI agents"),
    ("https://www.youtube.com/@itsmake", "workflow_builder", "No-code AI automation platform"),
    ("https://www.youtube.com/@zapier", "workflow_builder", "Automation platform with agent workflows"),
    ("https://www.youtube.com/@uipath", "official_platform", "Enterprise agentic automation"),
    ("https://www.youtube.com/@warpdotdev", "agentic_dev", "Agentic development environment"),
    ("https://www.youtube.com/@mastra-ai", "dev_framework", "Open-source TypeScript agent framework"),
    ("https://www.youtube.com/@ai-agents-podcast", "market_signal", "Podcast dedicated to AI agents"),
    ("https://www.youtube.com/@ai-agents", "market_signal", "Jotform AI agents channel"),
    ("https://www.youtube.com/@relevanceai", "official_platform", "AI workforce/agent platform"),
    ("https://www.youtube.com/@taskade", "workflow_builder", "Prompt-to-app and AI workflow agent product"),
    ("https://www.youtube.com/@qodoai", "agentic_dev", "Multi-agent code review / AI coding quality"),
    ("https://www.youtube.com/@testmuai", "agentic_dev", "Autonomous testing agents"),
    ("https://www.youtube.com/@ateracloud", "official_platform", "Autonomous IT platform"),
    ("https://www.youtube.com/@telnyx", "voice_agents", "Voice AI / telephony agents"),
    ("https://www.youtube.com/@fiddlerai", "official_platform", "AI observability/security for agents"),
    ("https://www.youtube.com/@teradata", "official_platform", "Enterprise data context for agents"),
    ("https://www.youtube.com/@google", "official_platform", "Big-tech AI/Gemini/agent ecosystem signal"),
    ("https://www.youtube.com/@ibmtechnology", "official_platform", "Enterprise AI/automation education with agent coverage"),
    ("https://www.youtube.com/@autonomy.computer", "dev_framework", "Agentic systems platform"),
    ("https://www.youtube.com/@mindstudio_ai", "workflow_builder", "Build AI agents/apps with prompts"),
    ("https://www.youtube.com/@bika_ai", "workflow_builder", "AI organizer / agent teams positioning"),
    ("https://www.youtube.com/@zipchatai", "commercial_agent", "Ecommerce AI agent use case"),
    ("https://www.youtube.com/@kommunicatechatbots", "commercial_agent", "Customer-service AI agents"),
    ("https://www.youtube.com/@flank-ai", "commercial_agent", "Legal enterprise agents"),
    ("https://www.youtube.com/@docsie", "commercial_agent", "Agentic knowledge-base product"),
    ("https://www.youtube.com/@vast_ai", "infrastructure", "Compute infrastructure for autonomous agents"),
    ("https://www.youtube.com/@treasuredata", "commercial_agent", "Agentic customer experience platform"),
    ("https://www.youtube.com/@blackboxbruiser", "agentic_dev", "AI coding LLM/tool channel"),
    ("https://www.youtube.com/@manuagi", "dev_framework", "AutoGPT/AGI tutorials"),
    ("https://www.youtube.com/@alexfinnofficial", "agentic_dev", "Claude Code/Codex/vibe coding creator"),
    ("https://www.youtube.com/@kevinstratvert", "market_signal", "Mainstream AI/productivity tutorials and agent adoption signal"),
    ("https://www.youtube.com/@sabrina_ramonov", "market_signal", "AI prompts/playbooks/agents creator"),
    ("https://www.youtube.com/@creatormagicai", "agentic_dev", "AI coding, workflow automation and tools"),
    ("https://www.youtube.com/@itssssss_jack", "commercial_agency", "AI automation business and creator angle"),
    ("https://www.youtube.com/@productivedude", "workflow_builder", "Claude/n8n/no-code productivity workflows"),
    ("https://www.youtube.com/@fireship", "agentic_dev", "High-signal dev/AI tools commentary"),
    ("https://www.youtube.com/@colemedin", "agentic_dev", "AI agents and AI coding assistants"),
    ("https://www.youtube.com/@rileybrownai", "agentic_dev", "AI agents for knowledge work and vibe coding"),
    ("https://www.youtube.com/@leonvanzyl", "builder_creator", "Real AI agent/automation/vibe coding builds"),
    ("https://www.youtube.com/@alex.followell", "builder_creator", "Claude Code, n8n, AI coding agents"),
    ("https://www.youtube.com/@nicksaraev", "builder_creator", "Claude Code/Codex/n8n creator"),
    ("https://www.youtube.com/@swiftui-awareness", "agentic_dev", "Codex/agentic coding for Apple dev"),
    ("https://www.youtube.com/@tonbisaigarage", "market_signal", "AI tools, agents, research explainers"),
    ("https://www.youtube.com/@samwitteveenai", "dev_framework", "LLM/agents technical educator"),
    ("https://www.youtube.com/@berkeleyrdi", "research_education", "LLM agents MOOC / research education"),
    ("https://www.youtube.com/@theailanguage", "dev_framework", "MCP/A2A/LangChain/agent development"),
    ("https://www.youtube.com/@ai-luke", "agentic_dev", "AI coding, Claude Code and Codex"),
    ("https://www.youtube.com/@snapperai", "agentic_dev", "Codex vs Claude and AI dev workflows"),
    ("https://www.youtube.com/@pyplane", "agentic_dev", "Software builds with AI agents"),
    ("https://www.youtube.com/@ericwtech", "agentic_dev", "AI products, voice AI, Claude/n8n"),
    ("https://www.youtube.com/@mehulmpt", "agentic_dev", "Software, AI, system design"),
    ("https://www.youtube.com/@conceptandcodingbyshrayansh", "agentic_dev", "Software engineering + AI assistant coding"),
    ("https://www.youtube.com/@codewithclinton", "agentic_dev", "AI-assisted full-stack development"),
    ("https://www.youtube.com/@codeplus_ai", "agentic_dev", "Coding + AI tools"),
    ("https://www.youtube.com/@ailabs-393", "agentic_dev", "AI coding tools and models"),
    ("https://www.youtube.com/@codingtechnyks", "dev_framework", "Agentic AI, RAG, MCP, n8n"),
    ("https://www.youtube.com/@gosucoder", "dev_framework", "AI agents/benchmarking technical channel"),
    ("https://www.youtube.com/@aibites", "research_education", "LLM/agent concept explainers"),
    ("https://www.youtube.com/@brainqub3", "builder_creator", "Production experience with AI agents"),
    ("https://www.youtube.com/@tonykipkemboi", "research_education", "AI agents and data career angle"),
    ("https://www.youtube.com/@claes-ki", "workflow_builder", "N8N and AI agents tutorials"),
    ("https://www.youtube.com/@otromasdesistemas", "workflow_builder", "N8N/Claude Code automation systems"),
    ("https://www.youtube.com/@yashica-jain", "commercial_agency", "AI automation agency implementation"),
    ("https://www.youtube.com/@joshfpocock", "commercial_agency", "AI agents, n8n, GoHighLevel automation"),
    ("https://www.youtube.com/@jamesjernigan", "commercial_agency", "AI automation consulting angle"),
    ("https://www.youtube.com/@liamottley", "commercial_agency", "AI automation agency model"),
    ("https://www.youtube.com/@augmented_ai", "commercial_agency", "AI automation systems for entrepreneurs"),
    ("https://www.youtube.com/@chase-h-ai", "workflow_builder", "No-code AI solutions creator"),
    ("https://www.youtube.com/@jay.ai.automation", "workflow_builder", "AI + automation for solopreneurs"),
    ("https://www.youtube.com/@derekcheungsa", "workflow_builder", "AI agents automation tutorials"),
    ("https://www.youtube.com/@ailearnersbyabhijeet", "workflow_builder", "No-code AI agents and n8n tutorials"),
    ("https://www.youtube.com/@zero2launchai", "workflow_builder", "AI/no-code automation blueprints"),
    ("https://www.youtube.com/@kunaalnaik", "workflow_builder", "n8n and AI agents for SMBs"),
    ("https://www.youtube.com/@automation-tribe", "workflow_builder", "Make/Zapier/n8n automation"),
    ("https://www.youtube.com/@automation-avenue", "workflow_builder", "AI agents/homelab/workflow automation"),
    ("https://www.youtube.com/@automatewithmarc", "workflow_builder", "Business AI agents and automation"),
    ("https://www.youtube.com/@swautomation", "workflow_builder", "AI automation systems and workflows"),
    ("https://www.youtube.com/@nicholaspuru", "commercial_agency", "AI automation systems for business"),
    ("https://www.youtube.com/@lakshit-ukani", "commercial_agency", "WhatsApp/Instagram/voice AI automation"),
    ("https://www.youtube.com/@andylokcl", "commercial_agency", "AI automation agency/proxa"),
    ("https://www.youtube.com/@automate-your-business", "commercial_agency", "AI systems for entrepreneurs"),
    ("https://www.youtube.com/@brendanautomation", "commercial_agency", "AI voice agents and automation agency"),
    ("https://www.youtube.com/@nateherk", "commercial_agency", "AI automations for businesses"),
    ("https://www.youtube.com/@aiautomationkit", "workflow_builder", "AI automation kit/tutorials"),
    ("https://www.youtube.com/@ynteractiveai", "workflow_builder", "n8n ambassador, AI agents/workflows"),
    ("https://www.youtube.com/@syncbricks", "workflow_builder", "AI agents and automation builds"),
    ("https://www.youtube.com/@brennan_wells5", "commercial_agency", "Agentic workflows / AI agency"),
    ("https://www.youtube.com/@bradbonanno", "agentic_dev", "Claude skills and Claude Code projects"),
    ("https://www.youtube.com/@codewithmuh", "workflow_builder", "n8n/Claude automation systems"),
    ("https://www.youtube.com/@ai-gptworkshop", "workflow_builder", "No-code AI tools and agents"),
    ("https://www.youtube.com/@nocodeaibuilders", "workflow_builder", "AI app/no-code builder channel"),
    ("https://www.youtube.com/@theaiuniversity", "agentic_dev", "Claude/Codex/AI tools tutorials"),
    ("https://www.youtube.com/@edhillai", "workflow_builder", "AI automation tutorials"),
    ("https://www.youtube.com/@benai92", "commercial_agency", "AI businesses and practical AI use"),
    ("https://www.youtube.com/@mithunmohanai", "workflow_builder", "AI automation tutorials"),
    ("https://www.youtube.com/@aiautomation-a1", "workflow_builder", "AI automation education"),
    ("https://www.youtube.com/@enterproai", "agentic_dev", "Vibe coding AI agent"),
    ("https://www.youtube.com/@aaacrm", "dev_framework", "Autonomous AI agents orchestration"),
]


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT channel_id, title, url, subscribers, views, verified,
                   regexp_replace(coalesce(description,''), '[[:space:]]+', ' ', 'g') AS description
            FROM yt_channel_catalog
            WHERE url = ANY($1::text[])
            """,
            [url for url, _, _ in SELECTION],
        )
    finally:
        await conn.close()

    by_url = {row["url"].rstrip("/").lower(): dict(row) for row in rows}
    seen = set()
    final = []
    missing = []
    for url, category, reason in SELECTION:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        row = by_url.get(key)
        if not row:
            missing.append((url, category, reason))
            continue
        row["category"] = category
        row["selection_reason"] = reason
        final.append(row)
        if len(final) == 100:
            break

    fields = [
        "rank",
        "category",
        "title",
        "url",
        "channel_id",
        "subscribers",
        "views",
        "verified",
        "selection_reason",
        "description_snippet",
    ]
    import sys

    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    for idx, row in enumerate(final, start=1):
        writer.writerow(
            {
                "rank": idx,
                "category": row["category"],
                "title": row["title"],
                "url": row["url"],
                "channel_id": row["channel_id"],
                "subscribers": row["subscribers"],
                "views": row["views"],
                "verified": row["verified"],
                "selection_reason": row["selection_reason"],
                "description_snippet": row["description"][:260],
            }
        )
    if missing:
        print("missing", len(missing), file=sys.stderr)
        for item in missing:
            print("MISSING", item[0], file=sys.stderr)


asyncio.run(main())
