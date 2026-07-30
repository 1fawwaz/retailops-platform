"""Task 3.6: shared FastAPI dependencies for the API layer -- the ONLY
place routes construct a StockPilotClient or a DB session factory, so
every route shares the same long-lived client (auth-token caching,
circuit-breaker state) instead of rebuilding one per request.

Stage 6: also the home of get_current_subject, the auth.py-backed
dependency every non-health route requires (see auth.py's own docstring
for why this service validates StockPilot-issued tokens rather than
running a second user system).
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, sessionmaker

from auth import decode_bearer_subject
from clients.stockpilot import StockPilotClient
from database import get_session_factory
from settings import get_settings

_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    description=(
        "A JWT issued by StockPilot Core's own POST /auth/login -- this service has no "
        "login endpoint of its own."
    ),
)


def get_current_subject(token: str = Depends(_oauth2_scheme)) -> str:
    """The authenticated StockPilot user's email (the token's `sub`
    claim). Every non-health route depends on this; a missing, expired,
    or wrong-secret token yields a 401 before the route body runs.
    """
    try:
        return decode_bearer_subject(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@lru_cache
def get_stockpilot_client() -> StockPilotClient:
    """Process-lifetime singleton, same lru_cache pattern already used by
    database.py::get_engine and llm/providers/gemini.py::_client -- a
    StockPilotClient constructed fresh per request would lose its cached
    auth token and circuit-breaker failure count between requests.
    """
    settings = get_settings()
    return StockPilotClient(
        base_url=settings.stockpilot_base_url,
        username=settings.stockpilot_username,
        password=settings.stockpilot_password,
    )


def get_db_session_factory() -> sessionmaker[Session]:
    return get_session_factory()
