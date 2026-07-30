"""10-unanswerable-question: a question about data StockPilot genuinely
has none of (customer satisfaction, marketing spend, geography) must be
refused honestly, never fabricated -- no agent has a tool for it, so
none makes a real tool call, and the final answer states the gap.
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
)
from evals.scenarios.fixtures import login_response

QUESTION = "What is our customer satisfaction score?"


def handler(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/auth/login":
        return login_response()
    raise AssertionError(f"unexpected request: {request.method} {request.url.path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "decision": [
                ai_message(
                    "StockPilot has no customer satisfaction data -- this question can't be "
                    "answered from what's available. I can report on inventory, forecasts, "
                    "or revenue/profit analytics instead."
                )
            ],
        },
        default=ai_message("No tool is available for this question."),
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="10-unanswerable-question",
    title="Refuses cleanly when the data doesn't exist",
    description="A question about data StockPilot has none of must be refused, never guessed at.",
    run=_run,
    expected_facts=[ExpectedFact("states no such data exists", "no customer satisfaction data")],
    expected_agents=frozenset(),
    expect_refusal=True,
)
