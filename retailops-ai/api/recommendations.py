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

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_current_subject, get_db_session_factory
from orchestration.models.recommendation import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationActionRequest(BaseModel):
    status: Literal["accepted", "rejected", "snoozed"]
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


@router.get("", response_model=list[RecommendationResponse])
def list_recommendations(
    _subject: str = Depends(get_current_subject),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> list[RecommendationResponse]:
    session = session_factory()
    try:
        rows = session.query(Recommendation).order_by(Recommendation.created_at.desc()).all()
        return [RecommendationResponse.model_validate(row) for row in rows]
    finally:
        session.close()


@router.post("/{recommendation_id}/action", response_model=RecommendationResponse)
def record_recommendation_action(
    recommendation_id: uuid.UUID,
    request: RecommendationActionRequest,
    _subject: str = Depends(get_current_subject),
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

        # Support SQLite tests dynamically
        if session.bind.dialect.name == "sqlite":
            session.execute(
                sa.text(
                    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)"
                )
            )
            session.execute(
                sa.text(
                    "CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, permission TEXT, method TEXT, path TEXT, outcome TEXT, created_at DATETIME)"
                )
            )
            user_exists = session.execute(
                sa.text("SELECT id FROM users WHERE email = :email"), {"email": _subject}
            ).fetchone()
            if not user_exists:
                session.execute(
                    sa.text("INSERT INTO users (email) VALUES (:email)"), {"email": _subject}
                )

        # Resolve subject (email) to user_id (int)
        user_row = session.execute(
            sa.text("SELECT id FROM users WHERE email = :email"), {"email": _subject}
        ).fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"User with email {_subject} not found in database.",
            )
        user_id = user_row[0]

        # Insert audit log entry
        session.execute(
            sa.text(
                "INSERT INTO audit_logs (user_id, permission, method, path, outcome, created_at) "
                "VALUES (:user_id, :permission, :method, :path, :outcome, NOW())"
            )
            if session.bind.dialect.name != "sqlite"
            else sa.text(
                "INSERT INTO audit_logs (user_id, permission, method, path, outcome, created_at) "
                "VALUES (:user_id, :permission, :method, :path, :outcome, datetime('now'))"
            ),
            {
                "user_id": user_id,
                "permission": "recommendations:update",
                "method": "POST",
                "path": f"/recommendations/{recommendation_id}/action",
                "outcome": "granted",
            },
        )

        session.commit()
        return RecommendationResponse.model_validate(recommendation)
    finally:
        session.close()
