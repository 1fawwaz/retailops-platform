"""Stage 6 Task 6.4: the LLMProvider interface every concrete provider
(GeminiProvider, GroqProvider) and FallbackProvider implement -- the
exact seam CLAUDE.md section 7 has always described: generate(),
generate_structured(), stream(). Nothing above this layer (agents/,
orchestration/) ever imports a provider SDK or knows which provider
actually served a call except by reading the `provider`/`model` fields
this module's own result types carry.

Shared exception taxonomy:
  ProviderUnavailableError -- raised by ONE concrete provider when IT
    could not serve a call. This is the failover-eligible signal
    FallbackProvider catches to try the next provider in the chain.
  LLMUnavailableError(ProviderUnavailableError) -- the TERMINAL "every
    provider in the chain failed" signal. Subclassing ProviderUnavailableError
    means orchestration/graph.py's existing `except LLMUnavailableError`
    catches (Task 3.6, unchanged by this task) keep working unmodified --
    FallbackProvider is the only thing that ever raises this variant,
    never a single provider on its own.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderUnavailableError(Exception):
    """This specific provider could not serve the call after whatever
    in-provider retry policy applies to the failure class (immediate
    for quota/429, after backoff for timeouts/connection errors/5xx --
    see each provider's own docstring). A provider used standalone with
    no FallbackProvider wrapping it should be treated as fully
    unavailable by any caller that catches this.
    """


class LLMUnavailableError(ProviderUnavailableError):
    """Every provider in the chain failed. Raised only by
    FallbackProvider, never by a single concrete provider on its own.
    """


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    """generate_structured()'s return value. `provider`/`model` record
    who ACTUALLY served the call -- with failover, that can differ from
    whatever model string the caller originally asked for -- so callers
    that persist a trace record (CLAUDE.md invariant 2) have the real
    answer, not the configured one.
    """

    parsed: T
    usage_metadata: dict[str, int]
    provider: str
    model: str


@dataclass(frozen=True)
class StreamChunk:
    """One piece of a streamed response. `usage_metadata`/`provider`/
    `model` are only populated on the FINAL chunk of a stream, once the
    whole call (and, implicitly, which provider actually served it) is
    known.
    """

    text: str
    usage_metadata: dict[str, int] | None = None
    provider: str | None = None
    model: str | None = None


class LLMProvider(Protocol):
    """Every concrete provider and FallbackProvider itself implement
    this. `name` is the provider key used in config/models.yaml
    ("gemini", "groq") and recorded verbatim in every result's
    `provider`/AIMessage.response_metadata["provider"] field.
    """

    name: str

    def generate(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIMessage:
        """Returns an AIMessage whose response_metadata carries
        {"provider": ..., "model": ...} for the model that actually
        served the call.
        """
        ...

    def generate_structured(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        response_schema: type[T],
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> StructuredResult[T]: ...

    def stream(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[StreamChunk]: ...

    def list_model_ids(self) -> list[str]:
        """Every model ID this provider's API reports as available to
        the configured credentials -- used by the startup validation
        check (Task 6.4) to fail fast on a misconfigured model ID
        rather than discovering it on the first real request.
        """
        ...
