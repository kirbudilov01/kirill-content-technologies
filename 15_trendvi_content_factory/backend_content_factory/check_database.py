#!/usr/bin/env python3
"""
Проверка состояния БД для content_factory:
- Количество проектов
- Количество каналов по платформам
- Количество видео с данными по платформам
- Статистика по сбору данных
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db import get_conn

logger = logging.getLogger(__name__)


async def check_database_health():
    """Проверить состояние и статистику БД."""
    conn = await get_conn()
    try:
        # Проверка структуры таблиц
        print("=" * 80)
        print("CONTENT FACTORY DATABASE HEALTH CHECK")
        print("=" * 80)

        # 1. Projects
        projects = await conn.fetch("SELECT COUNT(*) as count FROM content_factory_projects")
        print(f"\n📁 Проекты: {projects[0]['count']}")

        active_projects = await conn.fetch(
            "SELECT COUNT(*) as count FROM content_factory_projects WHERE is_active = TRUE"
        )
        print(f"   Активных: {active_projects[0]['count']}")

        # 2. Channels by platform
        print("\n📺 Каналы по платформам:")
        channels_by_platform = await conn.fetch(
            """
            SELECT 
                social_network,
                COUNT(*) as total,
                COUNT(CASE WHEN last_sync_status = 'ok' THEN 1 END) as synced_ok,
                COUNT(CASE WHEN last_sync_status = 'partial' THEN 1 END) as synced_partial,
                COUNT(CASE WHEN last_sync_status IS NULL THEN 1 END) as not_synced,
                MAX(last_sync_at) as last_sync_time
            FROM content_factory_channels
            GROUP BY social_network
            ORDER BY total DESC
            """
        )

        for row in channels_by_platform:
            print(f"   {row['social_network'].upper():12} | Всего: {row['total']:3} | OK: {row['synced_ok']:2} | Partial: {row['synced_partial']:2} | Not synced: {row['not_synced']:2} | Last: {row['last_sync_time']}")

        # 3. Videos with data by platform
        print("\n🎬 Видео по платформам (с метриками):")
        videos_by_platform = await conn.fetch(
            """
            SELECT 
                social_network,
                COUNT(*) as total,
                COUNT(CASE WHEN views > 0 THEN 1 END) as with_views,
                COUNT(CASE WHEN likes > 0 THEN 1 END) as with_likes,
                COUNT(CASE WHEN comments > 0 THEN 1 END) as with_comments,
                ROUND(AVG(views)::numeric, 0) as avg_views,
                ROUND(AVG(likes)::numeric, 0) as avg_likes,
                ROUND(AVG(comments)::numeric, 0) as avg_comments
            FROM content_factory_video_stats
            GROUP BY social_network
            ORDER BY total DESC
            """
        )

        for row in videos_by_platform:
            total = int(row["total"] or 0)
            with_views = int(row["with_views"] or 0)
            with_likes = int(row["with_likes"] or 0)
            with_comments = int(row["with_comments"] or 0)
            print(f"\n   {row['social_network'].upper()}:")
            print(f"      Видео: {total} | Просмотры: {with_views} ({(with_views / max(1, total) * 100):.0f}%) | avg: {row['avg_views']}")
            print(f"      Лайки: {with_likes} ({(with_likes / max(1, total) * 100):.0f}%) | avg: {row['avg_likes']}")
            print(f"      Комментарии: {with_comments} ({(with_comments / max(1, total) * 100):.0f}%) | avg: {row['avg_comments']}")

        # 4. Data completeness
        print("\n✅ Полнота данных (видео с ВСЕ тремя метриками):")
        complete = await conn.fetch(
            """
            SELECT 
                social_network,
                COUNT(*) as total,
                COUNT(CASE WHEN views > 0 AND likes > 0 AND comments > 0 THEN 1 END) as complete,
                ROUND(100.0 * COUNT(CASE WHEN views > 0 AND likes > 0 AND comments > 0 THEN 1 END) / COUNT(*)::numeric, 1) as percent
            FROM content_factory_video_stats
            GROUP BY social_network
            ORDER BY percent DESC
            """
        )

        for row in complete:
            status = "✓" if row['percent'] >= 80 else "⚠" if row['percent'] >= 50 else "✗"
            print(f"   {status} {row['social_network'].upper():12} | {row['complete']:3}/{row['total']:3} ({row['percent']:5.1f}%)")

        # 5. Recent sync errors
        print("\n⚠️  Недавние ошибки синхронизации:")
        errors = await conn.fetch(
            """
            SELECT 
                social_network,
                channel_title,
                last_sync_error,
                last_sync_at
            FROM content_factory_channels
            WHERE last_sync_error IS NOT NULL
            ORDER BY last_sync_at DESC
            LIMIT 5
            """
        )

        if errors:
            for row in errors:
                print(f"   {row['social_network'].upper()} | {row['channel_title']}")
                print(f"      Error: {row['last_sync_error'][:100]}...")
                print(f"      Time: {row['last_sync_at']}")
        else:
            print("   Нет ошибок ✓")

        # 6. Data freshness
        print("\n📅 Свежесть данных (последняя сборка):")
        freshness = await conn.fetch(
            """
            SELECT 
                social_network,
                MAX(captured_at) as last_capture,
                MIN(captured_at) as first_capture,
                COUNT(*) as video_count
            FROM content_factory_video_stats
            GROUP BY social_network
            ORDER BY last_capture DESC
            """
        )

        for row in freshness:
            print(f"   {row['social_network'].upper():12} | Last: {row['last_capture']} | Videos: {row['video_count']}")

        print("\n" + "=" * 80)

    finally:
        await conn.close()


async def get_detailed_stats(social_network: Optional[str] = None):
    """Получить детальную статистику по платформе."""
    conn = await get_conn()
    try:
        if social_network:
            print(f"\n\n📊 ДЕТАЛЬНАЯ СТАТИСТИКА: {social_network.upper()}")
            print("=" * 80)

            # Каналы
            channels = await conn.fetch(
                """
                SELECT 
                    channel_id,
                    channel_title,
                    channel_url,
                    last_sync_status,
                    last_sync_at,
                    (SELECT COUNT(*) FROM content_factory_video_stats v WHERE v.channel_id = c.channel_id) as video_count
                FROM content_factory_channels c
                WHERE social_network = $1
                ORDER BY video_count DESC
                LIMIT 10
                """,
                social_network,
            )

            print(f"\nТоп каналов ({len(channels)}):")
            for ch in channels:
                print(
                    f"  • {ch['channel_title'][:50]:50} | Videos: {ch['video_count']:4} | Status: {ch['last_sync_status']} | Last: {ch['last_sync_at']}"
                )

            # Videos stats
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_videos,
                    COUNT(DISTINCT channel_id) as channels,
                    MIN(published_at) as oldest_video,
                    MAX(published_at) as newest_video,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY views) as median_views,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY likes) as median_likes,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY comments) as median_comments,
                    MAX(views) as max_views,
                    MAX(likes) as max_likes,
                    MAX(comments) as max_comments
                FROM content_factory_video_stats
                WHERE social_network = $1
                """,
                social_network,
            )

            print(f"\nВидео статистика:")
            print(f"  Всего видео: {stats['total_videos']}")
            print(f"  Каналов: {stats['channels']}")
            print(f"  Период: {stats['oldest_video']} ... {stats['newest_video']}")
            print(f"  Просмотры (median/max): {float(stats['median_views'] or 0):.0f} / {stats['max_views']}")
            print(f"  Лайки (median/max): {float(stats['median_likes'] or 0):.0f} / {stats['max_likes']}")
            print(f"  Комментарии (median/max): {float(stats['median_comments'] or 0):.0f} / {stats['max_comments']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)

    # Запуск проверки
    asyncio.run(check_database_health())

    # Опционально: детальная статистика для конкретной платформы
    # asyncio.run(get_detailed_stats("youtube"))
