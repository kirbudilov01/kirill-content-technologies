import asyncio
import hashlib
import logging
import math
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple
import re
from zoneinfo import ZoneInfo

import googleapiclient.discovery
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


_SHARED_KEY_POOLS: Dict[Tuple[str, ...], "_SharedKeyPool"] = {}
_SHARED_KEY_POOLS_LOCK = threading.Lock()


class _SharedKeyPool:
    def __init__(self, api_keys: List[str]):
        self.all_keys: Tuple[str, ...] = tuple(api_keys)
        self.available_keys: List[str] = list(self.all_keys)
        self.cooled_down_keys: Dict[str, float] = {}
        self.current_key_idx = 0
        self.lock = threading.Lock()

    def _release_expired(self, now_ts: float):
        for key, cooldown_until in list(self.cooled_down_keys.items()):
            if now_ts >= cooldown_until:
                if key not in self.available_keys:
                    self.available_keys.append(key)
                del self.cooled_down_keys[key]

    def next_key(self) -> Tuple[Optional[str], Optional[float]]:
        with self.lock:
            now_ts = datetime.now(timezone.utc).timestamp()
            self._release_expired(now_ts)
            if self.available_keys:
                key = self.available_keys[self.current_key_idx % len(self.available_keys)]
                self.current_key_idx = (self.current_key_idx + 1) % max(1, len(self.available_keys))
                return key, 0.0

            if not self.cooled_down_keys:
                return None, None

            next_delay = min(max(0.0, cooldown_until - now_ts) for cooldown_until in self.cooled_down_keys.values())
            return None, next_delay

    def cooldown_key(self, key: str, ttl_seconds: int):
        with self.lock:
            now_ts = datetime.now(timezone.utc).timestamp()
            cooldown_until = now_ts + max(1, int(ttl_seconds))
            existing = self.cooled_down_keys.get(key)
            self.cooled_down_keys[key] = max(existing or 0.0, cooldown_until)
            if key in self.available_keys:
                self.available_keys.remove(key)


def _get_shared_key_pool(api_keys: List[str]) -> _SharedKeyPool:
    normalized = tuple(dict.fromkeys(key.strip() for key in api_keys if key.strip()))
    if not normalized:
        raise ValueError("No valid API keys provided")

    with _SHARED_KEY_POOLS_LOCK:
        pool = _SHARED_KEY_POOLS.get(normalized)
        if pool is None:
            pool = _SharedKeyPool(list(normalized))
            _SHARED_KEY_POOLS[normalized] = pool
        return pool


def collect_youtube_api_keys(*raw_groups: str) -> List[str]:
    keys: List[str] = []
    seen = set()

    for raw_group in raw_groups:
        for raw_key in str(raw_group or "").split(","):
            key = raw_key.strip()
            if key and key not in seen:
                seen.add(key)
                keys.append(key)

    for idx in range(1, 51):
        for prefix in ("YT_API_KEY_", "GOOGLE_API_KEY_", "YOUTUBE_API_KEY_"):
            env_value = os.getenv(f"{prefix}{idx}", "").strip()
            if env_value and env_value not in seen:
                seen.add(env_value)
                keys.append(env_value)

    return keys


