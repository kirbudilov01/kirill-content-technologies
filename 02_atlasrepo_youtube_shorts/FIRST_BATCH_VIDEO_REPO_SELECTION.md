# First batch: 3 long videos + 10 repo-review Shorts

Дата сборки: 2026-06-19.

Источники:

- `source_inputs/content_review_projects_base.xlsx` — база проектов из Telegram/X/ручного отбора.
- AtlasRepo live feed, проверен 2026-06-19: `atlasrepo.com/api/scout-feed`.
- Два X-поста: `one-person company GitHub repos` и `content factory 2026 stack`.
- Локальная база AtlasRepo / RepoSearchEngine.

Главная идея первой пачки: не пытаться сразу снять всё. Берем один сильный production loop, но разводим логику трех длинных видео:

1. Video 1 — самый сочный общий список repo: AI company stack, без банального n8n.
2. 10 однотипных Shorts — repo-review тест формата по части этой же пачки.
3. Video 2 — отдельная история: micro-SaaS за вечер, там repo работают как строительные блоки.
4. Video 3 — отдельная история: AtlasRepo как сайт, который нашел 3 gold repo под конкретную задачу.

Так партнер снимает один набор скринкастов, а мы получаем long-form, Shorts и повторяемый формат.

---

## Video 1: These 10 GitHub Repos Can Build a One-Person Company

**Рабочее название:** `These 10 GitHub Repos Can Build a One-Person Company`

**Русская формулировка:** `10 GitHub repo, из которых можно собрать компанию из одного человека`

**Статус:** берем первым.

**Почему это сильное:** понятный массовый фрейм. Не "обзор репозиториев", а мечта: один человек + open-source рычаги вместо команды и SaaS-подписок.

**Редакторское решение:** n8n не берем. Он слишком очевидный и заезженный для первого удара. MarkItDown и Activepieces тоже убираем из первой десятки: полезные, но не "сохрани канал". Первый список должен смешивать проекты, которые уже на слуху, и свежие вау-находки. Важно: repo не должны дублировать друг друга. Каждый закрывает отдельный слой one-person AI company.

**Основная структура:**

1. Хук: "Если бы я сегодня собирал one-person company, я бы начал не с найма, а с этих 10 open-source repo."
2. Коротко про AtlasRepo: "Мы просмотрели тысячи open-source проектов в AtlasRepo."
3. 10 блоков: проблема -> repo -> что заменяет -> что показать на экране -> verdict.
4. Финал: "Один weekend setup может дать years of leverage."

### Финальные 10 GitHub repo для видео 1 и 10 Shorts

Проверено через GitHub API 2026-06-19: все 10 пунктов — реальные GitHub repositories, не просто сайты/сервисы.

Порядок ниже выбран не по stars, а по удержанию: сначала самые визуальные "я хочу это протестить", потом фундаментальный AI stack, затем coding/agent layer, потом бизнес-слой и дистрибуция.

| # | Repo | Ссылка | Роль в one-person company | Основной хук |
|---|---|---|---|---|
| 1 | browser-use | https://github.com/browser-use/browser-use | AI agents для браузера | Stop clicking buttons — let AI use websites |
| 2 | MoneyPrinterTurbo | https://github.com/harry0703/MoneyPrinterTurbo | AI Shorts/Reels/TikToks generation | Generate Shorts, Reels and TikToks with AI |
| 3 | Ollama | https://github.com/ollama/ollama | Local AI models | Stop renting AI — run powerful models locally |
| 4 | Open WebUI | https://github.com/open-webui/open-webui | Свой ChatGPT-like workspace | Build your own ChatGPT workspace |
| 5 | Dify | https://github.com/langgenius/dify | Быстрая сборка AI apps / assistants / RAG | Stop building AI products from scratch |
| 6 | ComfyUI | https://github.com/Comfy-Org/ComfyUI | Visual AI image workflow | This is Photoshop for AI workflows |
| 7 | OpenHands | https://github.com/OpenHands/OpenHands | AI software engineer в repo | Stop writing every line of code yourself |
| 8 | Multica | https://github.com/multica-ai/multica | AI teammates / agent project management | Turn coding agents into real teammates |
| 9 | Twenty CRM | https://github.com/twentyhq/twenty | CRM / business operations | Stop paying for Salesforce before you even have a sales team |
| 10 | Postiz | https://github.com/gitroomhq/postiz-app | Social scheduling / distribution | Stop paying for social media scheduling tools |

**Anti-duplication logic:** `browser-use` = browser worker, `MoneyPrinterTurbo` = video generator, `Ollama` = engine, `Open WebUI` = workspace, `Dify` = AI app builder, `ComfyUI` = creative/image workflow, `OpenHands` = coding worker, `Multica` = agent team management, `Twenty CRM` = business operations, `Postiz` = distribution.

**Backup / проверить перед съемкой:** `Deer Flow`, `UI-TARS Desktop`, `mem0`, `Flowise`, `AnythingLLM`, `AppFlowy`, `Coolify`, `droidrun`, `Hyperframes`, `video-use`, `OpenMontage`. Если один из финальных 10 окажется плохо снимаемым или не даст нормального proof-screen, заменить из backup.

