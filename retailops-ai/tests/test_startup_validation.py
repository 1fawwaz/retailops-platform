"""Stage 6 Task 6.4: llm/providers/startup.py::validate_configured_models().
Previously only informally verified live (twice, once passing and once
with a deliberately bad model ID); this is the mocked unit-test
coverage -- provider_for() is patched so no real network call happens.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from llm.providers.startup import ModelValidationError, validate_configured_models
from model_config import get_model_config


def _live_ids_for(config: object) -> dict[str, list[str]]:
    cfg = get_model_config()
    return {
        "gemini": [cfg.roles.planner.model, cfg.roles.retriever.model, cfg.roles.decision.model],
        "groq": [cfg.fallback.model],
    }


def test_validate_configured_models_passes_when_every_id_is_live() -> None:
    live_ids = _live_ids_for(get_model_config())

    def fake_provider_for(name: str) -> MagicMock:
        fake = MagicMock()
        fake.list_model_ids.return_value = live_ids[name]
        return fake

    with patch("llm.providers.startup.provider_for", side_effect=fake_provider_for):
        validate_configured_models()  # must not raise


def test_validate_configured_models_calls_list_model_ids_once_per_distinct_provider() -> None:
    live_ids = _live_ids_for(get_model_config())
    call_count: dict[str, int] = {}

    def fake_provider_for(name: str) -> MagicMock:
        call_count[name] = call_count.get(name, 0) + 1
        fake = MagicMock()
        fake.list_model_ids.return_value = live_ids[name]
        return fake

    with patch("llm.providers.startup.provider_for", side_effect=fake_provider_for):
        validate_configured_models()

    # All three roles share the "gemini" provider -- one call, not three.
    assert call_count == {"gemini": 1, "groq": 1}


def test_validate_configured_models_raises_naming_the_missing_id_and_provider() -> None:
    def fake_provider_for(name: str) -> MagicMock:
        fake = MagicMock()
        fake.list_model_ids.return_value = ["some-other-model"]
        return fake

    with (
        patch("llm.providers.startup.provider_for", side_effect=fake_provider_for),
        pytest.raises(ModelValidationError) as exc_info,
    ):
        validate_configured_models()

    message = str(exc_info.value)
    assert "roles.planner" in message
    assert "fallback" in message
    assert get_model_config().fallback.model in message
