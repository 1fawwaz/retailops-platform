"""Stage 3 Task 3.2: the typed state object threaded through the graph.

Fields match what CLAUDE.md invariant 2 (full trace) and the spec's Task
3.2 description both require the graph to carry: execution_id, query,
plan, agent results, tool ledger, provenance map, errors, budgets --
plus `timings`, needed to demonstrate the milestone (retrieval agents
provably running concurrently), and `final_answer`, the Decision
Engine's output.

`agent_results`, `tool_ledger`, `provenance_map`, `errors`, and
`timings` are all written by more than one node in the same superstep
(the three retrieval agents fan out from the Planner in parallel), so
each needs a reducer telling LangGraph how to merge concurrent partial
updates instead of raising a conflict -- confirmed necessary and
sufficient by a throwaway concurrency test before writing this file.

Task 3.3 adds `replan_history`: one entry per replan round, each the
Planner's structured sufficiency judgement (agents/replan.py) plus the
`iteration` number the graph attaches. It does double duty as the
persisted trace record the spec requires AND the thing the graph's own
conditional routing reads to decide sufficient-vs-retry -- no separate
routing-only field needed, since `len(replan_history)` after a replan
node runs is exactly the round it just evaluated.

Task 3.4 adds `conversation_id` (which thread this execution belongs
to, or None for a standalone one-off run) and `memory_context` (prior
conversation history + rolling task memory, rendered by
orchestration/memory.py and loaded once before the graph starts -- not
recomputed by any node). Per spec, this memory is passed "to the
Planner" specifically, not to every agent, so only the planner node
reads `memory_context`; it isn't threaded any further than that.

Task 3.5 adds `citation_failures`: one entry per Validator attempt
(orchestration/validator.py), the same double-duty pattern as
`replan_history` -- persisted trace record AND the thing the graph's
own conditional routing reads to decide pass/regenerate/give-up, via
`len(citation_failures)` after a Validator run being exactly the
attempt it just evaluated.
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, TypedDict


def _merge_dicts(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    return {**left, **right}


def _merge_timings(
    left: dict[str, dict[str, float]], right: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    return {**left, **right}


class ExecutionState(TypedDict):
    execution_id: uuid.UUID
    conversation_id: uuid.UUID | None
    query: str
    memory_context: str | None
    plan: str | None
    agent_results: Annotated[dict[str, str], _merge_dicts]
    tool_ledger: Annotated[list[dict[str, str | int | None]], operator.add]
    provenance_map: Annotated[dict[str, str], _merge_dicts]
    # Not written by any node yet -- populated once the graph gains
    # degradation logic (Task 3.6). Present now because the spec lists it
    # as one of the state object's required fields for this task.
    errors: Annotated[list[str], operator.add]
    budgets: dict[str, int]
    timings: Annotated[dict[str, dict[str, float]], _merge_timings]
    replan_history: Annotated[list[dict[str, object]], operator.add]
    citation_failures: Annotated[list[dict[str, object]], operator.add]
    final_answer: str | None


def new_execution_state(
    *,
    execution_id: uuid.UUID,
    query: str,
    budgets: dict[str, int],
    conversation_id: uuid.UUID | None = None,
    memory_context: str | None = None,
) -> ExecutionState:
    """The all-fields-present initial state every graph run starts from --
    `ExecutionState` has no optional keys, so every caller needs one of
    these rather than hand-rolling a partial dict.
    """
    return ExecutionState(
        execution_id=execution_id,
        conversation_id=conversation_id,
        query=query,
        memory_context=memory_context,
        plan=None,
        agent_results={},
        tool_ledger=[],
        provenance_map={},
        errors=[],
        budgets=budgets,
        timings={},
        replan_history=[],
        citation_failures=[],
        final_answer=None,
    )
