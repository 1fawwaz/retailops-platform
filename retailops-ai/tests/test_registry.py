"""Stage 6 Task 6.4: llm/providers/registry.py -- chain resolution.
Covers both paths described in that module's own docstring: FRESH
resolution (primary/fallback order per Settings.llm_primary_provider)
and PINNED resolution (a later round of an existing conversation stays
on whichever provider served the last AIMessage). The pin is the
critical, live-verified fix for the cross-provider thought_signature
bug -- see registry.py's docstring -- so it gets the most thorough
coverage here.

Fakes stand in for the two concrete providers (never the real SDKs);
`llm.providers.registry._PROVIDERS_BY_NAME` is patched directly so
these tests exercise registry.py's own resolution logic in isolation
from gemini.py/groq.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from llm.providers import registry
from llm.providers.base import (
    LLMUnavailableError,
    ProviderUnavailableError,
    StreamChunk,
    StructuredResult,
)
from model_config import get_model_config
from settings import get_settings


class Sentiment(BaseModel):
    label: str


class FakeProvider:
    def __init__(self, name: str, *, error: Exception | None = None) -> None:
        self.name = name
        self._error = error
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
            parsed=response_schema(label=self.name),
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            provider=self.name,
            model=model,
        )

    def stream(self, *, model: str, messages: list[Any], **_: Any) -> Iterator[StreamChunk]:
        self.calls.append(model)
        if self._error is not None:
            raise self._error
        yield StreamChunk(text="chunk", provider=self.name, model=model)

    def list_model_ids(self) -> list[str]:  # pragma: no cover - unused here
        return []


@pytest.fixture
def fake_providers(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeProvider, FakeProvider]:
    gemini = FakeProvider("gemini")
    groq = FakeProvider("groq")
    monkeypatch.setattr(registry, "_PROVIDERS_BY_NAME", {"gemini": gemini, "groq": groq})
    return gemini, groq


@pytest.fixture
def primary_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Flips Settings.llm_primary_provider for one test via the real env
    var + settings cache, restoring both afterward -- get_settings() is
    lru_cache'd, so a bare monkeypatch.setenv alone wouldn't take effect.
    """

    def _set(value: str) -> None:
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", value)
        get_settings.cache_clear()

    yield _set  # type: ignore[misc]
    get_settings.cache_clear()


PLANNER_MODEL = get_model_config().roles.planner.model
FALLBACK_MODEL = get_model_config().fallback.model


