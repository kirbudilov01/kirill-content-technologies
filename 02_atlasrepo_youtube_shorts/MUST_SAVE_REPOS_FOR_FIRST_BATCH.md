# Must-save repos for first batch

Дата: 2026-06-19.

Цель: выбрать не просто хорошие repo, а такие, после которых зритель думает: "мне надо сохранить этот канал, тут находят реально полезные штуки".

Фильтр жесткий:

1. **На слуху / социальное доказательство** — много stars, известность, узнаваемость в AI/dev/product среде.
2. **Вау за 3 секунды** — легко объяснить одним человеческим предложением.
3. **Сразу хочется тестить** — repo решает понятную боль.
4. **Снимается визуально** — есть UI, demo, workflow, output, а не только библиотека.
5. **Связь с AtlasRepo** — органично: "мы нашли/отобрали это в AtlasRepo".

## Финальный вывод

Предыдущая "сочная" десятка была слишком агентной и местами слишком внутренней. Для первого удара лучше микс:

- 6-7 repo, которые уже на слуху и дают доверие;
- 3-4 repo, которые выглядят как свежая находка и дают эффект "где вы это откопали?".

## Tier S: брать почти обязательно

### 1. Ollama

**URL:** https://github.com/ollama/ollama  
**GitHub stars на 2026-06-19:** ~174k  
**Почему на слуху:** один из главных символов local AI.  
**Вау-хук:** `Stop renting AI — run powerful models locally.`  
**Почему хочется тестить:** человек сразу понимает: можно запустить модели у себя.  
**Что снять:** install, model pull/run, локальный чат/CLI, список моделей.

### 2. Open WebUI

**URL:** https://github.com/open-webui/open-webui  
**GitHub stars на 2026-06-19:** ~142k  
**Почему на слуху:** популярный self-hosted AI workspace поверх локальных/облачных моделей.  
**Вау-хук:** `Build your own ChatGPT workspace.`  
**Почему хочется тестить:** понятный UI, сразу видно продукт.  
**Что снять:** interface, model connection, chat, workspace/settings.

### 3. Dify

**URL:** https://github.com/langgenius/dify  
**GitHub stars на 2026-06-19:** ~146k  
**Почему на слуху:** один из самых известных open-source AI app builders.  
**Вау-хук:** `Stop building AI products from scratch.`  
**Почему хочется тестить:** можно быстро собрать assistant/workflow/RAG app.  
**Что снять:** app builder, workflow, RAG/knowledge, published app.

### 4. ComfyUI

**URL:** https://github.com/comfyanonymous/ComfyUI  
**GitHub stars на 2026-06-19:** ~118k  
**Почему на слуху:** культовый node-based UI для image generation.  
**Вау-хук:** `This is Photoshop for AI workflows.`  
**Почему хочется тестить:** сильный визуал, nodes, картинки, output.  
**Что снять:** node graph, prompt, generated image, workflow gallery.

### 5. browser-use

**URL:** https://github.com/browser-use/browser-use  
**GitHub stars на 2026-06-19:** ~100k  
**Почему на слуху:** один из самых понятных browser-agent проектов.  
**Вау-хук:** `Stop clicking buttons — let an AI use websites.`  
**Почему хочется тестить:** очень визуально: AI реально кликает сайт.  
**Что снять:** browser task, agent action, result.

### 6. MoneyPrinterTurbo

**URL:** https://github.com/harry0703/MoneyPrinterTurbo  
**GitHub stars на 2026-06-19:** ~90k  
**Почему на слуху:** сильный curiosity title + AI short video generation.  
**Вау-хук:** `Generate Shorts, Reels and TikToks with AI.`  
**Почему хочется тестить:** creator/founder аудитория сразу понимает пользу.  
**Что снять:** input topic, generation flow, output short.

### 7. OpenHands

**URL:** https://github.com/All-Hands-AI/OpenHands  
**GitHub stars на 2026-06-19:** ~78k  
**Почему на слуху:** AI software engineer — понятная категория после Devin/Codex/Claude Code хайпа.  
**Вау-хук:** `Stop writing every line of code yourself.`  
**Почему хочется тестить:** дает ощущение "AI реально работает в repo".  
**Что снять:** task UI, code diff, issue/task, result.

## Tier A: добавить для свежего вау

### 8. Multica

**URL:** https://github.com/multica-ai/multica  
**GitHub stars на 2026-06-19:** ~37k  
**Почему вау:** agent teammates — не один агент, а система управления AI-командой.  
**Вау-хук:** `Turn coding agents into real teammates.`  
**Что снять:** tasks/issues, agent assignment, progress tracking, team dashboard.  
**Комментарий:** обязательно добавить, как ты сказал. Хорошо продает идею one-person company.

### 9. Twenty CRM

**URL:** https://github.com/twentyhq/twenty  
**GitHub stars на 2026-06-19:** ~50k  
**Почему вау:** open-source Salesforce alternative designed for AI. Это закрывает не "еще одного агента", а бизнес-слой: лиды, клиенты, pipeline, CRM.  
**Вау-хук:** `Stop paying for Salesforce before you even have a sales team.`  
**Что снять:** CRM dashboard, contacts/companies, pipeline, AI angle/automation if visible.  
**Комментарий:** добавляем, чтобы список не дублировал agent tools и выглядел как настоящий стек one-person company.

