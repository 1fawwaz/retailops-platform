"""llm/providers/key_rotation.py::KeyRotationPool -- the shared rotation
state both llm/providers/groq.py and llm/providers/gemini.py delegate to.
Provider-specific behavior (which SDK exception triggers a rotation, the
retry-with-backoff loop for transient errors) is covered by each
provider's own test file; this file only covers the pool's own
index/lock/logging contract in isolation.
"""

from __future__ import annotations

import logging

import pytest

from llm.providers.key_rotation import KeyRotationPool


def _pool(provider_label: str = "TestProvider") -> KeyRotationPool:
    return KeyRotationPool(provider_label=provider_label, logger=logging.getLogger("test-pool"))


def test_starts_at_index_zero() -> None:
    assert _pool().current_index == 0


def test_rotate_advances_the_index_when_a_next_key_exists() -> None:
    pool = _pool()
    assert pool.rotate(key_count=2) is True
    assert pool.current_index == 1


def test_rotate_returns_false_and_stays_put_when_already_on_the_last_key() -> None:
    pool = _pool()
    assert pool.rotate(key_count=1) is False
    assert pool.current_index == 0


def test_rotate_cascades_through_every_key_before_returning_false() -> None:
    pool = _pool()
    assert pool.rotate(key_count=4) is True
    assert pool.current_index == 1
    assert pool.rotate(key_count=4) is True
    assert pool.current_index == 2
    assert pool.rotate(key_count=4) is True
    assert pool.current_index == 3
    assert pool.rotate(key_count=4) is False
    assert pool.current_index == 3


def test_reset_returns_the_index_to_zero() -> None:
    pool = _pool()
    pool.rotate(key_count=3)
    pool.rotate(key_count=3)
    assert pool.current_index == 2

    pool.reset()

    assert pool.current_index == 0


def test_rotate_logs_the_key_index_never_a_secret_value(caplog: pytest.LogCaptureFixture) -> None:
    pool = _pool(provider_label="Groq")
    with caplog.at_level("WARNING", logger="test-pool"):
        pool.rotate(key_count=2)

    assert "Groq API key #1" in caplog.text
    assert "rotating to key #2 of 2 configured" in caplog.text


def test_exhaustion_logs_a_distinct_terminal_message(caplog: pytest.LogCaptureFixture) -> None:
    pool = _pool(provider_label="Gemini")
    with caplog.at_level("WARNING", logger="test-pool"):
        pool.rotate(key_count=1)

    assert "Gemini API key #1" in caplog.text
    assert "all 1 configured Gemini API key(s) exhausted" in caplog.text


def test_two_pools_are_independent() -> None:
    """A separate KeyRotationPool per provider (as groq.py and gemini.py
    each construct their own module-level instance) must not share state.
    """
    groq_pool = _pool("Groq")
    gemini_pool = _pool("Gemini")

    groq_pool.rotate(key_count=3)
    groq_pool.rotate(key_count=3)

    assert groq_pool.current_index == 2
    assert gemini_pool.current_index == 0
