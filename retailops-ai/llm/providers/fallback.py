"""Stage 6 Task 6.4: FallbackProvider -- wraps an ordered chain of
(provider, model) pairs and tries each in turn, entirely inside the
provider layer. Nothing above llm/providers/ (agents/, orchestration/)
ever sees this class or knows failover happened, except by reading which
provider/model actually served a call from the result it gets back
(response_metadata / StructuredResult.provider / StreamChunk.provider).

Failover is deliberately narrow: ONLY ProviderUnavailableError (raised
by a concrete provider per its own documented policy -- immediately for
a quota/429, after in-provider retries for timeouts/connection drops/5xx,
see llm/providers/gemini.py and llm/providers/groq.py) triggers moving to
the next provider in the chain. A ValueError from a provider failing to
return a schema-valid structured response, or any other exception, is
NOT failover-eligible and propagates unmodified -- the model didn't
follow instructions, which is not "this provider is unavailable" and
retrying against a different provider wouldn't fix a validation problem
anyway (nor would it be honest to represent a different model's
different attempt as evidence the original was "unavailable"). Citation
validation and replan judgement live entirely in orchestration/, with no
visibility into this layer at all -- there is no path by which this
class could ever intercept one of those failures even by accident.

If every provider in the chain fails, raises LLMUnavailableError -- the
SAME terminal signal this codebase's Task 3.6/6.3 degradation paths
already catch (orchestration/graph.py's per-node except clauses,
api/errors.py's taxonomy). That existing handling needed zero changes
for this task: it was already written to catch "the LLM is unavailable"
generically, and a fallback chain exhausting itself is exactly that.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from llm.providers.base import (
    LLMProvider,
    LLMUnavailableError,
    ProviderUnavailableError,
    StreamChunk,
    StructuredResult,
)

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class FallbackProvider:
    """Constructed fresh per resolved chain (cheap -- providers are
    stateless class instances, see GeminiProvider/GroqProvider's own
    docstrings) by llm/providers/registry.py's facade functions, which
    are what actually resolve "which provider serves this model, and
    what's the fallback" from config/models.yaml. `model` on each method
    below is accepted for LLMProvider Protocol conformance but NOT used
    to pick a model per provider -- that's already fixed by `chain`
    itself (each provider in the chain gets ITS OWN configured model,
    which can genuinely differ, e.g. a Gemini role model vs Groq's one
    global fallback model) -- the registry is the only caller, and it
    already resolved model->chain before constructing this.
    """

    name = "fallback"

    def __init__(self, chain: list[tuple[LLMProvider, str]]) -> None:
        if not chain:
            raise ValueError("FallbackProvider requires at least one (provider, model) pair")
        self._chain = chain

    def generate(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIMessage:
        last_exc: ProviderUnavailableError | None = None
        for provider, effective_model in self._chain:
            try:
                return provider.generate(
                    model=effective_model,
                    messages=messages,
                    tools=tools,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
            except ProviderUnavailableError as exc:
                logger.warning(
                    "provider %s (model %s) unavailable, trying next in chain: %s",
                    provider.name,
                    effective_model,
                    exc,
                )
                last_exc = exc
        raise LLMUnavailableError(
            f"All providers in the fallback chain failed: {last_exc}"
        ) from last_exc

    def generate_structured(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        response_schema: type[T],
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> StructuredResult[T]:
        last_exc: ProviderUnavailableError | None = None
        for provider, effective_model in self._chain:
            try:
                return provider.generate_structured(
                    model=effective_model,
                    messages=messages,
                    response_schema=response_schema,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
            except ProviderUnavailableError as exc:
                logger.warning(
                    "provider %s (model %s) unavailable, trying next in chain: %s",
                    provider.name,
                    effective_model,
                    exc,
                )
                last_exc = exc
        raise LLMUnavailableError(
            f"All providers in the fallback chain failed: {last_exc}"
        ) from last_exc

    def stream(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[StreamChunk]:
        """Primary fails before its first chunk -> transparently retried
        against the next provider in the chain (identical in spirit to
        generate()/generate_structured() above). Fails AFTER yielding at
        least one chunk -> propagates unmodified, no silent restart --
        a caller (api/agent.py's SSE generator) may have already relayed
        those chunks onward to a real client; silently starting a
        second provider's answer over the top of a partially-delivered
        first one would be actively misleading, not resilient.
        """
        last_exc: ProviderUnavailableError | None = None
        for provider, effective_model in self._chain:
            try:
                iterator = iter(
                    provider.stream(
                        model=effective_model,
                        messages=messages,
                        tools=tools,
                        max_output_tokens=max_output_tokens,
                        temperature=temperature,
                    )
                )
                first = next(iterator)
            except ProviderUnavailableError as exc:
                logger.warning(
                    "provider %s (model %s) unavailable before first token, "
                    "trying next in chain: %s",
                    provider.name,
                    effective_model,
                    exc,
                )
                last_exc = exc
                continue
            except StopIteration:
                return  # a genuinely empty stream is valid; nothing to yield
            yield first
            yield from iterator
            return
        raise LLMUnavailableError(
            f"All providers in the fallback chain failed: {last_exc}"
        ) from last_exc

    def list_model_ids(self) -> list[str]:
        """Not used for failover (each concrete provider's own
        list_model_ids() is what startup validation calls directly, per
        provider) -- implemented for Protocol completeness, aggregating
        every provider in the chain.
        """
        ids: list[str] = []
        for provider, _ in self._chain:
            ids.extend(provider.list_model_ids())
        return ids
