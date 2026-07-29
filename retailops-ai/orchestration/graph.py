"""Stage 3 Task 3.2: the LangGraph orchestration graph connecting the six
agents built in Task 3.1.

Topology (per the spec): entry -> Planner -> PARALLEL fan-out to the
three retrieval agents (Inventory, Forecast, Analytics) -> Report ->
Decision Engine -> end. The Validator is deliberately absent -- Task
3.5 ("Citation validator") is the task that adds it, and CLAUDE.md's
"no placeholders" rule means it isn't scaffolded here as an empty
pass-through node ahead of that.

Confirmed by a standalone throwaway test before writing this file:
LangGraph's Pregel scheduler runs plain synchronous node functions
concurrently when they have no dependency edge between them (here, the
three retrieval agents fanned out from "planner") -- no async rewrite
of Agent.invoke() or the Gemini provider is needed to get genuine
wall-clock parallelism. `ExecutionState`'s `agent_results`,
`tool_ledger`, `provenance_map`, and `timings` fields all carry merge
reducers (orchestration/state.py) for exactly this reason: three nodes
write them in the same superstep.

Each retrieval node also reads back the `tool_calls` rows written
during its own `Agent.invoke()` call (tools/stockpilot_tools.py commits
one row per call) to populate `tool_ledger` and `provenance_map`.
`agent_step_id` isn't populated on `ToolCall` yet (a known gap, see
scripts/verify_agents.py's precedent of documenting rather than
silently working around such gaps), so attribution is done by
`tool_name` ownership instead: each retrieval agent's tool subset
(INVENTORY_TOOL_NAMES/FORECAST_TOOL_NAMES/ANALYTICS_TOOL_NAMES in
agents/base.py) is disjoint by construction, and unlike diffing
before/after tool_call_id sets, ownership filtering can't misattribute
a row to a concurrently-running sibling node whose invocation window
happens to overlap the moment the row was committed. This assumes each
retrieval agent runs at most once per execution, true today; Task 3.3's
replan loop, which can re-invoke an agent within the same execution,
will need to revisit this once agent_step_id is wired up.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any, cast

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from agents.base import Agent
from orchestration.models.tool_call import ToolCall
from orchestration.state import ExecutionState

RETRIEVAL_AGENT_NAMES = ("inventory", "forecast", "analytics")

NodeFn = Callable[[ExecutionState], dict[str, object]]


def _content_str(message: AIMessage) -> str:
    # The Gemini provider always sets .content to a plain string (see
    # llm/providers/gemini.py::_response_to_ai_message); this only guards
    # against langchain_core's wider `str | list[str | dict]` type.
    content = message.content
    return content if isinstance(content, str) else str(content)


def _tool_calls_by_name(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    owned_tool_names: set[str],
) -> list[ToolCall]:
    if not owned_tool_names:
        return []
    session = session_factory()
    try:
        return (
            session.query(ToolCall)
            .filter(
                ToolCall.execution_id == execution_id,
                ToolCall.tool_name.in_(owned_tool_names),
            )
            .all()
        )
    finally:
        session.close()


def _make_planner_node(
    agent: Agent, session_factory: Callable[[], Session], execution_id: uuid.UUID
) -> NodeFn:
    def node(state: ExecutionState) -> dict[str, object]:
        started = time.monotonic()
        response = agent.invoke(
            state["query"], session_factory=session_factory, execution_id=execution_id
        )
        ended = time.monotonic()
        return {
            "plan": _content_str(response),
            "timings": {agent.name: {"start": started, "end": ended}},
        }

    return node


def _make_retrieval_node(
    agent: Agent, session_factory: Callable[[], Session], execution_id: uuid.UUID
) -> NodeFn:
    owned_tool_names = {tool.name for tool in agent.tools}

    def node(state: ExecutionState) -> dict[str, object]:
        prompt = state["query"]
        if state["plan"]:
            prompt = f"{prompt}\n\nPlanner's guidance:\n{state['plan']}"

        started = time.monotonic()
        response = agent.invoke(prompt, session_factory=session_factory, execution_id=execution_id)
        ended = time.monotonic()

        new_calls = _tool_calls_by_name(session_factory, execution_id, owned_tool_names)
        provenance: dict[str, str] = {}
        ledger: list[dict[str, str | int | None]] = []
        for call in new_calls:
            if call.provenance_map:
                provenance.update(call.provenance_map)
            ledger.append(
                {
                    "tool_call_id": str(call.tool_call_id),
                    "tool_name": call.tool_name,
                    "status": call.status,
                    "latency_ms": call.latency_ms,
                }
            )

        return {
            "agent_results": {agent.name: _content_str(response)},
            "tool_ledger": ledger,
            "provenance_map": provenance,
            "timings": {agent.name: {"start": started, "end": ended}},
        }

    return node


def _make_synthesis_node(
    agent: Agent,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    *,
    is_final: bool,
) -> NodeFn:
    def node(state: ExecutionState) -> dict[str, object]:
        sections = [f"User query:\n{state['query']}"]
        if state["plan"]:
            sections.append(f"Planner's plan:\n{state['plan']}")
        for name in (*RETRIEVAL_AGENT_NAMES, "report"):
            result = state["agent_results"].get(name)
            if result:
                sections.append(f"{name.capitalize()} agent findings:\n{result}")
        prompt = "\n\n".join(sections)

        started = time.monotonic()
        response = agent.invoke(prompt, session_factory=session_factory, execution_id=execution_id)
        ended = time.monotonic()

        content = _content_str(response)
        update: dict[str, object] = {
            "agent_results": {agent.name: content},
            "timings": {agent.name: {"start": started, "end": ended}},
        }
        if is_final:
            update["final_answer"] = content
        return update

    return node


def build_execution_graph(
    agents: dict[str, Agent],
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> CompiledStateGraph[ExecutionState, None, ExecutionState, ExecutionState]:
    """Wires the six Task 3.1 agents into the graph topology above. Node
    bodies are closures over `agents`/`session_factory`/`execution_id`
    rather than passing those through LangGraph's state or config
    machinery -- they're live runtime dependencies (a DB session
    factory, tool-bound agent instances), not serializable execution
    data, so they don't belong in `ExecutionState`.
    """
    builder: StateGraph[ExecutionState, None, ExecutionState, ExecutionState] = StateGraph(
        ExecutionState
    )

    # cast(Any, ...): each factory's return type (Callable[[ExecutionState],
    # dict[str, object]]) is correctly typed at its own definition, but mypy
    # can't unify a `collections.abc.Callable`-typed *value* against
    # add_node's generic `_Node[NodeInputT]` Protocol overloads during type
    # inference (confirmed with a minimal repro against a plain `def` passed
    # directly, which mypy accepts fine) -- a mypy/langgraph-stubs
    # limitation with Callable-vs-Protocol matching in overloaded generics,
    # not a real type-safety gap in these node functions.
    builder.add_node(
        "planner",
        cast(Any, _make_planner_node(agents["planner"], session_factory, execution_id)),
    )
    for name in RETRIEVAL_AGENT_NAMES:
        builder.add_node(
            name,
            cast(Any, _make_retrieval_node(agents[name], session_factory, execution_id)),
        )
    builder.add_node(
        "report",
        cast(
            Any,
            _make_synthesis_node(agents["report"], session_factory, execution_id, is_final=False),
        ),
    )
    builder.add_node(
        "decision",
        cast(
            Any,
            _make_synthesis_node(agents["decision"], session_factory, execution_id, is_final=True),
        ),
    )

    builder.add_edge(START, "planner")
    for name in RETRIEVAL_AGENT_NAMES:
        builder.add_edge("planner", name)
        builder.add_edge(name, "report")
    builder.add_edge("report", "decision")
    builder.add_edge("decision", END)

    return builder.compile()
