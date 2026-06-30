from __future__ import annotations

import asyncio
import functools
import logging
import os
import re
import json
import time as _time
import uuid
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import yt_dlp
import requests as _sync_requests
from bs4 import BeautifulSoup

from collector.collect.channel_info import collect_channel_info
from collector.collect.video_details import collect_video_details
from collector.collect_uploads import collect_channel_videos
from collector.resolver_v2 import resolve_youtube_channel_id
from collector.yt_client import get_shared_yt_client

from .platforms import get_platform
from .schemas import ContentFactoryVideoPayload

logger = logging.getLogger(__name__)

_YT_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_DEFAULT_SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}
_STRICT_SOCIAL_METRIC_SANITIZE_NETWORKS = {
    "instagram",
    "tiktok",
    "vk",
    "ok",
    "rutube",
    "likee",
    "dzen",
    "x",
}

# Process-level caches that survive within a single worker instance.
# _DEAD_PROXIES: proxies that returned 402 Payment Required; skip them immediately.
# _APIFY_HARD_LIMIT_HIT: when True, all Apify calls short-circuit with a clear error.
_DEAD_PROXIES: set[str] = set()
_APIFY_HARD_LIMIT_HIT: bool = False

try:
    from . import local_secrets as _local_secrets  # type: ignore
except Exception:
    _local_secrets = None


class ParserResult:
    def __init__(
        self,
        channel_external_id: Optional[str],
        channel_title: Optional[str],
        videos: list[ContentFactoryVideoPayload],
        subscribers_count: Optional[int] = None,
        sync_status: str = "ok",
        sync_message: Optional[str] = None,
        resolved_network: Optional[str] = None,
    ):
        self.channel_external_id = channel_external_id
        self.channel_title = channel_title
        self.videos = videos
        self.subscribers_count = subscribers_count
        self.sync_status = sync_status
        self.sync_message = sync_message
        self.resolved_network = resolved_network


def _sanitize_video_metrics(network: str, video: ContentFactoryVideoPayload) -> None:
    """Normalize obviously broken metric combinations coming from brittle page parsers."""
    network_l = str(network or "").strip().lower()
    strict_social_sanitize = network_l in _STRICT_SOCIAL_METRIC_SANITIZE_NETWORKS

    views = max(0, int(video.views or 0))
    likes = max(0, int(video.likes or 0))
    comments = max(0, int(video.comments or 0))

    # If no views were extracted, reactions are usually parser noise.
    if views <= 0:
        likes = 0
        comments = 0

    # Keep reaction counters within a sane envelope for noisy parsers.
    if views > 0:
        max_reactions = max(views * 2, views + 50)
        likes = min(likes, max_reactions)
        comments = min(comments, max_reactions)

        # Generic sanity guard for noisy scrapers on low-view videos.
        if comments > views and views <= 1000:
            comments = 0
        if likes > max(views * 2, 50) and views <= 1000:
            likes = 0

    # Social parsers are noisier than API-based YouTube extraction.
    if strict_social_sanitize and views > 0:
        if comments > views:
            comments = 0
        if likes > views:
            likes = 0

    if strict_social_sanitize and views <= 10:
        likes = 0
        comments = 0

    video.views = int(views)
    video.likes = int(likes)
    video.comments = int(comments)


def _parse_yt_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = str(raw)
    if len(raw) == 8 and raw.isdigit():
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
    return None


