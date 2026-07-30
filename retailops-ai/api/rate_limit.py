"""Stage 6 backend hardening: per-user rate limiting.

No Redis in this project's pinned stack (CLAUDE.md section 6) and no
multi-process deployment target either -- a single process-lifetime
in-memory sliding window, guarded by a lock since FastAPI's sync routes
run across a thread pool (Starlette's own run_in_threadpool), is
sufficient and doesn't introduce a component the spec never asked for.
Keyed by the authenticated subject (api/deps.py::get_current_subject's
own JWT `sub` claim) -- there is no anonymous access to rate-limit
separately, since every route this is applied to already requires a
valid token.

Applied only to the LLM-cost-incurring routes (POST /agent/query, the
two POST /workflow/*/run routes) -- a deliberate scoping decision, not
an oversight: those are the ones that trigger multiple real LLM/tool
calls per request and are what "per-user rate limiting" is actually
protecting against abuse of. The cheap, read-only trace/report/action
endpoints (GET /agent/execution/{id}, GET /report/{id}, POST
/recommendations/{id}/action) stay unlimited.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Depends, HTTPException

from api.deps import get_current_subject
from api.errors import RATE_LIMITED
from settings import get_settings

_lock = threading.Lock()
_requests_by_subject: dict[str, deque[float]] = {}


def reset_rate_limit_state() -> None:
    """Test-only: this module's state is process-lifetime, not
    per-request -- tests that exercise the limiter need a clean slate
    between cases, the same reason llm/providers/gemini.py exposes its
    own _reset_client_cache().
    """
    with _lock:
        _requests_by_subject.clear()


def check_rate_limit(subject: str) -> None:
    settings = get_settings()
    limit = settings.rate_limit_requests
    window = settings.rate_limit_window_seconds
    now = time.monotonic()
    with _lock:
        timestamps = _requests_by_subject.setdefault(subject, deque())
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()
        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=RATE_LIMITED.http_status, detail=RATE_LIMITED.safe_message
            )
        timestamps.append(now)


def rate_limit(subject: str = Depends(get_current_subject)) -> None:
    """A FastAPI dependency -- add alongside get_current_subject on a
    route. FastAPI caches a dependency's result per request, so this
    doesn't cause get_current_subject (and its JWT decode) to run twice
    just because a route also depends on it directly for `_subject`.
    """
    check_rate_limit(subject)
