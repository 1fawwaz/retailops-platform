import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base, JsonDict


class AgentStep(Base):
    """One invocation of one of the six agents (Task 3.1: planner,
    inventory, forecast, analytics, report, decision) within an execution.
    `iteration` tracks the replan loop (Task 3.3) -- the Planner's
    sufficiency judgement is persisted here as a structured `output`, e.g.
    {"sufficient": false, "missing": [...], "next_action": "...",
    "iteration": 1}, per that task's explicit example. `model_id` and
    `prompt_version_hash` are per-step because different agents (and
    different replan iterations of the same agent) can use different
    model roles (config/models.yaml) and prompt versions.
    """

    __tablename__ = "agent_steps"
    __table_args__ = (
        CheckConstraint(
            "agent_name IN ('planner', 'inventory', 'forecast', 'analytics', 'report', 'decision')",
            name="ck_agent_steps_agent_name",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_agent_steps_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    input: Mapped[JsonDict | None] = mapped_column(JSON)
    output: Mapped[JsonDict | None] = mapped_column(JSON)
    model_id: Mapped[str | None] = mapped_column(String)
    prompt_version_hash: Mapped[str | None] = mapped_column(String)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