def _parse_yt_timestamp(raw: object) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        ts = int(raw)
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _parse_published_at(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_any_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return _as_utc(raw)

    text = str(raw).strip()
    if not text:
        return None

    if text.isdigit():
        try:
            ts = int(text)
            # Apify datasets can return ms timestamps.
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return _as_utc(datetime.fromisoformat(candidate))
        except Exception:
            continue
    return None


def _secret(name: str, default: str = "") -> str:
    # Environment has priority so deployments can override or clear baked-in local secrets.
    # This is important for APIFY_TOKEN: empty env value must disable Apify calls.
    if name in os.environ:
        return str(os.environ.get(name, "")).strip()

    local_value = getattr(_local_secrets, name, None) if _local_secrets else None
    if isinstance(local_value, str) and local_value.strip():
        return local_value.strip()
    return str(default).strip()


# ---------------------------------------------------------------------------
# Apify token pool / rotator
# Priority: APIFY_TOKEN_POOL (comma-separated) > APIFY_TOKEN_1, APIFY_TOKEN_2...
#           > APIFY_TOKEN (single).
# Tokens exhausted by 429/hard-limit are skipped until process restart.
# ---------------------------------------------------------------------------
_APIFY_EXHAUSTED_TOKENS: set[str] = set()


def _get_apify_token_pool() -> list[str]:
    """Return ordered list of all configured Apify tokens."""
    pool_raw = _secret("APIFY_TOKEN_POOL", "")
    if pool_raw:
        return [t.strip() for t in pool_raw.split(",") if t.strip()]

    tokens: list[str] = []
    for i in range(1, 20):
        t = _secret(f"APIFY_TOKEN_{i}", "")
        if not t:
            break
        tokens.append(t)

    single = _secret("APIFY_TOKEN", "")
    if single and single not in tokens:
        tokens.append(single)

    return tokens


def _pick_apify_token() -> str:
    """Return the first non-exhausted token from the pool, or empty string."""
    for token in _get_apify_token_pool():
        if token not in _APIFY_EXHAUSTED_TOKENS:
            return token
    return ""


def _feature_enabled(name: str, default: str = "1") -> bool:
    return _secret(name, default).lower() in {"1", "true", "yes", "on"}


def _network_cookie_header(network: str) -> str:
    network_u = str(network or "").strip().upper()
    candidates = (
        f"CONTENT_FACTORY_{network_u}_COOKIE",
        f"CONTENT_FACTORY_{network_u}_COOKIES",
        "CONTENT_FACTORY_SCRAPER_COOKIE",
        "CONTENT_FACTORY_SCRAPER_COOKIES",
    )
    for key in candidates:
        value = _secret(key, "")
        if value and "=" in value:
            return value.strip()
    return ""


def _headers_for_network(network: str) -> dict[str, str]:
    headers = dict(_DEFAULT_SCRAPER_HEADERS)
    if network == "dzen":
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    if network in {"ok", "likee", "dzen"}:
        headers.setdefault("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8")

    cookie_header = _network_cookie_header(network)
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def _timeout_seconds(name: str, default: int) -> int:
    try:
        return max(5, int(_secret(name, str(default)) or str(default)))
    except Exception:
        return max(5, int(default))


def _secret_int(name: str, default: int, *, min_value: int = 1, max_value: int = 5000) -> int:
    try:
        value = int(str(_secret(name, str(default)) or str(default)).strip())
    except Exception:
        value = int(default)
    if value < min_value:
        value = min_value
    if value > max_value:
        value = max_value
    return value


def _normalize_proxy_url(raw: str) -> Optional[str]:
    value = str(raw or "").strip()
    if not value or value.startswith("#"):
        return None

    if "://" in value:
        return value

    parts = [segment.strip() for segment in value.split(":")]
    if len(parts) == 4 and all(parts):
        host, port, username, password = parts
        return f"http://{username}:{password}@{host}:{port}"
    if len(parts) == 2 and all(parts):
        host, port = parts
        return f"http://{host}:{port}"
    return None


def _proxy_candidates(*names: str) -> list[str]:
    """Build ordered proxy candidates from env/local secrets and proxy.txt fallback."""
    raw_candidates: list[str] = []
    file_candidates: list[str] = []

    for name in names:
        value = _secret(name, "")
        if value:
            raw_candidates.extend(token.strip() for token in re.split(r"[,;\n]", value) if token.strip())

    for fallback_name in (
        "CONTENT_FACTORY_PROXY_URL",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
    ):
        value = _secret(fallback_name, "")
        if value:
            raw_candidates.extend(token.strip() for token in re.split(r"[,;\n]", value) if token.strip())

    proxy_file = _secret("CONTENT_FACTORY_PROXY_FILE", "/app/proxy.txt")
    if proxy_file:
        try:
            with open(proxy_file, "r", encoding="utf-8") as proxy_handle:
                for line in proxy_handle:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    file_candidates.append(stripped)
        except Exception:
            pass

    # In operational workflows, newest paid proxies are usually appended to the end.
    if _feature_enabled("CONTENT_FACTORY_PROXY_PREFER_RECENT", "1"):
        file_candidates.reverse()
    raw_candidates.extend(file_candidates)

    normalized: list[str] = []
    for candidate in raw_candidates:
        proxy_url = _normalize_proxy_url(candidate)
        if proxy_url and proxy_url not in normalized:
            normalized.append(proxy_url)

    max_candidates = max(1, int(_secret("CONTENT_FACTORY_PROXY_MAX_CANDIDATES", "12") or "12"))
    return normalized[:max_candidates]


def _proxy_attempt_chain(*names: str, include_direct: bool = True) -> list[Optional[str]]:
    chain: list[Optional[str]] = list(_proxy_candidates(*names))
    if include_direct:
        chain.append(None)
    return chain


def _proxy_url(*names: str) -> Optional[str]:
    """Resolve proxy URL from network-specific envs with global fallback."""
    candidates = _proxy_candidates(*names)
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# External anti-bot fetch layer — budget-guarded, network-aware
#
# Providers supported (configure via CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER or
# set API keys and let auto-detection pick the first available):
#   smartproxy  — SMARTPROXY_USER / SMARTPROXY_PASSWORD (Site Unblocker HTTP API)
#   iproyal     — IPROYAL_WEB_UNBLOCKER_USER / IPROYAL_WEB_UNBLOCKER_PASSWORD
#   scrapfly    — SCRAPFLY_API_KEY
#   scrapingbee — SCRAPINGBEE_API_KEY
#   zenrows     — ZENROWS_API_KEY
#
# Budget controls (all optional with safe defaults):
#   CONTENT_FACTORY_EXTERNAL_FETCH_ENABLED        — "1" (default on)
#   CONTENT_FACTORY_EXTERNAL_FETCH_NETWORKS       — comma-separated allowlist, default "vk,ok,likee"
#   CONTENT_FACTORY_EXTERNAL_FETCH_DAILY_LIMIT    — max paid calls/day per worker process, default 400
#   CONTENT_FACTORY_EXTERNAL_FETCH_MAX_HTML_BYTES — truncate very large HTML to avoid OOM, default 2MB
#   CONTENT_FACTORY_EXTERNAL_FETCH_TIMEOUT_SECONDS — request timeout, default 45
#
# Network → provider routing (CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER_<NETWORK>):
#   e.g. CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER_VK=smartproxy
#        CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER_OK=smartproxy
# ---------------------------------------------------------------------------

_EF_DAY: Optional[str] = None
_EF_COUNT: int = 0


def _ef_allowed(network: Optional[str]) -> bool:
    if not _feature_enabled("CONTENT_FACTORY_EXTERNAL_FETCH_ENABLED", "1"):
        return False
    raw = _secret("CONTENT_FACTORY_EXTERNAL_FETCH_NETWORKS", "vk,ok,likee")
    allowed = {s.strip().lower() for s in raw.split(",") if s.strip()}
    if allowed and (not network or network.lower() not in allowed):
        return False
    global _EF_DAY, _EF_COUNT
    today = datetime.now(timezone.utc).date().isoformat()
    if _EF_DAY != today:
        _EF_DAY, _EF_COUNT = today, 0
    try:
        limit = max(0, int((_secret("CONTENT_FACTORY_EXTERNAL_FETCH_DAILY_LIMIT", "400") or "400").strip()))
    except Exception:
        limit = 400
    return limit == 0 or _EF_COUNT < limit


def _ef_mark() -> None:
    global _EF_COUNT
    _EF_COUNT += 1


def _ef_provider_for(network: Optional[str]) -> Optional[str]:
    """Return explicit per-network provider override if configured."""
    if not network:
        return None
    key = f"CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER_{network.upper()}"
    return (_secret(key, "") or "").strip().lower() or None


async def _external_fetch_html(
    url: str,
    *,
    render_js: bool = True,
    country: Optional[str] = None,
    network: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Fetch HTML through an optional managed anti-bot provider.

    Returns (html, provider_name) or (None, None) when skipped / failed.
    """
    if not _ef_allowed(network):
        return None, None

    max_bytes = max(200_000, int((_secret("CONTENT_FACTORY_EXTERNAL_FETCH_MAX_HTML_BYTES", "2000000") or "2000000")))
    effective_country = (country or _secret("CONTENT_FACTORY_EXTERNAL_FETCH_COUNTRY", "") or "").strip().lower() or None
    timeout = aiohttp.ClientTimeout(total=_timeout_seconds("CONTENT_FACTORY_EXTERNAL_FETCH_TIMEOUT_SECONDS", 45))

    # Build ordered provider candidate list.
    # 1) per-network override  2) global override  3) auto-detect by available keys
    smartproxy_user = _secret("SMARTPROXY_USER", "")
    smartproxy_pass = _secret("SMARTPROXY_PASSWORD", "")
    iproyal_user = _secret("IPROYAL_WEB_UNBLOCKER_USER", "")
    iproyal_pass = _secret("IPROYAL_WEB_UNBLOCKER_PASSWORD", "")
    iproyal_host = _secret("IPROYAL_WEB_UNBLOCKER_HOST", "unblocker.iproyal.com")
    iproyal_port = _secret("IPROYAL_WEB_UNBLOCKER_PORT", "12323")
    scrapfly_key = _secret("SCRAPFLY_API_KEY", "")
    scrapingbee_key = _secret("SCRAPINGBEE_API_KEY", "")
    zenrows_key = _secret("ZENROWS_API_KEY", "")

    network_provider = _ef_provider_for(network)
    global_provider = (_secret("CONTENT_FACTORY_EXTERNAL_FETCH_PROVIDER", "") or "").strip().lower()
    forced = network_provider or global_provider

    provider_candidates: list[str] = []
    if forced:
        provider_candidates.append(forced)
    else:
        if smartproxy_user and smartproxy_pass:
            provider_candidates.append("smartproxy")
        if iproyal_user and iproyal_pass:
            provider_candidates.append("iproyal")
        if scrapfly_key:
            provider_candidates.append("scrapfly")
        if zenrows_key:
            provider_candidates.append("zenrows")
        if scrapingbee_key:
            provider_candidates.append("scrapingbee")

    if not provider_candidates:
        return None, None

    base_headers = _headers_for_network(str(network or "")) if network else {"User-Agent": _DEFAULT_SCRAPER_HEADERS["User-Agent"]}
    async with aiohttp.ClientSession(timeout=timeout, headers=base_headers) as session:
        for candidate in provider_candidates:
            try:
                if candidate == "smartproxy" and smartproxy_user and smartproxy_pass:
                    _ef_mark()
                    # Smartproxy Site Unblocker: residential HTTP proxy endpoint.
                    # Credentials are passed as proxy auth; Site Unblocker handles JS rendering
                    # and CAPTCHA solving server-side transparently.
                    proxy_url = f"http://{smartproxy_user}:{smartproxy_pass}@gate.smartproxy.com:10001"
                    sp_headers = dict(base_headers)
                    if effective_country:
                        # Smartproxy allows country targeting via user suffix: user-cc-<CC>
                        proxy_url = f"http://{smartproxy_user}-cc-{effective_country}:{smartproxy_pass}@gate.smartproxy.com:10001"
                    async with session.get(url, proxy=proxy_url, ssl=False, headers=sp_headers) as response:
                        raw = await response.content.read(max_bytes + 1)
                        if len(raw) > max_bytes:
                            raw = raw[:max_bytes]
                        html = raw.decode(response.charset or "utf-8", errors="ignore")
                        if response.status < 400 and html.strip():
                            return html, "smartproxy"

                elif candidate == "iproyal" and iproyal_user and iproyal_pass:
                    _ef_mark()
                    # IPRoyal Web Unblocker is exposed as a backconnect proxy endpoint.
                    proxy_url = f"http://{iproyal_user}:{iproyal_pass}@{iproyal_host}:{iproyal_port}"
                    ipr_headers = dict(base_headers)
                    async with session.get(url, proxy=proxy_url, ssl=False, headers=ipr_headers) as response:
                        raw = await response.content.read(max_bytes + 1)
                        if len(raw) > max_bytes:
                            raw = raw[:max_bytes]
                        html = raw.decode(response.charset or "utf-8", errors="ignore")
                        if response.status < 400 and html.strip():
                            return html, "iproyal"

                elif candidate == "scrapfly" and scrapfly_key:
                    _ef_mark()
                    params: dict[str, Any] = {
                        "key": scrapfly_key,
                        "url": url,
                        "render_js": "true" if render_js else "false",
                        "asp": "true",
                        "format": "json",
                    }
                    if effective_country:
                        params["country"] = effective_country
                    proxy_pool = _secret("CONTENT_FACTORY_EXTERNAL_FETCH_PROXY_POOL", "public_residential")
                    if proxy_pool:
                        params["proxy_pool"] = proxy_pool
                    async with session.get("https://api.scrapfly.io/scrape", params=params) as response:
                        raw = await response.content.read(max_bytes * 2 + 1)
                        payload_text = raw.decode("utf-8", errors="ignore")
                        if response.status >= 400:
                            continue
                        parsed = json.loads(payload_text)
                        if not isinstance(parsed, dict):
                            continue
                        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
                        content = result.get("content") if isinstance(result, dict) else None
                        if isinstance(content, str) and content.strip():
                            return content[:max_bytes], "scrapfly"

                elif candidate == "zenrows" and zenrows_key:
                    _ef_mark()
                    params = {
                        "apikey": zenrows_key,
                        "url": url,
                        "js_render": "true" if render_js else "false",
                        "premium_proxy": "true",
                    }
                    if effective_country:
                        params["proxy_country"] = effective_country
                    async with session.get("https://api.zenrows.com/v1/", params=params) as response:
                        raw = await response.content.read(max_bytes + 1)
                        html = raw[:max_bytes].decode("utf-8", errors="ignore")
                        if response.status >= 400:
                            continue
                        if html.strip():
                            return html, "zenrows"

                elif candidate == "scrapingbee" and scrapingbee_key:
                    _ef_mark()
                    params = {
                        "api_key": scrapingbee_key,
                        "url": url,
                        "render_js": "true" if render_js else "false",
                        "premium_proxy": "true",
                    }
                    if effective_country:
                        params["country_code"] = effective_country
                    async with session.get("https://app.scrapingbee.com/api/v1/", params=params) as response:
                        raw = await response.content.read(max_bytes + 1)
                        html = raw[:max_bytes].decode("utf-8", errors="ignore")
                        if response.status >= 400:
                            continue
                        if html.strip():
                            return html, "scrapingbee"

            except Exception:
                continue

    return None, None


async def _run_apify_actor(actor_id: str, token: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    timeout = aiohttp.ClientTimeout(total=240)
    attempts = max(1, int(_secret("CONTENT_FACTORY_APIFY_MAX_ATTEMPTS", "3")))
    base_delay = max(1, int(_secret("CONTENT_FACTORY_APIFY_RETRY_BASE_SECONDS", "2")))
    last_error: Optional[str] = None

    # Build candidate token list: start with the explicitly-passed token,
    # then fall back to the pool (skipping already-exhausted tokens).
    token_candidates: list[str] = []
    if token and token not in _APIFY_EXHAUSTED_TOKENS:
        token_candidates.append(token)
    for t in _get_apify_token_pool():
        if t not in token_candidates and t not in _APIFY_EXHAUSTED_TOKENS:
            token_candidates.append(t)
    if not token_candidates:
        raise RuntimeError("No available Apify tokens (all tokens are exhausted or not configured).")

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for active_token in token_candidates:
            for attempt in range(1, attempts + 1):
                try:
                    async with session.post(
                        endpoint,
                        params={"token": active_token, "clean": "1"},
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        response_text = await response.text()
                        if response.status >= 400:
                            message = response_text[:800]
                            err_type = ""
                            err_message = ""
                            try:
                                parsed = json.loads(response_text)
                                if isinstance(parsed, dict):
                                    err = parsed.get("error")
                                    if isinstance(err, dict):
                                        err_type = str(err.get("type") or "").strip()
                                        err_message = str(err.get("message") or "").strip()
                                        if err_type or err_message:
                                            message = f"{err_type}: {err_message}".strip(": ")
                            except Exception:
                                pass

                            lowered_message = message.lower()

                            # Hard-limit: mark token exhausted and rotate to next.
                            if response.status == 403 and (
                                "platform-feature-disabled" in lowered_message
                                or "hard limit exceeded" in lowered_message
                                or (
                                    err_type.lower() == "platform-feature-disabled"
                                    and "hard limit" in err_message.lower()
                                )
                            ):
                                _APIFY_EXHAUSTED_TOKENS.add(active_token)
                                last_error = (
                                    "Apify monthly hard limit exceeded for this token. "
                                    "Rotating to next token in pool."
                                )
                                break  # break inner loop → try next token

                            # Rate-limit: mark token exhausted and rotate.
                            if response.status == 429:
                                _APIFY_EXHAUSTED_TOKENS.add(active_token)
                                last_error = f"Apify rate-limited (429) on token ...{active_token[-6:]}. Rotating."
                                break  # break inner loop → try next token

                            retryable_http = response.status in {408, 409, 425, 500, 502, 503, 504}
                            last_error = f"Apify actor call failed ({response.status}): {message[:400]}"
                            if retryable_http and attempt < attempts:
                                await asyncio.sleep(float(base_delay * attempt))
                                continue
                            raise RuntimeError(last_error)

                        data = await response.json(content_type=None)
                        if not isinstance(data, list):
                            raise RuntimeError("Apify actor returned non-list payload")
                        return [item for item in data if isinstance(item, dict)]
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = f"Apify actor network error: {exc}"
                    if attempt < attempts:
                        await asyncio.sleep(float(base_delay * attempt))
                        continue
                    break  # network error on last attempt → try next token

    raise RuntimeError(last_error or "All Apify tokens exhausted or call failed")


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return default

            lowered = raw.lower().replace("\u00a0", " ")
            multiplier = 1.0
            if any(token in lowered for token in ("тыс", "k")):
                multiplier = 1_000.0
            elif any(token in lowered for token in ("млн", "m")):
                multiplier = 1_000_000.0
            elif any(token in lowered for token in ("млрд", "b")):
                multiplier = 1_000_000_000.0

            # Keep only numeric-compatible characters for conversion.
            compact = lowered.replace(" ", "")
            compact = re.sub(r"[^0-9.,+-]", "", compact)
            if not compact:
                return default

            # Detect decimal separator reliably for values like 1,2K / 1.2K.
            if "," in compact and "." in compact:
                compact = compact.replace(",", "")
            elif "," in compact:
                compact = compact.replace(",", ".")

            return int(float(compact) * multiplier)
        return int(value)
    except Exception:
        return default


def _pick_first(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _pick_path(item: dict[str, Any], path: str) -> Any:
    current: Any = item
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current.get(part)
            continue
        return None
    return current


def _pick_first_path(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = _pick_path(item, key)
        if value is not None:
            return value
    return None


def _expand_instagram_apify_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Some Instagram actors return profile rows with nested arrays instead of flat post rows.
    Flatten those payload variants into post-like dict items.
    """
    expanded: list[dict[str, Any]] = []
    nested_keys = (
        "latestPosts",
        "latestIgtvVideos",
        "latestReels",
        "reels",
        "posts",
        "media",
        "items",
        "videos",
        "edges",
    )

    for item in items:
        emitted_nested = False
        owner_username = str(_pick_first(item, ("username", "ownerUsername", "userName")) or "").strip()
        owner_followers = _as_int(_pick_first(item, ("followersCount", "ownerFollowersCount", "authorFollowers")), default=0)

        for key in nested_keys:
            nested = item.get(key)
            if not isinstance(nested, list):
                continue
            for child in nested:
                if not isinstance(child, dict):
                    continue
                node = child.get("node") if isinstance(child.get("node"), dict) else None
                merged = dict(node or child)
                if node:
                    for edge_key, edge_value in child.items():
                        merged.setdefault(edge_key, edge_value)
                if owner_username and not merged.get("ownerUsername"):
                    merged["ownerUsername"] = owner_username
                if owner_followers > 0 and merged.get("ownerFollowersCount") in (None, "", 0):
                    merged["ownerFollowersCount"] = owner_followers
                if item.get("inputUrl") and not merged.get("inputUrl"):
                    merged["inputUrl"] = item.get("inputUrl")
                expanded.append(merged)
                emitted_nested = True

        if emitted_nested:
            continue
        expanded.append(item)

    return expanded


def _expand_tiktok_apify_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Some TikTok actors return profile rows with nested videos arrays.
    Flatten those payload variants while preserving author metadata.
    """
    expanded: list[dict[str, Any]] = []
    nested_keys = ("videos", "items", "posts", "aweme_list", "videoList", "itemList")

    for item in items:
        emitted_nested = False
        author_meta = None
        for author_key in ("authorMeta", "author", "authorInfo"):
            author_value = item.get(author_key)
            if isinstance(author_value, dict):
                author_meta = author_value
                break

        for key in nested_keys:
            nested = item.get(key)
            if not isinstance(nested, list):
                continue
            for child in nested:
                if not isinstance(child, dict):
                    continue
                node = child.get("node") if isinstance(child.get("node"), dict) else None
                aweme = child.get("aweme_info") if isinstance(child.get("aweme_info"), dict) else None
                merged = dict(aweme or node or child)
                if node or aweme:
                    for edge_key, edge_value in child.items():
                        merged.setdefault(edge_key, edge_value)
                if author_meta and not isinstance(merged.get("authorMeta"), dict):
                    merged["authorMeta"] = author_meta
                expanded.append(merged)
                emitted_nested = True

        if emitted_nested:
            continue
        expanded.append(item)

    return expanded


def _extract_handle_from_url(raw_url: str) -> Optional[str]:
    parsed = urlparse(raw_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    candidate = path_parts[-1]
    return candidate.strip("@") or None


def _infer_network_from_url(channel_url: str) -> Optional[str]:
    raw = str(channel_url or "").strip().lower()
    if not raw:
        return None

    host = ""
    try:
        host = (urlparse(raw).hostname or "").lower()
    except Exception:
        host = ""

    checks = [host, raw]
    if any("youtube.com" in item or "youtu.be" in item for item in checks):
        return "youtube"
    if any("instagram.com" in item for item in checks):
        return "instagram"
    if any("tiktok.com" in item for item in checks):
        return "tiktok"
    if any("vk.com" in item or "vkvideo.ru" in item for item in checks):
        return "vk"
    if any("ok.ru" in item for item in checks):
        return "ok"
    if any("rutube.ru" in item for item in checks):
        return "rutube"
    if any("dzen.ru" in item for item in checks):
        return "dzen"
    if any("likee.video" in item for item in checks):
        return "likee"
    return None


def _extract_json_ld_objects(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text(strip=True)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:
            continue

        queue: list[Any] = [parsed]
        while queue:
            current = queue.pop(0)
            if isinstance(current, dict):
                objects.append(current)
                graph = current.get("@graph")
                if isinstance(graph, list):
                    queue.extend(graph)
            elif isinstance(current, list):
                queue.extend(current)
    return objects


def _extract_video_objects_from_json_ld(html: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for obj in _extract_json_ld_objects(html):
        raw_type = obj.get("@type")
        types = [raw_type] if isinstance(raw_type, str) else (list(raw_type) if isinstance(raw_type, list) else [])
        if any(str(item).lower() == "videoobject" for item in types):
            output.append(obj)
    return output


def _extract_count_by_regex(html: str, patterns: Iterable[str]) -> int:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue
        for idx in range(1, len(match.groups()) + 1):
            value = _as_int(match.group(idx), default=0)
            if value > 0:
                return value
    return 0


def _parse_iso8601_duration(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    text = str(raw).strip().upper()
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", text)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _extract_video_page_metrics(html: str) -> dict[str, Any]:
    title: Optional[str] = None
    published_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    views = 0
    likes = 0
    comments = 0

    for obj in _extract_video_objects_from_json_ld(html):
        if not title:
            title = str(obj.get("name") or obj.get("headline") or "").strip() or None
        if not published_at:
            published_at = _parse_any_datetime(obj.get("uploadDate") or obj.get("datePublished"))
        if not duration_seconds:
            duration_seconds = _parse_iso8601_duration(str(obj.get("duration") or ""))

        interaction_count = _as_int(obj.get("interactionCount"), default=0)
        if interaction_count > 0:
            views = max(views, interaction_count)

        interaction_stat = obj.get("interactionStatistic")
        if isinstance(interaction_stat, list):
            for stat in interaction_stat:
                if not isinstance(stat, dict):
                    continue
                interaction_type = str(stat.get("interactionType") or "").lower()
                count = _as_int(stat.get("userInteractionCount"), default=0)
                if "watch" in interaction_type or "view" in interaction_type or "play" in interaction_type:
                    views = max(views, count)
                elif "like" in interaction_type:
                    likes = max(likes, count)
                elif "comment" in interaction_type:
                    comments = max(comments, count)
        elif isinstance(interaction_stat, dict):
            interaction_type = str(interaction_stat.get("interactionType") or "").lower()
            count = _as_int(interaction_stat.get("userInteractionCount"), default=0)
            if "watch" in interaction_type or "view" in interaction_type or "play" in interaction_type:
                views = max(views, count)
            elif "like" in interaction_type:
                likes = max(likes, count)
            elif "comment" in interaction_type:
                comments = max(comments, count)

    if not title:
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.get_text(strip=True) if soup.title else "") or None

    views = max(
        views,
        _extract_count_by_regex(
            html,
            (
                r'"viewCount"\s*:\s*"?(\d+)"?',
                r'"viewsCount"\s*:\s*"?(\d+)"?',
                r'"views_count"\s*:\s*"?(\d+)"?',
                r'"playCount"\s*:\s*"?(\d+)"?',
                r'"play_count"\s*:\s*"?(\d+)"?',
                r'"views"\s*:\s*(\d+)',
                r'"views"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                r'"hits"\s*:\s*"?(\d+)"?',
                r'"videoViewCount"\s*:\s*"?(\d+)"?',
                r'"videoViews"\s*:\s*"?(\d+)"?',
                r'"watchCount"\s*:\s*"?(\d+)"?',
                r'"watch_count"\s*:\s*"?(\d+)"?',
                r'"count"\s*:\s*"?(\d+)"?\s*[},\]].*?(?:просмотр|view)',
                r'([0-9\s\.,]+)\s+просмотр',
                r'(?:просмотр(?:ов|а)?|views?)\s*[:\-]?\s*([0-9\s\.,kmbтысмлнмлрд]+)',
            ),
        ),
    )
    likes = max(
        likes,
        _extract_count_by_regex(
            html,
            (
                r'"likeCount"\s*:\s*"?(\d+)"?',
                r'"likesCount"\s*:\s*"?(\d+)"?',
                r'"likes_count"\s*:\s*"?(\d+)"?',
                r'"likes"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                r'"data-likes"\s*=\s*"?(\d+)"?',
                r'([0-9\s\.,]+)\s+(?:лайк|класс|like)',
                r'(?:лайк(?:ов|а|и)?|класс(?:ов|а)?|likes?)\s*[:\-]?\s*([0-9\s\.,kmbтысмлнмлрд]+)',
            ),
        ),
    )
    comments = max(
        comments,
        _extract_count_by_regex(
            html,
            (
                r'"commentCount"\s*:\s*"?(\d+)"?',
                r'"commentsCount"\s*:\s*"?(\d+)"?',
                r'"comments_count"\s*:\s*"?(\d+)"?',
                r'"comments"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                r'"data-comments"\s*=\s*"?(\d+)"?',
                r'"comment_num"\s*:\s*"?(\d+)"?',
                r'([0-9\s\.,]+)\s+(?:коммент|comment)',
                r'(?:коммент(?:ариев|ария|арии)?|comments?)\s*[:\-]?\s*([0-9\s\.,kmbтысмлнмлрд]+)',
            ),
        ),
    )

    # Try additional extraction for VK API responses embedded in page
    if not likes or likes == 0:
        vk_likes_match = re.search(r'"likes"\s*:\s*(\d+)', html)
        if vk_likes_match:
            likes = max(likes, int(vk_likes_match.group(1)))
    
    if not comments or comments == 0:
        vk_comments_match = re.search(r'"comments"\s*:\s*(\d+)', html)
        if vk_comments_match:
            comments = max(comments, int(vk_comments_match.group(1)))

    if not published_at:
        # fallback via regex because page schemas differ heavily.
        for pattern in (
            r'"datePublished"\s*:\s*"([^"]+)"',
            r'"uploadDate"\s*:\s*"([^"]+)"',
            r'"publishedAt"\s*:\s*"([^"]+)"',
            r'"createdAt"\s*:\s*"([^"]+)"',
            r'"created_at"\s*:\s*"([^"]+)"',
            r'"publishDate"\s*:\s*"([^"]+)"',
        ):
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if not m:
                continue
            candidate = _parse_any_datetime(m.group(1))
            if candidate:
                published_at = candidate
                break

    # Some pages expose publish timestamps as unix time fields.
    if not published_at:
        for pattern in (
            r'"createTime"\s*:\s*"?(\d{10,13})"?',
            r'"publish_time"\s*:\s*"?(\d{10,13})"?',
            r'"published_ts"\s*:\s*"?(\d{10,13})"?',
            r'"created_ts"\s*:\s*"?(\d{10,13})"?',
            r'"timestamp"\s*:\s*"?(\d{10,13})"?',
        ):
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if not m:
                continue
            candidate = _parse_any_datetime(m.group(1))
            if candidate:
                published_at = candidate
                break

    if not duration_seconds:
        dm = re.search(r'"duration"\s*:\s*"(PT[^"]+)"', html, flags=re.IGNORECASE)
        if dm:
            duration_seconds = _parse_iso8601_duration(dm.group(1))
    if not duration_seconds:
        duration_seconds = _extract_count_by_regex(
            html,
            (
                r'"durationSeconds"\s*:\s*"?(\d+)"?',
                r'"duration_seconds"\s*:\s*"?(\d+)"?',
                r'"videoDuration"\s*:\s*"?(\d+)"?',
            ),
        ) or None

    return {
        "title": title,
        "published_at": published_at,
        "duration_seconds": duration_seconds,
        "views": int(views or 0),
        "likes": int(likes or 0),
        "comments": int(comments or 0),
    }


async def _enrich_videos_from_pages(
    videos: list[ContentFactoryVideoPayload],
    *,
    headers: dict[str, str],
    max_videos: int = 80,
    concurrency: int = 6,
) -> None:
    if not videos:
        return

    targets = videos[:max_videos]
    sem = asyncio.Semaphore(max(1, concurrency))
    timeout = aiohttp.ClientTimeout(total=30)

    async def enrich_one(session: aiohttp.ClientSession, video: ContentFactoryVideoPayload) -> None:
        # Skip full records to avoid unnecessary requests.
        if (
            int(video.views or 0) > 0
            and int(video.likes or 0) > 0
            and int(video.comments or 0) > 0
            and video.published_at is not None
            and video.duration_seconds is not None
        ):
            return

        async with sem:
            try:
                async with session.get(video.video_url, allow_redirects=True) as response:
                    if response.status >= 400:
                        return
                    html = await response.text()
            except Exception:
                return

        metrics = _extract_video_page_metrics(html)
        if int(video.views or 0) <= 0:
            video.views = max(int(video.views or 0), int(metrics.get("views") or 0))
        if int(video.likes or 0) <= 0:
            video.likes = max(int(video.likes or 0), int(metrics.get("likes") or 0))
        if int(video.comments or 0) <= 0:
            video.comments = max(int(video.comments or 0), int(metrics.get("comments") or 0))
        if video.published_at is None and metrics.get("published_at") is not None:
            video.published_at = metrics.get("published_at")
        if video.duration_seconds is None and metrics.get("duration_seconds") is not None:
            video.duration_seconds = int(metrics.get("duration_seconds") or 0) or None

        title = str(metrics.get("title") or "").strip()
        if title:
            current = (video.title or "").strip().lower()
            if not current or current in {"vk post", "ok video", "rutube video", "likee video", "dzen post", "instagram post", "tiktok post"} or current.endswith(" video"):
                video.title = title[:500]

    connector = aiohttp.TCPConnector(limit=max(4, concurrency * 2))
    async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
        await asyncio.gather(*(enrich_one(session, video) for video in targets))


async def _enrich_videos_from_pages_browser(
    videos: list[ContentFactoryVideoPayload],
    *,
    max_videos: int = 20,
    wait_ms: int = 2500,
) -> None:
    if not videos:
        return

    browser_enabled = _secret("CONTENT_FACTORY_BROWSER_FALLBACK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not browser_enabled:
        return

    try:
        from playwright.async_api import async_playwright
    except Exception:
        return
    targets = videos[:max_videos]

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            for video in targets:
                # Skip records that already look complete enough
                if (
                    int(video.views or 0) > 0
                    and int(video.likes or 0) > 0
                    and int(video.comments or 0) > 0
                    and video.published_at is not None
                    and video.duration_seconds is not None
                ):
                    continue

                try:
                    await page.goto(str(video.video_url), wait_until="domcontentloaded", timeout=60_000)
                    await page.wait_for_timeout(wait_ms)
                    html = await page.content()
                    try:
                        body_text = await page.locator("body").inner_text(timeout=3_000)
                    except Exception:
                        body_text = ""
                    if body_text:
                        html = html + "\n" + body_text
                except Exception:
                    continue

                metrics = _extract_video_page_metrics(html)

                if int(video.views or 0) <= 0:
                    video.views = max(int(video.views or 0), int(metrics.get("views") or 0))
                if int(video.likes or 0) <= 0:
                    video.likes = max(int(video.likes or 0), int(metrics.get("likes") or 0))
                if int(video.comments or 0) <= 0:
                    video.comments = max(int(video.comments or 0), int(metrics.get("comments") or 0))
                if video.published_at is None and metrics.get("published_at") is not None:
                    video.published_at = metrics.get("published_at")
                if video.duration_seconds is None and metrics.get("duration_seconds") is not None:
                    video.duration_seconds = int(metrics.get("duration_seconds") or 0) or None

                title = str(metrics.get("title") or "").strip()
                if title:
                    current = (video.title or "").strip().lower()
                    if not current or current in {"vk post", "ok video", "rutube video", "likee video", "dzen post", "instagram post", "tiktok post"} or current.endswith(" video"):
                        video.title = title[:500]

            await context.close()
            await browser.close()
    except Exception:
        return


async def _enrich_videos_from_pages_external(
    videos: list[ContentFactoryVideoPayload],
    *,
    network: str,
    max_videos: int = 20,
    country: Optional[str] = None,
) -> None:
    """
    Enrich video metrics through managed anti-bot providers.

    Uses _external_fetch_html (Smartproxy/Scrapfly/ScrapingBee/ZenRows) and is
    intended as the last-mile recovery pass for anti-bot heavy networks.
    """
    if not videos:
        return

    targets = videos[:max_videos]
    for video in targets:
        # Skip records that already look complete enough.
        if (
            int(video.views or 0) > 0
            and int(video.likes or 0) > 0
            and int(video.comments or 0) > 0
            and video.published_at is not None
            and video.duration_seconds is not None
        ):
            continue

        html, provider = await _external_fetch_html(
            str(video.video_url),
            render_js=True,
            country=country,
            network=network,
        )
        if not html or _detect_antibot_page(html):
            continue

        metrics = _extract_video_page_metrics(html)
        if int(video.views or 0) <= 0:
            video.views = max(int(video.views or 0), int(metrics.get("views") or 0))
        if int(video.likes or 0) <= 0:
            video.likes = max(int(video.likes or 0), int(metrics.get("likes") or 0))
        if int(video.comments or 0) <= 0:
            video.comments = max(int(video.comments or 0), int(metrics.get("comments") or 0))
        if video.published_at is None and metrics.get("published_at") is not None:
            video.published_at = metrics.get("published_at")
        if video.duration_seconds is None and metrics.get("duration_seconds") is not None:
            video.duration_seconds = int(metrics.get("duration_seconds") or 0) or None

        title = str(metrics.get("title") or "").strip()
        if title:
            current = (video.title or "").strip().lower()
            if not current or current in {"vk post", "ok video", "rutube video", "likee video", "dzen post", "instagram post", "tiktok post"} or current.endswith(" video"):
                video.title = title[:500]

        if provider:
            extra = dict(video.extra or {})
            extra["external_enrichment_provider"] = provider
            video.extra = extra


def _video_coverage(videos: list[ContentFactoryVideoPayload]) -> dict[str, int]:
    total = len(videos)
    if total <= 0:
        return {
            "title": 0,
            "published_at": 0,
            "views": 0,
            "likes": 0,
            "comments": 0,
        }

    def percent(filled: int) -> int:
        return max(0, min(100, int(round((filled / total) * 100))))

    return {
        "title": percent(sum(1 for video in videos if str(video.title or "").strip() and str(video.title or "").strip().lower() not in {"vk post", "ok video", "rutube video", "likee video", "dzen post", "instagram post", "tiktok post"} and not str(video.title or "").strip().lower().endswith(" video"))),
        "published_at": percent(sum(1 for video in videos if video.published_at is not None)),
        "views": percent(sum(1 for video in videos if int(video.views or 0) > 0)),
        "likes": percent(sum(1 for video in videos if int(video.likes or 0) > 0)),
        "comments": percent(sum(1 for video in videos if int(video.comments or 0) > 0)),
    }


def _recovery_headers_for_network(network: str) -> dict[str, str]:
    return _headers_for_network(network)


def _needs_video_link_recovery(network: str, videos: list[ContentFactoryVideoPayload]) -> bool:
    if not videos:
        return False

    coverage = _video_coverage(videos)
    thresholds = {
        "youtube": {"title": 95, "published_at": 95, "views": 95, "likes": 70, "comments": 70},
        "instagram": {"title": 80, "published_at": 70, "views": 80, "likes": 60, "comments": 60},
        "tiktok": {"title": 80, "published_at": 70, "views": 80, "likes": 60, "comments": 60},
        "vk": {"title": 60, "published_at": 40, "views": 60, "likes": 50, "comments": 50},
        "ok": {"title": 60, "published_at": 40, "views": 60, "likes": 50, "comments": 50},
        "rutube": {"title": 60, "published_at": 40, "views": 60, "likes": 50, "comments": 50},
        "likee": {"title": 60, "published_at": 40, "views": 60, "likes": 50, "comments": 50},
        "dzen": {"title": 60, "published_at": 40, "views": 60, "likes": 50, "comments": 50},
    }
    required = thresholds.get(network, {"title": 60, "published_at": 50, "views": 70, "likes": 50, "comments": 50})

    return any(coverage.get(metric, 0) < threshold for metric, threshold in required.items())


def _should_expand_channel_video_set(network: str, videos: list[ContentFactoryVideoPayload]) -> bool:
    # Rutube channel pages often include recommendation blocks from other channels.
    # Keep discovery opt-in there to avoid pulling unrelated videos.
    if network == "rutube":
        return _feature_enabled("CONTENT_FACTORY_RUTUBE_CHANNEL_DISCOVERY_ENABLED", "0")

    minimum_count_by_network = {
        "instagram": 5,
        "tiktok": 5,
        "vk": 4,
        "ok": 4,
        "rutube": 4,
        "likee": 4,
        "dzen": 4,
    }
    thresholds_by_network = {
        "instagram": {"views": 60, "published_at": 50},
        "tiktok": {"views": 60, "published_at": 50},
        "vk": {"views": 50, "published_at": 40},
        "ok": {"views": 50, "published_at": 40},
        "rutube": {"views": 50, "published_at": 40},
        "likee": {"views": 50, "published_at": 40},
        "dzen": {"views": 50, "published_at": 40},
    }

    if network not in minimum_count_by_network:
        return False
    if len(videos) < minimum_count_by_network[network]:
        return True

    coverage = _video_coverage(videos)
    thresholds = thresholds_by_network[network]
    return any(coverage.get(metric, 0) < threshold for metric, threshold in thresholds.items())


def _channel_discovery_urls(network: str, channel_url: str) -> list[str]:
    candidates = [channel_url]

    if network == "vk":
        if "vkvideo.ru" in channel_url:
            candidates.append(channel_url.replace("https://vkvideo.ru", "https://vk.com"))
        elif "vk.com" in channel_url:
            candidates.append(channel_url.replace("https://vk.com", "https://vkvideo.ru"))
    elif network == "ok":
        candidates.append(f"{channel_url.rstrip('/')}/video")
    elif network == "rutube":
        if "rutube.ru" in channel_url and "www.rutube.ru" not in channel_url:
            candidates.append(channel_url.replace("https://rutube.ru", "https://www.rutube.ru"))
        elif "www.rutube.ru" in channel_url:
            candidates.append(channel_url.replace("https://www.rutube.ru", "https://rutube.ru"))

    return list(dict.fromkeys(url for url in candidates if url))


async def _discover_channel_video_links(network: str, channel_url: str) -> list[ContentFactoryVideoPayload]:
    default_limits: dict[str, int] = {
        "instagram": 120,
        "tiktok": 120,
        "vk": 100,
        "ok": 100,
        "rutube": 100,
        "likee": 100,
        "dzen": 120,
    }
    max_links = _secret_int(
        f"CONTENT_FACTORY_{network.upper()}_DISCOVERY_MAX_LINKS",
        default_limits.get(network, 80),
        min_value=10,
        max_value=1000,
    )

    configs: dict[str, dict[str, Any]] = {
        "instagram": {
            "selectors": ["a[href*='/reel/']", "a[href*='/p/']"],
            "include_pattern": r"instagram\.com/(?:reel|p)/",
            "max_links": max_links,
            "title": "Instagram post",
            "extra": {"network": "instagram"},
            "validator": _is_valid_instagram_video_url,
        },
        "tiktok": {
            "selectors": ["a[href*='/video/']"],
            "include_pattern": r"tiktok\.com/.*/video/",
            "max_links": max_links,
            "title": "TikTok post",
            "extra": {"network": "tiktok", "is_short": True},
            "validator": _is_valid_tiktok_video_url,
        },
        "vk": {
            "selectors": ["a[href*='/video']", "a[href*='/clip']"],
            "include_pattern": r"(?:vk\.com|vkvideo\.ru)/(?:video-?\d+_\d+|clip-?\d+_\d+)",
            "max_links": max_links,
            "title": "VK video",
            "extra": {"network": "vk"},
        },
        "ok": {
            "selectors": ["a[href*='/video/']"],
            "include_pattern": r"ok\.ru/video/",
            "max_links": max_links,
            "title": "OK video",
            "extra": {"network": "ok"},
            "validator": _is_valid_ok_video_url,
        },
        "rutube": {
            "selectors": ["a[href*='/video/']", "a[href*='/shorts/']"],
            "include_pattern": r"rutube\.ru/(?:video|shorts)/[0-9a-f]{32}",
            "max_links": max_links,
            "title": "Rutube video",
            "extra": {"network": "rutube"},
            "validator": _is_valid_rutube_video_url,
        },
        "likee": {
            "selectors": ["a[href*='/video/']", "a[href*='likee.video']"],
            "include_pattern": r"likee\.video/.*/video/|likee\.video/video/",
            "max_links": max_links,
            "title": "Likee video",
            "extra": {"network": "likee", "is_short": True},
            "validator": _is_valid_likee_video_url,
        },
        "dzen": {
            "selectors": [
                "a[href*='/video/watch/']",
                "a[href*='dzen.ru/video/watch/']",
                "a[href*='/short-video/']",
                "a[href*='dzen.ru/short-video/']",
            ],
            "include_pattern": r"dzen\.ru/(?:video/watch|short-video)/",
            "max_links": max_links,
            "title": "Dzen post",
            "extra": {"network": "dzen"},
        },
    }

    config = configs.get(network)
    if not config:
        return []

    links: list[str] = []
    for page_url in _channel_discovery_urls(network, channel_url):
        discovered_links = await _collect_links_via_browser(
            page_url=page_url,
            selectors=config["selectors"],
            include_pattern=config["include_pattern"],
            max_links=config["max_links"],
        )
        links.extend(discovered_links)

    validator = config.get("validator")
    unique_links: list[str] = []
    seen_links: set[str] = set()
    for link in links:
        normalized_link = _canonical_video_url(network, str(link or "").strip())
        if not normalized_link or normalized_link in seen_links:
            continue
        if validator and not validator(normalized_link):
            continue
        seen_links.add(normalized_link)
        unique_links.append(normalized_link)

    return [
        ContentFactoryVideoPayload(
            video_external_id=str(_extract_handle_from_url(link) or link),
            video_url=link,
            title=config["title"],
            published_at=None,
            views=0,
            likes=0,
            comments=0,
            extra={
                "source": "browser_discovery",
                "discovery_source": "channel_page",
                **dict(config.get("extra") or {}),
            },
        )
        for link in unique_links
    ]


def _merge_discovered_videos(
    current_videos: list[ContentFactoryVideoPayload],
    discovered_videos: list[ContentFactoryVideoPayload],
    *,
    network: str,
) -> tuple[list[ContentFactoryVideoPayload], bool]:
    def _key(url: str) -> str:
        return _canonical_video_url(network, str(url or "").strip())

    merged_by_url: dict[str, ContentFactoryVideoPayload] = {}
    for video in current_videos:
        key = _key(str(video.video_url or ""))
        if key:
            merged_by_url[key] = video

    changed = False
    for video in discovered_videos:
        key = _key(str(video.video_url or ""))
        if not key:
            continue
        if key in merged_by_url:
            existing = merged_by_url[key]
            extra = dict(existing.extra or {})
            extra.setdefault("discovery_source", "channel_page")
            existing.extra = extra
            continue
        merged_by_url[key] = video
        changed = True

    return list(merged_by_url.values()), changed


def _mark_recovered_video_fields(
    video: ContentFactoryVideoPayload,
    *,
    before: dict[str, Any],
    network: str,
) -> None:
    recovered_fields: list[str] = []
    before_title = str(before.get("title") or "").strip().lower()
    after_title = str(video.title or "").strip()
    if (not before_title or before_title.endswith(" video") or before_title in {"vk post", "ok video", "rutube video", "likee video", "dzen post", "instagram post", "tiktok post"}) and after_title:
        recovered_fields.append("title")
    if before.get("published_at") is None and video.published_at is not None:
        recovered_fields.append("published_at")
    if int(before.get("views") or 0) <= 0 and int(video.views or 0) > 0:
        recovered_fields.append("views")
    if int(before.get("likes") or 0) <= 0 and int(video.likes or 0) > 0:
        recovered_fields.append("likes")
    if int(before.get("comments") or 0) <= 0 and int(video.comments or 0) > 0:
        recovered_fields.append("comments")
    if before.get("duration_seconds") is None and video.duration_seconds is not None:
        recovered_fields.append("duration_seconds")

    if not recovered_fields:
        return

    extra = dict(video.extra or {})
    current_fields = extra.get("recovered_fields")
    merged_fields = set(current_fields or [])
    merged_fields.update(recovered_fields)
    extra["recovered_fields"] = sorted(merged_fields)
    extra["recovery_source"] = "video_page"
    extra["recovery_network"] = network
    extra["recovery_applied"] = True
    video.extra = extra


async def _recover_missing_video_metrics(
    network: str,
    videos: list[ContentFactoryVideoPayload],
) -> tuple[list[ContentFactoryVideoPayload], bool]:
    if not videos:
        return videos, False

    if not _needs_video_link_recovery(network, videos):
        return videos, False

    before_state = {
        str(video.video_url): {
            "title": str(video.title or "").strip(),
            "published_at": video.published_at,
            "views": int(video.views or 0),
            "likes": int(video.likes or 0),
            "comments": int(video.comments or 0),
            "duration_seconds": video.duration_seconds,
        }
        for video in videos
        if video.video_url
    }

    # Dzen requires SSO-authenticated session; plain aiohttp gets a redirect wall.
    # Enrichment was already done by _dzen_enrich_sync in parse_dzen_http, skip here.
    if network != "dzen":
        await _enrich_videos_from_pages(
            videos,
            headers=_recovery_headers_for_network(network),
            max_videos=min(max(len(videos), 1), 120),
            concurrency=6,
        )

    # SPA-heavy networks often hide metrics from plain HTTP HTML.
    # Run a second browser-rendered pass only for partially recovered records.
    if network in {"instagram", "tiktok", "vk", "ok", "likee"}:
        unresolved = [
            video
            for video in videos
            if int(video.views or 0) <= 0
            or int(video.likes or 0) <= 0
            or int(video.comments or 0) <= 0
            or video.published_at is None
        ]
        if unresolved:
            await _enrich_videos_from_pages_browser(
                unresolved,
                max_videos=min(len(unresolved), 24),
                wait_ms=2500,
            )

    # Final paid/unlocker pass for the most anti-bot-sensitive networks.
    if network in {"ok", "likee"}:
        unresolved_after_browser = [
            video
            for video in videos
            if int(video.views or 0) <= 0
            or int(video.likes or 0) <= 0
            or int(video.comments or 0) <= 0
            or video.published_at is None
        ]
        if unresolved_after_browser:
            await _enrich_videos_from_pages_external(
                unresolved_after_browser,
                network=network,
                max_videos=min(len(unresolved_after_browser), 16),
                country="ru" if network == "ok" else None,
            )

    changed = False
    for video in videos:
        snapshot = before_state.get(str(video.video_url))
        if not snapshot:
            continue
        before_extra = dict(video.extra or {})
        _mark_recovered_video_fields(video, before=snapshot, network=network)
        if dict(video.extra or {}) != before_extra:
            changed = True

    return videos, changed


def _ensure_minimum_video_completeness(
    network: str,
    videos: list[ContentFactoryVideoPayload],
) -> tuple[list[ContentFactoryVideoPayload], bool]:
    if not videos:
        return videos, False

    changed = False
    now_utc = datetime.now(timezone.utc)

    for video in videos:
        synthetic_fields: list[str] = []

        if not str(video.title or "").strip():
            video.title = f"{network.title()} video"
            synthetic_fields.append("title")

        if video.published_at is None:
            video.published_at = now_utc
            synthetic_fields.append("published_at")

        if not str(video.video_external_id or "").strip():
            fallback_external_id = str(_extract_handle_from_url(str(video.video_url or "")) or str(video.video_url or "")).strip()
            if fallback_external_id:
                video.video_external_id = fallback_external_id[:255]
                synthetic_fields.append("video_external_id")

        try:
            views_value = int(video.views or 0)
        except Exception:
            views_value = 0
        if views_value < 0:
            views_value = 0
        if views_value != int(video.views or 0):
            synthetic_fields.append("views")
        video.views = views_value

        try:
            likes_value = int(video.likes or 0)
        except Exception:
            likes_value = 0
        if likes_value < 0:
            likes_value = 0
        if likes_value != int(video.likes or 0):
            synthetic_fields.append("likes")
        video.likes = likes_value

        try:
            comments_value = int(video.comments or 0)
        except Exception:
            comments_value = 0
        if comments_value < 0:
            comments_value = 0
        if comments_value != int(video.comments or 0):
            synthetic_fields.append("comments")
        video.comments = comments_value

        if video.duration_seconds is not None and int(video.duration_seconds or 0) <= 0:
            video.duration_seconds = None
            synthetic_fields.append("duration_seconds")

        if synthetic_fields:
            extra = dict(video.extra or {})
            existing = extra.get("synthetic_fields")
            existing_fields = set(existing if isinstance(existing, list) else [])
            existing_fields.update(synthetic_fields)
            extra["synthetic_fields"] = sorted(str(item) for item in existing_fields if str(item).strip())
            extra["synthetic_source"] = "hard_completeness_fallback"
            extra["synthetic_applied"] = True
            video.extra = extra
            changed = True

    return videos, changed


async def _collect_links_via_browser(
    *,
    page_url: str,
    selectors: list[str],
    include_pattern: str,
    max_links: int = 60,
) -> list[str]:
    browser_enabled = _secret("CONTENT_FACTORY_BROWSER_FALLBACK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not browser_enabled:
        return []

    try:
        from playwright.async_api import async_playwright
    except Exception:
        return []

    links: list[str] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(page_url, wait_until="domcontentloaded", timeout=90_000)

            # Warm up lazy lists in JS-heavy pages before collecting anchors.
            try:
                await page.wait_for_timeout(900)
                await page.mouse.wheel(0, 1800)
                await page.wait_for_timeout(600)
                await page.mouse.wheel(0, 1800)
                await page.wait_for_timeout(600)
            except Exception:
                pass

            entries = await page.evaluate(
                r"""
                ({ selectors, includePattern, maxLinks }) => {
                    const rx = new RegExp(includePattern, 'i');
                    const found = new Map();
                    for (const selector of selectors) {
                        const nodes = Array.from(document.querySelectorAll(selector));
                        for (const node of nodes) {
                            const rawHref = (node.getAttribute('href') || '').trim();
                            if (!rawHref) continue;
                            const href = rawHref.startsWith('http')
                                ? rawHref
                                : new URL(rawHref, window.location.origin).toString();
                            if (!rx.test(href)) continue;
                            if (!found.has(href)) found.set(href, true);
                            if (found.size >= maxLinks) break;
                        }
                        if (found.size >= maxLinks) break;
                    }
                    return Array.from(found.keys());
                }
                """,
                {
                    "selectors": selectors,
                    "includePattern": include_pattern,
                    "maxLinks": max_links,
                },
            )

            links = [str(item).strip() for item in (entries or []) if str(item).strip()]
            await context.close()
            await browser.close()
    except Exception:
        return []

    return links


def _normalize_instagram_video_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip()
    if "instagram.com" not in host or not path:
        return ""
    match = re.match(r"^/(reel|p)/([A-Za-z0-9_-]+)", path, flags=re.IGNORECASE)
    if not match:
        return ""
    kind, code = match.groups()
    return f"https://www.instagram.com/{kind.lower()}/{code}/"


def _is_valid_instagram_video_url(url: str) -> bool:
    return bool(_normalize_instagram_video_url(url))


def _instagram_short_format(item_url: str, item_kind: str, is_vertical: Optional[bool]) -> Optional[str]:
    url = str(item_url or "").lower()
    kind = str(item_kind or "").lower()

    if "/reel/" in url:
        return "reel"
    if any(token in kind for token in ("reel", "clips", "clip")):
        return "reel"
    if "/p/" in url and is_vertical is False:
        return "video"
    return None


def _normalize_tiktok_video_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip()
    if "tiktok.com" not in host or not path:
        return ""
    match = re.match(r"^/(@[^/]+)/video/(\d+)", path, flags=re.IGNORECASE)
    if not match:
        return ""
    handle, video_id = match.groups()
    return f"https://www.tiktok.com/{handle}/video/{video_id}"


def _is_valid_tiktok_video_url(url: str) -> bool:
    return bool(_normalize_tiktok_video_url(url))


def _is_rutube_short_url(url: str) -> bool:
    return bool(re.match(r"^https?://(?:www\.)?rutube\.ru/shorts/[0-9a-f]{32}/?(?:\?.*)?$", str(url or ""), flags=re.IGNORECASE))


def _is_rutube_short_video(url: str, duration_seconds: Optional[int] = None) -> bool:
    if _is_rutube_short_url(url):
        return True
    duration_value = _as_int(duration_seconds, default=0)
    return bool(duration_value and duration_value <= 180)


def _canonical_video_url(network: str, url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if network == "instagram":
        return _normalize_instagram_video_url(raw)
    if network == "tiktok":
        return _normalize_tiktok_video_url(raw)
    if network == "dzen":
        return _clean_dzen_video_url(raw)
    if network in {"rutube", "ok", "likee"}:
        return raw.split("?", 1)[0].split("#", 1)[0].strip()
    return raw


def _is_valid_rutube_video_url(url: str) -> bool:
    value = str(url or "")
    return bool(
        re.match(r"^https?://(?:www\.)?rutube\.ru/video/[0-9a-f]{32}/?(?:\?.*)?$", value, flags=re.IGNORECASE)
        or _is_rutube_short_url(value)
    )



def _extract_vk_owner_id(channel_url: str) -> Optional[str]:
    """Extract numeric club/group ID from a vkvideo.ru or vk.com channel URL."""
    for pattern in (r"club(\d+)", r"public(\d+)", r"group(\d+)"):
        m = re.search(pattern, channel_url, re.IGNORECASE)
        if m:
            return m.group(1)
    # Handle @clubNNNNN or @NNNNN handle style (vkvideo.ru/@club237523032)
    m = re.search(r"@club(\d+)", channel_url, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"/@(\d+)$", channel_url, re.IGNORECASE)
    if m:
        return m.group(1)
    return None



async def _extract_vk_clip_ids_via_browser(channel_url: str, owner_id: str) -> list[str]:
    """Render a VK Video channel page with Playwright and reconstruct clip URLs.

    vkvideo.ru is a full SPA — clip IDs only appear in the browser-rendered DOM.
    Raw HTTP gives a React shell with no video data.

    Returns a list of ``https://vkvideo.ru/clip-{owner_id}_{video_id}`` strings.
    Falls back to ``[]`` when the browser feature is disabled or unavailable.
    """
    browser_enabled = _secret(
        "CONTENT_FACTORY_BROWSER_FALLBACK_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    if not browser_enabled:
        return []
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return []

    proxy_chain = _proxy_attempt_chain("CONTENT_FACTORY_VK_PROXY_URL", include_direct=True)
    for vk_proxy in proxy_chain:
        try:
            async with async_playwright() as pw:
                _launch_kwargs: dict[str, Any] = {"headless": True}
                if vk_proxy:
                    _launch_kwargs["proxy"] = {"server": vk_proxy}

                br = await pw.chromium.launch(**_launch_kwargs)
                ctx = await br.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    )
                )
                pg = await ctx.new_page()

                candidate_urls = [channel_url, f"{channel_url.rstrip('/')}/videos"]
                html_chunks: list[str] = []
                discovered_links: list[str] = []
                for request_url in dict.fromkeys(candidate_urls):
                    try:
                        await pg.goto(request_url, wait_until="domcontentloaded", timeout=35_000)
                        await asyncio.sleep(1.2)
                        try:
                            await pg.mouse.wheel(0, 2400)
                            await asyncio.sleep(0.7)
                            await pg.mouse.wheel(0, 2400)
                            await asyncio.sleep(0.7)
                        except Exception:
                            pass
                        html_chunks.append(await pg.content())
                        dom_links = await pg.evaluate(
                            r"""
                            () => Array.from(document.querySelectorAll('a[href*="/clip-"],a[href*="/video-"]'))
                                .map((a) => (a.getAttribute('href') || '').trim())
                                .filter(Boolean)
                            """
                        )
                        if isinstance(dom_links, list):
                            discovered_links.extend(str(item).strip() for item in dom_links if str(item).strip())
                    except Exception:
                        continue

                html = "\n".join(chunk for chunk in html_chunks if chunk)
                await ctx.close()
                await br.close()

            video_urls: list[str] = []

            explicit_clip_urls = list(
                dict.fromkeys(
                    m.group(0)
                    for m in re.finditer(r"https?://(?:www\.)?vkvideo\.ru/clip-\d+_\d+", html, flags=re.IGNORECASE)
                )
            )

            for raw_link in discovered_links:
                normalized = raw_link
                if normalized.startswith("/"):
                    normalized = f"https://vkvideo.ru{normalized}"
                elif normalized.startswith("clip-"):
                    normalized = f"https://vkvideo.ru/{normalized}"
                if re.match(r"^https?://(?:www\.)?vkvideo\.ru/clip-\d+_\d+$", normalized, flags=re.IGNORECASE):
                    explicit_clip_urls.append(normalized)

            explicit_clip_urls = list(dict.fromkeys(explicit_clip_urls))[:40]
            if explicit_clip_urls:
                video_urls = explicit_clip_urls
            else:
                sparse_clip_ids = list(
                    dict.fromkeys(
                        m.group(0)
                        for m in re.finditer(r"clip-\d+_\d+", html, flags=re.IGNORECASE)
                    )
                )[:40]
                if sparse_clip_ids:
                    video_urls = [f"https://vkvideo.ru/{clip_id}" for clip_id in sparse_clip_ids]

                if not video_urls:
                    raw_ids = list(
                        dict.fromkeys(
                            m.group(1)
                            for m in re.finditer(r"clip\d*_(\d{3,})", html)
                        )
                    )[:40]
                    video_urls = [f"https://vkvideo.ru/clip-{owner_id}_{vid}" for vid in raw_ids]

            if video_urls:
                return video_urls
        except Exception:
            continue

    return []

async def _extract_ok_video_ids_via_browser(channel_url: str) -> list[str]:
    """Render an OK channel page with Playwright and extract video IDs from JS state.

    OK is a full SPA — individual video URLs are not in anchor hrefs but embedded in
    the page's JavaScript state as ``"videoId": "<numeric_id>"``.  This helper renders
    the page, waits for JS to settle, then scrapes those IDs.

    Returns a list of ``https://ok.ru/video/<id>`` strings.
    Falls back to ``[]`` when the browser feature is disabled or unavailable.
    """
    browser_enabled = _secret(
        "CONTENT_FACTORY_BROWSER_FALLBACK_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    if not browser_enabled:
        return []
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return []

    video_urls: list[str] = []
    try:
        async with async_playwright() as pw:
            br = await pw.chromium.launch(headless=True)
            ctx = await br.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            )
            pg = await ctx.new_page()
            html_parts: list[str] = []
            request_urls = [channel_url, f"{channel_url.rstrip('/')}/video"]
            for request_url in dict.fromkeys(request_urls):
                try:
                    await pg.goto(request_url, wait_until="domcontentloaded", timeout=60_000)
                    await asyncio.sleep(3.0)
                    html_parts.append(await pg.content())
                except Exception:
                    continue

            html = "\n".join(part for part in html_parts if part)
            await ctx.close()
            await br.close()

        # Extract numeric video IDs from embedded JS state
        ids = list(
            dict.fromkeys(
                re.findall(r'"(?:videoId|vid)"\s*:\s*"?(\d{8,})"?', html)
            )
        )
        video_urls = [f"https://ok.ru/video/{vid}" for vid in ids]
    except Exception:
        pass

    return video_urls

def _is_valid_ok_video_url(url: str) -> bool:
    # Keep only direct video IDs and drop common non-video placeholders.
    m = re.match(r"^https?://(?:www\.)?ok\.ru/video/([^/?#]+)/?(?:\?.*)?$", url, flags=re.IGNORECASE)
    if not m:
        return False
    token = m.group(1).strip().lower()
    if not token or token == "all":
        return False
    if token.startswith("holder_") or "videocard" in token or "alert" in token:
        return False
    if token.startswith("c") and token[1:].isdigit() and len(token) >= 6:
        return True
    return token.isdigit() and len(token) >= 8


def _is_valid_likee_video_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if "likee.video" not in host:
        return False
    if path in {"", "/", "/m_index"}:
        return False
    return "/video/" in path or path.startswith("/v/")


async def _likee_guest_headers(session: aiohttp.ClientSession, *, proxy: Optional[str] = None) -> dict[str, str]:
    """Build best-effort guest headers required by Likee web APIs."""
    base_headers: dict[str, str] = {}
    device_id = f"web{uuid.uuid4().hex}"
    endpoint = "https://api.like-video.com/likee-activity-flow-micro/user/getGuestInfoForPC"
    payload = {"requestJSON": True, "deviceId": device_id}

    try:
        async with session.post(endpoint, json=payload, proxy=proxy) as response:
            if response.status >= 400:
                return base_headers
            body = await response.json(content_type=None)
    except Exception:
        return base_headers

    if not isinstance(body, dict):
        return base_headers

    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    uid = str(data.get("uid") or "").strip()
    cookie = str(data.get("cookie") or "").strip()
    resolved_device = str(data.get("deviceId") or device_id).strip() or device_id

    if uid:
        base_headers["X-Uid"] = uid
    if resolved_device:
        base_headers["X-Client-DeviceId"] = resolved_device
    base_headers["X-Channel"] = "guest"
    if cookie:
        base_headers["Cookie"] = cookie

    return base_headers


async def _likee_api_call(
    session: aiohttp.ClientSession,
    endpoint: str,
    payload: dict[str, Any],
    *,
    extra_headers: Optional[dict[str, str]] = None,
    proxy: Optional[str] = None,
) -> dict[str, Any]:
    url = f"https://api.like-video.com/likee-activity-flow-micro/{endpoint.lstrip('/')}"
    headers = dict(extra_headers or {})
    data = {"requestJSON": True, **dict(payload or {})}
    try:
        async with session.post(url, json=data, headers=headers, proxy=proxy) as response:
            if response.status >= 400:
                return {}
            parsed = await response.json(content_type=None)
            return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _likee_extract_uid_from_profile_html(html: str) -> Optional[str]:
    """
    Best-effort uid extraction from Likee profile/video pages.
    Inspired by LikeeScraper's Selenium flow, but without browser dependency.
    """
    if not html:
        return None

    patterns = (
        r"window\.data\s*=\s*(\{.*?\});",
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.DOTALL):
            try:
                blob = match.group(1)
                data = json.loads(blob)
                uid = str(
                    _pick_first(data, ("poster_uid", "uid", "userId", "postUserId"))
                    or _pick_first_path(data, (
                        "userinfo.uid",
                        "user.uid",
                        "poster.uid",
                        "author.uid",
                    ))
                    or ""
                ).strip()
                if uid.isdigit():
                    return uid
            except Exception:
                continue

    raw_patterns = (
        r'"poster_uid"\s*:\s*"?(\d{6,})"?',
        r'"uid"\s*:\s*"?(\d{6,})"?',
        r'"userId"\s*:\s*"?(\d{6,})"?',
    )
    for pattern in raw_patterns:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None


async def _likee_fetch_profile_html(
    session: aiohttp.ClientSession,
    channel_url: str,
    *,
    proxy: Optional[str] = None,
) -> Optional[str]:
    try:
        async with session.get(channel_url, proxy=proxy) as response:
            if response.status >= 400:
                return None
            body = await response.text()
            return body or None
    except Exception:
        return None


async def _likee_fetch_videos_via_legacy_payload(
    session: aiohttp.ClientSession,
    *,
    uid: str,
    extra_headers: Optional[dict[str, str]] = None,
    proxy: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Repo-inspired fallback for Likee's getUserVideo endpoint.
    Uses the older payload shape observed in LikeeScraper.
    """
    response = await _likee_api_call(
        session,
        "videoApi/getUserVideo",
        {
            "country": "US",
            "count": 100,
            "page": 1,
            "pageSize": 28,
            "lastPostId": "",
            "tabType": 0,
            "uid": uid,
        },
        extra_headers=extra_headers,
        proxy=proxy,
    )
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return data.get("videoList") if isinstance(data.get("videoList"), list) else []


def _likee_parse_video_item(
    item: dict[str, Any],
    *,
    fallback_likee_id: Optional[str],
) -> Optional[ContentFactoryVideoPayload]:
    if not isinstance(item, dict):
        return None

    post_id = str(_pick_first(item, ("postId", "id", "videoId", "vid")) or "").strip()
    likee_id = str(_pick_first(item, ("likeeId", "profileId", "userName", "user_name")) or fallback_likee_id or "").strip("@")

    video_url = str(
        _pick_first(item, ("videoUrl", "shareUrl", "url", "webUrl", "postUrl"))
        or _pick_first_path(item, ("share.url", "video.url", "video.shareUrl"))
        or ""
    ).strip()
    if not video_url and post_id:
        if likee_id:
            video_url = f"https://likee.video/@{likee_id}/video/{post_id}"
        else:
            video_url = f"https://likee.video/video/{post_id}"

    if not video_url or not _is_valid_likee_video_url(video_url):
        return None

    published_at = _parse_any_datetime(
        _pick_first(item, ("postTime", "createdAt", "createTime", "timestamp", "publishedAt", "time"))
        or _pick_first_path(item, ("video.postTime", "video.createTime", "post.timestamp"))
    )

    title = str(_pick_first(item, ("title", "caption", "text", "desc", "msgText")) or "Likee video").strip() or "Likee video"

    return ContentFactoryVideoPayload(
        video_external_id=str(post_id or _extract_handle_from_url(video_url) or video_url),
        video_url=video_url,
        title=title[:500],
        published_at=published_at,
        views=_as_int(_pick_first(item, ("playCount", "viewCount", "views", "videoViews")))
        or _as_int(_pick_first_path(item, ("statistics.playCount", "stats.playCount", "video.playCount"))),
        likes=_as_int(_pick_first(item, ("likeCount", "likes", "diggCount")))
        or _as_int(_pick_first_path(item, ("statistics.likeCount", "stats.likeCount", "video.likeCount"))),
        comments=_as_int(_pick_first(item, ("commentCount", "comments")))
        or _as_int(_pick_first_path(item, ("statistics.commentCount", "stats.commentCount", "video.commentCount"))),
        shares=_as_int(_pick_first(item, ("shareCount", "shares")))
        or _as_int(_pick_first_path(item, ("statistics.shareCount", "stats.shareCount", "video.shareCount"))),
        duration_seconds=_as_int(_pick_first(item, ("duration", "videoDuration")), default=0)
        or _as_int(_pick_first_path(item, ("video.duration", "media.duration")), default=0)
        or None,
        extra={"source": "likee_internal_api", "network": "likee", "is_short": True},
    )


async def _likee_fetch_videos_via_internal_api(
    *,
    channel_url: str,
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[ContentFactoryVideoPayload], Optional[int], Optional[str], Optional[str]]:
    """Resolve profile -> uid -> user videos via Likee internal web API."""
    timeout = aiohttp.ClientTimeout(total=_timeout_seconds("CONTENT_FACTORY_LIKEE_HTTP_TIMEOUT_SECONDS", 15))
    headers = {"User-Agent": _DEFAULT_SCRAPER_HEADERS["User-Agent"], "Content-Type": "application/json"}
    proxy_chain = _proxy_attempt_chain("CONTENT_FACTORY_LIKEE_PROXY_URL", include_direct=True)
    likee_id = _extract_handle_from_url(channel_url)
    if likee_id:
        likee_id = likee_id.strip("@")
    if not likee_id:
        return [], None, None, "Не удалось извлечь likeeId из URL для internal API fallback."

    last_message: Optional[str] = None
    for likee_proxy in proxy_chain:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            guest_headers = await _likee_guest_headers(session, proxy=likee_proxy)

            profile_resp = await _likee_api_call(
                session,
                "official_website/WebView/getProfileDetail",
                {"likeeId": likee_id},
                extra_headers=guest_headers,
                proxy=likee_proxy,
            )
            if int(profile_resp.get("code", -1) if profile_resp.get("code") is not None else -1) != 0:
                last_message = f"Likee profile API error: {str(profile_resp.get('message') or '')[:160]}"
                continue

            profile_data = profile_resp.get("data") if isinstance(profile_resp.get("data"), dict) else {}
            userinfo = profile_data.get("userinfo") if isinstance(profile_data.get("userinfo"), dict) else {}

            uid = str(userinfo.get("uid") or "").strip()
            if not uid:
                # Try alternate endpoint: user/getUserInfoByName
                alt_resp = await _likee_api_call(
                    session,
                    "user/getUserInfoByName",
                    {"likeeId": likee_id, "country": ""},
                    extra_headers=guest_headers,
                    proxy=likee_proxy,
                )
                alt_data = alt_resp.get("data") if isinstance(alt_resp.get("data"), dict) else {}
                uid = str(
                    alt_data.get("uid")
                    or alt_data.get("userId")
                    or (alt_data.get("userinfo") or {}).get("uid")
                    or ""
                ).strip()
            if not uid:
                # Try getProfileDetail with userName instead of likeeId
                alt2_resp = await _likee_api_call(
                    session,
                    "official_website/WebView/getProfileDetail",
                    {"userName": likee_id},
                    extra_headers=guest_headers,
                    proxy=likee_proxy,
                )
                alt2_data = alt2_resp.get("data") if isinstance(alt2_resp.get("data"), dict) else {}
                alt2_user = alt2_data.get("userinfo") if isinstance(alt2_data.get("userinfo"), dict) else {}
                uid = str(alt2_user.get("uid") or "").strip()
                if uid and not userinfo:
                    userinfo = alt2_user
            if not uid:
                profile_html = await _likee_fetch_profile_html(session, channel_url, proxy=likee_proxy)
                uid = str(_likee_extract_uid_from_profile_html(profile_html or "") or "").strip()
            if not uid:
                last_message = "Likee profile API не вернул uid пользователя."
                continue

            if not userinfo:
                legacy_userinfo_resp = await _likee_api_call(
                    session,
                    "userApi/getUserInfo",
                    {"uid": uid},
                    extra_headers=guest_headers,
                    proxy=likee_proxy,
                )
                legacy_userinfo = legacy_userinfo_resp.get("data") if isinstance(legacy_userinfo_resp.get("data"), dict) else {}
                if legacy_userinfo:
                    userinfo = legacy_userinfo

            subscribers_count = _as_int(
                userinfo.get("fansCount") or userinfo.get("followers") or userinfo.get("followedCount"),
                default=0,
            ) or None
            channel_title = str(
                userinfo.get("nick_name")
                or userinfo.get("user_name")
                or userinfo.get("userName")
                or userinfo.get("nickname")
                or ""
            ).strip() or None

            videos_resp = await _likee_api_call(
                session,
                "videoApi/getUserVideo",
                {"uid": uid, "tabType": 0, "count": 200, "startNum": 0},
                extra_headers=guest_headers,
                proxy=likee_proxy,
            )
            if int(videos_resp.get("code", -1) if videos_resp.get("code") is not None else -1) != 0:
                last_message = f"Likee userVideo API error: {str(videos_resp.get('message') or '')[:160]}"
                continue

            videos_data = videos_resp.get("data") if isinstance(videos_resp.get("data"), dict) else {}
            raw_videos = videos_data.get("videoList") if isinstance(videos_data.get("videoList"), list) else []

            if not raw_videos:
                raw_videos = await _likee_fetch_videos_via_legacy_payload(
                    session,
                    uid=uid,
                    extra_headers=guest_headers,
                    proxy=likee_proxy,
                )

            # If primary endpoint returned empty list, try alternate video endpoints.
            if not raw_videos:
                for alt_endpoint, alt_payload in [
                    ("videoApi/getPublishedVideo", {"uid": uid, "count": 200, "startNum": 0}),
                    ("videoApi/getUserFollowVideos", {"uid": uid, "count": 50, "startNum": 0}),
                ]:
                    alt_video_resp = await _likee_api_call(
                        session,
                        alt_endpoint,
                        alt_payload,
                        extra_headers=guest_headers,
                        proxy=likee_proxy,
                    )
                    alt_vdata = alt_video_resp.get("data") if isinstance(alt_video_resp.get("data"), dict) else {}
                    alt_raw = alt_vdata.get("videoList") if isinstance(alt_vdata.get("videoList"), list) else []
                    if alt_raw:
                        raw_videos = alt_raw
                        break

            videos: list[ContentFactoryVideoPayload] = []
            seen_urls: set[str] = set()
            for raw in raw_videos:
                parsed = _likee_parse_video_item(raw, fallback_likee_id=likee_id)
                if not parsed:
                    continue
                if parsed.published_at and not _in_window(parsed.published_at, window_start, window_end):
                    continue
                key = str(parsed.video_url or "").strip()
                if not key or key in seen_urls:
                    continue
                seen_urls.add(key)
                videos.append(parsed)

            if not videos:
                last_message = "Likee internal API вернул пустой videoList."
                continue
            return videos, subscribers_count, channel_title, None

    return [], None, None, (last_message or "Likee internal API не дал данных через текущие прокси.")


def _decode_json_quoted(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except Exception:
        return raw


def _detect_antibot_page(html: str, title: Optional[str] = None) -> Optional[str]:
    """Best-effort anti-bot/CAPTCHA page detector for social pages."""
    blob = f"{title or ''}\n{html or ''}".lower()
    signs = (
        "captcha",
        "recaptcha",
        "robot check",
        "verify you are human",
        "cloudflare",
        "access denied",
        "большие запросы",
        "много запросов",
        "слишком много запросов",
        "не робот",
        "проверка безопасности",
    )
    for sign in signs:
        if sign in blob:
            return sign
    return None


def _is_antibot_sync_message(sync_message: Optional[str]) -> bool:
    """Detect anti-bot/CAPTCHA verdict in parser sync messages."""
    msg = str(sync_message or "").lower()
    if not msg:
        return False
    signs = (
        "anti-bot",
        "captcha",
        "recaptcha",
        "robot check",
        "cloudflare",
        "access denied",
        "не робот",
        "проверка безопасности",
        "много запросов",
        "большие запросы",
    )
    return any(sign in msg for sign in signs)


def _is_proxy_billing_error(text: str) -> bool:
    blob = str(text or "").lower()
    return "payment required" in blob or "proxyerror" in blob and "402" in blob


def _extract_rutube_embedded_candidates(html: str) -> list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]]:
    """
    Extract richer Rutube metadata from embedded page state blocks.
    Returns tuples: (url, title, published_at, views, likes, comments, duration_seconds)
    """
    results: list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]] = []
    seen: set[str] = set()

    for m in re.finditer(r'"video_url":"(https://rutube\.ru/(?:video|shorts)/[0-9a-f]{32}/)"', html, flags=re.IGNORECASE):
        url = m.group(1)
        if not _is_valid_rutube_video_url(url) or url in seen:
            continue

        start = m.start()
        left = html[max(0, start - 3500):start]
        right = html[start:min(len(html), start + 5000)]

        title_matches = re.findall(r'"title":"((?:\\.|[^"\\])*)"', left)
        title = _decode_json_quoted(title_matches[-1]) if title_matches else "Rutube video"

        created_match = re.search(r'"created_ts":"([^"]+)"', right)
        published_at = _parse_any_datetime(created_match.group(1)) if created_match else None

        hits_match = re.search(r'"hits":(\d+)', right)
        views = _as_int(hits_match.group(1), default=0) if hits_match else 0

        likes_match = re.search(r'"likes":(\d+)', right)
        likes = _as_int(likes_match.group(1), default=0) if likes_match else 0

        comments_match = re.search(r'"comments":(\d+)', right)
        comments = _as_int(comments_match.group(1), default=0) if comments_match else 0

        duration_match = re.search(r'"duration":(\d+)', right)
        duration_seconds = _as_int(duration_match.group(1), default=0) if duration_match else 0

        results.append((url, (title or "Rutube video")[:500], published_at, views, likes, comments, duration_seconds or None))
        seen.add(url)

    return results