### Партнеру: что снять для Video 1

Общий формат скринкастов: 16:9 для long-form + вертикальные кропы 9:16 для Shorts. Не показывать токены, почту, приватные аккаунты, реальные платежи, приватные repo.

Для каждого repo нужно:

1. GitHub header: название, stars, короткое описание.
2. README/demo screen: что делает инструмент.
3. Один proof screen: dashboard, workflow, UI, terminal run, example output.
4. Один limitation screen: setup, docs, issue, env, self-hosting, permissions.
5. Финальная карточка: `SAVE / TEST / SKIP`.

---

## Video 2: I Created a Micro-SaaS in One Evening with Open-Source Projects

**Рабочее название:** `I Created a Micro-SaaS in One Evening with Open-Source Projects`

**Русская формулировка:** `Я собрал micro-SaaS за вечер только из open-source проектов`

**Статус:** берем вторым, но сначала нужно выбрать нишу.

**Рекомендованная ниша для первой версии:** `AI Content Factory Dashboard`

Почему именно она:

- логично связана с нашей текущей задачей: YouTube, Shorts, research, AtlasRepo;
- можно использовать второй X-пост про content factory;
- продукт понятен шире, чем чисто dev-tool;
- хорошо ведет трафик на AtlasRepo как источник open-source инструментов.

**Что делает micro-SaaS:**

Пользователь вводит нишу или тему. Система находит релевантные open-source проекты, превращает их в темы для Shorts/long-form, генерирует контент-план, отправляет задачи на съемку и готовит публикации.

### Repo/сервисы для Video 2

| Роль | Repo/сервис | Ссылка | Что показать |
|---|---|---|---|
| Источник проектов | AtlasRepo | https://atlasrepo.com | Поиск/лента проектов, карточки repo |
| Competitor/content research | Want2View | https://want2view.com | Исследование трендов/конкурентов, если есть доступный экран |
| Workflow automation | Activepieces | https://github.com/activepieces/activepieces | Сценарий: repo -> таблица -> задача -> публикация |
| Agent workflow / backup automation | Pipedream | https://github.com/PipedreamHQ/pipedream | Как developer-friendly workflow layer, если нужен backup |
| Social distribution | Postiz | https://github.com/gitroomhq/postiz-app | Календарь постов / social scheduling |
| Shorts generation | MoneyPrinterTurbo | https://github.com/harry0703/MoneyPrinterTurbo | AI short video generation |
| Video editing | OpenCut | https://github.com/OpenCut-app/OpenCut | Open-source video editor |
| Video with code | Remotion | https://github.com/remotion-dev/remotion | Code-based video rendering |
| Research memory | Papra | https://github.com/papra-hq/papra | Хранение research / clipping |
| Knowledge base | Memos | https://github.com/usememos/memos | Заметки, идеи, snippets |

### Партнеру: что решить и снять для Video 2

**Решить до съемки:**

1. Micro-SaaS фиксируем как `Open-Source Tool Radar for Content Creators`.
2. Где будет итоговый экран продукта: простая локальная страница или таблица-дашборд с карточками найденных repo.
3. Какие 5-6 repo попадут в финальный стек, а какие останутся backup.

**Конкретная идея micro-SaaS:** пользователь вводит нишу, например `AI video tools`, `content automation`, `solo founder stack`. Сервис показывает 10 open-source repo, группирует их по роли, дает краткий verdict `save/test/skip`, генерирует 3 идеи Shorts и 1 long-form тему по каждому repo.

**Почему это хорошая первая micro-SaaS идея:** она напрямую продвигает AtlasRepo, использует нашу реальную базу, понятна YouTube-аудитории и не требует строить сложный B2B-продукт. Это маленький продукт, который выглядит полезным уже на первом экране.

**Снять:**

1. Empty state: пустая таблица/дашборд.
2. AtlasRepo: поиск 5 проектов.
3. Activepieces/Pipedream: workflow canvas.
4. Генерация тем/описаний.
5. Postiz: календарь публикаций.
6. MoneyPrinterTurbo/OpenCut/Remotion: видео/shorts production screen.
7. Final screen: готовый контент-план + очередь публикаций.

---

## Video 3: This Website Found 3 Gold GitHub Repos for a Content Factory

**Рабочее название:** `This Website Found 3 Gold GitHub Repos for a Content Factory`

**Русская формулировка:** `Этот сайт нашел 3 золотых GitHub repo для контент-фабрики`

**Статус:** берем как обзор AtlasRepo.

**Что продаем:** не просто "посмотрите наш сайт", а use-case: AtlasRepo помогает быстро найти open-source проекты под конкретную задачу.

**Конкретная задача:** собрать content factory in 2026.

### 3 gold repo для обзора AtlasRepo

