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
from collections.abc import Callable, Mapping
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
from llm.providers.gemini import StructuredResult, generate, generate_structured
from model_config import get_model_config
from orchestration.models.agent_step import AgentStep
from prompts.loader import LoadedPrompt, load_prompt
from serialization import to_jsonable
from tools.derived_tools import build_derived_tools
from tools.stockpilot_tools import build_stockpilot_tools

MAX_TOOL_ROUNDS = 4

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


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    prompt: LoadedPrompt
    tools: tuple[StructuredTool, ...] = ()

    @property
    def model_id(self) -> str:
        roles = get_model_config().roles
        model_id = getattr(roles, self.role, None)
        if model_id is None:
            raise ValueError(f"Unknown model role '{self.role}'")
        return str(model_id)

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

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = generate(
                    model=self.model_id, messages=messages, tools=list(self.tools) or None
                )
                messages.append(response)
                if not response.tool_calls:
                    break
                for tool_call in response.tool_calls:
                    tool_calls_made.append(dict(tool_call))
                    messages.append(self._run_tool_call(tool_call, tools_by_name))
            else:
                # Exhausted the round cap with a tool still requested --
                # force a final text-only answer with what's gathered so far.
                messages.append(
                    HumanMessage(
                        content="You have reached the maximum number of tool calls for "
                        "this step. Answer now using only the information already "
                        "gathered."
                    )
                )
                response = generate(model=self.model_id, messages=messages, tools=None)
        except Exception as exc:  # noqa: BLE001 -- recorded below, then re-raised unchanged
            status = "failed"
            error = exc

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
                content = envelope(name, to_jsonable(result))
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
        self._write_agent_step(
            session_factory=session_factory,
            execution_id=execution_id,
            query=query,
            output=output,
            usage=usage,
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
                    model_id=self.model_id,
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
