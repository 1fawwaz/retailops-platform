"""Stage 3 Task 3.2 milestone: the graph runs the full topology and the
retrieval agents provably run concurrently, with real timing overlap
proof captured at the level of the actual graph (not just a raw
LangGraph toy example).
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.base import Agent
from orchestration.graph import build_execution_graph
from orchestration.models import Base
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from orchestration.state import new_execution_state
from prompts.loader import load_prompt

AGENT_SPECS: dict[str, str] = {
    "planner": "planner",
    "inventory": "retriever",
    "forecast": "retriever",
    "analytics": "retriever",
    "report": "decision",
    "decision": "decision",
}
RETRIEVAL_NAMES = ("inventory", "forecast", "analytics")


@pytest.fixture
def session_factory() -> Generator[Callable[[], Session]]:
    # The graph's retrieval nodes genuinely run in parallel threads, each
    # opening its own session and committing independently. An in-memory
    # SQLite db -- whether a single shared connection (StaticPool, as
    # tests/conftest.py's db_session fixture uses for single-threaded
    # tests) or a shared-cache URI with separate connections -- breaks
    # under real concurrent commits (the former corrupts SQLAlchemy's
    # per-session transaction state; the latter still hits SQLite's
    # rollback-journal table lock instantly, since WAL mode -- which
    # allows a writer and readers to not block each other -- isn't
    # supported for in-memory databases). A real temp file with WAL mode
    # and a busy timeout is what actually tolerates concurrent writers.
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


def _new_execution(session_factory: Callable[[], Session]) -> uuid.UUID:
    session = session_factory()
    execution = Execution(query="test query", status="running")
    session.add(execution)
    session.commit()
    execution_id = execution.id
    session.close()
    return execution_id


def _six_agents(**overrides: Agent) -> dict[str, Agent]:
    agents = {
        name: Agent(name=name, role=role, prompt=load_prompt(name))
        for name, role in AGENT_SPECS.items()
    }
    agents.update(overrides)
    return agents


def _ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text,
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _dispatch_by_prompt(agents: dict[str, Agent]) -> dict[str, str]:
    """generate() only receives a model id and a message list, and several
    agents share a model id (planner/decision both use the "decision"...
    role; retriever agents share "retriever") -- the system message's text
    (each agent's own versioned prompt file) is what's actually unique per
    agent, so tests dispatch on that instead of on `model`.
    """
    return {agent.prompt.text: name for name, agent in agents.items()}


def test_graph_runs_full_topology_and_produces_a_final_answer(
    session_factory: Callable[[], Session],
) -> None:
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    with patch("agents.base.generate", side_effect=fake_generate):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id,
            query="How is inventory looking?",
            budgets={"max_tool_iterations": 12},
        )
        result = graph.invoke(state)

    assert result["plan"] == "planner answer"
    assert result["agent_results"] == {
        "inventory": "inventory answer",
        "forecast": "forecast answer",
        "analytics": "analytics answer",
        "report": "report answer",
        "decision": "decision answer",
    }
    assert result["final_answer"] == "decision answer"
    assert set(result["timings"]) == {
        "planner",
        "inventory",
        "forecast",
        "analytics",
        "report",
        "decision",
    }


def test_retrieval_agents_run_concurrently(session_factory: Callable[[], Session]) -> None:
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name in ("inventory", "forecast", "analytics"):
            time.sleep(0.5)
        return _ai_message(f"{name} answer")

    with patch("agents.base.generate", side_effect=fake_generate):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        started = time.monotonic()
        result = graph.invoke(state)
        elapsed = time.monotonic() - started

    # Sequential would take >= 3 * 0.5s = 1.5s for the retrieval fan-out
    # alone, before even counting planner/report/decision. Concurrent
    # execution finishes well under that.
    assert elapsed < 1.2

    timings = result["timings"]
    windows = {name: (timings[name]["start"], timings[name]["end"]) for name in RETRIEVAL_NAMES}
    overlap_found = any(
        windows[a][0] < windows[b][1] and windows[b][0] < windows[a][1]
        for a in windows
        for b in windows
        if a != b
    )
    assert overlap_found, f"expected overlapping timing windows, got {windows}"


class _SkuArgs(BaseModel):
    sku: str


def test_retrieval_node_populates_tool_ledger_and_provenance_from_real_tool_calls(
    session_factory: Callable[[], Session],
) -> None:
    execution_id = _new_execution(session_factory)

    def _run(sku: str) -> str:
        session = session_factory()
        try:
            session.add(
                ToolCall(
                    execution_id=execution_id,
                    tool_name="get_product",
                    args={"sku": sku},
                    raw_response={"sku": sku},
                    provenance_map={"sku": "observed", "unit_cost": "derived"},
                    latency_ms=5,
                    status="success",
                )
            )
            session.commit()
        finally:
            session.close()
        return f"data for {sku}"

    tool = StructuredTool.from_function(
        func=_run, name="get_product", description="Get a product.", args_schema=_SkuArgs
    )
    agents = _six_agents(
        inventory=Agent(
            name="inventory", role="retriever", prompt=load_prompt("inventory"), tools=(tool,)
        )
    )
    prompt_to_name = _dispatch_by_prompt(agents)

    tool_call_message = AIMessage(
        content="", tool_calls=[{"name": "get_product", "args": {"sku": "123"}, "id": "call_1"}]
    )
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "inventory" and calls[name] == 1:
            return tool_call_message
        return _ai_message(f"{name} answer")

    with patch("agents.base.generate", side_effect=fake_generate):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    assert result["provenance_map"] == {"sku": "observed", "unit_cost": "derived"}
    ledger_tool_names = {entry["tool_name"] for entry in result["tool_ledger"]}
    assert ledger_tool_names == {"get_product"}


def test_retrieval_nodes_do_not_cross_attribute_tool_calls(
    session_factory: Callable[[], Session],
) -> None:
    """Ownership filtering by tool_name -- rather than diffing which
    tool_call ids existed before/after a node's own invocation, which an
    earlier version of this test proved races under real concurrent
    writes against SQLite's single shared StaticPool connection -- must
    attribute each row correctly even when unrelated tool_calls rows
    already exist for the same execution_id under a name neither
    retrieval agent owns.
    """
    execution_id = _new_execution(session_factory)
    session = session_factory()
    try:
        for name in ("inventory_tool", "forecast_tool", "unowned_tool"):
            session.add(
                ToolCall(
                    execution_id=execution_id,
                    tool_name=name,
                    args={"sku": "1"},
                    raw_response={"sku": "1"},
                    provenance_map={"sku": "observed"},
                    latency_ms=5,
                    status="success",
                )
            )
        session.commit()
    finally:
        session.close()

    agents = _six_agents(
        inventory=Agent(
            name="inventory",
            role="retriever",
            prompt=load_prompt("inventory"),
            tools=(
                StructuredTool.from_function(
                    func=lambda sku: sku,
                    name="inventory_tool",
                    description="d",
                    args_schema=_SkuArgs,
                ),
            ),
        ),
        forecast=Agent(
            name="forecast",
            role="retriever",
            prompt=load_prompt("forecast"),
            tools=(
                StructuredTool.from_function(
                    func=lambda sku: sku,
                    name="forecast_tool",
                    description="d",
                    args_schema=_SkuArgs,
                ),
            ),
        ),
    )
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        # Neither agent actually calls its tool here -- the rows already
        # in the DB are what's under test, not anything Agent.invoke()
        # writes during this run.
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    with patch("agents.base.generate", side_effect=fake_generate):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    ledger_names = {entry["tool_name"] for entry in result["tool_ledger"]}
    assert ledger_names == {"inventory_tool", "forecast_tool"}
