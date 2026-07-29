import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from orchestration.models.base import Base


class EvalRun(Base):
    """One scenario's result from one run of the Stage 5 scenario suite
    (`make eval`). One row per (scenario_id, run). `is_baseline` flags the
    run recorded as the comparison point ("make eval runs the suite.
    Record the baseline. CI GATE: grounding must be 100%. Accuracy may not
    fall below baseline.") -- baseline comparison happens against whichever
    row has is_baseline=True for a given scenario_id, not by re-deriving
    a trend from the whole history.
    """

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String, index=True)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("executions.id"))
    grounding_pct: Mapped[float | None] = mapped_column(Float)
    factual_accuracy_pct: Mapped[float | None] = mapped_column(Float)
    routing_correct: Mapped[bool | None] = mapped_column(Boolean)
    replan_correct: Mapped[bool | None] = mapped_column(Boolean)
    refusal_correct: Mapped[bool | None] = mapped_column(Boolean)
    cost_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
