import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base, JsonDict


class ToolCall(Base):
    """Every tool invocation, exactly as Task 2.3 specifies: execution_id,
    tool_call_id, args, raw response, provenance map, latency, status.
    `tool_call_id` is the primary key -- it's the identifier cited in
    `recommendations.evidence` and checked by the citation validator
    (Task 3.5) against the draft answer, so it has to be a stable,
    independently addressable value, not just an internal row id.
    """

    __tablename__ = "tool_calls"

    tool_call_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    agent_step_id: Mapped[int | None] = mapped_column(ForeignKey("agent_steps.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String)
    args: Mapped[JsonDict | None] = mapped_column(JSON)
    raw_response: Mapped[JsonDict | None] = mapped_column(JSON)
    provenance_map: Mapped[JsonDict | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
