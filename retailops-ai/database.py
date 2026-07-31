from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from settings import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _normalized_database_url(url: str) -> str:
    """See stockpilot-core/database.py::_normalized_database_url's own
    docstring -- identical fix, needed here for the same reason:
    managed Postgres providers (Railway, Heroku, Render, ...) hand out
    a bare "postgresql://" scheme, defaulting to a psycopg2 DBAPI this
    project doesn't install (psycopg v3 only, per pyproject.toml).
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_normalized_database_url(get_settings().retailops_database_url))
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def get_db() -> Generator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
