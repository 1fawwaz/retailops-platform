"""Stage 6 backend hardening: a small, fixed error taxonomy translating
whatever exception surfaces at the API boundary into ONE of a few
user-safe messages. CLAUDE.md's own logging discipline (structured JSON,
never a secret in a response) applied to the failure path specifically:
"error taxonomy with user-safe messages and full detail in logs only"
per docs/BUILD-SPEC.md's Stage 6 backend-hardening bullet.

Every already-typed failure mode this codebase produces (StockPilot
outage, LLM outage/rate-limit-exhaustion) is normally absorbed by the
graph's own degradation logic (orchestration/graph.py, Task 3.6) before
it ever reaches here -- a grounded final_answer naming the gap, not a
raised exception. This module exists for what's LEFT after that: an
exception that genuinely propagates past the graph (a bug, a failure in
code that runs OUTSIDE it -- orchestration/executor.py's own DB writes,
api/rate_limit.py, api/timeouts.py -- or a request that a rate limit or
timeout itself rejects). It is the last line of defense before a raw
exception, and whatever sensitive detail it carries, would otherwise
reach an HTTP response body.

FastAPI's own HTTPException handling (404s in api/agent.py, 401s in
api/deps.py, the 429/504 this module's own callers raise) is untouched
by registering a handler for the base Exception class -- confirmed live:
Starlette resolves the more specific HTTPException handler first
regardless of a broader Exception handler also being registered.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import Request, status
from fastapi.responses import JSONResponse

from clients.stockpilot import StockPilotUnavailableError
from llm.providers.gemini import LLMUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorCategory:
    http_status: int
    safe_message: str


RATE_LIMITED = ErrorCategory(
    status.HTTP_429_TOO_MANY_REQUESTS,
    "Too many requests -- please slow down and try again shortly.",
)
LLM_UNAVAILABLE = ErrorCategory(
    status.HTTP_503_SERVICE_UNAVAILABLE,
    "The AI service is temporarily unavailable. Please try again shortly.",
)
STOCKPILOT_UNAVAILABLE = ErrorCategory(
    status.HTTP_503_SERVICE_UNAVAILABLE,
    "Inventory data is temporarily unavailable. Please try again shortly.",
)
TIMED_OUT = ErrorCategory(
    status.HTTP_504_GATEWAY_TIMEOUT,
    "This request took too long to complete. Please try again.",
)
INTERNAL = ErrorCategory(
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    "Something went wrong on our end. Please try again; if this keeps happening, contact support.",
)


def classify(exc: BaseException) -> ErrorCategory:
    """Exception type -> user-safe category. Order matters:
    TimeoutError is checked before the generic fallback since
    api/timeouts.py raises the bare builtin (concurrent.futures.TimeoutError
    IS builtins.TimeoutError as of Python 3.11, the pinned version here --
    no separate import needed).
    """
    if isinstance(exc, LLMUnavailableError):
        return LLM_UNAVAILABLE
    if isinstance(exc, StockPilotUnavailableError):
        return STOCKPILOT_UNAVAILABLE
    if isinstance(exc, TimeoutError):
        return TIMED_OUT
    return INTERNAL


def safe_error_body(exc: BaseException, *, error_id: uuid.UUID | None = None) -> dict[str, object]:
    """The exact user-safe JSON body for both the blocking-JSON exception
    handler below AND a streaming route's own "error" SSE event (see
    api/agent.py) -- one shape, two delivery mechanisms, so a client
    doesn't need to parse two different error formats depending on which
    path it happened to be using.
    """
    category = classify(exc)
    body: dict[str, object] = {"detail": category.safe_message}
    if error_id is not None:
        body["error_id"] = str(error_id)
    return body


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Registered in api/main.py for the base Exception class. Logs the
    FULL exception (message, type, traceback via exc_info) through the
    structured JSON logger (logging_config.py) -- server-side detail only
    -- and returns nothing but a safe category message plus an
    error_id a user could quote back for support, never the exception's
    own text.
    """
    error_id = uuid.uuid4()
    category = classify(exc)
    logger.error(
        "Unhandled exception on %s %s (error_id=%s, category=%s): %s",
        request.method,
        request.url.path,
        error_id,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=category.http_status,
        content=safe_error_body(exc, error_id=error_id),
    )
