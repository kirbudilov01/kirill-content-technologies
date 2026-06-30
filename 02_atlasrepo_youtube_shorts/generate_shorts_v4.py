from pathlib import Path

from openpyxl import Workbook


OUT_DIR = Path(__file__).resolve().parent
HOST_MD = OUT_DIR / "ATLAS_REPO_SHORTS_V4_SIMPLE_READABLE.md"
PARTNER_MD = OUT_DIR / "ATLAS_REPO_SHORTS_V4_PARTNER_SCREENCAST_TASKS.md"
XLSX = OUT_DIR / "ATLAS_REPO_SHORTS_V4_SIMPLE_READABLE.xlsx"


TOPICS = [
    {
        "title": "AI-инструменты выходят каждый день. Как не утонуть?",
        "hook": "Каждый день выходит новый AI-инструмент, и половина из них выглядит как революция.",
        "angle": "Показываем не список названий, а простой фильтр: что делает, кому полезно, можно ли быстро проверить.",
        "tool": "AtlasRepo feed",
        "link": "https://atlasrepo.com",
        "shots": ["AtlasRepo главная/лента", "3 карточки инструментов", "фильтр или поиск", "крупно вердикт Save/Test/Skip"],
    },
    {
        "title": "Бесплатная альтернатива дорогому SaaS: где искать?",
        "hook": "Перед тем как платить за очередной SaaS, я теперь проверяю одну вещь.",
        "angle": "Есть ли open-source альтернатива, которую можно поставить, потрогать и понять за 5 минут.",
        "tool": "AtlasRepo + GitHub",
        "link": "https://atlasrepo.com",
        "shots": ["платный SaaS pricing без личных данных", "AtlasRepo поиск alternative", "GitHub README", "финал: цена 0 vs подписка"],
    },
    {
        "title": "AI пишет код быстро, но часто не туда",
        "hook": "Самая частая проблема с AI-кодингом: он пишет быстро, но вообще не понимает твой проект.",
        "angle": "Показываем, зачем нужны правила проекта, AGENTS.md или CLAUDE.md, чтобы AI не ломал соседние части.",
        "tool": "AGENTS.md / CLAUDE.md",
        "link": "https://github.com/agentsmd/agents.md",
        "shots": ["repo без правил", "файл AGENTS.md или CLAUDE.md", "AI task до/после", "крупно: меньше хаоса"],
    },
    {
        "title": "Cursor без rules — это быстрый хаос",
        "hook": "Cursor не делает проект умнее сам по себе. Он просто очень быстро усиливает то, что уже есть.",
        "angle": "Если в проекте нет rules, тестов и понятной задачи, AI ускоряет хаос.",
        "tool": "Cursor rules",
        "link": "https://cursor.com",
        "shots": ["Cursor editor", "rules file", "одна задача для AI", "до/после ответа"],
    },
    {
        "title": "Что такое MCP человеческим языком",
        "hook": "Если коротко: раньше AI только советовал, теперь ему пытаются дать руки.",
        "angle": "MCP подключает к AI браузер, файлы, GitHub, таблицы и другие действия.",
        "tool": "Playwright MCP",
        "link": "https://github.com/microsoft/playwright-mcp",
        "shots": ["схема AI -> tools", "Playwright MCP repo", "браузерное действие", "вердикт: чат стал действием"],
    },
    {
        "title": "AI может открыть сайт и проверить кнопку",
        "hook": "Представь, что AI не просто говорит, где баг, а сам открывает сайт и проверяет кнопку.",
        "angle": "Browser agents полезны для тестов, ресерча, QA и скучных проверок.",
        "tool": "Playwright MCP / browser agents",
        "link": "https://github.com/microsoft/playwright-mcp",
        "shots": ["браузер", "клик по странице", "скриншот ошибки", "issue или checklist"],
    },
    {
        "title": "n8n не умер, но агенты подбираются близко",
        "hook": "Каждый раз, когда выходит новый AI-агент, кто-то пишет: n8n умер. Я бы не спешил.",
        "angle": "n8n силен там, где нужны стабильные workflow. Агенты сильны там, где нужна гибкость.",
        "tool": "n8n + Claude/agents",
        "link": "https://github.com/n8n-io/n8n",
        "shots": ["n8n workflow", "agent workflow mock", "таблица: стабильно/гибко", "вердикт: не замена, а выбор"],
    },
    {
        "title": "Open-source инструмент, который выглядит как платный продукт",
        "hook": "Иногда на GitHub находишь штуку, которая выглядит так, будто за нее должны брать 99 долларов в месяц.",
        "angle": "Показываем один инструмент: что делает, почему выглядит дорого, где подвох.",
        "tool": "AtlasRepo selected tool",
        "link": "https://atlasrepo.com",
        "shots": ["красивый demo screen", "GitHub stars/README", "install или demo", "подвох: setup/issues"],
    },
    {
        "title": "GitHub stars врут",
        "hook": "Большие звезды на GitHub не всегда означают, что инструмент живой.",
        "angle": "Смотрим не только stars, а commits, issues, README, demo и понятность установки.",
        "tool": "GitHub + AtlasRepo scoring",
        "link": "https://atlasrepo.com",
        "shots": ["repo с большими stars", "last commit", "issues", "маленький но живой repo"],
    },
    {
        "title": "Как я выбираю AI-инструмент за 30 секунд",
        "hook": "У меня есть фильтр на 30 секунд, чтобы понять: сохранять инструмент или закрывать вкладку.",
        "angle": "Что делает? Кому нужно? Есть demo? Живой ли repo? Можно ли быстро проверить?",
        "tool": "AtlasRepo method",
        "link": "https://atlasrepo.com",
        "shots": ["таймер 30 sec", "README", "demo", "Save/Test/Skip карточка"],
    },
    {
        "title": "AI skills — это не магия, а заготовки для работы",
        "hook": "AI skills звучит сложно, но идея простая: не объяснять агенту одно и то же каждый раз.",
        "angle": "Skill хранит правила, стиль и шаги, чтобы AI делал повторяемую работу.",
        "tool": "OpenClaw / Claude skills",
        "link": "https://github.com/openclaw/skills",
        "shots": ["папка skills", "один skill крупно", "задача до/после", "вердикт: экономит повторения"],
    },
    {
        "title": "Большинство AI skills бесполезны. Вот мой фильтр",
        "hook": "Если skill просто красиво называется, но не экономит время, он мне не нужен.",
        "angle": "Полезный skill должен давать повторяемый результат: ревью, тест, docs, чеклист, фикс.",
        "tool": "Claude/OpenClaw skills",
        "link": "https://github.com/openclaw/skills",
        "shots": ["список skills", "плохой пример", "хороший пример", "save/test/skip"],
    },
    {
        "title": "Hermes против OpenClaw без nerd-режима",
        "hook": "Я не хочу сравнивать названия. Я хочу понять: где быстрее собрать полезного ассистента.",
        "angle": "Один и тот же простой assistant в двух подходах: старт, навыки, demo, боль.",
        "tool": "Hermes Agent + OpenClaw",
        "link": "https://github.com/NousResearch/hermes-agent | https://github.com/openclaw/skills",
        "shots": ["два repo рядом", "быстрый setup", "одинаковая задача", "таблица победителя"],
    },
    {
        "title": "AI-агент не должен быть умным. Он должен доводить дело",
        "hook": "Мне не нужен агент, который красиво рассуждает. Мне нужен агент, который доводит задачу до результата.",
        "angle": "Проверяем инструмент по артефакту: файл, diff, отчет, скриншот, workflow.",
        "tool": "Any agent from AtlasRepo",
        "link": "https://atlasrepo.com",
        "shots": ["agent chat", "созданный файл/diff", "результат в браузере", "вердикт: есть артефакт?"],
    },
    {
        "title": "AI-агенты опаснее обычного софта",
        "hook": "Обычный софт делает то, что ты нажал. AI-агент может сделать то, что он понял.",
        "angle": "Поэтому важны permissions, sandbox, логи и ограничение доступа.",
        "tool": "agent safety checklist",
        "link": "https://atlasrepo.com",
        "shots": ["permissions screen", "terminal command warning", "logs", "чеклист безопасности"],
    },
    {
        "title": "Самый простой тест для любого AI repo",
        "hook": "Перед тем как ставить AI-инструмент, я задаю ему один тупой тест.",
        "angle": "Может ли он показать результат быстрее, чем я сам объясню, зачем он нужен?",
        "tool": "AtlasRepo review format",
        "link": "https://atlasrepo.com",
        "shots": ["GitHub README", "demo", "таймер", "вердикт"],
    },
    {
        "title": "AI для маркетинга: не генератор постов, а сборочная линия",
        "hook": "AI в маркетинге полезен не тогда, когда пишет один пост, а когда собирает весь процесс.",
        "angle": "Идея, ресерч, черновик, таблица, публикация, аналитика — вот где automation имеет смысл.",
        "tool": "n8n + AtlasRepo content workflow",
        "link": "https://github.com/n8n-io/n8n | https://atlasrepo.com",
        "shots": ["контент-таблица", "n8n workflow", "AI draft", "финальный календарь"],
    },
    {
        "title": "Контент-идеи из GitHub, а не из воздуха",
        "hook": "Если каждый день придумывать темы из головы, ты быстро устанешь.",
        "angle": "Свежие repo сами подсказывают тренды: агенты, MCP, open-source SaaS, AI coding.",
        "tool": "AtlasRepo",
        "link": "https://atlasrepo.com",
        "shots": ["AtlasRepo feed", "карточка repo", "из repo -> тема shorts", "контент-план"],
    },
    {
        "title": "Как из одного repo сделать 5 роликов",
        "hook": "Один хороший репозиторий — это не один ролик. Это минимум пять углов.",
        "angle": "Обзор, честный тест, ошибка, сравнение с SaaS, урок для вайбкодинга.",
        "tool": "AtlasRepo content method",
        "link": "https://atlasrepo.com",
        "shots": ["одна карточка repo", "5 заголовков", "быстрый монтаж углов", "финал: контент-машина"],
    },
    {
        "title": "AI coding для обычного человека",
        "hook": "AI coding — это не про то, что ты больше не думаешь. Это про то, что меньше тонешь в рутине.",
        "angle": "Показываем простую схему: идея, prompt, diff, проверка, правка, demo.",
        "tool": "Cursor/Claude/Codex-style workflow",
        "link": "https://atlasrepo.com",
        "shots": ["идея в заметке", "AI editor", "diff", "работающий экран"],
    },
]


