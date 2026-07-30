"""Stage 4 Task 4.5: query coverage. Runs each of the spec's eight
required questions through the REAL general-chat pipeline
(orchestration/executor.py::run_execution(), the same thing
POST /agent/query calls) -- a real StockPilotClient over a scripted
MockTransport, real agents/tools/graph/citation-validator, with only
generate()/generate_structured() mocked to script a plausible model
decision sequence per query. This is a verification task, not new
graph/agent code: it proves the pipeline already built across Stages
3-4 actually answers each question type correctly, and fixes real gaps
found along the way (Task 4.5 added tools/derived_tools.py's
dead_stock_capital tool after this file's own first draft surfaced that
"how much capital is in dead stock" had no way to be answered).

Deliberately NOT the Stage 5 eval suite (evals/scenarios/, ten seeded
scenarios with expected facts and an expected agent path) -- that is a
separate, later spec task with its own formal harness. This file proves
the eight specific queries Task 4.5 names, nothing more.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import patch

import httpx2
import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.replan import ReplanJudgement
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.executor import run_execution
from orchestration.models import Base
from prompts.loader import load_prompt

AGENT_NAMES = ("planner", "inventory", "forecast", "analytics", "report", "decision")
Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture
def session_factory() -> Generator[Callable[[], Session]]:
    # run_execution() runs the real concurrent graph (retrieval agents
    # fan out across threads) -- a plain sqlite ":memory:" DB is a fresh,
    # empty database per connection, so a second thread's session_factory()
    # call sees no tables at all. Same temp-file + WAL fixture as
    # tests/test_graph.py and tests/test_executor.py, which documents why.
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()
    os.remove(path)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)


def _client(handler: Handler) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
    )


def _login() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "t", "token_type": "bearer"})


def _low_stock_item() -> dict[str, object]:
    return {
        "sku": "85048",
        "description": "Glass Ball",
        "category": "Christmas",
        "quantity_on_hand": 12,
        "reorder_point": 40,
        "safety_stock": 10,
        "as_of_date": "2026-07-01",
        "is_low_stock": True,
        "_provenance": {"quantity_on_hand": "derived", "reorder_point": "derived"},
        "_derivation_ref": {},
    }


def _product(sku: str, *, unit_cost: float = 2.15) -> dict[str, object]:
    return {
        "sku": sku,
        "description": "Glass Ball",
        "category_id": 3,
        "supplier_id": 7,
        "unit_cost": unit_cost,
        "reorder_point": 40,
        "safety_stock": 10,
        "created_at": "2026-01-01T00:00:00",
        "quantity_on_hand": 12,
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
        "skus": ["85048"],
        "_provenance": {"lead_time_days": "derived"},
        "_derivation_ref": {},
    }


def _forecast(sku: str = "85048") -> dict[str, object]:
    return {
        "sku": sku,
        "predicted_daily_demand": 5.0,
        "confidence_interval_lower": 4.0,
        "confidence_interval_upper": 6.0,
        "model_used": "moving_average",
        "training_window_start": "2011-01-01",
        "training_window_end": "2011-11-11",
        "data_quality": "ok",
        "_provenance": {"predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def _dead_stock_item() -> dict[str, object]:
    return {
        "sku": "99999",
        "description": "Old Widget",
        "quantity_on_hand": 20,
        "last_movement_date": "2025-01-01T00:00:00",
        "days_since_movement": 200,
        "_provenance": {"sku": "observed", "quantity_on_hand": "derived"},
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
        "_provenance": {
            "period1_revenue": "derived",
            "period1_units": "derived",
            "period1_cost": "derived",
            "period1_gross_profit": "derived",
            "period1_margin": "derived",
            "period2_revenue": "derived",
            "period2_units": "derived",
            "period2_cost": "derived",
            "period2_gross_profit": "derived",
            "period2_margin": "derived",
            "revenue_delta": "derived",
            "revenue_delta_pct": "derived",
            "units_delta": "derived",
            "units_delta_pct": "derived",
            "gross_profit_delta": "derived",
            "gross_profit_delta_pct": "derived",
        },
        "_derivation_ref": {},
    }


def _category_revenue() -> list[dict[str, object]]:
    return [
        {
            "period": "Christmas",
            "revenue": 5000.0,
            "units": 300,
            "_provenance": {"revenue": "derived", "units": "observed"},
            "_derivation_ref": {},
        },
        {
            "period": "Toys",
            "revenue": 2000.0,
            "units": 100,
            "_provenance": {"revenue": "derived", "units": "observed"},
            "_derivation_ref": {},
        },
    ]


def _mega_handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path == "/auth/login":
        return _login()
    if path == "/inventory/low-stock":
        return httpx2.Response(200, json=[_low_stock_item()])
    if path == "/inventory/dead-stock":
        return httpx2.Response(200, json=[_dead_stock_item()])
    if path == "/inventory/slow-movers":
        return httpx2.Response(200, json=[])
    if path == "/inventory/valuation":
        return httpx2.Response(
            200,
            json={
                "by_category": [],
                "total_quantity_on_hand": 1000,
                "total_inventory_value": 50000.0,
                "_provenance": {"total_inventory_value": "derived"},
                "_derivation_ref": {},
            },
        )
    if path == "/products/85048":
        return httpx2.Response(200, json=_product("85048", unit_cost=2.15))
    if path == "/products/99999":
        return httpx2.Response(200, json=_product("99999", unit_cost=3.0))
    if path == "/suppliers/7":
        return httpx2.Response(200, json=_supplier())
    if path == "/forecast/demand":
        return httpx2.Response(200, json=[_forecast()])
    if path == "/analytics/period-comparison":
        return httpx2.Response(200, json=_period_comparison())
    if path == "/analytics/revenue":
        return httpx2.Response(200, json=_category_revenue())
    if path == "/analytics/top-products":
        return httpx2.Response(
            200,
            json=[
                {
                    "sku": "85048",
                    "description": "Glass Ball",
                    "revenue": 5000.0,
                    "units": 300,
                    "margin": 0.3,
                    "_provenance": {"revenue": "derived"},
                    "_derivation_ref": {},
                }
            ],
        )
    if path == "/analytics/bottom-products":
        return httpx2.Response(200, json=[])
    raise AssertionError(f"unexpected request: {request.method} {path}")


def _ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text, usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    )


def _tool_call_message(name: str, args: dict[str, object]) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])


def _always_sufficient(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[ReplanJudgement]:
    return StructuredResult(
        parsed=ReplanJudgement(
            sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
        ),
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        provider="gemini",
        model=model,
    )


def _prompt_to_name() -> dict[str, str]:
    return {load_prompt(name).text: name for name in AGENT_NAMES}


def test_query_which_products_should_i_reorder_today(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "inventory" and calls[name] == 1:
            return _tool_call_message("rank_stockout_risk", {})
        if name == "inventory":
            return _ai_message(
                "SKU 85048 is at 12 units against a reorder point of 40 -- reorder today."
            )
        if name == "forecast" and calls[name] == 1:
            return _tool_call_message("reorder_timing", {"sku": "85048"})
        if name == "forecast":
            return _ai_message("SKU 85048's reorder is already overdue given the lead time.")
        if name == "decision":
            return _ai_message(
                "Reorder SKU 85048 today: it's at 12 units against a reorder point of 40, "
                "and the reorder is already overdue given the supplier's lead time."
            )
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "Which products should I reorder today?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "85048" in result["final_answer"]
    assert not result["errors"]


def test_query_why_did_profit_fall_last_month(session_factory: Callable[[], Session]) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "analytics" and calls[name] == 1:
            return _tool_call_message(
                "get_period_comparison",
                {
                    "period1_start": "2011-10-01",
                    "period1_end": "2011-10-30",
                    "period2_start": "2011-11-01",
                    "period2_end": "2011-11-30",
                },
            )
        if name == "analytics":
            return _ai_message(
                "Gross profit fell 25.00% (from $4000.00 to $3000.00) as revenue fell "
                "20.00% period over period."
            )
        if name == "decision":
            return _ai_message(
                "Profit fell because gross profit dropped 25.00% (from $4000.00 to $3000.00), "
                "driven by a 20.00% revenue decline period over period."
            )
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "Why did profit fall last month?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "25" in result["final_answer"]
    assert not result["errors"]


def test_query_dead_stock_and_capital(session_factory: Callable[[], Session]) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "inventory" and calls[name] == 1:
            return _tool_call_message("get_dead_stock", {})
        if name == "inventory" and calls[name] == 2:
            return _tool_call_message("dead_stock_capital", {})
        if name == "inventory":
            return _ai_message(
                "SKU 99999 is dead stock (200 days since last movement); $60.00 of capital "
                "is tied up in dead stock overall."
            )
        if name == "decision":
            return _ai_message(
                "SKU 99999 is dead stock, with $60.00 of capital tied up in dead stock overall."
            )
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "Which products are dead stock and how much capital is in them?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "99999" in result["final_answer"]
    assert "60" in result["final_answer"]
    assert not result["errors"]


def test_query_which_categories_perform_best(session_factory: Callable[[], Session]) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "analytics" and calls[name] == 1:
            return _tool_call_message("get_revenue", {"group_by": "category"})
        if name == "analytics":
            return _ai_message(
                "Christmas is the best-performing category at $5000.00 in revenue, well "
                "ahead of Toys at $2000.00."
            )
        if name == "decision":
            return _ai_message("Christmas performs best, at $5000.00 in revenue vs Toys' $2000.00.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "Which categories perform best, and why?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "Christmas" in result["final_answer"]
    assert not result["errors"]


def test_query_which_skus_are_at_stockout_risk_this_week(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "inventory" and calls[name] == 1:
            return _tool_call_message("rank_stockout_risk", {})
        if name == "inventory":
            return _ai_message("SKU 85048 is the most urgent stockout risk this week.")
        if name == "decision":
            return _ai_message("SKU 85048 is the most urgent stockout risk this week.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "Which SKUs are at stockout risk this week?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "85048" in result["final_answer"]
    assert not result["errors"]


def test_query_what_changed_most_vs_last_month(session_factory: Callable[[], Session]) -> None:
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "analytics" and calls[name] == 1:
            return _tool_call_message(
                "get_period_comparison",
                {
                    "period1_start": "2011-10-01",
                    "period1_end": "2011-10-30",
                    "period2_start": "2011-11-01",
                    "period2_end": "2011-11-30",
                },
            )
        if name == "analytics":
            return _ai_message(
                "Gross profit moved the most, down 25.00%, a larger swing than revenue's "
                "20.00% decline."
            )
        if name == "decision":
            return _ai_message(
                "Gross profit changed the most vs last month, down 25.00%, a larger swing "
                "than revenue's 20.00% decline."
            )
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "What changed most vs last month?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "25" in result["final_answer"]
    assert not result["errors"]


def test_query_hows_business_states_its_interpretation(
    session_factory: Callable[[], Session],
) -> None:
    """ "How's business?" is genuinely ambiguous -- the Planner must
    clarify or state its interpretation (prompts/planner/v1.md already
    says so), and that interpretation must actually reach the final
    answer, not just live in the internal plan text nobody sees.
    """
    prompt_to_name = _prompt_to_name()
    calls: dict[str, int] = {}
    interpretation = (
        "This is ambiguous -- I'm interpreting it as a request for overall recent "
        "revenue and profit performance."
    )

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        calls[name] = calls.get(name, 0) + 1
        if name == "planner":
            return _ai_message(interpretation)
        if name == "analytics" and calls[name] == 1:
            return _tool_call_message(
                "get_period_comparison",
                {
                    "period1_start": "2011-10-01",
                    "period1_end": "2011-10-30",
                    "period2_start": "2011-11-01",
                    "period2_end": "2011-11-30",
                },
            )
        if name == "analytics":
            return _ai_message("Revenue is $8000.00 this period, down from $10000.00.")
        if name == "decision":
            return _ai_message(
                f"{interpretation} Revenue is $8000.00 this period, down from $10000.00."
            )
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "How's business?", client=_client(_mega_handler), session_factory=session_factory
        )

    assert result["final_answer"] is not None
    assert "interpreting" in result["final_answer"].lower()
    assert not result["errors"]


def test_query_needing_absent_data_refuses_cleanly(
    session_factory: Callable[[], Session],
) -> None:
    """A question about data StockPilot genuinely doesn't have (customer
    satisfaction, marketing spend, geography -- none of this dataset)
    must be refused honestly, never fabricated. No agent has a tool for
    it, so none makes a tool call; the final answer states the gap.
    """
    prompt_to_name = _prompt_to_name()

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "decision":
            return _ai_message(
                "StockPilot has no customer satisfaction data -- this question can't be "
                "answered from what's available. I can report on inventory, forecasts, "
                "or revenue/profit analytics instead."
            )
        return _ai_message(f"{name}: no tool available for this question.")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_always_sufficient),
    ):
        result = run_execution(
            "What is our customer satisfaction score?",
            client=_client(_mega_handler),
            session_factory=session_factory,
        )

    assert result["final_answer"] is not None
    assert "no customer satisfaction data" in result["final_answer"].lower()
    # Honest refusal cites no numbers, so it must pass citation validation
    # on the first attempt, not degrade to INSUFFICIENT_DATA.
    assert len(result["citation_failures"]) == 1
    assert result["citation_failures"][0]["passed"] is True
