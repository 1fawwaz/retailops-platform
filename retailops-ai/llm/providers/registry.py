"""Stage 6 Task 6.4: the facade agents/base.py imports generate()/
generate_structured()/stream() from -- the "existing seam" the spec
describes, now backed by two providers and a fallback chain instead of
one. Nothing about the call signature changes from before this task:
callers still pass a bare `model: str` (agents/base.py keeps passing
`self.model_id`, itself a plain model string), never a provider name.

Chain resolution has two paths:
  - FIRST call of a conversation (no prior AIMessage in `messages` yet):
    resolve the normal primary/fallback chain from config/models.yaml,
    by matching the bare `model` string against a role's own configured
    provider. Which end is "primary" is controlled by
    Settings.llm_primary_provider (default "groq" -- Groq is the
    project's default primary provider, Gemini its default fallback,
    see that setting's own docstring) -- see that setting's own
    docstring for the "forced as primary" live-verification use this
    also exists for.
  - LATER round of an existing multi-round tool-calling conversation
    (agents/base.py::Agent.invoke()'s own loop, which re-calls generate()
    once per round with the growing message history): PINNED to
    whichever provider served the LAST AIMessage already in that
    history, no fresh chain resolution, no further failover attempted
    if that pinned provider fails this round.

The pin is a real, load-bearing fix, not a defensive nicety -- confirmed
live during Task 6.4's own TRUST GATE verification: without it, round 1
of an inventory tool-call loop could fail over from Gemini to Groq
(quota), and round 2 (the SAME conversation, continuing after the tool
result) could independently re-resolve back to Gemini if its quota
happened to have room again a few seconds later. Gemini's own API then
rejects the conversation with `400 INVALID_ARGUMENT: Function call is
missing a thought_signature` -- thought_signature is metadata only
Gemini's own responses carry (llm/providers/gemini.py), required when
Gemini is asked to continue a function-call turn it produced itself;
a mid-conversation provider handoff can never satisfy that, regardless
of how carefully thought_signature capture/replay is implemented on the
Gemini side alone (which was already correct -- the bug was allowing a
conversation to change providers mid-flight in the first place, not a
missing-metadata bug in either provider). Deliberately NOT retried with
a different provider if the pinned one fails: the same "never silently
restart" principle stream()'s own mid-stream-failure handling already
uses (llm/providers/fallback.py) applies here too.

No provider SDK is imported here -- only the two concrete providers'
own already-SDK-isolated modules.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from llm.providers import gemini, groq
from llm.providers.base import LLMProvider, StreamChunk, StructuredResult
from llm.providers.fallback import FallbackProvider
from model_config import ModelConfig, get_model_config
from settings import get_settings

T = TypeVar("T", bound=BaseModel)

_GEMINI_PROVIDER: LLMProvider = gemini.GeminiProvider()
_GROQ_PROVIDER: LLMProvider = groq.GroqProvider()
_PROVIDERS_BY_NAME: dict[str, LLMProvider] = {
    _GEMINI_PROVIDER.name: _GEMINI_PROVIDER,
    _GROQ_PROVIDER.name: _GROQ_PROVIDER,
}


def _provider_for_role_model(model: str, config: ModelConfig) -> str:
    """Which provider config/models.yaml configured `model` under, for
    whichever role it belongs to. Raises if `model` isn't any
    configured role's own primary model -- every real caller passes
    Agent.model_id, itself sourced from this same config, so this
    should never actually miss in practice; a clear error here beats a
    confusing one two layers down if that invariant is ever broken.
    """
    for role_config in (config.roles.planner, config.roles.retriever, config.roles.decision):
        if role_config.model == model:
            return role_config.provider
    raise ValueError(
        f"Model {model!r} is not any role's configured primary model in config/models.yaml "
        "-- callers must pass a role's own Agent.model_id, not an arbitrary string."
    )


def _resolve_fresh_chain(model: str) -> list[tuple[LLMProvider, str]]:
    config = get_model_config()
    settings = get_settings()

    primary_provider_name = _provider_for_role_model(model, config)
    primary = (_PROVIDERS_BY_NAME[primary_provider_name], model)
    fallback = (_PROVIDERS_BY_NAME[config.fallback.provider], config.fallback.model)

    if settings.llm_primary_provider == primary_provider_name:
        return [primary, fallback]
    # The configured primary provider isn't the one this role's model
    # belongs to (i.e. llm_primary_provider was flipped to the
    # fallback's own provider) -- try the fallback's provider+model
    # FIRST, falling back to the originally-requested role model second.
    return [fallback, primary]


def _pinned_provider(messages: list[BaseMessage]) -> str | None:
    """Which provider served the LAST AIMessage already in this
    conversation, if any -- see this module's own docstring for why a
    later round must stay pinned to it rather than re-resolving fresh.
    None means this is the first call of a new conversation (only a
    SystemMessage/HumanMessage pair so far, no AIMessage yet).
    """
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            provider = message.response_metadata.get("provider")
            return str(provider) if provider else None
    return None


def _resolve_chain(model: str, messages: list[BaseMessage]) -> list[tuple[LLMProvider, str]]:
    pinned = _pinned_provider(messages)
    if pinned is None:
        return _resolve_fresh_chain(model)
    config = get_model_config()
    effective_model = (
        model if pinned == _provider_for_role_model(model, config) else config.fallback.model
    )
    return [(_PROVIDERS_BY_NAME[pinned], effective_model)]


def generate(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> AIMessage:
    chain = _resolve_chain(model, messages)
    return FallbackProvider(chain).generate(
        model=model,
        messages=messages,
        tools=tools,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def generate_structured(
    *,
    model: str,
    messages: list[BaseMessage],
    response_schema: type[T],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> StructuredResult[T]:
    chain = _resolve_chain(model, messages)
    return FallbackProvider(chain).generate_structured(
        model=model,
        messages=messages,
        response_schema=response_schema,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def stream(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[StreamChunk]:
    chain = _resolve_chain(model, messages)
    yield from FallbackProvider(chain).stream(
        model=model,
        messages=messages,
        tools=tools,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def provider_for(name: str) -> LLMProvider:
    """Direct provider lookup by name, bypassing any fallback chain --
    used by the startup validation check (llm/providers/startup.py),
    which needs to ask EACH provider's own list_model_ids() individually
    rather than going through a chain built for one specific model.
    """
    return _PROVIDERS_BY_NAME[name]
