"""09-ambiguous-question: "How's business?" has no single correct
reading -- the Planner must clarify or state its own interpretation
(prompts/planner/v1.md, written in Task 3.1), and that interpretation
must actually reach the final answer, not just live in the internal
plan text nobody sees (the same check Task 4.5's own query-coverage
suite already proved once; rebuilt here as a first-class eval scenario).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2
from sqlalchemy.orm import Session

from clients.stockpilot import StockPilotClient
from evals.scenarios.base import (
    ExpectedFact,
    Scenario,
    ScenarioOutcome,
    ScriptedGenerate,
    ai_message,
    run_chat_scenario,
    tool_call_message,
)
from evals.scenarios.fixtures import login_response, period_comparison_payload

QUESTION = "How's business?"
INTERPRETATION = (
    "This is ambiguous -- I'm interpreting it as a request for overall recent revenue "
    "and profit performance."
)


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/analytics/period-comparison":
        return httpx2.Response(
            200, json=period_comparison_payload(period1_revenue=10000.0, period2_revenue=8000.0)
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "planner": [ai_message(INTERPRETATION)],
            "analytics": [
                tool_call_message(
                    "get_period_comparison",
                    {
                        "period1_start": "2011-10-01",
                        "period1_end": "2011-10-30",
                        "period2_start": "2011-11-01",
                        "period2_end": "2011-11-30",
                    },
                ),
                ai_message("Revenue is $8000.00 this period, down from $10000.00."),
            ],
            "decision": [
                ai_message(
                    f"{INTERPRETATION} Revenue is $8000.00 this period, down from $10000.00."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="09-ambiguous-question",
    title='"How\'s business?" must clarify or state its interpretation',
    description=(
        "A genuinely ambiguous question must have its interpretation reach the final answer."
    ),
    run=_run,
    expected_facts=[ExpectedFact("states its interpretation", "interpreting")],
    expected_agents=frozenset({"analytics"}),
)
