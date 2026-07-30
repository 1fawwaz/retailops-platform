from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVICE_ROOT / ".env", extra="ignore")

    retailops_database_url: str
    stockpilot_base_url: str
    stockpilot_username: str
    stockpilot_password: str
    gemini_api_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    # Stage 6 backend hardening. Defaults are tuning knobs (any real
    # deployment overrides via env, same as every other Settings field),
    # not hardcoded business logic -- CLAUDE.md's "no hardcoded values"
    # rule is about values with no override path, not about a field
    # having a sensible default.
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    request_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
