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
    ProviderUnavailableError,
    _response_to_ai_message,
    _split_messages,
    _tool_to_gemini,
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

    message = _response_to_ai_message(response, model="gemini-3.5-flash")

    assert message.content == "hello"
    assert message.tool_calls == []
    assert message.usage_metadata == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert message.response_metadata == {"provider": "gemini", "model": "gemini-3.5-flash"}


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

    message = _response_to_ai_message(response, model="gemini-3.5-flash")

    assert message.tool_calls == [
        {"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1", "type": "tool_call"}
    ]
    assert message.additional_kwargs["thought_signatures"] == {"call_1": b"sig"}


def test_response_to_ai_message_handles_empty_candidates() -> None:
    response = _fake_response(SimpleNamespace(candidates=[], usage_metadata=None))

    message = _response_to_ai_message(response, model="gemini-3.5-flash")

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


def test_generate_raises_provider_unavailable_after_exhausting_retries() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = httpx.ConnectError("refused")

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="unreachable after"),
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


def test_generate_does_not_retry_a_429_rate_limit_fails_over_immediately() -> None:
    """Stage 6 Task 6.4: a real 429 RESOURCE_EXHAUSTED from Gemini's own
    quota is a genai_errors.ClientError, not a ServerError -- confirmed
    live during Task 6.3 to previously propagate raw past every
    degradation path (fixed there by retrying it). Task 6.4 REVERSES
    that: a quota error is deterministic within its window, so retrying
    it here only delays FallbackProvider (llm/providers/fallback.py)
    from trying Groq -- exactly one attempt, no sleep, immediate
    ProviderUnavailableError.
    """
    fake_client = MagicMock()
    rate_limited = genai_errors.ClientError(
        429, {"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )
    fake_client.models.generate_content.side_effect = rate_limited

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])

    assert fake_client.models.generate_content.call_count == 1
    fake_sleep.assert_not_called()


def test_stream_does_not_retry_a_429_rate_limit_fails_over_immediately() -> None:
    fake_client = MagicMock()
    rate_limited = genai_errors.ClientError(429, {"error": {"message": "quota exceeded"}})
    fake_client.models.generate_content_stream.side_effect = rate_limited

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="quota exceeded"),
    ):
        list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert fake_client.models.generate_content_stream.call_count == 1
    fake_sleep.assert_not_called()


def test_stream_does_not_retry_non_rate_limit_client_errors() -> None:
    fake_client = MagicMock()
    client_error = genai_errors.ClientError(400, {"error": {"message": "bad request"}})
    fake_client.models.generate_content_stream.side_effect = client_error

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(genai_errors.ClientError),
    ):
        list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert fake_client.models.generate_content_stream.call_count == 1
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


def test_stream_yields_text_chunks_then_a_final_usage_chunk() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content_stream.return_value = [
        SimpleNamespace(text="Hel", usage_metadata=None),
        SimpleNamespace(text="lo", usage_metadata=None),
        SimpleNamespace(
            text=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=3, candidates_token_count=2, thoughts_token_count=0
            ),
        ),
    ]

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client):
        chunks = list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert [c.text for c in chunks] == ["Hel", "lo", ""]
    assert chunks[0].usage_metadata is None
    assert chunks[1].usage_metadata is None
    assert chunks[2].usage_metadata == {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}


def test_stream_retries_a_failed_connection_then_succeeds() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content_stream.side_effect = [
        httpx.ConnectError("refused"),
        [SimpleNamespace(text="recovered", usage_metadata=None)],
    ]

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep"),
    ):
        chunks = list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert [c.text for c in chunks] == ["recovered"]


def test_stream_raises_provider_unavailable_after_exhausting_retries() -> None:
    fake_client = MagicMock()
    fake_client.models.generate_content_stream.side_effect = httpx.ConnectError("refused")

    with (
        patch("llm.providers.gemini.genai.Client", return_value=fake_client),
        patch("llm.providers.gemini.time.sleep") as fake_sleep,
        pytest.raises(ProviderUnavailableError, match="unreachable after"),
    ):
        list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))

    assert fake_client.models.generate_content_stream.call_count == MAX_LLM_RETRIES + 1
    assert fake_sleep.call_count == MAX_LLM_RETRIES