### 10. Postiz

**URL:** https://github.com/gitroomhq/postiz-app  
**GitHub stars на 2026-06-19:** ~32k  
**Почему вау:** creator/founder use-case, open-source social scheduling.  
**Вау-хук:** `Stop paying for social media scheduling tools.`  
**Что снять:** calendar, composer, queue, connected channels.  
**Комментарий:** не самый "AI magic", зато сразу понятно, зачем тестить.

## Strong alternates

Использовать, если один из top-10 плохо снимается или хочется повернуть выпуск в другую сторону.

### UI-TARS Desktop

**URL:** https://github.com/bytedance/UI-TARS-desktop  
**Stars:** ~37k  
**Почему:** AI работает с desktop/UI. Вау сильный, но нужно понятное демо.

### mem0

**URL:** https://github.com/mem0ai/mem0  
**Stars:** ~59k  
**Почему:** memory layer для agents. Полезно, но сложнее объяснить массово.

### Flowise

**URL:** https://github.com/FlowiseAI/Flowise  
**Stars:** ~54k  
**Почему:** visual AI agents/workflows. Понятнее, чем многие agent frameworks.

### AnythingLLM

**URL:** https://github.com/Mintplex-Labs/anything-llm  
**Stars:** ~62k  
**Почему:** local-first AI workspace. Хорошая альтернатива Open WebUI/LibreChat.

### AppFlowy

**URL:** https://github.com/AppFlowy-IO/AppFlowy  
**Stars:** ~73k  
**Почему:** open-source Notion-like workspace with AI. Хорошо для "company OS".

### Twenty CRM

**URL:** https://github.com/twentyhq/twenty  
**Stars:** ~50k  
**Почему:** open-source Salesforce alternative designed for AI. Хорошо для one-person company business stack.

### Coolify

**URL:** https://github.com/coollabsio/coolify  
**Stars:** ~57k  
**Почему:** self-hosted Vercel/Heroku/Netlify alternative. Очень полезно, но меньше AI-вау.

## Что не ставить в первый топ-10

### MarkItDown

Stars большие, Microsoft, полезно. Но для первого "must-save" ролика это слабее визуально: file conversion не вызывает такого "я побежал тестить" у широкой аудитории.

### Activepieces

Практично, но воспринимается как automation platform. После отказа от n8n не надо подменять его менее известным n8n-like инструментом в первом ударе.

### Langfuse / vLLM / Sentry / Bruno / Metabase

Сильные и известные, но это больше dev/infra/professional stack. Их лучше вынести в отдельное видео: `Dev tools that actually save a solo founder`.

## Recommended Video 1 final title

**Primary:** `These 10 GitHub Repos Can Build a One-Person AI Company`

**Alt 1:** `I Found 10 Open-Source AI Tools You’ll Want to Test Immediately`

**Alt 2:** `10 GitHub Repos That Feel Like Hiring a Team`

## Recommended Video 1 final top-10

Порядок выбран для внимания, а не по stars:

1. browser-use
2. MoneyPrinterTurbo
3. Ollama
4. Open WebUI
5. Dify
6. ComfyUI
7. OpenHands
8. Multica
9. Twenty CRM
10. Postiz

## Anti-duplication logic

Каждый repo должен закрывать отдельную роль:

| Role | Repo |
|---|---|
| Browser worker | browser-use |
| Short video generation | MoneyPrinterTurbo |
| Local AI engine | Ollama |
| AI workspace | Open WebUI |
| AI app builder | Dify |
| Creative/image workflow | ComfyUI |
| Coding worker | OpenHands |
| Agent team management | Multica |
| CRM / business operations | Twenty CRM |
| Content distribution | Postiz |

`Deer Flow`, `UI-TARS`, `Flowise`, `AnythingLLM`, `AppFlowy`, `Coolify`, `mem0` остаются strong alternates. Их можно менять местами под конкретный угол, но в первом списке не надо ставить слишком много agent/workspace tools одновременно.

## Why this top-10 is stronger

Старый список был "умный". Этот список — "сохрани канал".

- Ollama / Open WebUI / Dify / ComfyUI — большие, узнаваемые, доверие.
- browser-use / OpenHands — AI реально действует.
- MoneyPrinterTurbo / Postiz — creator/founder utility.
- Multica — свежая вау-находка про AI-teammates.
- Twenty CRM — бизнес-слой, чтобы список был не только про агентов, а реально про one-person company.

## Micro-SaaS idea for Video 2

**Название:** `Open-Source Tool Radar for Content Creators`

**Что делает:** пользователь вводит нишу, например `AI video tools`, `content automation`, `solo founder stack`. Сервис показывает 10 open-source repo, группирует их по роли, дает краткий verdict `save/test/skip`, генерирует 3 идеи Shorts и 1 long-form тему по каждому repo.

**Почему это хороший первый micro-SaaS:** он напрямую продвигает AtlasRepo, использует нашу реальную базу, понятен аудитории канала и визуально легко снимается. Это не выдуманный B2B-монстр, а маленький продукт, который можно показать за вечер.

**Минимальный экран продукта:**

1. Input: niche/topic.
2. Results: 10 repo cards.
3. Each card: role, GitHub URL, stars, why useful, save/test/skip.
4. Content ideas: 3 Shorts + 1 long-form.
5. Export: partner shooting brief / content table.
