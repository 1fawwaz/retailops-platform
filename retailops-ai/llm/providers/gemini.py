"""One of two concrete providers (the other: llm/providers/groq.py) behind
the LLMProvider interface (llm/providers/base.py). The ONLY module
allowed to import the Gemini SDK (CLAUDE.md section 7: "No provider SDK
outside llm/providers/"). Messages and tools are LangChain primitives
(SystemMessage, HumanMessage, AIMessage, ToolMessage;
langchain_core.tools.StructuredTool) per CLAUDE.md's "LangChain
(tools/messages primitives only)" rule -- nothing outside llm/providers/
ever sees a google.genai type.

Tool declarations are built directly from each StructuredTool's Pydantic
args_schema via parameters_json_schema (verified live against the real
API rather than assumed -- google-genai's SDK accepts a raw JSON Schema
dict there, no hand-rolled JSON-Schema-to-Gemini-Schema conversion
needed). generate_structured() similarly passes a Pydantic class
directly as response_schema and returns a StructuredResult wrapping
response.parsed (already validated as that type by the SDK) alongside
token usage.

Gemini's "thinking" models return a `thought_signature` on function-call
and text parts; it's preserved via AIMessage.additional_kwargs and
re-attached when a message is sent back in a later turn, since dropping
it could break multi-turn tool use on those models even though nothing
in the current smoke testing surfaced a concrete failure from omitting
it -- cheap to preserve, not worth the risk of silently degrading a
future model swap.

Stage 6 Task 6.4 retry policy (a deliberate change from this build's own
prior behaviour, not an oversight -- see the module docstring history in
git blame if curious): a genuine 429 RESOURCE_EXHAUSTED (Gemini's own
free-tier quota) raises ProviderUnavailableError IMMEDIATELY, no
in-provider retry -- a quota error is deterministic within its window,
so retrying it here only delays FallbackProvider from trying Groq.
Every OTHER retryable failure (timeout, connection drop, 5xx) still
retries MAX_LLM_RETRIES times with exponential backoff first, exactly as
before. Any OTHER ClientError (400 bad request, 401 bad key, ...)
propagates immediately and unmodified either way -- those need a human
to fix configuration, not a retry or a silent failover that would hide
a broken deployment forever.
"""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Iterator
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

# LLMUnavailableError re-exported (the `as LLMUnavailableError` self-alias signals
# this is intentional, not an unused import): orchestration/graph.py, api/errors.py,
# and existing tests all import it from THIS module. Keeping that import path valid,
# rather than requiring every caller to switch to llm.providers.base, is a deliberate,
# minimal-footprint choice matching Task 6.4's own "orchestration, agents, and tools do
# not change at all" constraint. The class itself now lives in base.py since it's the
# shared terminal signal FallbackProvider (not this module) raises once every provider
# in the chain has failed.
from llm.providers.base import LLMUnavailableError as LLMUnavailableError
from llm.providers.base import ProviderUnavailableError as ProviderUnavailableError
from llm.providers.base import StreamChunk as StreamChunk
from llm.providers.base import StructuredResult as StructuredResult
from settings import get_settings

T = TypeVar("T", bound=BaseModel)

THOUGHT_SIGNATURES_KEY = "thought_signatures"

# "LLM timeout -> backoff x3, then a partial answer flagged incomplete".
# Mirrors clients/stockpilot.py's retry shape (same exponential-backoff
# idea, a separate implementation since the retryable exception types
# are provider-specific and this module may never import anything from
# clients/). Does NOT apply to a 429 -- see module docstring.
MAX_LLM_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECONDS = 1.0
RETRYABLE_LLM_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    genai_errors.ServerError,
)
RATE_LIMITED_STATUS_CODE = 429

PROVIDER_NAME = "gemini"


_thread_local = threading.local()


def _client() -> genai.Client:
    """Cached per thread, not per process. google-genai shares an
    underlying httpx connection pool across Client instances constructed
    with the same API key, and closes it when an instance is garbage
    collected -- a fresh, unbound genai.Client() per call gets collected
    immediately after use and silently breaks every later call in the
    process. A single process-wide cached instance (the original fix)
    avoids that, but introduces a second bug confirmed live once Task
    3.2's graph started running retrieval agents concurrently: two
    threads calling .models.generate_content() at the same time on one
    shared Client fail with "Cannot send a request, as the client has
    been closed" -- the SDK isn't safe for truly concurrent use of a
    single instance either. Caching one instance per thread instead
    avoids both failure modes: each thread's client survives for that
    thread's lifetime (no premature GC) and is never touched by another
    thread (no concurrent-use closure).
    """
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = genai.Client(api_key=get_settings().gemini_api_key)
        _thread_local.client = client
    return client


