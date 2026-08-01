from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_default_roles_are_seeded(client: TestClient) -> None:
    headers = _auth_headers(client)  # first user -> admin, can list roles

    response = client.get("/roles", headers=headers)

    assert response.status_code == 200
    names = {r["name"] for r in response.json()}
    assert names == {"admin", "inventory_manager", "procurement", "sales", "analyst", "viewer"}
    admin_role = next(r for r in response.json() if r["name"] == "admin")
    assert "products:create" in admin_role["permissions"]
    assert "purchase_order:receive" in admin_role["permissions"]
    viewer_role = next(r for r in response.json() if r["name"] == "viewer")
    assert set(viewer_role["permissions"]) == {"dashboard:read", "profile:read"}


def test_create_role(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.post(
        "/roles",
        json={"name": "warehouse_clerk", "permissions": ["inventory:read"]},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["permissions"] == ["inventory:read"]


def test_create_duplicate_role_name_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/roles", json={"name": "warehouse_clerk", "permissions": []}, headers=headers)

    response = client.post(
        "/roles", json={"name": "warehouse_clerk", "permissions": []}, headers=headers
    )

    assert response.status_code == 409


def test_update_role_permissions(client: TestClient) -> None:
    headers = _auth_headers(client)
    create_response = client.post(
        "/roles",
        json={"name": "warehouse_clerk", "permissions": ["inventory:read"]},
        headers=headers,
    )
    role_id = create_response.json()["id"]

    response = client.put(
        f"/roles/{role_id}",
        json={"permissions": ["inventory:read", "inventory:update"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["permissions"] == ["inventory:read", "inventory:update"]


def test_second_user_has_no_roles_and_cannot_manage_roles(client: TestClient) -> None:
    _auth_headers(client, email="first@example.com")  # becomes admin
    second_headers = _auth_headers(client, email="second@example.com")

    me_response = client.get("/me", headers=second_headers)
    assert me_response.json()["roles"] == []

    list_response = client.get("/roles", headers=second_headers)
    assert list_response.status_code == 403

    create_response = client.post(
        "/roles", json={"name": "x", "permissions": []}, headers=second_headers
    )
    assert create_response.status_code == 403
