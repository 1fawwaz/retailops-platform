import time

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_keepalive_endpoint() -> None:
    started = time.monotonic()
    response = client.get("/health")
    elapsed_ms = (time.monotonic() - started) * 1000

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "retailops-ai"
    assert "version" in data and isinstance(data["version"], str) and bool(data["version"])
    assert "timestamp" in data and isinstance(data["timestamp"], str) and bool(data["timestamp"])
    assert elapsed_ms < 50.0, f"Health endpoint exceeded 50ms (took {elapsed_ms:.2f}ms)"
