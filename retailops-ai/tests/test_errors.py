"""Stage 6 backend hardening: api/errors.py's taxonomy and the
registered exception handler -- proves an unhandled exception NEVER
reaches the client as raw text (the exact gap a live 429 ClientError
exposed during the SSE task, see project memory), and that registering
a handler for the base Exception class does NOT interfere with
FastAPI's own HTTPException handling (404s, 401s, this module's own
429/504 raisers) -- confirmed live before wiring this into api/main.py.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.errors import (
    INTERNAL,
    LLM_UNAVAILABLE,
    RATE_LIMITED,
    STOCKPILOT_UNAVAILABLE,
    TIMED_OUT,
    classify,
    safe_error_body,
    unhandled_exception_handler,
)
from clients.stockpilot import StockPilotUnavailableError
from llm.providers.gemini import LLMUnavailableError


def test_classify_maps_known_exception_types() -> None:
    assert classify(LLMUnavailableError("x")) is LLM_UNAVAILABLE
    assert classify(StockPilotUnavailableError("x")) is STOCKPILOT_UNAVAILABLE
    assert classify(TimeoutError("x")) is TIMED_OUT
    assert classify(RuntimeError("x")) is INTERNAL
    assert classify(ValueError("some sensitive detail: password=hunter2")) is INTERNAL


def test_safe_error_body_never_contains_the_original_exception_text() -> None:
    exc = RuntimeError("some sensitive internal detail: password=hunter2")
    body = safe_error_body(exc)
    assert "hunter2" not in str(body)
    assert body["detail"] == INTERNAL.safe_message


def test_safe_error_body_includes_error_id_when_given() -> None:
    import uuid

    error_id = uuid.uuid4()
    body = safe_error_body(RuntimeError("x"), error_id=error_id)
    assert body["error_id"] == str(error_id)


def _app_with_handler() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("some sensitive internal detail: password=hunter2")

    @app.get("/llm-down")
    def llm_down() -> None:
        raise LLMUnavailableError("Gemini unreachable after 3 retries: timeout")

    @app.get("/not-found")
    def not_found() -> None:
        raise HTTPException(status_code=404, detail="specific not found message")

    return app


def test_unhandled_exception_handler_never_leaks_the_raw_exception_text() -> None:
    client = TestClient(_app_with_handler(), raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert "hunter2" not in response.text
    assert "password" not in response.text
    assert body["detail"] == INTERNAL.safe_message
    assert "error_id" in body


def test_unhandled_exception_handler_classifies_known_types() -> None:
    client = TestClient(_app_with_handler(), raise_server_exceptions=False)
    response = client.get("/llm-down")

    assert response.status_code == 503
    assert response.json()["detail"] == LLM_UNAVAILABLE.safe_message


def test_registering_the_exception_handler_does_not_break_existing_http_exceptions() -> None:
    """The critical safety property this whole design depends on: a
    broad Exception handler must not shadow FastAPI's own, more specific
    HTTPException handling (the 404s in api/agent.py, the 401s in
    api/deps.py, RATE_LIMITED's own 429). Confirmed here, not assumed.
    """
    client = TestClient(_app_with_handler(), raise_server_exceptions=False)
    response = client.get("/not-found")

    assert response.status_code == 404
    assert response.json()["detail"] == "specific not found message"


def test_error_categories_have_distinct_safe_messages() -> None:
    # LLM_UNAVAILABLE and STOCKPILOT_UNAVAILABLE legitimately share the
    # same 503 status (both are "a downstream dependency is down"), but
    # each category's own message must still say which one, distinctly.
    categories = [RATE_LIMITED, LLM_UNAVAILABLE, STOCKPILOT_UNAVAILABLE, TIMED_OUT, INTERNAL]
    assert len({c.safe_message for c in categories}) == len(categories)
