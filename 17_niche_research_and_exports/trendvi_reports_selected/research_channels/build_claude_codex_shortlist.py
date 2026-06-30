import asyncio
import csv
from pathlib import Path

import asyncpg
from db import _get_dsn


SELECTION = [
    ("https://www.youtube.com/@openai", "official_platform", 10, "OpenAI source for Codex, ChatGPT coding agents, and platform narrative"),
    ("https://www.youtube.com/@anthropic-ai", "official_platform", 10, "Anthropic source for Claude and Claude Code positioning"),
    ("https://www.youtube.com/@claude", "official_platform", 10, "Claude product channel and official problem-solver framing"),
    ("https://www.youtube.com/@cursor_ai", "official_platform", 10, "Cursor is a core AI coding IDE/platform in the niche"),
    ("https://www.youtube.com/@replit", "official_platform", 10, "Replit Agent and prompt-to-app platform signal"),
    ("https://www.youtube.com/@lovable", "official_platform", 10, "Lovable is a core vibe-coding/app-builder platform"),
    ("https://www.youtube.com/@windsurf", "official_platform", 10, "Windsurf official channel for agentic IDE coverage"),
    ("https://www.youtube.com/@vercelhq", "official_platform", 9, "Vercel/v0 ecosystem and AI app-building workflows"),
    ("https://www.youtube.com/@boltdotnew", "official_platform", 9, "Bolt.new official prompt-to-full-stack app builder"),
    ("https://www.youtube.com/@cline-bot", "official_platform", 9, "Cline official autonomous coding agent channel"),
    ("https://www.youtube.com/@googleantigravity", "official_platform", 9, "Google agentic development platform signal"),
    ("https://www.youtube.com/@warpdotdev", "official_platform", 9, "Warp agentic terminal/development environment"),
    ("https://www.youtube.com/@github", "official_platform", 9, "GitHub/Copilot source and developer platform signal"),
    ("https://www.youtube.com/@sourcegraph", "official_platform", 8, "Sourcegraph/Cody enterprise code-agent context"),
    ("https://www.youtube.com/@continuedev", "official_platform", 8, "Open-source AI code assistant platform"),
    ("https://www.youtube.com/@nvidiadeveloper", "official_platform", 8, "Developer ecosystem with AI engineering and agent tooling"),
    ("https://www.youtube.com/@sonarsource", "official_platform", 8, "Code quality/security angle around AI coding adoption"),
    ("https://www.youtube.com/@leonvanzyl", "creator_builder", 10, "High-signal practical AI builds, agents, and coding workflows"),
    ("https://www.youtube.com/@alexfinnofficial", "creator_builder", 10, "Dedicated vibe-coding channel covering Claude Code and Codex"),
    ("https://www.youtube.com/@alex.followell", "creator_builder", 10, "Claude Code tutorials, n8n automation, and coding-agent workflows"),
    ("https://www.youtube.com/@avtharai", "creator_builder", 10, "AI coding tool reviews and practical Claude/Cursor/v0 workflows"),
    ("https://www.youtube.com/@aioriented", "creator_builder", 10, "Practical Codex, Claude Code, Cursor, and agentic dev tutorials"),
    ("https://www.youtube.com/@ai-luke", "creator_builder", 10, "Builder channel focused on Claude Code, Codex, apps, and automations"),
    ("https://www.youtube.com/@nicksaraev", "creator_builder", 10, "Strong Claude Code, Codex, n8n, and AI tool adoption signal"),
    ("https://www.youtube.com/@colemedin", "creator_builder", 10, "AI agents and AI coding assistants with practical builds"),
    ("https://www.youtube.com/@rileybrownai", "creator_builder", 10, "AI agents for knowledge work and vibe-coding market signal"),
    ("https://www.youtube.com/@adriantwarog", "creator_builder", 9, "AI websites/apps and Claude/OpenAI Codex builder content"),
    ("https://www.youtube.com/@etishagarg", "creator_builder", 9, "Developer-oriented AI product and coding workflow channel"),
    ("https://www.youtube.com/@theaiuniversity", "creator_builder", 9, "AI tools tutorials with Claude/Codex coverage"),
    ("https://www.youtube.com/@mikeynocode", "no_code_vibe", 9, "No-code and AI app-building channel relevant to prompt-to-product demand"),
    ("https://www.youtube.com/@swiftui-awareness", "agentic_dev", 9, "Agentic coding, Codex, and Apple developer workflow angle"),
    ("https://www.youtube.com/@bitfumes", "agentic_dev", 9, "Coding channel with Claude, LLM, and AI development coverage"),
    ("https://www.youtube.com/@bencord", "creator_builder", 9, "Spanish vibe-coding, AI agents, and digital products"),
    ("https://www.youtube.com/@ayyaztech", "agentic_dev", 9, "AI developer tools, automation, and coding productivity"),
    ("https://www.youtube.com/@codingclassroom-f5u", "agentic_dev", 9, "AI coding education focused on current coding-agent workflows"),
    ("https://www.youtube.com/@codingtechnyks", "agentic_dev", 9, "Agentic AI, RAG, MCP, and full-stack engineering"),
    ("https://www.youtube.com/@frontierailabs", "creator_builder", 9, "Builds products with Claude and teaches Claude-based workflows"),
    ("https://www.youtube.com/@duncanrogoff", "creator_builder", 9, "Focused Claude Code education"),
    ("https://www.youtube.com/@goose-oss", "open_source_agent", 9, "Open-source on-machine AI coding agent"),
    ("https://www.youtube.com/@hustlinglabs", "creator_builder", 9, "Tests Cursor, Lovable, Claude MCP, and no-code AI tools"),
    ("https://www.youtube.com/@nicekateai", "creator_builder", 9, "AI programming, Claude Code, Codex, Cursor, and agents"),
    ("https://www.youtube.com/@kevinstratvert", "mainstream_signal", 8, "Large mainstream tutorial channel for AI/coding adoption signals"),
    ("https://www.youtube.com/@mehulmpt", "dev_influencer", 8, "Software, AI, security, and system-design audience overlap"),
    ("https://www.youtube.com/@internetmadecoder", "dev_influencer", 8, "Learning-to-code and AI startup/dev audience"),
    ("https://www.youtube.com/@creatormagicai", "creator_builder", 8, "AI coding tools, workflow automation, and tool reviews"),
    ("https://www.youtube.com/@tinahuang1", "mainstream_signal", 8, "AI, coding, tech career, and tool-adoption signal"),
    ("https://www.youtube.com/@mattpocockuk", "dev_influencer", 8, "Real-engineer framing around AI coding workflows"),
    ("https://www.youtube.com/@t3dotgg", "dev_influencer", 8, "High-signal TypeScript/dev audience and AI coding commentary"),
    ("https://www.youtube.com/@seanmatthewai", "creator_builder", 8, "Build apps with Claude Code, v0, and Cursor"),
    ("https://www.youtube.com/@clouddevengineering", "agentic_dev", 8, "Agentic tooling, MCP servers, and developer systems"),
    ("https://www.youtube.com/@subhankaladi", "agentic_dev", 8, "Practical AI engineering and modern developer workflows"),
    ("https://www.youtube.com/@thecodebear", "agentic_dev", 8, "Coding channel with AI/Python/JavaScript overlap"),
    ("https://www.youtube.com/@codingwithsagarcw", "agentic_dev", 8, "Data/AI/ML coding channel with AI tool overlap"),
    ("https://www.youtube.com/@pythonsimplified", "dev_influencer", 8, "Python/software audience useful for AI coding adoption"),
    ("https://www.youtube.com/@codingcrashcourses8533", "agentic_dev", 8, "Software engineer in AI space, practical teaching angle"),
    ("https://www.youtube.com/@ailabs-393", "creator_builder", 8, "AI coding tools and models for builders"),
    ("https://www.youtube.com/@devexpert_io", "agentic_dev", 8, "AI for developers without empty vibe-coding framing"),
    ("https://www.youtube.com/@codingwithroby", "agentic_dev", 8, "Backend development shifting into AI coding and architecture"),
    ("https://www.youtube.com/@arctutorials", "agentic_dev", 8, "LangChain, LLMOps, and AI architecture education"),
    ("https://www.youtube.com/@bmadcode", "agentic_dev", 8, "Production software leadership plus Claude Code/AI coding"),
    ("https://www.youtube.com/@iamnamangupta22", "creator_builder", 8, "Vibe-coding and AI software development tutorials"),
    ("https://www.youtube.com/@franknillard", "agentic_dev", 8, "Agentic coding and AI-agent founder experience"),
    ("https://www.youtube.com/@mattpalmer", "creator_builder", 8, "Vibe-coding and AI tools testing"),
    ("https://www.youtube.com/@aidrivencoder", "creator_builder", 8, "Turns ideas into deployed apps using AI dev tools"),
    ("https://www.youtube.com/@mikeyvibecoding", "no_code_vibe", 8, "Dedicated vibe-coding tutorial channel"),
    ("https://www.youtube.com/@derekcheungsa", "automation_builder", 8, "AI agents automation from a non-coder/no-code angle"),
    ("https://www.youtube.com/@davidsonnocode", "automation_builder", 8, "AI, automation, agents, SaaS, and no-code development"),
    ("https://www.youtube.com/@flutteragentic", "agentic_dev", 8, "Flutter plus AI agent coding practices"),
    ("https://www.youtube.com/@theaiarchitectswithtom", "automation_builder", 8, "AI automation/workflow systems for builders"),
    ("https://www.youtube.com/@elie2222", "open_source_agent", 8, "Open source, Cursor, and AI assistant/product building"),
    ("https://www.youtube.com/@programadorhumilde3", "creator_builder", 8, "Portuguese vibe-coding and tech builder channel"),
    ("https://www.youtube.com/@rodrigodelatorre-ai", "creator_builder", 8, "Spanish vibe-coding/SaaS/AI architecture builder"),
    ("https://www.youtube.com/@thiagodigitalz", "no_code_vibe", 8, "Lovable, Bubble, no-code/AI-code solution building"),
    ("https://www.youtube.com/@johnelderai", "ai_tools_signal", 7, "AI tools, Claude Code, OpenClaw, and fast-moving tool reviews"),
    ("https://www.youtube.com/@syncbricks", "automation_builder", 7, "AI automation, agents, and coding workflows"),
    ("https://www.youtube.com/@diysmartcode", "agentic_dev", 7, "AI IDEs and developer tooling tutorials"),
    ("https://www.youtube.com/@pavanadhav", "dev_influencer", 7, "Short-form dev/AI/security/system design channel"),
    ("https://www.youtube.com/@tommyyipxyz", "creator_builder", 7, "Live AI website builds with Claude Code and Replit"),
    ("https://www.youtube.com/@codewithclinton", "agentic_dev", 7, "Full-stack development plus AI-assisted coding"),
    ("https://www.youtube.com/@sebastianhardyai", "automation_builder", 7, "Claude Code tutorials and AI automation for businesses"),
    ("https://www.youtube.com/@aicoding2010", "agentic_dev", 7, "AI engineering and AI coding tutorials"),
    ("https://www.youtube.com/@tylerreedai", "creator_builder", 7, "Software engineer explaining AI tools and building with AI"),
    ("https://www.youtube.com/@markshust", "agentic_dev", 7, "Production apps with Claude Code and AI coding"),
    ("https://www.youtube.com/@masyntech", "creator_builder", 7, "Vibe coding and AI-powered full-stack development"),
    ("https://www.youtube.com/@aibites", "ai_tools_signal", 7, "LLM/AI concept explainers useful for agentic-dev context"),
    ("https://www.youtube.com/@enterproai", "no_code_vibe", 7, "No-code AI dev agent and prompt-to-dev positioning"),
    ("https://www.youtube.com/@lungcode-ai-agent-automation", "automation_builder", 7, "AI agent/workflow automation and programming tutorials"),
    ("https://www.youtube.com/@growproduct", "mainstream_signal", 7, "AI PM/product audience around building and AI tools"),
    ("https://www.youtube.com/@aiagentsaz", "agentic_dev", 7, "Practical AI agents education"),
    ("https://www.youtube.com/@aiautomationclips", "automation_builder", 7, "AI agent systems and automation clips"),
    ("https://www.youtube.com/@socialmediacompanynl", "automation_builder", 7, "AI agents for organizations and business workflows"),
    ("https://www.youtube.com/@automation-tribe", "automation_builder", 7, "AI/no-code workflow optimization with automation tools"),
    ("https://www.youtube.com/@manus-ai", "ai_tools_signal", 7, "General AI agent product signal"),
    ("https://www.youtube.com/@sabrina_ramonov", "mainstream_signal", 7, "AI prompts, playbooks, agents, and creator adoption"),
    ("https://www.youtube.com/@jessautomates", "automation_builder", 7, "AI agents education and automation angle"),
    ("https://www.youtube.com/@nateherk", "automation_builder", 7, "Business AI automations and agency-style market signal"),
    ("https://www.youtube.com/@wscubeaiandtechschool", "ai_tools_signal", 7, "AI, automation, agents, GPTs, and modern tech education"),
    ("https://www.youtube.com/@mr2coool", "agentic_dev", 7, "Generative AI, agentic AI, and hands-on automation tutorials"),
    ("https://www.youtube.com/@cuttingedgeschool", "ai_tools_signal", 7, "AI agent training and applied automation education"),
    ("https://www.youtube.com/@viDev9858", "creator_builder", 7, "Claude Code workflows and AI builders content"),
]


