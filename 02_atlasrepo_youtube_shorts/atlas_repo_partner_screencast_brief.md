# ATLAS REPO — бриф партнеру на скринкасты для 30 Shorts

Цель: партнер открывает конкретную ссылку, снимает нужные экраны и не тратит время на придумывание, что показывать. Не показывать токены, приватные репозитории, реальные платежи, email и ключи. Если сервис не запускается за 10-15 минут, снимаем README, screenshots/GIF, docs и заранее подготовленный mock/demo.

## 1. Хватит платить за 5 AI-инструментов

**Что обозреваем:** OpenAlternative + 3 конкретных альтернативы: Activepieces, AppFlowy, Dify

**Ссылка:** https://github.com/piotrkulpinski/openalternative

**Как объяснить партнеру:** Показываем не один сервис, а каталог open-source альтернатив платным SaaS. Главная мысль: вместо пяти подписок можно найти self-hosted repo под automation, workspace и AI app builder.

**Что снять:** 1) открыть OpenAlternative GitHub; 2) показать список альтернатив; 3) открыть Activepieces/AppFlowy/Dify; 4) показать README/install/demo; 5) финальный кадр: несколько вкладок с repo.

**Если не заводится:** Если демо не запускается, снять только GitHub README, stars, features, screenshots/GIF и docs install block.

**Приоритет:** high

## 2. Open-source альтернатива Figma для AI-прототипов

**Что обозреваем:** Onlook или Penpot как open-source visual/design tool

**Ссылка:** https://github.com/onlook-dev/onlook

**Как объяснить партнеру:** Показываем инструмент для визуальной правки/прототипирования интерфейсов. Угол: это не убивает Figma, но помогает founder-у быстрее собрать MVP/UI.

**Что снять:** 1) открыть repo; 2) показать hero/screenshot; 3) показать install; 4) если есть demo app, открыть canvas/editor; 5) снять изменение компонента или prompt/edit flow.

**Если не заводится:** Если Onlook не заведется, использовать Penpot: https://github.com/penpot/penpot и показать как open-source design platform.

**Приоритет:** high

## 3. Repo, который делает из сайта CLI

**Что обозреваем:** Browser-use / Playwright MCP как способ управлять сайтом командами

**Ссылка:** https://github.com/browser-use/browser-use

**Как объяснить партнеру:** Показываем не буквально CLI для любого сайта, а механику: AI/скрипт управляет браузером и превращает клики в автоматизированные команды.

**Что снять:** 1) repo browser-use; 2) README example; 3) короткий terminal run; 4) браузер сам открывает сайт/делает действие; 5) показать результат в логах.

**Если не заводится:** Если browser-use не заводится, снять microsoft/playwright-mcp: https://github.com/microsoft/playwright-mcp и README с примером browser automation.

**Приоритет:** high

## 4. 4 файла, которые делают Claude/Codex полезнее

**Что обозреваем:** AGENTS.md standard + локальный пример repo с README/AGENTS/ARCHITECTURE/TASKS

**Ссылка:** https://github.com/agentsmd/agents.md

**Как объяснить партнеру:** Показываем стандарт AGENTS.md и локальный пример: как AI-агенту дать правила проекта. Главная мысль: AI работает лучше, когда repo объясняет себя.

**Что снять:** 1) открыть agentsmd/agents.md; 2) показать sample AGENTS.md; 3) открыть локальный repo; 4) показать README, AGENTS.md, ARCHITECTURE.md, TASKS.md; 5) показать prompt в Codex/Claude.

**Если не заводится:** Если нет готового локального repo, создать папку demo-repo с 4 markdown-файлами и снять их в VS Code.

**Приоритет:** high

## 5. Claude Code + Obsidian за минуту

**Что обозреваем:** Obsidian + Markdown notes как память проекта

**Ссылка:** https://obsidian.md

**Как объяснить партнеру:** Это workflow, не repo. Показываем Obsidian/Markdown как память разработки: решения, ошибки, архитектурные заметки, на которые ссылается AGENTS.md.

