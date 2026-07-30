"""Stage 4 Task 4.3: tests for the Decision Engine pipeline
(agents/decision.py) -- data gathering + Python quantification
(compute_recommendation_numbers), the narrative-only LLM call
(build_recommendation), persistence, and the spec's own REQUIRED TEST:
run the Decision Engine twice and assert every numeric field is
identical, proving the LLM never computes them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from unittest.mock import patch

import httpx2
import pytest
from sqlalchemy.orm import Session

from agents.base import Agent
from agents.decision import (
    DecisionNarrative,
    Recommendation,
    RecommendationDataGap,
    build_recommendation,
    compute_recommendation_numbers,
    persist_recommendation,
)
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.models.execution import Execution
from orchestration.models.recommendation import Recommendation as RecommendationRow
from orchestration.models.tool_call import ToolCall
from prompts.loader import load_prompt
from services.confidence import compute_confidence

Handler = Callable[[httpx2.Request], httpx2.Response]


def _login_response() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "test-token", "token_type": "bearer"})


def _client(handler: Handler) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
    )


def _new_execution(db_session: Session) -> uuid.UUID:
    execution = Execution(query="test query", status="running")
    db_session.add(execution)
    db_session.commit()
    return execution.id


def _decision_agent() -> Agent:
    return Agent(name="decision", role="decision", prompt=load_prompt("decision"))


def _product_payload(
    sku: str = "85048",
    *,
    quantity_on_hand: int | None = 30,
    safety_stock: int | None = 20,
    supplier_id: int | None = 7,
    unit_cost: float | None = 2.0,
    reorder_point: int | None = 40,
) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "category_id": 3,
        "supplier_id": supplier_id,
        "unit_cost": unit_cost,
        "reorder_point": reorder_point,
        "safety_stock": safety_stock,
        "created_at": "2026-01-01T00:00:00",
        "quantity_on_hand": quantity_on_hand,
        "movement_history": [],
        "_provenance": {"sku": "observed", "quantity_on_hand": "derived"},
        "_derivation_ref": {},
    }


def _supplier_payload(
    supplier_id: int = 7, *, lead_time_days: int = 5, name: str = "Acme Wholesale"
) -> dict[str, object]:
    return {
        "id": supplier_id,
        "name": name,
        "lead_time_days": lead_time_days,
        "reliability_score": 0.9,
        "created_at": "2026-01-01T00:00:00",
        "skus": [],
        "_provenance": {"lead_time_days": "derived"},
        "_derivation_ref": {},
    }


def _forecast_payload(
    sku: str = "85048",
    *,
    predicted_daily_demand: float = 10.0,
    ci_lower: float = 9.0,
    ci_upper: float = 11.0,
    data_quality: str = "ok",
    training_start: str | None = "2011-01-01",
    training_end: str | None = "2011-12-31",
) -> dict[str, object]:
    return {
        "sku": sku,
        "predicted_daily_demand": predicted_daily_demand,
        "confidence_interval_lower": ci_lower,
        "confidence_interval_upper": ci_upper,
        "model_used": "moving_average",
        "training_window_start": training_start,
        "training_window_end": training_end,
        "data_quality": data_quality,
        "_provenance": {"predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def _perf_row_payload(sku: str, revenue: float, units: int) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "revenue": revenue,
        "units": units,
        "margin": 0.2,
        "_provenance": {"revenue": "derived", "units": "observed", "margin": "derived"},
        "_derivation_ref": {},
    }


def _standard_handler(
    *,
    top_products: list[dict[str, object]] | None = None,
    bottom_products: list[dict[str, object]] | None = None,
    product_overrides: dict[str, object] | None = None,
) -> Handler:
    top_products = (
        top_products if top_products is not None else [_perf_row_payload("85048", 1000.0, 100)]
    )
    bottom_products = bottom_products if bottom_products is not None else []
    product_overrides = product_overrides or {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/auth/login":
            return _login_response()
        if path == "/products/85048":
            # mypy can't verify a dict[str, object] splat against
            # _product_payload's individually-typed kwargs; this is a
            # small ad-hoc test override dict, not worth a TypedDict.
            return httpx2.Response(
                200,
                json=_product_payload(**product_overrides),  # type: ignore[arg-type]
            )
        if path == "/suppliers/7":
            return httpx2.Response(200, json=_supplier_payload())
        if path == "/forecast/demand":
            return httpx2.Response(200, json=[_forecast_payload()])
        if path == "/analytics/top-products":
            return httpx2.Response(200, json=top_products)
        if path == "/analytics/bottom-products":
            return httpx2.Response(200, json=bottom_products)
        raise AssertionError(f"unexpected request: {path}")

    return handler


# -- compute_recommendation_numbers() --------------------------------------


def test_compute_recommendation_numbers_matches_hand_calculated_values(
    db_session: Session,
) -> None:
    client = _client(_standard_handler())
    execution_id = _new_execution(db_session)

    numbers = compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")

    # days_of_cover = 30 / 10 = 3.0
    assert numbers.days_of_cover == 3.0
    # projected_stockout_days = max(0, lead_time(5) - days_of_cover(3)) = 2.0
    # unit_price = 1000/100 = 10.0 -> revenue_at_risk = 10 * 10 * 2 = 200.0
    assert numbers.unit_price == 10.0
    assert numbers.revenue_at_risk == 200.0
    # recommended_order_qty = 10*5 + 20 - 30 = 40 -> inventory_cost = 40*2.0
    assert numbers.recommended_order_qty == 40
    assert numbers.inventory_cost == 80.0
    assert numbers.priority == "critical"  # days_to_stockout(3) <= critical threshold(3)
    assert numbers.action == "Reorder 40 units of 85048 from Acme Wholesale"
    expected_confidence = compute_confidence(
        confidence_interval_lower=9.0,
        confidence_interval_upper=11.0,
        predicted_daily_demand=10.0,
        data_quality="ok",
        history_days=364,
    )
    assert numbers.confidence == expected_confidence

    # Evidence must be real, persisted tool_call_ids for this execution.
    assert numbers.evidence
    persisted_ids = {
        str(row.tool_call_id)
        for row in db_session.query(ToolCall).filter(ToolCall.execution_id == execution_id).all()
    }
    assert set(numbers.evidence) <= persisted_ids


def test_compute_recommendation_numbers_raises_a_gap_for_missing_stock(
    db_session: Session,
) -> None:
    client = _client(_standard_handler(product_overrides={"quantity_on_hand": None}))
    execution_id = _new_execution(db_session)

    with pytest.raises(RecommendationDataGap, match="quantity_on_hand"):
        compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")


def test_compute_recommendation_numbers_raises_a_gap_for_no_supplier(
    db_session: Session,
) -> None:
    client = _client(_standard_handler(product_overrides={"supplier_id": None}))
    execution_id = _new_execution(db_session)

    with pytest.raises(RecommendationDataGap, match="supplier"):
        compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")


def test_compute_recommendation_numbers_raises_a_gap_for_missing_safety_stock(
    db_session: Session,
) -> None:
    client = _client(_standard_handler(product_overrides={"safety_stock": None}))
    execution_id = _new_execution(db_session)

    with pytest.raises(RecommendationDataGap, match="safety_stock"):
        compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")


def test_compute_recommendation_numbers_raises_a_gap_for_missing_unit_cost(
    db_session: Session,
) -> None:
    client = _client(_standard_handler(product_overrides={"unit_cost": None}))
    execution_id = _new_execution(db_session)

    with pytest.raises(RecommendationDataGap, match="unit_cost"):
        compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")


def test_compute_recommendation_numbers_leaves_revenue_at_risk_unset_when_price_not_found(
    db_session: Session,
) -> None:
    """docs/stockpilot-gaps.md#2: a SKU absent from both top/bottom
    rankings has no computable revenue_at_risk -- must stay None, never
    a guessed or defaulted figure. Priority still falls back to
    days_to_stockout alone.
    """
    client = _client(_standard_handler(top_products=[], bottom_products=[]))
    execution_id = _new_execution(db_session)

    numbers = compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")

    assert numbers.unit_price is None
    assert numbers.revenue_at_risk is None
    assert numbers.priority == "critical"  # still driven by days_to_stockout(3) <= 3


def test_compute_recommendation_numbers_handles_zero_predicted_demand(
    db_session: Session,
) -> None:
    """A no_history SKU forecasts zero demand by design -- days_of_cover,
    revenue_at_risk must be handled without a division error, and
    priority must land as "low" (no meaningful stockout risk).
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/forecast/demand":
            return httpx2.Response(
                200,
                json=[
                    _forecast_payload(
                        predicted_daily_demand=0.0,
                        ci_lower=0.0,
                        ci_upper=0.0,
                        data_quality="no_history",
                        training_start=None,
                        training_end=None,
                    )
                ],
            )
        return _standard_handler()(request)

    client = _client(handler)
    execution_id = _new_execution(db_session)

    numbers = compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")

    assert numbers.days_of_cover is None
    assert numbers.revenue_at_risk == 0.0
    assert numbers.priority == "low"


