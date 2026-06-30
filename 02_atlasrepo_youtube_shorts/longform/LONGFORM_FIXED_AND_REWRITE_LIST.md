# Long-form: fixed topics, rewrites, rejects

Файл фиксирует текущий редакторский статус длинных видео. Это не финальные сценарии. Это карта: что берем, что переписываем, что выкидываем, где нужна начинка из реальных repo/проектов.

## Fixed: берем в работу

### 1. Я собрал micro-SaaS за вечер только из open-source repo

**Почему берем:** сильный массовый фрейм: продукт, скорость, open-source, деньги.

**Нужно решить:** конкретная ниша SaaS.

**Кандидаты ниш:**

- open-source alternatives finder;
- AI content calendar для YouTube/Shorts;
- AI tool radar для фаундеров/маркетологов;
- mini CRM/support desk на open-source базе.

**Repo-кандидаты из нашей базы:**

- `drawdb-io/drawdb` — база/схемы;
- `chatwoot/chatwoot` — support/CRM альтернатива;
- `langfuse/langfuse` — LLM analytics/observability;
- `usebruno/bruno` — API/dev workflow;
- `juspay/hyperswitch` — payments layer;
- `metabase/metabase` — analytics/dashboard;
- `n8n-io/n8n` — automation.

**Партнеру:** выбрать 2-3 SaaS-ниши, под каждую подобрать repo-кирпичи и снять: GitHub README, demo, install/setup, итоговый экран продукта, таблицу "что из чего собрано".

---

### 2. AI сам собрал мне контент-план на месяц из свежих open-source инструментов

**Почему берем:** тема напрямую связывает YouTube, Shorts, AtlasRepo и реальную пользу для маркетинга/контента.

**Нужно решить:** workflow: AtlasRepo feed -> отбор repo -> таблица -> сценарии -> задачи партнеру.

**Repo/инструменты-кандидаты:**

- `n8n-io/n8n` — automation;
- `langfuse/langfuse` — трекинг LLM/генераций;
- `metabase/metabase` или таблица — аналитика/дашборд;
- AtlasRepo feed — источник тем;
- GitHub repo pages — proof по инструментам.

**Партнеру:** снять цепочку до/после: пустая таблица, AtlasRepo feed, выбранные repo, workflow/n8n, заполненный контент-план на 30 дней.

---

### 3. Я проверил 100 AI-инструментов: 10 реально стоят твоего времени

**Почему берем:** доказанный конкурентный фрейм. Продает экономию времени.

**Нужно решить:** список 100 и финальные 10.

**Repo-кандидаты для финала:** брать из AtlasRepo/нашей базы, в том числе `n8n`, `Dify`, `Daytona`, `OpenCLI`, `MCP Context Forge`, `Langfuse`, `Bruno`, `Metabase`, `Chatwoot`, `AutoGPT`, `vLLM`, `Sentry`, `DrawDB`.

**Партнеру:** собрать 100 AI/open-source инструментов из AtlasRepo или нашей базы, отобрать 10. По каждому снять карточку, GitHub/сайт, README/demo, один экран пользы, одно ограничение, verdict `save/test/skip`.

---

### 4. Я открыл 50 новых GitHub repo за день. Большинство мусор, но эти 7 — золото

**Почему берем:** хорошая драматургия: шум, боль, отбор, золото.

**Нужно решить:** категории repo, чтобы не было хаоса.

**Категории:** AI agents, MCP, automation, devtools, marketing/content, open-source SaaS alternatives.

**Партнеру:** собрать 50 свежих repo из AtlasRepo/базы/GitHub trending, выбрать 7 лучших. Снять быстрый монтаж слабых repo и отдельные proof-экраны победителей.

---

### 5. Я протестировал AI tools для контента: какие реально делают работу, а не презентацию

**Почему берем:** лучше, чем "для маркетинга" в целом. Контент конкретнее и ближе к нашей задаче.

**Нужно решить:** задача теста: темы, сценарии, контент-план, нарезки, публикации, аналитика.

**Партнеру:** выбрать 10-15 open-source AI tools под контент-задачу из AtlasRepo/базы. По каждому снять вход, результат, сайт/GitHub, ограничение.

---

### 6. Хватит платить за 5 AI-сервисов: вот open-source замены

**Почему берем:** деньги и подписки понятны всем.

**Нужно решить:** конкретные пары paid -> open-source.

**Repo-кандидаты из базы:**

