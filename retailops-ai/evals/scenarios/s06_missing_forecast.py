"""06-missing-forecast: the forecast endpoint itself returns no rows for
the requested SKU (distinct from 03-new-sku-no-history, where it DOES
return a row with data_quality="no_history") -- a genuine empty response
must be named plainly, never silently treated as zero demand.
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
from evals.scenarios.fixtures import login_response

QUESTION = "What's the demand forecast for SKU 77777?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/forecast/demand":
        return httpx2.Response(200, json=[])
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "forecast": [
                tool_call_message("forecast_demand", {"skus": ["77777"], "horizon_days": 14}),
                ai_message(
                    "No forecast data was returned for the requested SKU -- the forecast "
                    "tool responded with no rows at all, not even a no_history entry."
                ),
            ],
            "decision": [
                ai_message(
                    "No forecast is currently available for the requested SKU -- the "
                    "forecast tool returned no data for it at all."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="06-missing-forecast",
    title="Forecast endpoint returns nothing for the requested SKU",
    description="An empty forecast response must be named plainly, never read as zero demand.",
    run=_run,
    expected_facts=[ExpectedFact("states no forecast data was returned", "no forecast")],
    expected_agents=frozenset({"forecast"}),
)
