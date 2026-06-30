#!/usr/bin/env python3
"""
Утилита для тестирования парсеров по всем платформам.
Проверяет что каждый парсер корректно собирает данные.

Использование:
    python test_parsers.py                    # Проверить все платформы
    python test_parsers.py --platform youtube # Проверить конкретную платформу
    python test_parsers.py --verbose          # Подробный вывод
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from content_factory.parsers import parse_channel

logger = logging.getLogger(__name__)

# Тестовые ссылки для каждой платформы
TEST_CHANNELS = {
    "youtube": "https://www.youtube.com/@YouTube",
    "tiktok": "https://www.tiktok.com/@tiktok",
    "instagram": "https://www.instagram.com/instagram/",
    "vk": "https://vk.com/youtube",
    "rutube": "https://rutube.ru/channel/1/",
    "dzen": "https://dzen.ru/youtube",
    "likee": "https://likee.video/@likeeofficial",
    # "ok": "https://ok.ru/youtube",  # OK требует специальной обработки
    # "x": None,  # X/Twitter пока не интегрирован
}

EXPECTED_METRICS = {
    "youtube": {"views": True, "likes": True, "comments": True},
    "tiktok": {"views": True, "likes": True, "comments": True},
    "instagram": {"views": True, "likes": True, "comments": True},
    "vk": {"views": True, "likes": True, "comments": True},
    "rutube": {"views": True, "likes": True, "comments": True},
    "dzen": {"views": True, "likes": True, "comments": True},
    "likee": {"views": True, "likes": True, "comments": True},
    "ok": {"views": True, "likes": True, "comments": True},
}


async def test_parser(
    platform: str,
    url: str,
    owner_id: int = 999999,
    verbose: bool = False,
) -> dict:
    """Тестировать парсер для платформы."""
    print(f"\n{'=' * 80}")
    print(f"🧪 Тестирование {platform.upper()}")
    print(f"   URL: {url}")
    print(f"{'=' * 80}")

    try:
        result = await parse_channel(
            network=platform,
            channel_url=url,
            owner_id=owner_id,
            period_days=30,
        )

        # Базовые результаты
        print(f"\n✓ Парсер выполнен успешно")
        print(f"  Статус: {result.sync_status}")
        print(f"  Канал: {result.channel_title or 'unknown'} (ID: {result.channel_external_id})")
        print(f"  Видео собрано: {len(result.videos)}")
        print(f"  Подписчики: {result.subscribers_count or 'unknown'}")

        if result.sync_message:
            print(f"  Сообщение: {result.sync_message}")

        # Анализ видео
        if result.videos:
            print(f"\n📊 Анализ видео ({len(result.videos)} видео):")

            videos_with_views = sum(1 for v in result.videos if v.views and v.views > 0)
            videos_with_likes = sum(1 for v in result.videos if v.likes and v.likes > 0)
            videos_with_comments = sum(1 for v in result.videos if v.comments and v.comments > 0)
            videos_complete = sum(
                1
                for v in result.videos
                if (v.views and v.views > 0)
                and (v.likes and v.likes > 0)
                and (v.comments and v.comments > 0)
            )

            print(f"  Просмотры: {videos_with_views}/{len(result.videos)} ({100*videos_with_views/len(result.videos):.0f}%)")
            print(f"  Лайки: {videos_with_likes}/{len(result.videos)} ({100*videos_with_likes/len(result.videos):.0f}%)")
            print(f"  Комментарии: {videos_with_comments}/{len(result.videos)} ({100*videos_with_comments/len(result.videos):.0f}%)")
            print(f"  Полные данные: {videos_complete}/{len(result.videos)} ({100*videos_complete/len(result.videos):.0f}%)")

            # Проверка ожидаемых метрик
            expected = EXPECTED_METRICS.get(platform, {})
            print(f"\n✓ Ожидаемые метрики:")

            for metric, required in expected.items():
                if metric == "views":
                    actual = videos_with_views > 0
                elif metric == "likes":
                    actual = videos_with_likes > 0
                elif metric == "comments":
                    actual = videos_with_comments > 0
                else:
                    actual = False

                status = "✓" if actual else "✗"
                print(f"  {status} {metric.capitalize()}: {'OK' if actual else 'MISSING'}")

            # Подробный вывод если запрошен
            if verbose and len(result.videos) > 0:
                print(f"\n📝 Примеры видео (первые 3):")
                for i, v in enumerate(result.videos[:3], 1):
                    print(f"\n  Video {i}:")
                    print(f"    Title: {v.title[:60]}")
                    print(f"    URL: {v.video_url}")
                    print(f"    Views: {v.views}, Likes: {v.likes}, Comments: {v.comments}")
                    print(f"    Published: {v.published_at}")
                    print(f"    Duration: {v.duration_seconds}s")

            return {
                "platform": platform,
                "status": "ok",
                "total_videos": len(result.videos),
                "views_coverage": 100 * videos_with_views / len(result.videos) if result.videos else 0,
                "likes_coverage": 100 * videos_with_likes / len(result.videos) if result.videos else 0,
                "comments_coverage": 100 * videos_with_comments / len(result.videos) if result.videos else 0,
                "completeness": 100 * videos_complete / len(result.videos) if result.videos else 0,
            }
        else:
            print(f"\n⚠️  Видео не найдены")
            return {
                "platform": platform,
                "status": "partial",
                "total_videos": 0,
                "error": "No videos found",
            }

    except Exception as exc:
        print(f"\n✗ Ошибка при парсинге {platform}")
        print(f"   {type(exc).__name__}: {str(exc)[:200]}")
        return {
            "platform": platform,
            "status": "error",
            "error": str(exc)[:200],
        }


async def test_all_parsers(verbose: bool = False, platform: Optional[str] = None):
    """Тестировать все парсеры или конкретный."""
    print("\n" + "=" * 80)
    print("PARSER TEST SUITE - Content Factory")
    print("=" * 80)

    platforms_to_test = (TEST_CHANNELS.keys() if platform is None else [platform])
    results = []

    for plat in platforms_to_test:
        if plat not in TEST_CHANNELS:
            print(f"\n⚠️  Платформа {plat} не найдена в тестовых ссылках")
            continue

        url = TEST_CHANNELS[plat]
        if url:
            result = await test_parser(plat, url, verbose=verbose)
            results.append(result)
        else:
            print(f"\n⏭️  Пропущена {plat} (тестовая ссылка не установлена)")

    # Итоговая таблица
    print(f"\n\n{'=' * 80}")
    print("📊 ИТОГОВАЯ ТАБЛИЦА")
    print("=" * 80)
    print(
        f"\n{'Platform':<12} | {'Status':<8} | {'Videos':<8} | {'Views':<8} | {'Likes':<8} | {'Comments':<10} | {'Complete':<10}"
    )
    print("-" * 80)

    for res in results:
        if res["status"] == "ok":
            print(
                f"{res['platform']:<12} | {res['status']:<8} | {res['total_videos']:<8} | "
                f"{res['views_coverage']:<7.0f}% | {res['likes_coverage']:<7.0f}% | {res['comments_coverage']:<9.0f}% | {res['completeness']:<9.0f}%"
            )
        else:
            print(f"{res['platform']:<12} | {res['status']:<8} | ERROR: {res.get('error', 'Unknown')[:40]}")

    # Статистика
    print("\n" + "=" * 80)
    successful = [r for r in results if r["status"] == "ok"]
    print(f"\n✓ Успешно протестировано: {len(successful)}/{len(results)}")

    if successful:
        avg_completeness = sum(r.get("completeness", 0) for r in successful) / len(successful)
        print(f"  Средняя полнота данных: {avg_completeness:.0f}%")

        excellent = [r for r in successful if r["completeness"] >= 80]
        good = [r for r in successful if 50 <= r["completeness"] < 80]
        poor = [r for r in successful if r["completeness"] < 50]

        if excellent:
            print(f"  ✓ Отличные результаты (≥80%): {', '.join(r['platform'] for r in excellent)}")
        if good:
            print(f"  ⚠  Хорошие результаты (50-80%): {', '.join(r['platform'] for r in good)}")
        if poor:
            print(f"  ✗ Требуют внимания (<50%): {', '.join(r['platform'] for r in poor)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    platform = None

    if "--platform" in sys.argv:
        idx = sys.argv.index("--platform")
        if idx + 1 < len(sys.argv):
            platform = sys.argv[idx + 1]

    asyncio.run(test_all_parsers(verbose=verbose, platform=platform))
