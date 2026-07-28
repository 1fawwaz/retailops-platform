from fastapi.testclient import TestClient


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