**Что снять:** 1) открыть Obsidian vault или папку docs/notes; 2) показать заметку decision-log.md; 3) открыть AGENTS.md со ссылкой на notes; 4) спросить AI о решении; 5) AI отвечает с учетом заметки.

**Если не заводится:** Если Obsidian не установлен, снять обычную папку Markdown в VS Code.

**Приоритет:** medium

## 6. Cursor красивый, но repo решает

**Что обозреваем:** Локальный пример плохой и хорошей структуры repo

**Ссылка:** https://developers.openai.com/codex/guides/agents-md

**Как объяснить партнеру:** Это workflow-ролик. Обозреваем не сервис, а принцип: AI coding зависит от качества repo context. Ссылка нужна как подтверждение AGENTS.md/custom instructions.

**Что снять:** 1) показать хаотичную структуру папок; 2) показать хорошую структуру src/tests/docs/scripts; 3) показать AGENTS.md; 4) дать AI задачу; 5) AI сам находит команды.

**Если не заводится:** Если нет Cursor/Codex записи, снять только VS Code + текстовый prompt в отдельном окне.

**Приоритет:** medium

## 7. Repo читает весь codebase и объясняет обратно

**Что обозреваем:** Sourcegraph Cody / Continue как codebase-aware assistant

**Ссылка:** https://github.com/sourcegraph/cody

**Как объяснить партнеру:** Показываем инструмент, который понимает codebase и помогает задавать вопросы по проекту. Угол: onboarding и legacy repo.

**Что снять:** 1) открыть repo/source docs; 2) открыть проект в IDE; 3) задать вопрос where auth/payment is implemented; 4) показать ссылки на файлы; 5) кадр с explanation.

**Если не заводится:** Если Cody не подходит, взять Continue: https://github.com/continuedev/continue и показать codebase chat.

**Приоритет:** high

## 8. Repo превращает терминальный мусор в HTML-страницу

**Что обозреваем:** AI-generated error report на базе terminal output

**Ссылка:** https://github.com/upscayl/llm-error-explainer-example-placeholder

**Как объяснить партнеру:** Здесь нужен локальный постановочный пример: берем npm/test error, просим AI превратить в HTML report. Сервис можно заменить любым repo/tool, который делает log/error explanation.

**Что снять:** 1) терминал с ошибкой; 2) копируем output; 3) AI генерирует report.html; 4) открыть HTML; 5) показать root cause/fix sections.

**Если не заводится:** Если нужен реальный repo, найти/использовать любой log analyzer; если нет, снять workflow как кастомный demo для Atlas Repo.

**Приоритет:** medium

## 9. Куда ушли $200 на Claude Code

**Что обозреваем:** LiteLLM spend logs / Langfuse observability

**Ссылка:** https://github.com/langfuse/langfuse

**Как объяснить партнеру:** Показываем observability/cost tracking для LLM-приложений. Главная мысль: AI bills нужно отслеживать по проектам, моделям и сессиям.

**Что снять:** 1) открыть Langfuse repo; 2) показать dashboard screenshots/docs; 3) показать traces/costs; 4) открыть LiteLLM как gateway; 5) финальный кадр: cost table.

**Если не заводится:** Если нет локального Langfuse, снять README/docs screenshots и mock dashboard без реальных ключей.

**Приоритет:** high

## 10. Папка .github, которую все игнорируют

**Что обозреваем:** Любой repo с .github folder + GitHub docs

**Ссылка:** https://docs.github.com/en/actions

**Как объяснить партнеру:** Показываем .github как операционную папку repo: workflows, issue templates, PR template, dependabot.

**Что снять:** 1) открыть repo с .github; 2) показать workflows/check.yml; 3) issue template; 4) PR template; 5) Actions tab.

**Если не заводится:** Можно снять на локальном demo repo, создав .github/workflows/check.yml и pull_request_template.md.

**Приоритет:** high

## 11. GitHub Actions как бесплатный сотрудник

**Что обозреваем:** GitHub Actions workflow

**Ссылка:** https://github.com/actions/starter-workflows

**Как объяснить партнеру:** Показываем starter workflows и запуск проверки на push/PR. Объяснение: это автоматизация повторяющихся операций команды.

