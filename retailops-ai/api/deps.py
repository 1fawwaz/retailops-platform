"""Task 3.6: shared FastAPI dependencies for the API layer -- the ONLY
place routes construct a StockPilotClient or a DB session factory, so
every route shares the same long-lived client (auth-token caching,
circuit-breaker state) instead of rebuilding one per request.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from clients.stockpilot import StockPilotClient
from database import get_session_factory
from settings import get_settings


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