VARIANTS = [
    ("обывательский тест", "смотрим без сложных слов, есть ли тут реальная польза"),
    ("честная проверка", "не верим красивому README, пока не увидим понятный результат на экране"),
    ("для маркетолога", "смотрим на это как на инструмент для контента, роста или автоматизации"),
    ("для фаундера", "проверяем один вопрос: поможет ли это быстрее собрать продукт или сэкономить деньги"),
    ("для разработчика", "проверяем, уменьшает ли это рутину или просто добавляет новый слой хаоса"),
]

BRIDGES = [
    "Сегодня",
    "В этом ролике",
    "За минуту",
    "Проверяю на простом примере:",
    "Без лекции и сложных терминов:",
    "Смотрю как обычный человек:",
    "Смотрю как человек, которому нужен результат:",
]

PROOF_LINES = [
    "На экране нужны только живые признаки: что это, где демо, где польза и где подвох.",
    "Показываю не легенду из README, а то, что можно быстро понять глазами.",
    "Если за пару экранов непонятно, зачем это нужно, значит инструмент пока не готов для широкой аудитории.",
    "Главное не название инструмента, а понятный результат: экран, файл, workflow, отчет или экономия времени.",
    "Я специально смотрю на самый простой путь: открыть, понять, проверить, сделать вывод.",
]


