"""Stage 4 Task 4.2: tests for the Report Agent's structured output
(agents/report.py) -- schema construction, the pure markdown renderer
(no LLM involved, so fully deterministic to test), and build_report()'s
dispatch through Agent.invoke_structured() (already tested generically
in tests/test_agent_base.py; this proves it works for these specific
schemas too).
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.base import Agent
from agents.report import (
    CategoryPerformance,
    DeadStockRow,
    HealthReport,
    LowStockItem,
    PerformanceReport,
    ProductPerformanceEntry,
    ReorderReport,
    ReorderReportItem,
    SlowMoverRow,
    build_report,
    persist_report,
    render_report_markdown,
)
from llm.providers.gemini import StructuredResult
from orchestration.models.agent_step import AgentStep
from orchestration.models.execution import Execution
from orchestration.models.report import Report as ReportRow
from prompts.loader import load_prompt


def _new_execution(db_session: Session) -> uuid.UUID:
    execution = Execution(query="test query", status="running")
    db_session.add(execution)
    db_session.commit()
    return execution.id


def _report_agent() -> Agent:
    return Agent(name="report", role="decision", prompt=load_prompt("report"))


# -- ReorderReport ------------------------------------------------------


def test_reorder_report_renders_a_markdown_table() -> None:
    report = ReorderReport(
        title="Reorder Report",
        items=[
            ReorderReportItem(
                sku="85048",
                description="Glass ball",
                quantity_on_hand=12,
                reorder_point=40,
                safety_stock=10,
                predicted_daily_demand=5.0,
                days_of_cover=2.4,
                reorder_by_days=-3.0,
                reorder_now=True,
                supplier_name="Acme Wholesale",
                lead_time_days=7,
            )
        ],
        summary="SKU 85048 is overdue for reorder.",
        evidence=["11111111-1111-1111-1111-111111111111"],
    )

    markdown = render_report_markdown(report)

    assert "# Reorder Report" in markdown
    assert "85048" in markdown
    assert "Acme Wholesale" in markdown
    assert "yes" in markdown  # reorder_now rendered as yes/no, not True/False
    assert "SKU 85048 is overdue for reorder." in markdown


def test_reorder_report_renders_none_for_empty_items() -> None:
    report = ReorderReport(title="Reorder Report", items=[], summary="Nothing needs reordering.")

    markdown = render_report_markdown(report)

    assert "_None._" in markdown
    assert "Nothing needs reordering." in markdown


def test_reorder_report_stamps_backtest_banner_when_as_of_date_is_set() -> None:
    report = ReorderReport(title="Reorder Report", items=[], summary="s")

    markdown = render_report_markdown(report, as_of_date=date(2011, 11, 12))

    assert "Historical simulation as of 2011-11-12. Not live monitoring." in markdown


def test_reorder_report_omits_backtest_banner_when_as_of_date_is_none() -> None:
    report = ReorderReport(title="Reorder Report", items=[], summary="s")

    markdown = render_report_markdown(report)

    assert "Historical simulation" not in markdown


# -- HealthReport ---------------------------------------------------------


def test_health_report_renders_all_three_tables() -> None:
    report = HealthReport(
        title="Inventory Health",
        total_inventory_value=125000.5,
        low_stock_items=[
            LowStockItem(sku="A", description="d", quantity_on_hand=5, reorder_point=40)
        ],
        dead_stock_items=[
            DeadStockRow(sku="B", description="d", quantity_on_hand=20, days_since_movement=120)
        ],
        slow_mover_items=[
            SlowMoverRow(sku="C", description="d", quantity_on_hand=15, avg_daily_demand=0.1)
        ],
        summary="Overall healthy, three SKUs need attention.",
    )

    markdown = render_report_markdown(report)

    assert "## Low stock" in markdown
    assert "## Dead stock" in markdown
    assert "## Slow movers" in markdown
    assert "125000.50" in markdown
    assert "Overall healthy, three SKUs need attention." in markdown


def test_health_report_handles_all_empty_lists() -> None:
    report = HealthReport(title="Inventory Health", summary="Nothing to flag.")

    markdown = render_report_markdown(report)

    assert markdown.count("_None._") == 3


# -- PerformanceReport -----------------------------------------------------


def test_performance_report_renders_products_and_categories() -> None:
    report = PerformanceReport(
        title="Business Review",
        period_start="2011-11-01",
        period_end="2011-11-30",
        revenue=50000.0,
        gross_profit=12000.0,
        margin=0.24,
        revenue_delta_pct=-8.5,
        gross_profit_delta_pct=-10.0,
        top_products=[ProductPerformanceEntry(sku="A", description="d", revenue=5000.0, units=100)],
        bottom_products=[ProductPerformanceEntry(sku="B", description="d", revenue=10.0, units=1)],
        category_performance=[CategoryPerformance(category="Toys", revenue=8000.0, units=200)],
        largest_change_driver="A seasonal dip in the Toys category drove most of the decline.",
        summary="Profit fell mainly due to the Toys category.",
    )

    markdown = render_report_markdown(report)

    assert "## Top products" in markdown
    assert "## Bottom products" in markdown
    assert "## Category performance" in markdown
    assert "Toys" in markdown
    assert "A seasonal dip in the Toys category drove most of the decline." in markdown
    assert "-8.50" in markdown


# -- build_report() ----------------------------------------------------


def test_build_report_dispatches_reorder_type_and_persists_the_step(
    db_session: Session,
) -> None:
    agent = _report_agent()
    execution_id = _new_execution(db_session)
    parsed = ReorderReport(title="Reorder Report", items=[], summary="s")
    fake_result: StructuredResult[ReorderReport] = StructuredResult(
        parsed=parsed,
        usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
        provider="gemini",
        model="gemini-3.1-pro-preview",
    )

    with patch("agents.base.generate_structured", return_value=fake_result) as mock_generate:
        result = build_report(
            agent,
            "reorder",
            "Build a reorder report.",
            session_factory=lambda: db_session,
            execution_id=execution_id,
        )

    assert result == parsed
    assert mock_generate.call_args.kwargs["response_schema"] is ReorderReport

    step = db_session.query(AgentStep).one()
    assert step.agent_name == "report"
    assert step.status == "completed"


@pytest.mark.parametrize(
    ("report_type", "schema"),
    [("reorder", ReorderReport), ("health", HealthReport), ("performance", PerformanceReport)],
)
def test_build_report_selects_the_matching_schema(
    db_session: Session, report_type: str, schema: type[BaseModel]
) -> None:
    agent = _report_agent()
    execution_id = _new_execution(db_session)
    captured: dict[str, object] = {}

    def fake_generate_structured(
        *, model: str, messages: list[object], response_schema: type[BaseModel]
    ) -> StructuredResult[BaseModel]:
        captured["schema"] = response_schema
        instance = (
            schema(title="t", items=[], summary="s")
            if schema is ReorderReport
            else schema(title="t", summary="s")
            if schema is HealthReport
            else schema(
                title="t",
                period_start="2011-01-01",
                period_end="2011-01-31",
                largest_change_driver="d",
                summary="s",
            )
        )
        return StructuredResult(
            parsed=instance,
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            provider="gemini",
            model=model,
        )

    with patch("agents.base.generate_structured", side_effect=fake_generate_structured):
        result = build_report(
            agent,
            report_type,  # type: ignore[arg-type]
            "prompt",
            session_factory=lambda: db_session,
            execution_id=execution_id,
        )

    assert captured["schema"] is schema
    assert isinstance(result, schema)


# -- persist_report() ---------------------------------------------------


def test_persist_report_writes_a_row_with_the_rendered_markdown(db_session: Session) -> None:
    execution_id = _new_execution(db_session)
    report = HealthReport(title="Inventory Health", summary="All clear.")

    report_id = persist_report(
        lambda: db_session,
        execution_id,
        report,
        inputs={"limit": 10},
        duration_ms=123,
        cost_tokens=45,
    )

    row = db_session.get(ReportRow, report_id)
    assert row is not None
    assert row.execution_id == execution_id
    assert row.report_type == "health"
    assert row.inputs == {"limit": 10}
    assert row.duration_ms == 123
    assert row.cost_tokens == 45
    assert row.as_of_date is None
    assert "# Inventory Health" in (row.markdown or "")
    assert row.outputs is not None
    assert row.outputs["summary"] == "All clear."


def test_persist_report_stamps_the_backtest_banner_when_as_of_date_is_set(
    db_session: Session,
) -> None:
    execution_id = _new_execution(db_session)
    report = PerformanceReport(
        title="Business Review",
        period_start="2011-11-01",
        period_end="2011-11-30",
        largest_change_driver="d",
        summary="s",
    )

    report_id = persist_report(
        lambda: db_session, execution_id, report, as_of_date=date(2011, 11, 30)
    )

    row = db_session.get(ReportRow, report_id)
    assert row is not None
    assert row.report_type == "performance"
    assert row.as_of_date == date(2011, 11, 30)
    assert "Historical simulation as of 2011-11-30" in (row.markdown or "")


def test_persist_report_recognizes_the_reorder_type(db_session: Session) -> None:
    execution_id = _new_execution(db_session)
    report = ReorderReport(title="Reorder Report", items=[], summary="Nothing to reorder.")

    report_id = persist_report(lambda: db_session, execution_id, report)

    row = db_session.get(ReportRow, report_id)
    assert row is not None
    assert row.report_type == "reorder"
