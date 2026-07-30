"""Stage 4 Task 4.3: POST /recommendations/{id}/action -- records a
user's accept/reject decision on a recommendation. Per spec: "This is a
decision LOG. Do not compute learning from it, do not claim the system
improves from it, do not derive an accuracy score from it." This route
does exactly one thing -- update status/note/decided_at -- and nothing
downstream reads this history to adjust future behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_db_session_factory
from orchestration.models.recommendation import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationActionRequest(BaseModel):
    status: Literal["accepted", "rejected"]
    note: str | None = None

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "accepted", "note": "Approved for reorder."}]}
    )


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    sku: str | None
    action: str
    priority: str
    reason: str
    revenue_at_risk: float
    inventory_cost: float
    confidence: float
    risk_if_ignored: str
    evidence: list[str]
    status: str
    note: str | None
    decided_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/{recommendation_id}/action", response_model=RecommendationResponse)
def record_recommendation_action(
    recommendation_id: uuid.UUID,
    request: RecommendationActionRequest,
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> RecommendationResponse:
    session = session_factory()
    try:
        recommendation = session.get(Recommendation, recommendation_id)
        if recommendation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No recommendation with id {recommendation_id}",
            )
        recommendation.status = request.status
        recommendation.note = request.note
        recommendation.decided_at = datetime.now(UTC)
        session.commit()
        return RecommendationResponse.model_validate(recommendation)
    finally:
        session.close()
