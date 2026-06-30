# Repo wow score and revised top list

Дата: 2026-06-19.

Задача: оценить, насколько текущие repo реально "вау" для первых видео, и пересобрать пачку так, чтобы это был не просто полезный open-source список, а сильная YouTube-начинка.

## Критерии оценки

Оцениваем не только полезность. Для видео важнее смесь:

1. **Wow factor** — зритель за 5 секунд понимает: "ничего себе, такое уже есть?"
2. **Visual proof** — можно ли снять красивый/понятный экран.
3. **One-person company leverage** — заменяет ли человека, подписку, отдел или кусок процесса.
4. **Freshness / not obvious** — не выглядит ли как банальный список из n8n/Cursor/ChatGPT.
5. **AtlasRepo fit** — органично ли звучит "мы нашли это через AtlasRepo".

Шкала: 10 — надо брать почти обязательно; 8 — сильный кандидат; 6-7 — полезно, но не всегда вау; ниже 6 — не в первую пачку.

---

## Оценка текущей десятки

| Repo | Wow | Вердикт | Комментарий |
|---|---:|---|---|
| OpenHands | 8.5 | оставить | Сильный фрейм: AI software engineer внутри repo. Хорошо для "перестань писать каждую строку кода". |
| browser-use | 9.0 | оставить | Очень визуально: агент кликает сайты как человек. Один из лучших для Shorts. |
| Dify | 7.5 | оставить условно | Полезно и зрелое, но уже не супер-новинка. Нужен хороший proof: "AI app за 10 минут". |
| Open WebUI | 7.0 | под вопросом | Полезно, но визуально похоже на очередной AI chat. Оставлять только если нужен self-hosted AI workspace. |
| Postiz | 8.0 | оставить | Хороший creator/founder use-case, визуальный календарь, понятная замена SaaS. |
| MoneyPrinterTurbo | 9.0 | оставить | Очень сильный вау для контента: AI генерирует Shorts/Reels/TikToks. Надо честно показать качество. |
| OpenMontage | 9.0 | оставить | Жирная тема: agentic video production. Может быть raw, но звучит свежо и мощно. |
| mem0 | 7.5 | оставить условно | Важная инфраструктура памяти, но сложно показать массово. Лучше как "AI remembers everything". |
| MarkItDown | 6.5 | убрать из первой десятки | Полезно, но не вау. Хорошо для второго слоя/документного workflow, не для первого хука. |
| Activepieces | 6.5 | убрать из первой десятки | Практично, но выглядит как n8n/automation platform. Не самый сок для первого видео. |

---

## Репозитории, которые выглядят более "вау"

### 1. Multica

**Repo:** `multica-ai/multica`  
**URL:** https://github.com/multica-ai/multica  
**Почему вау:** превращает coding agents в teammates: assign tasks, track progress, compound skills. Это сильнее, чем "еще один агент": это уже образ AI-команды.

**Хук:** Stop managing tasks alone — turn coding agents into teammates.

**Что снять:** dashboard/issues, agent tasks, progress tracking, human + agent team workflow.

**Оценка:** 9.0

### 2. Deer Flow

**Repo:** `bytedance/deer-flow`  
**URL:** https://github.com/bytedance/deer-flow  
**Почему вау:** long-horizon SuperAgent: researches, codes, creates; sandboxes, memories, tools, subagents. Это хорошо ложится на "AI может вести длинные задачи".

**Хук:** Stop using AI for tiny prompts — this agent handles long tasks.

**Что снять:** repo README, architecture/flow, task demo, output artifact.

**Оценка:** 9.0

### 3. UI-TARS Desktop

**Repo:** `bytedance/UI-TARS-desktop`  
**URL:** https://github.com/bytedance/UI-TARS-desktop  
**Почему вау:** multimodal desktop agent stack. Визуально сильнее обычного чатбота: AI видит экран/интерфейс и действует.

**Хук:** Stop explaining screens to AI — let it use the desktop.

**Что снять:** desktop UI, visual agent actions, task execution, result.

**Оценка:** 8.8

### 4. PraisonAI

**Repo:** `MervinPraison/PraisonAI`  
**URL:** https://github.com/MervinPraison/PraisonAI  
**Почему вау:** "Hire a 24/7 AI Workforce" — формулировка прямо YouTube-ready. Research, plan, code, execute tasks.

**Хук:** Stop hiring for every task — spin up an AI workforce.

**Что снять:** quick setup, agents/team config, task execution, output.

**Оценка:** 8.5

### 5. AgentScope

**Repo:** `agentscope-ai/agentscope`  
**URL:** https://github.com/agentscope-ai/agentscope  
**Почему вау:** build and run agents you can see, understand and trust. Менее попсово, но хорошо как serious agent framework.

**Хук:** Stop running black-box agents.

**Что снять:** agent run visualization, logs, workflow, output.

**Оценка:** 8.0

### 6. Hyperframes

**Repo:** `heygen-com/hyperframes`  
**URL:** https://github.com/heygen-com/hyperframes  
**Почему вау:** "Write HTML. Render video. Built for agents." Очень вкусно для content/video stack.

**Хук:** Stop editing videos manually — render video from code.

**Что снять:** HTML input, render process, output video frame.

