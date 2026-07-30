"""07-api-unavailable: StockPilot itself is unreachable -- every request,
including auth, fails at the transport level. The graph must degrade
gracefully (Task 3.6): the answer names the outage explicitly, never a
crash and never a fabricated stock figure standing in for real data.
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

QUESTION = "What's low on stock right now?"


def handler(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection refused", request=request)


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "inventory": [
                tool_call_message("get_low_stock", {}),
                ai_message(
                    "Stock levels are unavailable right now because StockPilot could not "
                    "be reached."
                ),
            ],
            "decision": [
                ai_message(
                    "I can't report on current stock levels -- StockPilot is unreachable "
                    "right now. Please try again shortly."
                )
            ],
        }
    )
    return run_chat_scenario(QUESTION, client, session_factory, generate=generate)


SCENARIO = Scenario(
    handler=handler,
    id="07-api-unavailable",
    title="StockPilot unreachable degrades gracefully",
    description=(
        "Every StockPilot request fails at the transport level -- the answer must name "
        "the outage explicitly, never crash and never invent a stand-in figure."
    ),
    run=_run,
    expected_facts=[ExpectedFact("names the outage", "unreachable")],
    # A failed tool call still persists its own ToolCall row (status
    # "error") before Agent._run_tool_call absorbs it into an error
    # message -- "inventory" tried, which is the correct behaviour here,
    # not a routing miss.
    expected_agents=frozenset({"inventory"}),
)
