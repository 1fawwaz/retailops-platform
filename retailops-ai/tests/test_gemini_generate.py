from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from llm.providers.gemini import (
    MAX_LLM_RETRIES,
    LLMUnavailableError,
    _response_to_ai_message,
    _split_messages,
    _tool_to_gemini,
    generate,
    generate_structured,
    stream,
)


class GetWeatherArgs(BaseModel):
    city: str = Field(description="City name")


def _weather_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda city: f"sunny in {city}",
        name="get_weather",
        description="Get the weather for a city.",
        args_schema=GetWeatherArgs,
    )


def _fake_response(obj: object) -> types.GenerateContentResponse:
    """SimpleNamespace stand-ins duck-type the real SDK response shape for
    these tests; cast at the boundary rather than weakening the real
    function's signature.
    """
    return cast(types.GenerateContentResponse, obj)


def test_split_messages_extracts_system_instruction() -> None:
    system, contents = _split_messages(
        [SystemMessage(content="You are helpful."), HumanMessage(content="Hi")]
    )

    assert system == "You are helpful."
    assert len(contents) == 1
    assert contents[0].role == "user"


def test_split_messages_rejects_more_than_one_system_message() -> None:
    with pytest.raises(ValueError, match="Only one SystemMessage"):
        _split_messages([SystemMessage(content="a"), SystemMessage(content="b")])


def test_split_messages_converts_ai_message_with_tool_calls() -> None:
    ai_message = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1"}],
    )

    _, contents = _split_messages([ai_message])

    assert contents[0].role == "model"
    parts = contents[0].parts
    assert parts is not None
    function_call = parts[0].function_call
    assert function_call is not None
    assert function_call.name == "get_weather"
    assert function_call.args == {"city": "Paris"}


def test_split_messages_converts_tool_message() -> None:
    tool_message = ToolMessage(content="sunny", tool_call_id="call_1", name="get_weather")

    _, contents = _split_messages([tool_message])

    assert contents[0].role == "user"
    parts = contents[0].parts
    assert parts is not None
    function_response = parts[0].function_response
    assert function_response is not None
    assert function_response.name == "get_weather"
    assert function_response.response == {"result": "sunny"}


def test_split_messages_rejects_unsupported_message_type() -> None:
    with pytest.raises(TypeError):
        _split_messages([object()])  # type: ignore[list-item]


def test_tool_to_gemini_uses_the_pydantic_json_schema() -> None:
    gemini_tool = _tool_to_gemini(_weather_tool())

    declarations = gemini_tool.function_declarations
    assert declarations is not None
    declaration = declarations[0]
    assert declaration.name == "get_weather"
    schema = declaration.parameters_json_schema
    assert schema is not None
    assert schema["properties"]["city"]["description"] == "City name"


def test_response_to_ai_message_extracts_text() -> None:
    response = _fake_response(
        SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(text="hello", function_call=None)]
                    )
                )
            ],
            usage_metadata=SimpleNamespace(
                prompt_token_count=10, candidates_token_count=5, thoughts_token_count=0
            ),
        )
    )

    message = _response_to_ai_message(response)

    assert message.content == "hello"
    assert message.tool_calls == []
    assert message.usage_metadata == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_response_to_ai_message_extracts_tool_calls_and_thought_signature() -> None:
    function_call = SimpleNamespace(id="call_1", name="get_weather", args={"city": "Paris"})
    response = _fake_response(
        SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[
                            SimpleNamespace(
                                text=None, function_call=function_call, thought_signature=b"sig"
                            )
                        ]
                    )
                )
            ],
            usage_metadata=None,
        )
    )

    message = _response_to_ai_message(response)

    assert message.tool_calls == [
        {"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1", "type": "tool_call"}
    ]
    assert message.additional_kwargs["thought_signatures"] == {"call_1": b"sig"}


def test_response_to_ai_message_handles_empty_candidates() -> None:
    response = _fake_response(SimpleNamespace(candidates=[], usage_metadata=None))

    message = _response_to_ai_message(response)

    assert message.content == ""
    assert message.tool_calls == []


