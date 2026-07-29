import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base, JsonDict


class Execution(Base):
    """One full run of the agent graph for a single query: entry -> Planner
    -> retrieval agents -> Report -> Decision Engine -> Validator -> end
    (Task 3.2). `plan`, `provenance_map`, `errors`, and `budgets` mirror the
    typed LangGraph state object's own fields, persisted so a run's summary
    doesn't only exist in-memory for the duration of one request.

    Per-agent detail (which agents ran, their inputs/outputs, model IDs,
    prompt hashes, token counts, timings) lives in `agent_steps`, not here --
    this row is the execution-level summary invariant 2 requires exists.
    """

    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'degraded')",
            name="ck_executions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    query: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="running")
    plan: Mapped[JsonDict | None] = mapped_column(JSON)
    final_answer: Mapped[str | None] = mapped_column(String)
    provenance_map: Mapped[JsonDict | None] = mapped_column(JSON)
    errors: Mapped[JsonDict | None] = mapped_column(JSON)
    budgets: Mapped[JsonDict | None] = mapped_column(JSON)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
