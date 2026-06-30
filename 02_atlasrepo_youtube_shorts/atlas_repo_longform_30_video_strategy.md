# ATLAS REPO — 30 long-form videos strategy

Основа: YouTube research workbook + публичный AtlasRepo feed (`https://atlasrepo.com/api/scout-feed`).

## Аналитика

- **In research file, Videos_7d has 6046 long videos; 3682 matched AI/dev/tooling patterns; relevant videos total ~604M views.** The category is big enough for long-form; we should not stay Shorts-only.
- **Relevant long-form median duration ~14 min; relevant 100k+ median duration ~25 min.** Target 12-30 minutes. 8-minute videos only for single repo teardown; big guides should be 20-30 min.
- **Formats_Videos: Education 51%, Expert 20%, Podcast 15%.** Prioritize guides, build-alongs, comparisons, investigations. Podcast only after authority exists.
- **High-ER titles include “Full guide”, “Build X in 25 minutes”, “I automated…”, “I tested 100…”, “Stop doing ugly/bad X”.** Use result-driven titles with a clear transformation, not abstract repo names.
- **Shorts winners used provocation; long winners use outcome + completeness.** Long titles should promise a complete workflow, teardown, or buyer decision.
- **AtlasRepo public API currently returns totalCatalog 8756 and 300 feed items.** Use public feed as daily source, then private DB when DATABASE_URL/API key is available.

## 30 видео

### 1. Я заменил дорогой SaaS open-source стеком из Atlas Repo

**Формат:** Experiment / challenge, 22 мин.

**Promise:** Сколько денег реально можно сэкономить, если заменить 5 платных сервисов open-source репозиториями?

**Проекты:** n8n, PostHog, Chatwoot, Metabase, OpenAPI Generator

**Ссылки:** https://github.com/n8n-io/n8n | https://github.com/OpenAPITools/openapi-generator

**Почему может набрать:** Не “обзор топ-5”, а челлендж: берем стек условного AI/SaaS проекта и заменяем сервисы на OSS.

**Структура:** 0:00 счет за SaaS; 1:30 правила челленджа; 3:00 automation; 7:00 analytics; 11:00 support; 15:00 API generation; 19:00 кому не стоит; 21:00 итоговая таблица экономии

**Нарезка в Shorts:** 5 Shorts: SaaS bill, n8n, PostHog, Chatwoot, OpenAPI Generator, финальная экономия

### 2. AI-агент за 25 минут без хайпа: что реально работает в 2026

**Формат:** Build-along tutorial, 25 мин.

**Promise:** Соберем первого агента и покажем, где он ломается.

**Проекты:** rocketride-server, better-agents, google/adk-go, full-stack-ai-agent-template

**Ссылки:** https://github.com/rocketride-org/rocketride-server | https://github.com/langwatch/better-agents | https://github.com/google/adk-go

**Почему может набрать:** Формат повторяет вирусные “From Zero to First AI Agent”, но с честными fail points.

**Структура:** 0:00 что агент должен сделать; 2:00 выбор framework; 5:00 tools; 9:00 memory/context; 13:00 запуск; 17:00 где ломается; 21:00 как чинить; 24:00 verdict

**Нарезка в Shorts:** 6 Shorts: “agent без магии”, tool calling, memory, fail, framework verdict, Atlas Repo CTA

### 3. Claude/Codex/Cursor: полный workflow для repo, который не разваливается

**Формат:** Full guide, 28 мин.

**Promise:** Не лучший prompt, а система файлов, тестов и правил.

**Проекты:** AGENTS.md, Gemini CLI, OpenAPI Generator, GitHub Actions

**Ссылки:** https://github.com/agentsmd/agents.md | https://github.com/google-gemini/gemini-cli | https://github.com/OpenAPITools/openapi-generator

**Почему может набрать:** Гайд для аудитории vibe coding: как сделать repo управляемым для AI.

**Структура:** 0:00 почему vibe coding ломается; 2:00 AGENTS.md; 7:00 README/architecture; 11:00 tests; 15:00 CLI agents; 20:00 PR workflow; 25:00 checklist

**Нарезка в Shorts:** 8 Shorts из каждого блока

### 4. Я проверил 30 проектов из Atlas Repo: какие реально можно монетизировать

**Формат:** Ranking / teardown, 30 мин.

**Promise:** Не звезды, а деньги: какие repo можно превратить в продукт, услугу или контент.

**Проекты:** Top 30 public AtlasRepo feed

