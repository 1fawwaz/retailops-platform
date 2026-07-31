"""One of two concrete providers (the other: llm/providers/gemini.py)
behind the LLMProvider interface (llm/providers/base.py). The ONLY
module allowed to import the Groq SDK (CLAUDE.md section 7). Mirrors
gemini.py's own shape deliberately -- same retry policy, same
thread-local client caching, same class-wraps-module-functions
structure -- so the two providers are easy to compare and audit
side by side, not because Groq's SDK forced this shape.

Groq's API is OpenAI-compatible: plain dict messages
({"role": ..., "content": ...}), function-calling tools as
{"type": "function", "function": {...}}, and response_format=
{"type": "json_schema", "json_schema": {"name": ..., "schema": ...}}
for structured output. Verified live before writing this module (not
assumed): a plain pydantic model_json_schema() -- no OpenAI-style
`additionalProperties: false` strictness needed -- round-trips
correctly through Groq's json_schema mode.

Real, load-bearing findings from live checks during Task 6.4's own
implementation -- see config/models.yaml's own comment for the full
detail, summarized here since both matter for anyone touching this
module:
  1. Only a handful of models on this account's live model list support
     response_format=json_schema at all (most reject it outright with a
     400) -- generate_structured() is used by several roles, so the
     fallback model must be one of those, not just fast/cheap.
  2. Of THOSE, the smaller openai/gpt-oss-20b and -safeguard-20b
     variants unreliably attempted a phantom tool call (rejected by
     Groq's own backend as a 400) even with tool_choice="none" set,
     specifically against this codebase's real planner prompt.
     openai/gpt-oss-120b did not reproduce this. tool_choice is
     therefore ALWAYS set explicitly below (never left at Groq's own
     default) -- omitting it is what originally surfaced finding #2.
The startup validation check (llm/providers/startup.py) only confirms a
configured ID EXISTS on its provider's list, not that it supports every
call shape this codebase needs -- worth remembering if the fallback
model is ever changed; re-verify both properties live, the same way
this module's own docstring history did.

Multiple Groq API keys: `settings.py::Settings.groq_api_keys` is an
ordered list, not a single key (see its own docstring for the
GROQ_API_KEY / GROQ_API_KEY_N precedence). On a rate-limit-class failure
(a 429 groq.RateLimitError, or the 413 "too large for this TPM window"
shape below) THIS module rotates to the next configured key and retries
the same request before ever raising ProviderUnavailableError -- Gemini
failover (llm/providers/fallback.py) only sees Groq as "unavailable"
once every configured key has been tried. Rotation is a one-way,
process-wide ratchet (`_rotate_to_next_key`/`_current_key_index`): it
never un-rotates back to an earlier key within a process's lifetime, and
it's shared across threads (not thread-local like the client cache)
specifically so one agent thread's discovery that a key is exhausted
immediately benefits the other concurrently-running retrieval agents
instead of each independently re-discovering the same 429. Rotation is
NOT a retry-on-transient-error mechanism -- connection/timeout/5xx
errors still use the existing per-key retry-with-backoff loop
unchanged; only a genuine rate-limit signal advances the key pointer.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from collections.abc import Iterator
from typing import Literal, NoReturn, TypeVar

import groq
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from llm.providers.base import ProviderUnavailableError, StreamChunk, StructuredResult
from settings import get_settings

T = TypeVar("T", bound=BaseModel)

PROVIDER_NAME = "groq"

# Same policy as llm/providers/gemini.py: a RateLimitError (429) is NOT
# retried here at all -- immediate failover, since a quota error is
# deterministic within its window. Connection/timeout/5xx errors retry
# with backoff first. Every other groq.APIStatusError (400, 401, 403,
# 404, 409, 422, ...) propagates immediately and unmodified -- those
# need a human to fix configuration, not a retry or silent failover.
MAX_LLM_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECONDS = 1.0
RETRYABLE_GROQ_EXCEPTIONS: tuple[type[Exception], ...] = (
    groq.APIConnectionError,
    groq.APITimeoutError,
    groq.InternalServerError,
)

# Real, live-discovered finding from Task 6.5's own TRUST GATE
# verification (once Groq took full primary-role traffic rather than
# only occasional post-failover calls): Groq signals "this single
# request exceeds the per-minute token budget" as HTTP 413 with
# body.code == "rate_limit_exceeded" -- a bare groq.APIStatusError, NOT
# a groq.RateLimitError (that class is reserved for 429 in this SDK).
# Semantically this IS the same quota problem a 429 represents (the
# request cannot succeed against this window no matter how many times
# it's retried), so it gets the identical immediate-failover treatment
# below -- distinguished from every OTHER APIStatusError (400 bad
# request, 401 bad key, ...), which still propagate unmodified.
GROQ_REQUEST_TOO_LARGE_STATUS_CODE = 413

_thread_local = threading.local()

# Multiple-key rotation state, module-wide (not thread-local -- see the
# module docstring for why). _current_key_index is a plain int; CPython's
# GIL makes a bare read/write of it safe enough for this purpose (worst
# case under a race is one thread briefly using a slightly stale index,
# which self-corrects on its next call), but every INCREMENT goes through
# _rotate_to_next_key() under _key_lock so two threads racing to rotate
# past the same rate-limited key can't both advance it twice.
_key_lock = threading.Lock()
_current_key_index = 0


class _GroqKeyRateLimited(Exception):
    """Internal signal only, never raised past this module: the
    CURRENTLY ACTIVE Groq key hit a rate-limit-class error (429, or the
    413 "too large" shape). The caller (_create_with_retry / stream)
    catches this, tries rotating to the next configured key, and only
    converts it to a caller-facing ProviderUnavailableError once every
    key has been tried -- that's the point at which Groq is genuinely
    "unavailable" and Gemini failover should take over.
    """


def _api_keys() -> list[str]:
    keys = get_settings().groq_api_keys
    if not keys:
        raise RuntimeError(
            "No Groq API keys configured -- set at least GROQ_API_KEY_1 "
            "(or the bare GROQ_API_KEY alias) in .env. See .env.example."
        )
    return keys


def _rotate_to_next_key() -> bool:
    """Advances the shared "current Groq key" pointer to the next
    configured key. Returns True if it did (a next key existed), False
    if the current key was already the last one configured -- the
    caller's cue to give up on Groq entirely for this request and let
    Gemini failover take over.
    """
    global _current_key_index
    keys = _api_keys()
    with _key_lock:
        if _current_key_index + 1 < len(keys):
            _current_key_index += 1
            return True
        return False


def _reset_key_rotation() -> None:
    """Test-only: resets the shared key-rotation pointer back to the
    first configured key, mirroring _reset_client_cache() below.
    """
    global _current_key_index
    with _key_lock:
        _current_key_index = 0


def _client() -> groq.Groq:
    """Cached per thread, keyed to WHICH Groq API key is currently
    active -- same defensive per-thread pattern as
    llm/providers/gemini.py::_client() (nothing has proven Groq's SDK
    shares google-genai's cross-instance connection-pool gotcha, but
    it's consistent and cheap either way), extended so a thread's cached
    client is rebuilt whenever the shared key pointer has moved past
    what it was built with -- e.g. another thread just rotated away from
    a key this thread was still caching a client for.
    """
    keys = _api_keys()
    index = min(_current_key_index, len(keys) - 1)
    client = getattr(_thread_local, "client", None)
    cached_index = getattr(_thread_local, "client_key_index", None)
    if client is None or cached_index != index:
        client = groq.Groq(api_key=keys[index])
        _thread_local.client = client
        _thread_local.client_key_index = index
    return client


def _reset_client_cache() -> None:
    """Test-only: see llm/providers/gemini.py::_reset_client_cache()."""
    _thread_local.client = None
    _thread_local.client_key_index = None


def _message_to_dict(message: BaseMessage) -> dict[str, object]:
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": str(message.content)}
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": str(message.content)}
    if isinstance(message, AIMessage):
        result: dict[str, object] = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {
                        "name": tool_call["name"],
                        "arguments": json.dumps(tool_call["args"]),
                    },
                }
                for tool_call in message.tool_calls
            ]
        return result
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": str(message.content),
        }
    raise TypeError(f"Unsupported message type for Groq: {type(message)!r}")


def _tool_to_groq(tool: StructuredTool) -> dict[str, object]:
    args_schema = tool.args_schema
    schema = (
        args_schema.model_json_schema()
        if isinstance(args_schema, type) and issubclass(args_schema, BaseModel)
        else {"type": "object", "properties": {}}
    )
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": schema},
    }


def _usage_metadata(usage: object) -> dict[str, int]:
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
    return {
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _raise_for_request_too_large(
    exc: groq.APIStatusError, *, model: str, context: str = ""
) -> NoReturn:
    """Re-raises `exc` as _GroqKeyRateLimited (the current key should be
    rotated past) if it's the 413 "too large for this TPM window" shape
    (see GROQ_REQUEST_TOO_LARGE_STATUS_CODE's own comment); otherwise
    re-raises `exc` itself, unmodified -- every other groq.APIStatusError
    (400, 401, 403, 404, 409, 422, ...) still needs a human to fix
    configuration, not a retry, rotation, or silent failover.
    """
    if exc.status_code == GROQ_REQUEST_TOO_LARGE_STATUS_CODE:
        raise _GroqKeyRateLimited(
            f"Groq quota exceeded calling model {model!r}{context}: {exc}"
        ) from exc
    raise exc


def _response_to_ai_message(response: object, *, model: str) -> AIMessage:
    choice = response.choices[0]  # type: ignore[attr-defined]
    message = choice.message
    tool_calls: list[dict[str, object]] = []
    for tool_call in message.tool_calls or []:
        tool_calls.append(
            {
                "name": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments),
                "id": tool_call.id,
            }
        )
    return AIMessage(
        content=message.content or "",
        tool_calls=tool_calls,
        usage_metadata=_usage_metadata(response.usage),  # type: ignore[attr-defined]
        response_metadata={"provider": PROVIDER_NAME, "model": model},
    )


def _create_with_retry_one_key(
    *,
    model: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    response_format: dict[str, object] | None,
) -> object:
    """The original per-key retry loop (transient errors only) --
    raises _GroqKeyRateLimited, not ProviderUnavailableError, for the
    two rate-limit-class cases, so the caller (_create_with_retry) can
    try rotating to the next configured key first.
    """
    # Real, live-discovered bug (Task 6.4's own TRUST GATE verification):
    # with tools=None and tool_choice left at Groq's own default, the
    # gpt-oss family sometimes attempts a tool call anyway (some
    # agentic post-training bias, not this codebase's prompts -- the
    # SAME tool-less planner prompt has run correctly on Gemini this
    # entire build) -- and Groq's own backend then rejects its OWN
    # model's malformed response with a 400 "Tool choice is none, but
    # model called a tool". Explicitly forcing tool_choice="none" when
    # this call carries no tools (matching what a tool-less agent,
    # Task 3.1 invariant 1, always requests) fixes it -- confirmed live.
    last_exception: Exception | None = None
    tool_choice: Literal["none", "auto"] = "none" if not tools else "auto"
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            return _client().chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                tool_choice=tool_choice,
                response_format=response_format,  # type: ignore[arg-type]
            )
        except groq.RateLimitError as exc:
            raise _GroqKeyRateLimited(
                f"Groq quota exceeded calling model {model!r}: {exc}"
            ) from exc
        except RETRYABLE_GROQ_EXCEPTIONS as exc:
            # NOTE: groq.InternalServerError is ALSO a groq.APIStatusError
            # subclass -- this clause MUST stay ordered before the bare
            # APIStatusError one below, or a 5xx would stop retrying and
            # go straight to the 413-or-reraise check instead.
            last_exception = exc
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except groq.APIStatusError as exc:
            _raise_for_request_too_large(exc, model=model)
    assert last_exception is not None
    raise ProviderUnavailableError(
        f"Groq unreachable after {MAX_LLM_RETRIES} retries calling model {model!r}: "
        f"{last_exception}"
    ) from last_exception


def _create_with_retry(
    *,
    model: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    response_format: dict[str, object] | None,
) -> object:
    """Wraps _create_with_retry_one_key with key rotation: a
    _GroqKeyRateLimited signal tries the next configured key (a fresh
    call, not a resumption -- Groq's chat completions API is stateless
    per request, so retrying the identical request against a different
    key is safe); once no next key exists, converts to
    ProviderUnavailableError so llm/providers/fallback.py can fail over
    to Gemini. A transient-error ProviderUnavailableError raised
    directly by the one-key loop (retries exhausted) is NOT caught here
    -- rotating keys wouldn't plausibly fix a connection/timeout/5xx
    problem, so that path is unaffected by rotation, unchanged from
    before this feature existed.
    """
    while True:
        try:
            return _create_with_retry_one_key(
                model=model, messages=messages, tools=tools, response_format=response_format
            )
        except _GroqKeyRateLimited as exc:
            if _rotate_to_next_key():
                continue
            raise ProviderUnavailableError(str(exc)) from exc


def generate(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> AIMessage:
    groq_messages = [_message_to_dict(m) for m in messages]
    groq_tools = [_tool_to_groq(t) for t in tools] if tools else None
    response = _create_with_retry(
        model=model, messages=groq_messages, tools=groq_tools, response_format=None
    )
    return _response_to_ai_message(response, model=model)


def generate_structured(
    *,
    model: str,
    messages: list[BaseMessage],
    response_schema: type[T],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> StructuredResult[T]:
    groq_messages = [_message_to_dict(m) for m in messages]
    response_format: dict[str, object] = {
        "type": "json_schema",
        "json_schema": {
            "name": response_schema.__name__,
            "schema": response_schema.model_json_schema(),
        },
    }
    response = _create_with_retry(
        model=model, messages=groq_messages, tools=None, response_format=response_format
    )
    content = response.choices[0].message.content  # type: ignore[attr-defined]
    try:
        parsed = response_schema.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 -- re-raised with real context below
        raise ValueError(
            f"Groq did not return a valid {response_schema.__name__}: {content!r}"
        ) from exc
    return StructuredResult(
        parsed=parsed,
        usage_metadata=_usage_metadata(response.usage),  # type: ignore[attr-defined]
        provider=PROVIDER_NAME,
        model=model,
    )


def _stream_one_key(
    *,
    model: str,
    groq_messages: list[dict[str, object]],
    groq_tools: list[dict[str, object]] | None,
) -> Iterator[StreamChunk]:
    """The original retry-only-the-connection-and-first-chunk generator
    (see llm/providers/gemini.py::stream()'s docstring for the full
    reasoning) -- raises _GroqKeyRateLimited, not ProviderUnavailableError,
    for the two rate-limit-class cases. Because that can only happen
    inside the connection-establishment loop below, BEFORE this
    generator's first `yield`, the caller (stream()) can safely catch it
    and rotate keys: by construction, _GroqKeyRateLimited is never
    raised after a chunk has already been yielded to a client.
    """
    last_exception: Exception | None = None
    chunks: Iterator[object] | None = None
    first: object | None = None
    tool_choice: Literal["none", "auto"] = "none" if not groq_tools else "auto"
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            raw_stream = _client().chat.completions.create(
                model=model,
                messages=groq_messages,  # type: ignore[arg-type]
                tools=groq_tools,  # type: ignore[arg-type]
                tool_choice=tool_choice,
                stream=True,
            )
            chunks = iter(raw_stream)
            first = next(chunks, None)
            break
        except groq.RateLimitError as exc:
            raise _GroqKeyRateLimited(
                f"Groq quota exceeded calling model {model!r} (stream): {exc}"
            ) from exc
        except RETRYABLE_GROQ_EXCEPTIONS as exc:
            # NOTE: groq.InternalServerError is ALSO a groq.APIStatusError
            # subclass -- this clause MUST stay ordered before the bare
            # APIStatusError one below, same reasoning as _create_with_retry.
            last_exception = exc
            chunks = None
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except groq.APIStatusError as exc:
            _raise_for_request_too_large(exc, model=model, context=" (stream)")
    if chunks is None:
        assert last_exception is not None
        raise ProviderUnavailableError(
            f"Groq unreachable after {MAX_LLM_RETRIES} retries calling model {model!r} "
            f"(stream): {last_exception}"
        ) from last_exception

    last_usage: dict[str, int] | None = None
    remaining = itertools.chain([first], chunks) if first is not None else chunks
    for chunk in remaining:
        delta = chunk.choices[0].delta if chunk.choices else None  # type: ignore[attr-defined]
        if delta is not None and delta.content:
            yield StreamChunk(text=delta.content)
        x_groq = getattr(chunk, "x_groq", None)
        usage = getattr(x_groq, "usage", None) if x_groq is not None else None
        if usage is not None:
            last_usage = _usage_metadata(usage)
    if last_usage is not None:
        yield StreamChunk(text="", usage_metadata=last_usage, provider=PROVIDER_NAME, model=model)


def stream(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[StreamChunk]:
    """Wraps _stream_one_key with key rotation, the same before-first-
    token-only safety window _stream_one_key's own docstring establishes
    -- see _create_with_retry's docstring for the general rotation
    reasoning, identical here.
    """
    groq_messages = [_message_to_dict(m) for m in messages]
    groq_tools = [_tool_to_groq(t) for t in tools] if tools else None

    while True:
        try:
            yield from _stream_one_key(
                model=model, groq_messages=groq_messages, groq_tools=groq_tools
            )
            return
        except _GroqKeyRateLimited as exc:
            if _rotate_to_next_key():
                continue
            raise ProviderUnavailableError(str(exc)) from exc


def list_model_ids() -> list[str]:
    """Every model ID Groq's API currently reports as available to this
    account's key.
    """
    return [model.id for model in _client().models.list().data]


class GroqProvider:
    """Thin class wrapper -- see llm/providers/gemini.py::GeminiProvider's
    own docstring for why (this module's tested functions stay the
    patch targets, the class just delegates).
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
