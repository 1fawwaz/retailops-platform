"""Stage 4 Task 4.1: wraps tools/derived.py's pure computations as
StructuredTools the Inventory and Forecast agents can call, fetching the
real StockPilot data each one needs and computing the derived result in
Python before the model ever sees a number -- the same invariant
tools/stockpilot_tools.py (Task 2.3) enforces for the 18 real endpoints,
extended here to values no StockPilot endpoint returns.

Each tool still persists exactly one `tool_calls` row (execution_id,
args, raw computed result, provenance map, latency, status), same shape
as the endpoint tools, so these numbers are exactly as traceable via
tool_call_id and exactly as subject to the citation validator (Task 3.5)
as anything fetched directly from StockPilot -- grounding doesn't care
whether a number came straight off the wire or was computed locally from
things that did.

Deliberately a separate module from tools/stockpilot_tools.py rather than
folded into it: that module's own docstring describes its scope as
exactly the 18 read endpoints, and CLAUDE.md's workflow rules say not to
refactor an earlier task's shipped code without being asked -- this
duplicates its small persistence helper rather than extracting a shared
one.
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
from orchestration.models.base import JsonDict
from orchestration.models.tool_call import ToolCall
from serialization import to_jsonable
from tools.derived import (
    DaysOfCoverResult,
    ReorderTimingResult,
    StockoutRiskRanking,
    StockPosition,
    compute_days_of_cover,
    compute_reorder_timing,
    rank_stockout_risk,
)
from tools.schemas import DaysOfCoverArgs, RankStockoutRiskArgs, ReorderTimingArgs

ArgsT = TypeVar("ArgsT", bound=BaseModel)


def _extract_provenance(value: object) -> JsonDict:
    provenance = getattr(value, "field_provenance", None)
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
                    raw_response=(to_jsonable(result) if error is None else {"error": str(error)}),
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


def _rank_stockout_risk(
    client: StockPilotClient, args: RankStockoutRiskArgs
) -> StockoutRiskRanking:
    stock_items = client.get_low_stock(category=args.category, limit=args.limit, offset=args.offset)
    positions = [
        StockPosition(
            sku=item.sku,
            description=item.description,
            quantity_on_hand=item.quantity_on_hand,
            reorder_point=item.reorder_point,
        )
        for item in stock_items
    ]
    return rank_stockout_risk(positions)


def _days_of_cover(client: StockPilotClient, args: DaysOfCoverArgs) -> DaysOfCoverResult:
    product = client.get_product(args.sku)
    if product.quantity_on_hand is None:
        raise ValueError(f"SKU {args.sku} has no recorded quantity_on_hand -- cannot compute.")
    forecasts = client.forecast_demand([args.sku], args.horizon_days)
    forecast = forecasts[0]
    return compute_days_of_cover(
        sku=args.sku,
        quantity_on_hand=product.quantity_on_hand,
        predicted_daily_demand=forecast.predicted_daily_demand,
        data_quality=forecast.data_quality,
    )


def _reorder_timing(client: StockPilotClient, args: ReorderTimingArgs) -> ReorderTimingResult:
    product = client.get_product(args.sku)
    if product.quantity_on_hand is None:
        raise ValueError(f"SKU {args.sku} has no recorded quantity_on_hand -- cannot compute.")
    if product.safety_stock is None:
        raise ValueError(f"SKU {args.sku} has no recorded safety_stock -- cannot compute.")
    if product.supplier_id is None:
        raise ValueError(f"SKU {args.sku} has no assigned supplier -- cannot look up lead time.")
    supplier = client.get_supplier(product.supplier_id)
    forecasts = client.forecast_demand([args.sku], args.horizon_days)
    forecast = forecasts[0]
    return compute_reorder_timing(
        sku=args.sku,
        quantity_on_hand=product.quantity_on_hand,
        safety_stock=product.safety_stock,
        predicted_daily_demand=forecast.predicted_daily_demand,
        lead_time_days=supplier.lead_time_days,
        data_quality=forecast.data_quality,
    )


def build_derived_tools(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> list[StructuredTool]:
    """One StructuredTool per derived computation, bound to this
    execution_id exactly like tools/stockpilot_tools.py::build_stockpilot_tools.
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
            "rank_stockout_risk",
            "Rank currently low-stock products by proximity to (or past) their reorder "
            "point -- quantity_on_hand / reorder_point, ascending, so the most urgent SKU "
            "is first. A purely stock-side ranking (no forecast); a lower ratio means "
            "closer to running out relative to the reorder buffer StockPilot already "
            "computed. Rows whose reorder point is missing or zero sort last, not omitted.",
            RankStockoutRiskArgs,
            _rank_stockout_risk,
        ),
        tool(
            "days_of_cover",
            "Days of stock remaining for one SKU at its predicted daily demand rate "
            "(quantity_on_hand / predicted_daily_demand). None when predicted demand is "
            "zero -- state that explicitly, never as infinite or fully covered.",
            DaysOfCoverArgs,
            _days_of_cover,
        ),
        tool(
            "reorder_timing",
            "For one SKU: days until stock is projected to reach the safety-stock buffer "
            "at the predicted daily demand rate, and how many days from now to place a "
            "reorder so replenishment arrives before that buffer is breached, given the "
            "supplier's lead time. reorder_now=true means the order is already overdue. "
            "None when predicted demand is zero -- state that explicitly, don't guess.",
            ReorderTimingArgs,
            _reorder_timing,
        ),
    ]
