"""05-empty-inventory: zero stock across an entire category must be
reported as a valid, legitimate answer -- not an error to paper over,
not silently treated as "no data available".
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

QUESTION = "How much stock do we have in the Seasonal category?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/inventory/stock":
        return httpx2.Response(200, json=[])
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "inventory": [
                tool_call_message("get_stock", {"category": "Seasonal"}),
                ai_message(
                    "The Seasonal category currently has zero SKUs in stock -- an empty "
                    "result, not a data error."
                ),
            ],
            "decision": [
                ai_message(
                    "There is currently no stock in the Seasonal category -- zero units "
                    "across all SKUs."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="05-empty-inventory",
    title="Zero stock in a category is a valid answer",
    description="An empty result set must be reported plainly, not treated as an error.",
    run=_run,
    expected_facts=[ExpectedFact("states zero stock plainly", "zero")],
    expected_agents=frozenset({"inventory"}),
)
