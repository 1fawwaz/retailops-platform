"""Task 3.6 API layer: POST /agent/query and GET /agent/execution/{id}
wrap orchestration/executor.py::run_execution(), already tested directly
against the real graph in tests/test_executor.py and tests/test_graph.py.
These tests prove the FastAPI wiring itself: dependency overrides reach
the real graph, the HTTP response shape matches what got persisted, a
404 for an unknown execution id, and that the StockPilot-outage failure
behaviour returns 200 (never 500) all the way through the actual route,
not just at the graph level.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import patch

import httpx2
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.replan import ReplanJudgement
from api import deps
from api.main import app
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.models import Base
from prompts.loader import load_prompt

AGENT_NAMES = ("planner", "inventory", "forecast", "analytics", "report", "decision")


@pytest.fixture
def session_factory() -> Generator[Callable[[], Session]]:
    # Same rationale as tests/test_graph.py and tests/test_executor.py:
    # run_execution() runs the real concurrent graph, which needs genuine
    # per-thread connections (a temp file + WAL), not a single shared one.
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()
    os.remove(path)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)


def _login_only_client() -> StockPilotClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "t", "token_type": "bearer"})

    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
    )


def _unreachable_client() -> StockPilotClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
        max_retries=0,
    )


def _test_client(session_factory: Callable[[], Session], client: StockPilotClient) -> TestClient:
    """Every caller is responsible for `app.dependency_overrides.clear()`
    in its own `finally` block -- FastAPI's overrides dict is shared
    process-wide state on the module-level `app` object, so a test that
    forgot to clear it would leak its fake client/session into whichever
    test runs next.
    """
    app.dependency_overrides[deps.get_db_session_factory] = lambda: session_factory
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: client
    return TestClient(app)


def _ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text, usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    )


def _sufficient_judgement(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[ReplanJudgement]:
    return StructuredResult(
        parsed=ReplanJudgement(
            sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
        ),
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_query_agent_returns_the_answer_and_an_inline_trace(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    test_client = _test_client(session_factory, _login_only_client())
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
        ):
            response = test_client.post(
                "/agent/query", json={"query": "Which products are low on stock?"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["answer"] == "decision answer"
    assert body["plan"] == "planner answer"
    assert body["agent_results"]["inventory"] == "inventory answer"
    assert body["replan_rounds"] == 1
    assert body["citation_attempts"] == 1
    assert body["errors"] == []
    assert body["total_tokens"] > 0
    uuid.UUID(body["execution_id"])
    uuid.UUID(body["conversation_id"])


def test_query_agent_second_call_continues_the_same_conversation(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}
    captured_planner_prompts: list[str] = []

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "planner":
            captured_planner_prompts.append(str(messages[1].content))
        return _ai_message(f"{name} answer")

    test_client = _test_client(session_factory, _login_only_client())
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
        ):
            first = test_client.post(
                "/agent/query", json={"query": "Which products are low on stock?"}
            )
            conversation_id = first.json()["conversation_id"]
            second = test_client.post(
                "/agent/query",
                json={
                    "query": "And what does forecasting say about those?",
                    "conversation_id": conversation_id,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert "Which products are low on stock?" in captured_planner_prompts[1]


def test_query_agent_stockpilot_outage_returns_200_not_500(
    session_factory: Callable[[], Session],
) -> None:
    """Task 3.6: "Killing StockPilot yields a graceful degraded answer,
    not a 500" -- proved here through the real HTTP route, with a real
    StockPilotClient over a transport that fails every request (auth
    included), not a mocked-away client.
    """
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}
    tool_call_message = AIMessage(
        content="", tool_calls=[{"name": "get_stock", "args": {}, "id": "call_1"}]
    )
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "inventory" and calls[name] == 1:
            return tool_call_message
        if name == "inventory":
            return _ai_message("Stock levels are unavailable -- StockPilot could not be reached.")
        return _ai_message(f"{name} answer")

    test_client = _test_client(session_factory, _unreachable_client())
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
        ):
            response = test_client.post("/agent/query", json={"query": "What's low on stock?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "StockPilot could not be reached" in body["agent_results"]["inventory"]
    assert body["answer"] is not None


def test_get_execution_trace_returns_the_full_persisted_trace(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    test_client = _test_client(session_factory, _login_only_client())
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
        ):
            posted = test_client.post("/agent/query", json={"query": "How is inventory?"})
        execution_id = posted.json()["execution_id"]

        trace_response = test_client.get(f"/agent/execution/{execution_id}")
    finally:
        app.dependency_overrides.clear()

    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["execution_id"] == execution_id
    assert trace["status"] == "completed"
    assert trace["final_answer"] == "decision answer"
    agent_names_seen = {step["agent_name"] for step in trace["agent_steps"]}
    assert agent_names_seen == set(AGENT_NAMES)
    assert all(step["prompt_version_hash"] for step in trace["agent_steps"])


def test_get_execution_trace_returns_404_for_an_unknown_execution_id(
    session_factory: Callable[[], Session],
) -> None:
    test_client = _test_client(session_factory, _login_only_client())
    try:
        response = test_client.get(f"/agent/execution/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_query_agent_streams_sse_events_when_accept_header_requests_it(
    session_factory: Callable[[], Session],
) -> None:
    """Stage 6: the SAME POST /agent/query path, switched to SSE purely
    by the request's Accept header -- proves the whole chain end to end
    through the real ASGI app: real graph, real streaming=True wiring in
    orchestration/graph.py, real event framing in api/agent.py.
    """
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    def fake_stream(*, model: str, messages: list[Any], tools: Any = None) -> Any:
        from llm.providers.gemini import StreamChunk

        yield StreamChunk(text="decision ")
        yield StreamChunk(text="answer")
        yield StreamChunk(
            text="", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        )

    test_client = _test_client(session_factory, _login_only_client())
    events: list[tuple[str, dict[str, Any]]] = []
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
            patch("agents.base.stream", side_effect=fake_stream),
        ):
            with test_client.stream(
                "POST",
                "/agent/query",
                json={"query": "Which products are low on stock?"},
                headers={"Accept": "text/event-stream"},
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                event_type: str | None = None
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        event_type = line.removeprefix("event: ")
                    elif line.startswith("data: "):
                        assert event_type is not None
                        events.append((event_type, json.loads(line.removeprefix("data: "))))
    finally:
        app.dependency_overrides.clear()

    event_types = [event_type for event_type, _ in events]
    assert event_types.count("agent_completed") == 5  # 3 retrieval + report + decision
    assert "token" in event_types
    assert "replan_judgement" in event_types
    assert "citation_check" in event_types
    assert event_types[-1] == "done"

    token_text = "".join(data["text"] for event_type, data in events if event_type == "token")
    assert token_text == "decision answer"

    done_data = events[-1][1]
    assert done_data["status"] == "completed"
    assert done_data["answer"] == "decision answer"
    assert uuid.UUID(done_data["execution_id"])  # a real, parseable execution id


def test_query_agent_without_streaming_accept_header_returns_plain_json(
    session_factory: Callable[[], Session],
) -> None:
    """Regression guard: the default (no special Accept header) request
    shape -- what the existing non-streaming tests above already send --
    must stay a single plain JSON response, never SSE. Also proves the
    decision node never calls stream() at all on this path: only
    agents.base.generate is mocked here, exactly like every pre-Stage-6
    test in this file.
    """
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    test_client = _test_client(session_factory, _login_only_client())
    try:
        with (
            patch("agents.base.generate", side_effect=fake_generate),
            patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
        ):
            response = test_client.post(
                "/agent/query", json={"query": "Which products are low on stock?"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert response.json()["answer"] == "decision answer"
