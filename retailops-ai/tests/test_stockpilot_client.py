from collections.abc import Callable

import httpx2
import pytest

from clients.stockpilot import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    StockPilotClient,
    StockPilotUnavailableError,
)
from clients.stockpilot_models import ProductRead

Handler = Callable[[httpx2.Request], httpx2.Response]


def _login_response() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "test-token", "token_type": "bearer"})


def _product_read_payload(sku: str = "85048") -> dict[str, object]:
    return {
        "sku": sku,
        "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
        "category_id": 3,
        "supplier_id": 7,
        "unit_cost": 2.15,
        "reorder_point": 120,
        "safety_stock": 40,
        "created_at": "2026-01-01T00:00:00Z",
        "_provenance": {
            "sku": "observed",
            "description": "observed",
            "unit_cost": "derived",
            "reorder_point": "derived",
            "safety_stock": "derived",
        },
        "_derivation_ref": {},
    }


def _client(handler: Handler, **kwargs: object) -> StockPilotClient:
    return StockPilotClient(
        base_url="http://stockpilot.test",
        username="reader@example.com",
        password="hunter22!!",
        transport=httpx2.MockTransport(handler),
        base_delay_seconds=0.0,
        **kwargs,  # type: ignore[arg-type]
    )


def test_list_products_authenticates_then_returns_typed_models() -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/auth/login":
            return _login_response()
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx2.Response(200, json=[_product_read_payload()])

    with _client(handler) as client:
        products = client.list_products()

    assert calls == ["POST /auth/login", "GET /products"]
    assert len(products) == 1
    assert isinstance(products[0], ProductRead)
    assert products[0].sku == "85048"
    assert products[0].unit_cost == 2.15


def test_401_triggers_reauthentication_and_retries_once() -> None:
    login_calls = 0
    product_calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal login_calls, product_calls
        if request.url.path == "/auth/login":
            login_calls += 1
            return _login_response()
        product_calls += 1
        if product_calls == 1:
            return httpx2.Response(401, json={"detail": "token expired"})
        return httpx2.Response(200, json=[_product_read_payload()])

    with _client(handler) as client:
        products = client.list_products()

    assert login_calls == 2
    assert product_calls == 2
    assert len(products) == 1


def test_retries_on_503_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        if request.url.path == "/auth/login":
            return _login_response()
        attempts += 1
        if attempts < 3:
            return httpx2.Response(503, json={"detail": "unavailable"})
        return httpx2.Response(200, json=[_product_read_payload()])

    with _client(handler, max_retries=3) as client:
        products = client.list_products()

    assert attempts == 3
    assert len(products) == 1


def test_exhausted_retries_raise_stockpilot_unavailable_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        return httpx2.Response(503, json={"detail": "unavailable"})

    with _client(handler, max_retries=2) as client, pytest.raises(StockPilotUnavailableError):
        client.list_products()


def test_404_is_not_retried_and_propagates_as_http_status_error() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        if request.url.path == "/auth/login":
            return _login_response()
        attempts += 1
        return httpx2.Response(404, json={"detail": "Product not found"})

    with _client(handler, max_retries=3) as client:
        with pytest.raises(httpx2.HTTPStatusError) as exc_info:
            client.get_product("NOPE")

    assert attempts == 1
    assert exc_info.value.response.status_code == 404


def test_circuit_breaker_opens_after_threshold_and_rejects_immediately() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        if request.url.path == "/auth/login":
            return _login_response()
        attempts += 1
        return httpx2.Response(503, json={"detail": "unavailable"})

    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=999)
    with _client(handler, max_retries=0, circuit_breaker=breaker) as client:
        with pytest.raises(StockPilotUnavailableError):
            client.list_products()
        with pytest.raises(StockPilotUnavailableError):
            client.list_products()

        attempts_before_open = attempts
        with pytest.raises(CircuitBreakerOpenError):
            client.list_products()

    assert attempts == attempts_before_open


def test_health_check_does_not_authenticate() -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        return httpx2.Response(200, json={"status": "ok"})

    with _client(handler) as client:
        result = client.health()

    assert calls == ["/health"]
    assert result == {"status": "ok"}


def test_delete_product_returns_none_on_204() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/login":
            return _login_response()
        assert request.method == "DELETE"
        return httpx2.Response(204)

    with _client(handler) as client:
        client.delete_product("85048")
