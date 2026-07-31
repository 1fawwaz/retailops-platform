import uuid
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.base import MAX_TOOL_RESULT_ITEMS, Agent, _bounded_for_llm, build_agents
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StreamChunk, StructuredResult
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


def test_bounded_for_llm_truncates_a_list_over_the_cap() -> None:
    oversized = [{"sku": str(i)} for i in range(MAX_TOOL_RESULT_ITEMS + 50)]

    bounded = _bounded_for_llm(oversized)

    assert isinstance(bounded, dict)
    assert bounded["results"] == oversized[:MAX_TOOL_RESULT_ITEMS]
    assert bounded["_truncated"] is True
    assert bounded["_total_count"] == MAX_TOOL_RESULT_ITEMS + 50
    assert "Showing the first" in str(bounded["_note"])


def test_bounded_for_llm_leaves_a_list_at_or_under_the_cap_unchanged() -> None:
    exactly_at_cap = [{"sku": str(i)} for i in range(MAX_TOOL_RESULT_ITEMS)]
    assert _bounded_for_llm(exactly_at_cap) is exactly_at_cap

    small = [{"sku": "1"}, {"sku": "2"}]
    assert _bounded_for_llm(small) is small


def test_bounded_for_llm_leaves_a_non_list_result_unchanged() -> None:
    single = {"sku": "85048", "quantity_on_hand": 12}
    assert _bounded_for_llm(single) is single
    assert _bounded_for_llm("sunny in Paris") == "sunny in Paris"
    assert _bounded_for_llm(None) is None


def test_agent_invoke_truncates_an_oversized_list_tool_result_before_it_reaches_the_llm(
    db_session: Session,
) -> None:
    """Real, live-discovered bug (Stage 7 demo capture): a broad
    inventory question can make a retrieval agent call a list-shaped
    tool at its own allowed limit=1000, and feeding all 1000 rows back
    into that agent's own conversation history can exceed a real LLM's
    context window (Groq: 400 context_length_exceeded), crashing the
    request. This proves the fix at the level a real crash actually
    happened at: the ToolMessage content an agent's own next generate()
    call would see.
    """

    def _many_low_stock_rows(limit: int = 1000, offset: int = 0) -> list[dict[str, object]]:
        return [{"sku": str(i), "quantity_on_hand": 1} for i in range(limit)]

    class GetLowStockArgs(BaseModel):
        limit: int = Field(default=1000)
        offset: int = Field(default=0)

    tool = StructuredTool.from_function(
        func=_many_low_stock_rows,
        name="get_low_stock",
        description="List SKUs at or below their reorder point.",
        args_schema=GetLowStockArgs,
    )
    agent = Agent(
        name="inventory", role="retriever", prompt=load_prompt("inventory"), tools=(tool,)
    )
    execution_id = _new_execution(db_session)

    tool_call_message = AIMessage(
        content="",
        tool_calls=[{"name": "get_low_stock", "args": {"limit": 1000}, "id": "call_1"}],
    )
    final_message = _no_tool_ai_message("Here are the low-stock items.")
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
        agent.invoke(
            "Which products are low on stock?",
            session_factory=lambda: db_session,
            execution_id=execution_id,
        )

    assert len(captured_tool_message_content) == 1
    content = captured_tool_message_content[0]
    # The truncation note and the total count are visible to the model...
    assert "Showing the first 200 of 1000 results" in content
    # ...but the 1000 raw rows are not -- proving genuine truncation, not
    # just an appended note alongside the full payload.
    assert content.count('"sku"') == MAX_TOOL_RESULT_ITEMS
    assert '"999"' not in content  # the 1000th row (index 999) is cut


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


def _fake_stream(*texts: str, usage: dict[str, int] | None = None) -> Any:
    def _stream(**kwargs: object) -> Any:
        for text in texts:
            yield StreamChunk(text=text)
        if usage is not None:
            yield StreamChunk(text="", usage_metadata=usage)

    return _stream


def test_agent_invoke_streaming_accumulates_chunks_and_calls_on_chunk(db_session: Session) -> None:
    agent = Agent(name="decision", role="decision", prompt=load_prompt("decision"))
    execution_id = _new_execution(db_session)
    received: list[str] = []

    with patch(
        "agents.base.stream",
        side_effect=_fake_stream(
            "Hel", "lo", usage={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}
        ),
    ):
        result = agent.invoke_streaming(
            "Summarize.",
            session_factory=lambda: db_session,
            execution_id=execution_id,
            on_chunk=received.append,
        )

    assert result.content == "Hello"
    assert received == ["Hel", "lo"]

    step = db_session.query(AgentStep).one()
    assert step.execution_id == execution_id
    assert step.agent_name == "decision"
    assert step.status == "completed"
    assert step.output is not None
    assert step.output["content"] == "Hello"
    assert step.prompt_tokens == 4
    assert step.completion_tokens == 2


def test_agent_invoke_streaming_works_with_no_on_chunk_callback(db_session: Session) -> None:
    agent = Agent(name="decision", role="decision", prompt=load_prompt("decision"))
    execution_id = _new_execution(db_session)

    with patch("agents.base.stream", side_effect=_fake_stream("all at once")):
        result = agent.invoke_streaming(
            "q", session_factory=lambda: db_session, execution_id=execution_id
        )

    assert result.content == "all at once"


def test_agent_invoke_streaming_rejects_agents_with_tools(db_session: Session) -> None:
    agent = Agent(
        name="inventory",
        role="retriever",
        prompt=load_prompt("inventory"),
        tools=(_weather_tool(),),
    )
    with pytest.raises(ValueError, match="only for tool-less agents"):
        agent.invoke_streaming(
            "q", session_factory=lambda: db_session, execution_id=_new_execution(db_session)
        )


def test_agent_invoke_streaming_persists_a_failed_step_and_reraises(db_session: Session) -> None:
    agent = Agent(name="decision", role="decision", prompt=load_prompt("decision"))
    execution_id = _new_execution(db_session)

    def _boom(**kwargs: object) -> Any:
        raise RuntimeError("stream broke")

    with (
        patch("agents.base.stream", side_effect=_boom),
        pytest.raises(RuntimeError, match="stream broke"),
    ):
        agent.invoke_streaming("q", session_factory=lambda: db_session, execution_id=execution_id)

    step = db_session.query(AgentStep).one()
    assert step.status == "failed"


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
        provider="gemini",
        model="gemini-3.1-pro-preview",
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
    assert step.provider == "gemini"
    assert step.model_id == "gemini-3.1-pro-preview"


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
    # Stage 4 Task 4.1 adds local derived tools to inventory
    # (rank_stockout_risk) and forecast (days_of_cover, reorder_timing);
    # Task 4.5 adds one more to inventory (dead_stock_capital) -- see
    # tools/derived_tools.py.
    assert len(agents["inventory"].tools) == 11
    assert len(agents["forecast"].tools) == 4
    assert len(agents["analytics"].tools) == 7


def test_build_agents_report_and_decision_share_the_decision_role(db_session: Session) -> None:
    client = StockPilotClient(base_url="http://x", username="u", password="p")
    execution_id = _new_execution(db_session)

    agents = build_agents(client, lambda: db_session, execution_id)

    assert agents["report"].role == "decision"
    assert agents["decision"].role == "decision"
