"""
genai_jobs/utils/security.py
─────────────────────────────────────────────────────────────────────────────
Security, anti-bot mitigation, and stealth request management.

Implements realistic browser fingerprinting, rotating user agents, modern
Client Hints, and jittered delays to avoid bot blocks against career portals.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Modern, realistic desktop browser User-Agents (macOS, Windows, Linux)
_REALISTIC_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        '"macOS"',
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        '"Windows"',
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        None,
        '"macOS"',
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        None,
        '"Windows"',
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
        None,
        '"macOS"',
    ),
]


def get_stealth_headers(
    accept_type: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    referer: Optional[str] = None,
) -> dict[str, str]:
    """
    Generate complete modern browser request headers including Client Hints
    and Sec-Fetch directives to mimic genuine user navigation.
    """
    ua, sec_ch_ua, platform = random.choice(_REALISTIC_USER_AGENTS)

    headers = {
        "User-Agent": ua,
        "Accept": accept_type,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
    if platform:
        headers["sec-ch-ua-platform"] = platform
    if referer:
        headers["Referer"] = referer

    return headers


def apply_jitter_delay(base_seconds: float = 1.0, jitter_ratio: float = 0.5) -> None:
    """
    Sleep for base_seconds ± randomized jitter to break deterministic request timing
    which automated WAFs (Cloudflare, Akamai) use to flag bot crawlers.
    """
    if base_seconds <= 0:
        return
    min_delay = max(0.2, base_seconds * (1 - jitter_ratio))
    max_delay = base_seconds * (1 + jitter_ratio)
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)

