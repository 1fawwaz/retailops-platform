"""Stage 4 Task 4.4: the two goal-driven workflow pipelines. Unlike
orchestration/executor.py's run_execution() (the general /agent/query
flow, LLM-planned via the LangGraph graph), these are deterministic,
code-driven pipelines with a fixed sequence of steps -- no Planner, no
replan loop, no citation validator node, since there's no open-ended
question to plan around. Each still creates its own Execution row (so
every tool call and agent_steps row it makes is attributed to a real
execution, same full-trace guarantee as the chat flow) and reuses the
exact same agents/tools built for that flow: agents/decision.py's
per-SKU recommendation pipeline (Task 4.3), agents/report.py's
structured reports (Task 4.2), and tools/derived_tools.py's
rank_stockout_risk (Task 4.1).

BACKTEST MODE (docs/stockpilot-gaps.md#3, resolved with the user): the
two workflows are honest about what "as_of_date" can and can't mean.
business-review does a REAL backtest -- as_of_date sets the end of the
review period, and every revenue/profit/margin/top-bottom/category
figure is queried for that actual historical window via StockPilot's
date-range-capable analytics endpoints (which query immutable
sales_transactions). inventory-health can only apply the required LABEL
-- StockPilot has no endpoint returning a past stock/forecast snapshot,
so as_of_date stamps "Historical simulation as of <date>. Not live
monitoring." on the report without changing which data was queried.

Each report's `evidence` field is overwritten with the REAL tool_call_ids
gathered during that workflow's own data-fetching, not left to whatever
the Report Agent's structured output wrote -- an LLM recalling exact
UUIDs accurately in free-form structured output is not a safe
assumption invariant 1 should rest on; Python already knows the true list.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.base import build_agents
from agents.decision import (
    Recommendation,
    RecommendationDataGap,
    build_recommendation,
    compute_recommendation_numbers,
    persist_recommendation,
)
from agents.report import (
    CategoryPerformance,
    DeadStockRow,
    HealthReport,
    LowStockItem,
    PerformanceReport,
    ProductPerformanceEntry,
    SlowMoverRow,
    build_report,
    persist_report,
    render_report_markdown,
)
from clients.stockpilot import StockPilotClient
from orchestration.models.agent_step import AgentStep
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from services.dead_stock import compute_dead_stock_capital
from thresholds_config import get_thresholds_config
from tools.derived_tools import build_derived_tools
from tools.stockpilot_tools import build_stockpilot_tools


def _new_execution(session_factory: Callable[[], Session], query: str) -> uuid.UUID:
    session = session_factory()
    try:
        execution = Execution(query=query, status="running")
        session.add(execution)
        session.commit()
        return execution.id
    finally:
        session.close()


def _sum_agent_step_tokens(session_factory: Callable[[], Session], execution_id: uuid.UUID) -> int:
    session = session_factory()
    try:
        total_tokens = (
            session.query(
                func.coalesce(
                    func.sum(
                        func.coalesce(AgentStep.prompt_tokens, 0)
                        + func.coalesce(AgentStep.completion_tokens, 0)
                    ),
                    0,
                )
            )
            .filter(AgentStep.execution_id == execution_id)
            .scalar()
        )
        return int(total_tokens)
    finally:
        session.close()


def _complete_execution(
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    final_answer: str,
    total_tokens: int,
) -> None:
    session = session_factory()
    try:
        execution = session.get(Execution, execution_id)
        assert execution is not None
        execution.status = "completed"
        execution.final_answer = final_answer
        execution.total_tokens = total_tokens
        execution.completed_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()


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


# -- Inventory health -----------------------------------------------------


@dataclass(frozen=True)
class PersistedRecommendation:
    id: uuid.UUID
    recommendation: Recommendation


@dataclass(frozen=True)
class InventoryHealthResult:
    execution_id: uuid.UUID
    report_id: uuid.UUID
    report: HealthReport
    markdown: str
    recommendations: list[PersistedRecommendation]
    skipped_skus: list[str]
    as_of_date: date | None
    backtest: bool


def run_inventory_health_workflow(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    *,
    as_of_date: date | None = None,
    max_recommendations: int | None = None,
) -> InventoryHealthResult:
    started = time.monotonic()
    thresholds = get_thresholds_config().workflows
    limit = max_recommendations or thresholds.inventory_health_max_recommendations

    execution_id = _new_execution(session_factory, "[workflow] inventory-health")
    agents = build_agents(client, session_factory, execution_id)
    derived_tools = {
        tool.name: tool for tool in build_derived_tools(client, session_factory, execution_id)
    }
    core_tools = {
        tool.name: tool for tool in build_stockpilot_tools(client, session_factory, execution_id)
    }
    all_tool_names = set(derived_tools) | set(core_tools)
    before_ids = _owned_tool_call_ids(session_factory, execution_id, all_tool_names)

    ranking = derived_tools["rank_stockout_risk"].invoke({"limit": limit})
    candidate_skus = [item.sku for item in ranking.items[:limit]]

    recommendations: list[Recommendation] = []
    skipped: list[str] = []
    for sku in candidate_skus:
        try:
            numbers = compute_recommendation_numbers(client, session_factory, execution_id, sku)
        except RecommendationDataGap as exc:
            skipped.append(f"{sku}: {exc}")
            continue
        recommendation = build_recommendation(
            agents["decision"],
            numbers,
            session_factory=session_factory,
            execution_id=execution_id,
        )
        recommendations.append(recommendation)

    recommendations.sort(
        key=lambda rec: rec.revenue_at_risk if rec.revenue_at_risk is not None else -1.0,
        reverse=True,
    )

    dead_stock_items = core_tools["get_dead_stock"].invoke(
        {"days": 90, "limit": thresholds.dead_stock_lookup_limit, "offset": 0}
    )
    slow_movers = core_tools["get_slow_movers"].invoke({"limit": 50, "offset": 0})
    valuation = core_tools["get_inventory_valuation"].invoke({})

    low_stock_items = [
        LowStockItem(
            sku=item.sku,
            description=item.description,
            quantity_on_hand=item.quantity_on_hand,
            reorder_point=item.reorder_point,
        )
        for item in ranking.items
    ]

    prompt = (
        f"Inventory health check. {len(ranking.items)} SKUs are at or below their reorder "
        f"point; {len(recommendations)} were fully quantified into ranked recommendations "
        f"(top action: {recommendations[0].action if recommendations else 'none'!r}). "
        f"Total inventory value is {valuation.total_inventory_value:.2f}. "
        f"{len(dead_stock_items)} SKUs are dead stock; {len(slow_movers)} are slow movers. "
        + (
            f"{len(skipped)} SKUs could not be quantified: {'; '.join(skipped)}. "
            if skipped
            else ""
        )
        + "Write a short `summary` of overall inventory health, grounded only in these figures."
    )
    draft = build_report(
        agents["report"],
        "health",
        prompt,
        session_factory=session_factory,
        execution_id=execution_id,
    )
    assert isinstance(draft, HealthReport)

    new_ids = [
        tool_call_id
        for tool_call_id in _owned_tool_call_ids(session_factory, execution_id, all_tool_names)
        if tool_call_id not in before_ids
    ]
    report = draft.model_copy(
        update={
            "title": "Inventory Health",
            "total_inventory_value": valuation.total_inventory_value,
            "low_stock_items": low_stock_items,
            "dead_stock_items": [
                DeadStockRow(
                    sku=item.sku,
                    description=item.description,
                    quantity_on_hand=item.quantity_on_hand,
                    days_since_movement=item.days_since_movement,
                )
                for item in dead_stock_items
            ],
            "slow_mover_items": [
                SlowMoverRow(
                    sku=item.sku,
                    description=item.description,
                    quantity_on_hand=item.quantity_on_hand,
                    avg_daily_demand=item.avg_daily_demand,
                )
                for item in slow_movers
            ],
            "evidence": [str(tool_call_id) for tool_call_id in new_ids],
        }
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    cost_tokens = _sum_agent_step_tokens(session_factory, execution_id)
    inputs: dict[str, object] = {
        "as_of_date": as_of_date.isoformat() if as_of_date else None,
        "limit": limit,
    }
    report_id = persist_report(
        session_factory,
        execution_id,
        report,
        inputs=inputs,
        duration_ms=duration_ms,
        cost_tokens=cost_tokens,
        as_of_date=as_of_date,
    )

    persisted: list[PersistedRecommendation] = []
    for recommendation in recommendations:
        recommendation_id = persist_recommendation(
            session_factory, execution_id, recommendation, report_id=report_id
        )
        persisted.append(
            PersistedRecommendation(id=recommendation_id, recommendation=recommendation)
        )

    markdown = render_report_markdown(report, as_of_date=as_of_date)
    _complete_execution(session_factory, execution_id, report.summary, cost_tokens)

    return InventoryHealthResult(
        execution_id=execution_id,
        report_id=report_id,
        report=report,
        markdown=markdown,
        recommendations=persisted,
        skipped_skus=skipped,
        as_of_date=as_of_date,
        backtest=as_of_date is not None,
    )


# -- Business review -----------------------------------------------------


@dataclass(frozen=True)
class BusinessReviewResult:
    execution_id: uuid.UUID
    report_id: uuid.UUID
    report: PerformanceReport
    markdown: str
    as_of_date: date | None
    backtest: bool


def run_business_review_workflow(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    *,
    as_of_date: date | None = None,
    period_days: int | None = None,
) -> BusinessReviewResult:
    """A REAL backtest when as_of_date is set (docs/stockpilot-gaps.md#3):
    every figure below is queried for the actual historical window ending
    at as_of_date, via StockPilot's date-range-capable analytics
    endpoints -- these query immutable sales_transactions, so a past
    as_of_date genuinely changes which data comes back, unlike
    inventory-health's label-only backtest mode.
    """
    started = time.monotonic()
    thresholds = get_thresholds_config().workflows
    days = period_days or thresholds.business_review_period_days

    period2_end = as_of_date or date.today()
    period2_start = period2_end - timedelta(days=days - 1)
    period1_end = period2_start - timedelta(days=1)
    period1_start = period1_end - timedelta(days=days - 1)

    execution_id = _new_execution(session_factory, "[workflow] business-review")
    agents = build_agents(client, session_factory, execution_id)
    tools = {
        tool.name: tool for tool in build_stockpilot_tools(client, session_factory, execution_id)
    }
    tool_names = set(tools)
    before_ids = _owned_tool_call_ids(session_factory, execution_id, tool_names)

    comparison = tools["get_period_comparison"].invoke(
        {
            "period1_start": period1_start,
            "period1_end": period1_end,
            "period2_start": period2_start,
            "period2_end": period2_end,
        }
    )
    top_products = tools["get_top_products"].invoke(
        {"metric": "revenue", "limit": 10, "start_date": period2_start, "end_date": period2_end}
    )
    bottom_products = tools["get_bottom_products"].invoke(
        {"metric": "revenue", "limit": 10, "start_date": period2_start, "end_date": period2_end}
    )
    category_rows = tools["get_revenue"].invoke(
        {"group_by": "category", "start_date": period2_start, "end_date": period2_end}
    )
    valuation = tools["get_inventory_valuation"].invoke({})
    dead_stock_capital = compute_dead_stock_capital(
        dead_stock_tool=tools["get_dead_stock"],
        get_product_tool=tools["get_product"],
        days=90,
        limit=thresholds.dead_stock_lookup_limit,
    )

    margin_delta_pct = (
        comparison.period2_margin - comparison.period1_margin
        if comparison.period2_margin is not None and comparison.period1_margin is not None
        else None
    )

    dimension_deltas = {
        "revenue": comparison.revenue_delta_pct,
        "gross profit": comparison.gross_profit_delta_pct,
        "margin": margin_delta_pct,
    }
    known_deltas = {name: value for name, value in dimension_deltas.items() if value is not None}
    largest_dimension = max(known_deltas, key=lambda name: abs(known_deltas[name]), default=None)

    new_ids = [
        tool_call_id
        for tool_call_id in _owned_tool_call_ids(session_factory, execution_id, tool_names)
        if tool_call_id not in before_ids
    ]

    prompt = (
        f"Business review for {period2_start.isoformat()} to {period2_end.isoformat()}, vs prior "
        f"period {period1_start.isoformat()} to {period1_end.isoformat()}.\n"
        f"Revenue: {comparison.period2_revenue:.2f} "
        f"({_pct(comparison.revenue_delta_pct)} vs prior). "
        f"Gross profit: {comparison.period2_gross_profit:.2f} "
        f"({_pct(comparison.gross_profit_delta_pct)} vs prior). "
        f"Margin: {_fmt_optional(comparison.period2_margin)} "
        f"({_fmt_optional(margin_delta_pct)} points vs prior).\n"
        f"Total inventory value: {valuation.total_inventory_value:.2f}. "
        f"Dead-stock capital: {dead_stock_capital:.2f}.\n"
        f"Top products by revenue: "
        f"{', '.join(f'{p.sku} ({p.revenue:.2f})' for p in top_products) or 'none'}.\n"
        f"Bottom products by revenue: "
        f"{', '.join(f'{p.sku} ({p.revenue:.2f})' for p in bottom_products) or 'none'}.\n"
        f"Category revenue: "
        f"{', '.join(f'{c.period} ({c.revenue:.2f})' for c in category_rows) or 'none'}.\n\n"
        + (
            f"The single largest change was in {largest_dimension} "
            f"({_pct(known_deltas[largest_dimension])}). Explain its likely driver using only "
            "the category/product figures above -- never a change you haven't confirmed "
            "happened in this data. "
            if largest_dimension is not None
            else "No period-over-period comparison figure was available to identify a largest "
            "change. Say so plainly. "
        )
        + "Then write a short overall `summary`."
    )
    draft = build_report(
        agents["report"],
        "performance",
        prompt,
        session_factory=session_factory,
        execution_id=execution_id,
    )
    assert isinstance(draft, PerformanceReport)

    report = draft.model_copy(
        update={
            "title": "Business Review",
            "period_start": period2_start.isoformat(),
            "period_end": period2_end.isoformat(),
            "revenue": comparison.period2_revenue,
            "gross_profit": comparison.period2_gross_profit,
            "margin": comparison.period2_margin,
            "revenue_delta_pct": comparison.revenue_delta_pct,
            "gross_profit_delta_pct": comparison.gross_profit_delta_pct,
            "margin_delta_pct": margin_delta_pct,
            "total_inventory_value": valuation.total_inventory_value,
            "dead_stock_capital": dead_stock_capital,
            "top_products": [
                ProductPerformanceEntry(
                    sku=p.sku,
                    description=p.description,
                    revenue=p.revenue,
                    units=p.units,
                    margin=p.margin,
                )
                for p in top_products
            ],
            "bottom_products": [
                ProductPerformanceEntry(
                    sku=p.sku,
                    description=p.description,
                    revenue=p.revenue,
                    units=p.units,
                    margin=p.margin,
                )
                for p in bottom_products
            ],
            "category_performance": [
                CategoryPerformance(category=c.period, revenue=c.revenue, units=c.units)
                for c in category_rows
            ],
            "evidence": [str(tool_call_id) for tool_call_id in new_ids],
        }
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    cost_tokens = _sum_agent_step_tokens(session_factory, execution_id)
    inputs: dict[str, object] = {
        "as_of_date": as_of_date.isoformat() if as_of_date else None,
        "period_days": days,
    }
    report_id = persist_report(
        session_factory,
        execution_id,
        report,
        inputs=inputs,
        duration_ms=duration_ms,
        cost_tokens=cost_tokens,
        as_of_date=as_of_date,
    )

    markdown = render_report_markdown(report, as_of_date=as_of_date)
    _complete_execution(session_factory, execution_id, report.summary, cost_tokens)

    return BusinessReviewResult(
        execution_id=execution_id,
        report_id=report_id,
        report=report,
        markdown=markdown,
        as_of_date=as_of_date,
        backtest=as_of_date is not None,
    )


def _pct(value: float | None) -> str:
    return f"{value:+.2f}%" if value is not None else "unavailable"


def _fmt_optional(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "unavailable"
