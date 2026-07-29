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


@lru_cache
def get_settings() -> Settings:
    return Settings()