class YouTubeOutlierParser:
    def __init__(self, api_keys: List[str], cooldown_time: int = 60):
        if not api_keys:
            raise ValueError("At least one API key is required")
        self.configured_api_keys = [key.strip() for key in api_keys if key.strip()]
        if not self.configured_api_keys:
            raise ValueError("No valid API keys provided")
        self.cooldown_time = cooldown_time
        self._key_pool = _get_shared_key_pool(self.configured_api_keys)
        self._redis_client = None
        self._redis_client_loaded = False
        self._channel_metadata_cache: Dict[str, Dict] = {}
        self._uploads_playlist_videos_cache: Dict[str, List[str]] = {}
        self._channel_baseline_cache: Dict[str, Dict[str, int]] = {}

    def _build_client(self, api_key: str):
        return googleapiclient.discovery.build(
            "youtube",
            "v3",
            developerKey=api_key,
            cache_discovery=False,
        )

    async def _get_available_key(self) -> str:
        max_wait_seconds = self._int_env("OUTLIER_SEARCH_MAX_KEY_WAIT_SECONDS", 90)
        while True:
            key, next_delay = self._key_pool.next_key()
            if key:
                distributed_delay = self._distributed_cooldown_delay(key)
                if distributed_delay > 0:
                    self._key_pool.cooldown_key(key, distributed_delay)
                    continue
                return key

            if next_delay is None or next_delay <= 0 or next_delay > max_wait_seconds:
                raise RuntimeError("No available API keys")

            wait_seconds = max(1, int(math.ceil(next_delay)))
            logger.warning(
                "[OutlierParser] All keys are cooling down; waiting %ss for the next available key",
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    @staticmethod
    def _seconds_until_next_daily_quota_reset() -> int:
        explicit = YouTubeOutlierParser._int_env("YOUTUBE_DAILY_QUOTA_COOLDOWN_SECONDS", 0)
        if explicit > 0:
            return explicit

        try:
            tz_name = os.getenv("YOUTUBE_QUOTA_RESET_TIMEZONE", "America/Los_Angeles")
            quota_tz = ZoneInfo(tz_name)
            now = datetime.now(quota_tz)
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            return max(3600, int((next_reset - now).total_seconds()))
        except Exception:
            return 12 * 60 * 60

    def _quota_cooldown_seconds(self, error: Optional[Exception] = None) -> int:
        if error and self._is_daily_quota_error(error):
            return self._seconds_until_next_daily_quota_reset()
        if error and self._is_rate_limit_error(error):
            return self._int_env("YOUTUBE_RATE_LIMIT_COOLDOWN_SECONDS", self.cooldown_time)
        if error and self._is_forbidden_key_error(error):
            return self._int_env("YOUTUBE_FORBIDDEN_KEY_COOLDOWN_SECONDS", 7 * 24 * 60 * 60)
        if error and self._is_invalid_key_error(error):
            return self._int_env("YOUTUBE_INVALID_KEY_COOLDOWN_SECONDS", 7 * 24 * 60 * 60)
        return self.cooldown_time

    async def _cooldown_key(self, key: str, cooldown_seconds: Optional[int] = None):
        ttl = max(1, int(cooldown_seconds or self.cooldown_time))
        self._key_pool.cooldown_key(key, ttl)
        self._set_distributed_cooldown(key, ttl)

    @staticmethod
    def _distributed_cooldown_key(key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return f"outlier_search:yt_key_cooldown:{digest}"

    def _get_redis_client(self):
        if self._redis_client_loaded:
            return self._redis_client

        self._redis_client_loaded = True
        redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL")
        if not redis_url:
            return None

        try:
            import redis

            self._redis_client = redis.from_url(redis_url, decode_responses=True, socket_keepalive=False)
        except Exception as error:
            logger.warning("[OutlierParser] Redis cooldown coordination unavailable: %s", error)
            self._redis_client = None
        return self._redis_client

    def _distributed_cooldown_delay(self, key: str) -> int:
        client = self._get_redis_client()
        if client is None:
            return 0

        try:
            ttl = int(client.ttl(self._distributed_cooldown_key(key)) or -2)
            return ttl if ttl > 0 else 0
        except Exception:
            return 0

    def _set_distributed_cooldown(self, key: str, ttl_seconds: int):
        client = self._get_redis_client()
        if client is None:
            return

        try:
            client.set(self._distributed_cooldown_key(key), "1", ex=max(1, int(ttl_seconds)))
        except Exception as error:
            logger.warning("[OutlierParser] Failed to publish distributed cooldown for key ...%s: %s", key[-4:], error)

    @staticmethod
    def _is_quota_error(error: Exception) -> bool:
        return YouTubeOutlierParser._is_daily_quota_error(error) or YouTubeOutlierParser._is_rate_limit_error(error)

    @staticmethod
    def _is_daily_quota_error(error: Exception) -> bool:
        error_str = str(error).lower()
        return any(marker in error_str for marker in ("quotaexceeded", "dailylimitexceeded"))

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        error_str = str(error).lower()
        return any(marker in error_str for marker in ("userratelimitexceeded", "ratelimitexceeded"))

    @staticmethod
    def _is_forbidden_key_error(error: Exception) -> bool:
        error_str = str(error).lower()
        forbidden_markers = [
            "reason \"forbidden\"",
            "'reason': 'forbidden'",
            "permission denied: consumer 'api_key:",
            "api key not valid",
            "accessnotconfigured",
            "iprefererblocked",
            "service disabled",
        ]
        return any(marker in error_str for marker in forbidden_markers)

    @staticmethod
    def _is_invalid_key_error(error: Exception) -> bool:
        error_str = str(error).lower()
        invalid_markers = [
            "api key not valid",
            "keyinvalid",
            "invalid api key",
            "request uses an api key that is invalid",
        ]
        return any(marker in error_str for marker in invalid_markers)

    @staticmethod
    def _status_code(error: Exception) -> Optional[int]:
        http_resp = getattr(error, "resp", None)
        if http_resp is not None:
            try:
                return int(getattr(http_resp, "status", None))
            except Exception:
                return None
        try:
            return int(getattr(error, "status_code", None))
        except Exception:
            return None

    def _is_retryable_http_error(self, error: Exception) -> bool:
        status_code = self._status_code(error)
        return status_code == 429 or (isinstance(status_code, int) and status_code >= 500)

    @staticmethod
    def _parse_int(value) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw)
            return value if value > 0 else default
        except Exception:
            return default

    @staticmethod
    def _float_env(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
            return value if value > 0 else default
        except Exception:
            return default

    @staticmethod
    def _bool_env(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    async def _safe_execute(self, request_factory, operation: str):
        max_attempts = max(len(self.configured_api_keys) * 3, 3)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            api_key = await self._get_available_key()
            try:
                youtube = self._build_client(api_key)
                return await asyncio.to_thread(lambda: request_factory(youtube).execute())
            except HttpError as error:
                last_error = error
                if self._is_quota_error(error) or self._is_forbidden_key_error(error) or self._is_invalid_key_error(error):
                    cooldown = self._quota_cooldown_seconds(error)
                    logger.warning(
                        "[OutlierParser] %s failed on key ...%s; cooling down for %ss (%s/%s)",
                        operation,
                        api_key[-4:],
                        cooldown,
                        attempt,
                        max_attempts,
                    )
                    await self._cooldown_key(api_key, cooldown_seconds=cooldown)
                    continue

                if self._is_retryable_http_error(error) and attempt < max_attempts:
                    wait_seconds = min(8, attempt)
                    logger.warning(
                        "[OutlierParser] %s transient HTTP error on key ...%s; retry in %ss (%s/%s)",
                        operation,
                        api_key[-4:],
                        wait_seconds,
                        attempt,
                        max_attempts,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue
                raise
            except Exception as error:
                last_error = error
                if attempt < max_attempts:
                    wait_seconds = min(4, attempt)
                    logger.warning(
                        "[OutlierParser] %s unexpected error; retry in %ss (%s/%s): %s",
                        operation,
                        wait_seconds,
                        attempt,
                        max_attempts,
                        error,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"YouTube API call failed during {operation}")

    @staticmethod
    def _parse_published_at(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _age_hours(published_at: datetime) -> float:
        now = datetime.now(timezone.utc)
        return max((now - published_at).total_seconds() / 3600.0, 1.0)

    @staticmethod
    def _parse_iso_duration_seconds(duration: str) -> int:
        if not duration:
            return 0
        pattern = re.compile(
            r"PT"
            r"(?:(?P<hours>\d+)H)?"
            r"(?:(?P<minutes>\d+)M)?"
            r"(?:(?P<seconds>\d+)S)?"
        )
        match = pattern.fullmatch(duration)
        if not match:
            return 0
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        seconds = int(match.group("seconds") or 0)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _normalize_content_type(content_type: str) -> str:
        normalized = (content_type or "all").strip().lower()
        if normalized in {"short", "shorts", "yt_shorts"}:
            return "shorts"
        if normalized in {"long", "video", "videos", "regular"}:
            return "long"
        return "all"

    @staticmethod
    def _detect_content_type(duration_seconds: int) -> str:
        return "shorts" if 0 < duration_seconds <= 65 else "long"

    @staticmethod
    def _normalize_topic_tokens(title: str) -> List[str]:
        cleaned = re.sub(r"[^\w\sа-яА-ЯёЁ]", " ", (title or "").lower(), flags=re.UNICODE)
        tokens = [token for token in cleaned.split() if len(token) >= 3]
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "you", "your", "how", "why",
            "что", "как", "для", "это", "или", "где", "когда", "видео", "shorts", "youtube",
        }
        return [token for token in tokens if token not in stopwords]

    def _keyword_tokens(self, keyword: str) -> List[str]:
        return self._normalize_topic_tokens(keyword)

    def _snippet_tokens(self, snippet: Dict) -> Dict[str, set]:
        title_tokens = set(self._normalize_topic_tokens(str(snippet.get("title") or "")))
        description_tokens = set(self._normalize_topic_tokens(str(snippet.get("description") or "")))
        tag_tokens = set()
        raw_tags = snippet.get("tags")
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                tag_tokens.update(self._normalize_topic_tokens(str(tag or "")))
        return {
            "title": title_tokens,
            "description": description_tokens,
            "tags": tag_tokens,
        }

    def _keyword_relevance(self, snippet: Dict, keyword_tokens: List[str]) -> Dict[str, float]:
        if not keyword_tokens:
            return {"matches": 0.0, "ratio": 0.0, "title_matches": 0.0, "title_ratio": 0.0}
        token_buckets = self._snippet_tokens(snippet)
        text_tokens = token_buckets["title"] | token_buckets["description"] | token_buckets["tags"]
        title_tokens = token_buckets["title"]
        unique_keyword_tokens = set(keyword_tokens)
        matches = len(unique_keyword_tokens & text_tokens)
        title_matches = len(unique_keyword_tokens & title_tokens)
        ratio = matches / max(1, len(unique_keyword_tokens))
        title_ratio = title_matches / max(1, len(unique_keyword_tokens))
        return {
            "matches": float(matches),
            "ratio": float(ratio),
            "title_matches": float(title_matches),
            "title_ratio": float(title_ratio),
        }

    def _topic_cluster_key(self, title: str, keyword: str) -> str:
        # Do not inject keyword tokens into topic cluster: it causes false relevance matches downstream.
        tokens = self._normalize_topic_tokens(title)
        if not tokens:
            tokens = self._normalize_topic_tokens(keyword)
        if not tokens:
            return "misc"
        return " ".join(tokens[:4])

    @staticmethod
    def _normalize_language_code(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = str(value).strip().lower()
        if not normalized:
            return ""
        return normalized.split("-")[0].split("_")[0]

    def _extract_video_language(self, snippet: Dict) -> str:
        audio_lang = self._normalize_language_code(snippet.get("defaultAudioLanguage"))
        if audio_lang:
            return audio_lang
        return self._normalize_language_code(snippet.get("defaultLanguage"))

    @staticmethod
    def _keyword_language_hint(keyword: str) -> str:
        text = (keyword or "").strip()
        if not text:
            return ""
        if re.search(r"[А-Яа-яЁё]", text):
            return "ru"
        if re.search(r"[\u0600-\u06FF]", text):
            return "ar"
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        if re.search(r"[A-Za-z]", text):
            return "en"
        return ""

    def _build_query_variants(self, keyword: str, content_type: str, language: str) -> List[str]:
        base = (keyword or "").strip()
        variants = [base]
        if not base:
            return variants

        if language == "ru":
            if content_type == "shorts":
                variants.extend([f"{base} shorts", f"{base} вирусные shorts"])
            elif content_type == "long":
                variants.extend([f"{base} длинное видео", f"{base} подробный разбор"])
            else:
                variants.extend([f"{base} shorts", f"{base} вирусное", f"{base} тренды"])
            return variants

        if content_type == "shorts":
            variants.extend([f"{base} shorts", f"{base} viral shorts"])
        elif content_type == "long":
            variants.extend([f"{base} full video", f"{base} deep dive"])
        else:
            variants.extend([f"{base} shorts", f"{base} viral", f"{base} trending"])
        return variants

    @staticmethod
    def _is_script_mismatch(title: str, requested_lang: str) -> bool:
        if not title or not requested_lang:
            return False

        arabic_chars = len(re.findall(r"[\u0600-\u06FF]", title))
        devanagari_chars = len(re.findall(r"[\u0900-\u097F]", title))
        latin_chars = len(re.findall(r"[A-Za-z]", title))
        cyrillic_chars = len(re.findall(r"[А-Яа-яЁё]", title))

        if requested_lang == "ru":
            return (arabic_chars + devanagari_chars) >= 4 and cyrillic_chars == 0
        if requested_lang in {"en", "de", "fr", "es", "it", "pt", "nl"}:
            return (arabic_chars + devanagari_chars) >= 4 and latin_chars == 0
        return False

    @staticmethod
    def _script_counts(text: str) -> Dict[str, int]:
        source = text or ""
        return {
            "arabic": len(re.findall(r"[\u0600-\u06FF]", source)),
            "devanagari": len(re.findall(r"[\u0900-\u097F]", source)),
            "latin": len(re.findall(r"[A-Za-z]", source)),
            "cyrillic": len(re.findall(r"[А-Яа-яЁё]", source)),
        }

    def _passes_language_gate(self, snippet: Dict, effective_lang: str) -> bool:
        min_confidence = self._float_env("OUTLIER_SEARCH_MIN_LANGUAGE_CONFIDENCE", 0.40)
        return self._language_confidence(snippet, effective_lang) >= min_confidence

    def _language_confidence(self, snippet: Dict, effective_lang: str) -> float:
        if not effective_lang:
            return 1.0

        title = str(snippet.get("title") or "")
        description = str(snippet.get("description") or "")
        text_counts = self._script_counts(f"{title} {description}")
        score = 1.0

        heavy_non_target = (text_counts["arabic"] + text_counts["devanagari"]) >= 5
        if effective_lang in {"ru", "en"} and heavy_non_target:
            score -= 0.7

        text_lower = f"{title} {description}".lower()
        if effective_lang == "en" and self._bool_env("OUTLIER_SEARCH_EN_FILTER_INDIC_HINTS", True):
            if re.search(r"\b(hindi|hinglish|tamil|telugu|malayalam|kannada|punjabi|bhojpuri|bangla|urdu)\b", text_lower):
                score -= 0.65

        video_lang = self._extract_video_language(snippet)
        if video_lang:
            if effective_lang == "ru" and video_lang != "ru":
                score -= 0.75
            if effective_lang == "en" and video_lang not in {"en", ""}:
                score -= 0.70

        if not video_lang:
            if effective_lang == "ru":
                if text_counts["cyrillic"] < 3:
                    score -= 0.55
                if text_counts["latin"] > text_counts["cyrillic"] * 1.5:
                    score -= 0.35
            elif effective_lang == "en":
                if text_counts["latin"] < 3:
                    score -= 0.55
                if text_counts["cyrillic"] >= 3:
                    score -= 0.40

        return self._clip(score, 0.0, 1.0)

    def _normalize_views_band(self, outliers: List[Dict], hard_min_views: int, target_limit: int) -> List[Dict]:
        if not outliers:
            return outliers

        min_keep = self._int_env("OUTLIER_SEARCH_VIEWS_BAND_MIN_KEEP", min(12, max(6, target_limit // 2)))
        min_ratio = self._float_env("OUTLIER_SEARCH_VIEWS_BAND_MIN_RATIO", 0.20)
        max_ratio = self._float_env("OUTLIER_SEARCH_VIEWS_BAND_MAX_RATIO", 120.0)

        views_values = [int(item.get("views") or 0) for item in outliers if int(item.get("views") or 0) > 0]
        if len(views_values) < 4:
            return outliers

        median_views = int(median(views_values))
        floor = max(hard_min_views, int(median_views * min_ratio))
        ceiling = max(floor + 1, int(median_views * max_ratio))

        filtered = [item for item in outliers if floor <= int(item.get("views") or 0) <= ceiling]
        if len(filtered) >= min_keep:
            return filtered
        return outliers

    def _prefer_popular_results(self, outliers: List[Dict], target_limit: int, search_profile: str) -> List[Dict]:
        if not outliers or search_profile != "overview":
            return outliers

        final_min_views = self._int_env("OUTLIER_SEARCH_OVERVIEW_FINAL_MIN_VIEWS", 30_000)
        popular = [item for item in outliers if int(item.get("views") or 0) >= final_min_views]
        if not popular:
            return outliers
        # Always place high-view videos first so that downstream stage limits
        # (target_limit slicing) preserve the strongest candidates.
        rest = [item for item in outliers if int(item.get("views") or 0) < final_min_views]
        return popular + rest

    def _quality_signals(
        self,
        views: int,
        velocity_per_hour: float,
        relative_multiplier: float,
        outlier_score: float,
        min_views: int,
        min_velocity: int,
        min_multiplier: float,
        min_outlier: float,
    ) -> int:
        signals = 0
        if views >= min_views:
            signals += 1
        if velocity_per_hour >= float(min_velocity):
            signals += 1
        if relative_multiplier >= float(min_multiplier):
            signals += 1
        if outlier_score >= float(min_outlier):
            signals += 1
        return signals

    def _composite_trend_score(
        self,
        views: int,
        velocity_per_hour: float,
        relative_multiplier: float,
        outlier_score: float,
        quality_score: float,
        confidence_score: float,
        relevance_ratio: float,
        language_confidence: float,
    ) -> float:
        return float(
            outlier_score * 0.29
            + math.log1p(max(views, 0.0)) * 0.14
            + math.log1p(max(velocity_per_hour, 0.0)) * 0.19
            + math.log1p(max(relative_multiplier, 0.0)) * 0.15
            + float(quality_score) * 0.08
            + float(confidence_score) * 0.06
            + float(relevance_ratio) * 0.06
            + float(language_confidence) * 0.03
        )

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return max(low, min(value, high))

    def _quality_score(
        self,
        views: int,
        likes: int,
        comments: int,
        subscribers: int,
        age_hours: float,
    ) -> float:
        engagement_rate = (likes + comments + 1.0) / (views + 20.0)
        engagement_component = self._clip(engagement_rate * 12.0, 0.0, 1.0)

        comment_density = (comments + 1.0) / (views + 100.0)
        discussion_component = self._clip(comment_density * 45.0, 0.0, 1.0)

        channel_fit = (views + 1.0) / (subscribers + 200.0)
        channel_fit_component = self._clip(channel_fit * 2.0, 0.0, 1.0)

        age_component = self._clip(1.0 - (age_hours / 240.0), 0.2, 1.0)
        quality = (
            engagement_component * 0.35
            + discussion_component * 0.25
            + channel_fit_component * 0.20
            + age_component * 0.20
        )
        return round(self._clip(quality, 0.0, 1.0), 4)

    def _confidence_score(
        self,
        views: int,
        baseline_views: int,
        age_hours: float,
        subscribers: int,
    ) -> float:
        signal_strength = self._clip(math.log10(max(views, 1) + 1) / 6.0, 0.0, 1.0)
        baseline_strength = self._clip(math.log10(max(baseline_views, 1) + 1) / 6.0, 0.0, 1.0)
        freshness = self._clip(1.0 - (age_hours / 336.0), 0.1, 1.0)
        channel_scale = self._clip(math.log10(max(subscribers, 10) + 1) / 7.0, 0.0, 1.0)
        confidence = signal_strength * 0.35 + baseline_strength * 0.20 + freshness * 0.25 + channel_scale * 0.20
        return round(self._clip(confidence, 0.0, 1.0), 4)

    def _compute_score(
        self,
        views: int,
        likes: int,
        comments: int,
        subscribers: int,
        baseline_views: int,
        age_hours: float,
    ) -> Dict:
        relative_multiplier = (views + 1.0) / (baseline_views + 1.0)
        velocity_per_hour = views / max(age_hours, 1.0)
        baseline_velocity = max(baseline_views / 48.0, 1.0)
        velocity_ratio = velocity_per_hour / baseline_velocity

        engagement_rate = (likes + comments + 1.0) / (views + 20.0)
        engagement_component = min(engagement_rate * 100.0, 4.0)

        scale_penalty = 1.0 / (1.0 + math.log10(max(subscribers, 1000) / 1000.0 + 1.0) * 0.15)

        # Absolute-scale weight: prevents micro-channel videos (e.g. 1k views / 1k subs)
        # from outscoring genuinely popular videos by having a high relative_multiplier.
        # Transitions: 0.50 at ≤1k views → 0.67 at 10k → 0.83 at 100k → 1.00 at ≥1M.
        abs_weight = 0.5 + 0.5 * self._clip((math.log10(max(views, 1)) - 3.0) / 3.0, 0.0, 1.0)

        score = (relative_multiplier * 0.55 + velocity_ratio * 0.35 + engagement_component * 0.10) * scale_penalty * abs_weight

        return {
            "outlier_score": round(score, 4),
            "relative_multiplier": round(relative_multiplier, 3),
            "velocity_per_hour": round(velocity_per_hour, 2),
            "engagement_rate": round(engagement_rate, 4),
        }

    def _build_reason(self, relative_multiplier: float, velocity_per_hour: float, baseline_views: int) -> str:
        return (
            f"{relative_multiplier:.2f}x выше базовой нормы канала; "
            f"скорость {velocity_per_hour:.0f} просмотров/час; "
            f"база {baseline_views} просмотров"
        )

    def _parallel_request_concurrency(self, env_name: str, default: int, total_items: int) -> int:
        if total_items <= 0:
            return 0
        safe_default = min(default, max(1, len(self.configured_api_keys)))
        configured = self._int_env(env_name, safe_default)
        return max(1, min(total_items, configured))

    async def _videos_list(self, ids: List[str], part: str) -> List[Dict]:
        chunks = [ids[idx:idx + 50] for idx in range(0, len(ids), 50)]
        if not chunks:
            return []

        concurrency = self._parallel_request_concurrency(
            "OUTLIER_SEARCH_VIDEOS_LIST_CONCURRENCY",
            4,
            len(chunks),
        )
        semaphore = asyncio.Semaphore(concurrency)
        chunk_results: List[List[Dict]] = [[] for _ in chunks]

        async def fetch_chunk(chunk_index: int, chunk: List[str]):
            async with semaphore:
                response = await self._safe_execute(
                    lambda yt, chunk=chunk, part=part: yt.videos().list(id=",".join(chunk), part=part, maxResults=50),
                    operation="videos.list",
                )
            chunk_results[chunk_index] = response.get("items", [])

        await asyncio.gather(*(fetch_chunk(idx, chunk) for idx, chunk in enumerate(chunks)))

        items: List[Dict] = []
        for chunk_items in chunk_results:
            items.extend(chunk_items)
        return items

    async def _channels_list(self, channel_ids: List[str]) -> Dict[str, Dict]:
        channels_map: Dict[str, Dict] = {}
        missing_ids: List[str] = []

        for channel_id in channel_ids:
            if not channel_id:
                continue
            cached = self._channel_metadata_cache.get(channel_id)
            if cached is not None:
                channels_map[channel_id] = cached
            else:
                missing_ids.append(channel_id)

        chunks = [missing_ids[idx:idx + 50] for idx in range(0, len(missing_ids), 50)]
        if chunks:
            concurrency = self._parallel_request_concurrency(
                "OUTLIER_SEARCH_CHANNELS_LIST_CONCURRENCY",
                4,
                len(chunks),
            )
            semaphore = asyncio.Semaphore(concurrency)

            async def fetch_chunk(channel_chunk: List[str]):
                async with semaphore:
                    try:
                        response = await self._safe_execute(
                            lambda yt, channel_chunk=channel_chunk: yt.channels().list(
                                id=",".join(channel_chunk),
                                part="statistics,contentDetails",
                                maxResults=50,
                            ),
                            operation="channels.list",
                        )
                    except Exception as error:
                        logger.warning("[OutlierParser] channels.list unavailable for %d channels, using empty metadata: %s", len(channel_chunk), error)
                        response = {"items": []}

                fetched_ids = set()
                for item in response.get("items", []):
                    channel_id = item.get("id")
                    if not channel_id:
                        continue
                    self._channel_metadata_cache[channel_id] = item
                    channels_map[channel_id] = item
                    fetched_ids.add(channel_id)

                for channel_id in channel_chunk:
                    if channel_id not in fetched_ids:
                        self._channel_metadata_cache[channel_id] = {}
                        channels_map[channel_id] = {}

            await asyncio.gather(*(fetch_chunk(channel_chunk) for channel_chunk in chunks))

        return channels_map

    async def _search_videos_ids(
        self,
        keyword: str,
        order: str,
        region_code: str,
        language: str,
        published_after: Optional[str],
        target_count: int,
    ) -> List[str]:
        collected: List[str] = []
        seen = set()
        page_token = None
        pages = 0
        configured_page_cap = self._int_env("OUTLIER_SEARCH_MAX_SEARCH_PAGES", 4)
        configured_page_cap = max(1, min(configured_page_cap, 8))
        expected_pages = max(1, math.ceil(max(1, target_count) / 50))
        page_budget = min(configured_page_cap, expected_pages + 1)

        while len(collected) < target_count and pages < page_budget:
            pages += 1
            search_kwargs = {
                "q": keyword,
                "part": "snippet",
                "type": "video",
                "maxResults": min(50, max(1, target_count - len(collected))),
                "order": order,
                "regionCode": (region_code or "US")[:2].upper(),
                "relevanceLanguage": (language or "ru")[:2].lower(),
                "safeSearch": "none",
                "pageToken": page_token,
            }
            if published_after:
                search_kwargs["publishedAfter"] = published_after

            response = await self._safe_execute(
                lambda yt, search_kwargs=search_kwargs: yt.search().list(**search_kwargs),
                operation=f"search.list:{order}",
            )

            for item in response.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid and vid not in seen:
                    seen.add(vid)
                    collected.append(vid)
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return collected

    async def _channel_recent_video_ids(self, uploads_playlist_id: str, max_items: int = 20) -> List[str]:
        collected = []
        page_token = None
        while len(collected) < max_items:
            response = await self._safe_execute(
                lambda yt, uploads_playlist_id=uploads_playlist_id, max_items=max_items, collected=collected, page_token=page_token: yt.playlistItems().list(
                    playlistId=uploads_playlist_id,
                    part="contentDetails",
                    maxResults=min(50, max_items - len(collected)),
                    pageToken=page_token,
                ),
                operation="playlistItems.list",
            )
            for item in response.get("items", []):
                vid = item.get("contentDetails", {}).get("videoId")
                if vid:
                    collected.append(vid)
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return collected

    async def _get_channel_baseline_bundle(
        self,
        channel_id: str,
        uploads_playlist_id: str,
        max_items: int = 20,
    ) -> Dict[str, int]:
        cached = self._channel_baseline_cache.get(channel_id)
        if cached is not None:
            return dict(cached)

        bundle = {
            "all": 10_000,
            "shorts": 8_000,
            "long": 15_000,
        }

        if not uploads_playlist_id:
            self._channel_baseline_cache[channel_id] = dict(bundle)
            return dict(bundle)

        try:
            recent_video_ids = self._uploads_playlist_videos_cache.get(uploads_playlist_id)
            if recent_video_ids is None:
                recent_video_ids = await self._channel_recent_video_ids(uploads_playlist_id, max_items=max_items)
                self._uploads_playlist_videos_cache[uploads_playlist_id] = list(recent_video_ids)

            if recent_video_ids:
                recent_videos = await self._videos_list(recent_video_ids, "statistics,contentDetails")
                recent_views = [self._parse_int(rv.get("statistics", {}).get("viewCount")) for rv in recent_videos]
                recent_views = [value for value in recent_views if value > 0]
                if recent_views:
                    bundle["all"] = int(median(recent_views))

                recent_short_views = []
                recent_long_views = []
                for rv in recent_videos:
                    view_count = self._parse_int(rv.get("statistics", {}).get("viewCount"))
                    duration_seconds = self._parse_iso_duration_seconds(
                        rv.get("contentDetails", {}).get("duration", "")
                    )
                    detected_type = self._detect_content_type(duration_seconds)
                    if view_count <= 0:
                        continue
                    if detected_type == "shorts":
                        recent_short_views.append(view_count)
                    else:
                        recent_long_views.append(view_count)

                if recent_short_views:
                    bundle["shorts"] = int(median(recent_short_views))
                if recent_long_views:
                    bundle["long"] = int(median(recent_long_views))
        except Exception as error:
            logger.warning("[OutlierParser] Baseline fallback for channel %s: %s", channel_id, error)

        self._channel_baseline_cache[channel_id] = dict(bundle)
        return dict(bundle)

    async def _hydrate_channel_baselines(
        self,
        channel_ids: List[str],
        channels_map: Dict[str, Dict],
        max_channel_baselines: int,
        max_items: int,
    ) -> Dict[str, Dict[str, int]]:
        selected_channel_ids = [channel_id for channel_id in channel_ids[:max_channel_baselines] if channel_id]
        if not selected_channel_ids:
            return {}

        concurrency = self._parallel_request_concurrency(
            "OUTLIER_SEARCH_BASELINE_CONCURRENCY",
            4,
            len(selected_channel_ids),
        )
        logger.info(
            "[OutlierParser] Loading baseline bundles for %d channels (sample=%d, concurrency=%d)",
            len(selected_channel_ids),
            max_items,
            concurrency,
        )

        semaphore = asyncio.Semaphore(concurrency)
        progress_lock = asyncio.Lock()
        bundles: Dict[str, Dict[str, int]] = {}
        completed = 0
        report_every = 1 if len(selected_channel_ids) <= 5 else 5

        async def load_bundle(channel_id: str):
            nonlocal completed
            channel = channels_map.get(channel_id) or {}
            uploads_playlist_id = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

            async with semaphore:
                bundle = await self._get_channel_baseline_bundle(
                    channel_id=channel_id,
                    uploads_playlist_id=uploads_playlist_id,
                    max_items=max_items,
                )

            bundles[channel_id] = bundle

            async with progress_lock:
                completed += 1
                if completed == len(selected_channel_ids) or completed % report_every == 0:
                    logger.info("[OutlierParser] Baseline bundles progress: %d/%d channels", completed, len(selected_channel_ids))

        await asyncio.gather(*(load_bundle(channel_id) for channel_id in selected_channel_ids))
        return bundles

    def _candidate_baseline_bundles(self, videos: List[Dict]) -> Dict[str, Dict[str, int]]:
        channel_views_all: Dict[str, List[int]] = defaultdict(list)
        channel_views_shorts: Dict[str, List[int]] = defaultdict(list)
        channel_views_long: Dict[str, List[int]] = defaultdict(list)

        for video in videos:
            snippet = video.get("snippet", {})
            stats = video.get("statistics", {})
            content_details = video.get("contentDetails", {})
            channel_id = str(snippet.get("channelId") or "")
            if not channel_id:
                continue

            view_count = self._parse_int(stats.get("viewCount"))
            if view_count <= 0:
                continue

            duration_seconds = self._parse_iso_duration_seconds(content_details.get("duration", ""))
            detected_type = self._detect_content_type(duration_seconds)

            channel_views_all[channel_id].append(view_count)
            if detected_type == "shorts":
                channel_views_shorts[channel_id].append(view_count)
            else:
                channel_views_long[channel_id].append(view_count)

        bundles: Dict[str, Dict[str, int]] = {}
        for channel_id, all_views in channel_views_all.items():
            bundle = {
                "all": int(median(all_views)) if all_views else 10_000,
                "shorts": int(median(channel_views_shorts[channel_id])) if channel_views_shorts[channel_id] else 8_000,
                "long": int(median(channel_views_long[channel_id])) if channel_views_long[channel_id] else 15_000,
            }
            if not channel_views_shorts[channel_id]:
                bundle["shorts"] = max(8_000, int(bundle["all"] * 0.8))
            if not channel_views_long[channel_id]:
                bundle["long"] = max(15_000, int(bundle["all"] * 1.2))
            bundles[channel_id] = bundle

        return bundles

    async def search_outliers(
        self,
        keyword: str,
        language: str = "ru",
        region_code: str = "US",
        lookback_hours: int = 72,
        max_results: int = 25,
        content_type: str = "all",
        candidate_pool: int = 600,
        search_profile: str = "default",
    ) -> List[Dict]:
        try:
            profile = str(search_profile or "default").strip().lower()

            min_lookback_hours = self._int_env("OUTLIER_SEARCH_MIN_LOOKBACK_HOURS", 6)
            max_lookback_hours = self._int_env("OUTLIER_SEARCH_MAX_LOOKBACK_HOURS", 720)
            lookback_normalized = max(min_lookback_hours, int(lookback_hours or min_lookback_hours))
            if max_lookback_hours > 0:
                lookback_normalized = min(lookback_normalized, max_lookback_hours)

            published_after = (
                datetime.now(timezone.utc) - timedelta(hours=lookback_normalized)
            ).isoformat().replace("+00:00", "Z")
            content_type_normalized = self._normalize_content_type(content_type)
            requested_lang = self._normalize_language_code(language)
            keyword_lang = self._keyword_language_hint(keyword)
            effective_lang = keyword_lang or requested_lang or "ru"
            min_pool = self._int_env("OUTLIER_SEARCH_MIN_CANDIDATE_POOL", 300)
            max_pool = self._int_env("OUTLIER_SEARCH_MAX_CANDIDATE_POOL", 2000)
            requested_pool = int(candidate_pool or min_pool)
            target_pool = max(min_pool, min(requested_pool, max_pool))
            max_results_cap = self._int_env("OUTLIER_SEARCH_MAX_RESULTS_CAP", 120)
            target_limit = max(5, min(int(max_results or 25), max_results_cap))
            min_return_target = max(5, min(target_limit, self._int_env("OUTLIER_SEARCH_MIN_RETURN_RESULTS", 20)))
            hard_min_views = self._int_env("OUTLIER_SEARCH_HARD_MIN_VIEWS", 8_000)
            min_views = self._int_env("OUTLIER_SEARCH_MIN_VIEWS", 25_000)
            min_velocity = self._int_env("OUTLIER_SEARCH_MIN_VELOCITY_PER_HOUR", 120)
            min_multiplier = self._float_env("OUTLIER_SEARCH_MIN_RELATIVE_MULTIPLIER", 2.5)
            min_outlier = self._float_env("OUTLIER_SEARCH_MIN_OUTLIER_SCORE", 1.8)
            min_signal_count = self._int_env("OUTLIER_SEARCH_MIN_SIGNAL_COUNT", 2)
            relaxed_factor = self._float_env("OUTLIER_SEARCH_RELAXED_FACTOR", 0.80)
            relaxed_min_views = int(max(hard_min_views, min_views * relaxed_factor))
            relaxed_min_velocity = int(max(1, min_velocity * relaxed_factor))
            relaxed_min_multiplier = float(max(1.0, min_multiplier * relaxed_factor))
            relaxed_min_outlier = float(max(0.8, min_outlier * relaxed_factor))
            relaxed_min_signals = max(1, min(min_signal_count, self._int_env("OUTLIER_SEARCH_RELAXED_MIN_SIGNAL_COUNT", 2)))
            strict_min_keep = self._int_env("OUTLIER_SEARCH_STRICT_MIN_KEEP", max(12, target_limit // 2 + 2))
            min_relevance_matches = self._int_env("OUTLIER_SEARCH_MIN_RELEVANCE_MATCHES", 1)
            keyword_tokens = self._keyword_tokens(keyword)
            required_relevance_matches = max(1, min(min_relevance_matches, len(keyword_tokens))) if keyword_tokens else 0
            min_relevance_ratio = self._float_env("OUTLIER_SEARCH_MIN_RELEVANCE_RATIO", 0.25)
            min_title_relevance_matches = self._int_env("OUTLIER_SEARCH_MIN_TITLE_RELEVANCE_MATCHES", 1)
            required_title_relevance_matches = (
                max(1, min(min_title_relevance_matches, len(keyword_tokens))) if keyword_tokens else 0
            )

            if profile == "overview":
                target_pool = max(target_pool, self._int_env("OUTLIER_SEARCH_OVERVIEW_MIN_CANDIDATE_POOL", 320))
                hard_min_views = max(hard_min_views, self._int_env("OUTLIER_SEARCH_OVERVIEW_HARD_MIN_VIEWS", 10_000))
                min_views = max(min_views, self._int_env("OUTLIER_SEARCH_OVERVIEW_MIN_VIEWS", 40_000))
                min_velocity = max(min_velocity, self._int_env("OUTLIER_SEARCH_OVERVIEW_MIN_VELOCITY_PER_HOUR", 120))
                min_signal_count = max(min_signal_count, self._int_env("OUTLIER_SEARCH_OVERVIEW_MIN_SIGNAL_COUNT", 2))
                strict_min_keep = max(strict_min_keep, self._int_env("OUTLIER_SEARCH_OVERVIEW_STRICT_MIN_KEEP", max(14, target_limit // 2 + 4)))

            if keyword_lang and requested_lang and keyword_lang != requested_lang:
                logger.info("[OutlierParser] Keyword language override applied: request=%s keyword=%s", requested_lang, keyword_lang)

            query_variants = self._build_query_variants(keyword, content_type_normalized, effective_lang)
            logger.info(
                "[OutlierParser] Searching for '%s' (lang=%s) with %d query variants: %s",
                keyword, effective_lang, len(query_variants), query_variants[:2] if len(query_variants) > 1 else query_variants
            )

            candidate_ids = []
            candidate_seen = set()
            if profile == "overview":
                strategy_weights = [
                    ("viewCount", int(target_pool * 0.55)),
                    ("relevance", int(target_pool * 0.30)),
                    ("date", int(target_pool * 0.15)),
                ]
            else:
                strategy_weights = [
                    ("viewCount", int(target_pool * 0.50)),
                    ("relevance", int(target_pool * 0.30)),
                    ("date", int(target_pool * 0.20)),
                ]
            per_variant_target = max(25, int(target_pool / max(len(query_variants), 1)))
            logger.info(
                "[OutlierParser] Candidate pool settings: target=%d, per_variant_target=%d, strategies=%s",
                target_pool, per_variant_target, len(strategy_weights)
            )
            for variant in query_variants:
                for order, strategy_target in strategy_weights:
                    try:
                        ids = await self._search_videos_ids(
                            keyword=variant,
                            order=order,
                            region_code=region_code,
                            language=effective_lang,
                            published_after=published_after,
                            target_count=max(int(strategy_target * 0.6), per_variant_target),
                        )
                    except RuntimeError as strategy_error:
                        if "No available API keys" in str(strategy_error):
                            raise RuntimeError("YouTube API quota exceeded for all configured keys")
                        logger.warning("[OutlierParser] Search strategy %s failed for query '%s': %s", order, variant, strategy_error)
                        break

                    for vid in ids:
                        if vid not in candidate_seen:
                            candidate_seen.add(vid)
                            candidate_ids.append(vid)
                        if len(candidate_ids) >= target_pool:
                            break
                    if len(candidate_ids) >= target_pool:
                        break
                if len(candidate_ids) >= target_pool:
                    break

            logger.info("[OutlierParser] Collected %d candidate IDs after strict search", len(candidate_ids))
            
            if not candidate_ids:
                logger.info("[OutlierParser] No candidates in strict window, retrying relaxed search")
                relaxed_pool = max(40, int(target_pool * 0.4))
                relaxed_orders = ["viewCount", "relevance"] if profile == "overview" else ["relevance"]
                for variant in query_variants:
                    ids = []
                    for relaxed_order in relaxed_orders:
                        try:
                            ids = await self._search_videos_ids(
                                keyword=variant,
                                order=relaxed_order,
                                region_code=region_code,
                                language=effective_lang,
                                published_after=None,
                                target_count=relaxed_pool,
                            )
                        except RuntimeError as relaxed_error:
                            if "No available API keys" in str(relaxed_error):
                                raise RuntimeError("YouTube API quota exceeded for all configured keys")
                            logger.warning("[OutlierParser] Relaxed search failed for '%s': %s", variant, relaxed_error)
                            break
                        if ids:
                            break

                    for vid in ids:
                        if vid not in candidate_seen:
                            candidate_seen.add(vid)
                            candidate_ids.append(vid)
                        if len(candidate_ids) >= relaxed_pool:
                            break

                logger.info("[OutlierParser] Collected %d candidate IDs after relaxed search", len(candidate_ids))
                if not candidate_ids:
                    return []

            logger.info("[OutlierParser] Fetching full metadata for %d candidate videos", len(candidate_ids))
            videos = await self._videos_list(candidate_ids, "snippet,statistics,contentDetails")
            logger.info("[OutlierParser] Retrieved full info for %d videos", len(videos))
            if not videos:
                return []

            channel_candidate_score: Dict[str, int] = defaultdict(int)
            for video in videos:
                channel_id = str(video.get("snippet", {}).get("channelId") or "")
                if not channel_id:
                    continue
                channel_candidate_score[channel_id] = max(
                    channel_candidate_score[channel_id],
                    self._parse_int(video.get("statistics", {}).get("viewCount")),
                )

            channel_ids = sorted(
                channel_candidate_score.keys(),
                key=lambda channel_id: channel_candidate_score[channel_id],
                reverse=True,
            )

            logger.info("[OutlierParser] Fetching metadata for %d candidate channels", len(channel_ids))
            channels_map = await self._channels_list(channel_ids) if channel_ids else {}
            candidate_baselines = self._candidate_baseline_bundles(videos)

            channel_baseline_views: Dict[str, int] = defaultdict(lambda: 10_000)
            channel_baseline_views_shorts: Dict[str, int] = defaultdict(lambda: 8_000)
            channel_baseline_views_long: Dict[str, int] = defaultdict(lambda: 15_000)

            for channel_id, bundle in candidate_baselines.items():
                channel_baseline_views[channel_id] = int(bundle.get("all") or 10_000)
                channel_baseline_views_shorts[channel_id] = int(bundle.get("shorts") or 8_000)
                channel_baseline_views_long[channel_id] = int(bundle.get("long") or 15_000)

            max_channel_baselines = self._int_env("OUTLIER_SEARCH_MAX_CHANNEL_BASELINES", 18)
            baseline_sample_size = max(6, self._int_env("OUTLIER_SEARCH_CHANNEL_BASELINE_SAMPLE_SIZE", 10))
            if profile == "overview":
                max_channel_baselines = self._int_env(
                    "OUTLIER_SEARCH_OVERVIEW_MAX_CHANNEL_BASELINES",
                    min(36, max_channel_baselines),
                )
                baseline_sample_size = max(
                    6,
                    self._int_env(
                        "OUTLIER_SEARCH_OVERVIEW_CHANNEL_BASELINE_SAMPLE_SIZE",
                        min(12, baseline_sample_size),
                    ),
                )

            hydrated_baselines = await self._hydrate_channel_baselines(
                channel_ids=channel_ids,
                channels_map=channels_map,
                max_channel_baselines=max_channel_baselines,
                max_items=baseline_sample_size,
            )
            logger.info("[OutlierParser] Prepared baseline bundles for %d channels", len(hydrated_baselines))

            for channel_id, baseline_bundle in hydrated_baselines.items():
                channel_baseline_views[channel_id] = int(baseline_bundle.get("all") or 10_000)
                channel_baseline_views_shorts[channel_id] = int(baseline_bundle.get("shorts") or 8_000)
                channel_baseline_views_long[channel_id] = int(baseline_bundle.get("long") or 15_000)

            outliers_strict = []
            outliers_relaxed = []
            per_channel_counter: Dict[str, int] = defaultdict(int)
            per_topic_counter: Dict[str, int] = defaultdict(int)
            filter_stats = defaultdict(int)
            
            # Log first few videos for debugging
            for idx, video in enumerate(videos[:3]):
                try:
                    snippet = video.get("snippet", {})
                    stats = video.get("statistics", {})
                    views = self._parse_int(stats.get("viewCount", 0))
                    logger.info(
                        "[OutlierParser] Sample video [%d]: title='%s...', views=%d, lang=%s",
                        idx, snippet.get("title", "")[:40], views,
                        snippet.get("defaultLanguage", "unknown")
                    )
                except Exception as e:
                    logger.warning("[OutlierParser] Error logging sample video: %s", e)
            
            for video in videos:
                snippet = video.get("snippet", {})
                stats = video.get("statistics", {})
                content_details = video.get("contentDetails", {})
                channel_id = snippet.get("channelId")
                if not channel_id:
                    continue

                channel_cap = 2 if profile == "overview" else 4
                if per_channel_counter[channel_id] >= channel_cap:
                    filter_stats["channel_cap_exceeded"] += 1
                    continue

                views = self._parse_int(stats.get("viewCount"))
                if views < hard_min_views:
                    filter_stats["hard_min_views"] += 1
                    continue
                likes = self._parse_int(stats.get("likeCount"))
                comments = self._parse_int(stats.get("commentCount"))
                duration_seconds = self._parse_iso_duration_seconds(content_details.get("duration", ""))
                detected_type = self._detect_content_type(duration_seconds)

                if content_type_normalized == "shorts" and detected_type != "shorts":
                    filter_stats["content_type_shorts"] += 1
                    continue
                if content_type_normalized == "long" and detected_type != "long":
                    filter_stats["content_type_long"] += 1
                    continue

                language_confidence = self._language_confidence(snippet, effective_lang)
                if language_confidence < self._float_env("OUTLIER_SEARCH_MIN_LANGUAGE_CONFIDENCE", 0.40):
                    filter_stats["language_confidence"] += 1
                    continue

                relevance_ratio = 0.0
                if keyword_tokens:
                    relevance = self._keyword_relevance(snippet, keyword_tokens)
                    if (
                        (relevance["matches"] < required_relevance_matches)
                        or (relevance["ratio"] < min_relevance_ratio)
                        or (relevance["title_matches"] < required_title_relevance_matches)
                    ):
                        filter_stats["keyword_relevance"] += 1
                        continue
                    relevance_ratio = float(relevance["ratio"])

                published_at_raw = snippet.get("publishedAt")
                if not published_at_raw:
                    continue

                published_at = self._parse_published_at(published_at_raw)
                age_hours = self._age_hours(published_at)
                if detected_type == "shorts":
                    baseline_views = max(channel_baseline_views_shorts[channel_id], 40)
                else:
                    baseline_views = max(channel_baseline_views_long[channel_id], 60)

                # Fallback to global per-channel baseline when type bucket is sparse
                baseline_views = max(baseline_views, int(channel_baseline_views[channel_id] * (0.55 if detected_type == "shorts" else 0.75)))

                channel_stats = channels_map.get(channel_id, {}).get("statistics", {})
                subscribers = self._parse_int(channel_stats.get("subscriberCount"))

                score_data = self._compute_score(
                    views=views,
                    likes=likes,
                    comments=comments,
                    subscribers=subscribers,
                    baseline_views=baseline_views,
                    age_hours=age_hours,
                )
                quality_score = self._quality_score(
                    views=views,
                    likes=likes,
                    comments=comments,
                    subscribers=subscribers,
                    age_hours=age_hours,
                )
                confidence_score = self._confidence_score(
                    views=views,
                    baseline_views=baseline_views,
                    age_hours=age_hours,
                    subscribers=subscribers,
                )
                topic_cluster = self._topic_cluster_key(snippet.get("title", ""), keyword)
                if per_topic_counter[topic_cluster] >= 4:
                    continue

                final_outlier_score = score_data["outlier_score"] * (0.78 + quality_score * 0.22) * (0.84 + confidence_score * 0.16)
                signal_count = self._quality_signals(
                    views=views,
                    velocity_per_hour=float(score_data["velocity_per_hour"]),
                    relative_multiplier=float(score_data["relative_multiplier"]),
                    outlier_score=float(final_outlier_score),
                    min_views=min_views,
                    min_velocity=min_velocity,
                    min_multiplier=min_multiplier,
                    min_outlier=min_outlier,
                )
                relaxed_signal_count = self._quality_signals(
                    views=views,
                    velocity_per_hour=float(score_data["velocity_per_hour"]),
                    relative_multiplier=float(score_data["relative_multiplier"]),
                    outlier_score=float(final_outlier_score),
                    min_views=relaxed_min_views,
                    min_velocity=relaxed_min_velocity,
                    min_multiplier=relaxed_min_multiplier,
                    min_outlier=relaxed_min_outlier,
                )

                item = {
                    "video_id": video.get("id"),
                    "title": snippet.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={video.get('id')}",
                    "channel_id": channel_id,
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": published_at_raw,
                    "thumbnail": (snippet.get("thumbnails", {}).get("high", {}) or snippet.get("thumbnails", {}).get("default", {})).get("url"),
                    "duration_seconds": duration_seconds,
                    "content_type": detected_type,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "subscribers": subscribers,
                    "baseline_views": baseline_views,
                    "outlier_score": round(final_outlier_score, 4),
                    "quality_score": quality_score,
                    "confidence_score": confidence_score,
                    "engagement_rate": score_data["engagement_rate"],
                    "topic_cluster": topic_cluster,
                    "relative_multiplier": score_data["relative_multiplier"],
                    "velocity_per_hour": score_data["velocity_per_hour"],
                    "reason": self._build_reason(
                        score_data["relative_multiplier"],
                        score_data["velocity_per_hour"],
                        baseline_views,
                    ),
                    "__trend_value": self._composite_trend_score(
                        views=views,
                        velocity_per_hour=float(score_data["velocity_per_hour"]),
                        relative_multiplier=float(score_data["relative_multiplier"]),
                        outlier_score=float(final_outlier_score),
                        quality_score=float(quality_score),
                        confidence_score=float(confidence_score),
                        relevance_ratio=float(relevance_ratio),
                        language_confidence=float(language_confidence),
                    ),
                }

                if signal_count >= min_signal_count:
                    outliers_strict.append(dict(item))
                if relaxed_signal_count >= relaxed_min_signals:
                    outliers_relaxed.append(dict(item))

                per_channel_counter[channel_id] += 1
                per_topic_counter[topic_cluster] += 1

            outliers = outliers_strict if len(outliers_strict) >= strict_min_keep else outliers_relaxed
            outliers.sort(key=lambda item: (float(item.get("__trend_value") or 0.0), float(item.get("outlier_score") or 0.0)), reverse=True)
            logger.info(
                "[OutlierParser] Filter stats: %s. Found %d strict outliers, %d relaxed outliers. Using %s set.",
                dict(filter_stats), len(outliers_strict), len(outliers_relaxed),
                "strict" if len(outliers_strict) >= strict_min_keep else "relaxed"
            )
            if len(outliers) < min_return_target and outliers_relaxed:
                seen_ids = {str(item.get("video_id") or "") for item in outliers}
                relaxed_sorted = sorted(
                    outliers_relaxed,
                    key=lambda item: (float(item.get("__trend_value") or 0.0), float(item.get("outlier_score") or 0.0)),
                    reverse=True,
                )
                supplements_added = 0
                for candidate in relaxed_sorted:
                    candidate_id = str(candidate.get("video_id") or "")
                    if not candidate_id or candidate_id in seen_ids:
                        continue
                    outliers.append(dict(candidate))
                    seen_ids.add(candidate_id)
                    supplements_added += 1
                    if len(outliers) >= min_return_target:
                        break
                if supplements_added > 0:
                    logger.info(
                        "[OutlierParser] Added %d relaxed candidates to reach minimum return target (%d)",
                        supplements_added,
                        min_return_target,
                    )

            normalized_primary: List[Dict] = []
            if outliers:
                normalized_primary = self._normalize_views_band(
                    outliers,
                    hard_min_views=hard_min_views,
                    target_limit=target_limit,
                )
                normalized_primary = self._prefer_popular_results(
                    normalized_primary,
                    target_limit=target_limit,
                    search_profile=profile,
                )
                for item in normalized_primary:
                    item.pop("__trend_value", None)
                if len(normalized_primary) >= min_return_target:
                    return normalized_primary[:target_limit]

            fallback_outliers = []
            coverage_outliers = []
            fallback_min_signal_count = max(1, min(min_signal_count, self._int_env("OUTLIER_SEARCH_FALLBACK_MIN_SIGNAL_COUNT", 1)))
            fallback_per_channel: Dict[str, int] = defaultdict(int)
            for video in videos:
                snippet = video.get("snippet", {})
                stats = video.get("statistics", {})
                content_details = video.get("contentDetails", {})
                channel_id = snippet.get("channelId")
                if not channel_id:
                    continue
                if fallback_per_channel[channel_id] >= 2:
                    continue

                duration_seconds = self._parse_iso_duration_seconds(content_details.get("duration", ""))
                detected_type = self._detect_content_type(duration_seconds)
                if content_type_normalized == "shorts" and detected_type != "shorts":
                    continue
                if content_type_normalized == "long" and detected_type != "long":
                    continue

                language_confidence = self._language_confidence(snippet, effective_lang)
                if language_confidence < self._float_env("OUTLIER_SEARCH_MIN_LANGUAGE_CONFIDENCE", 0.40):
                    continue

                if keyword_tokens:
                    fallback_relevance = self._keyword_relevance(snippet, keyword_tokens)
                    fallback_min_ratio = self._float_env("OUTLIER_SEARCH_FALLBACK_MIN_RELEVANCE_RATIO", 0.25)
                    if (
                        (fallback_relevance["matches"] < 1)
                        or (fallback_relevance["title_matches"] < 1)
                        or (fallback_relevance["ratio"] < fallback_min_ratio)
                    ):
                        continue

                views = self._parse_int(stats.get("viewCount"))
                if views < hard_min_views:
                    continue
                likes = self._parse_int(stats.get("likeCount"))
                comments = self._parse_int(stats.get("commentCount"))
                published_at_raw = snippet.get("publishedAt")
                if not published_at_raw:
                    continue

                published_at = self._parse_published_at(published_at_raw)
                age_hours = self._age_hours(published_at)
                if detected_type == "shorts":
                    baseline_views = max(channel_baseline_views_shorts[channel_id], 40)
                else:
                    baseline_views = max(channel_baseline_views_long[channel_id], 60)

                channel_stats = channels_map.get(channel_id, {}).get("statistics", {})
                subscribers = self._parse_int(channel_stats.get("subscriberCount"))
                score_data = self._compute_score(
                    views=views,
                    likes=likes,
                    comments=comments,
                    subscribers=subscribers,
                    baseline_views=baseline_views,
                    age_hours=age_hours,
                )
                quality_score = self._quality_score(
                    views=views,
                    likes=likes,
                    comments=comments,
                    subscribers=subscribers,
                    age_hours=age_hours,
                )
                confidence_score = self._confidence_score(
                    views=views,
                    baseline_views=baseline_views,
                    age_hours=age_hours,
                    subscribers=subscribers,
                )
                final_outlier_score = score_data["outlier_score"] * (0.78 + quality_score * 0.22) * (0.84 + confidence_score * 0.16)
                signal_count = self._quality_signals(
                    views=views,
                    velocity_per_hour=float(score_data["velocity_per_hour"]),
                    relative_multiplier=float(score_data["relative_multiplier"]),
                    outlier_score=float(final_outlier_score),
                    min_views=min_views,
                    min_velocity=min_velocity,
                    min_multiplier=min_multiplier,
                    min_outlier=min_outlier,
                )

                coverage_item = {
                    "video_id": video.get("id"),
                    "title": snippet.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={video.get('id')}",
                    "channel_id": channel_id,
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": published_at_raw,
                    "thumbnail": (snippet.get("thumbnails", {}).get("high", {}) or snippet.get("thumbnails", {}).get("default", {})).get("url"),
                    "duration_seconds": duration_seconds,
                    "content_type": detected_type,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "subscribers": subscribers,
                    "baseline_views": baseline_views,
                    "outlier_score": round(final_outlier_score, 4),
                    "quality_score": quality_score,
                    "confidence_score": confidence_score,
                    "engagement_rate": score_data["engagement_rate"],
                    "topic_cluster": self._topic_cluster_key(snippet.get("title", ""), keyword),
                    "relative_multiplier": score_data["relative_multiplier"],
                    "velocity_per_hour": score_data["velocity_per_hour"],
                    "views_delta_24h": 0,
                    "momentum_score": 0.0,
                    "__trend_value": self._composite_trend_score(
                        views=views,
                        velocity_per_hour=float(score_data["velocity_per_hour"]),
                        relative_multiplier=float(score_data["relative_multiplier"]),
                        outlier_score=float(final_outlier_score),
                        quality_score=float(quality_score),
                        confidence_score=float(confidence_score),
                        relevance_ratio=0.0,
                        language_confidence=float(language_confidence),
                    ),
                    "reason": "Coverage fill: relevant fast-growing candidate",
                }
                coverage_outliers.append(coverage_item)

                if signal_count < fallback_min_signal_count:
                    continue
                fallback_outliers.append(
                    {
                        "video_id": video.get("id"),
                        "title": snippet.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={video.get('id')}",
                        "channel_id": channel_id,
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": published_at_raw,
                        "thumbnail": (snippet.get("thumbnails", {}).get("high", {}) or snippet.get("thumbnails", {}).get("default", {})).get("url"),
                        "duration_seconds": duration_seconds,
                        "content_type": detected_type,
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "subscribers": subscribers,
                        "baseline_views": baseline_views,
                        "outlier_score": round(final_outlier_score, 4),
                        "quality_score": quality_score,
                        "confidence_score": confidence_score,
                        "engagement_rate": score_data["engagement_rate"],
                        "topic_cluster": self._topic_cluster_key(snippet.get("title", ""), keyword),
                        "relative_multiplier": score_data["relative_multiplier"],
                        "velocity_per_hour": score_data["velocity_per_hour"],
                        "views_delta_24h": 0,
                        "momentum_score": 0.0,
                        "__trend_value": self._composite_trend_score(
                            views=views,
                            velocity_per_hour=float(score_data["velocity_per_hour"]),
                            relative_multiplier=float(score_data["relative_multiplier"]),
                            outlier_score=float(final_outlier_score),
                            quality_score=float(quality_score),
                            confidence_score=float(confidence_score),
                            relevance_ratio=0.0,
                            language_confidence=float(language_confidence),
                        ),
                        "reason": "Fallback ranking: strongest recent candidates for this keyword",
                    }
                )
                fallback_per_channel[channel_id] += 1

            fallback_outliers.sort(
                key=lambda item: (float(item.get("__trend_value") or 0.0), float(item.get("outlier_score") or 0.0), int(item.get("views") or 0)),
                reverse=True,
            )
            normalized_fallback = self._normalize_views_band(
                fallback_outliers,
                hard_min_views=hard_min_views,
                target_limit=target_limit,
            )
            normalized_fallback = self._prefer_popular_results(normalized_fallback, target_limit=target_limit, search_profile=profile)
            for item in normalized_fallback:
                item.pop("__trend_value", None)

            combined_results: List[Dict] = []
            seen_combined = set()
            for item in normalized_primary:
                video_id = str(item.get("video_id") or "")
                if not video_id or video_id in seen_combined:
                    continue
                seen_combined.add(video_id)
                combined_results.append(item)
                if len(combined_results) >= target_limit:
                    break

            for item in normalized_fallback:
                if len(combined_results) >= target_limit:
                    break
                video_id = str(item.get("video_id") or "")
                if not video_id or video_id in seen_combined:
                    continue
                seen_combined.add(video_id)
                combined_results.append(item)

            if len(combined_results) < min_return_target and coverage_outliers:
                coverage_outliers.sort(
                    key=lambda item: (
                        float(item.get("__trend_value") or 0.0),
                        float(item.get("outlier_score") or 0.0),
                        int(item.get("views") or 0),
                    ),
                    reverse=True,
                )
                added_coverage = 0
                for item in coverage_outliers:
                    if len(combined_results) >= target_limit:
                        break
                    video_id = str(item.get("video_id") or "")
                    if not video_id or video_id in seen_combined:
                        continue
                    seen_combined.add(video_id)
                    item.pop("__trend_value", None)
                    combined_results.append(item)
                    added_coverage += 1
                    if len(combined_results) >= min_return_target:
                        break
                if added_coverage > 0:
                    logger.info(
                        "[OutlierParser] Added %d coverage candidates to improve return count",
                        added_coverage,
                    )

            logger.info(
                "[OutlierParser] Returning %d results (primary=%d, fallback=%d, min_target=%d)",
                len(combined_results),
                len(normalized_primary),
                len(normalized_fallback),
                min_return_target,
            )
            return combined_results[:target_limit]

        except HttpError as e:
            if self._is_quota_error(e) or self._is_forbidden_key_error(e) or self._is_invalid_key_error(e):
                raise RuntimeError("YouTube API quota exceeded for all configured keys")
            logger.error("[OutlierParser] API error: %s", e)
            return []
        except Exception as e:
            if isinstance(e, RuntimeError) and (
                "YouTube API quota exceeded" in str(e)
                or "YouTube API keys are forbidden/suspended" in str(e)
                or "No available API keys" in str(e)
            ):
                raise
            logger.error("[OutlierParser] Unexpected error: %s", e, exc_info=True)
            return []
