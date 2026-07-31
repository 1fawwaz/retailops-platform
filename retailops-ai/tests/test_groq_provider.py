"""Stage 6 Task 6.4: llm/providers/groq.py -- mirrors
tests/test_gemini_generate.py's own structure (same retry policy, same
class-wraps-functions shape), covering the parts specific to Groq: the
OpenAI-compatible message/tool dict conversion, and the two live-found
behaviors documented in this module's own docstring (429 fails over
immediately with no retry; tool_choice is always explicit).

Multiple-Groq-key rotation tests live at the bottom of this file --
same module, since rotation is entirely internal to groq.py's own retry
machinery (_create_with_retry / stream), not a separate concern.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import groq
import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from llm.providers.base import ProviderUnavailableError, StreamChunk, StructuredResult
from llm.providers.fallback import FallbackProvider
from llm.providers.groq import (
    MAX_LLM_RETRIES,
    GroqProvider,
    _message_to_dict,
    _tool_to_groq,
    generate,
    generate_structured,
    stream,
)
from settings import get_settings


class GetWeatherArgs(BaseModel):
    city: str = Field(description="City name")


def _weather_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda city: f"sunny in {city}",
        name="get_weather",
        description="Get the weather for a city.",
        args_schema=GetWeatherArgs,
    )


def _fake_response(*, content: str = "", tool_calls: list[Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls or []))
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )


def test_message_to_dict_converts_every_message_type() -> None:
    assert _message_to_dict(SystemMessage(content="be helpful")) == {
        "role": "system",
        "content": "be helpful",
    }
    assert _message_to_dict(HumanMessage(content="hi")) == {"role": "user", "content": "hi"}
    assert _message_to_dict(ToolMessage(content="sunny", tool_call_id="call_1", name="x")) == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "sunny",
    }


def test_message_to_dict_converts_ai_message_with_tool_calls() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1"}],
    )
    result = _message_to_dict(message)
    assert result["role"] == "assistant"
    assert result["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
        }
    ]


def test_message_to_dict_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError):
        _message_to_dict(object())  # type: ignore[arg-type]


def test_tool_to_groq_uses_the_pydantic_json_schema() -> None:
    groq_tool = _tool_to_groq(_weather_tool())
    assert groq_tool["type"] == "function"
    function = groq_tool["function"]
    assert isinstance(function, dict)
    assert function["name"] == "get_weather"
    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["properties"]["city"]["description"] == "City name"


def test_generate_calls_the_sdk_with_tool_choice_none_when_no_tools() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(content="hi there")

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        result = generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert result.content == "hi there"
    assert result.response_metadata == {"provider": "groq", "model": "openai/gpt-oss-120b"}
    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == "none"
    assert call_kwargs["tools"] is None


def test_generate_calls_the_sdk_with_tool_choice_auto_when_tools_given() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(content="hi there")

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        generate(
            model="openai/gpt-oss-120b",
            messages=[HumanMessage(content="hi")],
            tools=[_weather_tool()],
        )

    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == "auto"
    assert call_kwargs["tools"] is not None


def test_generate_extracts_tool_calls() -> None:
    fake_client = MagicMock()
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="get_weather", arguments='{"city": "Paris"}'),
    )
    fake_client.chat.completions.create.return_value = _fake_response(tool_calls=[tool_call])

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        result = generate(
            model="openai/gpt-oss-120b",
            messages=[HumanMessage(content="weather?")],
            tools=[_weather_tool()],
        )

    assert result.tool_calls == [
        {"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1", "type": "tool_call"}
    ]


def test_generate_structured_returns_the_parsed_pydantic_instance() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(
        content='{"label": "positive"}'
    )

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        result = generate_structured(
            model="openai/gpt-oss-120b",
            messages=[HumanMessage(content="classify")],
            response_schema=Sentiment,
        )

    assert result.parsed == Sentiment(label="positive")
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-120b"
    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"]["type"] == "json_schema"


def test_generate_structured_raises_if_response_is_not_valid_json_for_the_schema() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(content="not json")

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        pytest.raises(ValueError, match="did not return a valid"),
    ):
        generate_structured(
            model="openai/gpt-oss-120b",
            messages=[HumanMessage(content="classify")],
            response_schema=Sentiment,
        )


def test_generate_does_not_retry_a_429_rate_limit_fails_over_immediately() -> None:
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    rate_limited = groq.RateLimitError("rate limited", response=fake_response, body=None)
    fake_client.chat.completions.create.side_effect = rate_limited

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_generate_retries_a_connection_error_then_succeeds() -> None:
    fake_client = MagicMock()
    fake_request = MagicMock()
    connection_error = groq.APIConnectionError(message="refused", request=fake_request)
    fake_client.chat.completions.create.side_effect = [
        connection_error,
        _fake_response(content="recovered"),
    ]

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep"),
    ):
        result = generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert result.content == "recovered"
    assert fake_client.chat.completions.create.call_count == 2


def test_generate_raises_provider_unavailable_after_exhausting_retries() -> None:
    fake_client = MagicMock()
    fake_request = MagicMock()
    fake_client.chat.completions.create.side_effect = groq.APITimeoutError(request=fake_request)

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="unreachable after"),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == MAX_LLM_RETRIES + 1
    assert fake_sleep.call_count == MAX_LLM_RETRIES


def test_generate_fails_over_immediately_on_a_413_request_too_large() -> None:
    """Real, live-discovered finding (Task 6.5): Groq signals "this
    request exceeds the per-minute token budget" as a 413
    groq.APIStatusError, not a groq.RateLimitError (429-only in this
    SDK) -- semantically the same quota problem, same immediate
    no-retry failover treatment.
    """
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    fake_response.status_code = 413
    too_large = groq.APIStatusError(
        "Request too large", response=fake_response, body={"code": "rate_limit_exceeded"}
    )
    fake_client.chat.completions.create.side_effect = too_large

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_generate_does_not_retry_a_non_413_api_status_error() -> None:
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    fake_response.status_code = 422
    unprocessable = groq.APIStatusError("unprocessable", response=fake_response, body=None)
    fake_client.chat.completions.create.side_effect = unprocessable

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(groq.APIStatusError),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_generate_still_retries_a_5xx_internal_server_error_not_the_413_path() -> None:
    """groq.InternalServerError is ALSO a groq.APIStatusError subclass --
    proves the except-clause ORDER keeps it on the retry-then-fail path,
    not the 413-or-reraise one.
    """
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    fake_response.status_code = 500
    server_error = groq.InternalServerError("server error", response=fake_response, body=None)
    fake_client.chat.completions.create.side_effect = server_error

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="unreachable after"),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == MAX_LLM_RETRIES + 1
    assert fake_sleep.call_count == MAX_LLM_RETRIES


def test_generate_does_not_retry_other_client_errors() -> None:
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    bad_request = groq.BadRequestError("bad request", response=fake_response, body=None)
    fake_client.chat.completions.create.side_effect = bad_request

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(groq.BadRequestError),
    ):
        generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_stream_yields_text_chunks_then_a_final_usage_chunk() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hel"))],
            x_groq=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))],
            x_groq=None,
        ),
        SimpleNamespace(
            choices=[],
            x_groq=SimpleNamespace(usage=SimpleNamespace(prompt_tokens=2, completion_tokens=2)),
        ),
    ]

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        chunks = list(stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]))

    assert [c.text for c in chunks] == ["Hel", "lo", ""]
    assert chunks[-1].usage_metadata == {"input_tokens": 2, "output_tokens": 2, "total_tokens": 4}
    assert chunks[-1].provider == "groq"
    assert chunks[-1].model == "openai/gpt-oss-120b"


def test_stream_does_not_retry_a_429_rate_limit_fails_over_immediately() -> None:
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    rate_limited = groq.RateLimitError("rate limited", response=fake_response, body=None)
    fake_client.chat.completions.create.side_effect = rate_limited

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        list(stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]))

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_stream_fails_over_immediately_on_a_413_request_too_large() -> None:
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    fake_response.status_code = 413
    too_large = groq.APIStatusError(
        "Request too large", response=fake_response, body={"code": "rate_limit_exceeded"}
    )
    fake_client.chat.completions.create.side_effect = too_large

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        list(stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]))

    assert fake_client.chat.completions.create.call_count == 1
    fake_sleep.assert_not_called()


def test_list_model_ids_returns_every_model_id() -> None:
    fake_client = MagicMock()
    fake_client.models.list.return_value = SimpleNamespace(
        data=[SimpleNamespace(id="openai/gpt-oss-120b"), SimpleNamespace(id="llama-3.1-8b-instant")]
    )

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        from llm.providers.groq import list_model_ids

        result = list_model_ids()

    assert result == ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]


def test_groq_provider_class_delegates_to_module_functions() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(content="hi there")

    provider = GroqProvider()
    assert provider.name == "groq"

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        result = provider.generate(
            model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]
        )

    assert result.content == "hi there"


def test_groq_provider_class_delegates_generate_structured() -> None:
    class Sentiment(BaseModel):
        label: str

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response(
        content='{"label": "positive"}'
    )
    provider = GroqProvider()

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        result = provider.generate_structured(
            model="openai/gpt-oss-120b",
            messages=[HumanMessage(content="classify")],
            response_schema=Sentiment,
        )

    assert result.parsed == Sentiment(label="positive")


def test_groq_provider_class_delegates_stream() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hi"))], x_groq=None)
    ]
    provider = GroqProvider()

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        chunks = list(
            provider.stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])
        )

    assert [c.text for c in chunks] == ["hi"]


def test_groq_provider_class_delegates_list_model_ids() -> None:
    fake_client = MagicMock()
    fake_client.models.list.return_value = SimpleNamespace(
        data=[SimpleNamespace(id="openai/gpt-oss-120b")]
    )
    provider = GroqProvider()

    with patch("llm.providers.groq.groq.Groq", return_value=fake_client):
        assert provider.list_model_ids() == ["openai/gpt-oss-120b"]


def test_stream_retries_a_connection_error_then_succeeds() -> None:
    fake_client = MagicMock()
    fake_request = MagicMock()
    connection_error = groq.APIConnectionError(message="refused", request=fake_request)
    fake_client.chat.completions.create.side_effect = [
        connection_error,
        [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="hi"))], x_groq=None
            )
        ],
    ]

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep"),
    ):
        chunks = list(stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]))

    assert [c.text for c in chunks] == ["hi"]
    assert fake_client.chat.completions.create.call_count == 2


def test_stream_raises_provider_unavailable_after_exhausting_retries() -> None:
    fake_client = MagicMock()
    fake_request = MagicMock()
    fake_client.chat.completions.create.side_effect = groq.APITimeoutError(request=fake_request)

    with (
        patch("llm.providers.groq.groq.Groq", return_value=fake_client),
        patch("llm.providers.groq.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="unreachable after"),
    ):
        list(stream(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")]))

    assert fake_client.chat.completions.create.call_count == MAX_LLM_RETRIES + 1
    assert fake_sleep.call_count == MAX_LLM_RETRIES


# ---------------------------------------------------------------------------
# Multiple Groq API keys: rotation on a rate limit, before Gemini failover.
# ---------------------------------------------------------------------------


def _rate_limited() -> groq.RateLimitError:
    fake_response = MagicMock()
    fake_response.request = MagicMock()
    return groq.RateLimitError("rate limited", response=fake_response, body=None)


def _two_keys_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY_1", "key-1")
    monkeypatch.setenv("GROQ_API_KEY_2", "key-2")
    get_settings.cache_clear()


def test_generate_rotates_to_the_next_key_after_a_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement: rotate to the next configured key on a rate limit,
    before failing over to Gemini. Two distinct fake clients (keyed by
    which api_key the SDK constructor received) prove genuine rotation
    happened, not just a retry against the same client.
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.chat.completions.create.side_effect = _rate_limited()
    key_2_client = MagicMock()
    key_2_client.chat.completions.create.return_value = _fake_response(content="from key 2")
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with (
            patch(
                "llm.providers.groq.groq.Groq",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.groq.time.sleep") as fake_sleep,
        ):
            result = generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    assert result.content == "from key 2"
    key_1_client.chat.completions.create.assert_called_once()
    key_2_client.chat.completions.create.assert_called_once()
    # Rotation is not the transient-error retry-with-backoff path -- a
    # rate limit on one key never sleeps, it moves to the next key.
    fake_sleep.assert_not_called()


def test_generate_does_not_rotate_keys_on_a_normal_successful_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement: do NOT rotate keys for normal successful requests --
    keep using the current key until it reaches a rate limit. Proven
    across two separate calls: both must be served by key 1's client.
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.chat.completions.create.return_value = _fake_response(content="ok")
    key_2_client = MagicMock()
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with patch(
            "llm.providers.groq.groq.Groq", side_effect=lambda api_key: clients_by_key[api_key]
        ):
            generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])
            generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi again")])
    finally:
        get_settings.cache_clear()

    assert key_1_client.chat.completions.create.call_count == 2
    key_2_client.chat.completions.create.assert_not_called()


def test_generate_raises_provider_unavailable_once_every_configured_key_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "All Groq keys exhausted" from groq.py's own point of view: once
    every configured key has hit a rate limit, it gives up on Groq
    entirely (a plain ProviderUnavailableError) rather than looping
    forever -- this is the exact signal llm/providers/fallback.py needs
    to move on to Gemini (proven end-to-end in the test below).
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.chat.completions.create.side_effect = _rate_limited()
    key_2_client = MagicMock()
    key_2_client.chat.completions.create.side_effect = _rate_limited()
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with (
            patch(
                "llm.providers.groq.groq.Groq",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.groq.time.sleep") as fake_sleep,
            pytest.raises(ProviderUnavailableError, match="quota exceeded"),
        ):
            generate(model="openai/gpt-oss-120b", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    key_1_client.chat.completions.create.assert_called_once()
    key_2_client.chat.completions.create.assert_called_once()
    fake_sleep.assert_not_called()


def test_all_groq_keys_exhausted_falls_over_to_gemini_via_fallback_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end proof of the literal requirement: once every configured
    Groq key is rate-limited, FallbackProvider (which only ever reacts to
    ProviderUnavailableError -- see its own module docstring) sees Groq
    as unavailable and proceeds to the next provider in the chain, unaware
    that key rotation is what happened underneath.
    """
    _two_keys_configured(monkeypatch)
    exhausted_client = MagicMock()
    exhausted_client.chat.completions.create.side_effect = _rate_limited()
    clients_by_key = {"key-1": exhausted_client, "key-2": exhausted_client}

    class FakeGemini:
        """Implements the full LLMProvider Protocol (only .generate() is
        actually exercised here) -- matching tests/test_fallback_provider.py's
        own FakeProvider convention of a complete stand-in rather than a
        partial one narrowed with a type: ignore.
        """

        name = "gemini"

        def generate(self, *, model: str, messages: list[BaseMessage], **_: Any) -> AIMessage:
            return AIMessage(
                content="served by gemini",
                response_metadata={"provider": "gemini", "model": model},
            )

        def generate_structured(
            self, *, model: str, messages: list[BaseMessage], response_schema: type[Any], **_: Any
        ) -> StructuredResult[Any]:
            raise NotImplementedError

        def stream(
            self, *, model: str, messages: list[BaseMessage], **_: Any
        ) -> Iterator[StreamChunk]:
            raise NotImplementedError
            yield  # pragma: no cover -- makes this a generator function

        def list_model_ids(self) -> list[str]:
            raise NotImplementedError

    try:
        with patch(
            "llm.providers.groq.groq.Groq", side_effect=lambda api_key: clients_by_key[api_key]
        ):
            chain = FallbackProvider(
                [(GroqProvider(), "openai/gpt-oss-120b"), (FakeGemini(), "gemini-3.5-flash")]
            )
            result = chain.generate(model="unused", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    assert result.content == "served by gemini"
    assert exhausted_client.chat.completions.create.call_count == 2


def test_client_raises_clearly_when_no_groq_api_keys_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "No Groq keys configured -> existing startup validation behavior":
    llm/providers/startup.py::validate_configured_models() calls
    list_model_ids() -> _client() at boot, with no try/except of its own
    -- a clear, immediate failure here is what makes the app fail fast
    with a real explanation, the same "fails fast with a clear error"
    contract the spec already required when a single required
    groq_api_key field being unset raised a pydantic ValidationError.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()

    from llm.providers.groq import list_model_ids

    try:
        with pytest.raises(RuntimeError, match="No Groq API keys configured"):
            list_model_ids()
    finally:
        monkeypatch.setenv("GROQ_API_KEY", "test-key-not-for-production")
        get_settings.cache_clear()
