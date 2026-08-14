"""Dependency-free in-memory sliding-window rate limiter for the public
auth endpoints (SEC-01: no brute-force protection existed).

Single-process only: a multi-worker or multi-instance deployment must
back this with a shared store (e.g. Redis) -- see docs/ARCHITECTURE.md
§ Security. This is deliberately only applied to the unauthenticated
public endpoints; authenticated routes already require a valid token.

`reset_rate_limits()` is the test hook so a fresh TestClient starts with
a clean store instead of inheriting hits from an earlier test in the
same process.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Drop all recorded hits (test hook)."""
    with _lock:
        _hits.clear()


def rate_limited(bucket: str, max_requests: int, window_seconds: int) -> Callable[[Request], None]:
    """Build a FastAPI dependency that returns 429 once `max_requests`
    hits to `bucket` from the same client IP occur within
    `window_seconds`. The 429 carries a Retry-After header.
    """

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client is not None else "unknown"
        key = (bucket, ip)
        now = time.monotonic()
        with _lock:
            window = _hits[key]
            while window and now - window[0] > window_seconds:
                window.popleft()
            if len(window) >= max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again shortly.",
                    headers={"Retry-After": str(window_seconds)},
                )
            window.append(now)

    return dependency