# -- build_recommendation() -------------------------------------------


def _narrative_result(reason: str, risk: str) -> StructuredResult[DecisionNarrative]:
    return StructuredResult(
        parsed=DecisionNarrative(reason=reason, risk_if_ignored=risk),
        usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
    )


def test_build_recommendation_assembles_numbers_and_llm_narrative(
    db_session: Session,
) -> None:
    client = _client(_standard_handler())
    execution_id = _new_execution(db_session)
    agent = _decision_agent()
    numbers = compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")

    with patch(
        "agents.base.generate_structured",
        return_value=_narrative_result("Stock will run out soon.", "Lost sales for two days."),
    ):
        recommendation = build_recommendation(
            agent, numbers, session_factory=lambda: db_session, execution_id=execution_id
        )

    assert recommendation.reason == "Stock will run out soon."
    assert recommendation.risk_if_ignored == "Lost sales for two days."
    assert recommendation.revenue_at_risk == numbers.revenue_at_risk
    assert recommendation.inventory_cost == numbers.inventory_cost
    assert recommendation.confidence == numbers.confidence
    assert recommendation.evidence == numbers.evidence


def test_required_running_decision_engine_twice_yields_identical_numeric_fields(
    db_session: Session,
) -> None:
    """The spec's own REQUIRED TEST, verbatim: "run the Decision Engine
    twice at temperature > 0 and assert every numeric field is
    identical. If any value moves, an LLM is computing it." Simulated
    here by giving the two runs genuinely DIFFERENT mocked LLM narrative
    text (standing in for temperature>0 variability) while keeping the
    underlying StockPilot data fixed -- every numeric/priority/evidence
    field must still match exactly; only the free-text fields may differ.
    """
    client = _client(_standard_handler())
    execution_id = _new_execution(db_session)
    agent = _decision_agent()
    numbers = compute_recommendation_numbers(client, lambda: db_session, execution_id, "85048")

    with patch(
        "agents.base.generate_structured",
        return_value=_narrative_result("First phrasing of the reason.", "First phrasing of risk."),
    ):
        first = build_recommendation(
            agent, numbers, session_factory=lambda: db_session, execution_id=execution_id
        )

    with patch(
        "agents.base.generate_structured",
        return_value=_narrative_result(
            "A completely different way of explaining the same thing.",
            "An entirely different sentence about the same risk.",
        ),
    ):
        second = build_recommendation(
            agent, numbers, session_factory=lambda: db_session, execution_id=execution_id
        )

    assert first.reason != second.reason
    assert first.risk_if_ignored != second.risk_if_ignored

    assert first.sku == second.sku
    assert first.action == second.action
    assert first.priority == second.priority
    assert first.revenue_at_risk == second.revenue_at_risk
    assert first.inventory_cost == second.inventory_cost
    assert first.confidence == second.confidence
    assert first.evidence == second.evidence


