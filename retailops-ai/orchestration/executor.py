"""Stage 3 Task 3.4: the orchestration entrypoint tying one full agent
turn together -- creates or continues a conversation, loads prior-turn
memory, runs the graph, and persists the turn's Message rows plus the
Execution row's own summary fields (created with status="running" at
Task 2.1 and never updated again since; this is what actually completes
that write) so the NEXT turn in the same conversation can see it.

This is the callable core of what Task 3.6's `POST /agent/query` will
eventually wrap in an HTTP route. Building the entrypoint now, ahead of
that route, is what lets Task 3.4's own milestone -- a follow-up
question that depends on the previous turn -- actually be run and
verified: there is nothing else in the codebase yet that ties a
conversation, memory, and a graph run together into one turn.

Stage 6: run_execution_streaming() is the SSE-serving sibling of
run_execution() -- same setup and same final persistence tail (both now
factored into _setup_execution()/_persist_execution_result() so neither
copy can silently drift from the other), but consumes the graph via
graph.stream(...) instead of graph.invoke(...), yielding progress events
as the graph runs. build_query_response_fields() is the third shared
piece: the exact response shape api/agent.py's POST /agent/query needs,
usable identically after either function finishes.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import cast

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.base import build_agents
from clients.stockpilot import StockPilotClient
from model_config import get_model_config
from orchestration.graph import build_execution_graph
from orchestration.memory import load_conversation_context
from orchestration.models.agent_step import AgentStep
from orchestration.models.conversation import Conversation
from orchestration.models.execution import Execution
from orchestration.models.message import Message
from orchestration.state import ExecutionState, new_execution_state


def _setup_execution(
    query: str,
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID | None,
    *,
    streaming: bool = False,
) -> tuple[
    CompiledStateGraph[ExecutionState, None, ExecutionState, ExecutionState],
    ExecutionState,
    uuid.UUID,
    uuid.UUID,
]:
    """Everything both run_execution() and run_execution_streaming() do
    identically before actually running the graph: create/continue the
    conversation, load prior-turn memory (before this turn's own rows
    exist, so it only ever reflects genuinely prior turns -- see
    orchestration/memory.py's docstring for why the ordering matters),
    persist the user's own Message and a fresh "running" Execution row,
    and build the graph + its initial state. Returns
    (graph, state, execution_id, conversation_id) -- conversation_id is
    returned even though the caller may have already passed one in,
    since a None input is resolved to a real id here.
    """
    budgets = get_model_config().budgets.model_dump()

    session = session_factory()
    try:
        if conversation_id is None:
            conversation = Conversation()
            session.add(conversation)
            session.commit()
            conversation_id = conversation.id
    finally:
        session.close()

    memory_context = load_conversation_context(session_factory, conversation_id)

    session = session_factory()
    try:
        session.add(Message(conversation_id=conversation_id, role="user", content=query))
        execution = Execution(
            conversation_id=conversation_id, query=query, status="running", budgets=budgets
        )
        session.add(execution)
        session.commit()
        execution_id = execution.id
    finally:
        session.close()

    agents = build_agents(client, session_factory, execution_id)
    graph = build_execution_graph(agents, session_factory, execution_id, streaming=streaming)
    state = new_execution_state(
        execution_id=execution_id,
        query=query,
        budgets=budgets,
        conversation_id=conversation_id,
        memory_context=memory_context,
    )
    return graph, state, execution_id, conversation_id


def _persist_execution_result(
    result: ExecutionState,
    conversation_id: uuid.UUID,
    execution_id: uuid.UUID,
    session_factory: Callable[[], Session],
) -> None:
    """The tail both run_execution() and run_execution_streaming() run
    once the graph has genuinely finished (blocking invoke() returned,
    or streaming iteration exhausted): the assistant's own Message row,
    the total-tokens aggregate over this execution's AgentStep rows, and
    the Execution row's final status/plan/final_answer/provenance_map/
    errors/completed_at -- these columns existed since Task 2.1's
    scaffold but nothing had ever populated them until this function.
    """
    session = session_factory()
    try:
        session.add(
            Message(
                conversation_id=conversation_id,
                execution_id=execution_id,
                role="assistant",
                content=result["final_answer"] or "",
            )
        )
        total_tokens = (
            session.query(
                func.coalesce(
                    func.sum(
                        func.coalesce(AgentStep.prompt_tokens, 0)
                        + func.coalesce(AgentStep.completion_tokens, 0)
                    ),
                    0,
                )
            )
            .filter(AgentStep.execution_id == execution_id)
            .scalar()
        )

        db_execution = session.get(Execution, execution_id)
        assert db_execution is not None
        errors_payload: dict[str, object] = {}
        if result["errors"]:
            errors_payload["messages"] = result["errors"]
        if result["citation_failures"]:
            # Task 3.5: the Validator's own trace isn't an AgentStep row
            # (it's not one of the six named agents), so this is where
            # its full history durably lives beyond the graph's own
            # ephemeral return value.
            errors_payload["citation_failures"] = result["citation_failures"]

        if not result["final_answer"]:
            db_execution.status = "failed"
        elif result["errors"]:
            # Task 3.6: state["errors"] is populated only by the graph's own
            # LLM/StockPilot-outage degradation paths (orchestration/graph.py),
            # distinct from citation_failures (Task 3.5's own, separately
            # tracked validator mechanism) -- an execution that finished via
            # the validator's INSUFFICIENT_DATA path with no LLM/tool outage
            # is still "completed", not "degraded".
            db_execution.status = "degraded"
        else:
            db_execution.status = "completed"
        db_execution.plan = {"text": result["plan"]} if result["plan"] else None
        db_execution.final_answer = result["final_answer"]
        db_execution.provenance_map = result["provenance_map"] or None
        db_execution.errors = errors_payload or None
        db_execution.total_tokens = total_tokens
        db_execution.completed_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()


def build_query_response_fields(
    state: ExecutionState, session_factory: Callable[[], Session]
) -> dict[str, object]:
    """The shared response shape api/agent.py's POST /agent/query needs,
    for both the blocking JSON path and the streaming "done" SSE event --
    reads status/final_answer/total_tokens fresh from the persisted
    Execution row (written by _persist_execution_result just before this
    is called), since those three differ from state's own raw fields:
    state doesn't track "status" at all, and DB total_tokens is a SQL
    aggregate over AgentStep rows, never carried in ExecutionState itself.
    """
    session = session_factory()
    try:
        execution = session.get(Execution, state["execution_id"])
    finally:
        session.close()
    assert execution is not None, "run_execution() always persists its own Execution row"
    assert execution.conversation_id is not None, "run_execution() always assigns a conversation"
    return {
        "execution_id": execution.id,
        "conversation_id": execution.conversation_id,
        "status": execution.status,
        "answer": execution.final_answer,
        "plan": state["plan"],
        "agent_results": state["agent_results"],
        "tool_ledger": state["tool_ledger"],
        "provenance_map": state["provenance_map"],
        "replan_rounds": len(state["replan_history"]),
        "citation_attempts": len(state["citation_failures"]),
        "errors": state["errors"],
        "total_tokens": execution.total_tokens,
    }


def run_execution(
    query: str,
    *,
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID | None = None,
) -> ExecutionState:
    """Runs one full conversation turn against a real graph and returns
    its final state. Pass `conversation_id` to continue an existing
    thread (its Message/Execution history informs the Planner); omit it
    to start a new one.
    """
    graph, state, execution_id, conversation_id = _setup_execution(
        query, client, session_factory, conversation_id
    )

    # cast: CompiledStateGraph.invoke()'s return type doesn't narrow to the
    # exact ExecutionState TypedDict here even though it's the graph's own
    # declared output schema -- the same generic-inference limitation
    # noted in build_execution_graph's own add_node casts.
    result = cast(ExecutionState, graph.invoke(state))

    _persist_execution_result(result, conversation_id, execution_id, session_factory)
    return result


def run_execution_streaming(
    query: str,
    *,
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID | None = None,
) -> Iterator[dict[str, object]]:
    """The SSE-serving sibling of run_execution() -- same conversation
    setup and the same final persistence tail (both shared via
    _setup_execution()/_persist_execution_result(), so this can't drift
    from the blocking path's own behaviour), but consumes the graph via
    graph.stream(..., stream_mode=["custom", "values"]) instead of
    graph.invoke(), yielding progress events as the graph actually runs.
    The final yielded event (type="done") carries the exact same fields
    build_query_response_fields() gives run_execution()'s own caller --
    everything before it is a live signal layered on top of that same
    eventual result, not a different execution.

    Event shapes yielded:
      {"type": "token", "node": "decision", "text": "..."} -- one per
        text delta from the decision node's own generation (only ever
        the "decision" node, since orchestration/graph.py's streaming
        wiring is scoped to the one node whose text is the live answer).
      {"type": "agent_completed", "agent": name, "output": text} -- once
        per agent the moment its result lands in state["agent_results"]
        (derived from LangGraph's own "values" mode, no graph.py change
        needed for this one).
      {"type": "replan_judgement", "iteration": ..., "sufficient": ...,
        "missing": [...], "next_action": "...", "agents_to_retry": [...]}
        -- once per replan round, straight from state["replan_history"].
      {"type": "citation_check", "attempt": ..., "passed": ...,
        "failures": [...]} -- once per Validator attempt. A caller that
        sees passed=False followed by more "token" events should treat
        those as a FRESH draft, not a continuation of the rejected one --
        the Decision Engine is regenerating from scratch, not editing.
      {"type": "done", ...} -- exactly once, last: the same field shape
        build_query_response_fields() returns.
    """
    graph, state, execution_id, conversation_id = _setup_execution(
        query, client, session_factory, conversation_id, streaming=True
    )

    previous_agents: set[str] = set()
    previous_replan_rounds = 0
    previous_citation_attempts = 0
    final_state: ExecutionState = state

    for mode, chunk in graph.stream(state, stream_mode=["custom", "values"]):
        if mode == "custom":
            yield dict(cast(dict[str, object], chunk))
            continue

        current = cast(ExecutionState, chunk)
        final_state = current

        new_agents = set(current["agent_results"]) - previous_agents
        for name in sorted(new_agents):
            yield {
                "type": "agent_completed",
                "agent": name,
                "output": current["agent_results"][name],
            }
        previous_agents = set(current["agent_results"])

        if len(current["replan_history"]) > previous_replan_rounds:
            judgement = current["replan_history"][-1]
            yield {"type": "replan_judgement", **judgement}
            previous_replan_rounds = len(current["replan_history"])

        if len(current["citation_failures"]) > previous_citation_attempts:
            check = current["citation_failures"][-1]
            yield {"type": "citation_check", **check}
            previous_citation_attempts = len(current["citation_failures"])

    _persist_execution_result(final_state, conversation_id, execution_id, session_factory)
    fields = build_query_response_fields(final_state, session_factory)
    yield {"type": "done", **fields}
