"""The ONLY module that talks to StockPilot Core. Every other part of
retailops-ai reaches StockPilot exclusively through StockPilotClient --
see ADR 001 (environment/agent boundary) and CLAUDE.md's rule that
RetailOps AI must never query StockPilot's database directly or
re-implement its inventory/analytics/forecasting logic.

Typed: every method returns a model generated from the frozen contract
(clients/stockpilot_models.py, generated from
contracts/stockpilot-api/versions/v1.json -- `make generate-models`),
never a raw dict.

Resilient: retries with exponential backoff on transient network errors
and persistent 5xx responses; a circuit breaker stops hammering a
downed StockPilot once failures cross a threshold. 4xx responses are
never retried and never open the circuit -- they're normal, meaningful
answers (not found, validation error), not an outage.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from types import TracebackType
from typing import TypeVar

import httpx2
from pydantic import TypeAdapter

from clients.stockpilot_models import (
    AbcRow,
    DeadStockItem,
    ForecastAccuracy,
    InventoryValuation,
    PeriodComparison,
    ProductCreate,
    ProductDetail,
    ProductPerformanceRow,
    ProductRead,
    ProductUpdate,
    ProfitPeriod,
    RevenuePeriod,
    SkuForecast,
    SlowMoverItem,
    StockItem,
    SupplierCreate,
    SupplierDetail,
    SupplierRead,
    SupplierUpdate,
    Token,
    TurnoverRow,
    UserRead,
)

T = TypeVar("T")

RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx2.TimeoutException,
    httpx2.ConnectError,
    httpx2.ReadError,
)
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class StockPilotError(Exception):
    """Base class for all StockPilot client errors."""


class StockPilotUnavailableError(StockPilotError):
    """Raised when StockPilot could not be reached after retries, or the
    circuit breaker is open. Task 3.6's graceful-degradation behavior
    (typed ToolUnavailable, degrade rather than 500) is expected to catch
    this specifically -- it is never raised for a normal 4xx response.
    """


class CircuitBreakerOpenError(StockPilotUnavailableError):
    """Raised immediately, without attempting a request, while the
    circuit breaker is open.
    """


class CircuitBreaker:
    """Closed: requests flow normally. Open: after `failure_threshold`
    consecutive failures, every request is rejected immediately for
    `reset_timeout_seconds` rather than adding load to a downed
    dependency. Half-open: once the timeout elapses, one trial request is
    allowed through; success closes the breaker, failure re-opens it.
    """

    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._reset_timeout_seconds:
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._opened_at = time.monotonic()


def _retry_with_backoff(
    func: Callable[[], T],
    *,
    max_retries: int,
    base_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retries `func` on transient network errors and 5xx responses, with
    exponential backoff (base_delay * 2**attempt). 4xx responses raise
    immediately without retrying -- they won't succeed on retry, and
    retrying them would silently burn the caller's latency budget.
    """
    last_exception: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except RETRYABLE_EXCEPTIONS as exc:
            last_exception = exc
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code not in RETRYABLE_STATUS_CODES:
                raise
            last_exception = exc
        if attempt < max_retries:
            sleep(base_delay_seconds * (2**attempt))
    assert last_exception is not None
    raise last_exception


QueryParamValue = str | int | float | bool


def _params(**kwargs: QueryParamValue | date | None) -> dict[str, QueryParamValue]:
    """Drops None values (unset query params) and serializes dates."""
    result: dict[str, QueryParamValue] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        result[key] = value.isoformat() if isinstance(value, date) else value
    return result


class StockPilotClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
        circuit_breaker: CircuitBreaker | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._client = httpx2.Client(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )
        self._token: str | None = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> StockPilotClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _authenticate(self) -> None:
        response = self._client.post(
            "/auth/login",
            data={"username": self._username, "password": self._password},
        )
        response.raise_for_status()
        self._token = Token.model_validate(response.json()).access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, QueryParamValue] | None = None,
        json: object | None = None,
        auth_required: bool = True,
    ) -> httpx2.Response:
        if self._circuit_breaker.is_open:
            raise CircuitBreakerOpenError(f"Circuit breaker open for StockPilot ({path})")

        def _do_request() -> httpx2.Response:
            headers: dict[str, str] = {}
            if auth_required:
                if self._token is None:
                    self._authenticate()
                headers["Authorization"] = f"Bearer {self._token}"
            response = self._client.request(method, path, params=params, json=json, headers=headers)
            if auth_required and response.status_code == 401:
                self._authenticate()
                headers["Authorization"] = f"Bearer {self._token}"
                response = self._client.request(
                    method, path, params=params, json=json, headers=headers
                )
            response.raise_for_status()
            return response

        try:
            response = _retry_with_backoff(
                _do_request,
                max_retries=self._max_retries,
                base_delay_seconds=self._base_delay_seconds,
            )
        except RETRYABLE_EXCEPTIONS as exc:
            self._circuit_breaker.record_failure()
            raise StockPilotUnavailableError(f"StockPilot unreachable: {method} {path}") from exc
        except httpx2.HTTPStatusError as exc:
            if exc.response.status_code in RETRYABLE_STATUS_CODES:
                self._circuit_breaker.record_failure()
                raise StockPilotUnavailableError(
                    f"StockPilot returned {exc.response.status_code} after retries: {method} {path}"
                ) from exc
            raise
        self._circuit_breaker.record_success()
        return response

    # -- auth -----------------------------------------------------------

    def register_user(self, email: str, password: str) -> UserRead:
        response = self._request(
            "POST",
            "/auth/register",
            json={"email": email, "password": password},
            auth_required=False,
        )
        return UserRead.model_validate(response.json())

    # -- health -----------------------------------------------------------

    def health(self) -> dict[str, str]:
        response = self._request("GET", "/health", auth_required=False)
        result: dict[str, str] = response.json()
        return result

    # -- products ---------------------------------------------------------

    def list_products(self, *, limit: int = 100, offset: int = 0) -> list[ProductRead]:
        response = self._request("GET", "/products", params=_params(limit=limit, offset=offset))
        return TypeAdapter(list[ProductRead]).validate_python(response.json())

    def get_product(self, sku: str) -> ProductDetail:
        response = self._request("GET", f"/products/{sku}")
        return ProductDetail.model_validate(response.json())

    def create_product(self, data: ProductCreate) -> ProductRead:
        response = self._request(
            "POST", "/products", json=data.model_dump(mode="json", exclude_unset=True)
        )
        return ProductRead.model_validate(response.json())

    def update_product(self, sku: str, data: ProductUpdate) -> ProductRead:
        response = self._request(
            "PUT", f"/products/{sku}", json=data.model_dump(mode="json", exclude_unset=True)
        )
        return ProductRead.model_validate(response.json())

    def delete_product(self, sku: str) -> None:
        self._request("DELETE", f"/products/{sku}")

    # -- suppliers ----------------------------------------------------------

    def list_suppliers(self, *, limit: int = 100, offset: int = 0) -> list[SupplierRead]:
        response = self._request("GET", "/suppliers", params=_params(limit=limit, offset=offset))
        return TypeAdapter(list[SupplierRead]).validate_python(response.json())

    def get_supplier(self, supplier_id: int) -> SupplierDetail:
        response = self._request("GET", f"/suppliers/{supplier_id}")
        return SupplierDetail.model_validate(response.json())

    def create_supplier(self, data: SupplierCreate) -> SupplierRead:
        response = self._request(
            "POST", "/suppliers", json=data.model_dump(mode="json", exclude_unset=True)
        )
        return SupplierRead.model_validate(response.json())

    def update_supplier(self, supplier_id: int, data: SupplierUpdate) -> SupplierRead:
        response = self._request(
            "PUT",
            f"/suppliers/{supplier_id}",
            json=data.model_dump(mode="json", exclude_unset=True),
        )
        return SupplierRead.model_validate(response.json())

    def delete_supplier(self, supplier_id: int) -> None:
        self._request("DELETE", f"/suppliers/{supplier_id}")

    # -- inventory ----------------------------------------------------------

    def get_stock(
        self,
        *,
        category: str | None = None,
        low_stock: bool | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockItem]:
        response = self._request(
            "GET",
            "/inventory/stock",
            params=_params(
                category=category, low_stock=low_stock, search=search, limit=limit, offset=offset
            ),
        )
        return TypeAdapter(list[StockItem]).validate_python(response.json())

    def get_low_stock(
        self, *, category: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[StockItem]:
        response = self._request(
            "GET",
            "/inventory/low-stock",
            params=_params(category=category, limit=limit, offset=offset),
        )
        return TypeAdapter(list[StockItem]).validate_python(response.json())

    def get_dead_stock(
        self, *, days: int = 90, limit: int = 100, offset: int = 0
    ) -> list[DeadStockItem]:
        response = self._request(
            "GET",
            "/inventory/dead-stock",
            params=_params(days=days, limit=limit, offset=offset),
        )
        return TypeAdapter(list[DeadStockItem]).validate_python(response.json())

    def get_slow_movers(
        self,
        *,
        window_days: int = 90,
        velocity_threshold: float = 0.2,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SlowMoverItem]:
        response = self._request(
            "GET",
            "/inventory/slow-movers",
            params=_params(
                window_days=window_days,
                velocity_threshold=velocity_threshold,
                limit=limit,
                offset=offset,
            ),
        )
        return TypeAdapter(list[SlowMoverItem]).validate_python(response.json())

    def get_inventory_valuation(self, *, category: str | None = None) -> InventoryValuation:
        response = self._request("GET", "/inventory/valuation", params=_params(category=category))
        return InventoryValuation.model_validate(response.json())

    # -- analytics ----------------------------------------------------------

    def get_revenue(
        self,
        *,
        group_by: str = "day",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[RevenuePeriod]:
        response = self._request(
            "GET",
            "/analytics/revenue",
            params=_params(group_by=group_by, start_date=start_date, end_date=end_date),
        )
        return TypeAdapter(list[RevenuePeriod]).validate_python(response.json())

    def get_profit(
        self,
        *,
        group_by: str = "day",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ProfitPeriod]:
        response = self._request(
            "GET",
            "/analytics/profit",
            params=_params(group_by=group_by, start_date=start_date, end_date=end_date),
        )
        return TypeAdapter(list[ProfitPeriod]).validate_python(response.json())

    def get_turnover(
        self, *, start_date: date | None = None, end_date: date | None = None
    ) -> list[TurnoverRow]:
        response = self._request(
            "GET",
            "/analytics/turnover",
            params=_params(start_date=start_date, end_date=end_date),
        )
        return TypeAdapter(list[TurnoverRow]).validate_python(response.json())

    def get_abc(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        a_threshold: float = 0.8,
        b_threshold: float = 0.95,
    ) -> list[AbcRow]:
        response = self._request(
            "GET",
            "/analytics/abc",
            params=_params(
                start_date=start_date,
                end_date=end_date,
                a_threshold=a_threshold,
                b_threshold=b_threshold,
            ),
        )
        return TypeAdapter(list[AbcRow]).validate_python(response.json())

    def get_top_products(
        self,
        *,
        metric: str = "revenue",
        limit: int = 10,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ProductPerformanceRow]:
        response = self._request(
            "GET",
            "/analytics/top-products",
            params=_params(metric=metric, limit=limit, start_date=start_date, end_date=end_date),
        )
        return TypeAdapter(list[ProductPerformanceRow]).validate_python(response.json())

    def get_bottom_products(
        self,
        *,
        metric: str = "revenue",
        limit: int = 10,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ProductPerformanceRow]:
        response = self._request(
            "GET",
            "/analytics/bottom-products",
            params=_params(metric=metric, limit=limit, start_date=start_date, end_date=end_date),
        )
        return TypeAdapter(list[ProductPerformanceRow]).validate_python(response.json())

    def get_period_comparison(
        self,
        *,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
    ) -> PeriodComparison:
        response = self._request(
            "GET",
            "/analytics/period-comparison",
            params=_params(
                period1_start=period1_start,
                period1_end=period1_end,
                period2_start=period2_start,
                period2_end=period2_end,
            ),
        )
        return PeriodComparison.model_validate(response.json())

    # -- forecast ----------------------------------------------------------

    def forecast_demand(self, skus: list[str], horizon_days: int) -> list[SkuForecast]:
        response = self._request(
            "POST",
            "/forecast/demand",
            json={"skus": skus, "horizon_days": horizon_days},
        )
        return TypeAdapter(list[SkuForecast]).validate_python(response.json())

    def get_forecast_accuracy(self) -> ForecastAccuracy:
        response = self._request("GET", "/forecast/accuracy")
        return ForecastAccuracy.model_validate(response.json())