- Intercom/Zendesk -> `chatwoot/chatwoot`;
- Postman/Insomnia -> `usebruno/bruno`;
- BI dashboards -> `metabase/metabase`;
- monitoring/error tracking -> `getsentry/sentry`;
- automation -> `n8n-io/n8n` или `apache/airflow`;
- payments routing -> `juspay/hyperswitch`;
- docs/files/collab -> `nextcloud/server`.

**Партнеру:** снять paid pricing, open-source repo, README/demo, что заменяет, где уступает, финальную таблицу сравнений.

---

### 7. Перед тем как купить очередную AI-подписку, проверь эти 10 GitHub repo

**Почему берем:** мягкий money-saving фрейм, хорошо заводит в AtlasRepo.

**Нужно решить:** 10 repo по категориям, не случайная пачка.

**Партнеру:** собрать 10 repo: research, automation, content, UI/design, devtools, docs, agents, browser automation, analytics, knowledge base. Снять quick proof по каждому.

---

### 8. Я собрал open-source AI stack для контента вместо 5 платных подписок

**Почему берем:** конкретнее, чем "что сломалось". Есть стек, экономия, честное сравнение.

**Нужно решить:** 5 функций стека.

**Возможный стек:**

- research/поиск тем: AtlasRepo + GitHub;
- automation: `n8n`;
- LLM observability/логика: `langfuse`;
- таблица/дашборд: `metabase` или Google Sheet;
- assets/video helper: подобрать отдельно из AtlasRepo/GitHub.

**Партнеру:** выбрать paid reference для 5 функций и open-source/tool alternative для каждой. Снять pricing, альтернативу, короткий demo, итоговую схему стека.

---

### 9. AI Tools Tier List 2026: что save, что test, что skip

**Почему берем:** формат быстрый, понятный, хорошо режется на Shorts.

**Нужно решить:** категории и критерии.

**Партнеру:** собрать 20-30 инструментов из AtlasRepo/базы, подготовить tier board `S/A/B/Skip` или `Save/Test/Skip`, снять quick proof по верхним 10.

---

### 10. Open-source AI tools: S-tier, нормальные и мусор

**Почему берем:** жесткая сортировка дает мнение и удержание.

**Нужно решить:** не повторить тему 9 один-в-один. Здесь сделать именно open-source и с более жестким тоном.

**Партнеру:** собрать только open-source tools, отсечь SaaS-only. Снять GitHub proof: stars, last commit, README, demo, issue/activity.

---

### 11. Dev tools tier list: что реально ускоряет вайбкодинг

**Почему берем:** хороший мост в dev-аудиторию без Cursor-центричности.

**Нужно решить:** убрать Cursor как главный герой. Сравнивать категории: API, local env, observability, browser QA, docs, database, deploy.

**Repo-кандидаты:** `Daytona`, `OpenCLI`, `Bruno`, `Sentry`, `Langfuse`, `DrawDB`, `MCP Context Forge`, `vLLM`.

**Партнеру:** собрать devtools из базы, снять по каждому не обзор, а "как ускоряет": setup, типовая задача, результат.

---

### 12. 10 open-source AI tools, которые выглядят незаконно полезными

**Почему берем:** сильный конкурентный фрейм, хорошо работает в топах.

**Нужно решить:** инструменты должны реально выглядеть вау, не просто "полезная библиотека".

**Партнеру:** найти 10 зрелых/визуально понятных open-source tools из AtlasRepo/базы. Нужны demo screens, красивые интерфейсы, before/after или понятный result.

---

### 13. Бесплатные GitHub repo, которые заменяют дорогие продукты

**Почему берем:** близко к `Stop paying`, но можно сделать как подборку alternatives.

**Нужно решить:** не дублировать тему 6. Здесь лучше сделать шире: не только AI-сервисы, а дорогие продукты вообще.

**Партнеру:** подобрать пары paid product -> GitHub repo, снять pricing и альтернативу.

---

### 14. Я нашел open-source инструменты, которые выглядят как продукты на $10M

**Почему берем:** хороший продуктовый/визуальный угол.

**Нужно решить:** нужны реально зрелые проекты с интерфейсом, demo, понятным use-case.

**Repo-кандидаты:** `Chatwoot`, `Metabase`, `Sentry`, `DrawDB`, `Nextcloud`, `Langfuse`, `Bruno`.

**Партнеру:** снять красивые продуктовые экраны, не только GitHub. Если demo нет, тема теряет силу.

