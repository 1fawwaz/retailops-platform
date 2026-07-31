from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_warehouses(client: TestClient) -> None:
    headers = _auth_headers(client)

    create_response = client.post("/warehouses", json={"name": "North Depot"}, headers=headers)
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["name"] == "North Depot"

    list_response = client.get("/warehouses", headers=headers)
    assert list_response.status_code == 200
    names = [w["name"] for w in list_response.json()]
    assert "North Depot" in names


def test_create_duplicate_warehouse_name_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/warehouses", json={"name": "North Depot"}, headers=headers)

    response = client.post("/warehouses", json={"name": "North Depot"}, headers=headers)

    assert response.status_code == 409
