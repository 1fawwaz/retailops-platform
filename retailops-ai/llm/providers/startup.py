"""Stage 6 Task 6.4: "On boot, the service validates every configured
model ID (all roles plus fallback) against its provider's model-list
endpoint and fails fast with a clear error naming the ID and provider if
any is missing." Wired into api/main.py as a FastAPI lifespan startup
step -- confirmed live that a bare TestClient(app) (this whole test
suite's own pattern, everywhere) never triggers lifespan/startup events
at all, only a real server boot or an explicit
`with TestClient(app) as client:` does, so this makes zero real network
calls during ordinary test runs.
"""

from __future__ import annotations

from llm.providers.registry import provider_for
from model_config import get_model_config


class ModelValidationError(Exception):
    """Raised when a configured model ID isn't present on its
    provider's own live model-list endpoint.
    """


def validate_configured_models() -> None:
    config = get_model_config()
    checks = [
        (config.roles.planner.provider, config.roles.planner.model, "roles.planner"),
        (config.roles.retriever.provider, config.roles.retriever.model, "roles.retriever"),
        (config.roles.decision.provider, config.roles.decision.model, "roles.decision"),
        (config.fallback.provider, config.fallback.model, "fallback"),
    ]
    # Cache each provider's own live list once -- multiple roles share
    # the same provider today (all three roles are "gemini"), no reason
    # to call list_model_ids() four times for it.
    live_ids_by_provider: dict[str, list[str]] = {}
    errors: list[str] = []
    for provider_name, model_id, config_path in checks:
        if provider_name not in live_ids_by_provider:
            live_ids_by_provider[provider_name] = provider_for(provider_name).list_model_ids()
        if model_id not in live_ids_by_provider[provider_name]:
            errors.append(
                f"{config_path}: model {model_id!r} not found on {provider_name}'s live "
                "model-list endpoint"
            )
    if errors:
        raise ModelValidationError(
            "config/models.yaml names a model ID that doesn't exist on its provider's "
            "live model list:\n" + "\n".join(f"  - {e}" for e in errors)
        )
