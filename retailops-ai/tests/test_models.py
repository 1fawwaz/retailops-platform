import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from orchestration.models import (
    AgentStep,
    Conversation,
    EvalRun,
    Execution,
    Message,
    Recommendation,
    Report,
    ToolCall,
)


def test_all_eight_memory_tables_exist(db_session: Session) -> None:
    from orchestration.models.base import Base

    assert set(Base.metadata.tables) == {
        "conversations",
        "messages",
        "executions",
        "agent_steps",
        "tool_calls",
        "reports",
        "recommendations",
        "eval_runs",
    }


def test_full_trace_chain_inserts_and_links_correctly(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.flush()

    execution = Execution(
        conversation_id=conversation.id,
        query="Which products should I reorder today?",
        status="running",
        plan={"steps": ["inventory", "forecast"]},
        budgets={"max_tool_iterations": 12},
    )
    db_session.add(execution)
    db_session.flush()

    user_message = Message(conversation_id=conversation.id, role="user", content="reorder?")
    db_session.add(user_message)
    db_session.flush()

    agent_step = AgentStep(
        execution_id=execution.id,
        agent_name="planner",
        iteration=1,
        output={
            "sufficient": False,
            "missing": ["supplier lead time for 3 SKUs"],
            "next_action": "forecast agent, targeted retrieval",
            "iteration": 1,
        },
        model_id="gemini-3.1-pro",
        prompt_version_hash="abc123",
    )
    db_session.add(agent_step)
    db_session.flush()

    tool_call = ToolCall(
        execution_id=execution.id,
        agent_step_id=agent_step.id,
        tool_name="get_stock",
        args={"sku": "85048"},
        raw_response={"quantity_on_hand": 96},
        provenance_map={"quantity_on_hand": "derived"},
        latency_ms=120,
        status="success",
    )
    db_session.add(tool_call)
    db_session.flush()

    report = Report(
        execution_id=execution.id,
        report_type="reorder",
        outputs={"skus": ["85048"]},
        markdown="# Reorder report",
    )
    db_session.add(report)
    db_session.flush()

    recommendation = Recommendation(
        execution_id=execution.id,
        report_id=report.id,
        sku="85048",
        action="Reorder 200 units",
        priority="high",
        reason="Stock below reorder point with rising demand.",
        revenue_at_risk=450.00,
        inventory_cost=210.00,
        confidence=0.82,
        risk_if_ignored="Stockout within 5 days.",
        evidence=[str(tool_call.tool_call_id)],
    )
    db_session.add(recommendation)
    db_session.flush()

    assistant_message = Message(
        conversation_id=conversation.id,
        execution_id=execution.id,
        role="assistant",
        content="You should reorder 85048.",
    )
    db_session.add(assistant_message)
    db_session.commit()

    fetched_user_message = db_session.get(Message, user_message.id)
    fetched_assistant_message = db_session.get(Message, assistant_message.id)
    fetched_tool_call = db_session.get(ToolCall, tool_call.tool_call_id)
    fetched_recommendation = db_session.get(Recommendation, recommendation.id)
    assert fetched_user_message is not None
    assert fetched_assistant_message is not None
    assert fetched_tool_call is not None
    assert fetched_recommendation is not None

    assert fetched_user_message.execution_id is None
    assert fetched_assistant_message.execution_id == execution.id
    assert fetched_tool_call.agent_step_id == agent_step.id
    assert fetched_recommendation.status == "pending"
    assert fetched_recommendation.evidence == [str(tool_call.tool_call_id)]


def test_recommendation_action_updates_status_and_records_decision(db_session: Session) -> None:
    execution = Execution(query="q", status="completed")
    db_session.add(execution)
    db_session.flush()

    recommendation = Recommendation(
        execution_id=execution.id,
        action="Reorder",
        priority="medium",
        reason="r",
        revenue_at_risk=1.0,
        inventory_cost=1.0,
        confidence=0.5,
        risk_if_ignored="r",
        evidence=[],
    )
    db_session.add(recommendation)
    db_session.commit()

    recommendation.status = "accepted"
    recommendation.note = "Approved by ops manager."
    recommendation.decided_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.commit()

    refreshed = db_session.get(Recommendation, recommendation.id)
    assert refreshed is not None
    assert refreshed.status == "accepted"
    assert refreshed.note == "Approved by ops manager."
    assert refreshed.decided_at is not None


def test_eval_run_persists_scorer_fields(db_session: Session) -> None:
    execution = Execution(query="q", status="completed")
    db_session.add(execution)
    db_session.flush()

    eval_run = EvalRun(
        scenario_id="01-normal-operations",
        execution_id=execution.id,
        grounding_pct=100.0,
        factual_accuracy_pct=95.0,
        routing_correct=True,
        replan_correct=True,
        refusal_correct=True,
        cost_tokens=4200,
        latency_ms=3100,
        passed=True,
        is_baseline=True,
    )
    db_session.add(eval_run)
    db_session.commit()

    refreshed = db_session.get(EvalRun, eval_run.id)
    assert refreshed is not None
    assert refreshed.scenario_id == "01-normal-operations"
    assert refreshed.grounding_pct == 100.0
    assert refreshed.is_baseline is True


def test_message_role_check_constraint_rejects_invalid_role(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.flush()

    db_session.add(
        Message(conversation_id=conversation.id, role="system_prompt_injection", content="x")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_recommendation_priority_check_constraint_rejects_invalid_value(
    db_session: Session,
) -> None:
    execution = Execution(query="q", status="completed")
    db_session.add(execution)
    db_session.flush()

    db_session.add(
        Recommendation(
            execution_id=execution.id,
            action="a",
            priority="urgent!!!",
            reason="r",
            revenue_at_risk=1.0,
            inventory_cost=1.0,
            confidence=0.5,
            risk_if_ignored="r",
            evidence=[],
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_execution_status_check_constraint_rejects_invalid_value(db_session: Session) -> None:
    db_session.add(Execution(query="q", status="not-a-real-status"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_execution_id_is_a_uuid(db_session: Session) -> None:
    execution = Execution(query="q", status="running")
    db_session.add(execution)
    db_session.commit()

    assert isinstance(execution.id, uuid.UUID)
