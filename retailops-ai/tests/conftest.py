import os

os.environ.setdefault("RETAILOPS_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("STOCKPILOT_BASE_URL", "http://localhost:8000")
os.environ.setdefault("STOCKPILOT_USERNAME", "test@example.com")
os.environ.setdefault("STOCKPILOT_PASSWORD", "test-password-not-for-production")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-for-production")
os.environ.setdefault("GROQ_API_KEY", "test-key-not-for-production")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-production-0123456789")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

from collections.abc import Generator  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from orchestration.models import Base  # noqa: E402
from settings import get_settings  # noqa: E402


def mint_test_token(subject: str = "test@example.com") -> str:
    """A JWT shaped exactly like one StockPilot's own /auth/login would
    issue (see auth.py's docstring) -- signed with this test process's
    own JWT_SECRET/JWT_ALGORITHM env defaults above, decodable by
    auth.py::decode_bearer_subject the same way a real StockPilot token
    would be.
    """
    settings = get_settings()
    payload = {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=60)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_test_token()}"}


@pytest.fixture(autouse=True)
def _default_auth_override() -> Generator[None]:
    """Every route test that goes through FastAPI's TestClient gets a
    free, valid "authenticated as test@example.com" identity by default
    -- the same app.dependency_overrides mechanism every existing route
    test already uses for get_db_session_factory/get_stockpilot_client,
    just applied here once instead of touching every test file's call
    sites. A test that specifically wants to prove auth is REALLY
    enforced (a real 401 with no token, a real 200 with a genuinely
    minted token) pops this override at the top of its own test body;
    the pop is undone here regardless of how that test exits.
    """
    from api import deps
    from api.main import app

    app.dependency_overrides[deps.get_current_subject] = lambda: "test@example.com"
    yield
    app.dependency_overrides.pop(deps.get_current_subject, None)


@pytest.fixture(autouse=True)
def _clear_rate_limit_state() -> Generator[None]:
    """api/rate_limit.py's sliding window is process-lifetime, in-memory,
    global module state -- every test in this session shares the same
    "test@example.com" subject (via _default_auth_override above), so
    without this, tests running earlier in the session would eat into
    later tests' budget and cause order-dependent 429s on routes that
    are supposed to succeed. Same rationale as _clear_gemini_client_cache
    below, just for a different piece of shared state.
    """
    from api.rate_limit import reset_rate_limit_state

    reset_rate_limit_state()
    yield
    reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _clear_gemini_client_cache() -> Generator[None]:
    """llm.providers.gemini._client() is cached per thread (see its own
    docstring for why); tests that patch google.genai.Client need the
    cache cleared first, or they'll silently get an earlier test's stale
    cached instance instead of their own patch.
    """
    from llm.providers.gemini import _reset_client_cache

    _reset_client_cache()
    yield
    _reset_client_cache()


@pytest.fixture(autouse=True)
def _clear_groq_client_cache() -> Generator[None]:
    """Same reasoning as _clear_gemini_client_cache above, for
    llm.providers.groq._client()'s own per-thread cache.
    """
    from llm.providers.groq import _reset_client_cache

    _reset_client_cache()
    yield
    _reset_client_cache()


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
