"""Stage 4 Task 4.1: pure, LLM-free derived computations the Inventory
and Forecast agents need that no StockPilot endpoint provides (Stage 1
is frozen -- these can't be added there). CLAUDE.md's corollary ("the
LLM never computes a business number") applies here exactly as it does
to StockPilot's own aggregates: these numbers are computed in Python,
from already-fetched, already-cited inputs, before an agent ever sees
them. tools/derived_tools.py wraps these as the same kind of
provenance-carrying, ToolCall-persisted tool as the 18 real StockPilot
endpoints (tools/stockpilot_tools.py) -- everything here is intentionally
pure (no DB, no HTTP, no randomness) so it's directly unit-testable
without any of that machinery.

Provenance never upgrades (CLAUDE.md section 5): days_of_cover and
reorder timing descend from a forecast, so they carry "predicted", the
same label as the forecast itself, never "derived". stock_ratio (the
stockout-risk ranking) descends only from quantity_on_hand and
reorder_point, both "derived", so it stays "derived".
"""

from __future__ import annotations

from pydantic import BaseModel

DAYS_OF_COVER_PROVENANCE = {
    "sku": "observed",
    "quantity_on_hand": "derived",
    "predicted_daily_demand": "predicted",
    "days_of_cover": "predicted",
    "data_quality": "observed",
}

REORDER_TIMING_PROVENANCE = {
    "sku": "observed",
    "quantity_on_hand": "derived",
    "safety_stock": "derived",
    "predicted_daily_demand": "predicted",
    "lead_time_days": "derived",
    "days_until_safety_stock": "predicted",
    "reorder_by_days": "predicted",
    "reorder_now": "predicted",
    "data_quality": "observed",
}

STOCKOUT_RISK_PROVENANCE = {
    "sku": "observed",
    "quantity_on_hand": "derived",
    "reorder_point": "derived",
    "stock_ratio": "derived",
}


class DaysOfCoverResult(BaseModel):
    field_provenance: dict[str, str]
    sku: str
    quantity_on_hand: int
    predicted_daily_demand: float
    # None when predicted_daily_demand is 0 (a genuine, documented forecast
    # outcome for a no-history SKU, not a missing value) -- division would
    # be undefined, so this states the gap rather than reporting infinity
    # or silently treating it as "fully covered".
    days_of_cover: float | None
    data_quality: str


def compute_days_of_cover(
    *, sku: str, quantity_on_hand: int, predicted_daily_demand: float, data_quality: str
) -> DaysOfCoverResult:
    days_of_cover = (
        quantity_on_hand / predicted_daily_demand if predicted_daily_demand > 0 else None
    )
    return DaysOfCoverResult(
        field_provenance=DAYS_OF_COVER_PROVENANCE,
        sku=sku,
        quantity_on_hand=quantity_on_hand,
        predicted_daily_demand=predicted_daily_demand,
        days_of_cover=days_of_cover,
        data_quality=data_quality,
    )


class ReorderTimingResult(BaseModel):
    field_provenance: dict[str, str]
    sku: str
    quantity_on_hand: int
    safety_stock: int
    predicted_daily_demand: float
    lead_time_days: int
    # Day the stock is projected to fall to the safety-stock buffer, at
    # the forecast daily demand rate.
    days_until_safety_stock: float | None
    # days_until_safety_stock - lead_time_days: order by this many days
    # from now so the replenishment arrives before safety stock is
    # breached. <= 0 means the order should already have been placed.
    reorder_by_days: float | None
    reorder_now: bool | None
    data_quality: str


def compute_reorder_timing(
    *,
    sku: str,
    quantity_on_hand: int,
    safety_stock: int,
    predicted_daily_demand: float,
    lead_time_days: int,
    data_quality: str,
) -> ReorderTimingResult:
    if predicted_daily_demand <= 0:
        days_until_safety_stock = None
        reorder_by_days = None
        reorder_now = None
    else:
        days_until_safety_stock = (quantity_on_hand - safety_stock) / predicted_daily_demand
        reorder_by_days = days_until_safety_stock - lead_time_days
        reorder_now = reorder_by_days <= 0
    return ReorderTimingResult(
        field_provenance=REORDER_TIMING_PROVENANCE,
        sku=sku,
        quantity_on_hand=quantity_on_hand,
        safety_stock=safety_stock,
        predicted_daily_demand=predicted_daily_demand,
        lead_time_days=lead_time_days,
        days_until_safety_stock=days_until_safety_stock,
        reorder_by_days=reorder_by_days,
        reorder_now=reorder_now,
        data_quality=data_quality,
    )


