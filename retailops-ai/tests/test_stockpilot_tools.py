import uuid
from collections.abc import Callable

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from clients.stockpilot import StockPilotClient
from clients.stockpilot_models import ProductRead
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from tools.stockpilot_tools import build_stockpilot_tools

Handler = Callable[[httpx2.Request], httpx2.Response]


def _login_response() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "test-token", "token_type": "bearer"})


def _product_read_payload(sku: str = "85048") -> dict[str, object]:
    return {
        "sku": sku,
        "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
        "category_id": 3,
        "supplier_id": 7,
        "unit_cost": 2.15,
        "reorder_point": 120,
        "safety_stock": 40,
        "created_at": "2026-01-01T00:00:00",
        "_provenance": {
            "sku": "observed",
            "description": "observed",
            "unit_cost": "derived",
            "reorder_point": "derived",
            "safety_stock": "derived",
        },
        "_derivation_ref": {},
    }


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


def test_build_stockpilot_tools_returns_eighteen_uniquely_named_tools(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _login_response()

    client = _client(handler)
    execution_id = _new_execution(db_session)

    tools = build_stockpilot_tools(client, lambda: db_session, execution_id)

    names = [t.name for t in tools]
    assert len(names) == 18
    assert len(set(names)) == 18
    for t in tools:
        assert isinstance(t, StructuredTool)
        assert t.description
        assert t.args_schema is not None


def test_write_endpoints_are_not_exposed_as_tools(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _login_response()

    client = _client(handler)
    execution_id = _new_execution(db_session)
    names = {t.name for t in build_stockpilot_tools(client, lambda: db_session, execution_id)}

    for excluded in (
        "create_product",
        "update_product",
        "delete_product",
        "create_supplier",
        "update_supplier",
        "delete_supplier",
        "register_user",
        "health",
    ):
        assert excluded not in names


def test_tool_invocation_is_callable_in_isolation_and_persists_a_tool_call_row(
    db_session: Session,
) -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(200, json=[_product_read_payload()])

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = build_stockpilot_tools(client, lambda: db_session, execution_id)
    list_products_tool = _tools_by_name(tools)["list_products"]

    result = list_products_tool.invoke({"limit": 5, "offset": 0})

    assert isinstance(result, list)
    assert isinstance(result[0], ProductRead)
    assert result[0].sku == "85048"

    rows = db_session.query(ToolCall).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.execution_id == execution_id
    assert row.tool_name == "list_products"
    assert row.args == {"limit": 5, "offset": 0}
    assert row.status == "success"
    assert row.latency_ms is not None
    assert row.latency_ms >= 0
    assert isinstance(row.raw_response, list)
    assert row.raw_response[0]["sku"] == "85048"
    assert row.provenance_map == {
        "sku": "observed",
        "description": "observed",
        "unit_cost": "derived",
        "reorder_point": "derived",
        "safety_stock": "derived",
    }


def test_empty_result_set_persists_a_successful_call_not_an_error(db_session: Session) -> None:
    """Task 3.6: "Empty result set -> a valid answer, not an error." At
    the tool layer, that means a query that legitimately matches nothing
    (e.g. every SKU in a category is well-stocked) must persist status
    "success" with an empty raw_response, never status "error" -- the
    opposite of test_failed_tool_call_persists_error_status_and_reraises,
    which the tool layer must keep genuinely distinguishable from this.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(200, json=[])

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = build_stockpilot_tools(client, lambda: db_session, execution_id)
    low_stock_tool = _tools_by_name(tools)["get_low_stock"]

    result = low_stock_tool.invoke({"limit": 100, "offset": 0})

    assert result == []
    row = db_session.query(ToolCall).one()
    assert row.execution_id == execution_id
    assert row.tool_name == "get_low_stock"
    assert row.status == "success"
    assert row.raw_response == []
    assert row.provenance_map == {}


def test_no_arg_tool_persists_empty_args(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(
            200,
            json={
                "selected_model": "moving_average",
                "training_window_start": "2009-12-01",
                "training_window_end": "2011-11-11",
                "test_window_start": "2011-11-12",
                "test_window_end": "2011-12-09",
                "n_skus_evaluated": 4801,
                "seasonal_naive_mae": 6.0,
                "seasonal_naive_mape": 246.0,
                "moving_average_mae": 5.1,
                "moving_average_mape": 158.0,
                "gbm_mae": 6.0,
                "gbm_mape": 250.0,
                "_provenance": {"n_skus_evaluated": "derived"},
                "_derivation_ref": {},
            },
        )

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = build_stockpilot_tools(client, lambda: db_session, execution_id)
    accuracy_tool = _tools_by_name(tools)["get_forecast_accuracy"]

    accuracy_tool.invoke({})

    row = db_session.query(ToolCall).one()
    assert row.tool_name == "get_forecast_accuracy"
    assert row.args == {}


def test_failed_tool_call_persists_error_status_and_reraises(db_session: Session) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(404, json={"detail": "Product not found"})

    client = _client(handler)
    execution_id = _new_execution(db_session)
    tools = build_stockpilot_tools(client, lambda: db_session, execution_id)
    get_product_tool = _tools_by_name(tools)["get_product"]

    with pytest.raises(httpx2.HTTPStatusError):
        get_product_tool.invoke({"sku": "NOPE"})

    row = db_session.query(ToolCall).one()
    assert row.tool_name == "get_product"
    assert row.status == "error"
    assert row.provenance_map == {}
    assert isinstance(row.raw_response, dict)
    assert "error" in row.raw_response
