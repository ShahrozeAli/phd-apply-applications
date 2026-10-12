from __future__ import annotations

import time

import httpx

from app.config import settings

_last_request_at = 0.0


def polite_get(url: str, timeout: float = 30.0) -> httpx.Response:
    global _last_request_at
    wait = settings.discovery_request_delay_seconds - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    headers = {
        "User-Agent": settings.discovery_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = client.get(url)
    _last_request_at = time.time()
    response.raise_for_status()
    return response
