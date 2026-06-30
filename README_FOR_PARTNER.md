# AtlasRepo Content Production Pack

Дата сборки: 2026-07-01

Это рабочий пакет по контентной системе AtlasRepo: daily radar, Shorts, long-form YouTube, карусели, вертикальные видео/avatar pipeline, дистрибуция в соцсети и связанные Codex skills.

## С чего начать

1. `01_daily_radar/daily-radar.md`
   - логика ежедневного выбора тем;
   - источники истины: AtlasRepo, Google Sheet, want2view, новости, YouTube/workbook;
   - целевой ритм: 3 вертикальных видео, 3-5 постов, long-form.

2. `02_atlasrepo_youtube_shorts/ATLAS_REPO_CONTENT_MASTER.md`
   - главный контентный документ по YouTube/Shorts.

3. `02_atlasrepo_youtube_shorts/ATLAS_REPO_SHORTS_V4_SIMPLE_READABLE.md`
   - готовые readable Shorts.

4. `02_atlasrepo_youtube_shorts/ATLAS_REPO_SHORTS_V4_PARTNER_SCREENCAST_TASKS.md`
   - что именно записывать на экране для Shorts.

5. `02_atlasrepo_youtube_shorts/ATLAS_REPO_LONGFORM_V3_FULL_15_20_MIN_SCRIPTS.md`
   - long-form сценарии.

6. `03_instagram_carousel/`
   - HTML/PNG/export pipeline для Instagram-каруселей.

7. `04_vertical_video_avatar/`
   - пайплайн вертикальных видео, talking-avatar, captions, thumbnails, sample scripts.

8. `05_distribution_agents/`
   - SMM/X/Threads agent материалы и безопасные config examples.
   - Реальные Postiz setup-логи и старые команды не включены, потому что в них встречались live keys.

9. `07_codex_skills/`
   - скиллы Codex, которые описывают генерацию Shorts, long-form, video, AI-video.

## Что специально не включено

- `.env`, реальные config-файлы, tokens, API keys.
- Browser profiles, auth/session/state files.
- `node_modules`, `venv`, `.git`, caches.
- Тяжелые рабочие видео-выводы и промежуточные job artifacts.
- Telegram/session/runtime файлы.

Если нужен полный runtime конкретного агента, его лучше переносить отдельно после ревизии секретов.
Postiz подключать заново через чистый `.env.example`, а не через старые локальные файлы.

## Быстрый смысл системы

AtlasRepo дает proof layer: конкретные open-source проекты и use cases.
want2view/YouTube workbook дает format validation: что уже смотрят и какие хуки работают.
Codex собирает daily slate: Shorts, X/Threads/WeChat posts, carousel, long-form topic, screencast brief.
Postiz/agents закрывают публикацию и дистрибуцию, но реальный автопостинг должен идти только после ручного approve.