**Ссылки:** https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Объемный рейтинг с критериями: боль, покупатель, demo, сложность внедрения.

**Структура:** 0:00 критерии; 2:00 automation; 7:00 AI agents; 12:00 backend tools; 17:00 monitoring; 22:00 payments; 26:00 top-5; 29:00 что берем в работу

**Нарезка в Shorts:** 30 Shorts: по одному на repo

### 5. OpenAPI Generator: скучный repo, который экономит недели backend-разработки

**Формат:** Deep repo teardown, 16 мин.

**Promise:** Почему 26k stars тут не главное. Главное: один spec становится SDK, сервером и документацией.

**Проекты:** OpenAPITools/openapi-generator

**Ссылки:** https://github.com/OpenAPITools/openapi-generator

**Почему может набрать:** Берем публичный top item AtlasRepo и объясняем бизнес-ценность.

**Структура:** 0:00 боль ручных SDK; 2:00 что такое OpenAPI; 5:00 генерация клиента; 8:00 server stub; 11:00 CI workflow; 14:00 кому подходит

**Нарезка в Shorts:** 4 Shorts: SDK за минуту, API spec, CI generation, скучный repo

### 6. Gemini CLI против Claude Code/Codex: что можно доверить терминальному агенту

**Формат:** Comparison, 20 мин.

**Promise:** Тестируем terminal-agent workflow на реальном repo.

**Проекты:** google-gemini/gemini-cli, AGENTS.md, local demo repo

**Ссылки:** https://github.com/google-gemini/gemini-cli

**Почему может набрать:** Сравнение лучше делать задачами, не мнениями.

**Структура:** 0:00 задача; 2:00 setup; 5:00 simple edit; 9:00 bug fix; 13:00 tests; 17:00 где опасно; 19:00 verdict

**Нарезка в Shorts:** 5 Shorts: terminal agent, тесты, опасность, best use case, verdict

### 7. n8n, AWX, Windmill: какой automation stack выбрать для AI-команды

**Формат:** Buyer guide, 24 мин.

**Promise:** Один workflow, три подхода: no-code, ops automation, scripts as product.

**Проекты:** n8n, ansible/awx, Windmill

**Ссылки:** https://github.com/n8n-io/n8n | https://github.com/ansible/awx | https://github.com/windmill-labs/windmill

**Почему может набрать:** Это “что выбрать”, хорошо собирает поиск и удержание.

**Структура:** 0:00 задача; 2:00 n8n; 7:00 AWX; 12:00 Windmill; 17:00 таблица выбора; 21:00 мой stack

**Нарезка в Shorts:** 6 Shorts: каждый tool + comparison

### 8. Как построить контент-завод на open-source инструментах

**Формат:** Build system, 26 мин.

**Promise:** Не “AI генерирует 1000 видео”, а нормальный pipeline: research, script, screen, edit, publish.

**Проекты:** changedetection.io, OpenAPI Generator, n8n, Atlas Repo feed

**Ссылки:** https://github.com/dgtlmoon/changedetection.io | https://github.com/n8n-io/n8n | https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Прямо связано с вашей задачей, может стать флагманским видео.

**Структура:** 0:00 зачем контент-завод; 3:00 source feed; 7:00 trend monitoring; 11:00 scripting; 15:00 screencast brief; 19:00 publish calendar; 23:00 метрики

**Нарезка в Shorts:** 10 Shorts и template lead magnet

### 9. MCP-серверы: полный гид для тех, кто не понял, зачем они нужны

**Формат:** Explainer + demos, 22 мин.

**Promise:** MCP не модное слово, а способ дать агенту инструменты.

**Проекты:** kubeshark, Skill_Seekers, claude-scholar, Playwright MCP

**Ссылки:** https://github.com/kubeshark/kubeshark | https://github.com/yusufkaraaslan/Skill_Seekers | https://github.com/microsoft/playwright-mcp

**Почему может набрать:** Educational “MCP explained” с demos.

**Структура:** 0:00 простая метафора; 3:00 browser; 8:00 data/search; 12:00 network/kube; 16:00 security risks; 20:00 stack

**Нарезка в Shorts:** 6 Shorts: что такое MCP, browser MCP, risks, top servers

### 10. Я собрал AI SaaS template из open-source repo за один вечер

**Формат:** Build in public, 30 мин.

**Promise:** Берем full-stack AI template и доводим до работающего MVP.

**Проекты:** vstorm-co/full-stack-ai-agent-template, Nango, Supabase/PostHog

