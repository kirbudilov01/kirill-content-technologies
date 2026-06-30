from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

SocialNetworkKey = Literal[
    "youtube",
    "instagram",
    "tiktok",
    "x",
    "vk",
    "ok",
    "rutube",
    "likee",
    "dzen",
]
CollectionMethod = Literal["youtube_api", "external_api", "http_scraper", "browser_scraper"]
PlatformStatus = Literal["live", "credentials", "planned"]


@dataclass(frozen=True)
class PlatformDefinition:
    key: SocialNetworkKey
    label: str
    collection_method: CollectionMethod
    status: PlatformStatus
    parser_kind: str
    requires_credentials: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


PLATFORM_REGISTRY: dict[SocialNetworkKey, PlatformDefinition] = {
    "youtube": PlatformDefinition(
        key="youtube",
        label="YouTube",
        collection_method="youtube_api",
        status="live",
        parser_kind="native",
        notes="Эталонный коннектор на YouTube API с fallback на yt-dlp.",
    ),
    "instagram": PlatformDefinition(
        key="instagram",
        label="Instagram",
        collection_method="external_api",
        status="credentials",
        parser_kind="apify",
        requires_credentials=True,
        notes="Подключение через внешний API/Apify; собственный парсер не используется.",
    ),
    "tiktok": PlatformDefinition(
        key="tiktok",
        label="TikTok",
        collection_method="external_api",
        status="credentials",
        parser_kind="apify",
        requires_credentials=True,
        notes="Подключение через внешний API/Apify; собственный парсер не используется.",
    ),
    "x": PlatformDefinition(
        key="x",
        label="X (Twitter)",
        collection_method="http_scraper",
        status="planned",
        parser_kind="html_json",
        notes="Закладывается как HTTP/JSON-коннектор для публичных профилей.",
    ),
    "vk": PlatformDefinition(
        key="vk",
        label="VK",
        collection_method="http_scraper",
        status="live",
        parser_kind="html_json",
        notes="Ориентир на собственный парсинг публичных страниц и внутренних JSON-ответов.",
    ),
    "ok": PlatformDefinition(
        key="ok",
        label="Одноклассники",
        collection_method="http_scraper",
        status="live",
        parser_kind="html_json",
        notes="Подключен HTTP парсер публичных страниц с targeted discovery и video-page recovery.",
    ),
    "rutube": PlatformDefinition(
        key="rutube",
        label="Rutube",
        collection_method="http_scraper",
        status="live",
        parser_kind="html_json",
        notes="Подключен базовый HTTP парсер с извлечением публикаций и частичных метрик.",
    ),
    "likee": PlatformDefinition(
        key="likee",
        label="Likee",
        collection_method="http_scraper",
        status="live",
        parser_kind="html_json",
        notes="Подключен базовый HTTP парсер публичных страниц.",
    ),
    "dzen": PlatformDefinition(
        key="dzen",
        label="Яндекс.Дзен",
        collection_method="browser_scraper",
        status="live",
        parser_kind="playwright",
        notes="Подключен браузерный scraping с HTTP fallback и возвратом частичных данных.",
    ),
}

SOCIAL_NETWORKS: tuple[SocialNetworkKey, ...] = tuple(PLATFORM_REGISTRY.keys())
SOCIAL_NETWORKS_SQL = ", ".join(f"'{network}'" for network in SOCIAL_NETWORKS)


def get_platform(network: str) -> PlatformDefinition:
    return PLATFORM_REGISTRY[network]  # type: ignore[index]


def is_known_platform(network: str) -> bool:
    return network in PLATFORM_REGISTRY


def list_platforms() -> list[PlatformDefinition]:
    return [platform for key, platform in PLATFORM_REGISTRY.items() if key != "x"]