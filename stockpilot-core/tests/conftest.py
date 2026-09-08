import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-key-not-for-production"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["DEMO_USER_EMAIL"] = "demo@retailops.local"
os.environ["DEMO_USER_PASSWORD"] = "test-demo-password"

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.main import app  # noqa: E402
from database import get_db  # noqa: E402
from models.base import Base  # noqa: E402
from services.rate_limit import reset_rate_limits  # noqa: E402
from services.rbac import seed_default_roles  # noqa: E402


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
    seed_default_roles(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    def _override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # SEC-01: each test starts with a clean rate-limit store so hits in
    # one test never 429 a later test in the same process.
    reset_rate_limits()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