**Что снять:** 1) открыть actions/starter-workflows; 2) показать YAML; 3) открыть Actions tab в любом repo; 4) показать green/red run; 5) лог ошибки.

**Если не заводится:** Если нет repo с Actions, создать локальный workflow file и показать пример из GitHub docs.

**Приоритет:** high

## 12. GitHub profile как 3D-город

**Что обозреваем:** GitHub City / GitHub Skyline style visualizer

**Ссылка:** https://github.com/anuraghazra/github-readme-stats

**Как объяснить партнеру:** Показываем визуализацию GitHub-профиля. Если 3D-city не найден/не работает, используем популярный visual profile repo как пример вирусного dev-visual.

**Что снять:** 1) открыть visualizer repo; 2) ввести username или показать generated SVG; 3) pan/zoom если 3D; 4) показать README embed; 5) финальный профиль.

**Если не заводится:** Fallback: GitHub Readme Stats, потому что стабильно и понятно визуализирует профиль.

**Приоритет:** medium

## 13. MCP сервер дает агенту браузер

**Что обозреваем:** Microsoft Playwright MCP

**Ссылка:** https://github.com/microsoft/playwright-mcp

**Как объяснить партнеру:** Показываем MCP server, который дает LLM browser automation через Playwright. Угол: агент не только пишет код, но и проверяет UI.

**Что снять:** 1) открыть repo; 2) показать README description; 3) показать install command; 4) запустить simple browser automation; 5) показать результат проверки страницы.

**Если не заводится:** Если запуск сложный, снять README + официальные docs: https://playwright.dev/docs/getting-started-mcp.

**Приоритет:** high

## 14. AI agents без babysitting

**Что обозреваем:** CrewAI / AutoGen как agent orchestration

**Ссылка:** https://github.com/crewAIInc/crewAI

**Как объяснить партнеру:** Показываем orchestration: несколько агентов, роли, задачи, статус выполнения. Главная мысль: это не чат, а task pipeline.

**Что снять:** 1) открыть CrewAI repo; 2) показать roles/tasks example; 3) terminal run; 4) output с несколькими agent steps; 5) итоговый markdown/report.

**Если не заводится:** Fallback: Microsoft AutoGen https://github.com/microsoft/autogen.

**Приоритет:** medium

## 15. Агент сам исследует ML papers

**Что обозреваем:** Open Deep Research / GPT Researcher

**Ссылка:** https://github.com/assafelovic/gpt-researcher

**Как объяснить партнеру:** Показываем research agent: задаешь тему, он строит план, ищет источники и делает отчет.

**Что снять:** 1) открыть repo; 2) показать query input; 3) запуск research; 4) sources list; 5) final report markdown.

**Если не заводится:** Если запуск долгий, снять README demo GIF/screenshots и заранее подготовленный report.

**Приоритет:** high

## 16. LLM-router не дает сжечь бюджет

**Что обозреваем:** LiteLLM AI Gateway

**Ссылка:** https://github.com/BerriAI/litellm

**Как объяснить партнеру:** Показываем gateway/router для разных LLM providers. Угол: не каждую задачу надо отправлять в самую дорогую модель.

**Что снять:** 1) открыть LiteLLM repo; 2) показать supported providers; 3) config с несколькими models; 4) proxy call; 5) dashboard/log с model/cost.

**Если не заводится:** Если dashboard не поднят, снять config + terminal curl examples + docs.

**Приоритет:** high

## 17. Какие LLM потянет твой Mac

**Что обозреваем:** Ollama + локальный список моделей

**Ссылка:** https://github.com/ollama/ollama

**Как объяснить партнеру:** Показываем practical local AI check: какие модели реально запускать локально. Можно не искать отдельный llmfit repo, а снять Ollama как базовый local LLM tool.

**Что снять:** 1) открыть Ollama repo; 2) terminal ollama list; 3) ollama run small model; 4) показать Activity Monitor/RAM если возможно; 5) вывод: small vs huge model.

**Если не заводится:** Если Ollama не установлен, снять сайт/README и объяснить, какие параметры важны: RAM, quantization, model size.

**Приоритет:** high

## 18. JSON viewer спасает разработчиков

