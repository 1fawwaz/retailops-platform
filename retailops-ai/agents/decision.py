"""Stage 4 Task 4.3: the Decision Engine. CLAUDE.md invariant 1 makes
this agent tool-less by design (agents/base.py's build_agents()) so it
is structurally incapable of inventing a number -- this module is the
graph-adjacent Python layer that runs BEFORE the Decision Engine's own
LLM call, gathering evidence and computing all four numeric fields
(revenue_at_risk, inventory_cost, confidence, priority) so that by the
time the model is invoked, it is only ever asked to write two text
fields (`reason`, `risk_if_ignored`), enforced structurally via
DecisionNarrative rather than merely requested in a prompt.

Every StockPilotClient call here goes through the SAME StructuredTool
objects tools/stockpilot_tools.py builds for the retrieval agents --
invoked directly (`.invoke(args)`), not through an agent's tool-calling
loop (the Decision Engine has none), but each invocation still persists
a `tool_calls` row exactly the same way, so every number in the
resulting Recommendation stays traceable via tool_call_id.

Two business values the spec's own text never defines a formula for
(confirmed by a full-text search, not an oversight) were resolved with
the user rather than guessed silently -- see project memory and
docs/stockpilot-gaps.md#2:
  - recommended_order_qty (services/order_quantity.py): the standard
    reorder-to-target-level formula, using fields already wired up
    elsewhere in this codebase (Task 4.1's reorder_timing tool).
  - unit_price (services/pricing.py): derived from a large-limit
    top/bottom-products search, since no StockPilot endpoint returns a
    per-SKU price directly -- None (not a default) when the SKU isn't
    found in either ranking, which this module then propagates as an
    unset `revenue_at_risk` rather than a fabricated figure.

`days_to_stockout` (priority tiering) and `projected_stockout_days`
(revenue_at_risk) are deliberately different quantities, matching the
spec's own different wording for each: days_to_stockout is simply
"when does stock hit zero" (days_of_cover, independent of any reorder
action); projected_stockout_days is "how many days will we actually be
unable to sell", i.e. only the portion of that runway not covered by
the supplier's lead time -- max(0, lead_time_days - days_of_cover). A
SKU whose lead time is shorter than its days of cover never actually
stocks out (replenishment arrives in time), so its revenue_at_risk is
correctly 0, not proportional to days_of_cover.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.base import Agent
from clients.stockpilot import StockPilotClient
from orchestration.models.recommendation import Recommendation as RecommendationRow
from orchestration.models.tool_call import ToolCall
from services.confidence import compute_confidence
from services.order_quantity import compute_recommended_order_qty
from services.pricing import find_unit_price
from services.priority import Priority, compute_priority
from thresholds_config import get_thresholds_config
from tools.stockpilot_tools import build_stockpilot_tools

DEFAULT_HORIZON_DAYS = 14


class RecommendationDataGap(Exception):
    """Raised when a SKU is missing data compute_recommendation_numbers()
    needs (no recorded stock, no assigned supplier, ...) -- surfaced as a
    clear, typed error so a batch caller (Task 4.4's workflow endpoints)
    can skip and continue rather than silently defaulting a business
    value for that SKU.
    """


class DecisionNarrative(BaseModel):
    """The ONLY thing the Decision Engine's own LLM call is allowed to
    produce -- structurally enforced (a two-field schema, not a prompt
    instruction alone) so it cannot restate or adjust any of the four
    numbers computed below it, matching the spec's "ALL FOUR NUMBERS ARE
    COMPUTED IN PYTHON. The LLM never produces them."
    """

    reason: str
    risk_if_ignored: str


@dataclass(frozen=True)
class RecommendationNumbers:
    sku: str
    action: str
    priority: Priority
    revenue_at_risk: float | None
    inventory_cost: float
    confidence: float
    evidence: list[str]
    quantity_on_hand: int
    reorder_point: int | None
    safety_stock: int
    predicted_daily_demand: float
    days_of_cover: float | None
    recommended_order_qty: int
    supplier_name: str
    lead_time_days: int
    unit_cost: float
    unit_price: float | None
    data_quality: str


class Recommendation(BaseModel):
    sku: str
    action: str
    priority: Priority
    reason: str
    revenue_at_risk: float | None
    inventory_cost: float
    confidence: float
    risk_if_ignored: str
    evidence: list[str]


def _owned_tool_call_ids(
    session_factory: Callable[[], Session], execution_id: uuid.UUID, tool_names: set[str]
) -> set[uuid.UUID]:
    session = session_factory()
    try:
        rows = (
            session.query(ToolCall.tool_call_id)
            .filter(ToolCall.execution_id == execution_id, ToolCall.tool_name.in_(tool_names))
            .all()
        )
        return {row.tool_call_id for row in rows}
    finally:
        session.close()


def _new_owned_tool_call_ids(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    tool_names: set[str],
    before_ids: set[uuid.UUID],
) -> list[uuid.UUID]:
    session = session_factory()
    try:
        rows = (
            session.query(ToolCall.tool_call_id)
            .filter(ToolCall.execution_id == execution_id, ToolCall.tool_name.in_(tool_names))
            .all()
        )
        return [row.tool_call_id for row in rows if row.tool_call_id not in before_ids]
    finally:
        session.close()


def compute_recommendation_numbers(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    sku: str,
    *,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> RecommendationNumbers:
    """Gathers every input the spec's formulas need for one SKU and
    computes all four numeric fields in pure Python. Raises
    RecommendationDataGap if the SKU is missing data required to proceed
    (no recorded stock, no safety stock, no assigned supplier) -- never
    fabricates a substitute.
    """
    tools: dict[str, StructuredTool] = {
        tool.name: tool for tool in build_stockpilot_tools(client, session_factory, execution_id)
    }
    owned_names = set(tools)
    before_ids = _owned_tool_call_ids(session_factory, execution_id, owned_names)

    product = tools["get_product"].invoke({"sku": sku})
    if product.quantity_on_hand is None:
        raise RecommendationDataGap(f"SKU {sku} has no recorded quantity_on_hand.")
    if product.safety_stock is None:
        raise RecommendationDataGap(f"SKU {sku} has no recorded safety_stock.")
    if product.supplier_id is None:
        raise RecommendationDataGap(f"SKU {sku} has no assigned supplier.")
    if product.unit_cost is None:
        raise RecommendationDataGap(f"SKU {sku} has no recorded unit_cost.")

    supplier = tools["get_supplier"].invoke({"supplier_id": product.supplier_id})
    forecasts = tools["forecast_demand"].invoke({"skus": [sku], "horizon_days": horizon_days})
    forecast = forecasts[0]

    pricing_limit = get_thresholds_config().pricing.lookup_limit
    unit_price = find_unit_price(
        top_products_tool=tools["get_top_products"],
        bottom_products_tool=tools["get_bottom_products"],
        sku=sku,
        limit=pricing_limit,
    )

    new_ids = _new_owned_tool_call_ids(session_factory, execution_id, owned_names, before_ids)
    evidence = [str(tool_call_id) for tool_call_id in new_ids]

    predicted_daily_demand = forecast.predicted_daily_demand
    days_of_cover = (
        product.quantity_on_hand / predicted_daily_demand if predicted_daily_demand > 0 else None
    )
    projected_stockout_days = (
        max(0.0, supplier.lead_time_days - days_of_cover) if days_of_cover is not None else 0.0
    )
    revenue_at_risk = (
        predicted_daily_demand * unit_price * projected_stockout_days
        if unit_price is not None
        else None
    )

    recommended_order_qty = compute_recommended_order_qty(
        predicted_daily_demand=predicted_daily_demand,
        lead_time_days=supplier.lead_time_days,
        safety_stock=product.safety_stock,
        quantity_on_hand=product.quantity_on_hand,
    )
    inventory_cost = recommended_order_qty * product.unit_cost

    confidence = compute_confidence(
        confidence_interval_lower=forecast.confidence_interval_lower,
        confidence_interval_upper=forecast.confidence_interval_upper,
        predicted_daily_demand=predicted_daily_demand,
        data_quality=forecast.data_quality,
        history_days=_history_days(forecast.training_window_start, forecast.training_window_end),
    )

    # Priority tiering wants a plain days-to-stockout number, never
    # infinite -- a SKU with no meaningful demand (days_of_cover is None)
    # is the opposite of urgent, so it's given a large sentinel that
    # never trips a threshold, not a special-cased branch in
    # services/priority.py itself.
    days_to_stockout = days_of_cover if days_of_cover is not None else float("inf")
    priority = compute_priority(revenue_at_risk=revenue_at_risk, days_to_stockout=days_to_stockout)

    action = (
        f"Reorder {recommended_order_qty} units of {sku} from {supplier.name}"
        if recommended_order_qty > 0
        else f"No reorder currently needed for {sku}"
    )

    return RecommendationNumbers(
        sku=sku,
        action=action,
        priority=priority,
        revenue_at_risk=revenue_at_risk,
        inventory_cost=inventory_cost,
        confidence=confidence,
        evidence=evidence,
        quantity_on_hand=product.quantity_on_hand,
        reorder_point=product.reorder_point,
        safety_stock=product.safety_stock,
        predicted_daily_demand=predicted_daily_demand,
        days_of_cover=days_of_cover,
        recommended_order_qty=recommended_order_qty,
        supplier_name=supplier.name,
        lead_time_days=supplier.lead_time_days,
        unit_cost=product.unit_cost,
        unit_price=unit_price,
        data_quality=forecast.data_quality,
    )


def _history_days(start: date | None, end: date | None) -> int:
    if start is None or end is None:
        return 0
    return (end - start).days


def _narrative_prompt(numbers: RecommendationNumbers) -> str:
    unit_price_text = (
        f"{numbers.unit_price:.2f}"
        if numbers.unit_price is not None
        else "unavailable (no unit price found for this SKU)"
    )
    revenue_at_risk_text = (
        f"{numbers.revenue_at_risk:.2f}" if numbers.revenue_at_risk is not None else "unavailable"
    )
    days_of_cover_text = (
        f"{numbers.days_of_cover:.1f}" if numbers.days_of_cover is not None else "not applicable"
    )
    return (
        f"SKU {numbers.sku}: quantity_on_hand={numbers.quantity_on_hand}, "
        f"reorder_point={numbers.reorder_point}, safety_stock={numbers.safety_stock}, "
        f"predicted_daily_demand={numbers.predicted_daily_demand:.2f} "
        f"(data_quality={numbers.data_quality}), days_of_cover={days_of_cover_text}, "
        f"supplier={numbers.supplier_name} (lead_time_days={numbers.lead_time_days}), "
        f"unit_cost={numbers.unit_cost:.2f}, unit_price={unit_price_text}.\n\n"
        f"Already-computed recommendation: action={numbers.action!r}, "
        f"priority={numbers.priority}, revenue_at_risk={revenue_at_risk_text}, "
        f"inventory_cost={numbers.inventory_cost:.2f}, confidence={numbers.confidence:.4f}.\n\n"
        "Write only `reason` (why this action, referencing the evidence above by figure) "
        "and `risk_if_ignored` (what happens if not acted on). Do not restate any number "
        "with a different value than given above."
    )


def build_recommendation(
    agent: Agent,
    numbers: RecommendationNumbers,
    *,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    iteration: int = 1,
) -> Recommendation:
    """The Decision Engine's only LLM call in this pipeline: writes
    `reason`/`risk_if_ignored` given the already-computed numbers as
    read-only context. Every numeric field on the returned Recommendation
    comes from `numbers`, never from the model's own output.
    """
    narrative = agent.invoke_structured(
        _narrative_prompt(numbers),
        DecisionNarrative,
        session_factory=session_factory,
        execution_id=execution_id,
        iteration=iteration,
    )
    return Recommendation(
        sku=numbers.sku,
        action=numbers.action,
        priority=numbers.priority,
        reason=narrative.reason,
        revenue_at_risk=numbers.revenue_at_risk,
        inventory_cost=numbers.inventory_cost,
        confidence=numbers.confidence,
        risk_if_ignored=narrative.risk_if_ignored,
        evidence=numbers.evidence,
    )


def persist_recommendation(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    recommendation: Recommendation,
) -> uuid.UUID:
    """Persists one Recommendation with status="pending" (the DB column's
    own default) -- ranking by revenue_at_risk across a batch is the
    caller's job (e.g. sorting before calling this per recommendation),
    not something this single-row insert does itself.

    revenue_at_risk can be None (docs/stockpilot-gaps.md#2, no unit
    price found) -- the column is NOT NULL, so that gap is persisted as
    0.0 with the gap itself visible in `reason`/`risk_if_ignored`
    (build_recommendation's prompt already tells the model to say so)
    rather than a NULL the schema doesn't allow.
    """
    session = session_factory()
    try:
        row = RecommendationRow(
            execution_id=execution_id,
            sku=recommendation.sku,
            action=recommendation.action,
            priority=recommendation.priority,
            reason=recommendation.reason,
            revenue_at_risk=(
                recommendation.revenue_at_risk
                if recommendation.revenue_at_risk is not None
                else 0.0
            ),
            inventory_cost=recommendation.inventory_cost,
            confidence=recommendation.confidence,
            risk_if_ignored=recommendation.risk_if_ignored,
            evidence=recommendation.evidence,
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()
