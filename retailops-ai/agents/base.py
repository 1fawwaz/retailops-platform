"""Stage 3 Task 3.1: the six agents. Each is a prompt + a role (resolved
to a model ID via config/models.yaml) + a tool allow-list. The tool-less
agents (Planner, Report, Decision Engine) are tool-less BY DESIGN --
CLAUDE.md invariant 1: they can only reason over what the retrieval
agents already fetched, so they are structurally incapable of inventing
a number. Never give them tools "for convenience".

Agent.invoke() is a single agent's own bounded tool-calling loop (call
the model, execute any tool calls it requests, feed results back,
repeat up to MAX_TOOL_ROUNDS) -- distinct from the graph-level replan
loop (Task 3.3), which decides whether to re-invoke retrieval agents
across a whole execution, not within one agent's own turn.

Agent.invoke_structured() (Task 3.3) is the tool-less counterpart used
for the Planner's sufficiency judgement: one generate_structured() call,
no tool loop, since the only caller has no tools to call. Both methods
accept `iteration`, identifying which replan round (1 = the initial
fan-out) the call belongs to, persisted on the agent_steps row so a
single agent's calls across rounds stay distinguishable in the trace.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import ToolCall
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.envelope import envelope
from clients.stockpilot import StockPilotClient
from llm.providers.base import StructuredResult
from llm.providers.registry import generate, generate_structured, stream
from model_config import get_model_config
from orchestration.models.agent_step import AgentStep
from prompts.loader import LoadedPrompt, load_prompt
from serialization import to_jsonable
from tools.derived_tools import build_derived_tools
from tools.stockpilot_tools import build_stockpilot_tools

# A retriever gets at most this many tool rounds before the loop forces
# a text-only wrap-up. Lowered 4 -> 2 with the Stage 3 timeout fix,
# measured reason: this account's Groq org is capped at 8000 tokens/minute
# shared by all 4 keys (see config/models.yaml budgets), so each extra
# round costs a 2-18s 429 backoff. The Inventory agent routinely burned
# all 4 rounds re-fetching get_low_stock (each round's history trim shows
# it a fresh truncated view), taking 60-132s for ONE invocation -- but the
# first round already fetches the data the query needs, and the forced
# wrap-up (with the inventory prompt's output contract) writes it up as a
# SKU table. Two rounds + wrap-up is enough for a data-carrying answer;
# the graph-level replan loop (not more per-agent rounds) is the designed
# mechanism for gathering more evidence. MAX_TOOL_ROUNDS only affects
# tool-bearing retrieval agents -- report/decision are tool-less by design.
MAX_TOOL_ROUNDS = 2
# Post-cap forced-answer retries. After MAX_TOOL_ROUNDS the wrap-up tries
# to get a plain-text answer; a weak model can still request a tool there,
# and Groq hard-rejects tools + tool_choice=none with a 400 tool_use_failed
# that would otherwise kill the whole run. These rounds execute any tool the
# model still insists on and re-force text; on exhaustion the gathered
# envelopes become the answer (see _forced_envelope_answer). Deliberately
# small -- this is a last-resort path, not a way around the cap.
MAX_FORCED_ANSWER_ROUNDS = 2
# Tool-result and conversation size bounds are CONFIG-DRIVEN, in
# config/models.yaml budgets -- see the comments there for the measured
# reason (Groq 413 at 8000 TPM; the Inventory agent's tool loop fed
# 100-item list results back in full until a single request carried
# 39,815 tokens and every key rejected it). The old module constant
# MAX_TOOL_RESULT_ITEMS=200 was no cap at all for such responses.
_CHARS_PER_TOKEN = 3.0

T = TypeVar("T", bound=BaseModel)

INVENTORY_TOOL_NAMES = (
    "list_products",
    "get_product",
    "list_suppliers",
    "get_supplier",
    "get_stock",
    "get_low_stock",
    "get_dead_stock",
    "get_slow_movers",
    "get_inventory_valuation",
    # Stage 4 Task 4.1: local (non-HTTP) derived tool, tools/derived_tools.py.
    "rank_stockout_risk",
    # Stage 4 Task 4.5: ditto -- get_dead_stock alone has no cost field.
    "dead_stock_capital",
)
FORECAST_TOOL_NAMES = (
    "forecast_demand",
    "get_forecast_accuracy",
    # Stage 4 Task 4.1: local (non-HTTP) derived tools, tools/derived_tools.py.
    "days_of_cover",
    "reorder_timing",
)
ANALYTICS_TOOL_NAMES = (
    "get_revenue",
    "get_profit",
    "get_turnover",
    "get_abc",
    "get_top_products",
    "get_bottom_products",
    "get_period_comparison",
)


def _bounded_for_llm(jsonable: object) -> object:
    """Caps a list-shaped tool result to the configured
    budgets.max_tool_result_items before it's wrapped in an envelope and
    fed into an agent's own conversation history -- see
    config/models.yaml budgets for why. `jsonable` is expected to
    already be the output of to_jsonable() (plain dicts/lists/primitives
    only), so slicing a list here and wrapping it in a plain dict is
    always JSON-safe; a non-list result (a single-entity lookup, a
    scalar) passes through unchanged, since those are never what's
    caused this in practice.
    """
    max_items = get_model_config().budgets.max_tool_result_items
    if isinstance(jsonable, list) and len(jsonable) > max_items:
        return {
            "results": jsonable[:max_items],
            "_truncated": True,
            "_total_count": len(jsonable),
            "_note": (
                f"Showing the first {max_items} of {len(jsonable)} results. "
                "The remaining rows are not shown in this view; answer using "
                "the rows above."
            ),
        }
    return jsonable


def _conversation_chars(messages: Iterable[BaseMessage]) -> int:
    """Rough serialized-size measure of a message list, used by
    _bound_history's budget check. Message `.content` is a str for every
    message type this codebase builds (the big payload is always a
    ToolMessage's envelope string); tool_call args ride on AIMessage and
    are small enough that ignoring them is fine for a safety-net bound.
    """
    total = 0
    for message in messages:
        content = message.content
        total += len(content) if isinstance(content, str) else len(str(content))
    return total


def _bound_history(messages: list[BaseMessage], max_request_tokens: int) -> list[BaseMessage]:
    """Keeps any single LLM request under the configured
    budgets.max_request_tokens by trimming the OLDEST complete tool
    round(s) -- an AIMessage plus the ToolMessages that follow it, so a
    kept ToolMessage can never dangle without the tool_calls message
    that owns it. Never drops the system prompt, never drops the newest
    evidence just fetched, and never drops the user's query: the final
    generate() must always still see the question it is answering --
    dropping the HumanMessage left the Inventory agent answering an
    empty prompt and produced its "I'm ready to help with any
    inventory-related questions" non-answers (measured, Stage 3 timeout
    fix). This is what stops a retrieval agent that calls several
    list-shaped tools in one turn from accumulating a conversation that
    413s against a provider's per-request ceiling (measured: Groq 8000
    TPM).
    """
    budget_chars = int(max_request_tokens * _CHARS_PER_TOKEN)
    if _conversation_chars(messages) <= budget_chars:
        return messages

    system = messages[0]
    system_size = _conversation_chars([system])
    human = messages[1] if isinstance(messages[1], HumanMessage) else None
    human_size = _conversation_chars([human]) if human is not None else 0
    kept: list[BaseMessage] = []
    used = human_size
    for message in reversed(messages[1:]):
        if message is human:
            continue
        if not kept:
            kept.append(message)
            used += _conversation_chars([message])
            continue
        if used + _conversation_chars([message]) <= budget_chars - system_size:
            kept.append(message)
            used += _conversation_chars([message])
        else:
            break

    result = [system]
    if human is not None:
        result.append(human)
    result.extend(reversed(kept))
    while len(result) > 1 and isinstance(result[1], ToolMessage):
        result.pop(1)
    owned_ids = {
        call["id"]
        for message in result
        for call in (message.tool_calls if isinstance(message, AIMessage) else [])
    }
    while (
        len(result) > 1
        and isinstance(result[-1], ToolMessage)
        and result[-1].tool_call_id not in owned_ids
    ):
        result.pop()
    return result


def _retrieved_data_appendix(tool_messages: Sequence[BaseMessage]) -> str:
    """The deduped `<tool_result>` envelope appendix for a retriever's
    actual tool output. Empty string when there is nothing to carry (no
    successful tool results). Shared by _append_retrieved_data and the
    forced wrap-up's deterministic fallback so both render evidence
    identically.
    """
    seen: set[tuple[str, str]] = set()
    sections: list[str] = []
    for message in tool_messages:
        if not isinstance(message, ToolMessage):
            continue
        content = message.content
        if not isinstance(content, str) or not content.strip():
            continue
        if content.startswith("Error calling") or content.startswith("Error: no such tool"):
            continue
        name = message.name
        if name is None:
            continue
        key = (name, content)
        if key in seen:
            continue
        seen.add(key)
        sections.append(f'<tool_result tool="{name}">\n{content}\n</tool_result>')
    if not sections:
        return ""
    return "\n\n## Retrieved data\n\n" + "\n\n".join(sections)


def _forced_envelope_answer(tool_messages: Sequence[BaseMessage]) -> AIMessage:
    """Deterministic last resort for the forced wrap-up: when a weak model
    keeps requesting tools even after being told to answer in text (Groq
    rejects tools + tool_choice=none outright with a 400 tool_use_failed,
    so the wrap-up can't just retry), the retrieved envelopes ARE the
    honest answer -- verbatim tool data, never a fabricated number. The
    report agent downstream reads exactly this content.
    """
    appendix = _retrieved_data_appendix(tool_messages)
    body = (
        "The tool budget for this step was reached before the model produced a "
        "plain-text answer. The retrieved data below is reported verbatim rather "
        "than summarized."
    )
    return AIMessage(content=body + appendix)


def _append_retrieved_data(response: AIMessage, tool_messages: Sequence[BaseMessage]) -> AIMessage:
    """Stage 3 timeout fix: a retriever's returned/persisted output is the
    model's prose plus the actual retrieved tool envelopes, so the graph's
    Replan/Report always see the fetched evidence even when the retrieval
    model (measured: gpt-oss-120b via Groq is nondeterministic here)
    answers with a data-free refusal or drifts off-topic -- the data is in
    its context, but its prose cannot be relied on to carry it. Dedupes by
    (tool name, content) so a repeated tool call isn't echoed; tool error
    messages are never treated as data. Tool-less agents (report/decision)
    have nothing to append and pass through unchanged; invoke() only calls
    this when the agent actually made tool calls.

    `tool_messages` is the list of ToolMessages COLLECTED AS THEY WERE
    PRODUCED during the tool loop -- not the final conversation `messages`,
    which _bound_history() may have trimmed of every ToolMessage (measured:
    when one round makes several tool calls, the next round's trimming can
    drop them all as dangling, leaving the model with no evidence to answer
    and nothing for this helper to find). Collecting as produced makes the
    evidence survive regardless of history trimming.
    """
    appendix = _retrieved_data_appendix(tool_messages)
    if not appendix or appendix in str(response.content):
        return response
    return AIMessage(
        content=str(response.content) + appendix,
        additional_kwargs=response.additional_kwargs,
        tool_calls=response.tool_calls,
        usage_metadata=response.usage_metadata,
        response_metadata=response.response_metadata,
    )


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    prompt: LoadedPrompt
    tools: tuple[StructuredTool, ...] = ()

    @property
    def model_id(self) -> str:
        """The CONFIGURED primary model for this agent's role -- what's
        actually requested first. The model that actually served a given
        call can differ (llm/providers/fallback.py) and is recorded
        separately, per call, from the response itself -- see
        _persist_step()/_write_agent_step()'s own `provider`/`model_id`
        handling, not this property.
        """
        roles = get_model_config().roles
        role_config = getattr(roles, self.role, None)
        if role_config is None:
            raise ValueError(f"Unknown model role '{self.role}'")
        return str(role_config.model)

    def invoke(
        self,
        query: str,
        *,
        session_factory: Callable[[], Session],
        execution_id: uuid.UUID,
        iteration: int = 1,
    ) -> AIMessage:
        """Runs this agent once: a bounded tool-calling loop against the
        real LLM (or a forced text-only wrap-up if it's still requesting
        tools at the round cap), and persists exactly one agent_steps row
        for the whole call. `iteration` identifies which replan round
        (Task 3.3) this call belongs to -- 1 for the initial fan-out,
        2+ for a later targeted retry of this same agent.
        """
        started = time.monotonic()
        messages: list[BaseMessage] = [
            SystemMessage(content=self.prompt.text),
            HumanMessage(content=query),
        ]
        budget = get_model_config().budgets
        tools_by_name = {tool.name: tool for tool in self.tools}
        response: AIMessage | None = None
        status = "completed"
        error: Exception | None = None
        # The final response's own .tool_calls is empty by construction once
        # the loop below breaks (it only stops when the model requests no
        # more tools) -- this tracks every call made across all rounds, since
        # otherwise a successfully completed agent_steps row would look
        # indistinguishable from one that never used a tool at all.
        tool_calls_made: list[dict[str, object]] = []
        tool_messages: list[ToolMessage] = []

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                messages = _bound_history(messages, budget.max_request_tokens)
                response = generate(
                    model=self.model_id,
                    messages=messages,
                    tools=list(self.tools) or None,
                )
                messages.append(response)
                if not response.tool_calls:
                    break
                for tool_call in response.tool_calls:
                    tool_calls_made.append(dict(tool_call))
                    tool_result = self._run_tool_call(tool_call, tools_by_name)
                    tool_messages.append(tool_result)
                    messages.append(tool_result)
            else:
                # Exhausted the round cap with a tool still requested --
                # force a final text-only answer with what's gathered so far.
                # The instruction must be explicit that the tool results
                # already in the conversation ARE the data to report: on a
                # weak model (measured: gpt-oss-120b via Groq) a softer
                # "answer using the information already gathered" got
                # replied to with a hallucinated "I cannot retrieve that
                # data" refusal -- the data was in its context -- which
                # starved Replan and looped to the SSE deadline (Stage 3
                # timeout fix).
                messages.append(
                    HumanMessage(
                        content="You have reached the maximum number of tool calls for "
                        "this step. The tool results in the messages above are real, "
                        "retrieved data -- you DO have the information, and the answer "
                        "IS that data. Report it now: enumerate the relevant products "
                        "and numbers from those tool results. Do not say you lack data, "
                        "do not offer further help, and do not ask the user to narrow "
                        "the question."
                    )
                )
                messages = _bound_history(messages, budget.max_request_tokens)
                for _ in range(MAX_FORCED_ANSWER_ROUNDS):
                    # Tools stay attached here -- never tools=None. A weak
                    # model that still requests a tool with tool_choice=none
                    # makes Groq reject the request outright (400
                    # tool_use_failed, failed_generation embedded), which
                    # killed the whole run. With tools attached the call is
                    # valid either way: if the model still calls a tool we
                    # execute it and re-force text (bounded); if it never
                    # stops, the else branch below falls back to the gathered
                    # envelopes -- deterministic, never a fabricated number.
                    response = generate(
                        model=self.model_id,
                        messages=messages,
                        tools=list(self.tools) or None,
                    )
                    messages.append(response)
                    if not response.tool_calls:
                        break
                    for tool_call in response.tool_calls:
                        tool_calls_made.append(dict(tool_call))
                        tool_result = self._run_tool_call(tool_call, tools_by_name)
                        tool_messages.append(tool_result)
                        messages.append(tool_result)
                    messages.append(
                        HumanMessage(
                            content="You MUST now answer in plain text only. Do not call "
                            "any more tools -- the data you need is already in the "
                            "messages above."
                        )
                    )
                    messages = _bound_history(messages, budget.max_request_tokens)
                else:
                    response = _forced_envelope_answer(tool_messages)
        except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised unchanged
            status = "failed"
            error = exc

        if error is None and self.tools and tool_calls_made and response is not None:
            # Guarantee the fetched evidence survives into the returned and
            # persisted output regardless of the model's prose (see
            # _append_retrieved_data) -- Replan and Report read exactly this
            # content, and a data-free answer is what looped the graph to
            # the SSE deadline (Stage 3 timeout fix).
            response = _append_retrieved_data(response, tool_messages)

        latency_ms = int((time.monotonic() - started) * 1000)
        self._persist_step(
            session_factory=session_factory,
            execution_id=execution_id,
            query=query,
            response=response,
            tool_calls_made=tool_calls_made,
            status=status,
            error=error,
            latency_ms=latency_ms,
            iteration=iteration,
        )

        if error is not None:
            raise error
        assert response is not None
        return response

    def invoke_streaming(
        self,
        query: str,
        *,
        session_factory: Callable[[], Session],
        execution_id: uuid.UUID,
        iteration: int = 1,
        on_chunk: Callable[[str], None] | None = None,
    ) -> AIMessage:
        """Stage 6: a streaming counterpart to invoke(), for tool-less
        agents only -- report/decision are tool-less by design (invariant
        1), so there's no tool-calling loop to preserve here, unlike
        invoke() itself. Calls llm.providers.gemini.stream() instead of
        generate(); `on_chunk` (if given) fires once per text delta as it
        arrives. The caller decides what "arriving" means to it --
        orchestration/graph.py wires this to LangGraph's own
        get_stream_writer() when running inside the graph -- this module
        stays graph-agnostic on purpose, since Agent is also invoked
        directly OUTSIDE the graph (agents/decision.py's per-SKU
        pipeline, Task 4.3) where there is no LangGraph stream to write
        to at all. Persists exactly one agent_steps row, same as
        invoke() -- the accumulated full text is what's stored, not the
        individual chunks.
        """
        if self.tools:
            raise ValueError(
                f"invoke_streaming() is only for tool-less agents; {self.name!r} has tools"
            )
        started = time.monotonic()
        messages: list[BaseMessage] = [
            SystemMessage(content=self.prompt.text),
            HumanMessage(content=query),
        ]
        status = "completed"
        error: Exception | None = None
        text_parts: list[str] = []
        usage: dict[str, int] | None = None
        provider: str | None = None
        served_model: str | None = None

        try:
            for chunk in stream(model=self.model_id, messages=messages):
                if chunk.text:
                    text_parts.append(chunk.text)
                    if on_chunk is not None:
                        on_chunk(chunk.text)
                if chunk.usage_metadata is not None:
                    usage = chunk.usage_metadata
                if chunk.provider is not None:
                    provider = chunk.provider
                if chunk.model is not None:
                    served_model = chunk.model
        except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised unchanged
            status = "failed"
            error = exc

        latency_ms = int((time.monotonic() - started) * 1000)
        response = (
            AIMessage(
                content="".join(text_parts),
                usage_metadata=usage,
                response_metadata={"provider": provider, "model": served_model}
                if provider and served_model
                else {},
            )
            if error is None
            else None
        )
        self._persist_step(
            session_factory=session_factory,
            execution_id=execution_id,
            query=query,
            response=response,
            tool_calls_made=[],
            status=status,
            error=error,
            latency_ms=latency_ms,
            iteration=iteration,
        )

        if error is not None:
            raise error
        assert response is not None
        return response

    def invoke_structured(
        self,
        query: str,
        response_schema: type[T],
        *,
        session_factory: Callable[[], Session],
        execution_id: uuid.UUID,
        iteration: int = 1,
    ) -> T:
        """A single tool-less structured-output call: no tool-calling
        loop, since the only caller (the Planner's replan/sufficiency
        judgement, Task 3.3) is tool-less by design (invariant 1) --
        there is nothing to loop over. Persists exactly one agent_steps
        row, same as invoke(), with the parsed structured output as
        `output["parsed"]` instead of free text.
        """
        started = time.monotonic()
        messages: list[BaseMessage] = [
            SystemMessage(content=self.prompt.text),
            HumanMessage(content=query),
        ]
        status = "completed"
        error: Exception | None = None
        result: StructuredResult[T] | None = None

        try:
            result = generate_structured(
                model=self.model_id, messages=messages, response_schema=response_schema
            )
        except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised unchanged
            status = "failed"
            error = exc

        latency_ms = int((time.monotonic() - started) * 1000)
        output: dict[str, Any] = (
            {"parsed": result.parsed.model_dump(mode="json")} if result is not None else {}
        )
        if error is not None:
            output["error"] = str(error)
        self._write_agent_step(
            session_factory=session_factory,
            execution_id=execution_id,
            query=query,
            output=output,
            usage=result.usage_metadata if result is not None else None,
            provider=result.provider if result is not None else None,
            model_id=result.model if result is not None else self.model_id,
            status=status,
            latency_ms=latency_ms,
            iteration=iteration,
        )

        if error is not None:
            raise error
        assert result is not None
        return result.parsed

    def _run_tool_call(
        self, tool_call: ToolCall, tools_by_name: dict[str, StructuredTool]
    ) -> ToolMessage:
        name = str(tool_call["name"])
        call_id = str(tool_call["id"])
        tool = tools_by_name.get(name)
        if tool is None:
            content = f"Error: no such tool '{name}'"
        else:
            try:
                result = tool.invoke(tool_call["args"])
                content = envelope(name, _bounded_for_llm(to_jsonable(result)))
                max_chars = get_model_config().budgets.max_tool_result_chars
                if len(content) > max_chars:
                    content = (
                        content[:max_chars] + "\n...(truncated to the configured request-size "
                        "budget: this bounded view is expected by design; the "
                        "omitted rows are not included here)"
                    )
            except Exception as exc:  # noqa: BLE001 -- surfaced to the model as a tool error
                content = f"Error calling {name}: {exc}"
        return ToolMessage(content=content, tool_call_id=call_id, name=name)

    def _persist_step(
        self,
        *,
        session_factory: Callable[[], Session],
        execution_id: uuid.UUID,
        query: str,
        response: AIMessage | None,
        tool_calls_made: list[dict[str, object]],
        status: str,
        error: Exception | None,
        latency_ms: int,
        iteration: int,
    ) -> None:
        output: dict[str, Any] = {"tool_calls_made": tool_calls_made}
        if response is not None:
            output["content"] = response.content
        if error is not None:
            output["error"] = str(error)
        usage = response.usage_metadata if response is not None else None
        # Stage 6 Task 6.4: response_metadata carries which provider/model
        # ACTUALLY served this call (llm/providers/gemini.py::
        # _response_to_ai_message, groq.py's own equivalent, and
        # invoke_streaming()'s own AIMessage construction above all set
        # it) -- can differ from self.model_id once a fallback fires, so
        # this is read from the response, never assumed to be the
        # configured primary.
        metadata = response.response_metadata if response is not None else {}
        provider = metadata.get("provider") if metadata else None
        served_model = metadata.get("model") if metadata else None
        self._write_agent_step(
            session_factory=session_factory,
            execution_id=execution_id,
            query=query,
            output=output,
            usage=usage,
            provider=provider,
            model_id=served_model or self.model_id,
            status=status,
            latency_ms=latency_ms,
            iteration=iteration,
        )

    def _write_agent_step(
        self,
        *,
        session_factory: Callable[[], Session],
        execution_id: uuid.UUID,
        query: str,
        output: dict[str, Any],
        # langchain_core's AIMessage.usage_metadata is a UsageMetadata
        # TypedDict (with non-int fields like input_token_details) and
        # StructuredResult's is a plain dict[str, int] -- Mapping[str, Any]
        # is the real common shape of the two; only ["input_tokens"] and
        # ["output_tokens"] (always int in both) are ever read below.
        usage: Mapping[str, Any] | None,
        # Stage 6 Task 6.4: which provider/model actually served this
        # call. `provider` is None only when the call failed outright
        # (every provider in the chain was exhausted -- nobody "served"
        # it); `model_id` still falls back to self.model_id (the
        # configured primary) in that case, since a step row needs SOME
        # model_id and the configured one is the most honest choice
        # available when nothing actually served the request.
        provider: str | None,
        model_id: str,
        status: str,
        latency_ms: int,
        iteration: int,
    ) -> None:
        session = session_factory()
        try:
            session.add(
                AgentStep(
                    execution_id=execution_id,
                    agent_name=self.name,
                    iteration=iteration,
                    input={"query": query},
                    output=output,
                    provider=provider,
                    model_id=model_id,
                    prompt_version_hash=self.prompt.content_hash,
                    prompt_tokens=usage["input_tokens"] if usage else None,
                    completion_tokens=usage["output_tokens"] if usage else None,
                    latency_ms=latency_ms,
                    status=status,
                )
            )
            session.commit()
        finally:
            session.close()


def build_agents(
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> dict[str, Agent]:
    """One Agent per role, with the three retrieval agents bound to their
    StockPilot tool subset (built fresh for this execution_id, so every
    tool call they make is attributed to this run -- see Task 2.3).

    Stage 4 Task 4.1 adds a second tool source, tools/derived_tools.py's
    local (non-HTTP) computed tools -- merged into the same name->tool map
    as the 18 real endpoint tools, so INVENTORY_TOOL_NAMES/FORECAST_TOOL_NAMES
    can reference either kind interchangeably and every downstream
    consumer (the graph's tool-ownership attribution, the citation
    validator) keeps working unchanged.
    """
    all_tools = [
        *build_stockpilot_tools(client, session_factory, execution_id),
        *build_derived_tools(client, session_factory, execution_id),
    ]
    tools_by_name = {tool.name: tool for tool in all_tools}

    def subset(names: tuple[str, ...]) -> tuple[StructuredTool, ...]:
        return tuple(tools_by_name[name] for name in names)

    return {
        "planner": Agent(name="planner", role="planner", prompt=load_prompt("planner")),
        "inventory": Agent(
            name="inventory",
            role="retriever",
            prompt=load_prompt("inventory"),
            tools=subset(INVENTORY_TOOL_NAMES),
        ),
        "forecast": Agent(
            name="forecast",
            role="retriever",
            prompt=load_prompt("forecast"),
            tools=subset(FORECAST_TOOL_NAMES),
        ),
        "analytics": Agent(
            name="analytics",
            role="retriever",
            prompt=load_prompt("analytics"),
            tools=subset(ANALYTICS_TOOL_NAMES),
        ),
        # Report Agent has no dedicated role in config/models.yaml (only
        # planner/retriever/decision exist) -- it shares the "decision"
        # role's (strongest reasoning) model, since assembling a
        # structured report correctly from cited evidence is closer in
        # difficulty to the Decision Engine's synthesis than to
        # fast/cheap retrieval. A deliberate choice, not a silent default.
        "report": Agent(name="report", role="decision", prompt=load_prompt("report")),
        "decision": Agent(name="decision", role="decision", prompt=load_prompt("decision")),
    }
