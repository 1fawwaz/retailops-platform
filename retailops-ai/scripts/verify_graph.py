"""Stage 3 Task 3.2/3.3 milestone check: the graph runs end to end, the
retrieval agents provably run concurrently -- show timings -- and the
replan loop demonstrably triggers a second, targeted retrieval round.

Requires a running stockpilot-core instance (STOCKPILOT_BASE_URL), a
real GEMINI_API_KEY, and retailops-ai's own Postgres database migrated
to head.

Planner/Report/Decision Engine (role="planner"/"decision") are NOT
called live here, for the same reason scripts/verify_agents.py excludes
them: this API key's free tier has a hard zero quota for that model
family (confirmed via a live 429 RESOURCE_EXHAUSTED with limit=0). This
script patches those two roles' calls to llm.providers.gemini.generate
AND generate_structured (the replan judgement, Task 3.3, also runs on
the "planner" role) with an immediate canned response so the graph's
full topology can still run start to finish against a real database --
the three retrieval agents (role="retriever") make real Gemini calls
and real StockPilot tool calls, completely unpatched. The milestones
this task cares about (retrieval-agent concurrency, the replan loop
firing) are entirely inside that unpatched section: the mocked replan
judgement deliberately says "insufficient, retry forecast" on its first
call so the second, targeted round's forecast re-invocation is also a
real live call, not just the first round's.

A second, tighter constraint surfaced while writing this script: this
key's free tier also caps gemini-3.5-flash (the retriever role) at
"generate_content_free_tier_requests, limit: 20" -- and in practice
that quota behaves as a small, slowly-refilling burst allowance rather
than a clean once-a-day reset, so three genuinely SIMULTANEOUS calls
(exactly what this script's concurrent fan-out sends) reliably exhaust
it and fail with 429 even when sequential calls spaced a few seconds
apart succeed. This isn't a bug in the graph -- see
tests/test_graph.py::test_retrieval_agents_run_concurrently, which
proves the same real graph object (build_execution_graph) genuinely
runs its retrieval nodes concurrently with overlapping wall-clock
timing windows, using the identical Agent.invoke() code path with only
the network call itself mocked. Running *this* script end to end needs
a billing-enabled key; re-run it once one is available.

While debugging this quota wall, this script's first version also
surfaced a real, previously-unknown bug in llm/providers/gemini.py: the
single process-wide cached genai.Client (the original fix for a
different bug -- see that module's docstring) isn't safe for two
threads calling .models.generate_content() on it at the same instant,
failing with "Cannot send a request, as the client has been closed."
Reproduced independently of this script or LangGraph with two bare
threads calling generate() concurrently, then fixed by caching one
Client per thread instead of one per process -- confirmed fixed by the
same reproduction, which then only hit the quota wall above, not the
closed-client error.

Run: python scripts/verify_graph.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage  # noqa: E402

from agents.base import build_agents  # noqa: E402
from agents.replan import ReplanJudgement  # noqa: E402
from clients.stockpilot import StockPilotClient  # noqa: E402
from database import get_session_factory  # noqa: E402
from llm.providers.gemini import StructuredResult  # noqa: E402
from llm.providers.gemini import generate as real_generate  # noqa: E402
from model_config import get_model_config  # noqa: E402
from orchestration.graph import RETRIEVAL_AGENT_NAMES, build_execution_graph  # noqa: E402
from orchestration.models.agent_step import AgentStep  # noqa: E402
from orchestration.models.execution import Execution  # noqa: E402
from orchestration.models.tool_call import ToolCall  # noqa: E402
from orchestration.state import new_execution_state  # noqa: E402
from settings import get_settings  # noqa: E402

QUERY = "Which products are low on stock, and what does demand forecasting say about them?"

_replan_calls = {"count": 0}


def _patched_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
    roles = get_model_config().roles
    if model == roles.retriever:
        return real_generate(model=model, messages=messages, tools=tools)
    # Planner/Report/Decision Engine share the zero-quota model family --
    # see the module docstring. A fast, fixed stand-in keeps the graph's
    # real topology (including the reducers merging the three retrieval
    # agents' concurrent writes) exercised end to end regardless.
    return AIMessage(
        content=f"[mocked -- quota-blocked model '{model}'] acknowledged.",
        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )


def _patched_generate_structured(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[Any]:
    # Only the replan judgement (agents/replan.py::ReplanJudgement) calls
    # generate_structured() anywhere in this graph, and it always runs on
    # the zero-quota "planner" role -- see the module docstring. The first
    # call says insufficient and names "forecast" for a targeted retry, so
    # the SECOND fan-out's forecast call is also a real live Gemini +
    # StockPilot call, not just the first round's.
    _replan_calls["count"] += 1
    if _replan_calls["count"] == 1:
        judgement = ReplanJudgement(
            sufficient=False,
            missing=["a closer look at demand forecasting for the flagged SKUs"],
            next_action="forecast agent, targeted retrieval",
            agents_to_retry=["forecast"],
        )
    else:
        judgement = ReplanJudgement(
            sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
        )
    return StructuredResult(
        parsed=judgement, usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    budgets = get_model_config().budgets.model_dump()

    session = session_factory()
    execution = Execution(query=QUERY, status="running")
    session.add(execution)
    session.commit()
    execution_id = execution.id
    session.close()

    print(f"execution_id = {execution_id}\n")

    with StockPilotClient(
        base_url=settings.stockpilot_base_url,
        username=settings.stockpilot_username,
        password=settings.stockpilot_password,
    ) as client:
        agents = build_agents(client, session_factory, execution_id)
        graph = build_execution_graph(agents, session_factory, execution_id)
        state = new_execution_state(execution_id=execution_id, query=QUERY, budgets=budgets)

        with (
            patch("agents.base.generate", side_effect=_patched_generate),
            patch("agents.base.generate_structured", side_effect=_patched_generate_structured),
        ):
            result = graph.invoke(state)

    print(f"final_answer: {result['final_answer']}\n")

    print(f"replan_history ({len(result['replan_history'])} round(s)):")
    for judgement in result["replan_history"]:
        print(f"  iteration={judgement['iteration']} sufficient={judgement['sufficient']}")
        print(f"    missing: {judgement['missing']}")
        print(f"    next_action: {judgement['next_action']}")

    print("\ntimings (relative to the earliest node start):")
    graph_start = min(t["start"] for t in result["timings"].values())
    for name, window in sorted(result["timings"].items(), key=lambda kv: kv[1]["start"]):
        print(
            f"  {name:<16} start={window['start'] - graph_start:6.3f}s  "
            f"end={window['end'] - graph_start:6.3f}s"
        )

    round_1_windows = {name: result["timings"][f"{name}_1"] for name in RETRIEVAL_AGENT_NAMES}
    overlap_found = any(
        round_1_windows[a]["start"] < round_1_windows[b]["end"]
        and round_1_windows[b]["start"] < round_1_windows[a]["end"]
        for a in round_1_windows
        for b in round_1_windows
        if a != b
    )

    verify_session = session_factory()
    try:
        agent_steps = (
            verify_session.query(AgentStep)
            .filter(AgentStep.execution_id == execution_id)
            .order_by(AgentStep.started_at)
            .all()
        )
        tool_calls = (
            verify_session.query(ToolCall).filter(ToolCall.execution_id == execution_id).all()
        )
    finally:
        verify_session.close()

    print(f"\nagent_steps rows: {len(agent_steps)}")
    for step in agent_steps:
        print(
            f"  {step.agent_name:<10} iteration={step.iteration} model={step.model_id} "
            f"status={step.status}"
        )
    print(f"tool_calls rows: {len(tool_calls)}")

    forecast_iterations = sorted(s.iteration for s in agent_steps if s.agent_name == "forecast")

    failures = []
    if set(result["agent_results"]) != {"inventory", "forecast", "analytics", "report", "decision"}:
        failures.append(f"Unexpected agent_results keys: {set(result['agent_results'])}")
    if result["final_answer"] is None:
        failures.append("final_answer was not set")
    if len(result["replan_history"]) != 2:
        failures.append(f"Expected 2 replan rounds, got {len(result['replan_history'])}")
    if forecast_iterations != [1, 2]:
        failures.append(
            f"Expected forecast to run in iterations [1, 2] (the replan loop's targeted "
            f"retry), got {forecast_iterations}"
        )
    if not overlap_found:
        failures.append(
            f"No timing overlap found among round-1 retrieval agents: {round_1_windows}"
        )

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print(
        "\nMilestone verified: the full graph topology (entry -> planner -> "
        "parallel retrieval fan-out -> replan -> [targeted retry] -> report -> "
        "decision -> end) ran end to end; round 1's three retrieval agents' "
        "timing windows genuinely overlap -- real concurrent execution, not "
        "just sequential calls that happen to be fast -- and the replan loop "
        "demonstrably triggered a second, targeted round (forecast re-ran in "
        "iteration 2 with real Gemini and real StockPilot calls), with the "
        "Planner's sufficiency reasoning visible in replan_history."
    )


if __name__ == "__main__":
    main()