def make_script(topic, variant_name, variant_line, number):
    cta = "Я такие инструменты собираю в AtlasRepo, чтобы не искать их вручную по всему интернету."
    if number % 5 == 0:
        cta = "Если хочешь, чтобы я так же проверял новые инструменты каждый день, подпишись и загляни в AtlasRepo."
    elif number % 3 == 0:
        cta = "В AtlasRepo я сохраняю только то, что можно быстро понять, проверить и применить."

    bridge = BRIDGES[number % len(BRIDGES)]
    proof = PROOF_LINES[number % len(PROOF_LINES)]
    first_word = topic["angle"].split(" ", 1)[0]
    if first_word.isupper() or first_word in {"AI", "MCP", "GitHub", "Cursor", "Open-source"}:
        angle = topic["angle"]
    else:
        angle = topic["angle"][0].lower() + topic["angle"][1:]
    return (
        f"{topic['hook']} "
        f"{bridge} {variant_line}. "
        f"Смысл простой: {angle} "
        f"{proof} "
        f"Мой вердикт в конце всегда один из трех: save, test или skip. "
        f"{cta}"
    )


def make_overlay(topic, number):
    overlays = [
        "Save, test или skip?",
        "Стоит твоего времени?",
        "AI tool без сложных слов",
        "Проверяю за 60 секунд",
        "Хайп или польза?",
    ]
    return overlays[number % len(overlays)]