**Что обозреваем:** JSON Crack / jq / browser JSON viewer

**Ссылка:** https://github.com/AykutSarac/jsoncrack.com

**Как объяснить партнеру:** Показываем маленький daily dev tool: визуализировать большой JSON как граф/дерево.

**Что снять:** 1) открыть JSON Crack repo/site; 2) вставить большой JSON; 3) показать graph/tree; 4) search/collapse; 5) copy path/result.

**Если не заводится:** Fallback: jq в терминале + любой browser JSON viewer extension.

**Приоритет:** medium

## 19. Разработчик автоматизировал 700 откликов

**Что обозреваем:** AI job application automation repo/example

**Ссылка:** https://github.com/feder-cr/Auto_Jobs_Applier_AIHawk

**Как объяснить партнеру:** Показываем automation case для job search: поиск вакансий, резюме, cover letter, статусы.

**Что снять:** 1) открыть repo; 2) показать config без личных данных; 3) dashboard/status или README flow; 4) generated cover letter; 5) application tracking.

**Если не заводится:** Не вводить реальные аккаунты/пароли; можно снять полностью на README и mock data.

**Приоритет:** medium

## 20. Self-hosted travel planner как готовый SaaS

**Что обозреваем:** AdventureLog / self-hosted travel planner

**Ссылка:** https://github.com/seanmorley15/AdventureLog

**Как объяснить партнеру:** Показываем open-source продукт, который выглядит как SaaS: trips, maps, media, planning. Угол: GitHub как каталог MVP.

**Что снять:** 1) открыть repo; 2) показать screenshots; 3) локальная/demo страница; 4) trip/map/collaboration features; 5) mobile/PWA кадр если есть.

**Если не заводится:** Если demo не запускается, снять README screenshots и issues/features.

**Приоритет:** medium

## 21. Repo как источник SaaS-идей

**Что обозреваем:** GitHub Trending + OpenAlternative + issues/forks workflow

**Ссылка:** https://github.com/trending

**Как объяснить партнеру:** Показываем процесс поиска идеи: stars growth, issues, forks, paid competitors. Это не обзор одного repo, а метод.

**Что снять:** 1) открыть GitHub Trending; 2) выбрать repo; 3) показать issues с pain points; 4) forks/stars; 5) найти paid competitor; 6) финал Atlas Repo scouting.

**Если не заводится:** Если GitHub Trending меняется, заранее выбрать любой repo из Atlas Repo списка.

**Приоритет:** high

## 22. Почему vibe coding не заменит архитектора

**Что обозреваем:** Demo repo + architecture prompt

**Ссылка:** https://github.com/codecrafters-io/build-your-own-x

**Как объяснить партнеру:** Показываем, что архитектура важнее magic prompt. Build-your-own-x можно использовать как визуальный пример структурированных проектов/архитектурных задач.

**Что снять:** 1) открыть плохой prompt; 2) открыть хороший architecture prompt; 3) показать структуру файлов; 4) показать tests; 5) итог: AI следует архитектуре.

**Если не заводится:** Можно снять полностью на локальном demo repo без внешнего сервиса.

**Приоритет:** medium

## 23. AI пишет код, но тесты должны быть твои

**Что обозреваем:** Testing workflow на любом JS/Python repo

**Ссылка:** https://github.com/vitest-dev/vitest

**Как объяснить партнеру:** Показываем tests-first AI workflow: агент пишет тест, тест падает, агент чинит, тест проходит.

**Что снять:** 1) открыть Vitest repo/docs; 2) локальный маленький проект; 3) test fail; 4) AI fix; 5) test pass.

**Если не заводится:** Можно использовать pytest вместо Vitest, если партнеру удобнее Python.

**Приоритет:** high

## 24. 12 подписок на AI coding tools — перебор

**Что обозреваем:** Tool stack board + Continue/Codex/Claude/Cursor examples

**Ссылка:** https://github.com/continuedev/continue

**Как объяснить партнеру:** Показываем идею: workflow before subscriptions. Continue как open-source AI code assistant для примера.

**Что снять:** 1) открыть Continue repo; 2) показать tool stack tabs/logos; 3) показать checklist context/tests/tasks/review; 4) сравнить хаос vs workflow.

