import os

os.environ.setdefault("RETAILOPS_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("STOCKPILOT_BASE_URL", "http://localhost:8000")
os.environ.setdefault("STOCKPILOT_USERNAME", "test@example.com")
os.environ.setdefault("STOCKPILOT_PASSWORD", "test-password-not-for-production")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-for-production")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from orchestration.models import Base  # noqa: E402


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
