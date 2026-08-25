from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "admin@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_settings_returns_defaults(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/settings", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "INR"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["low_stock_notifications_enabled"] is True


def test_update_settings(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.put("/settings", json={"currency": "USD"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"
    assert response.json()["timezone"] == "Asia/Kolkata"  # unchanged


def test_non_admin_cannot_view_or_update_settings(client: TestClient) -> None:
    _auth_headers(client, email="admin@example.com")
    second_headers = _auth_headers(client, email="second@example.com")

    get_response = client.get("/settings", headers=second_headers)
    assert get_response.status_code == 403

    put_response = client.put("/settings", json={"currency": "USD"}, headers=second_headers)
    assert put_response.status_code == 403