def _fake_generate_content_response(
    text: str = "", tool_call: dict[str, Any] | None = None
) -> types.GenerateContentResponse:
    parts = []
    if text:
        parts.append(SimpleNamespace(text=text, function_call=None, thought_signature=None))
    if tool_call:
        parts.append(
            SimpleNamespace(
                text=None,
                function_call=SimpleNamespace(**tool_call),
                thought_signature=None,
            )
        )
    return _fake_response(
        SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))],
            usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=1, thoughts_token_count=0
            ),
        )
    )


def test_generate_calls_the_sdk_and_returns_an_ai_message() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_generate_content_response(
        text="hi there"
    )

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client):
        result = generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert result.content == "hi there"
    fake_client.models.generate_content.assert_called_once()


def test_generate_structured_returns_the_parsed_pydantic_instance_and_usage() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = SimpleNamespace(
        parsed=Sentiment(label="positive"),
        text='{"label": "positive"}',
        usage_metadata=SimpleNamespace(
            prompt_token_count=7, candidates_token_count=3, thoughts_token_count=0
        ),
    )

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client):
        result = generate_structured(
            model="gemini-3.5-flash",
            messages=[HumanMessage(content="I love this")],
            response_schema=Sentiment,
        )

    assert result.parsed == Sentiment(label="positive")
    assert result.usage_metadata == {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}


def test_generate_structured_raises_if_sdk_did_not_return_the_schema_type() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = SimpleNamespace(parsed=None, text="oops")

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        pytest.raises(ValueError, match="did not return a valid"),
    ):
        generate_structured(
            model="gemini-3.5-flash",
            messages=[HumanMessage(content="x")],
            response_schema=Sentiment,
        )


def test_generate_retries_on_timeout_then_succeeds() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = [
        httpx.TimeoutException("timed out"),
        httpx.TimeoutException("timed out"),
        _fake_generate_content_response(text="finally"),
    ]

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
    ):
        result = generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert result.content == "finally"
    assert fake_client.models.generate_content.call_count == 3
    assert fake_sleep.call_count == 2


def test_generate_raises_llm_unavailable_after_exhausting_retries() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = httpx.ConnectError("refused")

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(LLMUnavailableError, match="unreachable after"),
    ):
        generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert fake_client.models.generate_content.call_count == MAX_LLM_RETRIES + 1
    assert fake_sleep.call_count == MAX_LLM_RETRIES


def test_generate_retries_on_server_error() -> None:
    fake_client = MagicMock()
    server_error = genai_errors.ServerError(503, {"error": {"message": "unavailable"}})
    fake_client.models.generate_content.side_effect = [
        server_error,
        _fake_generate_content_response(text="recovered"),
    ]

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep"),
    ):
        result = generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert result.content == "recovered"


def test_generate_does_not_retry_client_errors() -> None:
    fake_client = MagicMock()
    client_error = genai_errors.ClientError(400, {"error": {"message": "bad request"}})
    fake_client.models.generate_content.side_effect = client_error

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(genai_errors.ClientError),
    ):
        generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert fake_client.models.generate_content.call_count == 1
    fake_sleep.assert_not_called()


def test_generate_structured_retries_on_timeout_then_succeeds() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = [
        httpx.TimeoutException("timed out"),
        SimpleNamespace(
            parsed=Sentiment(label="positive"),
            text='{"label": "positive"}',
            usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=1, thoughts_token_count=0
            ),
        ),
    ]

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep"),
    ):
        result = generate_structured(
            model="gemini-3.5-flash",
            messages=[HumanMessage(content="hi")],
            response_schema=Sentiment,
        )

    assert result.parsed == Sentiment(label="positive")


def test_stream_yields_text_chunks() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content_stream.return_value = [
        SimpleNamespace(text="Hel"),
        SimpleNamespace(text="lo"),
        SimpleNamespace(text=None),
    ]

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client):
        chunks = list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert chunks == ["Hel", "lo"]