---

### 15. AI ломает SaaS-бизнес: что будет с обычными подписками

**Почему берем условно:** тема сильная, но только если будет на примерах. Без примеров это философская каша.

**Нужно решить:** сделать через 3-5 конкретных категорий: support, analytics, automation, content, devtools.

**Партнеру:** собрать примеры paid SaaS и open-source/AI alternatives, показать экономику и ограничения.

## Rewrite queue: переписать, но фрейм может жить

### A. X killed Y

**Что не нравится:** `Claude agents убьют n8n` избито. `OpenAI сделал tech stack устаревшим` непонятно. `Cursor убивает junior-разработчиков` выкинуть.

**Новая логика:** берем конкретный популярный сервис/категорию и показываем, что конкретная технология реально отъедает его use-case.

**Варианты на переписывание:**

1. **Open-source support desk против Intercom/Zendesk: можно ли перестать платить?**
   - Кандидат: `chatwoot/chatwoot`.

2. **Bruno против Postman: open-source API-клиент, который можно хранить в Git**
   - Кандидат: `usebruno/bruno`.

3. **Metabase против дорогих BI-дэшбордов: аналитика без enterprise-счета**
   - Кандидат: `metabase/metabase`.

4. **n8n против Zapier/Make: где open-source automation реально выигрывает**
   - Кандидат: `n8n-io/n8n`.

5. **Sentry open-source против дорогого monitoring stack: что реально можно забрать себе**
   - Кандидат: `getsentry/sentry`.

**Партнеру:** для каждого возможного баттла найти paid competitor, open-source repo, pricing, demo, ограничения, итоговую таблицу сравнения.

---

### B. Full Guide

**Что не нравится:** Cursor выкинуть, n8n automation слишком сложно в лоб, Claude Code для фаундера тоже пока сложно.

**Новая логика:** full guide должен быть не про один сложный инструмент, а про систему, которую реально интересно собрать.

**Варианты на переписывание:**

1. **Мультиагентная система для поиска AI-инструментов: один агент ищет, второй проверяет, третий делает контент-план**
   - AtlasRepo как источник и витрина результата.

2. **Codex + AtlasRepo + open-source tools: как собрать исследовательскую машину для новых repo**
   - Угол: не просто coding, а система отбора и упаковки инструментов.

3. **AI-команда вместо одного чатбота: как агенты делят работу по research, coding, QA и контенту**
   - Нужны реальные repo/инструменты под роли.

**Партнеру:** найти/предложить 3-5 repo для multi-agent/research/coding workflow и снять схему ролей + экраны каждого шага. Без реальной системы не писать сценарий.

---

### C. New release / Things you missed

**Что не нравится:** текущие темы шаблонные и пустые.

**Новая логика:** брать только из свежих новостей, чатов, релизов, GitHub trending, AtlasRepo feed. Этот блок нельзя писать заранее надолго.

**Рабочий формат:** `Новости недели: 5 AI/open-source релизов, которые реально стоит проверить`.

**Партнеру:** каждую неделю собрать 10-20 свежих сигналов, выбрать 5. Источники: AtlasRepo feed, GitHub releases/trending, Hacker News, Product Hunt, профильные Telegram/Discord/чат-сигналы от команды. По каждому нужен screenshot + ссылка + почему важно.

---

### D. AI will change / break industry

**Что не нравится:** слишком широко. `AI agents худшая вещь для интернета` и `маркетинг будет инженерной системой` звучат как эссе без ролика.

**Что можно оставить:** `AI ломает SaaS-бизнес` — но только через конкретные примеры и open-source alternatives.

**Партнеру:** собрать 3-5 конкретных категорий, где AI/open-source давит SaaS: support, automation, analytics, content, devtools.

## Reject / пока выкинуть

1. `Cursor 2.0: 5 функций...` — Cursor выкидываем из центральных тем.
2. `Cursor + MCP + rules...` — слишком заезжено и узко.
3. `Cursor убивает junior-разработчиков...` — не наш фокус.
4. `MCP объясняю простыми словами...` — beginners explainers сейчас не берем.
5. `AI Agents для новичков...` — слишком дно/обучалка без трафикового угла.
6. `RAG, agents, MCP, workflows: 7 терминов...` — образовательная энциклопедия, не то.
7. `Почему маркетинг после AI будет похож на инженерную систему` — слишком широко, пока выкинуть.

