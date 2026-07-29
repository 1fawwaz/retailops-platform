"""Stage 3 Tasks 3.2/3.3/3.5 milestones: the graph runs the full
topology, the retrieval agents provably run concurrently (real timing
overlap proof captured at the level of the actual graph, not just a raw
LangGraph toy example), the replan loop demonstrably triggers a second,
targeted retrieval round when the Planner judges the evidence
insufficient, and the citation validator regenerates once then gives up
with INSUFFICIENT_DATA when a draft answer can't be grounded.
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
from agents.replan import ReplanJudgement
from llm.providers.gemini import StructuredResult
from orchestration.graph import build_execution_graph
from orchestration.models import Base
from orchestration.models.agent_step import AgentStep
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
    """generate()/generate_structured() only receive a model id and a
    message list, and several agents share a model id (planner/decision
    both use the "decision"... role; retriever agents share "retriever")
    -- the system message's text (each agent's own versioned prompt file)
    is what's actually unique per agent, so tests dispatch on that
    instead of on `model`.
    """
    return {agent.prompt.text: name for name, agent in agents.items()}


def _judgement_result(
    *, sufficient: bool, missing: list[str], next_action: str, agents_to_retry: list[str]
) -> StructuredResult[ReplanJudgement]:
    return StructuredResult(
        parsed=ReplanJudgement(
            sufficient=sufficient,
            missing=missing,
            next_action=next_action,
            agents_to_retry=agents_to_retry,
        ),
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def _always_sufficient(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[ReplanJudgement]:
    """The Task 3.2-era tests only care about the graph's straight-line
    topology and concurrency, not the replan loop itself -- this keeps
    them at exactly one retrieval round by always judging "sufficient".
    """
    return _judgement_result(
        sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
    )


def test_graph_runs_full_topology_and_produces_a_final_answer(
    session_factory: Callable[[], Session],
) -> None:
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
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
        "inventory_1",
        "forecast_1",
        "analytics_1",
        "replan_1",
        "report",
        "decision",
    }
    assert len(result["replan_history"]) == 1
    assert result["replan_history"][0]["sufficient"] is True


def test_retrieval_agents_run_concurrently(session_factory: Callable[[], Session]) -> None:
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name in ("inventory", "forecast", "analytics"):
            time.sleep(0.5)
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
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
    windows = {
        name: (timings[f"{name}_1"]["start"], timings[f"{name}_1"]["end"])
        for name in RETRIEVAL_NAMES
    }
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

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
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
    """Two properties at once: ownership filtering by tool_name rules out
    ever attributing a concurrently-running sibling's row (an earlier
    version of this test proved plain before/after id-diffing with no
    name filter races under real concurrent writes); before/after
    id-diffing WITHIN the owned set rules out re-counting a row that
    already existed before this node's own invocation -- e.g. a stale
    row seeded here to stand in for a previous replan round's leftover
    tool call, or an entirely unowned name neither agent's subset
    includes.
    """
    execution_id = _new_execution(session_factory)
    session = session_factory()
    try:
        session.add(
            ToolCall(
                execution_id=execution_id,
                tool_name="unowned_tool",
                args={},
                raw_response={},
                provenance_map={},
                latency_ms=1,
                status="success",
            )
        )
        session.add(
            ToolCall(
                execution_id=execution_id,
                tool_name="inventory_tool",
                args={"sku": "stale"},
                raw_response={"sku": "stale"},
                provenance_map={"stale_field": "observed"},
                latency_ms=1,
                status="success",
            )
        )
        session.commit()
    finally:
        session.close()

    def _make_tool(name: str) -> StructuredTool:
        def _run(sku: str) -> str:
            write_session = session_factory()
            try:
                write_session.add(
                    ToolCall(
                        execution_id=execution_id,
                        tool_name=name,
                        args={"sku": sku},
                        raw_response={"sku": sku},
                        provenance_map={"sku": "observed"},
                        latency_ms=5,
                        status="success",
                    )
                )
                write_session.commit()
            finally:
                write_session.close()
            return f"data for {sku}"

        return StructuredTool.from_function(
            func=_run, name=name, description="d", args_schema=_SkuArgs
        )

    agents = _six_agents(
        inventory=Agent(
            name="inventory",
            role="retriever",
            prompt=load_prompt("inventory"),
            tools=(_make_tool("inventory_tool"),),
        ),
        forecast=Agent(
            name="forecast",
            role="retriever",
            prompt=load_prompt("forecast"),
            tools=(_make_tool("forecast_tool"),),
        ),
    )
    prompt_to_name = _dispatch_by_prompt(agents)

    tool_calls_made: dict[str, AIMessage] = {
        "inventory": AIMessage(
            content="",
            tool_calls=[{"name": "inventory_tool", "args": {"sku": "1"}, "id": "c1"}],
        ),
        "forecast": AIMessage(
            content="",
            tool_calls=[{"name": "forecast_tool", "args": {"sku": "2"}, "id": "c2"}],
        ),
    }
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name in tool_calls_made and calls[name] == 1:
            return tool_calls_made[name]
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    ledger_names = sorted(entry["tool_name"] for entry in result["tool_ledger"])
    # Exactly the two NEW, owned calls made during this run -- not the
    # pre-existing stale inventory_tool row, and not the unowned one.
    assert ledger_names == ["forecast_tool", "inventory_tool"]


def test_replan_loop_triggers_a_second_targeted_retrieval_round(
    session_factory: Callable[[], Session],
) -> None:
    """The Task 3.3 milestone: at least one query must demonstrably
    trigger a second retrieval round, with the reasoning visible in the
    trace. First judgement says insufficient and names only "forecast";
    second says sufficient. Only forecast should run twice.
    """
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    calls: dict[str, int] = {}
    ordinals = ("first", "second", "third")

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        # Words, not digits: Task 3.5's citation validator would otherwise
        # reject any digit here as an ungrounded fabricated number, since
        # nothing in this mocked flow ties a literal round count back to
        # real tool data.
        return _ai_message(f"{name} answer ({ordinals[calls[name] - 1]} call)")

    replan_calls = {"count": 0}

    def fake_generate_structured(
        *, model: str, messages: list[Any], response_schema: Any
    ) -> StructuredResult[ReplanJudgement]:
        replan_calls["count"] += 1
        if replan_calls["count"] == 1:
            return _judgement_result(
                sufficient=False,
                missing=["forecast confidence interval for the flagged SKUs"],
                next_action="forecast agent, targeted retrieval",
                agents_to_retry=["forecast"],
            )
        return _judgement_result(
            sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
        )

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=fake_generate_structured),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    assert len(result["replan_history"]) == 2
    assert result["replan_history"][0]["sufficient"] is False
    assert result["replan_history"][0]["iteration"] == 1
    assert result["replan_history"][0]["agents_to_retry"] == ["forecast"]
    assert result["replan_history"][1]["sufficient"] is True
    assert result["replan_history"][1]["iteration"] == 2

    # Only forecast was named for retry -- inventory/analytics must not
    # have re-run just because the loop went around again.
    assert calls["forecast"] == 2
    assert calls["inventory"] == 1
    assert calls["analytics"] == 1
    assert result["agent_results"]["forecast"] == "forecast answer (second call)"
    assert result["final_answer"] == "decision answer (first call)"

    verify_session = session_factory()
    try:
        steps = verify_session.query(AgentStep).filter(AgentStep.execution_id == execution_id).all()
    finally:
        verify_session.close()
    forecast_iterations = sorted(s.iteration for s in steps if s.agent_name == "forecast")
    assert forecast_iterations == [1, 2]
    inventory_iterations = [s.iteration for s in steps if s.agent_name == "inventory"]
    assert inventory_iterations == [1]
    replan_iterations = sorted(s.iteration for s in steps if s.agent_name == "planner")
    # One "planner" agent_steps row for the initial free-text plan (default
    # iteration=1) plus one per replan judgement (iterations 1 and 2).
    assert replan_iterations == [1, 1, 2]


def test_replan_loop_is_bounded_by_max_tool_iterations(
    session_factory: Callable[[], Session],
) -> None:
    """A persistently-insufficient judgement must not loop forever --
    once the iteration cap is reached, the loop falls through to
    Report/Decision anyway ("Bounded by max_tool_iterations" per spec).
    """
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    def fake_generate_structured(
        *, model: str, messages: list[Any], response_schema: Any
    ) -> StructuredResult[ReplanJudgement]:
        return _judgement_result(
            sufficient=False,
            missing=["always something more"],
            next_action="try again",
            agents_to_retry=["forecast"],
        )

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=fake_generate_structured),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 2}
        )
        result = graph.invoke(state)

    assert len(result["replan_history"]) == 2
    assert all(judgement["sufficient"] is False for judgement in result["replan_history"])
    assert result["final_answer"] == "decision answer"


def _seed_grounded_tool_call(
    session_factory: Callable[[], Session], execution_id: uuid.UUID
) -> None:
    session = session_factory()
    try:
        session.add(
            ToolCall(
                execution_id=execution_id,
                tool_name="get_low_stock",
                args={},
                raw_response={"sku": "85048", "quantity": 42},
                provenance_map={"sku": "observed", "quantity": "observed"},
                latency_ms=5,
                status="success",
            )
        )
        session.commit()
    finally:
        session.close()


def test_citation_validator_passes_a_grounded_answer_on_the_first_attempt(
    session_factory: Callable[[], Session],
) -> None:
    execution_id = _new_execution(session_factory)
    _seed_grounded_tool_call(session_factory, execution_id)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "decision":
            return _ai_message("There are 42 units of SKU 85048 in stock.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    assert len(result["citation_failures"]) == 1
    assert result["citation_failures"][0]["passed"] is True
    assert result["final_answer"] == "There are 42 units of SKU 85048 in stock."


def test_citation_validator_regenerates_once_then_succeeds(
    session_factory: Callable[[], Session],
) -> None:
    """The spec's "fail once -> regenerate" path: the first draft
    fabricates a figure; the Validator rejects it and Decision Engine
    gets a second attempt naming the offending value, which it corrects.
    """
    execution_id = _new_execution(session_factory)
    _seed_grounded_tool_call(session_factory, execution_id)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)
    decision_calls = {"count": 0}
    decision_prompts: list[str] = []

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "decision":
            decision_calls["count"] += 1
            decision_prompts.append(str(messages[1].content))
            if decision_calls["count"] == 1:
                return _ai_message("Revenue at risk is $99,999 this month.")
            return _ai_message("There are 42 units of SKU 85048 in stock.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    assert decision_calls["count"] == 2
    assert len(result["citation_failures"]) == 2
    assert result["citation_failures"][0]["passed"] is False
    assert result["citation_failures"][1]["passed"] is True
    assert result["final_answer"] == "There are 42 units of SKU 85048 in stock."
    # The regeneration prompt must name the offending value explicitly.
    assert "$99,999" in decision_prompts[1]
    assert "failed citation validation" in decision_prompts[1]


def test_citation_validator_gives_up_after_two_failed_attempts(
    session_factory: Callable[[], Session],
) -> None:
    """The spec's "fail twice -> INSUFFICIENT_DATA" path: a persistently
    fabricating Decision Engine must not get a third attempt.
    """
    execution_id = _new_execution(session_factory)
    agents = _six_agents()
    prompt_to_name = _dispatch_by_prompt(agents)
    decision_calls = {"count": 0}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "decision":
            decision_calls["count"] += 1
            return _ai_message(f"Revenue at risk is ${decision_calls['count'] * 1000}.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(
            execution_id=execution_id, query="q", budgets={"max_tool_iterations": 12}
        )
        result = graph.invoke(state)

    assert decision_calls["count"] == 2
    assert len(result["citation_failures"]) == 2
    assert all(not failure["passed"] for failure in result["citation_failures"])
    final_answer = result["final_answer"]
    assert final_answer is not None
    assert final_answer.startswith("INSUFFICIENT_DATA")
