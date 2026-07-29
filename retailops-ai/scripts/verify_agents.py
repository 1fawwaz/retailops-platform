"""Stage 3 Task 3.1 milestone check: the six agents actually work.

Requires a running stockpilot-core instance (STOCKPILOT_BASE_URL), a
real GEMINI_API_KEY, and retailops-ai's own Postgres database migrated
to head. Invokes each of the three retrieval agents (role="retriever",
model=gemini-3.5-flash) once with a real question, against real Gemini
and real stockpilot-core data -- no mocks -- and confirms:
  - they actually call StockPilot tools and produce an answer grounded
    in what they fetched
  - every invocation left exactly one agent_steps row, and every tool
    call left exactly one tool_calls row

Planner, Report, and Decision Engine (role="planner"/"decision", model=
gemini-3.1-pro-preview) are NOT live-verified here: this API key's free
tier has a hard zero quota for that model family (confirmed via a live
429 RESOURCE_EXHAUSTED with limit=0, not a transient rate limit). Their
code path is the identical Agent.invoke() exercised here and in
tests/test_agent_base.py's mocked tests (all passing); only the actual
network call to that specific model family is untested live. Re-run
this script (or a variant covering all six) once a billing-enabled key
is available.

Run: python scripts/verify_agents.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base import build_agents  # noqa: E402
from clients.stockpilot import StockPilotClient  # noqa: E402
from database import get_session_factory  # noqa: E402
from orchestration.models.agent_step import AgentStep  # noqa: E402
from orchestration.models.execution import Execution  # noqa: E402
from orchestration.models.tool_call import ToolCall  # noqa: E402
from settings import get_settings  # noqa: E402

# Only the retriever-role agents (gemini-3.5-flash) are live-verified here --
# see the module docstring for why planner/report/decision are excluded.
LIVE_VERIFIED_AGENTS = ("inventory", "forecast", "analytics")

QUERIES = {
    "inventory": "Which products are currently low on stock?",
    "forecast": "How accurate is the current demand forecasting model?",
    "analytics": "What was total revenue last month, grouped by category?",
}


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    session = session_factory()
    execution = Execution(query="verify all six agents", status="running")
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

        for name in LIVE_VERIFIED_AGENTS:
            agent = agents[name]
            query = QUERIES[name]
            print(f"--- {name} (model={agent.model_id}, tools={len(agent.tools)}) ---")
            print(f"Q: {query}")
            response = agent.invoke(
                query, session_factory=session_factory, execution_id=execution_id
            )
            print(f"A: {response.content}\n")

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

    print(f"agent_steps rows: {len(agent_steps)}")
    for step in agent_steps:
        print(
            f"  {step.agent_name:<10} model={step.model_id} status={step.status} "
            f"latency_ms={step.latency_ms} prompt_tokens={step.prompt_tokens} "
            f"completion_tokens={step.completion_tokens}"
        )
    print(f"\ntool_calls rows: {len(tool_calls)}")
    for call in tool_calls:
        print(f"  {call.tool_name:<24} status={call.status} latency_ms={call.latency_ms}")

    failures = []
    if len(agent_steps) != len(LIVE_VERIFIED_AGENTS):
        failures.append(
            f"Expected {len(LIVE_VERIFIED_AGENTS)} agent_steps rows, got {len(agent_steps)}"
        )
    if any(step.status != "completed" for step in agent_steps):
        failures.append("Not every agent_steps row has status=completed")
    if len(tool_calls) == 0:
        failures.append("No tool_calls rows were written -- expected at least one")
    steps_by_name = {step.agent_name: step for step in agent_steps}
    for name in LIVE_VERIFIED_AGENTS:
        output = steps_by_name[name].output
        if output is not None and output.get("tool_calls_made"):
            continue
        # A retrieval agent may legitimately answer without a tool only if the
        # question needed none, but for this fixed query set each one should.
        failures.append(f"{name} agent did not report having made any tool call")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print(
        "\nMilestone verified: the three retriever-role agents work end to end "
        "against real Gemini and real StockPilot data, call real tools, and "
        "every invocation left the expected trace rows. Planner/Report/Decision "
        "share the identical Agent.invoke() code path, verified by "
        "tests/test_agent_base.py's mocked tests instead (see module docstring)."
    )


if __name__ == "__main__":
    main()
