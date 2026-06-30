# 🚀 QUICK START - ЗАПУСТИ И ЗАБУДЬ

## 1️⃣ ВСЁ ЗА ОДИН РАУНД (5 минут)

Скопируй и запусти эту команду:

```bash
cd "/Users/kirill/Desktop/CONTENT DISTRIBUTION" && \
chmod +x setup_automation.sh start_automation.sh && \
./setup_automation.sh && \
./start_automation.sh
```

**Готово!** Система начнёт публиковать 🚀

---

## 2️⃣ ЧТО ПРОИСХОДИТ ПОСЛЕ ЗАПУСКА?

✅ Система проверяет очередь каждые 15 минут
✅ Публикует посты по расписанию
✅ На все платформы одновременно (Twitter, Threads, Instagram, etc.)
✅ Комментирует на Threads автоматически
✅ Логирует всё в `scheduler.log`

---

## 3️⃣ МОНИТОРИНГ В РЕАЛЬНОМ ВРЕМЕНИ

В новом терминале:

```bash
tail -f "/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT/scheduler.log"
```

Увидишь:
```
✅ Published 2 items to twitter, threads
📊 Queue: 5 pending, 12 published
⏳ Next cycle: 15 minutes
```

---

## 4️⃣ ЕСЛИ ЧТО-ТО ПОШЛО НЕ ТАК

**Посты не публикуются?**
```bash
cd "/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT"
source .venv/bin/activate
python scheduler.py --mode=once
deactivate
```

**Threads не комментирует?**
```bash
tail -f "/Users/kirill/Desktop/CONTENT DISTRIBUTION/TELEGRAM : THREADS AGENT/threads_autopilot/autopilot.log"
```

**Нужно остановить?**
```bash
# Если запущен вручную:
Ctrl + C

# Если автозапуск:
launchctl unload ~/Library/LaunchAgents/com.contentdistribution.scheduler.plist
```

---

## 5️⃣ ПЕРСОНАЛИЗАЦИЯ КОНТЕНТА

Отредактируй: `/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT/content_queue/queue.json`

Добавь пост:
```json
[
  {
    "content": "🎯 Your awesome post",
    "platforms": ["twitter", "threads"],
    "scheduled_at": "2026-05-20T15:00:00",
    "priority": 9,
    "hashtags": ["tag1", "tag2"]
  }
]
```

Сохрани — система автоматически опубликует!

---

## 6️⃣ КОМАНДЫ СПРАВОЧНИК

```bash
# Полная настройка
./setup_automation.sh

# Запустить 24/7
./start_automation.sh

# Одна проверка
cd AGENT && python scheduler.py --mode=once

# Просмотр логов
tail -f AGENT/scheduler.log

# Просмотр очереди
cat AGENT/content_queue/queue.json

# Остановить
Ctrl + C

# Перезапустить
./start_automation.sh
```

---

## ✅ ВСЁ ГОТОВО!

Твоя система теперь:
- 📤 Публикует 24/7
- 🤖 Работает автономно
- 💬 Комментирует на Threads
- 🎯 На основе твоей личности
- 📊 Отслеживает всё

**Просто запусти и смотри как растут метрики!** 🚀

---

## 📖 ПОДРОБНЕЕ

- Полная инструкция: `AUTOMATION_COMPLETE.md`
- Описание: `AUTONOMOUS_READY.md`
- Архитектура: `START_HERE.md`

**НАЧНИ ПРЯМО СЕЙЧАС:**

```bash
cd "/Users/kirill/Desktop/CONTENT DISTRIBUTION" && ./setup_automation.sh && ./start_automation.sh
```