# ---------------------------------------------------------------------------
# Multiple Gemini API keys: rotation on a 429 before raising the terminal
# "Gemini providers exhausted" error. Standardized to the exact same
# architecture as test_groq_provider.py's own rotation suite (both providers
# now share llm/providers/key_rotation.py::KeyRotationPool) -- these tests
# are the Gemini-side proof that refactor didn't change observable behavior.
# ---------------------------------------------------------------------------


def _rate_limited_client_error(*, stream: bool = False) -> genai_errors.ClientError:
    suffix = " (stream)" if stream else ""
    return genai_errors.ClientError(
        429, {"error": {"message": f"quota exceeded{suffix}", "status": "RESOURCE_EXHAUSTED"}}
    )


def _two_keys_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY_1", "key-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")
    get_settings.cache_clear()


def test_generate_rotates_to_the_next_key_after_a_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement: rotate to the next configured key on a 429, before
    raising a terminal error. Two distinct fake clients (keyed by which
    api_key the SDK constructor received) prove genuine rotation
    happened, not just a retry against the same client.
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.models.generate_content.side_effect = _rate_limited_client_error()
    key_2_client = MagicMock()
    key_2_client.models.generate_content.return_value = _fake_generate_content_response(
        text="from key 2"
    )
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with (
            patch(
                "llm.providers.gemini.genai.Client",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.gemini.time.sleep") as fake_sleep,
        ):
            result = generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    assert result.content == "from key 2"
    key_1_client.models.generate_content.assert_called_once()
    key_2_client.models.generate_content.assert_called_once()
    # Rotation is not the transient-error retry-with-backoff path -- a
    # rate limit on one key never sleeps, it moves to the next key.
    fake_sleep.assert_not_called()


def test_rotation_logs_the_key_index_never_the_secret_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: log which key index was used (e.g. "Gemini API key
    #2"), never the actual secret. Asserts both halves: the index
    appears, and neither configured key's literal value appears
    anywhere in the captured log text.
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.models.generate_content.side_effect = _rate_limited_client_error()
    key_2_client = MagicMock()
    key_2_client.models.generate_content.return_value = _fake_generate_content_response(
        text="from key 2"
    )
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with (
            patch(
                "llm.providers.gemini.genai.Client",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.gemini.time.sleep"),
            caplog.at_level("WARNING", logger="llm.providers.gemini"),
        ):
            generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    log_text = caplog.text
    assert "Gemini API key #1" in log_text
    assert "rotating to key #2 of 2 configured" in log_text
    assert "key-1" not in log_text
    assert "key-2" not in log_text


def test_rotation_cascades_through_every_configured_key_before_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """key 1 rate-limited -> key 2 rate-limited -> key 3 rate-limited ->
    key 4 succeeds. Proves rotation isn't hardcoded to a two-key case.
    """
    monkeypatch.setenv("GEMINI_API_KEY_1", "key-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key-3")
    monkeypatch.setenv("GEMINI_API_KEY_4", "key-4")
    get_settings.cache_clear()

    rate_limited_clients = {}
    for name in ("key-1", "key-2", "key-3"):
        client = MagicMock()
        client.models.generate_content.side_effect = _rate_limited_client_error()
        rate_limited_clients[name] = client
    key_4_client = MagicMock()
    key_4_client.models.generate_content.return_value = _fake_generate_content_response(
        text="from key 4"
    )
    clients_by_key = {**rate_limited_clients, "key-4": key_4_client}

    try:
        with (
            patch(
                "llm.providers.gemini.genai.Client",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.gemini.time.sleep") as fake_sleep,
        ):
            result = generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    assert result.content == "from key 4"
    for client in rate_limited_clients.values():
        client.models.generate_content.assert_called_once()
    key_4_client.models.generate_content.assert_called_once()
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
    key_1_client.models.generate_content.return_value = _fake_generate_content_response(text="ok")
    key_2_client = MagicMock()
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with patch(
            "llm.providers.gemini.genai.Client", side_effect=lambda api_key: clients_by_key[api_key]
        ):
            generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])
            generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi again")])
    finally:
        get_settings.cache_clear()

    assert key_1_client.models.generate_content.call_count == 2
    key_2_client.models.generate_content.assert_not_called()


def test_generate_raises_provider_unavailable_once_every_configured_key_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once every configured Gemini key has hit a 429, generate() gives
    up on Gemini entirely with a terminal "Gemini providers exhausted"
    ProviderUnavailableError, rather than looping forever -- this is the
    exact signal llm/providers/fallback.py needs to move on to the next
    provider in the chain (proven end-to-end below).
    """
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.models.generate_content.side_effect = _rate_limited_client_error()
    key_2_client = MagicMock()
    key_2_client.models.generate_content.side_effect = _rate_limited_client_error()
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with (
            patch(
                "llm.providers.gemini.genai.Client",
                side_effect=lambda api_key: clients_by_key[api_key],
            ),
            patch("llm.providers.gemini.time.sleep") as fake_sleep,
            pytest.raises(ProviderUnavailableError, match="Gemini providers exhausted"),
        ):
            generate(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    key_1_client.models.generate_content.assert_called_once()
    key_2_client.models.generate_content.assert_called_once()
    fake_sleep.assert_not_called()


def test_all_gemini_keys_exhausted_falls_over_to_groq_via_fallback_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end proof of the literal requirement: once every configured
    Gemini key is rate-limited, FallbackProvider (which only ever reacts
    to ProviderUnavailableError -- see its own module docstring) sees
    Gemini as unavailable and proceeds to the next provider in the chain,
    unaware that key rotation is what happened underneath.
    """
    from collections.abc import Iterator

    from llm.providers.base import StreamChunk, StructuredResult
    from llm.providers.fallback import FallbackProvider
    from llm.providers.gemini import GeminiProvider

    _two_keys_configured(monkeypatch)
    exhausted_client = MagicMock()
    exhausted_client.models.generate_content.side_effect = _rate_limited_client_error()
    clients_by_key = {"key-1": exhausted_client, "key-2": exhausted_client}

    class FakeGroq:
        """Implements the full LLMProvider Protocol (only .generate() is
        actually exercised here) -- matching test_groq_provider.py's own
        FakeGemini convention of a complete stand-in rather than a
        partial one narrowed with a type: ignore.
        """

        name = "groq"

        def generate(self, *, model: str, messages: list[Any], **_: Any) -> AIMessage:
            return AIMessage(
                content="served by groq", response_metadata={"provider": "groq", "model": model}
            )

        def generate_structured(
            self, *, model: str, messages: list[Any], response_schema: type[Any], **_: Any
        ) -> StructuredResult[Any]:
            raise NotImplementedError

        def stream(self, *, model: str, messages: list[Any], **_: Any) -> Iterator[StreamChunk]:
            raise NotImplementedError
            yield  # pragma: no cover -- makes this a generator function

        def list_model_ids(self) -> list[str]:
            raise NotImplementedError

    try:
        with patch(
            "llm.providers.gemini.genai.Client", side_effect=lambda api_key: clients_by_key[api_key]
        ):
            chain = FallbackProvider(
                [(GeminiProvider(), "gemini-3.5-flash"), (FakeGroq(), "openai/gpt-oss-120b")]
            )
            result = chain.generate(model="unused", messages=[HumanMessage(content="hi")])
    finally:
        get_settings.cache_clear()

    assert result.content == "served by groq"
    assert exhausted_client.models.generate_content.call_count == 2


def test_stream_rotates_to_the_next_key_after_a_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _two_keys_configured(monkeypatch)
    key_1_client = MagicMock()
    key_1_client.models.generate_content_stream.side_effect = _rate_limited_client_error(
        stream=True
    )
    key_2_client = MagicMock()
    key_2_client.models.generate_content_stream.return_value = [
        SimpleNamespace(text="from key 2", usage_metadata=None)
    ]
    clients_by_key = {"key-1": key_1_client, "key-2": key_2_client}

    try:
        with patch(
            "llm.providers.gemini.genai.Client", side_effect=lambda api_key: clients_by_key[api_key]
        ):
            chunks = list(stream(model="gemini-3.5-flash", messages=[HumanMessage(content="hi")]))
    finally:
        get_settings.cache_clear()

    assert [c.text for c in chunks] == ["from key 2"]
    key_1_client.models.generate_content_stream.assert_called_once()
    key_2_client.models.generate_content_stream.assert_called_once()


def test_client_raises_clearly_when_no_gemini_api_keys_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Gemini keys configured -> existing startup validation behavior:
    llm/providers/startup.py::validate_configured_models() calls
    list_model_ids() -> _client() at boot, with no try/except of its own
    -- a clear, immediate failure here is what makes the app fail fast
    with a real explanation, the same contract test_groq_provider.py's
    own equivalent test already established for Groq.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    from llm.providers.gemini import list_model_ids

    try:
        with pytest.raises(RuntimeError, match="No Gemini API keys configured"):
            list_model_ids()
    finally:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-for-production")
        get_settings.cache_clear()
