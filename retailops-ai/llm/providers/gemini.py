"""The ONLY module allowed to import the Gemini SDK (CLAUDE.md section 7,
ARCHITECTURE RULES: "No provider SDK outside llm/providers/"). One
interface for the rest of the codebase: generate(), generate_structured(),
stream(). Messages and tools are LangChain primitives (SystemMessage,
HumanMessage, AIMessage, ToolMessage; langchain_core.tools.StructuredTool)
per CLAUDE.md's "LangChain (tools/messages primitives only)" rule --
nothing outside this module ever sees a google.genai type. No model name
is hardcoded here; every call site passes a model ID resolved from
config/models.yaml via model_config.get_model_config().

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
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

from google import genai
from google.genai import types
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from settings import get_settings

T = TypeVar("T", bound=BaseModel)

THOUGHT_SIGNATURES_KEY = "thought_signatures"


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    """generate_structured()'s return value. A bare parsed Pydantic
    instance would lose token usage, and callers that need to persist a
    full trace record (CLAUDE.md invariant 2: prompt/completion tokens
    per agent_steps row) can't do that from response.parsed alone.
    """

    parsed: T
    usage_metadata: dict[str, int]


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


def _response_to_ai_message(response: types.GenerateContentResponse) -> AIMessage:
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
    )


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
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        tools=[_tool_to_gemini(tool) for tool in tools] if tools else None,
    )
    response = _client().models.generate_content(model=model, contents=contents, config=config)
    return _response_to_ai_message(response)


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
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
    )
    response = _client().models.generate_content(model=model, contents=contents, config=config)
    parsed = response.parsed
    if not isinstance(parsed, response_schema):
        raise ValueError(
            f"Gemini did not return a valid {response_schema.__name__}: {response.text!r}"
        )
    return StructuredResult(parsed=parsed, usage_metadata=_usage_metadata(response))


def stream(
    *,
    model: str,
    messages: list[BaseMessage],
    tools: list[StructuredTool] | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[str]:
    """Yields text chunks as they arrive. Tool-calling is not supported
    mid-stream (a streamed response is assumed to be the final answer,
    not a step in a tool-use loop) -- callers that need tools should use
    generate() for those turns and reserve stream() for the final
    response to a user.
    """
    system_instruction, contents = _split_messages(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        tools=[_tool_to_gemini(tool) for tool in tools] if tools else None,
    )
    for chunk in _client().models.generate_content_stream(
        model=model, contents=contents, config=config
    ):
        if chunk.text:
            yield chunk.text


def list_model_ids() -> list[str]:
    """Every model name Gemini's API currently reports as available to
    this API key, with the "models/" prefix stripped so callers can
    compare directly against config/models.yaml's bare IDs.
    """
    client = _client()
    return [model.name.removeprefix("models/") for model in client.models.list() if model.name]
