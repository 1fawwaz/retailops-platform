"""Stage 4 Task 4.1: tool-layer tests for tools/derived_tools.py -- proves
each derived tool fetches real StockPilot data over the wire, computes in
Python, and persists exactly one tool_calls row with the right
provenance, the same standard tools/stockpilot_tools.py's own tests hold
the 18 real endpoints to (tests/test_stockpilot_tools.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from clients.stockpilot import StockPilotClient
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from tools.derived_tools import build_derived_tools

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


def _tools_by_name(tools: list[StructuredTool]) -> dict[str, StructuredTool]:
    return {t.name: t for t in tools}


def _stock_item_payload(
    sku: str, quantity_on_hand: int, reorder_point: int | None
) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "category": "Widgets",
        "quantity_on_hand": quantity_on_hand,
        "reorder_point": reorder_point,
        "safety_stock": 10,
        "as_of_date": "2026-07-01",
        "is_low_stock": True,
        "_provenance": {"quantity_on_hand": "derived", "reorder_point": "derived"},
        "_derivation_ref": {},
    }


def _product_detail_payload(
    sku: str, *, quantity_on_hand: int | None, safety_stock: int | None, supplier_id: int | None
) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Widget",
        "category_id": 3,
        "supplier_id": supplier_id,
        "unit_cost": 2.15,
        "reorder_point": 40,
        "safety_stock": safety_stock,
        "created_at": "2026-01-01T00:00:00",
        "quantity_on_hand": quantity_on_hand,
        "movement_history": [],
        "_provenance": {
            "sku": "observed",
            "quantity_on_hand": "derived",
            "safety_stock": "derived",
        },
        "_derivation_ref": {},
    }


def _forecast_payload(
    sku: str, predicted_daily_demand: float, data_quality: str = "ok"
) -> dict[str, object]:
    return {
        "sku": sku,
        "predicted_daily_demand": predicted_daily_demand,
        "confidence_interval_lower": predicted_daily_demand * 0.8,
        "confidence_interval_upper": predicted_daily_demand * 1.2,
        "model_used": "moving_average",
        "training_window_start": "2011-01-01",
        "training_window_end": "2011-11-11",
        "data_quality": data_quality,
        "_provenance": {"predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def _supplier_detail_payload(supplier_id: int, lead_time_days: int) -> dict[str, object]:
    return {
        "id": supplier_id,
        "name": "Acme Wholesale",
        "lead_time_days": lead_time_days,
        "reliability_score": 0.9,
        "created_at": "2026-01-01T00:00:00",
        "skus": ["85048"],
        "_provenance": {"lead_time_days": "derived"},
        "_derivation_ref": {},
    }


def test_build_derived_tools_returns_three_uniquely_named_tools(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _login_response()

    client = _client(handler)
    execution_id = _new_execution(db_session)

    tools = build_derived_tools(client, lambda: db_session, execution_id)

    names = {t.name for t in tools}
    assert names == {"rank_stockout_risk", "days_of_cover", "reorder_timing"}


def test_rank_stockout_risk_tool_fetches_and_ranks_then_persists(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        assert request.url.path == "/inventory/low-stock"
        return httpx2.Response(
            200,
            json=[
                _stock_item_payload("A", quantity_on_hand=80, reorder_point=40),
                _stock_item_payload("B", quantity_on_hand=10, reorder_point=40),
            ],
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    result = tools["rank_stockout_risk"].invoke({})

    assert [item.sku for item in result.items] == ["B", "A"]

    row = db_session.query(ToolCall).one()
    assert row.execution_id == execution_id
    assert row.tool_name == "rank_stockout_risk"
    assert row.status == "success"
    assert row.provenance_map is not None
    assert row.provenance_map["stock_ratio"] == "derived"
    assert isinstance(row.raw_response, dict)
    items = row.raw_response["items"]
    assert isinstance(items, list)
    assert items[0]["sku"] == "B"


def test_days_of_cover_tool_combines_product_and_forecast_then_persists(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        if request.url.path == "/products/85048":
            return httpx2.Response(
                200,
                json=_product_detail_payload(
                    "85048", quantity_on_hand=100, safety_stock=20, supplier_id=7
                ),
            )
        assert request.url.path == "/forecast/demand"
        return httpx2.Response(200, json=[_forecast_payload("85048", 10.0)])

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    result = tools["days_of_cover"].invoke({"sku": "85048", "horizon_days": 14})

    assert result.days_of_cover == 10.0

    row = db_session.query(ToolCall).one()
    assert row.tool_name == "days_of_cover"
    assert row.status == "success"
    assert row.provenance_map is not None
    assert row.provenance_map["days_of_cover"] == "predicted"
    assert isinstance(row.raw_response, dict)
    assert row.raw_response["days_of_cover"] == 10.0


def test_days_of_cover_tool_raises_a_clear_error_when_stock_is_unrecorded(
    db_session: Session,
) -> None:
    """Never fabricate: a SKU with no recorded quantity_on_hand must fail
    loudly (surfaced to the agent as a tool error, per Task 3.6's
    tool-error handling), not silently compute against a guessed zero.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(
            200,
            json=_product_detail_payload(
                "85048", quantity_on_hand=None, safety_stock=20, supplier_id=7
            ),
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    with pytest.raises(ValueError, match="no recorded quantity_on_hand"):
        tools["days_of_cover"].invoke({"sku": "85048", "horizon_days": 14})

    row = db_session.query(ToolCall).one()
    assert row.status == "error"


def test_reorder_timing_tool_combines_product_supplier_and_forecast(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        if request.url.path == "/products/85048":
            return httpx2.Response(
                200,
                json=_product_detail_payload(
                    "85048", quantity_on_hand=100, safety_stock=20, supplier_id=7
                ),
            )
        if request.url.path == "/suppliers/7":
            return httpx2.Response(200, json=_supplier_detail_payload(7, lead_time_days=5))
        assert request.url.path == "/forecast/demand"
        return httpx2.Response(200, json=[_forecast_payload("85048", 10.0)])

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    result = tools["reorder_timing"].invoke({"sku": "85048", "horizon_days": 14})

    assert result.days_until_safety_stock == 8.0
    assert result.reorder_by_days == 3.0
    assert result.reorder_now is False

    row = db_session.query(ToolCall).one()
    assert row.tool_name == "reorder_timing"
    assert row.provenance_map is not None
    assert row.provenance_map["reorder_by_days"] == "predicted"


def test_reorder_timing_tool_raises_a_clear_error_when_no_supplier_is_assigned(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(
            200,
            json=_product_detail_payload(
                "85048", quantity_on_hand=100, safety_stock=20, supplier_id=None
            ),
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    with pytest.raises(ValueError, match="no assigned supplier"):
        tools["reorder_timing"].invoke({"sku": "85048", "horizon_days": 14})


def test_reorder_timing_tool_raises_a_clear_error_when_stock_is_unrecorded(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(
            200,
            json=_product_detail_payload(
                "85048", quantity_on_hand=None, safety_stock=20, supplier_id=7
            ),
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    with pytest.raises(ValueError, match="no recorded quantity_on_hand"):
        tools["reorder_timing"].invoke({"sku": "85048", "horizon_days": 14})


def test_reorder_timing_tool_raises_a_clear_error_when_safety_stock_is_unrecorded(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(
            200,
            json=_product_detail_payload(
                "85048", quantity_on_hand=100, safety_stock=None, supplier_id=7
            ),
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = _tools_by_name(build_derived_tools(client, lambda: db_session, execution_id))

    with pytest.raises(ValueError, match="no recorded safety_stock"):
        tools["reorder_timing"].invoke({"sku": "85048", "horizon_days": 14})
