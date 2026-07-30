"""02-seasonal-demand-spike: a large Nov/Dec revenue jump must be read as
expected holiday seasonality, not an unexpected trend break.
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

QUESTION = "Did SKU 85048's demand spike unexpectedly last month?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/analytics/revenue":
        return httpx2.Response(
            200,
            json=[
                revenue_period_payload("2011-10", revenue=3000.0, units=150),
                revenue_period_payload("2011-11", revenue=9000.0, units=450),
            ],
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "analytics": [
                tool_call_message("get_revenue", {"group_by": "month"}),
                ai_message(
                    "Revenue rose from $3000.00 in October to $9000.00 in November -- this "
                    "is expected seasonal demand ahead of the December holiday period, not "
                    "an unexpected trend break."
                ),
            ],
            "decision": [
                ai_message(
                    "The rise from $3000.00 to $9000.00 reflects normal seasonal demand "
                    "(holiday season), not an unexpected spike or a break in trend."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="02-seasonal-demand-spike",
    title="Seasonal demand is not a trend break",
    description=(
        "A large Nov/Dec revenue jump must be read as expected holiday seasonality, not "
        "flagged as an anomalous spike or a change in underlying trend."
    ),
    run=_run,
    expected_facts=[
        ExpectedFact("identifies the pattern as seasonal, not a break", "seasonal"),
    ],
    expected_agents=frozenset({"analytics"}),
)
