"""Stage 2 Task 2.3: wraps StockPilotClient's read endpoints as LangGraph
tools. Every invocation writes a tool_calls row (execution_id,
tool_call_id, args, raw response, provenance map, latency, status)
before returning -- this is what invariant 2 (full trace) and the
citation validator (Task 3.5) rely on downstream.

Scope: only the 18 read/retrieval endpoints are exposed as tools. Per
Task 3.1, the six agents (Planner, Inventory, Forecast, Analytics,
Report, Decision Engine) only ever need retrieval -- none of them is
described as creating, updating, or deleting StockPilot data, and CLAUDE.md
never asks the agent to write to StockPilot. create_product,
update_product, delete_product, create_supplier, update_supplier,
delete_supplier, register_user, and health remain available directly on
StockPilotClient (exercised by Task 2.2's milestone check) but are
deliberately not exposed as LLM-callable tools -- giving an LLM
autonomous write access to StockPilot's data is a real attack surface
with no described use case to justify it, in the same spirit as the
spec's "DO NOT BUILD: PO creation flows" boundary.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TypeVar

from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from clients.stockpilot import StockPilotClient
from orchestration.models.base import JsonDict, JsonValue
from orchestration.models.tool_call import ToolCall
from tools.schemas import (
    ForecastDemandArgs,
    GetAbcArgs,
    GetBottomProductsArgs,
    GetDeadStockArgs,
    GetForecastAccuracyArgs,
    GetInventoryValuationArgs,
    GetLowStockArgs,
    GetPeriodComparisonArgs,
    GetProductArgs,
    GetProfitArgs,
    GetRevenueArgs,
    GetSlowMoversArgs,
    GetStockArgs,
    GetSupplierArgs,
    GetTopProductsArgs,
    GetTurnoverArgs,
    ListProductsArgs,
    ListSuppliersArgs,
)

ArgsT = TypeVar("ArgsT", bound=BaseModel)


def _to_jsonable(value: object) -> JsonValue | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        result: JsonDict = value.model_dump(mode="json", by_alias=True)
        return result
    if isinstance(value, list):
        return [
            item.model_dump(mode="json", by_alias=True) if isinstance(item, BaseModel) else item
            for item in value
        ]
    if isinstance(value, dict):
        return value
    raise TypeError(f"Cannot serialize tool result of type {type(value)!r}")


def _extract_provenance(value: object) -> JsonDict:
    """Every generated response model carries a `field_provenance` attribute
    (aliased `_provenance` on the wire). List responses repeat the same
    static per-field labels on every row (see stockpilot-core's
    PRODUCT_PROVENANCE-style constants), so the first row is
    representative of the whole list, not a lossy sample.
    """
    candidate = value[0] if isinstance(value, list) and value else value
    provenance = getattr(candidate, "field_provenance", None)
    return dict(provenance) if isinstance(provenance, dict) else {}


def _build_tool(
    *,
    name: str,
    description: str,
    args_schema: type[ArgsT],
    call: Callable[[StockPilotClient, ArgsT], object],
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> StructuredTool:
    def _run(**kwargs: object) -> object:
        args_model = args_schema.model_validate(kwargs)
        started = time.monotonic()
        result: object = None
        error: Exception | None = None
        try:
            result = call(client, args_model)
        except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised unchanged
            error = exc
        latency_ms = int((time.monotonic() - started) * 1000)

        session = session_factory()
        try:
            session.add(
                ToolCall(
                    execution_id=execution_id,
                    tool_name=name,
                    args=args_model.model_dump(mode="json"),
                    raw_response=(_to_jsonable(result) if error is None else {"error": str(error)}),
                    provenance_map=_extract_provenance(result) if error is None else {},
                    latency_ms=latency_ms,
                    status="success" if error is None else "error",
                )
            )
            session.commit()
        finally:
            session.close()

        if error is not None:
            raise error
        return result

    return StructuredTool.from_function(
        func=_run, name=name, description=description, args_schema=args_schema
    )


def build_stockpilot_tools(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> list[StructuredTool]:
    """One StructuredTool per read endpoint, bound to this execution_id so
    every tool_calls row it writes is attributable to the run that made it.
    """

    def tool(
        name: str,
        description: str,
        args_schema: type[ArgsT],
        call: Callable[[StockPilotClient, ArgsT], object],
    ) -> StructuredTool:
        return _build_tool(
            name=name,
            description=description,
            args_schema=args_schema,
            call=call,
            client=client,
            session_factory=session_factory,
            execution_id=execution_id,
        )

    return [
        tool(
            "list_products",
            "List all products in the catalog, paginated. Returns each product's "
            "SKU, description, category, supplier, unit cost, reorder point, and "
            "safety stock, each with a provenance label.",
            ListProductsArgs,
            lambda c, a: c.list_products(limit=a.limit, offset=a.offset),
        ),
        tool(
            "get_product",
            "Get full detail for one product by SKU: current quantity on hand and "
            "its 90-day stock movement history, alongside the same fields as "
            "list_products.",
            GetProductArgs,
            lambda c, a: c.get_product(a.sku),
        ),
        tool(
            "list_suppliers",
            "List all suppliers, paginated: name, lead time, and reliability score.",
            ListSuppliersArgs,
            lambda c, a: c.list_suppliers(limit=a.limit, offset=a.offset),
        ),
        tool(
            "get_supplier",
            "Get full detail for one supplier by ID, including the list of SKUs they supply.",
            GetSupplierArgs,
            lambda c, a: c.get_supplier(a.supplier_id),
        ),
        tool(
            "get_stock",
            "Query current stock levels across products, optionally filtered by "
            "category, low-stock status, or a search term.",
            GetStockArgs,
            lambda c, a: c.get_stock(
                category=a.category,
                low_stock=a.low_stock,
                search=a.search,
                limit=a.limit,
                offset=a.offset,
            ),
        ),
        tool(
            "get_low_stock",
            "List products currently at or below their reorder point.",
            GetLowStockArgs,
            lambda c, a: c.get_low_stock(category=a.category, limit=a.limit, offset=a.offset),
        ),
        tool(
            "get_dead_stock",
            "List products with no stock movement in the given number of days "
            "(default 90) -- capital tied up in stock that isn't selling.",
            GetDeadStockArgs,
            lambda c, a: c.get_dead_stock(days=a.days, limit=a.limit, offset=a.offset),
        ),
        tool(
            "get_slow_movers",
            "List products in stock whose average daily sales velocity over the "
            "trailing window is below the threshold -- still selling, just "
            "slowly, distinct from dead stock.",
            GetSlowMoversArgs,
            lambda c, a: c.get_slow_movers(
                window_days=a.window_days,
                velocity_threshold=a.velocity_threshold,
                limit=a.limit,
                offset=a.offset,
            ),
        ),
        tool(
            "get_inventory_valuation",
            "Capital tied up in on-hand inventory (quantity x unit cost), by category.",
            GetInventoryValuationArgs,
            lambda c, a: c.get_inventory_valuation(category=a.category),
        ),
        tool(
            "get_revenue",
            "Revenue and units sold, grouped by day, week, month, or category, "
            "optionally filtered by date range.",
            GetRevenueArgs,
            lambda c, a: c.get_revenue(
                group_by=a.group_by, start_date=a.start_date, end_date=a.end_date
            ),
        ),
        tool(
            "get_profit",
            "Revenue, cost, gross profit, and margin, grouped by day, week, month, or category.",
            GetProfitArgs,
            lambda c, a: c.get_profit(
                group_by=a.group_by, start_date=a.start_date, end_date=a.end_date
            ),
        ),
        tool(
            "get_turnover",
            "Inventory turnover ratio (units sold / average stock on hand) per "
            "category over a date window.",
            GetTurnoverArgs,
            lambda c, a: c.get_turnover(start_date=a.start_date, end_date=a.end_date),
        ),
        tool(
            "get_abc",
            "ABC classification of SKUs by revenue contribution (Pareto "
            "analysis): class A/B/C plus each SKU's cumulative revenue share.",
            GetAbcArgs,
            lambda c, a: c.get_abc(
                start_date=a.start_date,
                end_date=a.end_date,
                a_threshold=a.a_threshold,
                b_threshold=a.b_threshold,
            ),
        ),
        tool(
            "get_top_products",
            "Top-performing products by revenue, margin, or units sold.",
            GetTopProductsArgs,
            lambda c, a: c.get_top_products(
                metric=a.metric, limit=a.limit, start_date=a.start_date, end_date=a.end_date
            ),
        ),
        tool(
            "get_bottom_products",
            "Worst-performing products by revenue, margin, or units sold.",
            GetBottomProductsArgs,
            lambda c, a: c.get_bottom_products(
                metric=a.metric, limit=a.limit, start_date=a.start_date, end_date=a.end_date
            ),
        ),
        tool(
            "get_period_comparison",
            "Compare revenue, units, cost, gross profit, and margin between two "
            "date periods, with deltas.",
            GetPeriodComparisonArgs,
            lambda c, a: c.get_period_comparison(
                period1_start=a.period1_start,
                period1_end=a.period1_end,
                period2_start=a.period2_start,
                period2_end=a.period2_end,
            ),
        ),
        tool(
            "forecast_demand",
            "Predicted daily demand, confidence interval, model used, training "
            "window, and data-quality flag for each requested SKU, over the "
            "given horizon.",
            ForecastDemandArgs,
            lambda c, a: c.forecast_demand(a.skus, a.horizon_days),
        ),
        tool(
            "get_forecast_accuracy",
            "Backtest MAE/MAPE for each forecasting model and which model is "
            "currently selected in production.",
            GetForecastAccuracyArgs,
            lambda c, _a: c.get_forecast_accuracy(),
        ),
    ]
