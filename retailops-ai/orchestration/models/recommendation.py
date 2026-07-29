import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base


class Recommendation(Base):
    """One ranked, quantified recommendation from the Decision Engine
    (Task 4.3). `revenue_at_risk`, `inventory_cost`, and `confidence` are
    always computed in Python from cited tool results, never by an LLM --
    provenance is fixed per field (revenue_at_risk=predicted,
    inventory_cost=derived, confidence=derived, since revenue_at_risk
    descends from a forecast and provenance never upgrades) and so is
    attached statically at the API layer rather than stored per-row here,
    matching stockpilot-core's PRODUCT_PROVENANCE constant-dict pattern.
    `evidence` is the list of tool_call_id values the citation validator
    and a human reviewer can trace every number back to. `status` starts
    at "pending"; POST /recommendations/{id}/action moves it to
    accepted/rejected and records `note` and `decided_at` -- a decision
    log, not a feedback signal the system learns from (Task 4.3 is
    explicit that no accuracy score may be derived from this history).
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name="ck_recommendations_priority",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_recommendations_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"), index=True)
    sku: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    revenue_at_risk: Mapped[float] = mapped_column(Numeric(12, 2))
    inventory_cost: Mapped[float] = mapped_column(Numeric(12, 2))
    confidence: Mapped[float] = mapped_column(Float)
    risk_if_ignored: Mapped[str] = mapped_column(String)
    evidence: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="pending")
    note: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
