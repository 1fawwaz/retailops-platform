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

Stage 6: POST /agent/query also serves Server-Sent Events on the SAME
path and SAME request shape -- an `Accept: text/event-stream` header
switches it from the single blocking JSON response above to a live
stream of progress events (agent completions, the Planner's replan
judgement, citation-validator attempts, and the Decision Engine's own
answer streamed token-by-token), ending in one "done" event carrying
the identical fields the JSON response has. See
orchestration/executor.py::run_execution_streaming()'s own docstring for
the full event-shape reference; api/agent.py's only job here is framing
those same dicts as SSE wire format and JSON-encoding them (UUIDs need
`default=str`, nothing else about the payload shape changes).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_current_subject, get_db_session_factory, get_stockpilot_client
from api.errors import safe_error_body
from api.rate_limit import rate_limit
from api.timeouts import run_with_timeout
from clients.stockpilot import StockPilotClient
from orchestration.executor import (
    build_query_response_fields,
    run_execution,
    run_execution_streaming,
)
from orchestration.models.agent_step import AgentStep
from orchestration.models.base import JsonDict, JsonValue
from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from settings import get_settings

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


class ServingModel(BaseModel):
    """Stage 6 Task 6.4 trace requirement: which provider/model ACTUALLY
    served an agent's most recent call this execution -- can differ from
    config/models.yaml's configured primary once
    llm/providers/fallback.py's chain fires. Never the configured one;
    always read back from the persisted agent_steps row.
    """

    provider: str
    model: str


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
    serving: dict[str, ServingModel]

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
                    "serving": {"inventory": {"provider": "gemini", "model": "gemini-3.5-flash"}},
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
    provider: str | None
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


def _tool_ledger_entries(raw_entries: object) -> list[ToolLedgerEntry]:
    entries = cast(list[dict[str, object]], raw_entries)
    return [
        ToolLedgerEntry(
            tool_call_id=str(entry["tool_call_id"]),
            tool_name=str(entry["tool_name"]),
            status=str(entry["status"]),
            latency_ms=entry["latency_ms"] if isinstance(entry["latency_ms"], int) else None,
        )
        for entry in entries
    ]


def _serving_models(raw_serving: object) -> dict[str, ServingModel]:
    serving = cast(dict[str, dict[str, str]], raw_serving)
    return {
        agent_name: ServingModel(provider=served["provider"], model=served["model"])
        for agent_name, served in serving.items()
    }


def _query_response_from_fields(fields: dict[str, object]) -> AgentQueryResponse:
    """The shared response shape, built from
    orchestration/executor.py::build_query_response_fields()'s plain
    dict -- used for the ordinary JSON response AND (JSON-encoded, not
    as a Pydantic model) for the streaming path's final "done" SSE
    event, so both ways of calling this endpoint end up describing the
    same execution the same way.
    """
    return AgentQueryResponse(
        execution_id=cast(uuid.UUID, fields["execution_id"]),
        conversation_id=cast(uuid.UUID, fields["conversation_id"]),
        status=cast(str, fields["status"]),
        answer=cast("str | None", fields["answer"]),
        plan=cast("str | None", fields["plan"]),
        agent_results=cast(dict[str, str], fields["agent_results"]),
        tool_ledger=_tool_ledger_entries(fields["tool_ledger"]),
        provenance_map=cast(dict[str, str], fields["provenance_map"]),
        replan_rounds=cast(int, fields["replan_rounds"]),
        citation_attempts=cast(int, fields["citation_attempts"]),
        errors=cast(list[str], fields["errors"]),
        total_tokens=cast("int | None", fields["total_tokens"]),
        serving=_serving_models(fields["serving"]),
    )


def _sse_event(payload: dict[str, object]) -> str:
    event_type = str(payload.get("type", "message"))
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    payload: AgentQueryRequest,
    request: Request,
    _subject: str = Depends(get_current_subject),
    _rate_limit: None = Depends(rate_limit),
    client: StockPilotClient = Depends(get_stockpilot_client),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> AgentQueryResponse | StreamingResponse:
    timeout_seconds = get_settings().request_timeout_seconds

    if "text/event-stream" in request.headers.get("accept", ""):

        def event_source() -> Iterator[str]:
            deadline = time.monotonic() + timeout_seconds
            try:
                for event in run_execution_streaming(
                    payload.query,
                    client=client,
                    session_factory=session_factory,
                    conversation_id=payload.conversation_id,
                ):
                    if time.monotonic() > deadline:
                        yield _sse_event({"type": "error", **safe_error_body(TimeoutError())})
                        return
                    yield _sse_event(event)
            except Exception as exc:  # noqa: BLE001 -- the last line of defense for an
                # already-started SSE stream: headers are sent as 200 the moment the
                # first byte goes out, so a mid-stream exception can't become a
                # different HTTP status code the way api/errors.py's registered
                # handler does for the blocking JSON path -- an "error" event, safely
                # categorized and logged in full here, is the only way left to tell
                # a listening client anything went wrong instead of the connection
                # just silently truncating (confirmed live: this is exactly what
                # happened before this fix, during Stage 6's own SSE live testing).
                error_id = uuid.uuid4()
                logging.getLogger(__name__).error(
                    "Unhandled exception mid-stream on POST /agent/query "
                    "(error_id=%s, category=%s): %s",
                    error_id,
                    type(exc).__name__,
                    exc,
                    exc_info=exc,
                )
                yield _sse_event({"type": "error", **safe_error_body(exc, error_id=error_id)})

        return StreamingResponse(event_source(), media_type="text/event-stream")

    try:
        state = run_with_timeout(
            lambda: run_execution(
                payload.query,
                client=client,
                session_factory=session_factory,
                conversation_id=payload.conversation_id,
            ),
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=safe_error_body(exc)["detail"]
        ) from None
    fields = build_query_response_fields(state, session_factory)
    return _query_response_from_fields(fields)


@router.get("/execution/{execution_id}", response_model=ExecutionTraceResponse)
def get_execution_trace(
    execution_id: uuid.UUID,
    _subject: str = Depends(get_current_subject),
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
