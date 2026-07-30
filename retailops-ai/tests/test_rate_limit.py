"""Stage 6 backend hardening: api/rate_limit.py's per-user in-memory
sliding window.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.rate_limit import check_rate_limit, reset_rate_limit_state


@pytest.fixture(autouse=True)
def _clean_rate_limit_state() -> None:
    reset_rate_limit_state()


def _settings(*, requests: int, window_seconds: int) -> SimpleNamespace:
    return SimpleNamespace(rate_limit_requests=requests, rate_limit_window_seconds=window_seconds)


def test_allows_requests_up_to_the_limit() -> None:
    with patch(
        "api.rate_limit.get_settings", return_value=_settings(requests=3, window_seconds=60)
    ):
        for _ in range(3):
            check_rate_limit("reader@example.com")  # must not raise


def test_rejects_the_request_over_the_limit() -> None:
    with patch(
        "api.rate_limit.get_settings", return_value=_settings(requests=2, window_seconds=60)
    ):
        check_rate_limit("reader@example.com")
        check_rate_limit("reader@example.com")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("reader@example.com")

    assert exc_info.value.status_code == 429
    assert "too many requests" in str(exc_info.value.detail).lower()


def test_limits_are_tracked_independently_per_subject() -> None:
    with patch(
        "api.rate_limit.get_settings", return_value=_settings(requests=1, window_seconds=60)
    ):
        check_rate_limit("reader-a@example.com")
        # A different subject gets its own budget, not a shared one.
        check_rate_limit("reader-b@example.com")
        with pytest.raises(HTTPException):
            check_rate_limit("reader-a@example.com")


def test_old_requests_fall_out_of_the_window_and_free_up_budget() -> None:
    with patch(
        "api.rate_limit.get_settings", return_value=_settings(requests=1, window_seconds=10)
    ):
        with patch("api.rate_limit.time.monotonic", return_value=1000.0):
            check_rate_limit("reader@example.com")
        with patch("api.rate_limit.time.monotonic", return_value=1000.0):
            with pytest.raises(HTTPException):
                check_rate_limit("reader@example.com")
        # Past the window: the earlier timestamp expires, budget resets.
        with patch("api.rate_limit.time.monotonic", return_value=1011.0):
            check_rate_limit("reader@example.com")  # must not raise