def _parse_duration_to_seconds(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    parts = [p for p in str(raw).strip().split(":") if p.isdigit()]
    if not parts:
        return None
    try:
        nums = [int(p) for p in parts]
        if len(nums) == 3:
            return nums[0] * 3600 + nums[1] * 60 + nums[2]
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        if len(nums) == 1:
            return nums[0]
    except Exception:
        return None
    return None


def _extract_ok_video_candidates(html: str) -> list[tuple[str, str, int, int, int, Optional[int]]]:
    """
    Extract OK cards from channel /video page.
    Returns: (url, title, views, likes, comments, duration_seconds)
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str, int, int, int, Optional[int]]] = []
    seen: set[str] = set()

    for card in soup.select(".video-card"):
        anchor = card.select_one("a.video-card_lk")
        if not anchor:
            continue
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        url = href if href.startswith("http") else f"https://ok.ru{href}"
        if not _is_valid_ok_video_url(url) or url in seen:
            continue

        img = card.select_one("img[alt]")
        title = (img.get("alt") if img else "") or "OK video"

        duration_el = card.select_one(".video-card_duration")
        duration_seconds = _parse_duration_to_seconds(duration_el.get_text(strip=True) if duration_el else None)

        text_blob = " ".join(card.get_text(" ", strip=True).split())
        views = 0
        vm = re.search(r"([0-9\s]+)\s+просмотр", text_blob, flags=re.IGNORECASE)
        if vm:
            views = _as_int(vm.group(1), default=0)

        likes = 0
        lm = re.search(r"([0-9\s]+)\s+(?:класс|лайк)", text_blob, flags=re.IGNORECASE)
        if lm:
            likes = _as_int(lm.group(1), default=0)

        comments = 0
        cm = re.search(r"([0-9\s]+)\s+коммент", text_blob, flags=re.IGNORECASE)
        if cm:
            comments = _as_int(cm.group(1), default=0)

        results.append((url, title[:500], views, likes, comments, duration_seconds))
        seen.add(url)

    return results


def _clean_dzen_video_url(url: str) -> str:
    if not url:
        return url
    return url.split("?", 1)[0].strip()


def _is_dzen_short_url(url: str) -> bool:
    return "/short-video/" in str(url or "").lower()


def _dzen_tab_hint_for_position(html: str, pos: int) -> Optional[str]:
    marker_start = html.rfind("<!-- dzen_tab:", 0, max(0, pos))
    if marker_start == -1:
        return None
    marker_end = html.find("-->", marker_start)
    if marker_end == -1 or marker_end < pos:
        return None

    marker = html[marker_start:marker_end]
    if "/short-video" in marker:
        return "short-video"
    if "/video" in marker:
        return "video"
    return None


def _is_dzen_short_video(url: str, *, tab_hint: Optional[str] = None) -> bool:
    if _is_dzen_short_url(url):
        return True
    return str(tab_hint or "").strip().lower() == "short-video"


def _parse_dzen_relative_time(raw: str) -> Optional[datetime]:
    text = (raw or "").strip().lower()
    if not text:
        return None
    now = datetime.now(timezone.utc)

    # Examples: "5 месяцев назад", "2 недели назад", "3 дня назад", "7 часов назад", "30 минут назад"
    m = re.search(r"(\d+)\s+(минут|минута|минуты|час|часа|часов|день|дня|дней|недел|неделя|недели|месяц|месяца|месяцев|год|года|лет)", text)
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2)

    if unit.startswith("минут") or unit == "минута" or unit == "минуты":
        return now - timedelta(minutes=value)
    if unit.startswith("час"):
        return now - timedelta(hours=value)
    if unit.startswith("дн"):
        return now - timedelta(days=value)
    if unit.startswith("недел") or unit == "неделя" or unit == "недели":
        return now - timedelta(days=value * 7)
    if unit.startswith("месяц"):
        return now - timedelta(days=value * 30)
    if unit.startswith("год") or unit.startswith("лет"):
        return now - timedelta(days=value * 365)
    return None


def _extract_dzen_json_state_candidates(html: str) -> list[tuple[str, str, Optional[datetime], int, Optional[int], bool]]:
    """
    Extract Dzen video metadata from embedded JSON state blocks in the page HTML.
    Dzen often serialises channel data as inline JS:
      window.__initial_state__ = {...} or <script type="application/json">...</script>
    Returns tuples: (url, title, published_at, views, duration_seconds, is_short)
    """
    results: list[tuple[str, str, Optional[datetime], int, Optional[int], bool]] = []
    seen: set[str] = set()

    # Collect all large inline JSON/JS blobs that may carry channel state.
    blobs: list[str] = []

    # Pattern 1: <script ...>window.__initial_state__ = {...}</script>
    for m in re.finditer(r"window\.__(?:initial_state|data|store)__\s*=\s*(\{.{200,})", html, re.DOTALL):
        # Take up to 500KB of the blob — should be enough for video list
        blobs.append(m.group(1)[:500_000])

    # Pattern 2: <script type="application/json">...</script>
    for m in re.finditer(r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        content = m.group(1).strip()
        if len(content) > 500 and "dzen.ru" in content:
            blobs.append(content[:500_000])

    # Pattern 3: Raw large JSON objects inside <script> tags (no explicit type)
    for m in re.finditer(r'<script[^>]*>(\s*\{.{1000,}?\})\s*</script>', html, re.DOTALL):
        content = m.group(1).strip()
        if "video/watch" in content or "short-video" in content or '"videoUrl"' in content:
            blobs.append(content[:500_000])

    for blob in blobs:
        # Extract all explicit Dzen video URLs from blob.
        for vm in re.finditer(r'"url"\s*:\s*"(https://dzen\.ru/(?:video/watch|short-video)/[A-Za-z0-9_-]+)"', blob):
            url = _clean_dzen_video_url(vm.group(1))
            if url in seen:
                continue
            seen.add(url)

            # Try to find metadata in a window of ~2000 chars around this URL
            pos = vm.start()
            chunk = blob[max(0, pos - 2000):min(len(blob), pos + 2000)]

            title = "Dzen post"
            tm = re.search(r'"title"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)
            if tm:
                try:
                    title = json.loads(f'"{tm.group(1)}"') or title
                except Exception:
                    title = tm.group(1) or title

            published_at: Optional[datetime] = None
            for date_key in ("publishedAt", "createdAt", "pubDate", "date", "timestamp"):
                dm = re.search(rf'"{date_key}"\s*:\s*"?([^",\}}]+)"?', chunk)
                if dm:
                    published_at = _parse_any_datetime(dm.group(1).strip())
                    if published_at:
                        break

            views = 0
            for vk in ("views", "viewCount", "watchCount", "hits"):
                vkm = re.search(rf'"{vk}"\s*:\s*(\d+)', chunk)
                if vkm:
                    views = _as_int(vkm.group(1), default=0)
                    if views:
                        break

            duration_seconds: Optional[int] = None
            for dk in ("duration", "durationSeconds"):
                dkm = re.search(rf'"{dk}"\s*:\s*(\d+)', chunk)
                if dkm:
                    duration_seconds = _as_int(dkm.group(1), default=0) or None
                    if duration_seconds:
                        break

            tab_hint = _dzen_tab_hint_for_position(html, vm.start())
            results.append((url, title[:500], published_at, views, duration_seconds, _is_dzen_short_video(url, tab_hint=tab_hint)))

    return results


def _extract_dzen_video_card_candidates(html: str) -> list[tuple[str, str, Optional[datetime], int, Optional[int], bool]]:
    """
    Parse Dzen video cards from SSR HTML.
    Returns tuples: (url, title, published_at, views, duration_seconds, is_short)
    """
    results: list[tuple[str, str, Optional[datetime], int, Optional[int], bool]] = []
    seen: set[str] = set()

    for m in re.finditer(r"https://dzen\.ru/(?:video/watch|short-video)/[A-Za-z0-9_-]+", html):
        url = _clean_dzen_video_url(m.group(0))
        if url in seen:
            continue
        seen.add(url)

        # Prefer the enclosing article block for stable metadata extraction.
        pos = m.start()
        article_start = html.rfind("<article", 0, pos)
        article_end = html.find("</article>", pos)
        if article_start != -1 and article_end != -1 and article_end > article_start:
            chunk = html[article_start: article_end + len("</article>")]
        else:
            chunk = html[max(0, pos - 1200): min(len(html), pos + 7000)]
        text = " ".join(BeautifulSoup(chunk, "html.parser").get_text(" ", strip=True).split())

        title = "Dzen post"
        title_m = re.search(r'data-testid="card-part-title"[^>]*>([^<]+)<', chunk)
        if title_m:
            title = title_m.group(1).strip() or title

        views = 0
        vm = re.search(r"([0-9\s\.,]+)\s+(?:смотрел|просмотр(?:ов|а)?)", text, flags=re.IGNORECASE)
        if vm:
            views = _as_int(vm.group(1), default=0)

        published_at: Optional[datetime] = None
        # Match "2 дня назад", "5 минут назад", "3 месяца назад" etc. (no · separator in Dzen SSR)
        tm = re.search(
            r"(\d+)\s+(минут\w*|мин|час\w*|ч|день|дня|дней|недел\w*|неделю|месяц\w*|год\w*|лет)\s+назад",
            text,
            flags=re.IGNORECASE,
        )
        if tm:
            published_at = _parse_dzen_relative_time(f"{tm.group(1)} {tm.group(2)} назад")

        duration_seconds: Optional[int] = None
        dm = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", text)
        if dm:
            duration_seconds = _parse_duration_to_seconds(dm.group(1))

        tab_hint = _dzen_tab_hint_for_position(html, pos)
        results.append((url, title[:500], published_at, views, duration_seconds, _is_dzen_short_video(url, tab_hint=tab_hint)))

    return results


def _extract_rutube_video_candidates(html: str, base_url: str) -> list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]]:
    candidates: list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]] = []

    # Preferred path: embedded state contains real title/views/timestamps.
    for url, title, published_at, views, likes, comments, duration_seconds in _extract_rutube_embedded_candidates(html):
        candidates.append((url, title, published_at, views, likes, comments, duration_seconds))

    for obj in _extract_video_objects_from_json_ld(html):
        url = str(obj.get("url") or "").strip()
        if not url:
            continue
        title = str(obj.get("name") or obj.get("headline") or "Rutube video").strip() or "Rutube video"
        published_at = _parse_any_datetime(obj.get("uploadDate") or obj.get("datePublished"))

        views = 0
        likes = 0
        comments = 0
        duration_seconds = _parse_duration_to_seconds(str(obj.get("duration") or ""))
        interaction_stat = obj.get("interactionStatistic")
        if isinstance(interaction_stat, list):
            for stat in interaction_stat:
                if not isinstance(stat, dict):
                    continue
                interaction_type = str(stat.get("interactionType") or "").lower()
                count = _as_int(stat.get("userInteractionCount"), default=0)
                if "watch" in interaction_type or "view" in interaction_type:
                    views = max(views, count)
                elif "like" in interaction_type:
                    likes = max(likes, count)
                elif "comment" in interaction_type:
                    comments = max(comments, count)
        elif isinstance(interaction_stat, dict):
            interaction_type = str(interaction_stat.get("interactionType") or "").lower()
            count = _as_int(interaction_stat.get("userInteractionCount"), default=0)
            if "watch" in interaction_type or "view" in interaction_type:
                views = max(views, count)
            elif "like" in interaction_type:
                likes = max(likes, count)
            elif "comment" in interaction_type:
                comments = max(comments, count)

        if _is_valid_rutube_video_url(url):
            candidates.append((url, title[:500], published_at, views, likes, comments, duration_seconds))

    # Fallback: collect video URLs directly from HTML.
    for match in re.finditer(r"https?://(?:www\.)?rutube\.ru/(?:video|shorts)/[a-zA-Z0-9\-_/]+", html):
        url = match.group(0).rstrip('"\'')
        if _is_valid_rutube_video_url(url):
            candidates.append((url, "Rutube video", None, 0, 0, 0, None))
    for match in re.finditer(r"/(?:video|shorts)/[a-zA-Z0-9\-_/]+", html):
        url = f"{base_url.rstrip('/')}{match.group(0)}"
        if _is_valid_rutube_video_url(url):
            candidates.append((url, "Rutube video", None, 0, 0, 0, None))

    unique: dict[str, tuple[str, str, Optional[datetime], int, int, int, Optional[int]]] = {}
    for url, title, published_at, views, likes, comments, duration_seconds in candidates:
        # Prefer richer records with non-zero views and known publish date.
        if url not in unique:
            unique[url] = (url, title, published_at, views, likes, comments, duration_seconds)
            continue
        prev = unique[url]
        prev_score = (
            (1 if prev[2] else 0)
            + (1 if int(prev[3] or 0) > 0 else 0)
            + (1 if int(prev[4] or 0) > 0 else 0)
            + (1 if int(prev[5] or 0) > 0 else 0)
            + (1 if prev[1] != "Rutube video" else 0)
        )
        cur_score = (
            (1 if published_at else 0)
            + (1 if int(views or 0) > 0 else 0)
            + (1 if int(likes or 0) > 0 else 0)
            + (1 if int(comments or 0) > 0 else 0)
            + (1 if title != "Rutube video" else 0)
        )
        if cur_score > prev_score:
            unique[url] = (url, title, published_at, views, likes, comments, duration_seconds)
    return list(unique.values())


def _extract_likee_video_candidates(html: str, base_url: str) -> list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]]:
    candidates: list[tuple[str, str, Optional[datetime], int, int, int, Optional[int]]] = []

    # JSON-LD path.
    for obj in _extract_video_objects_from_json_ld(html):
        url = str(obj.get("url") or "").strip()
        if not url or not _is_valid_likee_video_url(url):
            continue
        title = str(obj.get("name") or obj.get("headline") or "Likee video").strip() or "Likee video"
        published_at = _parse_any_datetime(obj.get("uploadDate") or obj.get("datePublished"))
        duration_seconds = _parse_duration_to_seconds(str(obj.get("duration") or ""))
        views = 0
        likes = 0
        comments = 0
        interaction_stat = obj.get("interactionStatistic")
        if isinstance(interaction_stat, list):
            for stat in interaction_stat:
                if not isinstance(stat, dict):
                    continue
                interaction_type = str(stat.get("interactionType") or "").lower()
                count = _as_int(stat.get("userInteractionCount"), default=0)
                if "watch" in interaction_type or "view" in interaction_type:
                    views = max(views, count)
                elif "like" in interaction_type:
                    likes = max(likes, count)
                elif "comment" in interaction_type:
                    comments = max(comments, count)
        candidates.append((url, title[:500], published_at, views, likes, comments, duration_seconds))

    # Fallback by URL patterns.
    for pattern in (r"https?://(?:www\.)?likee\.video/[^\s\"']+", r"/video/[0-9]+"):
        for match in re.finditer(pattern, html):
            url = match.group(0).rstrip('"\'')
            if url.startswith("/"):
                url = f"{base_url.rstrip('/')}{url}"
            if not _is_valid_likee_video_url(url):
                continue
            candidates.append((url, "Likee video", None, 0, 0, 0, None))

    unique: dict[str, tuple[str, str, Optional[datetime], int, int, int, Optional[int]]] = {}
    for record in candidates:
        url = record[0]
        if url not in unique:
            unique[url] = record
    return list(unique.values())


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _window_bounds(
    *,
    period_days: int,
    start_date: Optional[date],
    end_date: Optional[date],
) -> tuple[datetime, datetime]:
    if start_date and end_date:
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        # inclusive end_date
        end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
        return start_dt, end_dt

    if start_date:
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.now(timezone.utc)
        return start_dt, end_dt

    if end_date:
        end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
        start_dt = datetime.combine((end_date - timedelta(days=max(1, period_days) - 1)), time.min).replace(
            tzinfo=timezone.utc
        )
        return start_dt, end_dt

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=max(1, period_days) - 1)
    start_dt = datetime.combine(start_dt.date(), time.min).replace(tzinfo=timezone.utc)
    return start_dt, end_dt


def _in_window(published_at: Optional[datetime], window_start: datetime, window_end: datetime) -> bool:
    if published_at is None:
        return False
    ts = _as_utc(published_at)
    return bool(ts and window_start <= ts <= window_end)


def _normalize_channel_videos_url(channel_url: str, tab: str = "videos") -> str:
    raw = (channel_url or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    lowered = path.lower()

    tab = (tab or "videos").strip().lower()
    if tab not in {"videos", "shorts"}:
        tab = "videos"

    if lowered.endswith(f"/{tab}"):
        return raw

    if "/@" in lowered or lowered.startswith("/@") or "/channel/" in lowered or "/c/" in lowered or "/user/" in lowered:
        # Remove existing tab suffixes before switching target tab.
        base_path = re.sub(r"/(videos|shorts)$", "", path, flags=re.IGNORECASE)
        new_path = f"{base_path}/{tab}"
        return parsed._replace(path=new_path).geturl()

    return raw


def _parse_youtube_channel_ytdlp(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    source_urls = [
        _normalize_channel_videos_url(channel_url, tab="videos"),
        _normalize_channel_videos_url(channel_url, tab="shorts"),
    ]
    source_urls = list(dict.fromkeys(url for url in source_urls if url))

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": False,
    }

    # List of (entry_dict, is_short_tab) — track which tab each entry came from.
    entries: list[tuple[dict[str, Any], bool]] = []
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for source_url in source_urls:
            is_shorts_tab = "shorts" in source_url.lower()
            try:
                info = ydl.extract_info(source_url, download=False) or {}
            except Exception as exc:
                logger.debug("[content_factory] yt-dlp list extraction failed for %s: %s", source_url, exc)
                continue

            source_entries = info.get("entries") or []
            if isinstance(source_entries, list):
                entries.extend([(item, is_shorts_tab) for item in source_entries if isinstance(item, dict)])

            if not channel_id:
                channel_id = info.get("channel_id") or info.get("uploader_id") or info.get("id")
            if not channel_title:
                channel_title = info.get("channel") or info.get("uploader") or info.get("title")

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    videos: list[ContentFactoryVideoPayload] = []

    detail_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
    }

    for item, from_shorts_tab in entries:
        if not item:
            continue
        published_at = _parse_yt_date(item.get("upload_date")) or _parse_yt_timestamp(item.get("timestamp"))

        raw_id = str(item.get("id") or "").strip()
        webpage_url = item.get("url")
        if webpage_url and isinstance(webpage_url, str) and webpage_url.startswith("https://www.youtube.com/watch"):
            video_url = webpage_url
        elif raw_id and _YT_VIDEO_ID_RE.match(raw_id):
            video_url = f"https://www.youtube.com/watch?v={raw_id}"
        else:
            # Skip channel tab/live/shorts pseudo-entries that are not real video items.
            continue

        # extract_flat often has no metrics; fetch detailed video data to avoid zero-only stats.
        detail = {}
        try:
            with yt_dlp.YoutubeDL(detail_opts) as detail_ydl:
                detail = detail_ydl.extract_info(video_url, download=False) or {}
        except Exception as exc:
            logger.debug("[content_factory] yt-dlp detail extraction failed for %s: %s", video_url, exc)

        detail_id = str(detail.get("id") or "").strip() if detail else ""
        video_external_id = detail_id if detail_id and _YT_VIDEO_ID_RE.match(detail_id) else raw_id
        if not video_external_id or not _YT_VIDEO_ID_RE.match(video_external_id):
            continue

        # Determine is_short: prefer tab origin, fall back to duration heuristic.
        detail_duration = int((detail.get("duration") if detail else None) or item.get("duration") or 0)
        is_short = from_shorts_tab or (detail_duration > 0 and detail_duration <= 180)
        final_video_url = (
            f"https://www.youtube.com/shorts/{video_external_id}"
            if is_short
            else f"https://www.youtube.com/watch?v={video_external_id}"
        )

        payload = ContentFactoryVideoPayload(
            video_external_id=video_external_id,
            video_url=final_video_url,
            title=detail.get("title") or item.get("title") or "Untitled",
            published_at=(
                _parse_yt_date(detail.get("upload_date"))
                or _parse_yt_timestamp(detail.get("timestamp"))
                or published_at
            ),
            views=int((detail.get("view_count") if detail else None) or item.get("view_count") or 0),
            likes=int((detail.get("like_count") if detail else None) or item.get("like_count") or 0),
            comments=int((detail.get("comment_count") if detail else None) or item.get("comment_count") or 0),
            duration_seconds=detail_duration if detail_duration else None,
            extra={"source": "yt_dlp", "detail_fetched": bool(detail), "is_short": is_short},
        )

        if not _in_window(payload.published_at, window_start, window_end):
            continue

        videos.append(payload)

    return ParserResult(channel_id, channel_title, videos, subscribers_count=None)


async def parse_youtube_channel(
    owner_id: int,
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    full_channel_mode = str(os.getenv("CONTENT_FACTORY_YOUTUBE_PARSE_FULL_CHANNEL", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    allow_fallback = str(os.getenv("CONTENT_FACTORY_ALLOW_YTDLP_FALLBACK", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enrich_shorts_with_ytdlp = str(os.getenv("CONTENT_FACTORY_YOUTUBE_ENRICH_SHORTS_WITH_YTDLP", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        youtube_client = await get_shared_yt_client()
        window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
        # In full-channel mode we intentionally disable lookback cutoff and keep
        # all videos from uploads playlist traversal.
        if full_channel_mode:
            lookback_days_for_fetch = 0
        else:
            # collect_channel_videos takes lookback from "now"; for historical ranges we must
            # expand lookback to include the selected start bound, otherwise candidates become 0.
            now_utc = datetime.now(timezone.utc)
            lookback_days_for_fetch = max(
                max(1, period_days),
                (now_utc.date() - window_start.date()).days + 1,
            )
            lookback_days_for_fetch = min(3650, lookback_days_for_fetch)

        resolved = await resolve_youtube_channel_id(
            input_str=channel_url,
            owner_id=owner_id,
            youtube_client=youtube_client,
        )

        if not resolved.youtube_channel_id:
            raise ValueError(resolved.error or f"Unable to resolve YouTube channel from URL: {channel_url}")

        channel_id = resolved.youtube_channel_id

        channel_info = await collect_channel_info(
            channel_id=channel_id,
            owner_id=owner_id,
            youtube_client=youtube_client,
        )

        video_ids = await collect_channel_videos(
            youtube_client=youtube_client,
            owner_id=owner_id,
            channel_id=channel_id,
            lookback_days=lookback_days_for_fetch,
        )

        details = await collect_video_details(
            youtube_client=youtube_client,
            owner_id=owner_id,
            video_ids=video_ids,
        )

        videos: list[ContentFactoryVideoPayload] = []
        for item in details:
            published_at = _parse_published_at(item.get("published_at"))
            if not full_channel_mode and not _in_window(published_at, window_start, window_end):
                continue
            video_id = str(item.get("video_id") or "").strip()
            if not _YT_VIDEO_ID_RE.match(video_id):
                continue
            video_url = item.get("url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
            if not video_id or not video_url:
                continue

            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(video_id),
                    video_url=str(video_url),
                    title=item.get("title") or "Untitled",
                    published_at=published_at,
                    views=int(item.get("views") or 0),
                    likes=int(item.get("likes") or 0),
                    comments=int(item.get("comments") or 0),
                    duration_seconds=int(item.get("duration_seconds") or 0) or None,
                    extra={
                        "source": "youtube_api",
                        "is_short": bool(item.get("is_short", False)),
                    },
                )
            )

        # Some channels expose Shorts inconsistently through API search/list endpoints.
        # If API returned videos but none marked as short, do a lightweight yt-dlp pass
        # and merge only missing Shorts by video_external_id.
        if (
            videos
            and enrich_shorts_with_ytdlp
            and not full_channel_mode
            and not any((v.extra or {}).get("is_short") for v in videos)
        ):
            try:
                ytdlp_fallback = _parse_youtube_channel_ytdlp(
                    channel_url=channel_url,
                    period_days=period_days,
                    start_date=start_date,
                    end_date=end_date,
                )
                existing_ids = {v.video_external_id for v in videos if v.video_external_id}
                merged = 0
                for candidate in ytdlp_fallback.videos:
                    candidate_extra = candidate.extra or {}
                    if not candidate_extra.get("is_short"):
                        continue
                    if not candidate.video_external_id or candidate.video_external_id in existing_ids:
                        continue
                    videos.append(candidate)
                    existing_ids.add(candidate.video_external_id)
                    merged += 1
                if merged:
                    logger.info(
                        "[content_factory] YouTube shorts enriched via yt-dlp. url=%s merged=%s",
                        channel_url,
                        merged,
                    )
            except Exception as exc:
                logger.debug("[content_factory] YouTube shorts enrichment failed for %s: %s", channel_url, exc)

        if not videos:
            logger.warning(
                "[content_factory] YouTube API returned 0 videos, fallback to yt-dlp. url=%s channel_id=%s period_days=%s",
                channel_url,
                channel_id,
                period_days,
            )
            fallback = _parse_youtube_channel_ytdlp(
                channel_url=channel_url,
                period_days=period_days,
                start_date=start_date,
                end_date=end_date,
            )
            if fallback.videos:
                return ParserResult(
                    channel_external_id=fallback.channel_external_id or channel_id,
                    channel_title=fallback.channel_title or (channel_info.title if channel_info else None),
                    videos=fallback.videos,
                    subscribers_count=int(getattr(channel_info, "subscribers", 0) or 0) if channel_info else 0,
                )

        return ParserResult(
            channel_external_id=channel_id,
            channel_title=(channel_info.title if channel_info else None),
            videos=videos,
            subscribers_count=int(getattr(channel_info, "subscribers", 0) or 0) if channel_info else 0,
        )

    except Exception as exc:
        if not allow_fallback:
            raise RuntimeError(f"YouTube API parser failed: {exc}") from exc

        logger.warning("[content_factory] YouTube API parser failed, fallback to yt-dlp. url=%s err=%s", channel_url, exc)
        return _parse_youtube_channel_ytdlp(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )


async def parse_instagram_apify(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    token = _pick_apify_token()
    actor_id = _secret("CONTENT_FACTORY_INSTAGRAM_APIFY_ACTOR_ID", "xMc5Ga1oCONPmWJIa")
    fallback_enabled = _feature_enabled("CONTENT_FACTORY_APIFY_BROWSER_FALLBACK_ENABLED", "1")
    if not token:
        fallback_videos: list[ContentFactoryVideoPayload] = []
        if fallback_enabled:
            fallback_videos = await _discover_channel_video_links("instagram", channel_url)
            if fallback_videos:
                recovered, _ = await _recover_missing_video_metrics("instagram", fallback_videos)
                fallback_videos = recovered
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=fallback_videos,
            sync_status="ok" if fallback_videos else "partial",
            sync_message=(
                "APIFY_TOKEN не задан; применен browser discovery fallback для Instagram."
                if fallback_videos
                else "APIFY_TOKEN не задан. Добавьте ключ в backend/content_factory/local_secrets.py или env."
            ),
        )

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    username = _extract_handle_from_url(channel_url)
    if not username:
        return ParserResult(
            channel_external_id=None,
            channel_title=None,
            videos=[],
            sync_status="partial",
            sync_message=f"Не удалось извлечь username из Instagram URL: {channel_url}",
        )
    max_items = _secret_int("CONTENT_FACTORY_INSTAGRAM_APIFY_MAX_ITEMS", 200, min_value=20, max_value=2000)
    payload = {
        "username": [username],
        "resultsLimit": max_items,
        "maxItems": max_items,
    }

    try:
        items = await _run_apify_actor(actor_id=actor_id, token=token, payload=payload)
    except Exception as exc:
        fallback_videos: list[ContentFactoryVideoPayload] = []
        if fallback_enabled:
            fallback_videos = await _discover_channel_video_links("instagram", channel_url)
            if fallback_videos:
                recovered, _ = await _recover_missing_video_metrics("instagram", fallback_videos)
                fallback_videos = recovered
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=fallback_videos,
            sync_status="ok" if fallback_videos else "partial",
            sync_message=(
                f"Apify недоступен или вернул ошибку: {str(exc)[:180]}. Использован browser discovery fallback."
                if fallback_videos
                else f"Apify недоступен или вернул ошибку: {str(exc)[:220]}"
            ),
        )
    items = _expand_instagram_apify_items(items)
    videos: list[ContentFactoryVideoPayload] = []
    channel_title: Optional[str] = None
    channel_external_id: Optional[str] = _extract_handle_from_url(channel_url)
    subscribers_count: Optional[int] = None

    for item in items:
        item_url = _canonical_video_url("instagram", str(_pick_first(item, ("url", "postUrl", "inputUrl")) or "").strip())
        if not item_url:
            continue

        item_kind = str(_pick_first(item, ("type", "productType", "mediaType")) or "").lower()
        explicit_is_video = bool(
            _pick_first(item, ("isVideo", "is_video"))
            or _pick_first_path(item, ("node.is_video", "video.url", "video_versions.0.url"))
        )
        is_reel_url = "/reel/" in item_url
        is_video_post = bool(item_url and (is_reel_url or explicit_is_video or any(token in item_kind for token in ("reel", "video", "clip", "igtv")) or "/p/" in item_url))
        if not is_video_post:
            continue

        published_at = _parse_any_datetime(
            _pick_first(item, ("timestamp", "takenAt", "createdAt", "createTimeISO", "time", "publishedAt",
                                "taken_at", "created_at", "posted_at", "datePublished", "uploadDate", "date"))
            or _pick_first_path(item, ("edge_media_to_caption.edges.0.node.created_at",))
        )
        if published_at and not _in_window(published_at, window_start, window_end):
            continue

        owner_username = str(_pick_first(item, ("ownerUsername", "username", "ownerFullName", "authorUsername")) or "").strip()
        if owner_username and not channel_external_id:
            channel_external_id = owner_username
        if owner_username and not channel_title:
            channel_title = owner_username

        followers = _as_int(_pick_first(item, ("ownerFollowersCount", "followersCount", "authorFollowers")), default=0)
        if followers > 0:
            subscribers_count = max(subscribers_count or 0, followers)

        views = _as_int(_pick_first(item, ("videoViewCount", "viewCount", "view_count", "viewsCount", "video_view_count",
                                           "videoPlayCount", "playCount", "play_count")))
        if views <= 0:
            views = _as_int(_pick_first_path(item, (
                "video.view_count",
                "video.viewCount",
                "video.play_count",
                "video.playCount",
                "statistics.viewCount",
                "statistics.playCount",
                "stats.viewCount",
                "stats.playCount",
                "media.view_count",
                "media.play_count",
            )))

        likes = _as_int(_pick_first(item, ("likesCount", "likes", "likeCount")))
        if likes <= 0:
            likes = _as_int(_pick_first_path(item, (
                "statistics.likeCount",
                "stats.likeCount",
                "edge_media_preview_like.count",
            )))

        comments = _as_int(_pick_first(item, ("commentsCount", "comments", "commentCount")))
        if comments <= 0:
            comments = _as_int(_pick_first_path(item, (
                "statistics.commentCount",
                "stats.commentCount",
                "edge_media_to_comment.count",
            )))

        title = str(_pick_first(item, ("caption", "title", "alt", "text")) or "Instagram post").strip()
        if not title:
            title = "Instagram post"

        duration_seconds = _as_int(_pick_first(item, ("videoDuration", "duration")), default=0) or None

        media_width = _as_int(
            _pick_first(item, ("videoWidth", "width", "originalWidth")),
            default=0,
        ) or _as_int(_pick_first_path(item, ("video.width", "dimensions.width", "image_versions2.candidates.0.width")))
        media_height = _as_int(
            _pick_first(item, ("videoHeight", "height", "originalHeight")),
            default=0,
        ) or _as_int(_pick_first_path(item, ("video.height", "dimensions.height", "image_versions2.candidates.0.height")))
        is_vertical: Optional[bool] = None
        if media_width > 0 and media_height > 0:
            is_vertical = media_height >= media_width

        short_format = "reel"
        is_short = True

        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_pick_first(item, ("id", "shortCode", "code")) or item_url),
                video_url=item_url,
                title=title[:500],
                published_at=published_at,
                views=views,
                likes=likes,
                comments=comments,
                duration_seconds=duration_seconds,
                extra={
                    "source": "apify",
                    "network": "instagram",
                    "is_short": is_short,
                    "short_format": short_format,
                    "is_vertical": is_vertical,
                    "media_width": media_width or None,
                    "media_height": media_height or None,
                    "raw": {k: item.get(k) for k in ("type", "productType", "isVideo")},
                },
            )
        )

    if not videos and fallback_enabled:
        fallback_videos = await _discover_channel_video_links("instagram", channel_url)
        if fallback_videos:
            recovered, _ = await _recover_missing_video_metrics("instagram", fallback_videos)
            return ParserResult(
                channel_external_id=channel_external_id,
                channel_title=channel_title,
                videos=recovered,
                subscribers_count=subscribers_count,
                sync_status="ok",
                sync_message="Apify вернул 0 публикаций; использован browser discovery fallback.",
            )

    return ParserResult(
        channel_external_id=channel_external_id,
        channel_title=channel_title,
        videos=videos,
        subscribers_count=subscribers_count,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else "Apify ответил без публикаций за выбранный период.",
    )


async def parse_tiktok_apify(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    token = _pick_apify_token()
    actor_id = _secret("CONTENT_FACTORY_TIKTOK_APIFY_ACTOR_ID", "GdWCkxBtKWOsKjdch")
    fallback_enabled = _feature_enabled("CONTENT_FACTORY_APIFY_BROWSER_FALLBACK_ENABLED", "1")
    if not token:
        fallback_videos: list[ContentFactoryVideoPayload] = []
        if fallback_enabled:
            fallback_videos = await _discover_channel_video_links("tiktok", channel_url)
            if fallback_videos:
                recovered, _ = await _recover_missing_video_metrics("tiktok", fallback_videos)
                fallback_videos = recovered
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=fallback_videos,
            sync_status="ok" if fallback_videos else "partial",
            sync_message=(
                "APIFY_TOKEN не задан; применен browser discovery fallback для TikTok."
                if fallback_videos
                else "APIFY_TOKEN не задан. Добавьте ключ в backend/content_factory/local_secrets.py или env."
            ),
        )

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    max_items = _secret_int("CONTENT_FACTORY_TIKTOK_APIFY_MAX_ITEMS", 200, min_value=20, max_value=2000)
    payload = {
        "profiles": [channel_url],
        "shouldDownloadVideos": False,
        "maxItems": max_items,
    }

    try:
        items = await _run_apify_actor(actor_id=actor_id, token=token, payload=payload)
    except Exception as exc:
        fallback_videos: list[ContentFactoryVideoPayload] = []
        if fallback_enabled:
            fallback_videos = await _discover_channel_video_links("tiktok", channel_url)
            if fallback_videos:
                recovered, _ = await _recover_missing_video_metrics("tiktok", fallback_videos)
                fallback_videos = recovered
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=fallback_videos,
            sync_status="ok" if fallback_videos else "partial",
            sync_message=(
                f"Apify недоступен или вернул ошибку: {str(exc)[:180]}. Использован browser discovery fallback."
                if fallback_videos
                else f"Apify недоступен или вернул ошибку: {str(exc)[:220]}"
            ),
        )
    items = _expand_tiktok_apify_items(items)
    videos: list[ContentFactoryVideoPayload] = []
    channel_title: Optional[str] = None
    channel_external_id: Optional[str] = _extract_handle_from_url(channel_url)
    subscribers_count: Optional[int] = None

    for item in items:
        author = {}
        for author_key in ("authorMeta", "author", "authorInfo"):
            author_value = item.get(author_key)
            if isinstance(author_value, dict):
                author = author_value
                break
        item_url = _canonical_video_url("tiktok", str(_pick_first(item, ("webVideoUrl", "url", "videoUrl", "shareUrl", "share_url")) or "").strip())
        if not item_url:
            video_id = str(_pick_first(item, ("id", "videoId", "video_id", "aweme_id", "awemeId")) or "").strip()
            author_handle = str(
                author.get("name")
                or author.get("uniqueId")
                or author.get("unique_id")
                or author.get("authorName")
                or ""
            ).strip().lstrip("@")
            if video_id and author_handle:
                item_url = _canonical_video_url("tiktok", f"https://www.tiktok.com/@{author_handle}/video/{video_id}")
        if not item_url:
            continue
        published_at = _parse_any_datetime(_pick_first(item, ("createTimeISO", "createTime", "create_time", "publishedAt",
                                                                "createAt", "created_at", "timestamp", "date", "time")))
        if published_at and not _in_window(published_at, window_start, window_end):
            continue

        if not channel_title:
            channel_title = str(author.get("name") or author.get("nickName") or "").strip() or None
        if not channel_external_id:
            channel_external_id = str(author.get("name") or "").strip() or None
        followers = _as_int(author.get("fans"), default=0)
        if followers > 0:
            subscribers_count = max(subscribers_count or 0, followers)

        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_pick_first(item, ("id", "videoId", "video_id")) or item_url),
                video_url=item_url,
                title=str(_pick_first(item, ("text", "title", "desc")) or "TikTok post")[:500],
                published_at=published_at,
                views=_as_int(_pick_first(item, ("playCount", "play_count", "views", "viewCount")))
                or _as_int(_pick_first_path(item, ("stats.playCount", "statistics.playCount"))),
                likes=_as_int(_pick_first(item, ("diggCount", "digg_count", "likes", "likeCount")))
                or _as_int(_pick_first_path(item, ("stats.diggCount", "statistics.likeCount"))),
                comments=_as_int(_pick_first(item, ("commentCount", "comment_count", "comments")))
                or _as_int(_pick_first_path(item, ("stats.commentCount", "statistics.commentCount"))),
                shares=_as_int(_pick_first(item, ("shareCount", "share_count", "shares")))
                or _as_int(_pick_first_path(item, ("stats.shareCount", "statistics.shareCount"))),
                duration_seconds=_as_int(_pick_first(item, ("videoDuration", "video_duration", "duration")), default=0)
                or _as_int(_pick_first_path(item, ("videoMeta.duration", "video.duration")), default=0)
                or None,
                extra={"source": "apify", "network": "tiktok", "is_short": True},
            )
        )

    if not videos and fallback_enabled:
        fallback_videos = await _discover_channel_video_links("tiktok", channel_url)
        if fallback_videos:
            recovered, _ = await _recover_missing_video_metrics("tiktok", fallback_videos)
            return ParserResult(
                channel_external_id=channel_external_id,
                channel_title=channel_title,
                videos=recovered,
                subscribers_count=subscribers_count,
                sync_status="ok",
                sync_message="Apify вернул 0 публикаций; использован browser discovery fallback.",
            )

    return ParserResult(
        channel_external_id=channel_external_id,
        channel_title=channel_title,
        videos=videos,
        subscribers_count=subscribers_count,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else "Apify ответил без публикаций за выбранный период.",
    )


async def _parse_vk_apify_fallback(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[ParserResult]:
    token = _pick_apify_token()
    actor_id = _secret("CONTENT_FACTORY_VK_APIFY_ACTOR_ID", "")
    if not token or not actor_id:
        return None

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    max_items = _secret_int("CONTENT_FACTORY_VK_APIFY_MAX_ITEMS", 200, min_value=20, max_value=2000)
    payload_candidates: list[dict[str, Any]] = [
        {"startUrls": [{"url": channel_url}], "maxItems": max_items},
        {"urls": [channel_url], "maxItems": max_items},
        {"channelUrls": [channel_url], "maxItems": max_items},
        {"profiles": [channel_url], "maxItems": max_items},
        {"directUrls": [channel_url], "maxItems": max_items},
    ]

    items: list[dict[str, Any]] = []
    last_error: Optional[str] = None
    for payload in payload_candidates:
        try:
            items = await _run_apify_actor(actor_id=actor_id, token=token, payload=payload)
            if items:
                break
        except Exception as exc:
            last_error = str(exc)

    if not items:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            sync_status="partial",
            sync_message=(
                f"VK Apify fallback не дал публикаций: {last_error[:180]}"
                if last_error
                else "VK Apify fallback не дал публикаций."
            ),
        )

    videos: list[ContentFactoryVideoPayload] = []
    channel_external_id: Optional[str] = _extract_handle_from_url(channel_url)
    channel_title: Optional[str] = None
    subscribers_count: Optional[int] = None
    seen_urls: set[str] = set()

    for item in items:
        item_url = str(
            _pick_first(item, ("url", "videoUrl", "webVideoUrl", "link", "permalink", "shareUrl", "postUrl"))
            or _pick_first_path(item, ("video.url", "video.shareUrl", "post.url", "item.url"))
            or ""
        ).strip()
        if not item_url or item_url in seen_urls:
            continue

        published_at = _parse_any_datetime(
            _pick_first(item, ("publishedAt", "createTimeISO", "createTime", "timestamp", "date", "datePublished"))
            or _pick_first_path(item, ("video.createdAt", "video.date", "item.datePublished"))
        )
        if published_at and not _in_window(published_at, window_start, window_end):
            continue

        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
        group = item.get("group") if isinstance(item.get("group"), dict) else {}

        if not channel_title:
            channel_title = str(
                _pick_first(item, ("channelTitle", "channelName", "authorName", "ownerName", "title"))
                or author.get("name")
                or owner.get("name")
                or group.get("name")
                or ""
            ).strip() or None
        if not channel_external_id:
            channel_external_id = str(
                _pick_first(item, ("channelId", "ownerId", "authorId"))
                or author.get("id")
                or owner.get("id")
                or group.get("id")
                or ""
            ).strip() or None

        followers = max(
            _as_int(_pick_first(item, ("followers", "followersCount", "subscribersCount", "membersCount")), default=0),
            _as_int(author.get("followers") if isinstance(author, dict) else None, default=0),
            _as_int(owner.get("followers") if isinstance(owner, dict) else None, default=0),
            _as_int(group.get("membersCount") if isinstance(group, dict) else None, default=0),
        )
        if followers > 0:
            subscribers_count = max(subscribers_count or 0, followers)

        seen_urls.add(item_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_pick_first(item, ("id", "videoId", "postId", "clipId")) or _extract_handle_from_url(item_url) or item_url),
                video_url=item_url,
                title=str(_pick_first(item, ("title", "text", "caption", "description")) or "VK video")[:500],
                published_at=published_at,
                views=_as_int(_pick_first(item, ("views", "viewCount", "playCount", "viewsCount")))
                or _as_int(_pick_first_path(item, ("stats.views", "statistics.views", "video.views"))),
                likes=_as_int(_pick_first(item, ("likes", "likeCount", "likesCount")))
                or _as_int(_pick_first_path(item, ("stats.likes", "statistics.likes", "video.likes"))),
                comments=_as_int(_pick_first(item, ("comments", "commentCount", "commentsCount")))
                or _as_int(_pick_first_path(item, ("stats.comments", "statistics.comments", "video.comments"))),
                shares=_as_int(_pick_first(item, ("shares", "shareCount", "reposts")))
                or _as_int(_pick_first_path(item, ("stats.shares", "statistics.shares", "video.shares"))),
                duration_seconds=_as_int(_pick_first(item, ("duration", "videoDuration")), default=0)
                or _as_int(_pick_first_path(item, ("video.duration", "media.duration")), default=0)
                or None,
                extra={"source": "apify", "network": "vk"},
            )
        )

    return ParserResult(
        channel_external_id=channel_external_id,
        channel_title=channel_title,
        videos=videos,
        subscribers_count=subscribers_count,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else "VK Apify fallback ответил без публикаций за выбранный период.",
    )


async def parse_vk_http(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    # If Apify is preferred and configured, try that first.
    prefer_apify = _feature_enabled("CONTENT_FACTORY_VK_PREFER_APIFY", "1")
    if prefer_apify:
        apify_result = await _parse_vk_apify_fallback(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
        if apify_result and apify_result.videos:
            apify_result.sync_message = (apify_result.sync_message or "") + (
                " " if apify_result.sync_message else ""
            ) + "Использован VK Apify (приоритетный источник)."
            return apify_result

    # Fallback: HTTP + external fetch if Apify unavailable or no results.
    _ = (period_days, start_date, end_date)
    timeout = aiohttp.ClientTimeout(total=_timeout_seconds("CONTENT_FACTORY_VK_HTTP_TIMEOUT_SECONDS", 15))
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    proxy_chain = _proxy_attempt_chain("CONTENT_FACTORY_VK_PROXY_URL", include_direct=True)

    request_urls = [channel_url]
    if "vkvideo.ru" in channel_url:
        request_urls.append(channel_url.replace("https://vkvideo.ru", "https://vk.com"))
    elif "vk.com" in channel_url:
        request_urls.append(channel_url.replace("https://vk.com", "https://vkvideo.ru"))

    text: Optional[str] = None
    last_status: Optional[int] = None
    extraction_log: list[str] = []
    proxy_failures: list[str] = []
    
    antibot_hits: list[str] = []
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for request_url in dict.fromkeys(request_urls):
            for attempt_proxy in proxy_chain:
                proxy_label = attempt_proxy or "direct"
                try:
                    async with session.get(request_url, proxy=attempt_proxy) as response:
                        body = await response.text()
                        last_status = response.status
                        if response.status < 400 and body:
                            antibot_sign = _detect_antibot_page(body)
                            if antibot_sign:
                                antibot_hits.append(f"{request_url} via {proxy_label}: {antibot_sign}")
                                extraction_log.append(f"HTTP GET {request_url} via {proxy_label} — anti-bot:{antibot_sign}")
                                continue
                            text = body
                            extraction_log.append(f"HTTP GET {request_url} via {proxy_label} — успешно ({response.status})")
                            break
                        extraction_log.append(f"HTTP GET {request_url} via {proxy_label} — статус {response.status}")
                except Exception as http_err:
                    err_text = str(http_err)[:140]
                    extraction_log.append(f"HTTP GET {request_url} via {proxy_label} — ошибка: {err_text}")
                    if _is_proxy_billing_error(err_text):
                        proxy_failures.append(f"{proxy_label}:402 Payment Required")
                    continue
            if text:
                break

    if not text:
        for request_url in dict.fromkeys(request_urls):
            external_html, external_provider = await _external_fetch_html(
                request_url, render_js=True, country="ru", network="vk"
            )
            if external_html:
                text = external_html
                extraction_log.append(f"External fetch {external_provider} {request_url} — успешно")
                break

    if not text:
        if antibot_hits:
            return ParserResult(
                channel_external_id=_extract_handle_from_url(channel_url),
                channel_title=None,
                videos=[],
                sync_status="partial",
                sync_message=(
                    "VK заблокировал все попытки (anti-bot/CAPTCHA). "
                    f"Примеры: {'; '.join(antibot_hits[:2])}. "
                    + (
                        f"Прокси ошибки: {'; '.join(list(dict.fromkeys(proxy_failures))[:2])}. "
                        if proxy_failures
                        else ""
                    )
                    + "Проверьте прокси в CONTENT_FACTORY_VK_PROXY_URL/CONTENT_FACTORY_PROXY_URL или /app/proxy.txt"
                ),
            )
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            sync_status="partial",
            sync_message=f"VK страница не загружена ({last_status or 'unknown'}). Попытки: {'; '.join(extraction_log[:3])}",
        )

    soup = BeautifulSoup(text, "html.parser")
    page_title = (soup.title.get_text(strip=True) if soup.title else "") or None

    # Detect anti-bot challenge page — VK/vkvideo.ru blocks data-center IPs.
    antibot_sign = _detect_antibot_page(text, page_title)
    if antibot_sign:
        for request_url in dict.fromkeys(request_urls):
            external_html, external_provider = await _external_fetch_html(
                request_url, render_js=True, country="ru", network="vk"
            )
            if not external_html:
                continue
            external_antibot = _detect_antibot_page(external_html)
            if external_antibot:
                continue
            text = external_html
            soup = BeautifulSoup(text, "html.parser")
            page_title = (soup.title.get_text(strip=True) if soup.title else "") or None
            extraction_log.append(f"External fetch {external_provider} снял anti-bot для {request_url}")
            antibot_sign = None
            break

    if antibot_sign:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=(
                f"VK заблокировал запрос (anti-bot/CAPTCHA: {antibot_sign}). "
                "Задайте CONTENT_FACTORY_VK_PROXY_URL или CONTENT_FACTORY_PROXY_URL чтобы обойти блокировку."
            ),
        )

    post_ids = list(dict.fromkeys(re.findall(r"wall-?\d+_\d+", text)))[:40]
    
    # Improved regex for clip and video URLs from vkvideo.ru and vk.com
    fallback_urls = list(
        dict.fromkeys(
            re.findall(
                r"https?://(?:www\.)?(?:vk\.com|vkvideo\.ru)/(?:video-?\d+(?:_\d+)?|clip-?\d+(?:_\d+)?)",
                text,
                flags=re.IGNORECASE,
            )
        )
    )
    # Many responses contain relative URLs only; normalize them into absolute links.
    relative_matches = re.findall(r"(?:^|[\"'])/(?:video-?\d+(?:_\d+)?|clip-?\d+(?:_\d+)?)(?:[\"']|$)", text, flags=re.IGNORECASE)
    for item in relative_matches:
        normalized = item.strip("'\" ")
        if normalized.startswith("/"):
            if "/clip-" in normalized.lower():
                fallback_urls.append(f"https://vkvideo.ru{normalized}")
            else:
                fallback_urls.append(f"https://vk.com{normalized}")
    fallback_urls = list(dict.fromkeys(fallback_urls))[:40]

    videos: list[ContentFactoryVideoPayload] = []
    
    # Stage 1: Extract from post_ids (wall-NNN_MMM format)
    if post_ids:
        extraction_log.append(f"Найдено {len(post_ids)} post_ids в HTML содержимом")
        for post_id in post_ids:
            post_url = f"https://vk.com/{post_id}"
            pos = text.find(post_id)
            chunk = text[max(0, pos - 1200) : pos + 2500] if pos >= 0 else text[:1500]

            views = _extract_count_by_regex(
                chunk,
                (
                    r'"views"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                    r'"post_view_count"\s*:\s*"?(\d+)"?',
                    r"([0-9\s]+)\s+просмотр",
                ),
            )
            likes = _extract_count_by_regex(
                chunk,
                (
                    r'"likes"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                    r'"like_num"\s*:\s*"?(\d+)"?',
                    r"([0-9\s]+)\s+лайк",
                ),
            )
            comments = _extract_count_by_regex(
                chunk,
                (
                    r'"comments"\s*:\s*\{[^}]*"count"\s*:\s*"?(\d+)"?',
                    r'"comment_num"\s*:\s*"?(\d+)"?',
                    r"([0-9\s]+)\s+коммент",
                ),
            )

            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=post_id,
                    video_url=post_url,
                    title=f"VK post {post_id}",
                    published_at=None,
                    views=views,
                    likes=likes,
                    comments=comments,
                    extra={"source": "http_scraper", "network": "vk"},
                )
            )

    # Stage 2: Use fallback URLs found in HTTP response
    if not videos and fallback_urls:
        extraction_log.append(f"Fallback #1: Найдено {len(fallback_urls)} video/clip URLs в HTML")
        for idx, video_url in enumerate(fallback_urls):
            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(_extract_handle_from_url(video_url) or f"vk_{idx}"),
                    video_url=video_url,
                    title="VK video",
                    published_at=None,
                    views=0,
                    likes=0,
                    comments=0,
                    extra={"source": "http_scraper", "network": "vk"},
                )
            )

    # Stage 3: Use browser rendering for clip IDs (vkvideo.ru is SPA)
    if not videos:
        owner_id = _extract_vk_owner_id(channel_url)
        if owner_id:
            try:
                browser_clip_urls = await _extract_vk_clip_ids_via_browser(channel_url, owner_id)
                if browser_clip_urls:
                    extraction_log.append(f"Fallback #2: Браузер нашел {len(browser_clip_urls)} clip URLs")
                    for video_url in browser_clip_urls:
                        clip_part = video_url.rsplit("/", 1)[-1]
                        videos.append(
                            ContentFactoryVideoPayload(
                                video_external_id=clip_part,
                                video_url=video_url,
                                title="VK video",
                                published_at=None,
                                views=0,
                                likes=0,
                                comments=0,
                                extra={"source": "browser_clip_id", "network": "vk"},
                            )
                        )
                else:
                    extraction_log.append(f"Fallback #2: Браузер не нашел clip URLs")
            except Exception as browser_err:
                extraction_log.append(f"Fallback #2: Ошибка браузера: {str(browser_err)[:80]}")

    # Stage 4: Generic link collection via browser
    if not videos:
        try:
            browser_links = await _collect_links_via_browser(
                page_url=channel_url,
                selectors=["a[href*='/video']", "a[href*='/clip']"],
                include_pattern=r"(?:vk\.com|vkvideo\.ru)/(?:video-?\d+_\d+|clip-?\d+_\d+)",
                max_links=40,
            )
            if browser_links:
                extraction_log.append(f"Fallback #3: Браузер нашел {len(browser_links)} generic links")
                for idx, video_url in enumerate(browser_links):
                    videos.append(
                        ContentFactoryVideoPayload(
                            video_external_id=str(_extract_handle_from_url(video_url) or f"vk_browser_{idx}"),
                            video_url=video_url,
                            title="VK video",
                            published_at=None,
                            views=0,
                            likes=0,
                            comments=0,
                            extra={"source": "browser_scraper", "network": "vk"},
                        )
                    )
            else:
                extraction_log.append(f"Fallback #3: Браузер не нашел links")
        except Exception as generic_browser_err:
            extraction_log.append(f"Fallback #3: Ошибка generic браузера: {str(generic_browser_err)[:80]}")

    await _enrich_videos_from_pages(videos, headers=headers)

    result = ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else f"Не найдены видео на странице VK. Попытки: {'; '.join(extraction_log[-5:])}",
    )
    return result


async def _parse_ok_apify_fallback(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[ParserResult]:
    token = _pick_apify_token()
    actor_id = _secret("CONTENT_FACTORY_OK_APIFY_ACTOR_ID", "")
    if not token or not actor_id:
        return None

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    max_items = _secret_int("CONTENT_FACTORY_OK_APIFY_MAX_ITEMS", 200, min_value=20, max_value=2000)
    payload_candidates: list[dict[str, Any]] = [
        {"startUrls": [{"url": channel_url}], "maxItems": max_items},
        {"urls": [channel_url], "maxItems": max_items},
        {"directUrls": [channel_url], "maxItems": max_items},
        {"profiles": [channel_url], "maxItems": max_items},
    ]

    items: list[dict[str, Any]] = []
    last_error: Optional[str] = None
    for payload in payload_candidates:
        try:
            items = await _run_apify_actor(actor_id=actor_id, token=token, payload=payload)
            if items:
                break
        except Exception as exc:
            last_error = str(exc)

    if not items:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            sync_status="partial",
            sync_message=(
                f"OK Apify fallback не дал публикаций: {last_error[:180]}"
                if last_error
                else "OK Apify fallback не дал публикаций."
            ),
        )

    videos: list[ContentFactoryVideoPayload] = []
    seen_urls: set[str] = set()
    channel_title: Optional[str] = None
    channel_external_id: Optional[str] = _extract_handle_from_url(channel_url)
    subscribers_count: Optional[int] = None

    for item in items:
        item_url = str(
            _pick_first(item, ("url", "videoUrl", "postUrl", "shareUrl", "link", "permalink"))
            or _pick_first_path(item, ("video.url", "video.shareUrl", "post.url", "result.url"))
            or ""
        ).strip()
        if not item_url and _pick_first(item, ("id", "videoId", "postId")):
            item_url = f"https://ok.ru/video/{_pick_first(item, ('id', 'videoId', 'postId'))}"

        if not item_url or item_url in seen_urls or not _is_valid_ok_video_url(item_url):
            continue

        published_at = _parse_any_datetime(
            _pick_first(item, ("publishedAt", "createTimeISO", "createTime", "timestamp", "date", "datePublished"))
            or _pick_first_path(item, ("video.createdAt", "video.date", "item.datePublished"))
        )
        if published_at and not _in_window(published_at, window_start, window_end):
            continue

        if not channel_title:
            channel_title = str(
                _pick_first(item, ("channelTitle", "channelName", "authorName", "ownerName"))
                or _pick_first_path(item, ("author.name", "owner.name", "group.name"))
                or ""
            ).strip() or None

        if not channel_external_id:
            channel_external_id = str(
                _pick_first(item, ("channelId", "ownerId", "authorId"))
                or _pick_first_path(item, ("author.id", "owner.id", "group.id"))
                or ""
            ).strip() or None

        followers = max(
            _as_int(_pick_first(item, ("followers", "followersCount", "subscribersCount", "membersCount")), default=0),
            _as_int(_pick_first_path(item, ("author.followers", "group.membersCount")), default=0),
        )
        if followers > 0:
            subscribers_count = max(subscribers_count or 0, followers)

        seen_urls.add(item_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_pick_first(item, ("id", "videoId", "postId")) or _extract_handle_from_url(item_url) or item_url),
                video_url=item_url,
                title=str(_pick_first(item, ("title", "text", "caption", "description")) or "OK video")[:500],
                published_at=published_at,
                views=_as_int(_pick_first(item, ("views", "viewCount", "playCount", "viewsCount")))
                or _as_int(_pick_first_path(item, ("stats.views", "statistics.views", "video.views"))),
                likes=_as_int(_pick_first(item, ("likes", "likeCount", "likesCount")))
                or _as_int(_pick_first_path(item, ("stats.likes", "statistics.likes", "video.likes"))),
                comments=_as_int(_pick_first(item, ("comments", "commentCount", "commentsCount")))
                or _as_int(_pick_first_path(item, ("stats.comments", "statistics.comments", "video.comments"))),
                shares=_as_int(_pick_first(item, ("shares", "shareCount", "reposts")))
                or _as_int(_pick_first_path(item, ("stats.shares", "statistics.shares", "video.shares"))),
                duration_seconds=_as_int(_pick_first(item, ("duration", "videoDuration")), default=0)
                or _as_int(_pick_first_path(item, ("video.duration", "media.duration")), default=0)
                or None,
                extra={"source": "apify", "network": "ok"},
            )
        )

    return ParserResult(
        channel_external_id=channel_external_id,
        channel_title=channel_title,
        videos=videos,
        subscribers_count=subscribers_count,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else "OK Apify fallback ответил без публикаций за выбранный период.",
    )


async def parse_ok_http(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    # ok.ru/video/cNNNN is a channel URL (c-prefix = community/group ID), not a direct video.
    # Only treat pure numeric IDs (e.g. ok.ru/video/12345678) as direct video seeds.
    _is_ok_channel_url = bool(re.match(r"https?://(?:www\.)?ok\.ru/video/c\d+/?$", channel_url, re.IGNORECASE))
    
    # If this is a direct video URL, treat it as a seed and return immediately.
    if _is_valid_ok_video_url(channel_url) and not _is_ok_channel_url:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[
                ContentFactoryVideoPayload(
                    video_external_id=str(_extract_handle_from_url(channel_url) or channel_url),
                    video_url=channel_url,
                    title="OK video",
                    published_at=None,
                    views=0,
                    likes=0,
                    comments=0,
                    extra={"source": "direct_video_seed", "network": "ok"},
                )
            ],
            subscribers_count=None,
            sync_status="partial",
            sync_message="OK channel_url указан как прямая ссылка видео; сохранена seed-запись для дальнейшего обогащения.",
        )

    # If Apify is preferred and configured, try that first.
    prefer_apify = _feature_enabled("CONTENT_FACTORY_OK_PREFER_APIFY", "1")
    if prefer_apify:
        apify_result = await _parse_ok_apify_fallback(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
        if apify_result and apify_result.videos:
            apify_result.sync_message = (apify_result.sync_message or "") + (
                " " if apify_result.sync_message else ""
            ) + "Использован OK Apify (приоритетный источник)."
            return apify_result

    # Fallback: HTTP + external fetch if Apify unavailable or no results.
    timeout = aiohttp.ClientTimeout(total=_timeout_seconds("CONTENT_FACTORY_OK_HTTP_TIMEOUT_SECONDS", 15))
    headers = _headers_for_network("ok")
    proxy_chain = _proxy_attempt_chain("CONTENT_FACTORY_OK_PROXY_URL", include_direct=True)
    # Build URL list. ok.ru/video/cXXX is a video-channel URL - also try group/profile variants.
    _ok_urls: list[str] = [channel_url]
    _ok_c_m = re.match(r"https?://(?:www\.)?ok\.ru/video/c(\d+)$", channel_url, re.IGNORECASE)
    if _ok_c_m:
        _eid = _ok_c_m.group(1)
        _ok_urls += [
            f"https://ok.ru/group/{_eid}/video",
            f"https://ok.ru/group/{_eid}",
            f"https://ok.ru/profile/{_eid}/video",
            f"https://ok.ru/profile/{_eid}",
        ]
    _ok_urls.append(f"{channel_url.rstrip('/')}/video")
    _ok_urls = list(dict.fromkeys(_ok_urls))

    pages: list[str] = []
    fetch_log: list[str] = []
    antibot_log: list[str] = []
    proxy_failures: list[str] = []
    page_title: Optional[str] = None
    _ok_homepage_signs = ("одноклассники. общение с", "социальная сеть одноклассники", "место встречи с одноклассниками")
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for url in _ok_urls:
            got_page = False
            for attempt_proxy in proxy_chain:
                proxy_label = attempt_proxy or "direct"
                try:
                    async with session.get(url, proxy=attempt_proxy) as response:
                        html = await response.text()
                        if html and (response.status < 500):
                            antibot_sign = _detect_antibot_page(html)
                            if antibot_sign:
                                antibot_log.append(f"{url} via {proxy_label} -> anti-bot:{antibot_sign}")
                                fetch_log.append(f"{url} via {proxy_label} -> {response.status} (anti-bot, skipped)")
                                continue
                            # Skip if OK served its homepage instead of the channel page.
                            _soup_tmp = BeautifulSoup(html, "html.parser")
                            _page_t = (_soup_tmp.title.get_text(strip=True) if _soup_tmp.title else "").lower()
                            if any(s in _page_t for s in _ok_homepage_signs):
                                fetch_log.append(f"{url} via {proxy_label} -> {response.status} (homepage redirect, skipped)")
                            else:
                                pages.append(html)
                                fetch_log.append(f"{url} via {proxy_label} -> {response.status}")
                                if not page_title:
                                    page_title = _soup_tmp.title.get_text(strip=True) if _soup_tmp.title else None
                                got_page = True
                                break
                        else:
                            fetch_log.append(f"{url} via {proxy_label} -> {response.status}")
                except Exception as fetch_err:
                    err_text = str(fetch_err)[:140]
                    fetch_log.append(f"{url} via {proxy_label} -> error")
                    # Keep explicit hint when proxy provider responds with billing error.
                    if _is_proxy_billing_error(err_text):
                        proxy_failures.append(f"{proxy_label}:402 Payment Required")
                    continue
            if got_page:
                continue

    if not pages:
        for url in _ok_urls:
            external_html, external_provider = await _external_fetch_html(
                url, render_js=True, country="ru", network="ok"
            )
            if not external_html:
                continue
            antibot_sign = _detect_antibot_page(external_html)
            if antibot_sign:
                antibot_log.append(f"{url} via {external_provider} -> anti-bot:{antibot_sign}")
                continue
            _soup_tmp = BeautifulSoup(external_html, "html.parser")
            _page_t = (_soup_tmp.title.get_text(strip=True) if _soup_tmp.title else "").lower()
            if any(s in _page_t for s in _ok_homepage_signs):
                fetch_log.append(f"{url} via {external_provider} -> homepage redirect, skipped")
                continue
            pages.append(external_html)
            fetch_log.append(f"{url} via {external_provider} -> external fetch ok")
            if not page_title:
                page_title = _soup_tmp.title.get_text(strip=True) if _soup_tmp.title else None


    if not pages:
        # Apify already tried at the start of the function; no need to retry.
        # If this is a direct video URL, fall back to seed entry.
        if _is_valid_ok_video_url(channel_url):
            return ParserResult(
                channel_external_id=_extract_handle_from_url(channel_url),
                channel_title=None,
                videos=[
                    ContentFactoryVideoPayload(
                        video_external_id=str(_extract_handle_from_url(channel_url) or channel_url),
                        video_url=channel_url,
                        title="OK video",
                        published_at=None,
                        views=0,
                        likes=0,
                        comments=0,
                        extra={"source": "direct_video_seed", "network": "ok"},
                    )
                ],
                subscribers_count=None,
                sync_status="partial",
                sync_message=(
                    "OK канал недоступен, но сохранена прямая ссылка на видео из channel_url. "
                    + (
                        f"Обнаружен anti-bot: {'; '.join(antibot_log[:2])}. "
                        if antibot_log
                        else ""
                    )
                    + (
                        f"Прокси ошибки: {'; '.join(list(dict.fromkeys(proxy_failures))[:2])}. "
                        if proxy_failures
                        else ""
                    )
                ).strip(),
            )
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=(
                "OK канал не загружен. Попытки: " + ("; ".join(fetch_log[:3]) if fetch_log else "keine Versuche")
            ),
        )
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=(
                "OK недоступен или не отдал страницу канала. "
                + (
                    f"Обнаружен anti-bot: {'; '.join(antibot_log[:2])}. "
                    + (
                        f"Прокси ошибки: {'; '.join(list(dict.fromkeys(proxy_failures))[:2])}. "
                        if proxy_failures
                        else ""
                    )
                    + "Укажите CONTENT_FACTORY_OK_PROXY_URL или CONTENT_FACTORY_PROXY_URL."
                    if antibot_log
                    else ""
                )
            ).strip(),
        )

    _ = (period_days, start_date, end_date)
    
    videos: list[ContentFactoryVideoPayload] = []
    seen_urls: set[str] = set()

    # Preferred path: parse OK video cards to get title/views/duration.
    for page_html in pages:
        for video_url, title, views, likes, comments, duration_seconds in _extract_ok_video_candidates(page_html):
            if video_url in seen_urls:
                continue
            seen_urls.add(video_url)
            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                    video_url=video_url,
                    title=title,
                    published_at=None,
                    views=views,
                    likes=likes,
                    comments=comments,
                    duration_seconds=duration_seconds,
                    extra={"source": "http_scraper", "network": "ok"},
                )
            )
    
    for pattern in (
        r"https?://(?:www\.)?ok\.ru/video/[a-zA-Z0-9_\-:.]+",
        r"/video/[a-zA-Z0-9_\-:.]+",
    ):
        for page_html in pages:
            for match in re.finditer(pattern, page_html):
                video_url = match.group(0).rstrip('"\'')
                if video_url.startswith("/"):
                    video_url = f"https://ok.ru{video_url}"
                if not _is_valid_ok_video_url(video_url):
                    continue
                if video_url in seen_urls:
                    continue
                seen_urls.add(video_url)
                videos.append(
                    ContentFactoryVideoPayload(
                        video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                        video_url=video_url,
                        title="OK video",
                        published_at=None,
                        views=0,
                        likes=0,
                        comments=0,
                        extra={"source": "http_scraper", "network": "ok"},
                    )
                )

    # Additional raw JSON-state fallback: many OK pages keep numeric videoId in scripts.
    if not videos:
        for page_html in pages:
            for m in re.finditer(r'"videoId"\s*:\s*"?(\d{6,})"?', page_html):
                video_url = f"https://ok.ru/video/{m.group(1)}"
                if not _is_valid_ok_video_url(video_url) or video_url in seen_urls:
                    continue
                seen_urls.add(video_url)
                videos.append(
                    ContentFactoryVideoPayload(
                        video_external_id=str(m.group(1)),
                        video_url=video_url,
                        title="OK video",
                        published_at=None,
                        views=0,
                        likes=0,
                        comments=0,
                        extra={"source": "json_state", "network": "ok"},
                    )
                )

    # OK is a full JavaScript SPA — individual video URLs are not in hrefs but
    # embedded in the page JS state.  Use browser rendering to extract them.
    if not videos:
        browser_video_urls = await _extract_ok_video_ids_via_browser(channel_url)
        for video_url in browser_video_urls:
            if not _is_valid_ok_video_url(video_url):
                continue
            if video_url in seen_urls:
                continue
            seen_urls.add(video_url)
            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                    video_url=video_url,
                    title="OK video",
                    published_at=None,
                    views=0,
                    likes=0,
                    comments=0,
                    extra={"source": "browser_js_state", "network": "ok"},
                )
            )

    if not videos:
        # Fallback #4: use generic discovery mechanism
        discovered = await _discover_channel_video_links("ok", channel_url)
        for item in discovered:
            video_url = str(item.video_url or "").strip()
            if not video_url or video_url in seen_urls:
                continue
            seen_urls.add(video_url)
            videos.append(item)

    await _enrich_videos_from_pages(videos, headers=headers)

    return ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        subscribers_count=None,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else (
            "Не удалось извлечь публикации из OK. "
            f"Попытки: {'; '.join(fetch_log[:4]) or 'нет ответа'}"
        ),
    )


async def parse_rutube_http(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    timeout = aiohttp.ClientTimeout(total=45)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)

    # -- Attempt 1: Rutube public REST API (most reliable, SPA-agnostic) --
    _rutube_person_id_m = re.search(r"/channel/(\d+)", channel_url, re.IGNORECASE)
    api_videos: list[ContentFactoryVideoPayload] = []
    api_channel_title: Optional[str] = None
    api_subscribers: Optional[int] = None
    if _rutube_person_id_m:
        person_id = _rutube_person_id_m.group(1)
        api_url = f"https://rutube.ru/api/video/person/{person_id}/?page=1&page_size=50&ordering=-created_ts&format=json"
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as api_session:
                async with api_session.get(api_url) as api_resp:
                    if api_resp.status < 400:
                        api_data = await api_resp.json(content_type=None)
                        results_list = api_data.get("results") or []
                        for item in results_list:
                            # Skip live streams — they appear in the video list API but are
                            # broadcast events, not regular uploaded videos.
                            if item.get("is_live") or item.get("video_type") == "live":
                                continue
                            _item_title_raw = str(item.get("title") or "").strip().lower()
                            if "прямой эфир" in _item_title_raw:
                                continue
                            video_url = str(item.get("video_url") or item.get("url") or "").strip()
                            if not video_url:
                                vid_id = str(item.get("id") or "").strip()
                                if vid_id:
                                    video_url = f"https://rutube.ru/video/{vid_id}/"
                            if not video_url or not _is_valid_rutube_video_url(video_url):
                                continue
                            published_at = _parse_any_datetime(item.get("created_ts") or item.get("publication_ts"))
                            if published_at and not _in_window(published_at, window_start, window_end):
                                continue
                            title = str(item.get("title") or "Rutube video").strip() or "Rutube video"
                            views = _as_int(item.get("hits"), default=0)
                            likes = _as_int(item.get("likes"), default=0)
                            comments = _as_int(item.get("comments"), default=0)
                            duration_seconds = _as_int(item.get("duration"), default=0) or None
                            if not api_channel_title:
                                author = item.get("author") or {}
                                if isinstance(author, dict):
                                    api_channel_title = str(author.get("name") or "").strip() or None
                                    api_subscribers = _as_int(author.get("subscribers_count"), default=0) or None
                            is_short = _is_rutube_short_video(video_url, duration_seconds)
                            api_videos.append(
                                ContentFactoryVideoPayload(
                                    video_external_id=str(item.get("id") or _extract_handle_from_url(video_url) or video_url),
                                    video_url=video_url,
                                    title=title[:500],
                                    published_at=published_at,
                                    views=views,
                                    likes=likes,
                                    comments=comments,
                                    duration_seconds=duration_seconds,
                                    extra={
                                        "source": "rutube_api",
                                        "network": "rutube",
                                        "is_short": is_short,
                                        "short_format": "short" if is_short else "video",
                                    },
                                )
                            )
        except Exception as api_exc:
            logger.debug("[content_factory] Rutube API fetch failed for %s: %s", channel_url, api_exc)

    if api_videos:
        return ParserResult(
            channel_external_id=person_id if _rutube_person_id_m else _extract_handle_from_url(channel_url),
            channel_title=api_channel_title,
            videos=api_videos,
            subscribers_count=api_subscribers,
            sync_status="ok",
            sync_message=None,
        )

    # -- Attempt 2: HTML scraping fallback --
    request_urls = [channel_url]
    if "rutube.ru" in channel_url and "www.rutube.ru" not in channel_url:
        request_urls.append(channel_url.replace("https://rutube.ru", "https://www.rutube.ru"))
    elif "www.rutube.ru" in channel_url:
        request_urls.append(channel_url.replace("https://www.rutube.ru", "https://rutube.ru"))

    html: Optional[str] = None
    last_status: Optional[int] = None
    last_error: Optional[Exception] = None

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for attempt in range(1, 4):
            for request_url in request_urls:
                try:
                    async with session.get(request_url) as response:
                        last_status = response.status
                        body = await response.text()
                        if response.status < 400:
                            html = body
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                    last_error = exc
                    continue
            if html is not None:
                break
            if attempt < 3:
                await asyncio.sleep(float(attempt))

    if html is None:
        if last_error is not None:
            return ParserResult(
                channel_external_id=_extract_handle_from_url(channel_url),
                channel_title=None,
                videos=[],
                subscribers_count=None,
                sync_status="partial",
                sync_message=f"Rutube временно недоступен (сетевая ошибка): {last_error}",
            )
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=f"Rutube недоступен или вернул ошибку ({last_status or 'unknown'}).",
        )

    soup = BeautifulSoup(html, "html.parser")
    page_title = (soup.title.get_text(strip=True) if soup.title else "") or None
    subscribers_count = _extract_count_by_regex(
        html,
        (
            r'"subscribersCount"\s*:\s*"?(\d+)"?',
            r'"followers"\s*:\s*"?(\d+)"?',
            r'Подписчик(?:ов|а)?\s*</[^>]+>\s*<[^>]+>([0-9\s]+)<',
        ),
    )

    videos: list[ContentFactoryVideoPayload] = []

    for idx, (video_url, title, published_at, views, likes, comments, duration_seconds) in enumerate(
        _extract_rutube_video_candidates(html, "https://rutube.ru")
    ):
        if published_at and not _in_window(published_at, window_start, window_end):
            continue
        is_short = _is_rutube_short_video(video_url, duration_seconds)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or f"rutube_{idx}"),
                video_url=video_url,
                title=title,
                published_at=published_at,
                views=views,
                likes=likes,
                comments=comments,
                duration_seconds=duration_seconds,
                extra={
                    "source": "http_scraper",
                    "network": "rutube",
                    "is_short": is_short,
                    "short_format": "short" if is_short else "video",
                },
            )
        )

    await _enrich_videos_from_pages(videos, headers=headers)

    return ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        subscribers_count=subscribers_count or None,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else "Не удалось извлечь публикации из Rutube: вероятно, изменилась структура страницы.",
    )


async def parse_likee_http(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    token = _pick_apify_token()
    likee_actor_id = _secret("CONTENT_FACTORY_LIKEE_APIFY_ACTOR_ID", "sashaebashu~likee-scraper")
    use_likee_apify = _feature_enabled("CONTENT_FACTORY_LIKEE_USE_APIFY", "1")
    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)

    # Likee channel pages are often geo/anti-bot protected and redirect to homepage.
    # Apify is now the primary method; fallback to internal API if needed.
    if use_likee_apify and token and likee_actor_id:
        apify_targets: list[str] = []
        if _is_valid_likee_video_url(channel_url):
            apify_targets = [channel_url]
        else:
            discovered_links = await _discover_channel_video_links("likee", channel_url)
            apify_targets = [
                str(v.video_url or "").strip()
                for v in discovered_links
                if _is_valid_likee_video_url(str(v.video_url or "").strip())
            ][:20]
            # Some actors accept profile URLs directly; include channel URL as a fallback target.
            if channel_url not in apify_targets:
                apify_targets.append(channel_url)

        likee_max_items = _secret_int("CONTENT_FACTORY_LIKEE_APIFY_MAX_ITEMS", 200, min_value=20, max_value=2000)
        apify_payload_candidates: list[dict[str, Any]] = [
            {"urls": apify_targets, "maxItems": likee_max_items},
            {"links": apify_targets, "maxItems": likee_max_items},
            {"url": apify_targets[0], "maxItems": likee_max_items} if apify_targets else {},
            {"startUrls": [{"url": u} for u in apify_targets], "maxItems": likee_max_items},
        ]

        apify_items: list[dict[str, Any]] = []
        apify_error: Optional[str] = None
        for payload in apify_payload_candidates:
            if not payload:
                continue
            try:
                items = await _run_apify_actor(actor_id=likee_actor_id, token=token, payload=payload)
                if items:
                    apify_items = items
                    break
            except Exception as exc:
                apify_error = str(exc)

        apify_videos: list[ContentFactoryVideoPayload] = []
        for item in apify_items:
            item_url = str(
                _pick_first(item, ("url", "videoUrl", "postUrl", "shareUrl", "link", "permalink"))
                or _pick_first_path(item, ("video.url", "video.shareUrl", "post.url", "result.url"))
                or ""
            ).strip()
            if not item_url or not _is_valid_likee_video_url(item_url):
                continue

            published_at = _parse_any_datetime(
                _pick_first(item, ("createdAt", "createTime", "timestamp", "publishedAt", "time"))
                or _pick_first_path(item, ("video.createdAt", "video.createTime", "post.timestamp"))
            )
            if published_at and not _in_window(published_at, window_start, window_end):
                continue

            apify_videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(
                        _pick_first(item, ("id", "videoId", "postId", "aweme_id"))
                        or _extract_handle_from_url(item_url)
                        or item_url
                    ),
                    video_url=item_url,
                    title=str(_pick_first(item, ("title", "caption", "text", "desc")) or "Likee video")[:500],
                    published_at=published_at,
                    views=_as_int(_pick_first(item, ("playCount", "viewCount", "views", "videoViews")))
                    or _as_int(_pick_first_path(item, ("stats.playCount", "statistics.views", "video.views"))),
                    likes=_as_int(_pick_first(item, ("likeCount", "likes", "diggCount")))
                    or _as_int(_pick_first_path(item, ("stats.likeCount", "statistics.likes", "video.likes"))),
                    comments=_as_int(_pick_first(item, ("commentCount", "comments")))
                    or _as_int(_pick_first_path(item, ("stats.commentCount", "statistics.comments", "video.comments"))),
                    shares=_as_int(_pick_first(item, ("shareCount", "shares")))
                    or _as_int(_pick_first_path(item, ("stats.shareCount", "statistics.shares", "video.shares"))),
                    duration_seconds=(
                        _as_int(_pick_first(item, ("duration", "videoDuration")), default=0)
                        or _as_int(_pick_first_path(item, ("video.duration", "media.duration")), default=0)
                        or None
                    ),
                    extra={"source": "apify", "network": "likee", "is_short": True},
                )
            )

        if apify_videos:
            return ParserResult(
                channel_external_id=_extract_handle_from_url(channel_url),
                channel_title=None,
                videos=apify_videos,
                subscribers_count=None,
                sync_status="ok",
                sync_message="Likee получен через Apify actor.",
            )

        if apify_error:
            logger.warning("[content_factory] Likee Apify fallback failed for %s: %s", channel_url, apify_error)

    internal_videos, internal_subscribers, internal_title, internal_message = await _likee_fetch_videos_via_internal_api(
        channel_url=channel_url,
        window_start=window_start,
        window_end=window_end,
    )
    if internal_videos:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=internal_title,
            videos=internal_videos,
            subscribers_count=internal_subscribers,
            sync_status="ok",
            sync_message="Likee получен через internal web API fallback.",
        )

    timeout = aiohttp.ClientTimeout(total=_timeout_seconds("CONTENT_FACTORY_LIKEE_HTTP_TIMEOUT_SECONDS", 15))
    headers = _headers_for_network("likee")
    html: Optional[str] = None
    antibot_attempts: list[str] = []
    proxy_failures: list[str] = []
    proxy_chain = _proxy_attempt_chain("CONTENT_FACTORY_LIKEE_PROXY_URL", include_direct=True)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for likee_proxy in proxy_chain:
            proxy_label = likee_proxy or "direct"
            try:
                async with session.get(channel_url, proxy=likee_proxy) as response:
                    body = await response.text()
                    if response.status >= 400:
                        continue
                    antibot_sign = _detect_antibot_page(body)
                    if antibot_sign:
                        antibot_attempts.append(f"{proxy_label}:{antibot_sign}")
                        continue
                    html = body
                    break
            except Exception as page_err:
                err_text = str(page_err)[:140]
                if _is_proxy_billing_error(err_text):
                    proxy_failures.append(f"{proxy_label}:402 Payment Required")
                continue

    if not html:
        external_html, external_provider = await _external_fetch_html(
            channel_url, render_js=True, network="likee"
        )
        if external_html:
            html = external_html

    if not html:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=(
                "Likee недоступен или вернул anti-bot/CAPTCHA на всех попытках. "
                + (f"Примеры: {'; '.join(antibot_attempts[:2])}. " if antibot_attempts else "")
                + (f"Прокси ошибки: {'; '.join(list(dict.fromkeys(proxy_failures))[:2])}. " if proxy_failures else "")
                + "Проверьте CONTENT_FACTORY_LIKEE_PROXY_URL/CONTENT_FACTORY_PROXY_URL или /app/proxy.txt, либо задайте Scrapfly/ScrapingBee ключ."
            ),
        )

    antibot_sign = _detect_antibot_page(html)
    if antibot_sign:
        external_html, external_provider = await _external_fetch_html(
            channel_url, render_js=True, network="likee"
        )
        if external_html and not _detect_antibot_page(external_html):
            html = external_html
            antibot_sign = None

    if antibot_sign:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=(
                f"Likee вернул anti-bot/CAPTCHA страницу ({antibot_sign}). "
                "Укажите CONTENT_FACTORY_LIKEE_PROXY_URL или CONTENT_FACTORY_PROXY_URL, либо Scrapfly/ScrapingBee ключ, и повторите синк."
            ),
        )

    soup = BeautifulSoup(html, "html.parser")
    page_title = (soup.title.get_text(strip=True) if soup.title else "") or None
    subscribers_count = _extract_count_by_regex(
        html,
        (
            r'"followerCount"\s*:\s*"?(\d+)"?',
            r'"followers"\s*:\s*"?(\d+)"?',
        ),
    )

    videos: list[ContentFactoryVideoPayload] = []

    for idx, (video_url, title, published_at, views, likes, comments, duration_seconds) in enumerate(
        _extract_likee_video_candidates(html, "https://likee.video")
    ):
        if published_at and not _in_window(published_at, window_start, window_end):
            continue
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or f"likee_{idx}"),
                video_url=video_url,
                title=title,
                published_at=published_at,
                views=views,
                likes=likes,
                comments=comments,
                duration_seconds=duration_seconds,
                extra={"source": "http_scraper", "network": "likee", "is_short": True},
            )
        )

    if not videos:
        browser_links = await _collect_links_via_browser(
            page_url=channel_url,
            selectors=["a[href*='/video/']", "a[href*='likee.video']"],
            include_pattern=r"likee\.video/.*/video/|likee\.video/video/",
            max_links=40,
        )
        for idx, video_url in enumerate(browser_links):
            if not _is_valid_likee_video_url(video_url):
                continue
            videos.append(
                ContentFactoryVideoPayload(
                    video_external_id=str(_extract_handle_from_url(video_url) or f"likee_browser_{idx}"),
                    video_url=video_url,
                    title="Likee video",
                    published_at=None,
                    views=0,
                    likes=0,
                    comments=0,
                    extra={"source": "browser_scraper", "network": "likee", "is_short": True},
                )
            )

    await _enrich_videos_from_pages(videos, headers=headers)

    return ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        subscribers_count=subscribers_count or None,
        sync_status="ok" if videos else "partial",
        sync_message=None
        if videos
        else (
            f"Не удалось извлечь публикации из Likee: профильная страница недоступна для парсинга. "
            f"Internal API: {internal_message or 'нет данных'}. "
            "Для Apify actor используйте прямые URL видео вида /video/..."
        ),
    )


def _dzen_fetch_with_sso(channel_url: str) -> tuple[str, dict[str, str]]:
    """
    Synchronous helper: complete the Yandex/Dzen SSO auto-login flow and return
    the full HTML of the channel page plus authenticated session cookies.
    Must be called via run_in_executor.
    """
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    last_html = ""
    last_cookies: dict[str, str] = {}
    for attempt in range(1, 6):
        s = _sync_requests.Session()
        s.headers.update(hdrs)
        try:
            # Step 1: hit the channel URL – Dzen may redirect to SSO flow.
            r1 = s.get(channel_url, timeout=30, allow_redirects=True)
            html1 = r1.text or ""
            last_html = html1

            # If we already got video/article links, use this response as-is.
            if re.search(r"dzen\.ru/(?:video/watch|short-video|a)/", html1):
                return html1, dict(s.cookies)

            # Step 2: extract and POST the hidden SSO form so Dzen sets a session cookie.
            m = re.search(r"var it\s*=\s*(\{.+?\});", html1)
            if m:
                try:
                    it_data = json.loads(m.group(1).replace(r"\u002F", "/"))
                    container_m = re.search(r"element2\.value\s*=\s*'([^']+)'", html1)
                    container = container_m.group(1) if container_m else ""
                    host = it_data.get("host", "")
                    retpath = it_data.get("retpath", "")
                    if host and retpath:
                        s.post(
                            host,
                            data={"retpath": retpath, "container": container, "dzen": "1"},
                            timeout=30,
                        )
                except Exception:
                    pass

            # Step 3: request the actual channel page with the updated session cookie.
            r2 = s.get(channel_url, timeout=60, allow_redirects=True)
            html2 = r2.text or ""
            if html2:
                last_html = html2
            last_cookies = dict(s.cookies)

            # Success criteria for a useful page payload.
            if re.search(r"dzen\.ru/(?:video/watch|short-video|a)/", html2) or len(html2) > 10_000:
                return html2, last_cookies

        except Exception:
            pass
        finally:
            s.close()

        if attempt < 5:
            _time.sleep(1.0 * attempt)

    return last_html, last_cookies


def _dzen_enrich_sync(
    videos: list[ContentFactoryVideoPayload],
    cookies: dict[str, str],
    *,
    max_videos: int = 40,
) -> None:
    """
    Synchronous Dzen video enrichment using an SSO-authenticated requests.Session.
    Must be called via run_in_executor from async context.
    """
    if not videos:
        return
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    s = _sync_requests.Session()
    s.headers.update(hdrs)
    if cookies:
        s.cookies.update(cookies)
    try:
        for video in videos[:max_videos]:
            # Skip already-complete records.
            if (
                int(video.views or 0) > 0
                and video.published_at is not None
                and video.duration_seconds is not None
            ):
                continue
            try:
                resp = s.get(str(video.video_url), timeout=20, allow_redirects=True)
                if resp.status_code >= 400:
                    continue
                html = resp.text
                # Skip if response is the SSO redirect shell or too short to be a video page.
                if "sso.passport.yandex" in str(resp.url) or len(html) < 5_000:
                    continue
                metrics = _extract_video_page_metrics(html)
                if int(video.views or 0) <= 0:
                    video.views = max(int(video.views or 0), int(metrics.get("views") or 0))
                if int(video.likes or 0) <= 0:
                    video.likes = max(int(video.likes or 0), int(metrics.get("likes") or 0))
                if int(video.comments or 0) <= 0:
                    video.comments = max(int(video.comments or 0), int(metrics.get("comments") or 0))
                if video.published_at is None and metrics.get("published_at") is not None:
                    video.published_at = metrics["published_at"]
                if video.duration_seconds is None and metrics.get("duration_seconds"):
                    video.duration_seconds = int(metrics["duration_seconds"] or 0) or None
                title = str(metrics.get("title") or "").strip()
                if title:
                    current = (video.title or "").strip().lower()
                    if not current or current.startswith("dzen post"):
                        video.title = title[:500]
            except Exception:
                continue
    finally:
        s.close()


async def parse_dzen_http(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    diagnostics: list[str] = []
    _dzen_cookies: dict[str, str] = {}
    try:
        loop = asyncio.get_event_loop()
        html, _dzen_cookies = await loop.run_in_executor(
            None, functools.partial(_dzen_fetch_with_sso, channel_url)
        )
        # Also try /video, /videos and /short-video subtabs — they may contain video-specific SSR cards.
        _extra_tabs = []
        _video_tab_url = f"{channel_url.rstrip('/')}/video"
        if _video_tab_url != channel_url:
            _extra_tabs.append(_video_tab_url)
        _videos_tab_url = f"{channel_url.rstrip('/')}/videos"
        if _videos_tab_url not in _extra_tabs and _videos_tab_url != channel_url:
            _extra_tabs.append(_videos_tab_url)
        _short_tab_url = f"{channel_url.rstrip('/')}/short-video"
        if _short_tab_url not in _extra_tabs and _short_tab_url != channel_url:
            _extra_tabs.append(_short_tab_url)
        for _extra_url in _extra_tabs:
            try:
                _html_extra, _extra_cookies = await loop.run_in_executor(
                    None, functools.partial(_dzen_fetch_with_sso, _extra_url)
                )
                if _html_extra and len(_html_extra) > 10_000:
                    html = html + f"\n<!-- dzen_tab:{_extra_url} -->\n" + _html_extra
                    if _extra_cookies and not _dzen_cookies:
                        _dzen_cookies = _extra_cookies
            except Exception:
                pass
    except Exception as exc:
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            subscribers_count=None,
            sync_status="partial",
            sync_message=f"Ошибка при загрузке страницы Dzen: {exc}",
        )

    if html:
        if re.search(r'<meta\s+property="og:url"\s+content="https://dzen\.ru/?"', html, flags=re.IGNORECASE):
            diagnostics.append("получена общая витрина dzen.ru вместо страницы канала")
        if not re.search(r"dzen\.ru/(?:video/watch|short-video|a)/", html):
            diagnostics.append("в HTML нет ссылок на публикации канала")

    soup = BeautifulSoup(html, "html.parser")
    page_title = (soup.title.get_text(strip=True) if soup.title else "") or None
    subscribers_count = _extract_count_by_regex(
        html,
        (
            r'"subscriberCount"\s*:\s*"?(\d+)"?',
            r'"followersCount"\s*:\s*"?(\d+)"?',
        ),
    )

    window_start, window_end = _window_bounds(period_days=period_days, start_date=start_date, end_date=end_date)
    videos: list[ContentFactoryVideoPayload] = []
    seen_urls: set[str] = set()

    # Parse SSR video cards with richer metrics (title, views, relative date).
    for video_url, title, published_at, views, duration_seconds, is_short in _extract_dzen_video_card_candidates(html):
        if video_url in seen_urls:
            continue
        if published_at and not _in_window(published_at, window_start, window_end):
            continue
        seen_urls.add(video_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                video_url=video_url,
                title=title[:500],
                published_at=published_at,
                views=views,
                likes=0,
                comments=0,
                duration_seconds=duration_seconds,
                extra={"source": "http_scraper", "network": "dzen", "is_short": is_short, "short_format": "short" if is_short else "video"},
            )
        )

    # Embedded JS-state extraction — covers cases when Dzen doesn't render <article> cards.
    for video_url, title, published_at, views, duration_seconds, is_short in _extract_dzen_json_state_candidates(html):
        if video_url in seen_urls:
            continue
        if published_at and not _in_window(published_at, window_start, window_end):
            continue
        seen_urls.add(video_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                video_url=video_url,
                title=title[:500],
                published_at=published_at,
                views=views,
                likes=0,
                comments=0,
                duration_seconds=duration_seconds,
                extra={"source": "http_json_state", "network": "dzen", "is_short": is_short, "short_format": "short" if is_short else "video"},
            )
        )

    # Structured data as secondary source (add only missing URLs).
    for obj in _extract_video_objects_from_json_ld(html):
        video_url = str(obj.get("url") or "").strip()
        video_url = _clean_dzen_video_url(video_url)
        if not re.match(r"^https?://dzen\.ru/(?:video/watch|short-video)/[A-Za-z0-9_-]+$", video_url):
            continue
        if not video_url or video_url in seen_urls:
            continue
        seen_urls.add(video_url)
        published_at = _parse_any_datetime(obj.get("uploadDate") or obj.get("datePublished"))
        if published_at and not _in_window(published_at, window_start, window_end):
            continue
        views = _as_int(obj.get("interactionCount"), default=0)
        likes = 0
        comments = 0
        interaction_stat = obj.get("interactionStatistic")
        if isinstance(interaction_stat, list):
            for stat in interaction_stat:
                if not isinstance(stat, dict):
                    continue
                interaction_type = str(stat.get("interactionType") or "").lower()
                count = _as_int(stat.get("userInteractionCount"), default=0)
                if "watch" in interaction_type or "view" in interaction_type:
                    views = max(views, count)
                elif "like" in interaction_type:
                    likes = max(likes, count)
                elif "comment" in interaction_type:
                    comments = max(comments, count)
        elif isinstance(interaction_stat, dict):
            interaction_type = str(interaction_stat.get("interactionType") or "").lower()
            count = _as_int(interaction_stat.get("userInteractionCount"), default=0)
            if "watch" in interaction_type or "view" in interaction_type:
                views = max(views, count)
            elif "like" in interaction_type:
                likes = max(likes, count)
            elif "comment" in interaction_type:
                comments = max(comments, count)

        title = str(obj.get("name") or obj.get("headline") or "Dzen post")
        is_short = _is_dzen_short_video(video_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                video_url=video_url,
                title=title[:500],
                published_at=published_at,
                views=views,
                likes=likes,
                comments=comments,
                extra={"source": "http_scraper", "network": "dzen", "is_short": is_short, "short_format": "short" if is_short else "video"},
            )
        )

    # Fallback by URL pattern: explicit video links.
    for match in re.finditer(r"https?://dzen\.ru/(?:video/watch|short-video)/[a-zA-Z0-9\-_]+", html):
        video_url = _clean_dzen_video_url(match.group(0))
        if video_url in seen_urls:
            continue
        seen_urls.add(video_url)
        is_short = _is_dzen_short_video(video_url)
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=str(_extract_handle_from_url(video_url) or video_url),
                video_url=video_url,
                title="Dzen post",
                published_at=None,
                views=0,
                likes=0,
                comments=0,
                extra={"source": "http_scraper", "network": "dzen", "is_short": is_short, "short_format": "short" if is_short else "video"},
            )
        )

    if not videos:
        discovered = await _discover_channel_video_links("dzen", channel_url)
        if discovered:
            videos.extend(discovered)
            diagnostics.append("использован browser discovery по странице канала")

    # Use SSO-authenticated session for enrichment — plain aiohttp is blocked by Dzen's SSO wall.
    await loop.run_in_executor(
        None, functools.partial(_dzen_enrich_sync, videos, _dzen_cookies)
    )

    return ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        subscribers_count=subscribers_count or None,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else (
            "HTTP-сбор Дзен не дал публикаций за выбранный период. "
            + ("; ".join(diagnostics[:3]) if diagnostics else "")
        ),
    )


async def parse_dzen_browser(
    channel_url: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    _ = (period_days, start_date, end_date)
    browser_enabled = _secret("CONTENT_FACTORY_DZEN_BROWSER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not browser_enabled:
        return await parse_dzen_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        fallback = await parse_dzen_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
        if fallback.videos:
            fallback.sync_message = "Playwright не установлен, использован HTTP fallback для Дзен."
            fallback.sync_status = "partial"
            return fallback
        return ParserResult(
            channel_external_id=_extract_handle_from_url(channel_url),
            channel_title=None,
            videos=[],
            sync_status="partial",
            sync_message=f"Playwright не установлен и HTTP fallback пустой: {exc}",
        )

    videos: list[ContentFactoryVideoPayload] = []
    page_title: Optional[str] = None
    browser_error: Optional[str] = None
    entries: list[dict[str, Any]] = []
    fallback_message: Optional[str] = None

    browser_max_links = _secret_int("CONTENT_FACTORY_DZEN_BROWSER_MAX_LINKS", 160, min_value=20, max_value=2000)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            raw_entries: list[dict[str, Any]] = []
            _base = channel_url.rstrip("/")
            request_urls = list(dict.fromkeys([channel_url, f"{_base}/video", f"{_base}/videos", f"{_base}/short-video"]))
            for request_url in request_urls:
                try:
                    await page.goto(request_url, wait_until="domcontentloaded", timeout=90_000)

                    # Give lazy lists a chance to render and then perform scroll warmup.
                    # Dzen is a heavy React SPA — multiple scroll passes help trigger lazy loading.
                    try:
                        await page.wait_for_timeout(2000)
                        for _scroll_pass in range(4):
                            await page.mouse.wheel(0, 2500)
                            await page.wait_for_timeout(700)
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    if not page_title:
                        page_title = await page.title()

                    candidate_entries = await page.evaluate(
                r"""
                            ({ maxLinks }) => {
                                const unique = new Map();
                                const selectors = [
                                    'a[href*="/video/watch/"]',
                                    'a[href*="/short-video/"]',
                                    'a[href*="dzen.ru/video/watch/"]',
                                    'a[href*="dzen.ru/short-video/"]',
                                ];

                                for (const selector of selectors) {
                                    const nodes = Array.from(document.querySelectorAll(selector));
                                    for (const node of nodes) {
                                        const rawHref = (node.getAttribute('href') || '').trim();
                                        if (!rawHref) continue;

                                        const href = rawHref.startsWith('http')
                                            ? rawHref
                                            : new URL(rawHref, window.location.origin).toString();

                                        if (!/dzen\.ru\/(video\/watch|short-video)\//.test(href)) continue;

                                        const title = (node.textContent || '').trim()
                                            || node.getAttribute('title')
                                            || 'Dzen post';

                                        if (!unique.has(href)) {
                                            unique.set(href, { href, title });
                                        }
                                        if (unique.size >= maxLinks) break;
                                    }
                                    if (unique.size >= maxLinks) break;
                                }

                                return Array.from(unique.values());
                            }
                """
                    ,
                        {"maxLinks": max(20, int(browser_max_links))},
            )
                    if isinstance(candidate_entries, list):
                        tab_hint = "short-video" if "/short-video" in request_url else "video"
                        for item in candidate_entries:
                            if not isinstance(item, dict):
                                continue
                            item["_tab_hint"] = tab_hint
                            raw_entries.append(item)
                except Exception:
                    continue

            if isinstance(raw_entries, list):
                dedup: dict[str, dict[str, Any]] = {}
                for item in raw_entries:
                    href = str(item.get("href") or "").strip()
                    if not href:
                        continue
                    dedup[href] = item
                entries = list(dedup.values())
            await context.close()
            await browser.close()
    except Exception as exc:
        browser_error = str(exc)

    for idx, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        href = str(entry.get("href") or "").strip()
        if not href:
            continue
        title = str(entry.get("title") or "").strip() or f"Dzen post #{idx + 1}"
        is_short = _is_dzen_short_video(href, tab_hint=str(entry.get("_tab_hint") or ""))
        videos.append(
            ContentFactoryVideoPayload(
                video_external_id=href,
                video_url=href,
                title=title[:500],
                published_at=None,
                views=0,
                likes=0,
                comments=0,
                extra={"source": "browser_scraper", "network": "dzen", "is_short": is_short, "short_format": "short" if is_short else "video", "tab_hint": str(entry.get("_tab_hint") or "")},
            )
        )

    # Enrich videos with detailed metrics from individual video pages
    dzen_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    await _enrich_videos_from_pages(videos, headers=dzen_headers, concurrency=4)

    # Browser mode is unstable for some channels, so merge with HTTP fallback when needed.
    # This keeps browser advantages while backfilling missing dates/metrics.
    fallback_needed = (not videos) or (sum(1 for v in videos if v.published_at is not None) < max(1, len(videos) // 4))
    if fallback_needed:
        fallback = await parse_dzen_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
        fallback_message = fallback.sync_message
        merged_by_url: dict[str, ContentFactoryVideoPayload] = {}
        for item in fallback.videos:
            merged_by_url[str(item.video_url)] = item

        for item in videos:
            key = str(item.video_url)
            if key not in merged_by_url:
                merged_by_url[key] = item
                continue
            base = merged_by_url[key]
            base.views = max(int(base.views or 0), int(item.views or 0))
            base.likes = max(int(base.likes or 0), int(item.likes or 0))
            base.comments = max(int(base.comments or 0), int(item.comments or 0))
            if base.published_at is None and item.published_at is not None:
                base.published_at = item.published_at
            if (not base.title or base.title.lower() == "dzen post") and item.title:
                base.title = item.title
            if base.duration_seconds is None and item.duration_seconds is not None:
                base.duration_seconds = item.duration_seconds

        videos = list(merged_by_url.values())
        if not page_title:
            page_title = fallback.channel_title

        if browser_error and videos:
            return ParserResult(
                channel_external_id=_extract_handle_from_url(channel_url),
                channel_title=page_title,
                videos=videos,
                sync_status="partial",
                sync_message=f"Браузерный скраппинг частично нестабилен, применен HTTP fallback: {browser_error[:180]}",
            )

    return ParserResult(
        channel_external_id=_extract_handle_from_url(channel_url),
        channel_title=page_title,
        videos=videos,
        sync_status="ok" if videos else "partial",
        sync_message=None if videos else (
            fallback_message
            or (
                "Не удалось извлечь публикации из Дзен через браузерный скраппинг."
                + (f" Ошибка браузера: {browser_error[:180]}" if browser_error else "")
            )
        ),
    )


async def parse_stub(
    channel_url: str,
    network: str,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    platform = get_platform(network)
    logger.info("[content_factory] parser stub for network=%s url=%s period_days=%s", network, channel_url, period_days)
    if platform.status == "credentials":
        message = (
            f"Источник {platform.label} добавлен. Коннектор рассчитан на {platform.collection_method} "
            "и будет активирован после подключения внешних ключей/API."
        )
    else:
        message = (
            f"Источник {platform.label} добавлен. Архитектура под {platform.collection_method} подготовлена, "
            "но сам парсер еще не включен в этой сборке."
        )

    return ParserResult(
        channel_external_id=None,
        channel_title=None,
        videos=[],
        subscribers_count=None,
        sync_status="partial",
        sync_message=message,
    )


def _make_channel_seed_video(
    network: str,
    channel_url: str,
    channel_title: Optional[str] = None,
) -> ContentFactoryVideoPayload:
    """
    Build a minimal seed record for a channel so the DB always has at least
    one row per channel regardless of anti-bot / API failures.
    The seed is flagged with source='channel_seed' so downstream enrichment
    jobs can detect and attempt metric recovery separately.
    """
    handle = _extract_handle_from_url(channel_url) or channel_url
    return ContentFactoryVideoPayload(
        video_external_id=str(handle),
        video_url=channel_url,
        title=str(channel_title or handle or network + " channel")[:500],
        published_at=None,
        views=0,
        likes=0,
        comments=0,
        extra={"source": "channel_seed", "network": network},
    )


async def parse_channel(
    network: str,
    channel_url: str,
    owner_id: int,
    period_days: int = 30,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> ParserResult:
    inferred_network = _infer_network_from_url(channel_url)
    if inferred_network and inferred_network != network:
        logger.warning(
            "[content_factory] network mismatch for url=%s configured=%s inferred=%s; using inferred network",
            channel_url,
            network,
            inferred_network,
        )
        network = inferred_network

    result: ParserResult
    if network == "youtube":
        result = await parse_youtube_channel(
            owner_id=owner_id,
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "instagram":
        result = await parse_instagram_apify(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "tiktok":
        result = await parse_tiktok_apify(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "vk":
        result = await parse_vk_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "ok":
        result = await parse_ok_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "dzen":
        result = await parse_dzen_browser(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "rutube":
        result = await parse_rutube_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    elif network == "likee":
        result = await parse_likee_http(
            channel_url=channel_url,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        result = await parse_stub(
            channel_url=channel_url,
            network=network,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

    result.resolved_network = network

    # If source is hard-blocked by anti-bot/CAPTCHA, avoid synthetic discovery/recovery noise.
    # If source is hard-blocked by anti-bot/CAPTCHA, skip expensive discovery/recovery
    # but still ensure at least a seed record is returned.
    if network in {"vk", "ok", "likee"} and not result.videos and _is_antibot_sync_message(result.sync_message):
        result.videos = [_make_channel_seed_video(network, channel_url, result.channel_title)]
        return result

    if _feature_enabled("CONTENT_FACTORY_CHANNEL_LINK_DISCOVERY_ENABLED", "1") and _should_expand_channel_video_set(network, result.videos):
        discovered_videos = await _discover_channel_video_links(network, channel_url)
        merged_videos, discovery_changed = _merge_discovered_videos(result.videos, discovered_videos, network=network)
        if discovery_changed:
            result.videos = merged_videos
            note = "Добавлен targeted link discovery по странице канала."
            result.sync_message = (result.sync_message or "") + (" " if result.sync_message else "") + note

    if not _feature_enabled("CONTENT_FACTORY_VIDEO_LINK_RECOVERY_ENABLED", "1"):
        if _feature_enabled("CONTENT_FACTORY_FORCE_COMPLETE_FIELDS_ENABLED", "1"):
            completed_videos, completeness_applied = _ensure_minimum_video_completeness(network, result.videos)
            result.videos = completed_videos
            if completeness_applied:
                result.sync_message = (result.sync_message or "") + (" " if result.sync_message else "") + "Применен hard completeness fallback для обязательных полей видео."
        return result

    recovered_videos, recovery_applied = await _recover_missing_video_metrics(network, result.videos)
    result.videos = recovered_videos
    if recovery_applied:
        if result.sync_status == "ok":
            result.sync_message = (result.sync_message or "") + (" " if result.sync_message else "") + "Применен video-level recovery для добора недостающих метрик."
        elif result.sync_status == "partial":
            result.sync_message = (result.sync_message or "") + (" " if result.sync_message else "") + "Дополнительно выполнен video-level recovery по ссылкам видео."

    if _feature_enabled("CONTENT_FACTORY_FORCE_COMPLETE_FIELDS_ENABLED", "1"):
        completed_videos, completeness_applied = _ensure_minimum_video_completeness(network, result.videos)
        result.videos = completed_videos
        if completeness_applied:
            result.sync_message = (result.sync_message or "") + (" " if result.sync_message else "") + "Применен hard completeness fallback для обязательных полей видео."

    # Universal guarantee: never return 0 videos — inject a seed so the channel
    # always has at least one DB row and can be enriched in subsequent runs.
    if not result.videos:
        result.videos = [_make_channel_seed_video(network, channel_url, result.channel_title)]
        result.sync_status = result.sync_status or "partial"
        result.sync_message = (
            (result.sync_message or "")
            + (" " if result.sync_message else "")
            + "Нет видео по периоду — создана seed-запись канала для последующего обогащения."
        )

    # Final normalization pass shared by all network parsers.
    effective_network = str((result.resolved_network or network) or "").strip().lower()
    if effective_network:
        for video in result.videos:
            extra = dict(video.extra or {})
            extra.setdefault("network", effective_network)
            if effective_network in {"vk", "ok"}:
                extra["is_short"] = False
            elif effective_network == "rutube":
                is_short = _is_rutube_short_video(str(video.video_url or ""), video.duration_seconds)
                extra["is_short"] = is_short
                extra["short_format"] = "short" if is_short else "video"
            elif effective_network == "dzen":
                is_short = _is_dzen_short_video(str(video.video_url or ""), tab_hint=str(extra.get("tab_hint") or ""))
                extra["is_short"] = is_short
                extra["short_format"] = "short" if is_short else "video"
            video.extra = extra
            _sanitize_video_metrics(effective_network, video)

    return result
