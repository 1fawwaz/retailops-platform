"""Stage 3 Task 3.4 milestone: a follow-up question that depends on the
previous turn answers correctly. Proved by asserting the SECOND turn's
Planner prompt genuinely contains the first turn's question and answer
-- proof memory actually reached the Planner, not just that rows exist
in the database.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agents.replan import ReplanJudgement
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.executor import run_execution
from orchestration.models import Base
from orchestration.models.conversation import Conversation
from orchestration.models.execution import Execution
from orchestration.models.message import Message
from prompts.loader import load_prompt

AGENT_NAMES = ("planner", "inventory", "forecast", "analytics", "report", "decision")


@pytest.fixture
def session_factory() -> Generator[Callable[[], Session]]:
    # Same rationale as tests/test_graph.py's fixture: run_execution runs
    # the real concurrent graph underneath, which needs genuine per-thread
    # connections (a temp file + WAL), not a single shared one.
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


def _client() -> StockPilotClient:
    return StockPilotClient(base_url="http://x", username="u", password="p")


def _ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text, usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    )


def _sufficient_judgement(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[ReplanJudgement]:
    return StructuredResult(
        parsed=ReplanJudgement(
            sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
        ),
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_run_execution_creates_a_conversation_and_persists_the_turn(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
    ):
        result = run_execution(
            "Which products are low on stock?", client=_client(), session_factory=session_factory
        )

    assert result["final_answer"] == "decision answer"
    assert result["conversation_id"] is not None

    session = session_factory()
    try:
        conversations = session.query(Conversation).all()
        messages = session.query(Message).order_by(Message.created_at).all()
        executions = session.query(Execution).all()
    finally:
        session.close()

    assert len(conversations) == 1
    assert conversations[0].id == result["conversation_id"]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Which products are low on stock?"),
        ("assistant", "decision answer"),
    ]
    assert len(executions) == 1
    execution = executions[0]
    assert execution.status == "completed"
    assert execution.final_answer == "decision answer"
    assert execution.plan == {"text": "planner answer"}
    assert execution.completed_at is not None
    assert execution.total_tokens is not None and execution.total_tokens > 0


def test_run_execution_follow_up_question_sees_the_previous_turn(
    session_factory: Callable[[], Session],
) -> None:
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}
    captured_planner_prompts: list[str] = []

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "planner":
            captured_planner_prompts.append(messages[1].content)
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
    ):
        first = run_execution(
            "Which products are low on stock?", client=_client(), session_factory=session_factory
        )
        conversation_id = first["conversation_id"]
        second = run_execution(
            "And what does forecasting say about those same products?",
            client=_client(),
            session_factory=session_factory,
            conversation_id=conversation_id,
        )

    assert len(captured_planner_prompts) == 2
    # First turn: nothing precedes it, so no memory context is injected.
    assert "Conversation history" not in captured_planner_prompts[0]
    # Second turn: the Planner's own prompt must be informed by what was
    # asked and answered in the first turn -- the actual milestone.
    assert "Which products are low on stock?" in captured_planner_prompts[1]
    assert "decision answer" in captured_planner_prompts[1]
    assert "And what does forecasting say" in captured_planner_prompts[1]

    assert second["conversation_id"] == conversation_id
    assert second["final_answer"] == "decision answer"

    session = session_factory()
    try:
        messages = (
            session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        executions = (
            session.query(Execution).filter(Execution.conversation_id == conversation_id).all()
        )
    finally:
        session.close()

    assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]
    assert len(executions) == 2
    assert all(e.status == "completed" for e in executions)


def test_run_execution_persists_citation_failures_on_the_execution_row(
    session_factory: Callable[[], Session],
) -> None:
    """Task 3.5: the Validator has no agent_steps row of its own (it
    isn't one of the six named agents), so its full history must live
    somewhere durable -- Execution.errors is where run_execution puts it.
    """
    prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}
    decision_calls = {"count": 0}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = prompt_to_name[messages[0].content]
        if name == "decision":
            decision_calls["count"] += 1
            return _ai_message(f"Revenue at risk is ${decision_calls['count'] * 1000}.")
        return _ai_message(f"{name} answer")

    with (
        patch("agents.base.generate", side_effect=fake_generate),
        patch("agents.base.generate_structured", side_effect=_sufficient_judgement),
    ):
        result = run_execution(
            "How much revenue is at risk?", client=_client(), session_factory=session_factory
        )

    final_answer = result["final_answer"]
    assert final_answer is not None
    assert final_answer.startswith("INSUFFICIENT_DATA")

    session = session_factory()
    try:
        execution = session.query(Execution).one()
    finally:
        session.close()

    assert execution.status == "completed"
    assert execution.final_answer is not None and execution.final_answer.startswith(
        "INSUFFICIENT_DATA"
    )
    assert execution.errors is not None
    citation_failures = execution.errors["citation_failures"]
    assert len(citation_failures) == 2
    assert all(not attempt["passed"] for attempt in citation_failures)