class StockPosition(BaseModel):
    """The minimal shape rank_stockout_risk needs -- deliberately not
    StockItem itself (clients/stockpilot_models.py), so this pure
    function stays testable without constructing a full generated model.
    tools/derived_tools.py maps real StockItem rows into this shape.
    """

    sku: str
    description: str | None
    quantity_on_hand: int
    reorder_point: int | None


class StockoutRiskRow(BaseModel):
    sku: str
    description: str | None
    quantity_on_hand: int
    reorder_point: int | None
    # quantity_on_hand / reorder_point -- lower means closer to (or past)
    # the reorder point, i.e. more urgent. None when reorder_point is
    # missing or zero (can't form a meaningful ratio); such rows sort
    # last rather than being silently dropped or treated as zero risk.
    stock_ratio: float | None


class StockoutRiskRanking(BaseModel):
    field_provenance: dict[str, str]
    items: list[StockoutRiskRow]


def rank_stockout_risk(positions: list[StockPosition]) -> StockoutRiskRanking:
    rows = [
        StockoutRiskRow(
            sku=position.sku,
            description=position.description,
            quantity_on_hand=position.quantity_on_hand,
            reorder_point=position.reorder_point,
            stock_ratio=(
                position.quantity_on_hand / position.reorder_point
                if position.reorder_point
                else None
            ),
        )
        for position in positions
    ]
    ranked = sorted(
        rows, key=lambda row: row.stock_ratio if row.stock_ratio is not None else float("inf")
    )
    return StockoutRiskRanking(field_provenance=STOCKOUT_RISK_PROVENANCE, items=ranked)


# Stage 4 Task 4.5: "which products are dead stock and how much capital
# is in them" -- get_dead_stock has no cost field (capital needs
# quantity_on_hand * unit_cost, and unit_cost lives on the product
# record), so this was previously only computable inside the Task 4.4
# business-review workflow (services/dead_stock.py, which takes
# StructuredTool objects since it's invoked from a fixed pipeline, not
# an agent's own tool-calling loop). This is the same formula, reshaped
# for tools/derived_tools.py's fetch-then-compute split (like
# rank_stockout_risk above: derived_tools.py fetches raw data via the
# client directly, this function only sums already-paired data) so the
# Inventory Agent can compute it too when a user asks directly -- not a
# duplicate by oversight, a different call shape for a different caller.
DEAD_STOCK_CAPITAL_PROVENANCE = {
    "dead_stock_capital": "derived",
    "sku_count": "observed",
    "skus_missing_cost": "observed",
}


class DeadStockPosition(BaseModel):
    sku: str
    quantity_on_hand: int
    unit_cost: float | None


class DeadStockCapitalResult(BaseModel):
    field_provenance: dict[str, str]
    dead_stock_capital: float
    sku_count: int
    # SKUs skipped from the sum for lacking a recorded unit_cost --
    # surfaced explicitly so a caller can see the total undercounts
    # rather than silently treating a missing cost as zero.
    skus_missing_cost: int


def compute_dead_stock_capital(positions: list[DeadStockPosition]) -> DeadStockCapitalResult:
    capital = 0.0
    skus_missing_cost = 0
    for position in positions:
        if position.unit_cost is None:
            skus_missing_cost += 1
            continue
        capital += position.quantity_on_hand * position.unit_cost
    return DeadStockCapitalResult(
        field_provenance=DEAD_STOCK_CAPITAL_PROVENANCE,
        dead_stock_capital=capital,
        sku_count=len(positions),
        skus_missing_cost=skus_missing_cost,
    )