**Если не заводится:** Не нужно запускать все инструменты; это talking-head + screen board.

**Приоритет:** medium

## 25. Telegram-бот как интерфейс к GitHub repo

**Что обозреваем:** grammY / Telegraf + GitHub API demo

**Ссылка:** https://github.com/grammyjs/grammY

**Как объяснить партнеру:** Показываем Telegram bot framework и простую связку: команда в Telegram создает GitHub issue или запускает workflow.

**Что снять:** 1) открыть grammY repo; 2) показать bot command code; 3) Telegram chat command; 4) GitHub issue/action appears; 5) bot returns status.

**Если не заводится:** Без реальных токенов. Если нет интеграции, снять mocked Telegram chat + GitHub issue manually.

**Приоритет:** high

## 26. Referral system как repo, а не SaaS

**Что обозреваем:** Open-source affiliate/referral template or custom demo

**Ссылка:** https://github.com/ever-co/ever-gauzy

**Как объяснить партнеру:** Показываем общий referral/affiliate flow: invite link, tracking, dashboard, payout status. Ever Gauzy как пример большого open-source business platform; если тяжело, делаем кастомный mini demo.

**Что снять:** 1) показать referral flow diagram; 2) invite link; 3) signup attributed; 4) referrals dashboard; 5) payout/status table.

**Если не заводится:** Лучше снять кастомный lightweight demo без реальных платежей, потому что готовые referral repo могут быть тяжелыми.

**Приоритет:** medium

## 27. TON payments за 60 секунд

**Что обозреваем:** TON Connect / TON payments docs + demo flow

**Ссылка:** https://github.com/ton-connect/sdk

**Как объяснить партнеру:** Показываем структуру TON payment integration: invoice/payment request, wallet connect, webhook/status.

**Что снять:** 1) открыть TON Connect SDK repo; 2) показать docs/example; 3) payment flow diagram; 4) status screen pending/paid; 5) webhook handler code без ключей.

**Если не заводится:** Не делать реальный платеж. Снять sandbox/mock status.

**Приоритет:** high

## 28. AI tools tier list для разработчика

**Что обозреваем:** Tier list board: Codex, Claude Code, Cursor, Copilot, Continue, Ollama, Playwright MCP

**Ссылка:** https://tiermaker.com/create

**Как объяснить партнеру:** Это не обзор одного repo, а рейтинговый формат. Нужен экран tier list и несколько вкладок инструментов.

**Что снять:** 1) открыть tier board; 2) карточки инструментов; 3) перетаскивание по S/A/B/C; 4) короткие критерии; 5) финальный screenshot.

**Если не заводится:** Можно сделать tier list в Figma/Canva/Google Slides, не обязательно на TierMaker.

**Приоритет:** high

## 29. 5 repo, которые я бы ставил в каждый проект

**Что обозреваем:** Starter stack: Biome, Vitest, GitHub Actions, Sentry, AGENTS.md

**Ссылка:** https://github.com/biomejs/biome

**Как объяснить партнеру:** Показываем starter pack для нового проекта: formatter/lint, tests, CI, monitoring, AI docs.

**Что снять:** 1) открыть Biome; 2) Vitest; 3) Actions workflow; 4) Sentry/OpenTelemetry docs; 5) AGENTS.md; 6) финальный checklist.

**Если не заводится:** Если много вкладок, сделать montage: 1-2 секунды на каждый tool + checklist.

**Приоритет:** high

## 30. GitHub стал App Store для AI-строителей

**Что обозреваем:** Atlas Repo positioning + GitHub Trending/OpenAlternative montage

**Ссылка:** https://github.com/trending

**Как объяснить партнеру:** Показываем manifesto: GitHub как каталог инструментов, templates, agents, MCP, automation. Это вводный ролик серии Atlas Repo.

**Что снять:** 1) GitHub Trending; 2) OpenAlternative; 3) несколько repo pages; 4) clone/install/demo кадры; 5) финальный экран Atlas Repo: 1 repo/day.

**Если не заводится:** Можно использовать кадры из предыдущих 29 роликов как монтаж.

**Приоритет:** high

