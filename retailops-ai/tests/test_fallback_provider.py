"""Stage 6 Task 6.4: llm/providers/fallback.py::FallbackProvider -- the
catch-and-switch logic itself, using small fake providers (not the real
Gemini/Groq SDKs) so each test isolates exactly one behavior: which
exceptions trigger a switch, which don't, and the "never silently
restart mid-stream" rule.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from llm.providers.base import (
    LLMUnavailableError,
    ProviderUnavailableError,
    StreamChunk,
    StructuredResult,
)
from llm.providers.fallback import FallbackProvider


class Sentiment(BaseModel):
    label: str


class FakeProvider:
    """A minimal LLMProvider stand-in: raises `error` (if given) or
    returns a canned, provider-tagged result, and records every call it
    received so tests can assert on how many providers were actually
    tried.
    """

    def __init__(
        self,
        name: str,
        *,
        error: Exception | None = None,
        stream_chunks: list[StreamChunk] | None = None,
        stream_error_after: Exception | None = None,
    ) -> None:
        self.name = name
        self._error = error
        self._stream_chunks = stream_chunks or []
        self._stream_error_after = stream_error_after
        self.calls: list[str] = []

    def generate(self, *, model: str, messages: list[Any], **_: Any) -> AIMessage:
        self.calls.append(model)
        if self._error is not None:
            raise self._error
        return AIMessage(
            content=f"served by {self.name}",
            response_metadata={"provider": self.name, "model": model},
        )

    def generate_structured(
        self, *, model: str, messages: list[Any], response_schema: type, **_: Any
    ) -> StructuredResult[Any]:
        self.calls.append(model)
        if self._error is not None:
            raise self._error
        return StructuredResult(
            parsed=response_schema(label="ok"),
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            provider=self.name,
            model=model,
        )

    def stream(self, *, model: str, messages: list[Any], **_: Any) -> Iterator[StreamChunk]:
        self.calls.append(model)
        if self._error is not None:
            raise self._error
        yield from self._stream_chunks
        if self._stream_error_after is not None:
            raise self._stream_error_after

    def list_model_ids(self) -> list[str]:
        return [f"{self.name}-model-a", f"{self.name}-model-b"]


_MESSAGES: list[BaseMessage] = [HumanMessage(content="hi")]


def test_generate_returns_the_primary_result_when_it_succeeds() -> None:
    primary = FakeProvider("primary")
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    result = chain.generate(model="primary-model", messages=_MESSAGES)

    assert result.content == "served by primary"
    assert primary.calls == ["primary-model"]
    assert fallback.calls == []


def test_generate_switches_to_fallback_on_provider_unavailable() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("quota exceeded"))
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    result = chain.generate(model="primary-model", messages=_MESSAGES)

    assert result.content == "served by fallback"
    assert primary.calls == ["primary-model"]
    assert fallback.calls == ["fallback-model"]


def test_generate_does_not_switch_on_a_non_provider_unavailable_error() -> None:
    primary = FakeProvider("primary", error=ValueError("model returned malformed output"))
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    with pytest.raises(ValueError, match="malformed output"):
        chain.generate(model="primary-model", messages=_MESSAGES)

    assert primary.calls == ["primary-model"]
    assert fallback.calls == []


def test_generate_raises_llm_unavailable_when_every_provider_fails() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("primary down"))
    fallback = FakeProvider("fallback", error=ProviderUnavailableError("fallback down"))
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    with pytest.raises(LLMUnavailableError, match="fallback down"):
        chain.generate(model="primary-model", messages=_MESSAGES)

    assert primary.calls == ["primary-model"]
    assert fallback.calls == ["fallback-model"]


def test_generate_structured_switches_to_fallback_on_provider_unavailable() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("quota exceeded"))
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    result = chain.generate_structured(
        model="primary-model", messages=_MESSAGES, response_schema=Sentiment
    )

    assert result.provider == "fallback"
    assert result.parsed == Sentiment(label="ok")


def test_generate_structured_does_not_switch_on_validation_failure() -> None:
    primary = FakeProvider("primary", error=ValueError("did not return valid json"))
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    with pytest.raises(ValueError, match="did not return valid json"):
        chain.generate_structured(
            model="primary-model", messages=_MESSAGES, response_schema=Sentiment
        )

    assert fallback.calls == []


def test_stream_switches_to_fallback_when_primary_fails_before_first_chunk() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("quota exceeded"))
    fallback = FakeProvider(
        "fallback", stream_chunks=[StreamChunk(text="he"), StreamChunk(text="llo")]
    )
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    chunks = list(chain.stream(model="primary-model", messages=_MESSAGES))

    assert [c.text for c in chunks] == ["he", "llo"]
    assert primary.calls == ["primary-model"]
    assert fallback.calls == ["fallback-model"]


def test_stream_does_not_restart_when_primary_fails_mid_stream() -> None:
    primary = FakeProvider(
        "primary",
        stream_chunks=[StreamChunk(text="partial")],
        stream_error_after=ProviderUnavailableError("dropped mid-stream"),
    )
    fallback = FakeProvider("fallback", stream_chunks=[StreamChunk(text="should never appear")])
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    iterator = chain.stream(model="primary-model", messages=_MESSAGES)
    first = next(iterator)
    assert first.text == "partial"

    with pytest.raises(ProviderUnavailableError, match="dropped mid-stream"):
        next(iterator)

    assert fallback.calls == []


def test_generate_structured_raises_llm_unavailable_when_every_provider_fails() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("primary down"))
    fallback = FakeProvider("fallback", error=ProviderUnavailableError("fallback down"))
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    with pytest.raises(LLMUnavailableError, match="fallback down"):
        chain.generate_structured(
            model="primary-model", messages=_MESSAGES, response_schema=Sentiment
        )


def test_stream_returns_nothing_for_a_genuinely_empty_stream() -> None:
    primary = FakeProvider("primary", stream_chunks=[])
    fallback = FakeProvider("fallback", stream_chunks=[StreamChunk(text="should never appear")])
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    chunks = list(chain.stream(model="primary-model", messages=_MESSAGES))

    assert chunks == []
    assert fallback.calls == []


def test_stream_raises_llm_unavailable_when_every_provider_fails_before_first_chunk() -> None:
    primary = FakeProvider("primary", error=ProviderUnavailableError("primary down"))
    fallback = FakeProvider("fallback", error=ProviderUnavailableError("fallback down"))
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    with pytest.raises(LLMUnavailableError, match="fallback down"):
        list(chain.stream(model="primary-model", messages=_MESSAGES))


def test_list_model_ids_aggregates_every_provider_in_the_chain() -> None:
    primary = FakeProvider("primary")
    fallback = FakeProvider("fallback")
    chain = FallbackProvider([(primary, "primary-model"), (fallback, "fallback-model")])

    assert chain.list_model_ids() == [
        "primary-model-a",
        "primary-model-b",
        "fallback-model-a",
        "fallback-model-b",
    ]


def test_construction_rejects_an_empty_chain() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FallbackProvider([])
