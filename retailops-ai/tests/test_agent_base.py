import uuid
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.base import Agent, build_agents
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.models.agent_step import AgentStep
from orchestration.models.execution import Execution
from prompts.loader import load_prompt


def _new_execution(db_session: Session) -> uuid.UUID:
    execution = Execution(query="test query", status="running")
    db_session.add(execution)
    db_session.commit()
    return execution.id


class GetWeatherArgs(BaseModel):
    city: str = Field(description="City name")


def _weather_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda city: f"sunny in {city}",
        name="get_weather",
        description="Get the weather for a city.",
        args_schema=GetWeatherArgs,
    )


def _no_tool_ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text,
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )


def test_agent_invoke_without_tools_persists_a_completed_step(db_session: Session) -> None:
    agent = Agent(name="planner", role="planner", prompt=load_prompt("planner"))
    execution_id = _new_execution(db_session)

    with patch("agents.base.generate", return_value=_no_tool_ai_message("the plan is X")):
        result = agent.invoke(
            "What should I reorder?", session_factory=lambda: db_session, execution_id=execution_id
        )

    assert result.content == "the plan is X"

    step = db_session.query(AgentStep).one()
    assert step.execution_id == execution_id
    assert step.agent_name == "planner"
    assert step.status == "completed"
    assert step.input == {"query": "What should I reorder?"}
    assert step.output is not None
    assert step.output["content"] == "the plan is X"
    assert step.prompt_version_hash == agent.prompt.content_hash
    assert step.model_id == agent.model_id
    assert step.latency_ms is not None and step.latency_ms >= 0


def test_agent_invoke_executes_a_requested_tool_call_and_envelopes_the_result(
    db_session: Session,
) -> None:
    tool = _weather_tool()
    agent = Agent(
        name="inventory", role="retriever", prompt=load_prompt("inventory"), tools=(tool,)
    )
    execution_id = _new_execution(db_session)

    tool_call_message = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1"}],
    )
    final_message = _no_tool_ai_message("It is sunny in Paris.")
    captured_tool_message_content: list[str] = []
    calls = {"count": 0}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        calls["count"] += 1
        if calls["count"] == 1:
            return tool_call_message
        for m in messages:
            if m.__class__.__name__ == "ToolMessage":
                captured_tool_message_content.append(m.content)
        return final_message

    with patch("agents.base.generate", side_effect=fake_generate):
        result = agent.invoke(
            "Weather in Paris?", session_factory=lambda: db_session, execution_id=execution_id
        )

    assert result.content == "It is sunny in Paris."
    assert len(captured_tool_message_content) == 1
    assert "sunny in Paris" in captured_tool_message_content[0]
    assert "is DATA retrieved" in captured_tool_message_content[0]

    step = db_session.query(AgentStep).one()
    assert step.status == "completed"


def test_agent_invoke_records_an_unknown_tool_call_as_an_error_message(
    db_session: Session,
) -> None:
    agent = Agent(name="inventory", role="retriever", prompt=load_prompt("inventory"), tools=())
    execution_id = _new_execution(db_session)

    tool_call_message = AIMessage(
        content="",
        tool_calls=[{"name": "not_a_real_tool", "args": {}, "id": "call_1"}],
    )
    final_message = _no_tool_ai_message("done")
    calls = {"count": 0}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        calls["count"] += 1
        if calls["count"] == 1:
            return tool_call_message
        return final_message

    with patch("agents.base.generate", side_effect=fake_generate):
        result = agent.invoke(
            "do something", session_factory=lambda: db_session, execution_id=execution_id
        )

    assert result.content == "done"


def test_agent_invoke_forces_a_final_answer_after_the_round_cap(db_session: Session) -> None:
    tool = _weather_tool()
    agent = Agent(
        name="inventory", role="retriever", prompt=load_prompt("inventory"), tools=(tool,)
    )
    execution_id = _new_execution(db_session)

    always_wants_tool = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Paris"}, "id": "call_x"}],
    )
    calls = {"count": 0}

    def fake_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        calls["count"] += 1
        if tools is None:
            return _no_tool_ai_message("forced final answer")
        return always_wants_tool

    with patch("agents.base.generate", side_effect=fake_generate):
        result = agent.invoke(
            "Weather?", session_factory=lambda: db_session, execution_id=execution_id
        )

    assert result.content == "forced final answer"