**Ссылки:** https://github.com/vstorm-co/full-stack-ai-agent-template | https://github.com/NangoHQ/nango | https://github.com/PostHog/posthog

**Почему может набрать:** Видео-эксперимент с результатом на экране.

**Структура:** 0:00 идея; 2:00 template; 6:00 auth/integrations; 11:00 agent flow; 18:00 analytics; 23:00 deploy; 28:00 что продал бы

**Нарезка в Shorts:** 8 Shorts из процесса

### 11. Nango: repo, который решает самую грязную часть SaaS — интеграции

**Формат:** Deep repo teardown, 15 мин.

**Promise:** Пользователи хотят “подключите мой Google/Slack/CRM”. Вот где начинается боль.

**Проекты:** NangoHQ/nango

**Ссылки:** https://github.com/NangoHQ/nango

**Почему может набрать:** Очень сильная B2B SaaS тема.

**Структура:** 0:00 боль integrations; 2:00 что делает Nango; 5:00 OAuth; 8:00 sync; 11:00 use cases; 14:00 verdict

**Нарезка в Shorts:** 4 Shorts

### 12. Open-source RAG в 2026: что выбрать и где все ломается

**Формат:** Buyer guide, 27 мин.

**Promise:** RAG не умирает, он становится скучной инфраструктурой.

**Проекты:** airweave, RAGFlow, Qdrant/LanceDB from local list

**Ссылки:** https://github.com/airweave-ai/airweave | https://github.com/infiniflow/ragflow | https://github.com/qdrant/qdrant

**Почему может набрать:** Сильный search topic + практический угол.

**Структура:** 0:00 почему RAG разочаровывает; 3:00 ingestion; 8:00 chunking; 12:00 vector DB; 16:00 eval; 21:00 UI; 25:00 stack

**Нарезка в Shorts:** 7 Shorts

### 13. Changedetection.io: маленький repo, который может стать машиной для лидов

**Формат:** Use-case teardown, 14 мин.

**Promise:** Следить за изменениями страниц можно не только для скидок. Можно искать сигналы рынка.

**Проекты:** dgtlmoon/changedetection.io

**Ссылки:** https://github.com/dgtlmoon/changedetection.io

**Почему может набрать:** Показываем неожиданный business use case.

**Структура:** 0:00 monitoring pain; 2:00 setup; 5:00 конкуренты; 8:00 вакансии/цены/docs; 11:00 alerts to Telegram; 13:00 Atlas use case

**Нарезка в Shorts:** 5 Shorts

### 14. Open-source платежи и checkout: можно ли заменить Stripe?

**Формат:** Investigation, 24 мин.

**Promise:** Не обещаем “убить Stripe”, честно разбираем, где open-source помогает, а где нет.

**Проекты:** rynfar/meridian, Hyperswitch, TON Connect

**Ссылки:** https://github.com/rynfar/meridian | https://github.com/juspay/hyperswitch | https://github.com/ton-connect/sdk

**Почему может набрать:** Провокационный title, но зрелый анализ.

**Структура:** 0:00 почему Stripe сложно заменить; 3:00 payment orchestration; 8:00 crypto/TON; 13:00 compliance; 18:00 self-host risks; 22:00 verdict

**Нарезка в Shorts:** 6 Shorts

### 15. Daytona и dev environments: почему локальная разработка умирает медленно

**Формат:** Trend explainer, 18 мин.

**Promise:** Cloud dev envs не про моду, а про скорость onboarding и AI agents.

**Проекты:** daytonaio/daytona, devcontainers, GitHub Codespaces angle

**Ссылки:** https://github.com/daytonaio/daytona

**Почему может набрать:** Тема для разработчиков и founders.

**Структура:** 0:00 “works on my machine”; 2:00 Daytona; 6:00 devcontainers; 10:00 AI agents; 14:00 cost/security; 17:00 verdict

**Нарезка в Shorts:** 5 Shorts

### 16. PostHog против Google Analytics: почему product analytics важнее vanity metrics

**Формат:** Comparison, 18 мин.

**Promise:** Если ты строишь продукт, просмотры страниц не отвечают на главный вопрос.

**Проекты:** PostHog/posthog

**Ссылки:** https://github.com/PostHog/posthog

**Почему может набрать:** B2B/product audience.

**Структура:** 0:00 vanity metrics; 3:00 events; 6:00 funnels; 9:00 feature flags; 12:00 session replay; 16:00 когда не нужен

