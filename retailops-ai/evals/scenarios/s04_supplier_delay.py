"""04-supplier-delay: an extended supplier lead time must change both
reorder timing (the order becomes overdue) and priority (escalates via
revenue_at_risk, since projected_stockout_days = max(0, lead_time_days -
days_of_cover) grows once lead time exceeds days of cover).

The only scenario that runs through
orchestration/workflows.py::run_inventory_health_workflow() rather than
the general chat path -- `priority` is a Decision Engine / Task 4.3
concept that only exists there (agents/base.py's Decision Engine has no
tools and is never given a quantified-recommendation job in the general
/agent/query path, a deliberate Task 4.2/4.3 scoping decision, not an
oversight -- see project memory).
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

import httpx2
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.decision import DecisionNarrative
from agents.report import HealthReport
from clients.stockpilot import StockPilotClient
from evals.scenarios.base import ExpectedFact, Scenario, ScenarioOutcome
from evals.scenarios.fixtures import (
    login_response,
    product_payload,
    stock_item_payload,
    supplier_payload,
    top_product_payload,
)
from llm.providers.gemini import StructuredResult
from orchestration.models.execution import Execution
from orchestration.workflows import run_inventory_health_workflow

SKU = "85048"
# Long enough that lead_time_days (60) exceeds days_of_cover (30/5=6),
# so projected_stockout_days > 0 and revenue_at_risk actually moves --
# a short lead time here would leave revenue_at_risk at 0 regardless of
# how "delayed" the label sounds, proving nothing about the formula.
LEAD_TIME_DAYS = 60


def handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return login_response()
    if path == "/inventory/low-stock":
        return httpx2.Response(
            200, json=[stock_item_payload(SKU, quantity_on_hand=30, reorder_point=40)]
        )
    if path == f"/products/{SKU}":
        return httpx2.Response(
            200,
            json=product_payload(
                SKU, quantity_on_hand=30, safety_stock=20, reorder_point=40, unit_cost=2.0
            ),
        )
    if path == "/suppliers/7":
        return httpx2.Response(200, json=supplier_payload(7, lead_time_days=LEAD_TIME_DAYS))
    if path == "/forecast/demand":
        return httpx2.Response(200, json=[{"sku": SKU, **_forecast_fields()}])
    if path == "/analytics/top-products":
        return httpx2.Response(200, json=[top_product_payload(SKU, revenue=1000.0, units=100)])
    if path == "/analytics/bottom-products":
        return httpx2.Response(200, json=[])
    if path == "/inventory/dead-stock":
        return httpx2.Response(200, json=[])
    if path == "/inventory/slow-movers":
        return httpx2.Response(200, json=[])
    if path == "/inventory/valuation":
        return httpx2.Response(
            200,
            json={
                "by_category": [],
                "total_quantity_on_hand": 1000,
                "total_inventory_value": 50000.0,
                "_provenance": {"total_inventory_value": "derived"},
                "_derivation_ref": {},
            },
        )
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _forecast_fields() -> dict[str, object]:
    return {
        "predicted_daily_demand": 5.0,
        "confidence_interval_lower": 4.0,
        "confidence_interval_upper": 6.0,
        "model_used": "moving_average",
        "training_window_start": "2011-01-01",
        "training_window_end": "2011-11-11",
        "data_quality": "ok",
        "_provenance": {"predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def _fake_generate_structured(
    *, model: str, messages: list[object], response_schema: type[BaseModel]
) -> StructuredResult[BaseModel]:
    parsed: BaseModel
    if response_schema is DecisionNarrative:
        parsed = DecisionNarrative(
            reason=(
                f"Supplier lead time is {LEAD_TIME_DAYS} days, far longer than the "
                "remaining days of cover, so a real stockout window is now priced in."
            ),
            risk_if_ignored="Stock runs out well before replenishment arrives.",
        )
    elif response_schema is HealthReport:
        parsed = HealthReport(
            title="Inventory Health", summary="One SKU is at elevated risk due to a long lead time."
        )
    else:
        raise AssertionError(f"unexpected schema: {response_schema}")
    return StructuredResult(
        parsed=parsed,
        usage_metadata={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10},
        provider="gemini",
        model=model,
    )


def _run(client: StockPilotClient, session_factory: Callable[[], Session]) -> ScenarioOutcome:
    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_inventory_health_workflow(client, session_factory, max_recommendations=1)

    session = session_factory()
    try:
        execution = session.get(Execution, result.execution_id)
        total_tokens = execution.total_tokens if execution and execution.total_tokens else 0
    finally:
        session.close()

    recommendation = result.recommendations[0].recommendation if result.recommendations else None
    return ScenarioOutcome(
        final_text=result.markdown,
        tool_agents=frozenset({"inventory"}) if result.recommendations else frozenset(),
        replan_rounds=0,
        citation_attempts=0,
        citation_passed=True,
        total_tokens=total_tokens,
        extra={
            "priority": recommendation.priority if recommendation else None,
            "reorder_now": True if recommendation else None,
        },
    )


SCENARIO = Scenario(
    handler=handler,
    id="04-supplier-delay",
    title="Extended lead time changes reorder timing and priority",
    description=(
        "A supplier lead time long enough to exceed days of cover must push "
        "projected_stockout_days above zero, escalating both reorder urgency and priority."
    ),
    run=_run,
    expected_facts=[ExpectedFact("names the SKU affected", SKU)],
    expected_agents=frozenset({"inventory"}),
)
