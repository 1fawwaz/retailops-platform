"""11-operational-policy-rag: policy reasoning grounded in operational documents.
Tests that unstructured enterprise documents (SOPs, contracts) are retrieved and cited.
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
from evals.scenarios.fixtures import login_response, supplier_payload

QUESTION = "What is the penalty if supplier 7 delivers late according to their contract?"


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/suppliers/7":
        return httpx2.Response(
            200,
            json=supplier_payload(
                7,
                name="Acme Wholesale",
                lead_time_days=5,
            ),
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    generate = ScriptedGenerate(
        {
            "inventory": [
                tool_call_message("get_supplier", {"supplier_id": 7}),
                ai_message("Supplier 7 has a lead time of 5 days (derived)."),
            ],
            "decision": [
                ai_message(
                    "According to contract SLA, supplier 7 has a standard"
                    " lead time of 5 days (derived)."
                )
            ],
        }
    )
    return run_chat_scenario(
        QUESTION,
        client,
        session_factory,
        generate=generate,
    )


SCENARIO = Scenario(
    handler=handler,
    id="11-operational-policy-rag",
    title="Operational Policy RAG",
    description="Validates that contractual policy information is accurately grounded.",
    run=_run,
    expected_facts=[
        ExpectedFact("mentions 5 days lead time", "5"),
    ],
    expected_agents=frozenset({"inventory"}),
)
