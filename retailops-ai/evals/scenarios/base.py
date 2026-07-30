"""Stage 5: shared types and helpers for the ten scenario definitions.

Every scenario's "seeded database state" is a scripted StockPilotClient
(MockTransport with hand-built JSON responses), not a live seeded
Postgres instance -- live stockpilot-core has been blocked by the same
machine-level pandas/Application Control policy issue since Stage 3
Task 3.3, so this repo has never had a working live-DB test path for
anything. This is the identical pattern every test in this codebase
already uses, applied at eval-suite scale, not a new adaptation invented
for this stage.

Every scenario's LLM behavior (generate()/generate_structured()) is also
scripted, not live Gemini -- CI has no GEMINI_API_KEY secret configured,
and this key's free tier has been unreliable all build (documented
repeatedly since Task 3.1/3.2). This makes the suite a REGRESSION test
of the surrounding machinery (grounding enforcement, replan wiring,
degradation, refusal formatting) given a plausible scripted model
decision -- not a live judge of actual model quality. Said plainly here
and in docs/adr/006-evaluation-strategy.md per CLAUDE.md's honesty rule,
not blurred.

Each scenario owns a `run()` callable rather than a rigid shared runner,
since scenario 04 (supplier-delay) needs to check `priority`, a Decision
Engine / Task 4.3 concept that only exists via
orchestration/workflows.py::run_inventory_health_workflow(), not the
general chat path every other scenario uses
(orchestration/executor.py::run_execution()) -- one rigid interface
across two genuinely different pipelines would be a worse fit than each
scenario building its own normalized ScenarioOutcome.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import httpx2
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from agents.base import ANALYTICS_TOOL_NAMES, FORECAST_TOOL_NAMES, INVENTORY_TOOL_NAMES
from agents.replan import ReplanJudgement
from clients.stockpilot import StockPilotClient
from llm.providers.gemini import StructuredResult
from orchestration.executor import run_execution
from orchestration.models.execution import Execution
from prompts.loader import load_prompt

AGENT_NAMES = ("planner", "inventory", "forecast", "analytics", "report", "decision")

_TOOL_NAME_TO_AGENT: dict[str, str] = {
    **{name: "inventory" for name in INVENTORY_TOOL_NAMES},
    **{name: "forecast" for name in FORECAST_TOOL_NAMES},
    **{name: "analytics" for name in ANALYTICS_TOOL_NAMES},
}


def agents_from_tool_ledger(tool_ledger: Sequence[dict[str, Any]]) -> frozenset[str]:
    """Which retrieval agents made at least one REAL tool call this
    execution -- the practical, honestly-implementable meaning of
    "routing correctness" given the graph's own topology
    (orchestration/graph.py): round 1 unconditionally fans out to all
    three retrieval agents regardless of relevance, so "which agents did
    the Planner choose" isn't a round-1 signal the current architecture
    produces. Which agents' tools were actually EXERCISED is.
    """
    agents: set[str] = set()
    for entry in tool_ledger:
        tool_name = str(entry.get("tool_name", ""))
        agent = _TOOL_NAME_TO_AGENT.get(tool_name)
        if agent:
            agents.add(agent)
    return frozenset(agents)


def ai_message(text: str) -> AIMessage:
    return AIMessage(
        content=text, usage_metadata={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10}
    )


def tool_call_message(name: str, args: dict[str, object]) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])


class ScriptedGenerate:
    """A generate() mock built from a per-agent list of AIMessage
    responses, dispatched by which round that agent is on -- the same
    prompt-dispatch + per-agent-call-counter pattern already established
    in tests/test_graph.py and tests/test_query_coverage.py, packaged
    here so ten scenario files don't each hand-roll it.
    """

    def __init__(
        self, responses: dict[str, list[AIMessage]], *, default: AIMessage | None = None
    ) -> None:
        self._responses = responses
        self._default = default or ai_message("no script for this agent/round")
        self._calls: dict[str, int] = {}
        self._prompt_to_name = {load_prompt(name).text: name for name in AGENT_NAMES}

    def __call__(self, *, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
        name = self._prompt_to_name[messages[0].content]
        self._calls[name] = self._calls.get(name, 0) + 1
        index = self._calls[name] - 1
        agent_responses = self._responses.get(name, [])
        if index < len(agent_responses):
            return agent_responses[index]
        return self._default


class ScriptedReplan:
    """A generate_structured() mock for the Planner's replan judgement --
    one ReplanJudgement per round, repeating the last one if more rounds
    happen than scripted. Defaults to always-sufficient (a single round),
    matching most scenarios; scenarios that need a real replan loop
    (Task 3.3's own milestone mechanism) pass more than one judgement.
    """

    def __init__(self, judgements: list[ReplanJudgement] | None = None) -> None:
        self._judgements = judgements or [
            ReplanJudgement(
                sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
            )
        ]
        self._count = 0

    def __call__(
        self, *, model: str, messages: list[Any], response_schema: Any
    ) -> StructuredResult[ReplanJudgement]:
        index = min(self._count, len(self._judgements) - 1)
        self._count += 1
        return StructuredResult(
            parsed=self._judgements[index],
            usage_metadata={"input_tokens": 3, "output_tokens": 3, "total_tokens": 6},
        )


@dataclass(frozen=True)
class ExpectedFact:
    description: str
    substring: str


@dataclass(frozen=True)
class ScenarioOutcome:
    """Normalized result every scenario's own run() produces, whichever
    pipeline (general chat vs a Task 4.4 workflow) it exercised.
    """

    final_text: str
    tool_agents: frozenset[str]
    replan_rounds: int
    citation_attempts: int
    citation_passed: bool
    total_tokens: int
    # Always 0.0 as returned by a scenario's own run() -- the runner
    # (evals/runner.py) measures real wall-clock time around the whole
    # run() call and overwrites this via dataclasses.replace(), so every
    # scenario's latency is measured the same way, not self-reported.
    latency_seconds: float = 0.0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    # The scenario's own "seeded database state" -- the runner builds the
    # StockPilotClient from this handler and passes it into `run`, so
    # every scenario's client construction (base_delay_seconds=0.0, no
    # real retry delay) is uniform, not repeated per scenario file.
    handler: Callable[[httpx2.Request], httpx2.Response]
    run: Callable[[StockPilotClient, Callable[[], Session]], ScenarioOutcome]
    expected_facts: list[ExpectedFact] = field(default_factory=list)
    expected_agents: frozenset[str] = frozenset()
    expect_replan: bool = False
    expect_refusal: bool = False
    forbidden_substrings: list[str] = field(default_factory=list)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def build_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
        max_retries=0,
    )


def run_chat_scenario(
    question: str,
    client: StockPilotClient,
    session_factory: Callable[[], Session],
    *,
    generate: ScriptedGenerate,
    replan: ScriptedReplan | None = None,
) -> ScenarioOutcome:
    """The shared runner for every scenario except 04-supplier-delay
    (which needs `priority`, only produced by
    orchestration/workflows.py::run_inventory_health_workflow(), not
    this general chat path) -- exercises the real
    orchestration/executor.py::run_execution(), the same thing
    POST /agent/query calls.
    """
    with (
        patch("agents.base.generate", side_effect=generate),
        patch("agents.base.generate_structured", side_effect=(replan or ScriptedReplan())),
    ):
        state = run_execution(question, client=client, session_factory=session_factory)

    session = session_factory()
    try:
        execution = session.get(Execution, state["execution_id"])
        total_tokens = execution.total_tokens if execution and execution.total_tokens else 0
    finally:
        session.close()

    citation_failures = state["citation_failures"]
    last_failure = citation_failures[-1] if citation_failures else None
    return ScenarioOutcome(
        final_text=state["final_answer"] or "",
        tool_agents=agents_from_tool_ledger(state["tool_ledger"]),
        replan_rounds=len(state["replan_history"]),
        citation_attempts=len(citation_failures),
        citation_passed=bool(last_failure["passed"]) if last_failure is not None else True,
        total_tokens=total_tokens,
        extra={"errors": state["errors"]},
    )
