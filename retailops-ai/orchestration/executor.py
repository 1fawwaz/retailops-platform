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
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

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

    # Loaded before this turn's own rows exist below, so it only ever
    # reflects genuinely prior turns (see orchestration/memory.py's
    # docstring for why the ordering here matters).
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
    graph = build_execution_graph(agents, session_factory, execution_id)
    state = new_execution_state(
        execution_id=execution_id,
        query=query,
        budgets=budgets,
        conversation_id=conversation_id,
        memory_context=memory_context,
    )

    # cast: CompiledStateGraph.invoke()'s return type doesn't narrow to the
    # exact ExecutionState TypedDict here even though it's the graph's own
    # declared output schema -- the same generic-inference limitation
    # noted in build_execution_graph's own add_node casts.
    result = cast(ExecutionState, graph.invoke(state))

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

    return result