**Нарезка в Shorts:** 5 Shorts

### 17. Bruno против Postman: почему API-клиент стал git-friendly

**Формат:** Comparison, 16 мин.

**Promise:** API requests должны жить рядом с кодом, а не только в облаке.

**Проекты:** usebruno/bruno

**Ссылки:** https://github.com/usebruno/bruno

**Почему может набрать:** Простой понятный dev angle.

**Структура:** 0:00 Postman pain; 2:00 Bruno; 5:00 files in git; 8:00 team workflow; 12:00 CI; 15:00 verdict

**Нарезка в Shorts:** 4 Shorts

### 18. Sentry, OpenTelemetry, Grafana: как не летать вслепую после релиза

**Формат:** Stack guide, 24 мин.

**Promise:** MVP без observability — это не скорость, а слепота.

**Проекты:** getsentry/sentry, grafana/grafana, OpenTelemetry

**Ссылки:** https://github.com/getsentry/sentry | https://github.com/grafana/grafana | https://github.com/open-telemetry/opentelemetry-collector

**Почему может набрать:** Практическое видео для founders/devs.

**Структура:** 0:00 crash story; 3:00 errors; 8:00 logs/traces; 13:00 dashboards; 18:00 alerts; 22:00 starter stack

**Нарезка в Shorts:** 7 Shorts

### 19. Chatwoot: open-source Intercom для тех, кто не хочет платить за каждый контакт

**Формат:** SaaS replacement, 15 мин.

**Promise:** Customer support — первая платная боль у маленького SaaS.

**Проекты:** chatwoot/chatwoot

**Ссылки:** https://github.com/chatwoot/chatwoot

**Почему может набрать:** Очень понятная SaaS replacement тема.

**Структура:** 0:00 Intercom bill; 2:00 Chatwoot; 5:00 inbox; 8:00 website widget; 11:00 automation; 14:00 verdict

**Нарезка в Shorts:** 4 Shorts

### 20. Metabase и Lightdash: как сделать аналитику без команды BI

**Формат:** Comparison, 20 мин.

**Promise:** Dashboards нужны всем, но hiring BI-команды нужен не всем.

**Проекты:** metabase/metabase, lightdash/lightdash

**Ссылки:** https://github.com/metabase/metabase | https://github.com/lightdash/lightdash

**Почему может набрать:** Founder/operator angle.

**Структура:** 0:00 analytics bottleneck; 3:00 Metabase; 8:00 Lightdash; 13:00 semantic layer; 17:00 what to choose

**Нарезка в Shorts:** 5 Shorts

### 21. AutoGPT спустя хайп: что осталось полезного от AI agents

**Формат:** Post-hype analysis, 20 мин.

**Promise:** Хайп прошел, инфраструктура осталась.

**Проекты:** Significant-Gravitas/AutoGPT, OpenHands, SWE-agent

**Ссылки:** https://github.com/Significant-Gravitas/AutoGPT | https://github.com/All-Hands-AI/OpenHands | https://github.com/SWE-agent/SWE-agent

**Почему может набрать:** История + практический вывод.

**Структура:** 0:00 hype recap; 3:00 why failed; 7:00 what survived; 12:00 coding agents; 17:00 what to use now

**Нарезка в Shorts:** 6 Shorts

### 22. vLLM и SGLang: как реально сервят LLM, когда игрушки заканчиваются

**Формат:** Technical explainer, 22 мин.

**Promise:** Запустить модель — легко. Сервить быстро и дешево — другая игра.

**Проекты:** vllm-project/vllm, sgl-project/sglang

**Ссылки:** https://github.com/vllm-project/vllm | https://github.com/sgl-project/sglang

**Почему может набрать:** Для более технической аудитории, высокий authority.

**Структура:** 0:00 inference cost; 3:00 vLLM; 8:00 batching/cache; 12:00 SGLang; 17:00 when needed; 21:00 verdict

**Нарезка в Shorts:** 5 Shorts

### 23. Keycloak, OpenBao, auth/secrets: скучный слой, который спасает продукт

**Формат:** Infrastructure guide, 22 мин.

**Promise:** Самые дорогие ошибки обычно не в UI, а в auth и secrets.

**Проекты:** keycloak/keycloak, openbao/openbao

**Ссылки:** https://github.com/keycloak/keycloak | https://github.com/openbao/openbao

**Почему может набрать:** Сильный “boring but important” формат.

