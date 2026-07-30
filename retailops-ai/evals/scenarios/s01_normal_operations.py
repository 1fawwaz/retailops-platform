"""01-normal-operations: baseline correctness. A plain, unambiguous
analytics question with no edge case involved -- the floor every other
scenario is measured against.
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
from evals.scenarios.fixtures import login_response, revenue_period_payload

QUESTION = "What's our total revenue this month?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/analytics/revenue":
        return httpx2.Response(
            200, json=[revenue_period_payload("2011-11", revenue=8000.0, units=400)]
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "analytics": [
                tool_call_message("get_revenue", {}),
                ai_message("Revenue for the period is $8000.00."),
            ],
            "decision": [ai_message("Total revenue this month is $8000.00.")],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="01-normal-operations",
    title="Baseline correctness",
    description=(
        "A plain revenue question with no edge case -- the floor other scenarios are "
        "measured against."
    ),
    run=_run,
    expected_facts=[ExpectedFact("cites the real revenue figure", "8000")],
    expected_agents=frozenset({"analytics"}),
)
