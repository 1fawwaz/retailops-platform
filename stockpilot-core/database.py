from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from settings import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _normalized_database_url(url: str) -> str:
    """Managed Postgres providers (Railway, Heroku, Render, ...) hand out
    a bare "postgresql://" connection string -- the historical universal
    scheme, defaulting to the psycopg2 DBAPI SQLAlchemy has always shipped
    first. This project depends on psycopg (v3) only, per pyproject.toml,
    so a bare scheme fails with "No module named 'psycopg2'" the moment a
    real connection is attempted -- found live deploying to Railway.
    Local dev's own .env has always spelled this out explicitly
    ("postgresql+psycopg://"), which is why this was never hit before.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_normalized_database_url(get_settings().database_url))
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
