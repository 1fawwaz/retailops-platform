"""Stage 4 Task 4.3: tests for POST /recommendations/{id}/action."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import deps
from api.main import app
from orchestration.models.execution import Execution
from orchestration.models.recommendation import Recommendation

client = TestClient(app)


def _seed_recommendation(db_session: Session) -> uuid.UUID:
    execution = Execution(query="q", status="completed")
    db_session.add(execution)
    db_session.commit()

    recommendation = Recommendation(
        execution_id=execution.id,
        sku="85048",
        action="Reorder 40 units of 85048",
        priority="critical",
        reason="Stock is projected to run out before the supplier can replenish it.",
        revenue_at_risk=200.0,
        inventory_cost=80.0,
        confidence=0.5,
        risk_if_ignored="Two days of lost sales for this SKU.",
        evidence=["11111111-1111-1111-1111-111111111111"],
    )
    db_session.add(recommendation)
    db_session.commit()
    return recommendation.id


def test_record_recommendation_action_accepts_and_returns_the_updated_row(
    db_session: Session,
) -> None:
    recommendation_id = _seed_recommendation(db_session)
    app.dependency_overrides[deps.get_db_session_factory] = _factory(db_session)
    try:
        response = client.post(
            f"/recommendations/{recommendation_id}/action",
            json={"status": "accepted", "note": "Approved."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["note"] == "Approved."
    assert body["decided_at"] is not None
    assert body["revenue_at_risk"] == 200.0
    assert body["evidence"] == ["11111111-1111-1111-1111-111111111111"]


def test_record_recommendation_action_rejects_and_persists_the_note(
    db_session: Session,
) -> None:
    recommendation_id = _seed_recommendation(db_session)
    app.dependency_overrides[deps.get_db_session_factory] = _factory(db_session)
    try:
        response = client.post(
            f"/recommendations/{recommendation_id}/action",
            json={"status": "rejected", "note": "Not needed this cycle."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    row = db_session.get(Recommendation, recommendation_id)
    assert row is not None
    assert row.status == "rejected"
    assert row.note == "Not needed this cycle."
    assert row.decided_at is not None


def test_record_recommendation_action_returns_404_for_an_unknown_id(
    db_session: Session,
) -> None:
    app.dependency_overrides[deps.get_db_session_factory] = _factory(db_session)
    try:
        response = client.post(
            f"/recommendations/{uuid.uuid4()}/action",
            json={"status": "accepted", "note": None},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def _factory(db_session: Session) -> Callable[[], Callable[[], Session]]:
    return lambda: lambda: db_session
