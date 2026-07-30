"""Stage 4 Task 4.4: API-layer tests for the workflow endpoints and
GET /report/{id} -- proves the FastAPI wiring (dependency overrides,
response shape, 404s, the markdown export format) through the real
route; orchestration/workflows.py's own business logic is already
covered directly in tests/test_workflows.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from unittest.mock import patch

import httpx2
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.decision import DecisionNarrative
from agents.report import HealthReport, PerformanceReport
from api import deps
from api.main import app
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult

client = TestClient(app)


def _login() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "t", "token_type": "bearer"})


def _stock_item(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "category": "Widgets",
        "quantity_on_hand": 10,
        "reorder_point": 40,
        "safety_stock": 10,
        "as_of_date": "2026-07-01",
        "is_low_stock": True,
        "_provenance": {"quantity_on_hand": "derived", "reorder_point": "derived"},
        "_derivation_ref": {},
    }


def _product(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
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


def _perf_row(sku: str) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "revenue": 1000.0,
        "units": 100,
        "margin": 0.2,
        "_provenance": {"revenue": "derived", "units": "observed", "margin": "derived"},
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


def _inventory_health_handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return _login()
    if path == "/inventory/low-stock":
        return httpx2.Response(200, json=[_stock_item("85048")])
    if path.startswith("/products/"):
        return httpx2.Response(200, json=_product(path.rsplit("/", 1)[-1]))
    if path == "/suppliers/7":
        return httpx2.Response(200, json=_supplier())
    if path == "/forecast/demand":
        skus = json.loads(request.content)["skus"]
        return httpx2.Response(200, json=[_forecast(sku) for sku in skus])
    if path == "/analytics/top-products":
        return httpx2.Response(200, json=[_perf_row("85048")])
    if path == "/analytics/bottom-products":
        return httpx2.Response(200, json=[])
    if path == "/inventory/dead-stock":
        return httpx2.Response(200, json=[])
    if path == "/inventory/slow-movers":
        return httpx2.Response(200, json=[])
    if path == "/inventory/valuation":
        return httpx2.Response(200, json=_valuation())
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _business_review_handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return _login()
    if path == "/analytics/period-comparison":
        return httpx2.Response(200, json=_period_comparison())
    if path in ("/analytics/top-products", "/analytics/bottom-products"):
        return httpx2.Response(200, json=[_perf_row("85048")])
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
        return httpx2.Response(200, json=[])
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _stockpilot_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
    )


def _fake_generate_structured(
    *, model: str, messages: list[object], response_schema: type[BaseModel]
) -> StructuredResult[BaseModel]:
    parsed: BaseModel
    if response_schema is DecisionNarrative:
        parsed = DecisionNarrative(reason="Reorder needed.", risk_if_ignored="Lost sales.")
    elif response_schema is HealthReport:
        parsed = HealthReport(title="draft", summary="Manageable.")
    elif response_schema is PerformanceReport:
        parsed = PerformanceReport(
            title="draft",
            period_start="x",
            period_end="y",
            largest_change_driver="Revenue fell.",
            summary="Profit declined.",
        )
    else:
        raise AssertionError(f"unexpected schema: {response_schema}")
    return StructuredResult(
        parsed=parsed, usage_metadata={"input_tokens": 2, "output_tokens": 2, "total_tokens": 4}
    )


def test_inventory_health_endpoint_returns_report_and_recommendations(
    db_session: Session,
) -> None:
    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(
        _inventory_health_handler
    )
    try:
        with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
            response = client.post(
                "/workflow/inventory-health/run", json={"max_recommendations": 1}
            )
        assert response.status_code == 200
        body = response.json()
        report_id = body["report_id"]

        get_response = client.get(f"/report/{report_id}")
    finally:
        app.dependency_overrides.clear()

    assert len(body["recommendations"]) == 1
    assert body["backtest"] is False
    assert body["report"]["title"]
    assert get_response.status_code == 200
    assert get_response.json()["report_type"] == "health"


def test_business_review_endpoint_supports_backtest_mode(db_session: Session) -> None:
    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(
        _business_review_handler
    )
    try:
        with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
            response = client.post(
                "/workflow/business-review/run",
                json={"as_of_date": "2011-11-30", "period_days": 30},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["backtest"] is True
    assert "Historical simulation as of 2011-11-30" in body["markdown"]
    assert body["report"]["revenue"] == 8000.0


def test_get_report_markdown_export(db_session: Session) -> None:
    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(
        _business_review_handler
    )
    try:
        with patch("agents.base.generate_structured", side_effect=_fake_generate_structured):
            posted = client.post("/workflow/business-review/run", json={})
        report_id = posted.json()["report_id"]

        markdown_response = client.get(f"/report/{report_id}", params={"format": "markdown"})
    finally:
        app.dependency_overrides.clear()

    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert "# Business Review" in markdown_response.text


def test_get_report_returns_404_for_an_unknown_id(db_session: Session) -> None:
    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    try:
        response = client.get(f"/report/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_run_inventory_health_is_rate_limited_per_user(db_session: Session) -> None:
    """Stage 6 backend hardening: same api/rate_limit.py wiring as
    POST /agent/query, applied here too -- the mechanism itself is
    already exhaustively tested in tests/test_rate_limit.py and
    tests/test_agent_api.py; this just confirms THIS route is actually
    wired to it.
    """
    from types import SimpleNamespace

    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(
        _inventory_health_handler
    )
    try:
        with (
            patch("agents.base.generate_structured", side_effect=_fake_generate_structured),
            patch(
                "api.rate_limit.get_settings",
                return_value=SimpleNamespace(rate_limit_requests=1, rate_limit_window_seconds=60),
            ),
        ):
            first = client.post("/workflow/inventory-health/run", json={"max_recommendations": 1})
            second = client.post("/workflow/inventory-health/run", json={"max_recommendations": 1})
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert "too many requests" in second.json()["detail"].lower()


def test_run_business_review_returns_504_when_the_request_times_out(
    db_session: Session,
) -> None:
    """Stage 6 backend hardening: same api/timeouts.py wiring as POST
    /agent/query, confirmed here for the workflow route too.
    """
    import time
    from types import SimpleNamespace

    def _slow_generate_structured(
        *, model: str, messages: list[object], response_schema: type[BaseModel]
    ) -> StructuredResult[BaseModel]:
        time.sleep(0.2)
        return _fake_generate_structured(
            model=model, messages=messages, response_schema=response_schema
        )

    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(
        _business_review_handler
    )
    try:
        with (
            patch("agents.base.generate_structured", side_effect=_slow_generate_structured),
            patch(
                "api.workflows.get_settings",
                return_value=SimpleNamespace(request_timeout_seconds=0.05),
            ),
        ):
            response = client.post("/workflow/business-review/run", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert "took too long" in response.json()["detail"].lower()