async def main():
    urls = [url for url, _, _, _ in SELECTION]
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

    by_url = {row["url"].rstrip("/").lower(): dict(row) for row in rows}
    final = []
    missing = []
    seen = set()
    for url, category, audit_score, reason in SELECTION:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        row = by_url.get(key)
        if not row:
            missing.append(url)
            continue
        row["category"] = category
        row["audit_score"] = audit_score
        row["selection_reason"] = reason
        final.append(row)
        if len(final) == 100:
            break

    fields = [
        "rank",
        "audit_score",
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

    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    for idx, row in enumerate(final, start=1):
        writer.writerow(
            {
                "rank": idx,
                "audit_score": row["audit_score"],
                "category": row["category"],
                "title": row["title"],
                "url": row["url"],
                "channel_id": row["channel_id"],
                "subscribers": row["subscribers"],
                "views": row["views"],
                "verified": row["verified"],
                "selection_reason": row["selection_reason"],
                "description_snippet": row["description"][:280],
            }
        )

    if missing:
        missing_path = Path("reports/research_channels/claude_codex_missing_urls.txt")
        try:
            missing_path.write_text("\n".join(missing) + "\n", encoding="utf-8")
        except Exception:
            pass
        print(f"missing={len(missing)}", file=sys.stderr)
        for url in missing:
            print(f"MISSING {url}", file=sys.stderr)


if __name__ == "__main__":
    import sys

    asyncio.run(main())
