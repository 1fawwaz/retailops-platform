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
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from collections.abc import Iterator
from typing import Literal, TypeVar

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

_thread_local = threading.local()


def _client() -> groq.Groq:
    """Cached per thread -- same defensive pattern as
    llm/providers/gemini.py::_client(), even though nothing has (yet)
    proven Groq's SDK shares the same cross-instance connection-pool
    gotcha google-genai has. Consistent, cheap, and avoids rediscovering
    that class of bug a second time if it turns out Groq's client isn't
    safe for concurrent use either.
    """
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = groq.Groq(api_key=get_settings().groq_api_key)
        _thread_local.client = client
    return client


def _reset_client_cache() -> None:
    """Test-only: see llm/providers/gemini.py::_reset_client_cache()."""
    _thread_local.client = None


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


def _create_with_retry(
    *,
    model: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    response_format: dict[str, object] | None,
) -> object:
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
            raise ProviderUnavailableError(
                f"Groq quota exceeded calling model {model!r}: {exc}"
            ) from exc
        except RETRYABLE_GROQ_EXCEPTIONS as exc:
            last_exception = exc
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    assert last_exception is not None
    raise ProviderUnavailableError(
        f"Groq unreachable after {MAX_LLM_RETRIES} retries calling model {model!r}: "
        f"{last_exception}"
    ) from last_exception


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


def stream(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[StreamChunk]:
    """Same retry-only-the-connection-and-first-chunk policy as
    llm/providers/gemini.py::stream() -- see that module's docstring for
    the full reasoning, identical here.
    """
    groq_messages = [_message_to_dict(m) for m in messages]
    groq_tools = [_tool_to_groq(t) for t in tools] if tools else None

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
            raise ProviderUnavailableError(
                f"Groq quota exceeded calling model {model!r} (stream): {exc}"
            ) from exc
        except RETRYABLE_GROQ_EXCEPTIONS as exc:
            last_exception = exc
            chunks = None
            if attempt < MAX_LLM_RETRIES:
                time.sleep(LLM_RETRY_BASE_DELAY_SECONDS * (2**attempt))
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
