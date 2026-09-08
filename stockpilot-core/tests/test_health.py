from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_200_ok() -> None:
    response = client.get("/health")

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "stockpilot-core"


def test_root_returns_200_ok() -> None:
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "StockPilot Core API" in data["service"]
    assert data["docs"] == "/docs"