def _reset_client_cache() -> None:
    """Test-only: drops the *current thread's* cached client so a test
    that patches genai.Client gets a fresh instance instead of a
    previous test's stale one. Tests all run on the main thread, so
    clearing only the calling thread's slot is sufficient.
    """
    _thread_local.client = None


def _message_to_content(message: BaseMessage) -> types.Content:
    if isinstance(message, HumanMessage):
        return types.Content(role="user", parts=[types.Part(text=str(message.content))])
    if isinstance(message, AIMessage):
        thought_signatures = message.additional_kwargs.get(THOUGHT_SIGNATURES_KEY, {})
        parts: list[types.Part] = []
        if message.content:
            parts.append(types.Part(text=str(message.content)))
        for tool_call in message.tool_calls:
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        id=tool_call["id"], name=tool_call["name"], args=tool_call["args"]
                    ),
                    thought_signature=thought_signatures.get(tool_call["id"]),
                )
            )
        return types.Content(role="model", parts=parts)
    if isinstance(message, ToolMessage):
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=message.tool_call_id,
                        name=message.name or "",
                        response={"result": message.content},
                    )
                )
            ],
        )
    raise TypeError(f"Unsupported message type for Gemini: {type(message)!r}")


def _split_messages(messages: list[BaseMessage]) -> tuple[str | None, list[types.Content]]:
    """Gemini takes the system prompt as a separate top-level field, not a
    message in the conversation list.
    """
    system_instruction: str | None = None
    contents: list[types.Content] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            if system_instruction is not None:
                raise ValueError("Only one SystemMessage is supported per call.")
            system_instruction = str(message.content)
            continue
        contents.append(_message_to_content(message))
    return system_instruction, contents


def _tool_to_gemini(tool: StructuredTool) -> types.Tool:
    args_schema = tool.args_schema
    schema = (
        args_schema.model_json_schema()
        if isinstance(args_schema, type) and issubclass(args_schema, BaseModel)
        else {"type": "object", "properties": {}}
    )
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=schema,
            )
        ]
    )


def _usage_metadata(response: types.GenerateContentResponse) -> dict[str, int]:
    usage = response.usage_metadata
    prompt_tokens = (usage.prompt_token_count or 0) if usage else 0
    completion_tokens = (
        ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
    )
    return {
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _response_to_ai_message(response: types.GenerateContentResponse, *, model: str) -> AIMessage:
    candidate = response.candidates[0] if response.candidates else None
    parts = (
        candidate.content.parts
        if candidate and candidate.content and candidate.content.parts
        else []
    )

    text_parts: list[str] = []
    tool_calls: list[dict[str, object]] = []
    thought_signatures: dict[str, bytes] = {}
    for index, part in enumerate(parts):
        if part.text:
            text_parts.append(part.text)
        if part.function_call is not None:
            call_id = part.function_call.id or f"call_{index}"
            tool_calls.append(
                {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args or {}),
                    "id": call_id,
                }
            )
            if part.thought_signature:
                thought_signatures[call_id] = part.thought_signature

    return AIMessage(
        content="".join(text_parts),
        tool_calls=tool_calls,
        additional_kwargs={THOUGHT_SIGNATURES_KEY: thought_signatures}
        if thought_signatures
        else {},
        usage_metadata=_usage_metadata(response),
        response_metadata={"provider": PROVIDER_NAME, "model": model},
    )


def _generate_content_with_retry(
    *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
) -> types.GenerateContentResponse:
    """Retries a real Gemini call on transient network errors and 5xx
    responses, exponential backoff (base * 2**attempt). A 429 (quota)
    is NOT retried here at all -- see module docstring. Raises
    ProviderUnavailableError in both failure shapes; FallbackProvider is
    what decides whether to try Groq next.
    """
    last_exception: Exception | None = None
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            return _client().models.generate_content(model=model, contents=contents, config=config)
        except genai_errors.ClientError as exc:
            if exc.code != RATE_LIMITED_STATUS_CODE:
                raise
            raise ProviderUnavailableError(
                f"Gemini quota exceeded calling model {model!r}: {exc}"
            ) from exc
        except RETRYABLE_LLM_EXCEPTIONS as exc:
            last_exception = exc
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    assert last_exception is not None
    raise ProviderUnavailableError(
        f"Gemini unreachable after {MAX_LLM_RETRIES} retries calling model "
        f"{model!r}: {last_exception}"
    ) from last_exception


