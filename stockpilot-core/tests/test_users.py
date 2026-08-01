from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_first_registered_user_becomes_admin(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/me", headers=headers)

    assert response.json()["roles"] == ["admin"]


def test_second_registered_user_starts_with_no_roles(client: TestClient) -> None:
    _auth_headers(client, email="first@example.com")
    second_headers = _auth_headers(client, email="second@example.com")

    response = client.get("/me", headers=second_headers)

    assert response.json()["roles"] == []
    assert response.json()["permissions"] == []


def test_list_users_shows_roles(client: TestClient) -> None:
    admin_headers = _auth_headers(client, email="admin@example.com")
    _auth_headers(client, email="second@example.com")

    response = client.get("/users", headers=admin_headers)

    assert response.status_code == 200
    by_email = {u["email"]: u for u in response.json()}
    assert by_email["admin@example.com"]["roles"] == ["admin"]
    assert by_email["second@example.com"]["roles"] == []


def test_assign_and_revoke_role(client: TestClient) -> None:
    admin_headers = _auth_headers(client, email="admin@example.com")
    client.post("/auth/register", json={"email": "clerk@example.com", "password": "hunter22!!"})
    users = client.get("/users", headers=admin_headers).json()
    clerk_id = next(u["id"] for u in users if u["email"] == "clerk@example.com")
    roles = client.get("/roles", headers=admin_headers).json()
    viewer_role_id = next(r["id"] for r in roles if r["name"] == "viewer")

    assign_response = client.post(
        f"/users/{clerk_id}/roles/{viewer_role_id}", headers=admin_headers
    )
    assert assign_response.status_code == 201
    assert assign_response.json()["roles"] == ["viewer"]

    revoke_response = client.delete(
        f"/users/{clerk_id}/roles/{viewer_role_id}", headers=admin_headers
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["roles"] == []


def test_non_admin_cannot_list_users(client: TestClient) -> None:
    _auth_headers(client, email="admin@example.com")
    second_headers = _auth_headers(client, email="second@example.com")

    response = client.get("/users", headers=second_headers)

    assert response.status_code == 403


def test_assign_unknown_role_is_404(client: TestClient) -> None:
    admin_headers = _auth_headers(client, email="admin@example.com")
    users = client.get("/users", headers=admin_headers).json()
    admin_id = users[0]["id"]

    response = client.post(f"/users/{admin_id}/roles/999999", headers=admin_headers)

    assert response.status_code == 404
