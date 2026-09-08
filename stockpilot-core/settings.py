from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVICE_ROOT / ".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 60
    demo_user_email: str
    demo_user_password: str
    etl_max_transactions: int | None = None
    # docs/ARCHITECTURE.md § Environment Variables / CORS: "allow only the
    # known frontend origins" -- comma-separated, defaults to local dev
    # only so a missing env var in a real deployment fails closed
    # (no browser access), not open (allow-all).
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:3001"
    cors_allowed_origin_regex: str | None = None
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