| # | Repo | Ссылка | Почему gold |
|---|---|---|---|
| 1 | Postiz | https://github.com/gitroomhq/postiz-app | Open-source social media scheduling, сразу понятный creator/founder use-case |
| 2 | MoneyPrinterTurbo | https://github.com/harry0703/MoneyPrinterTurbo | AI Shorts/Reels/TikToks generation, сильный вау-фактор |
| 3 | OpenMontage | https://github.com/calesthio/OpenMontage | Agentic video production system, выглядит как более свежий и острый gold repo |

**Backup repo для замены/расширения:**

- OpenCut — https://github.com/OpenCut-app/OpenCut
- Remotion — https://github.com/remotion-dev/remotion
- Activepieces — https://github.com/activepieces/activepieces
- browser-use/video-use — https://github.com/browser-use/video-use
- Papra — https://github.com/papra-hq/papra
- Memos — https://github.com/usememos/memos

### Партнеру: что снять для Video 3

1. AtlasRepo главная/поиск/категории.
2. Поиск запроса: `content automation`, `social media`, `video`, `shorts`, `agentic video`.
3. Карточки 3 repo в AtlasRepo.
4. Переход из AtlasRepo в GitHub.
5. Для каждого repo: README, stars, demo, practical use-case.
6. Финальный экран: `3 repo = research + production + distribution`.

---

## 10 Shorts: однотипные repo reviews

**Цель:** проверить формат на основном канале. Ролики должны быть однообразными специально, чтобы понять эффективность формулы.

**Формула каждого Shorts:**

1. 0-3 sec: `Stop doing X manually`.
2. 3-8 sec: repo name + что заменяет.
3. 8-35 sec: 2-3 быстрых экрана: GitHub, demo, proof.
4. 35-50 sec: кому полезно.
5. 50-60 sec: verdict + AtlasRepo CTA.

**CTA:** `Мы нашли это в AtlasRepo — радаре open-source инструментов для AI, automation и one-person companies.`

### Short #1: browser-use

**Hook:** Stop clicking buttons — let AI use websites.

**Показать:** browser automation demo, agent task, website interaction, result.

**Verdict:** TEST — best visual wow for agents using websites.

### Short #2: MoneyPrinterTurbo

**Hook:** Generate Shorts, Reels and TikToks with AI.

**Показать:** GitHub README, input prompt/topic, generated video flow, output example.

**Verdict:** TEST — strong creator wow, check quality honestly.

### Short #3: Ollama

**Hook:** Stop renting AI — run powerful models locally.

**Показать:** install/model pull, local model run, CLI or local chat, model list.

**Verdict:** SAVE — local AI foundation everyone should test.

### Short #4: Open WebUI

**Hook:** Build your own ChatGPT workspace.

**Показать:** interface, model connection/local/cloud, chat workspace, settings/demo.

**Verdict:** SAVE — instantly understandable self-hosted AI workspace.

### Short #5: Dify

**Hook:** Stop building AI products from scratch.

**Показать:** app builder, workflow/RAG screen, assistant setup, published app/demo.

**Verdict:** SAVE — faster path to AI apps and internal tools.

### Short #6: ComfyUI

**Hook:** This is Photoshop for AI workflows.

**Показать:** node graph, prompt, generated image, workflow gallery.

**Verdict:** SAVE — huge visual wow and instantly testable.

### Short #7: OpenHands

**Hook:** Stop writing every line of code yourself.

**Показать:** repo, task UI, code changes/diff, issue/task example.

**Verdict:** TEST — powerful, but needs careful control.

### Short #8: Multica

**Hook:** Turn coding agents into real teammates.

**Показать:** dashboard/issues, agent tasks, progress tracking, human + agent team workflow.

**Verdict:** TEST — strongest fresh one-person company narrative.

### Short #9: Twenty CRM

**Hook:** Stop paying for Salesforce before you even have a sales team.

**Показать:** CRM dashboard, contacts/companies, pipeline, AI/automation angle if visible.

**Verdict:** SAVE — business layer for a one-person company.

### Short #10: Postiz

**Hook:** Stop paying for social media scheduling tools.

**Показать:** calendar, post composer, connected platforms, queue/schedule.

**Verdict:** SAVE — great creator/founder infrastructure.

---

## What partner should prepare first

### Priority package A: Video 1 + 10 Shorts

Снять 10 repo из обновленного one-person company list без n8n. Это приоритет, потому что один съемочный пакет даст сразу long-form и 10 Shorts.

### Priority package B: Video 3 AtlasRepo overview

Снять AtlasRepo flow + 3 gold repo: Postiz, MoneyPrinterTurbo, OpenMontage.

### Priority package C: Video 2 micro-SaaS

Сначала выбрать точную реализацию micro-SaaS. Рекомендация: `AI Content Factory Dashboard`.

---

## Notes

- `Want2View` и `AtlasRepo` не GitHub repo, а сервисы. Их не ставить в "10 GitHub repo" список, но использовать как части content factory / обзора.
- Для первых 10 Shorts лучше не брать слишком нишевые или сомнительные repo. Нужны узнаваемые, визуальные, легко объясняемые проекты.
- Если какой-то repo тяжело поставить, это не проблема: снимаем GitHub + docs + demo/video/screenshots + limitation. Главное — честно не обещать production-ready там, где только test.
