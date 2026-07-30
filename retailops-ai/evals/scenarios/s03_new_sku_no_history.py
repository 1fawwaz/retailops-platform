"""03-new-sku-no-history: a SKU with no sales history must surface its
data_quality flag, read as effectively zero confidence, and say so --
never a silent zero-demand forecast presented as a real prediction.
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
from evals.scenarios.fixtures import forecast_payload, login_response

QUESTION = "What's the demand forecast for new SKU 55555?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/forecast/demand":
        return httpx2.Response(
            200,
            json=[
                forecast_payload(
                    "55555",
                    predicted_daily_demand=0.0,
                    ci_lower=0.0,
                    ci_upper=0.0,
                    data_quality="no_history",
                    training_start=None,
                    training_end=None,
                )
            ],
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "forecast": [
                tool_call_message("forecast_demand", {"skus": ["55555"], "horizon_days": 14}),
                ai_message(
                    "SKU 55555 has no sales history to forecast from (data_quality: "
                    "no_history) -- no meaningful demand prediction can be made yet."
                ),
            ],
            "decision": [
                ai_message(
                    "SKU 55555 has no sales history to forecast from (data_quality: "
                    "no_history), so no reliable demand forecast is available yet -- "
                    "confidence should be treated as effectively zero until real sales "
                    "data accumulates."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="03-new-sku-no-history",
    title="New SKU with no sales history",
    description=(
        "A SKU with no history must surface data_quality=no_history, read as effectively "
        "zero confidence, and say so plainly rather than presenting a zero forecast as real."
    ),
    run=_run,
    expected_facts=[
        ExpectedFact("states there is no sales history", "no sales history"),
        ExpectedFact("names the data_quality flag", "no_history"),
    ],
    expected_agents=frozenset({"forecast"}),
)