**Оценка:** 8.5

### 7. video-use

**Repo:** `browser-use/video-use`  
**URL:** https://github.com/browser-use/video-use  
**Почему вау:** edit videos with coding agents. Логично рядом с OpenMontage и MoneyPrinterTurbo.

**Хук:** Stop dragging clips by hand — let coding agents edit video.

**Что снять:** repo, editing command/task, timeline/output.

**Оценка:** 8.2

### 8. droidrun / mobilerun

**Repo:** `droidrun/droidrun`  
**URL:** https://github.com/droidrun/droidrun  
**Почему вау:** mobile device automation with natural language. Хорошо смотрится, потому что не browser-only.

**Хук:** Stop tapping your phone — automate mobile apps with language.

**Что снять:** mobile screen, command, action, result.

**Оценка:** 8.4

### 9. agentmemory

**Repo:** `rohitg00/agentmemory`  
**URL:** https://github.com/rohitg00/agentmemory  
**Почему вау:** persistent memory for AI coding agents. Может заменить/усилить mem0 в dev-focused списке.

**Хук:** Stop resetting your AI agent every session.

**Что снять:** before/after memory, benchmark/README, agent remembers context.

**Оценка:** 7.8

### 10. Hermes Agent

**Repo:** `NousResearch/hermes-agent`  
**URL:** https://github.com/NousResearch/hermes-agent  
**Почему вау:** сильное имя и большой интерес, но тема может стать сложной. Лучше для отдельного video/battle, чем для первого generic top-10.

**Хук:** This agent grows with your projects.

**Что снять:** desktop/docs, skills, project memory, tool output.

**Оценка:** 8.2, но лучше backup/отдельный выпуск.

---

## Revised Top 10: самый сильный список для Video 1

Это версия "самый сок", если цель — не просто полезный стек, а вау-подборка для YouTube.

| # | Repo | URL | Роль | Почему в топе |
|---|---|---|---|---|
| 1 | Multica | https://github.com/multica-ai/multica | AI teammates / agent project management | Самый сильный новый нарратив: не один агент, а команда агентов |
| 2 | OpenHands | https://github.com/All-Hands-AI/OpenHands | AI software engineer | Понятно заменяет часть coding work |
| 3 | browser-use | https://github.com/browser-use/browser-use | Browser-operating agent | Лучший visual proof: агент кликает сайты |
| 4 | UI-TARS Desktop | https://github.com/bytedance/UI-TARS-desktop | Multimodal desktop agent | Сильнее обычного browser-agent: AI работает с UI/desktop |
| 5 | Deer Flow | https://github.com/bytedance/deer-flow | Long-horizon superagent | Агент не просто отвечает, а ведет длинные задачи |
| 6 | MoneyPrinterTurbo | https://github.com/harry0703/MoneyPrinterTurbo | AI short video generation | Очень понятный creator вау |
| 7 | OpenMontage | https://github.com/calesthio/OpenMontage | Agentic video production | Свежая история про video production agents |
| 8 | Postiz | https://github.com/gitroomhq/postiz-app | Social distribution | Практичный слой: контент нужно публиковать |
| 9 | Dify | https://github.com/langgenius/dify | AI app builder | Зрелый способ быстро собрать AI product |
| 10 | mem0 или agentmemory | https://github.com/mem0ai/mem0 / https://github.com/rohitg00/agentmemory | Memory layer | Нужен слой памяти, но выбрать по тому, что лучше снимается |

## Что убрать из первой десятки

### MarkItDown

Оставить в backup. Это полезная штука, но для первого ролика "самый сок" она проигрывает агентам и video/content tools. Можно использовать во втором видео, где строим micro-SaaS/content pipeline.

### Activepieces

Оставить для Video 2, где нужна сборка workflow. В Video 1 он слишком похож на n8n-замену и не дает максимального вау.

### Open WebUI

Оставить под вопросом. Полезно, но "свой ChatGPT" уже не звучит как открытие. Если нужна self-hosted AI workspace тема, можно вернуть вместо Dify или memory repo.

---

## Лучший вариант для 10 Shorts

Для Shorts я бы не делал полностью ту же десятку, если часть repo сложная. Shorts должны быть визуальными. Поэтому:

1. Multica — agent teammates.
2. OpenHands — AI software engineer.
3. browser-use — agent clicks websites.
4. UI-TARS Desktop — AI controls desktop.
5. MoneyPrinterTurbo — AI generates Shorts.
6. OpenMontage — agentic video production.
7. Postiz — schedules content.
8. Dify — builds AI apps.
9. droidrun — controls mobile apps.
10. mem0/agentmemory — agent remembers context.

**Backup for Shorts:** Hyperframes, video-use, Deer Flow, PraisonAI, AgentScope.

---

## Мой честный вывод

Текущая пачка была хорошей как "полезный open-source stack", но не вся была вау. Для первого удара я бы сделал пачку агрессивнее:

- больше agents-as-workers;
- больше browser/desktop/mobile control;
- больше content/video factory;
- меньше скучной инфраструктуры;
- меньше obvious automation.

И обязательно добавить `Multica`: он лучше всего закрывает идею "one-person company" через образ AI-команды.

