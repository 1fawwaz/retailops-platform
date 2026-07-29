"""Task 3.6: POST /agent/query and GET /agent/execution/{id} -- the HTTP
layer wrapping orchestration/executor.py::run_execution() (built ahead of
schedule in Task 3.4, whose own docstring already named this as its
eventual caller) and the graph's LangGraph orchestration (Task 3.2).

POST /agent/query returns the answer plus an inline execution trace
(plan, per-agent results, the tool ledger, provenance map, replan/citation
round counts, and any degradation errors -- CLAUDE.md invariant 2's
"full trace" fields, at the level a caller needs to judge THIS answer).
GET /agent/execution/{id} is the deeper, fully persisted trace: every
agent_steps and tool_calls row Postgres actually holds for that
execution, including raw tool responses and prompt hashes -- the two are
deliberately different depths, matching the spec's own two separate
bullets for this task.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_db_session_factory, get_stockpilot_client
from clients.stockpilot import StockPilotClient
from orchestration.executor import run_execution
from orchestration.models.agent_step import AgentStep
from orchestration.models.base import JsonDict, JsonValue
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    query: str = Field(min_length=1, description="The user's question or goal.")
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Continue an existing conversation thread. Omit to start a new one.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"query": "What should I reorder today?", "conversation_id": None}]
        }
    )


class ToolLedgerEntry(BaseModel):
    tool_call_id: str
    tool_name: str
    status: str
    latency_ms: int | None


class AgentQueryResponse(BaseModel):
    execution_id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    answer: str | None
    plan: str | None
    agent_results: dict[str, str]
    tool_ledger: list[ToolLedgerEntry]
    provenance_map: dict[str, str]
    replan_rounds: int
    citation_attempts: int
    errors: list[str]
    total_tokens: int | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "execution_id": "5d1a6a2e-3b1a-4b2a-8b1a-3b1a4b2a8b1a",
                    "conversation_id": "5d1a6a2e-3b1a-4b2a-8b1a-3b1a4b2a8b1b",
                    "status": "completed",
                    "answer": "SKU 85048 is at 12 units against a reorder point of 40 "
                    "(observed) -- reorder from supplier 7 today.",
                    "plan": "Check low-stock items, then supplier lead time.",
                    "agent_results": {"inventory": "..."},
                    "tool_ledger": [
                        {
                            "tool_call_id": "5d1a6a2e-3b1a-4b2a-8b1a-3b1a4b2a8b1c",
                            "tool_name": "get_low_stock",
                            "status": "success",
                            "latency_ms": 120,
                        }
                    ],
                    "provenance_map": {"quantity_on_hand": "observed"},
                    "replan_rounds": 1,
                    "citation_attempts": 1,
                    "errors": [],
                    "total_tokens": 4213,
                }
            ]
        }
    )


class AgentStepEntry(BaseModel):
    id: int
    agent_name: str
    iteration: int
    input: JsonDict | None
    output: JsonDict | None
    model_id: str | None
    prompt_version_hash: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    status: str
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ToolCallEntry(BaseModel):
    tool_call_id: uuid.UUID
    agent_step_id: int | None
    tool_name: str
    args: JsonDict | None
    # Raw tool responses can be a single object or a list of them (see
    # orchestration/models/base.py::JsonValue) -- Any beyond that is the
    # genuinely dynamic shape of whatever StockPilot returned, not a
    # shortcut around typing it properly.
    raw_response: JsonValue | None
    provenance_map: JsonDict | None
    latency_ms: int | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionTraceResponse(BaseModel):
    execution_id: uuid.UUID
    conversation_id: uuid.UUID | None
    query: str
    status: str
    plan: JsonDict | None
    final_answer: str | None
    provenance_map: JsonDict | None
    errors: JsonDict | None
    budgets: JsonDict | None
    total_tokens: int | None
    started_at: datetime
    completed_at: datetime | None
    agent_steps: list[AgentStepEntry]
    tool_calls: list[ToolCallEntry]


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    request: AgentQueryRequest,
    client: StockPilotClient = Depends(get_stockpilot_client),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> AgentQueryResponse:
    state = run_execution(
        request.query,
        client=client,
        session_factory=session_factory,
        conversation_id=request.conversation_id,
    )

    session = session_factory()
    try:
        execution = session.get(Execution, state["execution_id"])
    finally:
        session.close()
    assert execution is not None, "run_execution() always persists its own Execution row"
    assert execution.conversation_id is not None, "run_execution() always assigns a conversation"

    return AgentQueryResponse(
        execution_id=execution.id,
        conversation_id=execution.conversation_id,
        status=execution.status,
        answer=execution.final_answer,
        plan=state["plan"],
        agent_results=state["agent_results"],
        tool_ledger=[
            ToolLedgerEntry(
                tool_call_id=str(entry["tool_call_id"]),
                tool_name=str(entry["tool_name"]),
                status=str(entry["status"]),
                latency_ms=entry["latency_ms"] if isinstance(entry["latency_ms"], int) else None,
            )
            for entry in state["tool_ledger"]
        ],
        provenance_map=state["provenance_map"],
        replan_rounds=len(state["replan_history"]),
        citation_attempts=len(state["citation_failures"]),
        errors=state["errors"],
        total_tokens=execution.total_tokens,
    )


@router.get("/execution/{execution_id}", response_model=ExecutionTraceResponse)
def get_execution_trace(
    execution_id: uuid.UUID,
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> ExecutionTraceResponse:
    session = session_factory()
    try:
        execution = session.get(Execution, execution_id)
        if execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No execution with id {execution_id}",
            )
        steps = (
            session.query(AgentStep)
            .filter(AgentStep.execution_id == execution_id)
            .order_by(AgentStep.id)
            .all()
        )
        tool_calls = (
            session.query(ToolCall)
            .filter(ToolCall.execution_id == execution_id)
            .order_by(ToolCall.created_at)
            .all()
        )
        return ExecutionTraceResponse(
            execution_id=execution.id,
            conversation_id=execution.conversation_id,
            query=execution.query,
            status=execution.status,
            plan=execution.plan,
            final_answer=execution.final_answer,
            provenance_map=execution.provenance_map,
            errors=execution.errors,
            budgets=execution.budgets,
            total_tokens=execution.total_tokens,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            agent_steps=[AgentStepEntry.model_validate(step) for step in steps],
            tool_calls=[ToolCallEntry.model_validate(tc) for tc in tool_calls],
        )
    finally:
        session.close()
