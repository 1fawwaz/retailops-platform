from collections.abc import Callable

import httpx2
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import deps
from api.main import app
from clients.stockpilot import StockPilotClient

client = TestClient(app)


def test_health_returns_200_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _stockpilot_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
        max_retries=0,
    )


def test_health_deep_reports_ok_when_both_dependencies_are_reachable(
    db_session: Session,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"status": "ok"})

    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(handler)
    try:
        response = client.get("/health/deep")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok", "stockpilot": "ok"}


def test_health_deep_degrades_without_a_500_when_stockpilot_is_unreachable(
    db_session: Session,
) -> None:
    """Task 3.6: RetailOps AI itself is still up when only StockPilot is
    down -- /health/deep must report that as "degraded", not fail the
    whole request, mirroring the same StockPilot-outage failure
    behaviour the agent graph itself uses (name the gap, don't crash).
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
    app.dependency_overrides[deps.get_stockpilot_client] = lambda: _stockpilot_client(handler)
    try:
        response = client.get("/health/deep")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "ok"
    assert "unreachable" in body["stockpilot"]
