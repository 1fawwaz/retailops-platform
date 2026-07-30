"""Stage 6 backend hardening: request timeouts.

FastAPI's sync routes already run in a thread pool (Starlette's own
run_in_threadpool) -- the actual agent work underneath (run_execution(),
the two workflow pipelines) is a long, blocking chain of real LLM/
StockPilot HTTP calls with no cooperative cancellation point Python can
safely interrupt mid-call. run_with_timeout() bounds the CALLER's wait,
not the callee's actual work: past the timeout, the HTTP response
returns a clean, safe timeout error while the abandoned call keeps
running to completion (or its own eventual failure) on its own thread.
This is the same tradeoff most sync-call request timeouts make in
practice, since Python has no safe way to forcibly kill a running
thread -- documented here, not silently assumed away.

Every individual LLM/StockPilot call already has its OWN bounded retry
budget (llm/providers/gemini.py's MAX_LLM_RETRIES, clients/stockpilot.py's
own retry+circuit-breaker) -- no single call can hang unboundedly today.
What this guards against is the SUM of many bounded steps (a long replan
loop, several citation-validator regenerations, many tool calls) adding
up past what a caller should have to wait for.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

# Bounded but not tiny -- concurrent timed-out requests each hold a
# worker until run_with_timeout's own timeout fires (the abandoned call
# isn't interrupted, see module docstring), so this must comfortably
# exceed the busiest realistic burst under rate_limit_requests' own cap.
_executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="request-timeout")


def run_with_timeout(fn: Callable[[], T], *, timeout_seconds: float) -> T:
    """Raises builtins.TimeoutError (via concurrent.futures.Future.result,
    which is the same type as of Python 3.11) if `fn` doesn't complete
    within timeout_seconds.
    """
    future = _executor.submit(fn)
    return future.result(timeout=timeout_seconds)
