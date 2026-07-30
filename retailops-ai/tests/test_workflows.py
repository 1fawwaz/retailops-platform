"""Stage 4 Task 4.4: tests for the two goal-driven workflow pipelines
(orchestration/workflows.py) -- exercised directly (not through HTTP),
with a StockPilotClient over a scripted MockTransport and mocked LLM
structured calls, mirroring the pattern in tests/test_decision.py.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from unittest.mock import patch

import httpx2
import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.decision import DecisionNarrative
from agents.report import HealthReport, PerformanceReport
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.models import Base
from orchestration.models.execution import Execution
from orchestration.models.recommendation import Recommendation as RecommendationRow
from orchestration.models.report import Report as ReportRow
from orchestration.workflows import (
    run_business_review_workflow,
    run_inventory_health_workflow,
)

Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture
def session_factory():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _client(handler: Handler) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
    )


def _login() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "t", "token_type": "bearer"})


def _stock_item(sku: str, quantity_on_hand: int, reorder_point: int) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "category": "Widgets",
        "quantity_on_hand": quantity_on_hand,
        "reorder_point": reorder_point,
        "safety_stock": 10,
        "as_of_date": "2026-07-01",
        "is_low_stock": True,
        "_provenance": {"quantity_on_hand": "derived", "reorder_point": "derived"},
        "_derivation_ref": {},
    }


def _product(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "category_id": 3,
        "supplier_id": 7,
        "unit_cost": 2.0,
        "reorder_point": 40,
        "safety_stock": 20,
        "created_at": "2026-01-01T00:00:00",
        "quantity_on_hand": 30,
        "movement_history": [],
        "_provenance": {"sku": "observed", "quantity_on_hand": "derived"},
        "_derivation_ref": {},
    }


def _supplier() -> dict[str, object]:
    return {
        "id": 7,
        "name": "Acme Wholesale",
        "lead_time_days": 5,
        "reliability_score": 0.9,
        "created_at": "2026-01-01T00:00:00",
        "skus": [],
        "_provenance": {"lead_time_days": "derived"},
        "_derivation_ref": {},
    }


def _forecast(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "predicted_daily_demand": 10.0,
        "confidence_interval_lower": 9.0,
        "confidence_interval_upper": 11.0,
        "model_used": "moving_average",
        "training_window_start": "2011-01-01",
        "training_window_end": "2011-12-31",
        "data_quality": "ok",
        "_provenance": {"predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def _perf_row(sku: str, revenue: float, units: int, period: str | None = None) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "revenue": revenue,
        "units": units,
        "margin": 0.2,
        "_provenance": {"revenue": "derived", "units": "observed", "margin": "derived"},
        "_derivation_ref": {},
    }


def _dead_stock_item(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "quantity_on_hand": 15,
        "last_movement_date": "2025-01-01T00:00:00",
        "days_since_movement": 200,
        "_provenance": {"quantity_on_hand": "derived"},
        "_derivation_ref": {},
    }


def _slow_mover_item(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "quantity_on_hand": 25,
        "units_sold": 3,
        "avg_daily_demand": 0.1,
        "_provenance": {"quantity_on_hand": "derived"},
        "_derivation_ref": {},
    }


def _valuation() -> dict[str, object]:
    return {
        "by_category": [],
        "total_quantity_on_hand": 1000,
        "total_inventory_value": 50000.0,
        "_provenance": {"total_inventory_value": "derived"},
        "_derivation_ref": {},
    }


def _period_comparison() -> dict[str, object]:
    return {
        "period1_start": "2011-10-01",
        "period1_end": "2011-10-30",
        "period1_revenue": 10000.0,
        "period1_units": 500,
        "period1_cost": 6000.0,
        "period1_gross_profit": 4000.0,
        "period1_margin": 0.4,
        "period2_start": "2011-11-01",
        "period2_end": "2011-11-30",
        "period2_revenue": 8000.0,
        "period2_units": 400,
        "period2_cost": 5000.0,
        "period2_gross_profit": 3000.0,
        "period2_margin": 0.375,
        "revenue_delta": -2000.0,
        "revenue_delta_pct": -20.0,
        "units_delta": -100,
        "units_delta_pct": -20.0,
        "gross_profit_delta": -1000.0,
        "gross_profit_delta_pct": -25.0,
        "_provenance": {"period2_revenue": "derived"},
        "_derivation_ref": {},
    }


def _inventory_health_handler(*, low_stock_skus: list[str]) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/auth/login":
            return _login()
        if path == "/inventory/low-stock":
            return httpx2.Response(200, json=[_stock_item(sku, 10, 40) for sku in low_stock_skus])
        if path.startswith("/products/"):
            return httpx2.Response(200, json=_product(path.rsplit("/", 1)[-1]))
        if path == "/suppliers/7":
            return httpx2.Response(200, json=_supplier())
        if path == "/forecast/demand":
            body = json.loads(request.content)
            skus = body["skus"]
            return httpx2.Response(200, json=[_forecast(sku) for sku in skus])
        if path == "/analytics/top-products":
            return httpx2.Response(
                200, json=[_perf_row(sku, 1000.0, 100) for sku in low_stock_skus]
            )
        if path == "/analytics/bottom-products":
            return httpx2.Response(200, json=[])
        if path == "/inventory/dead-stock":
            return httpx2.Response(200, json=[_dead_stock_item("99999")])
        if path == "/inventory/slow-movers":
            return httpx2.Response(200, json=[_slow_mover_item("88888")])
        if path == "/inventory/valuation":
            return httpx2.Response(200, json=_valuation())
        raise AssertionError(f"unexpected request: {request.method} {path}")

    return handler


def _fake_generate_structured(
    *, model: str, messages: list[object], response_schema: type[BaseModel]
) -> StructuredResult[BaseModel]:
    parsed: BaseModel
    if response_schema is DecisionNarrative:
        parsed = DecisionNarrative(reason="Reorder needed.", risk_if_ignored="Lost sales.")
    elif response_schema is HealthReport:
        parsed = HealthReport(title="draft", summary="Inventory looks manageable overall.")
    elif response_schema is PerformanceReport:
        parsed = PerformanceReport(
            title="draft",
            period_start="x",
            period_end="y",
            largest_change_driver="Revenue fell across the board.",
            summary="Profit declined this period.",
        )
    else:
        raise AssertionError(f"unexpected schema: {response_schema}")
    return StructuredResult(
        parsed=parsed, usage_metadata={"input_tokens": 2, "output_tokens": 2, "total_tokens": 4}
    )


def test_inventory_health_workflow_persists_report_and_ranked_recommendations(
    session_factory: sessionmaker[Session],
) -> None:
    client = _client(_inventory_health_handler(low_stock_skus=["85048", "22841"]))

    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_inventory_health_workflow(client, session_factory, max_recommendations=2)

    assert len(result.recommendations) == 2
    assert result.skipped_skus == []
    assert result.backtest is False
    assert "Historical simulation" not in result.markdown

    # Ranked by revenue_at_risk, descending.
    risks = [r.recommendation.revenue_at_risk or -1.0 for r in result.recommendations]
    assert risks == sorted(risks, reverse=True)

    session = session_factory()
    try:
        report_row = session.get(ReportRow, result.report_id)
        assert report_row is not None
        assert report_row.report_type == "health"
        assert report_row.markdown == result.markdown

        recommendation_rows = (
            session.query(RecommendationRow)
            .filter(RecommendationRow.report_id == result.report_id)
            .all()
        )
        assert len(recommendation_rows) == 2
        assert all(row.status == "pending" for row in recommendation_rows)

        execution = session.get(Execution, result.execution_id)
        assert execution is not None
        assert execution.status == "completed"
    finally:
        session.close()


def test_inventory_health_workflow_stamps_backtest_label_without_changing_data(
    session_factory: sessionmaker[Session],
) -> None:
    """docs/stockpilot-gaps.md#3: inventory-health can only LABEL a
    backtest -- StockPilot has no historical stock/forecast snapshot, so
    the same live data is queried regardless of as_of_date.
    """
    client = _client(_inventory_health_handler(low_stock_skus=["85048"]))

    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_inventory_health_workflow(
            client, session_factory, as_of_date=date(2011, 11, 12), max_recommendations=1
        )

    assert result.backtest is True
    assert "Historical simulation as of 2011-11-12" in result.markdown


def test_inventory_health_workflow_skips_skus_with_a_data_gap(
    session_factory: sessionmaker[Session],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/products/85048":
            product = _product("85048")
            product["quantity_on_hand"] = None
            return httpx2.Response(200, json=product)
        return _inventory_health_handler(low_stock_skus=["85048"])(request)

    client = _client(handler)

    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_inventory_health_workflow(client, session_factory, max_recommendations=1)

    assert result.recommendations == []
    assert len(result.skipped_skus) == 1
    assert "85048" in result.skipped_skus[0]


def _business_review_handler() -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/auth/login":
            return _login()
        if path == "/analytics/period-comparison":
            return httpx2.Response(200, json=_period_comparison())
        if path == "/analytics/top-products":
            return httpx2.Response(200, json=[_perf_row("85048", 1000.0, 100)])
        if path == "/analytics/bottom-products":
            return httpx2.Response(200, json=[_perf_row("22841", 10.0, 2)])
        if path == "/analytics/revenue":
            return httpx2.Response(
                200,
                json=[
                    {
                        "period": "Widgets",
                        "revenue": 4000.0,
                        "units": 200,
                        "_provenance": {"revenue": "derived"},
                        "_derivation_ref": {},
                    }
                ],
            )
        if path == "/inventory/valuation":
            return httpx2.Response(200, json=_valuation())
        if path == "/inventory/dead-stock":
            return httpx2.Response(200, json=[_dead_stock_item("99999")])
        if path == "/products/99999":
            return httpx2.Response(200, json=_product("99999"))
        raise AssertionError(f"unexpected request: {request.method} {path}")

    return handler


def test_business_review_workflow_does_a_real_backtest_and_persists_a_report(
    session_factory: sessionmaker[Session],
) -> None:
    client = _client(_business_review_handler())

    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_business_review_workflow(
            client, session_factory, as_of_date=date(2011, 11, 30), period_days=30
        )

    assert result.backtest is True
    assert "Historical simulation as of 2011-11-30" in result.markdown
    assert result.report.revenue == 8000.0
    assert result.report.revenue_delta_pct == -20.0
    assert result.report.margin_delta_pct == pytest.approx(0.375 - 0.4)
    assert result.report.total_inventory_value == 50000.0
    # dead_stock_capital = 15 * unit_cost(2.0) = 30.0
    assert result.report.dead_stock_capital == 30.0
    assert result.report.period_start == "2011-11-01"
    assert result.report.period_end == "2011-11-30"

    session = session_factory()
    try:
        report_row = session.get(ReportRow, result.report_id)
        assert report_row is not None
        assert report_row.report_type == "performance"
        assert report_row.as_of_date == date(2011, 11, 30)
    finally:
        session.close()


def test_business_review_workflow_live_run_is_not_stamped_as_backtest(
    session_factory: sessionmaker[Session],
) -> None:
    client = _client(_business_review_handler())

    with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
        result = run_business_review_workflow(client, session_factory)

    assert result.backtest is False
    assert "Historical simulation" not in result.markdown
