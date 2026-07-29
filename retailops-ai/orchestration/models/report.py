import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base, JsonDict


class Report(Base):
    """One rendered report (Task 4.2: ReorderReport, HealthReport,
    PerformanceReport; Task 4.4: persisted with inputs, outputs, duration,
    cost). `as_of_date` is set only in backtest mode -- when present, the
    API and the rendered markdown must both stamp "Historical simulation
    as of <date>. Not live monitoring." (Task 4.4); null means a live run.
    """

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('reorder', 'health', 'performance')",
            name="ck_reports_report_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    report_type: Mapped[str] = mapped_column(String)
    inputs: Mapped[JsonDict | None] = mapped_column(JSON)
    outputs: Mapped[JsonDict | None] = mapped_column(JSON)
    markdown: Mapped[str | None] = mapped_column(String)
    as_of_date: Mapped[date | None] = mapped_column(Date)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cost_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
