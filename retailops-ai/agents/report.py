"""Stage 4 Task 4.2: the Report Agent's structured output. Per CLAUDE.md's
"structured objects, not LLM prose" directive and prompts/report/v1.md's
own framing (written back in Task 3.1 -- "the structure and its
rendering to markdown is the deliverable; you are not writing an
essay"): the Report Agent populates one of three typed Pydantic schemas
via Agent.invoke_structured() from already-gathered evidence, never free
text, and the markdown it's "rendered to" (render_report_markdown,
below) is produced deterministically by Python, not written by the
model. Only individual text fields inside the structure (`summary` /
`largest_change_driver`) are LLM-authored, embedded verbatim into an
otherwise machine-generated document.

Every numeric field here is meant to be COPIED from a real tool result
already in this execution's evidence, not computed -- unlike Task 4.3's
Decision Engine (which will compute revenue_at_risk/inventory_cost/
confidence/priority in Python and give the LLM zero numbers to write),
the Report Agent is allowed to transcribe numbers into a structured
shape, the same latitude prompts/report/v1.md already granted it before
this task existed. Each report's `evidence` field (a list of
tool_call_id strings) is how a transcribed number stays traceable,
mirroring the shape the spec gives Task 4.3's own Recommendation.evidence.

Fields are deliberately limited to what an existing tool already returns
(tools/stockpilot_tools.py's 18 endpoints, tools/derived_tools.py's 3
derived ones) -- e.g. no "recommended_order_qty" on ReorderReport or
"dead_stock_capital" on HealthReport, since nothing in the codebase
computes either yet and inventing a formula here would be exactly the
kind of fabricated business value CLAUDE.md section 11 says to stop and
flag rather than build.

Not yet wired into the default /agent/query graph path, which still
uses the Report Agent's original free-text mode
(orchestration/graph.py's _make_synthesis_node via Agent.invoke()) for
general ad-hoc questions -- deciding which of these three report types
fits an arbitrary question isn't something this task's spec text asks
for. Task 4.4's goal-driven workflow endpoints are what will call
build_report() with an already-known report_type (one per endpoint), not
a runtime classification invented for this task.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.base import Agent

ReportType = Literal["reorder", "health", "performance"]


# -- Reorder -----------------------------------------------------------------


class ReorderReportItem(BaseModel):
    sku: str
    description: str | None = None
    quantity_on_hand: int
    reorder_point: int | None = None
    safety_stock: int | None = None
    predicted_daily_demand: float | None = None
    days_of_cover: float | None = None
    reorder_by_days: float | None = None
    reorder_now: bool | None = None
    supplier_name: str | None = None
    lead_time_days: int | None = None


class ReorderReport(BaseModel):
    title: str
    items: list[ReorderReportItem] = Field(default_factory=list)
    summary: str
    evidence: list[str] = Field(
        default_factory=list, description="tool_call_id values backing this report's numbers."
    )


# -- Health --------------------------------------------------------------


class LowStockItem(BaseModel):
    sku: str
    description: str | None = None
    quantity_on_hand: int
    reorder_point: int | None = None


class DeadStockRow(BaseModel):
    sku: str
    description: str | None = None
    quantity_on_hand: int
    days_since_movement: int | None = None


class SlowMoverRow(BaseModel):
    sku: str
    description: str | None = None
    quantity_on_hand: int
    avg_daily_demand: float


class HealthReport(BaseModel):
    title: str
    total_inventory_value: float | None = None
    low_stock_items: list[LowStockItem] = Field(default_factory=list)
    dead_stock_items: list[DeadStockRow] = Field(default_factory=list)
    slow_mover_items: list[SlowMoverRow] = Field(default_factory=list)
    summary: str
    evidence: list[str] = Field(default_factory=list)


# -- Performance ---------------------------------------------------------


class ProductPerformanceEntry(BaseModel):
    sku: str
    description: str | None = None
    revenue: float
    units: int
    margin: float | None = None


class CategoryPerformance(BaseModel):
    category: str | None = None
    revenue: float
    units: int


class PerformanceReport(BaseModel):
    title: str
    period_start: str
    period_end: str
    revenue: float | None = None
    gross_profit: float | None = None
    margin: float | None = None
    revenue_delta_pct: float | None = None
    gross_profit_delta_pct: float | None = None
    top_products: list[ProductPerformanceEntry] = Field(default_factory=list)
    bottom_products: list[ProductPerformanceEntry] = Field(default_factory=list)
    category_performance: list[CategoryPerformance] = Field(default_factory=list)
    largest_change_driver: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


Report = ReorderReport | HealthReport | PerformanceReport


def build_report(
    agent: Agent,
    report_type: ReportType,
    prompt: str,
    *,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    iteration: int = 1,
) -> Report:
    """Populates the schema for `report_type` via Agent.invoke_structured()
    -- the same tool-less structured-output path Task 3.3 built for the
    Planner's replan judgement, reused here for a different schema.
    Branches explicitly per type rather than a dict-of-classes lookup so
    each call site's `response_schema` argument stays concretely typed
    for invoke_structured's own generic signature.
    """
    if report_type == "reorder":
        return agent.invoke_structured(
            prompt,
            ReorderReport,
            session_factory=session_factory,
            execution_id=execution_id,
            iteration=iteration,
        )
    if report_type == "health":
        return agent.invoke_structured(
            prompt,
            HealthReport,
            session_factory=session_factory,
            execution_id=execution_id,
            iteration=iteration,
        )
    return agent.invoke_structured(
        prompt,
        PerformanceReport,
        session_factory=session_factory,
        execution_id=execution_id,
        iteration=iteration,
    )


# -- Markdown rendering (pure, deterministic -- no LLM involved) -------------


def _fmt(value: float | int | bool | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_None._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _backtest_banner(as_of_date: date | None) -> str:
    if as_of_date is None:
        return ""
    return f"> **Historical simulation as of {as_of_date.isoformat()}. Not live monitoring.**\n\n"


def _render_reorder_report(report: ReorderReport, as_of_date: date | None) -> str:
    headers = [
        "SKU",
        "Description",
        "On hand",
        "Reorder pt",
        "Days of cover",
        "Reorder by (days)",
        "Reorder now",
        "Supplier",
        "Lead time",
    ]
    rows = [
        [
            item.sku,
            item.description or "—",
            _fmt(item.quantity_on_hand),
            _fmt(item.reorder_point),
            _fmt(item.days_of_cover),
            _fmt(item.reorder_by_days),
            _fmt(item.reorder_now),
            item.supplier_name or "—",
            _fmt(item.lead_time_days),
        ]
        for item in report.items
    ]
    return (
        f"# {report.title}\n\n"
        f"{_backtest_banner(as_of_date)}"
        f"{_table(headers, rows)}\n"
        f"{report.summary}\n"
    )


def _render_health_report(report: HealthReport, as_of_date: date | None) -> str:
    low_stock_rows = [
        [item.sku, item.description or "—", _fmt(item.quantity_on_hand), _fmt(item.reorder_point)]
        for item in report.low_stock_items
    ]
    dead_stock_rows = [
        [
            item.sku,
            item.description or "—",
            _fmt(item.quantity_on_hand),
            _fmt(item.days_since_movement),
        ]
        for item in report.dead_stock_items
    ]
    slow_mover_rows = [
        [
            item.sku,
            item.description or "—",
            _fmt(item.quantity_on_hand),
            _fmt(item.avg_daily_demand),
        ]
        for item in report.slow_mover_items
    ]
    stock_headers = ["SKU", "Description", "On hand", "Reorder pt"]
    dead_headers = ["SKU", "Description", "On hand", "Days since movement"]
    slow_headers = ["SKU", "Description", "On hand", "Avg daily demand"]
    return (
        f"# {report.title}\n\n"
        f"{_backtest_banner(as_of_date)}"
        f"**Total inventory value:** {_fmt(report.total_inventory_value)}\n\n"
        f"## Low stock\n\n{_table(stock_headers, low_stock_rows)}\n"
        f"## Dead stock\n\n{_table(dead_headers, dead_stock_rows)}\n"
        f"## Slow movers\n\n{_table(slow_headers, slow_mover_rows)}\n"
        f"{report.summary}\n"
    )


def _render_performance_report(report: PerformanceReport, as_of_date: date | None) -> str:
    product_headers = ["SKU", "Description", "Revenue", "Units", "Margin"]
    top_rows = [
        [p.sku, p.description or "—", _fmt(p.revenue), _fmt(p.units), _fmt(p.margin)]
        for p in report.top_products
    ]
    bottom_rows = [
        [p.sku, p.description or "—", _fmt(p.revenue), _fmt(p.units), _fmt(p.margin)]
        for p in report.bottom_products
    ]
    category_rows = [
        [c.category or "—", _fmt(c.revenue), _fmt(c.units)] for c in report.category_performance
    ]
    return (
        f"# {report.title}\n\n"
        f"{_backtest_banner(as_of_date)}"
        f"**Period:** {report.period_start} to {report.period_end}\n\n"
        f"**Revenue:** {_fmt(report.revenue)} ({_fmt(report.revenue_delta_pct)}% vs prior)\n\n"
        f"**Gross profit:** {_fmt(report.gross_profit)} "
        f"({_fmt(report.gross_profit_delta_pct)}% vs prior)\n\n"
        f"**Margin:** {_fmt(report.margin)}\n\n"
        f"## Top products\n\n{_table(product_headers, top_rows)}\n"
        f"## Bottom products\n\n{_table(product_headers, bottom_rows)}\n"
        f"## Category performance\n\n"
        f"{_table(['Category', 'Revenue', 'Units'], category_rows)}\n"
        f"## What changed most\n\n{report.largest_change_driver}\n\n"
        f"{report.summary}\n"
    )


def render_report_markdown(report: Report, *, as_of_date: date | None = None) -> str:
    if isinstance(report, ReorderReport):
        return _render_reorder_report(report, as_of_date)
    if isinstance(report, HealthReport):
        return _render_health_report(report, as_of_date)
    return _render_performance_report(report, as_of_date)
