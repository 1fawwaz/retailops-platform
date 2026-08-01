from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.auth_tokens import issue_password_reset_token
from services.users import get_user_by_email


def _register(
    client: TestClient, email: str = "user@example.com", password: str = "hunter22!!"
) -> None:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text


def test_register_creates_user(client: TestClient) -> None:
    _register(client)


def test_register_duplicate_email_is_rejected(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/register", json={"email": "user@example.com", "password": "another-pass"}
    )

    assert response.status_code == 409


def test_login_with_correct_credentials_returns_token(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "hunter22!!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_protected_route_without_token_is_rejected(client: TestClient) -> None:
    response = client.get("/products")

    assert response.status_code == 401


def test_protected_route_with_valid_token_succeeds(client: TestClient) -> None:
    _register(client)
    login_response = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "hunter22!!"}
    )
    token = login_response.json()["access_token"]

    response = client.get("/products", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def _login(
    client: TestClient, email: str = "user@example.com", password: str = "hunter22!!"
) -> dict[str, str]:
    _register(client, email=email, password=password)
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return cast(dict[str, str], response.json())


def test_login_returns_a_refresh_token_alongside_the_access_token(client: TestClient) -> None:
    body = _login(client)

    assert isinstance(body["refresh_token"], str) and body["refresh_token"]


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_returns_the_authenticated_users_profile(client: TestClient) -> None:
    tokens = _login(client)

    response = client.get("/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["is_active"] is True
    # First registered user on a fresh deployment becomes admin
    # (docs/BUILD.md Backend Module 10).
    assert body["roles"] == ["admin"]
    assert "products:create" in body["permissions"]


def test_refresh_with_a_valid_refresh_token_returns_a_new_access_token(client: TestClient) -> None:
    tokens = _login(client)

    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["token_type"] == "bearer"


def test_refresh_with_an_unknown_token_is_rejected(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    tokens = _login(client)

    logout_response = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout_response.status_code == 204

    refresh_response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 401


def test_logout_with_an_unknown_token_is_idempotent(client: TestClient) -> None:
    response = client.post("/auth/logout", json={"refresh_token": "never-issued"})

    assert response.status_code == 204


def test_password_reset_request_returns_202_for_a_real_account(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/password-reset/request", json={"email": "user@example.com"})

    assert response.status_code == 202


def test_password_reset_request_returns_202_for_an_unknown_account_too(
    client: TestClient,
) -> None:
    # Never confirms/denies account existence via response shape
    # (docs/ARCHITECTURE.md §6) -- same 202 either way.
    response = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    assert response.status_code == 202


def test_password_reset_confirm_changes_the_password_and_revokes_other_sessions(
    client: TestClient, db_session: Session
) -> None:
    tokens = _login(client)
    user = get_user_by_email(db_session, "user@example.com")
    assert user is not None
    raw_reset_token = issue_password_reset_token(db_session, user)

    confirm_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_reset_token, "new_password": "a-new-strong-password"},
    )
    assert confirm_response.status_code == 204

    old_password_login = client.post(
        "/auth/login", data={"username": "user@example.com", "password": "hunter22!!"}
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "a-new-strong-password"},
    )
    assert new_password_login.status_code == 200

    old_refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert old_refresh_response.status_code == 401


def test_password_reset_confirm_with_an_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "a-new-strong-password"},
    )

    assert response.status_code == 400


def test_password_reset_confirm_token_is_single_use(
    client: TestClient, db_session: Session
) -> None:
    _register(client)
    user = get_user_by_email(db_session, "user@example.com")
    assert user is not None
    raw_reset_token = issue_password_reset_token(db_session, user)

    first_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_reset_token, "new_password": "first-new-password"},
    )
    assert first_response.status_code == 204

    second_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_reset_token, "new_password": "second-new-password"},
    )
    assert second_response.status_code == 400