# -- persistence + API -------------------------------------------------


def test_persist_recommendation_writes_a_pending_row(db_session: Session) -> None:
    execution_id = _new_execution(db_session)
    recommendation = Recommendation(
        sku="85048",
        action="Reorder 40 units of 85048 from Acme Wholesale",
        priority="critical",
        reason="r",
        revenue_at_risk=200.0,
        inventory_cost=80.0,
        confidence=0.5,
        risk_if_ignored="risk",
        evidence=["11111111-1111-1111-1111-111111111111"],
    )

    recommendation_id = persist_recommendation(lambda: db_session, execution_id, recommendation)

    row = db_session.get(RecommendationRow, recommendation_id)
    assert row is not None
    assert row.execution_id == execution_id
    assert row.sku == "85048"
    assert row.status == "pending"
    assert row.revenue_at_risk == 200.0
    assert row.decided_at is None


def test_persist_recommendation_stores_zero_for_an_unset_revenue_at_risk(
    db_session: Session,
) -> None:
    execution_id = _new_execution(db_session)
    recommendation = Recommendation(
        sku="85048",
        action="Reorder 40 units of 85048",
        priority="low",
        reason="r",
        revenue_at_risk=None,
        inventory_cost=80.0,
        confidence=0.1,
        risk_if_ignored="risk",
        evidence=[],
    )

    recommendation_id = persist_recommendation(lambda: db_session, execution_id, recommendation)

    row = db_session.get(RecommendationRow, recommendation_id)
    assert row is not None
    assert row.revenue_at_risk == 0.0
