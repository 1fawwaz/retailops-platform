"""Stage 6 backend hardening: auth.py's JWT validation, plus a real
end-to-end proof that api/deps.py::get_current_subject genuinely
enforces it through the FastAPI app -- not just that the rest of the
test suite happens to pass because tests/conftest.py's autouse
`_default_auth_override` fixture is always on. Both of the tests in
`TestAuthReallyEnforced` explicitly pop that override first.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import deps
from api.main import app
from auth import decode_bearer_subject
from settings import get_settings


def _token(*, subject: object = "reader@example.com", expired: bool = False) -> str:
    settings = get_settings()
    delta = timedelta(minutes=-5) if expired else timedelta(minutes=60)
    payload = {"sub": subject, "exp": datetime.now(UTC) + delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_decode_bearer_subject_returns_the_sub_claim_for_a_valid_token() -> None:
    assert decode_bearer_subject(_token(subject="reader@example.com")) == "reader@example.com"


def test_decode_bearer_subject_rejects_an_expired_token() -> None:
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_bearer_subject(_token(expired=True))


def test_decode_bearer_subject_rejects_a_token_signed_with_a_different_secret() -> None:
    settings = get_settings()
    wrong_secret_token = jwt.encode(
        {"sub": "reader@example.com", "exp": datetime.now(UTC) + timedelta(minutes=60)},
        "a-completely-different-secret-not-in-settings",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_bearer_subject(wrong_secret_token)


def test_decode_bearer_subject_rejects_a_malformed_token() -> None:
    with pytest.raises(jwt.DecodeError):
        decode_bearer_subject("not-a-real-jwt-at-all")


def test_decode_bearer_subject_rejects_a_non_string_subject() -> None:
    with pytest.raises(jwt.InvalidTokenError):
        decode_bearer_subject(_token(subject=12345))


class TestAuthReallyEnforced:
    """Both tests here pop tests/conftest.py's autouse
    `_default_auth_override` first, so they exercise the REAL
    api/deps.py::get_current_subject dependency through the actual
    FastAPI app, not the test-suite-wide bypass every other route test
    relies on.
    """

    UNKNOWN_EXECUTION_ID = "00000000-0000-0000-0000-000000000000"

    def test_protected_route_401s_with_no_authorization_header(self) -> None:
        app.dependency_overrides.pop(deps.get_current_subject, None)
        client = TestClient(app)
        response = client.get(f"/agent/execution/{self.UNKNOWN_EXECUTION_ID}")
        assert response.status_code == 401

    def test_protected_route_401s_with_an_expired_token(self) -> None:
        # A missing header is rejected by OAuth2PasswordBearer itself,
        # before get_current_subject ever runs. A present-but-expired
        # token is the case that actually reaches (and needs)
        # api/deps.py::get_current_subject's own except block.
        app.dependency_overrides.pop(deps.get_current_subject, None)
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {_token(expired=True)}"}
        response = client.get(f"/agent/execution/{self.UNKNOWN_EXECUTION_ID}", headers=headers)
        assert response.status_code == 401

    def test_protected_route_accepts_a_real_stockpilot_shaped_token(
        self, db_session: Session
    ) -> None:
        app.dependency_overrides.pop(deps.get_current_subject, None)
        app.dependency_overrides[deps.get_db_session_factory] = lambda: lambda: db_session
        try:
            client = TestClient(app)
            headers = {"Authorization": f"Bearer {_token()}"}
            response = client.get(f"/agent/execution/{self.UNKNOWN_EXECUTION_ID}", headers=headers)
        finally:
            app.dependency_overrides.pop(deps.get_db_session_factory, None)
        # A real token clears auth and reaches the route body -- proven by
        # getting the route's own 404 (unknown execution id), not a 401.
        assert response.status_code == 404

    def test_health_stays_open_with_no_authorization_header(self) -> None:
        app.dependency_overrides.pop(deps.get_current_subject, None)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
