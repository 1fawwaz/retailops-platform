"""SEC-01: public auth endpoints are rate-limited per client IP."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from services.rate_limit import rate_limited, reset_rate_limits


def _make_limited_app(max_requests: int, window_seconds: int) -> FastAPI:
    app = FastAPI()
    limiter = rate_limited("test-bucket", max_requests=max_requests, window_seconds=window_seconds)

    @app.get("/ping")
    def ping(_: None = Depends(limiter)) -> dict[str, bool]:
        return {"ok": True}

    return app


def test_rate_limiter_allows_up_to_the_limit_then_429s() -> None:
    reset_rate_limits()
    app = _make_limited_app(max_requests=3, window_seconds=60)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/ping").status_code == 200
        limited = client.get("/ping")
        assert limited.status_code == 429
        assert limited.headers.get("Retry-After") == "60"


def test_rate_limiter_buckets_are_per_client_ip() -> None:
    reset_rate_limits()
    app = _make_limited_app(max_requests=1, window_seconds=60)
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200
        # Second hit from the same client is limited; a different client IP
        # (via the X-Forwarded-For-aware client host) is its own bucket.
        other = TestClient(app, client=("1.2.3.4", 50000))
        with other:
            assert other.get("/ping").status_code == 200


def test_login_rate_limited_end_to_end(client: TestClient) -> None:
    # Wiring check against the real router with its real default (30/5min).
    reset_rate_limits()
    statuses = [
        client.post("/auth/login", data={"username": "x@y.z", "password": "bad"}).status_code
        for _ in range(31)
    ]
    assert statuses[:30] == [401] * 30
    assert statuses[30] == 429


def test_register_rate_limited_end_to_end(client: TestClient) -> None:
    reset_rate_limits()
    statuses = [
        client.post(
            "/auth/register", json={"email": f"u{i}@example.com", "password": "hunter22!!"}
        ).status_code
        for i in range(11)
    ]
    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429
