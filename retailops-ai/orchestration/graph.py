"""Stage 3 Tasks 3.2/3.3/3.5: the LangGraph orchestration graph
connecting the six agents built in Task 3.1, including the replan loop
(Task 3.3) and the citation validator (Task 3.5).

Topology (per the spec): entry -> Planner -> PARALLEL fan-out to the
three retrieval agents (Inventory, Forecast, Analytics) -> Replan
(the Planner again, judging sufficiency) -> conditional:
  sufficient, or the iteration cap is reached -> Report -> Decision
    Engine -> Validator -> conditional:
      passed, or this was already the 2nd attempt -> end
      failed on the 1st attempt -> back to Decision Engine, regenerating
        with the offending values named explicitly (loop)
  insufficient and budget remains -> a second, TARGETED fan-out to just
    the retrieval agent(s) the judgement names -> Replan again (loop)

Confirmed by a standalone throwaway test before writing this file:
LangGraph's Pregel scheduler runs plain synchronous node functions
concurrently when they have no dependency edge between them (here, the
three retrieval agents fanned out from "planner") -- no async rewrite
of Agent.invoke() or the Gemini provider is needed to get genuine
wall-clock parallelism. `ExecutionState`'s `agent_results`,
`tool_ledger`, `provenance_map`, `timings`, and `replan_history` fields
all carry merge reducers (orchestration/state.py) for exactly this
reason: three nodes can write them in the same superstep.

Each retrieval node also reads back the `tool_calls` rows written
during its own `Agent.invoke()` call (tools/stockpilot_tools.py commits
one row per call) to populate `tool_ledger` and `provenance_map`.
`agent_step_id` isn't populated on `ToolCall` yet (a known gap), so
attribution combines two filters instead:
  - `tool_name` ownership -- each retrieval agent's tool subset
    (INVENTORY_TOOL_NAMES/FORECAST_TOOL_NAMES/ANALYTICS_TOOL_NAMES in
    agents/base.py) is disjoint by construction, so it rules out ever
    picking up a CONCURRENTLY-running sibling's row (unlike diffing
    tool_call_ids before/after with no name filter, which was proven to
    race across siblings in Task 3.2).
  - before/after id-diffing WITHIN that owned set -- needed now that
    Task 3.3 can re-invoke the same retrieval agent across replan
    rounds: without it, a round-2 query would re-count round-1's rows
    too, since both share the same owned tool names. Diffing is safe
    here because a single agent's own successive rounds are never
    concurrent with each other (round N+1 only starts after round N's
    replan judgement, which only starts after round N fully finishes) --
    it only failed in Task 3.2 when applied ACROSS different agents
    with no name filter to keep them apart in the first place.

Task 3.6 adds LLM-outage degradation: every node that calls agent.invoke()
or agent.invoke_structured() (all of them except the tool-less Validator)
now catches LLMUnavailableError (llm/providers/gemini.py -- raised only
after that call already retried 3x with backoff) and degrades its OWN
contribution instead of letting the exception blow up the whole graph
run. Each catch appends a plain-English entry to state["errors"] and
returns a node-appropriate fallback:
  - planner/replan: proceed with no plan / a forced-sufficient judgement
    (so the loop doesn't retry a call that's already known to be failing)
  - a retrieval agent: an explicit "[unavailable]" note as that agent's
    contribution -- the other, unaffected retrieval agents' real results
    still merge in via ExecutionState's reducers, since LangGraph's fan-out
    means each retrieval node's success/failure is independent
  - report/decision: a fixed INCOMPLETE message; for decision specifically,
    this becomes final_answer, since there is no later stage to recover
StockPilot-outage degradation (a *different* failure mode, "the answer
names the missing data explicitly") needs no equivalent graph-level catch:
agents/base.py::Agent._run_tool_call already absorbs a StockPilotUnavailableError
raised by a single tool call into a ToolMessage error string fed back to
that agent's own LLM loop, without ever raising past Agent.invoke() itself
-- confirmed by test_graph.py::test_stockpilot_outage_produces_a_grounded_answer_naming_the_gap.

Task 3.6 also flags truncated reasoning: _make_synthesis_node checks
whether the last replan_history entry has sufficient=False (meaning
Report was reached only because the iteration cap was hit, not because
the Planner judged the evidence sufficient) and, if so, tells Report and
Decision explicitly to flag the answer as based on incomplete evidence.
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
from agents.replan import ReplanJudgement
from llm.providers.gemini import LLMUnavailableError
from orchestration.models.tool_call import ToolCall
from orchestration.state import ExecutionState
from orchestration.validator import insufficient_data_message, validate_citations

RETRIEVAL_AGENT_NAMES = ("inventory", "forecast", "analytics")
# "Fail once -> regenerate. Fail twice -> INSUFFICIENT_DATA" per spec --
# a fixed cap distinct from budgets["max_tool_iterations"] (which bounds
# the replan loop, a different mechanism).
MAX_CITATION_ATTEMPTS = 2
# Task 3.6: the Decision Engine's own LLM-outage fallback text (set in
# _make_synthesis_node) is a fixed system-generated notice, not LLM-authored
# prose making a claim -- the citation validator (Task 3.5) exists to catch
# a model INVENTING a number, which doesn't apply here (and a retry count or
# similar digit embedded in the underlying exception's own message would
# otherwise get flagged as an ungrounded "citation", sending a known-broken
# LLM call around the regenerate loop pointlessly). _make_validator_node
# recognizes this exact prefix and skips citation checking for it.
LLM_DEGRADED_ANSWER_PREFIX = "INCOMPLETE:"

NodeFn = Callable[[ExecutionState], dict[str, object]]


def _content_str(message: AIMessage) -> str:
    # The Gemini provider always sets .content to a plain string (see
    # llm/providers/gemini.py::_response_to_ai_message); this only guards
    # against langchain_core's wider `str | list[str | dict]` type.
    content = message.content
    return content if isinstance(content, str) else str(content)


def _owned_tool_call_ids(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    owned_tool_names: set[str],
) -> set[uuid.UUID]:
    if not owned_tool_names:
        return set()
    session = session_factory()
    try:
        rows = (
            session.query(ToolCall.tool_call_id)
            .filter(
                ToolCall.execution_id == execution_id,
                ToolCall.tool_name.in_(owned_tool_names),
            )
            .all()
        )
        return {row.tool_call_id for row in rows}
    finally:
        session.close()


def _new_owned_tool_calls(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    owned_tool_names: set[str],
    before_ids: set[uuid.UUID],
) -> list[ToolCall]:
    if not owned_tool_names:
        return []
    session = session_factory()
    try:
        rows = (
            session.query(ToolCall)
            .filter(
                ToolCall.execution_id == execution_id,
                ToolCall.tool_name.in_(owned_tool_names),
            )
            .all()
        )
        return [row for row in rows if row.tool_call_id not in before_ids]
    finally:
        session.close()


def _make_planner_node(
    agent: Agent, session_factory: Callable[[], Session], execution_id: uuid.UUID
) -> NodeFn:
    def node(state: ExecutionState) -> dict[str, object]:
        prompt = state["query"]
        if state["memory_context"]:
            # Task 3.4: prior conversation history + rolling task memory,
            # passed "to the Planner" per spec -- no other node reads
            # memory_context, so this is the only place it's consumed.
            prompt = f"{state['memory_context']}\n\nCurrent question:\n{prompt}"

        started = time.monotonic()
        try:
            response = agent.invoke(
                prompt, session_factory=session_factory, execution_id=execution_id
            )
        except LLMUnavailableError as exc:
            ended = time.monotonic()
            return {
                "errors": [f"planner: {exc}"],
                "timings": {agent.name: {"start": started, "end": ended}},
            }
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
        iteration = len(state["replan_history"]) + 1
        prompt = state["query"]
        if state["replan_history"]:
            latest = state["replan_history"][-1]
            missing_raw = latest.get("missing")
            missing = [str(m) for m in missing_raw] if isinstance(missing_raw, list) else []
            next_action = str(latest.get("next_action", ""))
            prompt = (
                f"{prompt}\n\nThe Planner judged the evidence so far insufficient "
                f"and asked for this targeted follow-up: {next_action}\n"
                f"Specifically missing: {'; '.join(missing) if missing else 'unspecified'}"
            )
        elif state["plan"]:
            prompt = f"{prompt}\n\nPlanner's guidance:\n{state['plan']}"

        before_ids = _owned_tool_call_ids(session_factory, execution_id, owned_tool_names)

        started = time.monotonic()
        try:
            response = agent.invoke(
                prompt,
                session_factory=session_factory,
                execution_id=execution_id,
                iteration=iteration,
            )
        except LLMUnavailableError as exc:
            ended = time.monotonic()
            return {
                "agent_results": {
                    agent.name: f"[unavailable: {agent.name} agent could not reach the "
                    f"LLM after retries -- no data gathered this round: {exc}]"
                },
                "errors": [f"{agent.name} (round {iteration}): {exc}"],
                "timings": {f"{agent.name}_{iteration}": {"start": started, "end": ended}},
            }
        ended = time.monotonic()

        new_calls = _new_owned_tool_calls(
            session_factory, execution_id, owned_tool_names, before_ids
        )
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
            "timings": {f"{agent.name}_{iteration}": {"start": started, "end": ended}},
        }

    return node


def _make_replan_node(
    agent: Agent, session_factory: Callable[[], Session], execution_id: uuid.UUID
) -> NodeFn:
    """The Planner, re-invoked to judge sufficiency (Task 3.3) -- a
    tool-less structured-output call (invoke_structured), not the free
    text of the initial plan. `iteration` is derived from how many
    judgements exist already, not tracked as a separate state field:
    the replan_history this judgement is about to be appended to is
    exactly the round it's evaluating.
    """

    def node(state: ExecutionState) -> dict[str, object]:
        iteration = len(state["replan_history"]) + 1
        max_iterations = state["budgets"].get("max_tool_iterations", 1)

        sections = [f"Original question:\n{state['query']}"]
        if state["plan"]:
            sections.append(f"Initial plan:\n{state['plan']}")
        for name in RETRIEVAL_AGENT_NAMES:
            result = state["agent_results"].get(name)
            if result:
                sections.append(f"{name.capitalize()} agent findings:\n{result}")
        sections.append(
            f"This is your sufficiency judgement after retrieval round {iteration} "
            f"of at most {max_iterations}. Judge whether the evidence above is "
            "sufficient to answer the original question. If it is not, say exactly "
            "what's missing and name which retrieval agent(s) should run again with "
            "a more targeted ask."
        )
        prompt = "\n\n".join(sections)

        started = time.monotonic()
        try:
            judgement = agent.invoke_structured(
                prompt,
                ReplanJudgement,
                session_factory=session_factory,
                execution_id=execution_id,
                iteration=iteration,
            )
        except LLMUnavailableError as exc:
            ended = time.monotonic()
            # Forcing sufficient=True (rather than leaving it False and
            # letting the iteration cap eventually catch it) stops the loop
            # from spending its remaining budget on retrieval rounds whose
            # own replan judgement would hit this identical LLM outage
            # again -- proceed to Report with whatever evidence exists now.
            record: dict[str, object] = {
                "sufficient": True,
                "missing": [],
                "next_action": f"LLM unavailable after retries ({exc}); proceeding with "
                "evidence gathered so far.",
                "agents_to_retry": [],
                "iteration": iteration,
            }
            return {
                "replan_history": [record],
                "errors": [f"replan (round {iteration}): {exc}"],
                "timings": {f"replan_{iteration}": {"start": started, "end": ended}},
            }
        ended = time.monotonic()

        record = {**judgement.model_dump(), "iteration": iteration}
        return {
            "replan_history": [record],
            "timings": {f"replan_{iteration}": {"start": started, "end": ended}},
        }

    return node


def _route_after_replan(state: ExecutionState) -> str | list[str]:
    """sufficient, or the iteration cap already reached -> Report.
    Otherwise -> a targeted fan-out to just the agent(s) named in the
    judgement (falling back to all three if the model said insufficient
    but somehow named none, so the loop can't stall on a malformed
    judgement).
    """
    judgement = state["replan_history"][-1]
    max_iterations = state["budgets"].get("max_tool_iterations", 1)
    iteration_evaluated = len(state["replan_history"])
    if judgement["sufficient"] or iteration_evaluated >= max_iterations:
        return "report"
    agents_to_retry_raw = judgement.get("agents_to_retry")
    if isinstance(agents_to_retry_raw, list) and agents_to_retry_raw:
        return [str(a) for a in agents_to_retry_raw]
    return list(RETRIEVAL_AGENT_NAMES)


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
        if state["citation_failures"]:
            # Only ever non-empty when this is Decision Engine regenerating
            # after Task 3.5's Validator rejected its first attempt --
            # Report always runs before the Validator does, so this is a
            # no-op for the report node.
            latest = state["citation_failures"][-1]
            if not latest["passed"]:
                failures_raw = latest.get("failures")
                failure_list = failures_raw if isinstance(failures_raw, list) else []
                described = "; ".join(
                    f"{f['token']} ({f['reason']})" for f in failure_list if isinstance(f, dict)
                )
                sections.append(
                    "Your previous answer failed citation validation -- these values "
                    f"could not be verified against recorded tool data with provenance "
                    f"carried through: {described}. Rewrite your answer WITHOUT "
                    "restating those specific values; say plainly that the information "
                    "isn't available rather than guessing or rephrasing around it."
                )
        if state["replan_history"] and not state["replan_history"][-1]["sufficient"]:
            # Task 3.6: "iteration cap hit -> best effort, flagged as
            # truncated reasoning." Reached only when the iteration cap
            # (not genuine sufficiency) is why the graph routed here --
            # _route_after_replan sends "report" in both cases, so this is
            # the one place downstream that can still tell them apart.
            latest_judgement = state["replan_history"][-1]
            missing_raw = latest_judgement.get("missing")
            missing = [str(m) for m in missing_raw] if isinstance(missing_raw, list) else []
            missing_text = "; ".join(missing) if missing else "unspecified"
            sections.append(
                "Retrieval stopped at the iteration budget cap while the Planner still "
                "judged the evidence insufficient (not because it became sufficient). "
                "Explicitly flag your answer as based on incomplete, truncated evidence, "
                f"and state plainly what remained missing: {missing_text}."
            )
        prompt = "\n\n".join(sections)

        started = time.monotonic()
        try:
            response = agent.invoke(
                prompt, session_factory=session_factory, execution_id=execution_id
            )
        except LLMUnavailableError as exc:
            ended = time.monotonic()
            fallback = (
                f"{LLM_DEGRADED_ANSWER_PREFIX} the {agent.name} step could not reach the "
                f"LLM after retries ({exc}). This answer is flagged incomplete rather "
                "than fabricated -- retry the request."
            )
            update: dict[str, object] = {
                "agent_results": {agent.name: fallback},
                "errors": [f"{agent.name}: {exc}"],
                "timings": {agent.name: {"start": started, "end": ended}},
            }
            if is_final:
                update["final_answer"] = fallback
            return update
        ended = time.monotonic()

        content = _content_str(response)
        update = {
            "agent_results": {agent.name: content},
            "timings": {agent.name: {"start": started, "end": ended}},
        }
        if is_final:
            update["final_answer"] = content
        return update

    return node


def _make_validator_node(session_factory: Callable[[], Session], execution_id: uuid.UUID) -> NodeFn:
    """Task 3.5: runs after every Decision Engine draft, before it can
    ever reach `final_answer`'s intended recipient. Not an Agent (no LLM
    call -- pure deterministic checking), so it has no agent_steps row of
    its own; its trace lives entirely in `citation_failures`.

    Task 3.6: a draft starting with LLM_DEGRADED_ANSWER_PREFIX is the
    Decision node's own fixed system fallback for an exhausted LLM outage,
    not LLM-authored prose making a claim -- citation checking doesn't
    apply to it (and would otherwise misfire on a stray digit inside the
    wrapped exception's own message, e.g. a retry count). Passed
    immediately so the graph doesn't loop back to a Decision Engine call
    that's already known to be failing.
    """

    def node(state: ExecutionState) -> dict[str, object]:
        draft = state["final_answer"] or ""
        attempt = len(state["citation_failures"]) + 1
        if draft.startswith(LLM_DEGRADED_ANSWER_PREFIX):
            record: dict[str, object] = {"attempt": attempt, "passed": True, "failures": []}
            return {"citation_failures": [record]}
        failures = validate_citations(draft, session_factory, execution_id)

        record = {
            "attempt": attempt,
            "passed": not failures,
            "failures": [
                {"token": f.token, "value": f.value, "reason": f.reason} for f in failures
            ],
        }
        update: dict[str, object] = {"citation_failures": [record]}
        if failures and attempt >= MAX_CITATION_ATTEMPTS:
            update["final_answer"] = insufficient_data_message(failures)
        return update

    return node


def _route_after_validation(state: ExecutionState) -> str:
    """Passed -> end. Failed on the final allowed attempt -> end too
    (the validator node itself already replaced final_answer with the
    INSUFFICIENT_DATA message). Failed with attempts remaining -> back
    to Decision Engine to regenerate.
    """
    latest = state["citation_failures"][-1]
    attempt = latest["attempt"]
    if latest["passed"] or (isinstance(attempt, int) and attempt >= MAX_CITATION_ATTEMPTS):
        return END
    return "decision"


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
        "replan",
        cast(Any, _make_replan_node(agents["planner"], session_factory, execution_id)),
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
    builder.add_node("validator", cast(Any, _make_validator_node(session_factory, execution_id)))

    builder.add_edge(START, "planner")
    for name in RETRIEVAL_AGENT_NAMES:
        builder.add_edge("planner", name)
        builder.add_edge(name, "replan")
    builder.add_conditional_edges("replan", _route_after_replan, ["report", *RETRIEVAL_AGENT_NAMES])
    builder.add_edge("report", "decision")
    builder.add_edge("decision", "validator")
    builder.add_conditional_edges("validator", _route_after_validation, ["decision", END])

    return builder.compile()