**Структура:** 0:00 horror story; 3:00 auth; 8:00 secrets; 13:00 teams/roles; 18:00 starter rules

**Нарезка в Shorts:** 5 Shorts

### 24. Nextcloud, Notesnook, Karakeep: self-hosted knowledge base для AI-эпохи

**Формат:** Stack guide, 20 мин.

**Promise:** Если данные кормят AI, где они должны жить?

**Проекты:** nextcloud/server, streetwriters/notesnook, karakeep-app/karakeep

**Ссылки:** https://github.com/nextcloud/server | https://github.com/streetwriters/notesnook | https://github.com/karakeep-app/karakeep

**Почему может набрать:** Consumer + dev crossover.

**Структура:** 0:00 data ownership; 3:00 files; 7:00 notes; 11:00 bookmarks; 15:00 AI memory; 19:00 stack

**Нарезка в Shorts:** 6 Shorts

### 25. Kubernetes для людей, которые не хотят Kubernetes: Kubeshark, kubefwd, AWX

**Формат:** Ops guide, 23 мин.

**Promise:** DevOps-инструменты должны уменьшать боль, а не продавать сложность.

**Проекты:** kubeshark/kubeshark, txn2/kubefwd, ansible/awx

**Ссылки:** https://github.com/kubeshark/kubeshark | https://github.com/txn2/kubefwd | https://github.com/ansible/awx

**Почему может набрать:** Практичный ops angle.

**Структура:** 0:00 kube fatigue; 3:00 traffic visibility; 8:00 port forwarding; 12:00 automation; 18:00 what to install

**Нарезка в Shorts:** 5 Shorts

### 26. Я построил Atlas Repo content engine на Atlas Repo данных

**Формат:** Meta/build-in-public, 26 мин.

**Promise:** Берем нашу базу и превращаем ее в 30 дней контента.

**Проекты:** AtlasRepo public API + YouTube research

**Ссылки:** https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Самый сильный brand-native ролик: показать реальный процесс.

**Структура:** 0:00 проблема контента; 3:00 source database; 7:00 scoring; 11:00 scripts; 15:00 briefs; 19:00 shorts calendar; 23:00 analytics loop

**Нарезка в Shorts:** 10 Shorts

### 27. Почему “звезды GitHub” врут: как реально выбирать repo для бизнеса

**Формат:** Framework explainer, 18 мин.

**Promise:** Stars показывают внимание, но не показывают внедряемость.

**Проекты:** Atlas Repo scoring examples

**Ссылки:** https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Обучающий authority формат.

**Структура:** 0:00 star trap; 3:00 recency; 6:00 docs; 9:00 integrations; 12:00 adoption; 15:00 business fit

**Нарезка в Shorts:** 5 Shorts

### 28. 10 open-source проектов, которые могут заменить отдел операционки

**Формат:** Listicle with demos, 25 мин.

**Promise:** Не один инструмент, а operating stack для маленькой команды.

**Проекты:** n8n, AWX, changedetection, Chatwoot, Metabase, PostHog, OpenAPI Generator

**Ссылки:** https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Listicle хорошо работает для охватов и нарезки.

**Структура:** 0:00 promise; 2:00 monitoring; 5:00 automation; 9:00 support; 13:00 analytics; 17:00 API; 21:00 final stack

**Нарезка в Shorts:** 10 Shorts

### 29. AI tools tier list, но только open-source repo из Atlas Repo

**Формат:** Tier list, 24 мин.

**Promise:** S-tier не самый хайповый, а тот, который можно внедрить завтра.

**Проекты:** 30 AtlasRepo projects

**Ссылки:** https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Визуально сильный формат.

**Структура:** 0:00 criteria; 3:00 S-tier; 8:00 A-tier; 14:00 risky; 20:00 what we use; 23:00 comments

**Нарезка в Shorts:** 30 Shorts micro verdicts

### 30. Как мы будем набрать просмотры на Atlas Repo: 100 Shorts + 30 long videos

**Формат:** Strategy/public roadmap, 18 мин.

**Promise:** Публично показываем систему, а не просто контент.

**Проекты:** YouTube research + Atlas Repo feed

**Ссылки:** local research + https://atlasrepo.com/api/scout-feed

**Почему может набрать:** Мета-видео может привлечь builders/creators.

**Структура:** 0:00 цель; 2:00 research; 5:00 formats; 8:00 shorts engine; 11:00 long videos; 14:00 metrics; 17:00 invitation

**Нарезка в Shorts:** 5 Shorts + pinned roadmap