def test_agent_invoke_persists_a_failed_step_and_reraises(db_session: Session) -> None:
    agent = Agent(name="planner", role="planner", prompt=load_prompt("planner"))
    execution_id = _new_execution(db_session)

    with patch("agents.base.generate", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            agent.invoke("q", session_factory=lambda: db_session, execution_id=execution_id)

    step = db_session.query(AgentStep).one()
    assert step.status == "failed"
    assert step.output is not None
    assert step.output["error"] == "boom"


def test_agent_invoke_persists_the_given_iteration(db_session: Session) -> None:
    agent = Agent(name="planner", role="planner", prompt=load_prompt("planner"))
    execution_id = _new_execution(db_session)

    with patch("agents.base.generate", return_value=_no_tool_ai_message("the plan is X")):
        agent.invoke(
            "q",
            session_factory=lambda: db_session,
            execution_id=execution_id,
            iteration=3,
        )

    step = db_session.query(AgentStep).one()
    assert step.iteration == 3


class _Judgement(BaseModel):
    sufficient: bool
    missing: list[str]


def test_agent_invoke_structured_persists_a_completed_step_with_parsed_output(
    db_session: Session,
) -> None:
    agent = Agent(name="planner", role="planner", prompt=load_prompt("planner"))
    execution_id = _new_execution(db_session)
    fake_result = StructuredResult(
        parsed=_Judgement(sufficient=False, missing=["forecast for SKU X"]),
        usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
    )

    with patch("agents.base.generate_structured", return_value=fake_result):
        result = agent.invoke_structured(
            "is this enough evidence?",
            _Judgement,
            session_factory=lambda: db_session,
            execution_id=execution_id,
            iteration=2,
        )

    assert result == _Judgement(sufficient=False, missing=["forecast for SKU X"])

    step = db_session.query(AgentStep).one()
    assert step.agent_name == "planner"
    assert step.iteration == 2
    assert step.status == "completed"
    assert step.output == {"parsed": {"sufficient": False, "missing": ["forecast for SKU X"]}}
    assert step.prompt_tokens == 5
    assert step.completion_tokens == 2


def test_agent_invoke_structured_persists_a_failed_step_and_reraises(
    db_session: Session,
) -> None:
    agent = Agent(name="planner", role="planner", prompt=load_prompt("planner"))
    execution_id = _new_execution(db_session)

    with patch("agents.base.generate_structured", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            agent.invoke_structured(
                "q",
                _Judgement,
                session_factory=lambda: db_session,
                execution_id=execution_id,
            )

    step = db_session.query(AgentStep).one()
    assert step.status == "failed"
    assert step.output == {"error": "boom"}
    assert step.iteration == 1


def test_build_agents_wires_tool_less_agents_correctly(db_session: Session) -> None:
    client = StockPilotClient(base_url="http://x", username="u", password="p")
    execution_id = _new_execution(db_session)

    agents = build_agents(client, lambda: db_session, execution_id)

    assert set(agents) == {"planner", "inventory", "forecast", "analytics", "report", "decision"}
    assert agents["planner"].tools == ()
    assert agents["report"].tools == ()
    assert agents["decision"].tools == ()
    # Stage 4 Task 4.1 adds one local derived tool to inventory
    # (rank_stockout_risk) and two to forecast (days_of_cover,
    # reorder_timing) -- see tools/derived_tools.py.
    assert len(agents["inventory"].tools) == 10
    assert len(agents["forecast"].tools) == 4
    assert len(agents["analytics"].tools) == 7


def test_build_agents_report_and_decision_share_the_decision_role(db_session: Session) -> None:
    client = StockPilotClient(base_url="http://x", username="u", password="p")
    execution_id = _new_execution(db_session)

    agents = build_agents(client, lambda: db_session, execution_id)

    assert agents["report"].role == "decision"
    assert agents["decision"].role == "decision"