def generate(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> AIMessage:
    """One conversational turn. If `tools` is given and the model wants to
    call one, the returned AIMessage's `.tool_calls` is populated and
    `.content` may be empty -- the caller executes the tool(s) and sends
    the result back as a ToolMessage in a following call, same as any
    LangChain tool-calling loop.

    Raises ProviderUnavailableError if Gemini could not serve this call
    (immediately for quota, after retries for other transient failures).
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        tools=[_tool_to_gemini(tool) for tool in tools] if tools else None,
    )
    response = _generate_content_with_retry(model=model, contents=contents, config=config)
    return _response_to_ai_message(response, model=model)


def generate_structured(
    *,
    model: str,
    messages: list[BaseMessage],
    response_schema: type[T],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> StructuredResult[T]:
    """Structured output: response_schema is a Pydantic class, passed
    straight through to the SDK, which returns an already-validated
    instance via response.parsed.

    Raises ProviderUnavailableError -- see generate()'s docstring.
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
    )
    response = _generate_content_with_retry(model=model, contents=contents, config=config)
    parsed = response.parsed
    if not isinstance(parsed, response_schema):
        raise ValueError(
            f"Gemini did not return a valid {response_schema.__name__}: {response.text!r}"
        )
    return StructuredResult(
        parsed=parsed,
        usage_metadata=_usage_metadata(response),
        provider=PROVIDER_NAME,
        model=model,
    )


def stream(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[StreamChunk]:
    """Yields StreamChunks as text arrives, with a final chunk carrying
    usage_metadata/provider/model once generation completes. Tool-calling
    is not supported mid-stream (a streamed response is assumed to be
    the final answer, not a step in a tool-use loop) -- callers that
    need tools should use generate() for those turns and reserve
    stream() for the final response to a user.

    Retries ONLY establishing the stream (the SDK call plus fetching the
    first chunk) with the same policy as generate() -- immediate failure
    on quota, backoff-then-fail for other transient errors. A failure
    partway through an already-started stream (after some chunks have
    already reached the caller, e.g. already relayed onward as SSE
    tokens) is NOT retried -- transparently restarting a stream a caller
    has already partially consumed and relayed isn't safe, so this
    deliberately doesn't attempt it; the stream simply ends with the
    exception propagating, same as any other mid-stream network failure.
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        tools=[_tool_to_gemini(tool) for tool in tools] if tools else None,
    )

    last_exception: Exception | None = None
    chunks: Iterator[types.GenerateContentResponse] | None = None
    first: types.GenerateContentResponse | None = None
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            chunks = iter(
                _client().models.generate_content_stream(
                    model=model, contents=contents, config=config
                )
            )
            first = next(chunks, None)
            break
        except genai_errors.ClientError as exc:
            if exc.code != RATE_LIMITED_STATUS_CODE:
                raise
            raise ProviderUnavailableError(
                f"Gemini quota exceeded calling model {model!r} (stream): {exc}"
            ) from exc
        except RETRYABLE_LLM_EXCEPTIONS as exc:
            last_exception = exc
            chunks = None
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    if chunks is None:
        assert last_exception is not None
        raise ProviderUnavailableError(
            f"Gemini unreachable after {MAX_LLM_RETRIES} retries calling model {model!r} "
            f"(stream): {last_exception}"
        ) from last_exception

    last_usage: dict[str, int] | None = None
    remaining = itertools.chain([first], chunks) if first is not None else chunks
    for chunk in remaining:
        if chunk.usage_metadata is not None:
            last_usage = _usage_metadata(chunk)
        if chunk.text:
            yield StreamChunk(text=chunk.text)
    if last_usage is not None:
        yield StreamChunk(text="", usage_metadata=last_usage, provider=PROVIDER_NAME, model=model)


def list_model_ids() -> list[str]:
    """Every model name Gemini's API currently reports as available to
    this API key, with the "models/" prefix stripped so callers can
    compare directly against config/models.yaml's bare IDs.
    """
    client = _client()
    return [model.name.removeprefix("models/") for model in client.models.list() if model.name]


class GeminiProvider:
    """Thin class wrapper around this module's own tested functions --
    the LLMProvider interface (llm/providers/base.py) is implemented by
    delegating straight to generate()/generate_structured()/stream()/
    list_model_ids() above, which retain every existing test's own
    module-level patch targets (llm.providers.gemini.generate,
    llm.providers.gemini.genai.Client, ...) unchanged. Stateless -- safe
    to construct once and reuse (or construct fresh per call, same
    effect either way, since all real state lives in the module-level
    thread-local client cache).
    """

    name = PROVIDER_NAME

    def generate(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIMessage:
        return generate(
            model=model,
            messages=messages,
            tools=tools,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def generate_structured(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        response_schema: type[T],
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> StructuredResult[T]:
        return generate_structured(
            model=model,
            messages=messages,
            response_schema=response_schema,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def stream(
        self,
        *,
        model: str,
        messages: list[BaseMessage],
        tools: list[StructuredTool] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[StreamChunk]:
        return stream(
            model=model,
            messages=messages,
            tools=tools,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def list_model_ids(self) -> list[str]:
        return list_model_ids()
