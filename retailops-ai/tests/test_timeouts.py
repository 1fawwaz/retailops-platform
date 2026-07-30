"""Stage 6 backend hardening: api/timeouts.py's run_with_timeout()."""

from __future__ import annotations

import time

import pytest

from api.timeouts import run_with_timeout


def test_run_with_timeout_returns_the_function_result_when_fast_enough() -> None:
    result = run_with_timeout(lambda: 1 + 1, timeout_seconds=5.0)
    assert result == 2


def test_run_with_timeout_raises_timeout_error_when_too_slow() -> None:
    def _slow() -> int:
        time.sleep(0.5)
        return 1

    with pytest.raises(TimeoutError):
        run_with_timeout(_slow, timeout_seconds=0.05)


def test_run_with_timeout_propagates_the_function_s_own_exception() -> None:
    def _boom() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_with_timeout(_boom, timeout_seconds=5.0)
