# ATLAS REPO — Strategy Bible V2

Цель: сделать серию, которая выглядит не как каталог репозиториев, а как YouTube-шоу про AI-agent войны, хайп, инструменты и рынок. Atlas Repo внутри роликов — radar/proof layer.

## Research basis

- Workbook: `FABRICBOT_ECOSYSTEM_...xlsx`, листы `Videos_7d`, `Viral_Shorts`, `Project_Reports`.
- Metadata/captions: yt-dlp metadata + auto captions по 7 ключевым референсам. Субтитры использованы только для структурного анализа, без копирования текста.
- Public data: `https://atlasrepo.com/api/scout-feed`, публичный feed Atlas Repo.

## Concrete YouTube references

| Reference | URL | Pattern | What to steal structurally |
|---|---|---|---|
| From Zero to Your First AI Agent in 25 Minutes | https://www.youtube.com/watch?v=EH5jx5qPabU | From Zero / time-bound build | Promise результата за 25 минут; первые главы быстро объясняют agent vs automation, затем переходят в компоненты и практику. |
| Tragic mistake... Anthropic leaks Claude’s source code | https://www.youtube.com/watch?v=mBHRPeg8zPU | Drama / leak / danger | Короткое видео, сильный конфликт в названии, без долгого setup. Хорошо для news-drama формата. |
| Model Context Protocol (MCP) Explained for Beginners | https://www.youtube.com/watch?v=E2DEHOEbzks | Explainer with demo | Сначала проблема: LLM не умеет действовать. Потом агенты, tools, MCP, demo. Это идеальная структура для обучающего видео. |
| Hermes Agent Tutorial | https://www.youtube.com/watch?v=W_ZgH0WPayo | Tutorial + hype audit | Начинает с demo, потом объясняет background, learning loop, MCP/Supabase, live demo, pricing, limitation. |
| OpenClaw + MiniMax Agent | https://www.youtube.com/watch?v=W3P8FnhihzQ | Personal assistant demo | Сначала morning briefing demo, потом что такое агент, setup integrations, cloud 24/7, skills hub. |
| I Tried 100+ Claude Code Skills | https://www.youtube.com/watch?v=eRS3CmvrOvA | I tested / ranking | Четкая структура: intro, skill #1-#6, bonus. Это шаблон для skills/list videos. |
| Cursor AI: полный гайд | https://www.youtube.com/watch?v=eXp8TC0Sm6o | Full guide | 25 глав: проблема, что такое Cursor, settings, MCP, rules, project rules, context. Формат плотного гайда. |

## Reference metadata notes

- **Tragic mistake... Anthropic leaks Claude’s source code** — views: 3222220, duration: 7:22, chapters: 0.
- **I Tried 100+ Claude Code Skills. These 6 Are The Best** — views: 347628, duration: 13:39, chapters: 9. Chapter pattern: Intro -> Skill #1 -> Skill #2 -> Skill #3 -> Skill #4 -> Skill #5.
- **Cursor AI: полный гайд по вайб-кодингу (настройки, фишки, rules, MCP)** — views: 352585, duration: 27:06, chapters: 25. Chapter pattern: Start -> What problem does Cursor solve? -> What is Cursor? -> Basic settings. Auto-run -> MCP in Cursor -> Rules.
- **From Zero to Your First AI Agent in 25 Minutes (No Coding)** — views: 3819827, duration: 25:57, chapters: 19. Chapter pattern: Intro -> What is an Agent? -> Agents vs. Automations -> 3 Main Components -> Types of Systems -> Guardrails.
- **Hermes Agent Tutorial: The Self-Improving AI Assistant with DeepSeek v4** — views: 217876, duration: 10:38, chapters: 8. Chapter pattern: Hermes Agent Demo: Build a Database Table from Telegram -> What is Hermes Agent + Nous Research Background -> Self-Improving Learning Loop Explained -> Connecting Hermes Agent to Supabase via MCP -> Live Demo: Building a CRM from Telegram -> Full Stack Pricing (~$10/Month).
- **Model Context Protocol (MCP) Explained for Beginners: AI Flight Booking Demo!** — views: 1152238, duration: 24:09, chapters: 12. Chapter pattern: Introduction to AI Agents & MCPs -> ChatGPT Breakdown -> Why LLMs Can't Take Action -> What Are AI Agents? The Game-Changing Solution -> Real-world Agent Examples: IDEs, Cursor, GitHub Copilot -> How to get started with AI Agents?.
- **OpenClaw + MiniMax Agent: Personal AI Assistant That Uses Gmail, Calendar & 200+ Tools** — views: 201602, duration: 9:21, chapters: 7. Chapter pattern: AI Assistant Morning Briefing Demo -> What Is MiniMax Agent -> Desktop App: Build Apps & Research Reports -> Composio Setup: Gmail & Google Calendar Integration -> MaxClaw: Deploy Your Assistant to the Cloud 24/7 -> Experts Marketplace & Skills Hub.

## Winning title formulas

- `From Zero to [Outcome] in [Time]`
- `[Tool A] vs [Tool B]: I Built the Same Thing in Both`
- `I Tried [Big Number] [Tools/Skills]. These [N] Are Actually Useful`
- `[Famous Tool] Just Dropped… Does It Kill [Existing Tool]?`
- `[Famous Person/File] vs [New Standard]: Which Works Better?`
- `Stop [Bad Outcome] with [Famous Tool]`
- `[Danger]: Why AI Agents Are the Next [Security/Cost/Quality] Nightmare`
- `I Rebuilt a [$X] AI App in [Time] with Open-Source Repos`

## Production cadence

- 3 Shorts/day for 30+ days.
- 1 long-form/week minimum, 2/week if production catches up.
- Each long-form creates 5-10 Shorts.
- Weekly review: 3-sec hold, average view duration, comments per 1k views, saves, subs per video.
