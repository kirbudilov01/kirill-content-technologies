#!/usr/bin/env python3
"""Quick proxy health check for Content Factory social parsers.

Usage:
  PYTHONPATH=/app python3 /app/content_factory/check_proxies.py
  PYTHONPATH=/app python3 /app/content_factory/check_proxies.py --max 20 --timeout 18
"""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from typing import Optional

import aiohttp

TARGETS = [
    "https://vkvideo.ru/@club237523032",
    "https://ok.ru/video/c55317454",
    "https://likee.video/@likeeofficial",
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def normalize_proxy(raw: str) -> Optional[str]:
    value = (raw or "").strip()
    if not value or value.startswith("#"):
        return None
    if "://" in value:
        return value

    parts = [p.strip() for p in value.split(":")]
    if len(parts) == 4 and all(parts):
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 2 and all(parts):
        host, port = parts
        return f"http://{host}:{port}"
    return None


def redact_proxy(proxy: str) -> str:
    value = str(proxy or "")
    if "@" not in value:
        return value
    scheme, rest = value.split("@", 1)
    prefix = scheme.split("://", 1)[0] if "://" in scheme else "http"
    return f"{prefix}://***@{rest}"


def load_proxies(proxy_file: Path, max_count: int) -> list[str]:
    proxies: list[str] = []
    if not proxy_file.exists():
        return proxies

    for line in proxy_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        proxy = normalize_proxy(line)
        if not proxy:
            continue
        if proxy not in proxies:
            proxies.append(proxy)
        if len(proxies) >= max_count:
            break
    return proxies


async def check_one(proxy: str, timeout_sec: int) -> tuple[str, bool, list[str]]:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    marks: list[str] = []

    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": UA}) as session:
        for target in TARGETS:
            host = target.split("/")[2]
            try:
                async with session.get(target, proxy=proxy, allow_redirects=True) as response:
                    body_full = (await response.text())
                    body = body_full.lower()
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", body_full, flags=re.IGNORECASE | re.DOTALL)
                    title_text = (title_match.group(1).strip().lower() if title_match else "")

                    host_ok_signal = False
                    if host == "vkvideo.ru":
                        host_ok_signal = bool(re.search(r"(?:/clip-\d+_\d+|/video-\d+_\d+)", body, flags=re.IGNORECASE))
                    elif host == "ok.ru":
                        host_ok_signal = (
                            bool(re.search(r"ok\.ru/video/[a-z0-9_:\.-]+", body, flags=re.IGNORECASE))
                            or bool(re.search(r'"videoId"\s*:\s*"?\d+"?', body))
                        ) and ("социальная сеть одноклассники" not in title_text)
                    elif host == "likee.video":
                        host_ok_signal = ("page not available" not in title_text) and bool(re.search(r"/video/[a-z0-9_-]+", body, flags=re.IGNORECASE))

                    if response.status >= 400:
                        marks.append(f"{host}:{response.status}")
                    elif "captcha" in body or "robot" in body or "не робот" in body:
                        marks.append(f"{host}:captcha")
                    elif host_ok_signal:
                        marks.append(f"{host}:ok")
                    else:
                        marks.append(f"{host}:no-signal")
            except Exception as exc:
                marks.append(f"{host}:ERR:{type(exc).__name__}:{str(exc)[:48]}")

    good_count = sum(1 for m in marks if m.endswith(":ok"))
    return proxy, good_count > 0, marks


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check proxy health for VK/OK/Likee")
    parser.add_argument("--proxy-file", default="/app/proxy.txt", help="Path to proxy list file")
    parser.add_argument("--max", type=int, default=20, help="Max proxies to test")
    parser.add_argument("--timeout", type=int, default=18, help="Request timeout in seconds")
    args = parser.parse_args()

    proxies = load_proxies(Path(args.proxy_file), max_count=max(1, args.max))
    if not proxies:
        print("No proxies loaded")
        return 1

    print(f"Loaded {len(proxies)} proxies from {args.proxy_file}")

    tasks = [check_one(proxy, timeout_sec=max(8, args.timeout)) for proxy in proxies]
    results = await asyncio.gather(*tasks)

    working = [item for item in results if item[1]]
    blocked = [item for item in results if not item[1]]

    print("\nWorking proxies (at least one target without captcha/error):")
    for proxy, _, marks in working[:20]:
        print(f"  {redact_proxy(proxy)} | {'; '.join(marks)}")

    print("\nBlocked/bad proxies:")
    for proxy, _, marks in blocked[:20]:
        print(f"  {redact_proxy(proxy)} | {'; '.join(marks)}")

    print(f"\nSummary: working={len(working)} blocked={len(blocked)} total={len(results)}")
    return 0 if working else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
