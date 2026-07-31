import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parent

# Matches GROQ_API_KEY_1, GROQ_API_KEY_2, ... -- an open-ended numbered
# scheme (llm/providers/groq.py rotates through however many are
# configured), not a fixed set of fields, so "GROQ_API_KEY_3,
# GROQ_API_KEY_4... may be added later" needs no code change.
_GROQ_API_KEY_PATTERN = re.compile(r"^GROQ_API_KEY_(\d+)$")


def _parse_dotenv_values(text: str) -> dict[str, str]:
    """Minimal KEY=VALUE line parser, quote-stripping only -- deliberately
    not a general .env parser (no multiline values, no export prefix);
    good enough for the flat key=value files this project's own
    .env.example uses, and self-contained rather than depending on
    python-dotenv's own value-merging behavior for a case (an open-ended
    numbered key set) pydantic-settings has no built-in source for.
    """
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            values[key] = value
    return values


def _load_groq_api_keys(env_file: Path) -> list[str]:
    """Collects every configured Groq API key, in rotation order.

    Position 1 comes from GROQ_API_KEY_1 if set, else from the bare
    GROQ_API_KEY (the original single-key field name this replaces, kept
    as an alias for position 1 so an existing single-key deployment's
    .env needs no change). GROQ_API_KEY_2, _3, ... are additional keys.
    Real process environment values (what a real deployment's platform
    env vars inject, e.g. Railway/Render) take precedence over the .env
    file for the same name, matching pydantic-settings' own precedence
    for every other field. Keys with an empty or missing value are
    skipped, not appended as an empty string.
    """
    raw: dict[str, str] = {}
    if env_file.is_file():
        raw.update(_parse_dotenv_values(env_file.read_text(encoding="utf-8")))
    for name, value in os.environ.items():
        if value.strip() and (name == "GROQ_API_KEY" or _GROQ_API_KEY_PATTERN.match(name)):
            raw[name] = value

    found: dict[int, str] = {}
    for name, value in raw.items():
        match = _GROQ_API_KEY_PATTERN.match(name)
        if match:
            found[int(match.group(1))] = value
    if 1 not in found and raw.get("GROQ_API_KEY"):
        found[1] = raw["GROQ_API_KEY"]

    return [found[n] for n in sorted(found)]


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
    # An ordered rotation pool, not a single value -- llm/providers/groq.py
    # rotates to the next key on a rate limit before failing over to
    # Gemini. Populated by _load_groq_api_keys (see its own docstring for
    # the GROQ_API_KEY/GROQ_API_KEY_N precedence), not a plain env-mapped
    # field, since pydantic-settings has no built-in "collect every
    # GROQ_API_KEY_N" source for an open-ended numbered scheme.
    groq_api_keys: list[str] = Field(
        default_factory=lambda: _load_groq_api_keys(SERVICE_ROOT / ".env")
    )
    # Stage 6 Task 6.4: provider abstraction + Groq fallback.
    # "primary/fallback order switchable via env var" per the spec --
    # flips WHICH of the two configured (provider, model) pairs is
    # tried first: "groq" (the default -- Groq is the project's default
    # primary provider, Gemini its default fallback, a deliberate
    # project decision) or "gemini" (used for the TRUST GATE's own
    # "fallback forced as primary" live verification, and for reverting
    # to Gemini-first if that's ever wanted operationally). Whichever
    # isn't primary becomes the fallback for that request.
    llm_primary_provider: Literal["gemini", "groq"] = "groq"


@lru_cache
def get_settings() -> Settings:
    return Settings()