def make_partner_task(topic, number):
    shots = topic["shots"]
    return (
        f"Short #{number}. Тема: {topic['title']}\n"
        f"Сервис/ссылка: {topic['tool']} — {topic['link']}\n"
        "Нужно снять вертикальный скринкаст 9:16, без приватных данных, ключей, почты, токенов и платежных экранов.\n"
        f"Кадры: 1) {shots[0]}; 2) {shots[1]}; 3) {shots[2]}; 4) {shots[3]}; "
        "5) финальная карточка крупно: SAVE / TEST / SKIP.\n"
        "Темп: каждый кадр 2-5 секунд, курсор двигается медленно, важные места приблизить. "
        "Если инструмент не запускается, снять README, issue/error и экран с честным ограничением — это тоже материал.\n"
    )


items = []
for i in range(100):
    topic = TOPICS[i % len(TOPICS)]
    variant_name, variant_line = VARIANTS[(i // len(TOPICS)) % len(VARIANTS)]
    number = i + 1
    day = (i // 3) + 1
    slot = (i % 3) + 1
    script = make_script(topic, variant_name, variant_line, number)
    items.append(
        {
            "number": number,
            "day": day,
            "slot": slot,
            "title": topic["title"],
            "audience": variant_name,
            "overlay": make_overlay(topic, number),
            "script": script,
            "tool": topic["tool"],
            "link": topic["link"],
            "partner_task": make_partner_task(topic, number),
        }
    )


host_lines = [
    "# AtlasRepo Shorts V4 — простые сценарии на 30-60 секунд\n\n",
    "Принцип V4: сначала бытовая боль или понятная выгода, потом инструмент. Названия Hermes, MCP, OpenClaw, n8n и Cursor не должны быть первым смыслом ролика. Текст можно читать почти без подготовки: один абзац, короткие фразы, финальный вердикт Save/Test/Skip.\n\n",
    "Формула каждого шортса: хук -> простое объяснение -> что показываем на экране -> вердикт -> мягкий переход в AtlasRepo.\n\n",
]
for item in items:
    host_lines.extend(
        [
            f"## {item['number']}. День {item['day']}, слот {item['slot']}: {item['title']}\n\n",
            f"**Кому:** {item['audience']}  \n",
            f"**Первый экран:** {item['overlay']}  \n",
            f"**Инструмент:** {item['tool']}  \n",
            f"**Ссылка:** {item['link']}  \n\n",
            "**Озвучка, читать как есть:**\n\n",
            item["script"],
            "\n\n---\n\n",
        ]
    )

partner_lines = [
    "# AtlasRepo Shorts V4 — задачи партнеру на скринкасты\n\n",
    "Общие правила: вертикальный формат 9:16, чистый браузер/терминал, без приватных данных. Не надо записывать длинные туториалы: нужны короткие визуальные доказательства под озвучку. Каждый шорт должен иметь 4-5 быстрых кадров и финальную карточку SAVE / TEST / SKIP.\n\n",
    "Что нельзя показывать: API-ключи, токены, email, личные аккаунты, платежи, приватные репозитории, внутренние базы, админки с реальными пользователями.\n\n",
]
for item in items:
    partner_lines.extend([f"## {item['number']}. {item['title']}\n\n", item["partner_task"], "\n"])

HOST_MD.write_text("".join(host_lines), encoding="utf-8")
PARTNER_MD.write_text("".join(partner_lines), encoding="utf-8")

wb = Workbook()
ws = wb.active
ws.title = "Shorts V4"
ws.append(["#", "day", "slot", "title", "audience", "first_screen", "tool", "link", "voiceover", "partner_task"])
for item in items:
    ws.append(
        [
            item["number"],
            item["day"],
            item["slot"],
            item["title"],
            item["audience"],
            item["overlay"],
            item["tool"],
            item["link"],
            item["script"],
            item["partner_task"],
        ]
    )
ws.freeze_panes = "A2"
widths = {"A": 6, "B": 8, "C": 8, "D": 42, "E": 20, "F": 26, "G": 26, "H": 45, "I": 90, "J": 90}
for col, width in widths.items():
    ws.column_dimensions[col].width = width
wb.save(XLSX)

print(HOST_MD)
print(PARTNER_MD)
print(XLSX)
print("items", len(items))
print("words_min", min(len(i["script"].split()) for i in items))
print("words_max", max(len(i["script"].split()) for i in items))