def test_fresh_chain_tries_groq_first_by_default(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    """Groq is the project's default primary provider, Gemini its
    default fallback -- see Settings.llm_primary_provider's own
    docstring for the decision.
    """
    gemini, groq = fake_providers
    assert get_settings().llm_primary_provider == "groq"

    result = registry.generate(model=PLANNER_MODEL, messages=[HumanMessage(content="hi")])

    assert result.content == "served by groq"
    assert groq.calls == [PLANNER_MODEL]
    assert gemini.calls == []


def test_fresh_chain_tries_gemini_first_when_configured_as_primary(
    fake_providers: tuple[FakeProvider, FakeProvider],
    primary_provider: Any,
) -> None:
    """The override used by the TRUST GATE's own "fallback forced as
    primary" live verification, and for reverting to Gemini-first
    operationally.
    """
    primary_provider("gemini")
    gemini, groq = fake_providers

    result = registry.generate(model=PLANNER_MODEL, messages=[HumanMessage(content="hi")])

    assert result.content == "served by gemini"
    assert gemini.calls == [FALLBACK_MODEL]
    assert groq.calls == []


def test_fresh_chain_falls_over_to_the_configured_fallback_on_failure(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, groq = fake_providers
    groq._error = ProviderUnavailableError("quota exceeded")

    result = registry.generate(model=PLANNER_MODEL, messages=[HumanMessage(content="hi")])

    assert result.content == "served by gemini"
    assert groq.calls == [PLANNER_MODEL]
    assert gemini.calls == [FALLBACK_MODEL]


def test_provider_for_role_model_rejects_an_unconfigured_model() -> None:
    with pytest.raises(ValueError, match="not any role's configured primary model"):
        registry._provider_for_role_model("not-a-real-model", get_model_config())


def test_pinned_provider_is_none_for_a_fresh_conversation() -> None:
    assert registry._pinned_provider([HumanMessage(content="hi")]) is None


def test_pinned_provider_reads_the_last_ai_messages_provider() -> None:
    messages = [
        HumanMessage(content="hi"),
        AIMessage(content="first", response_metadata={"provider": "gemini"}),
        HumanMessage(content="continue"),
        AIMessage(content="second", response_metadata={"provider": "groq"}),
    ]
    assert registry._pinned_provider(messages) == "groq"


def test_pinned_conversation_stays_on_the_same_provider_even_if_it_would_lose_to_fresh_resolution(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    """The critical fix: round 2 of a Gemini-served conversation (e.g.
    Groq quota-exhausted mid-conversation, Task 6.4's own scenario) must
    call Gemini again, never re-resolve to Groq even though Groq is the
    configured default primary -- this is exactly the scenario that
    produced the real `thought_signature` bug (see registry.py's own
    docstring), and matters regardless of which provider is configured
    as the default primary. Also asserts the pinned round is NOT given
    a fresh two-provider chain: if the pinned provider fails, it must
    raise LLMUnavailableError immediately rather than trying the other
    one.
    """
    gemini, groq = fake_providers
    history = [
        HumanMessage(content="hi"),
        AIMessage(
            content="round 1, served by gemini",
            tool_calls=[{"name": "get_inventory", "args": {}, "id": "call_1"}],
            response_metadata={"provider": "gemini", "model": FALLBACK_MODEL},
        ),
    ]

    result = registry.generate(model=PLANNER_MODEL, messages=history)

    assert result.content == "served by gemini"
    assert gemini.calls == [FALLBACK_MODEL]
    assert groq.calls == []


def test_pinned_conversation_does_not_fail_over_if_the_pinned_provider_fails(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, groq = fake_providers
    groq._error = ProviderUnavailableError("groq down mid-conversation")
    history = [
        HumanMessage(content="hi"),
        AIMessage(
            content="round 1",
            response_metadata={"provider": "groq", "model": PLANNER_MODEL},
        ),
    ]

    with pytest.raises(LLMUnavailableError):
        registry.generate(model=PLANNER_MODEL, messages=history)

    assert groq.calls == [PLANNER_MODEL]
    assert gemini.calls == []


def test_pinned_conversation_uses_the_role_model_when_pinned_to_the_roles_own_provider(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, groq = fake_providers
    history = [
        HumanMessage(content="hi"),
        AIMessage(
            content="round 1, served by groq",
            response_metadata={"provider": "groq", "model": PLANNER_MODEL},
        ),
    ]

    registry.generate(model=PLANNER_MODEL, messages=history)

    assert groq.calls == [PLANNER_MODEL]
    assert gemini.calls == []


def test_stream_resolves_chain_from_message_history_too(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, groq = fake_providers
    history = [
        HumanMessage(content="hi"),
        AIMessage(
            content="round 1", response_metadata={"provider": "gemini", "model": FALLBACK_MODEL}
        ),
    ]

    chunks = list(registry.stream(model=PLANNER_MODEL, messages=history))

    assert [c.text for c in chunks] == ["chunk"]
    assert gemini.calls == [FALLBACK_MODEL]
    assert groq.calls == []


def test_generate_structured_resolves_the_same_fresh_chain_as_generate(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, groq = fake_providers
    groq._error = ProviderUnavailableError("quota exceeded")

    result = registry.generate_structured(
        model=PLANNER_MODEL, messages=[HumanMessage(content="hi")], response_schema=Sentiment
    )

    assert result.provider == "gemini"
    assert result.parsed == Sentiment(label="gemini")
    assert groq.calls == [PLANNER_MODEL]
    assert gemini.calls == [FALLBACK_MODEL]


def test_provider_for_returns_the_named_provider(
    fake_providers: tuple[FakeProvider, FakeProvider],
) -> None:
    gemini, _ = fake_providers
    assert registry.provider_for("gemini") is gemini
