from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_read_supplier(client: TestClient) -> None:
    headers = _auth_headers(client)

    create_response = client.post(
        "/suppliers",
        json={"name": "Acme Co", "lead_time_days": 7, "reliability_score": 0.92},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    supplier_id = create_response.json()["id"]

    get_response = client.get(f"/suppliers/{supplier_id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["name"] == "Acme Co"
    assert body["_provenance"]["lead_time_days"] == "derived"


def test_update_and_delete_supplier(client: TestClient) -> None:
    headers = _auth_headers(client)
    create_response = client.post(
        "/suppliers",
        json={"name": "Acme Co", "lead_time_days": 7, "reliability_score": 0.92},
        headers=headers,
    )
    supplier_id = create_response.json()["id"]

    update_response = client.put(
        f"/suppliers/{supplier_id}", json={"lead_time_days": 10}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["lead_time_days"] == 10

    delete_response = client.delete(f"/suppliers/{supplier_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/suppliers/{supplier_id}", headers=headers)
    assert get_response.status_code == 404


def test_supplier_detail_lists_assigned_skus(client: TestClient) -> None:
    headers = _auth_headers(client)
    create_response = client.post(
        "/suppliers",
        json={"name": "Acme Co", "lead_time_days": 7, "reliability_score": 0.92},
        headers=headers,
    )
    supplier_id = create_response.json()["id"]
    client.post("/products", json={"sku": "SKU-1", "supplier_id": supplier_id}, headers=headers)
    client.post("/products", json={"sku": "SKU-2", "supplier_id": supplier_id}, headers=headers)
    client.post("/products", json={"sku": "SKU-3"}, headers=headers)

    response = client.get(f"/suppliers/{supplier_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["skus"] == ["SKU-1", "SKU-2"]


def test_get_nonexistent_supplier_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/suppliers/999", headers=headers)

    assert response.status_code == 404


def _create_supplier(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        "/suppliers",
        json={"name": "Acme Co", "lead_time_days": 7, "reliability_score": 0.92},
        headers=headers,
    )
    return int(response.json()["id"])


def test_create_and_list_supplier_contacts(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id = _create_supplier(client, headers)

    create_response = client.post(
        f"/suppliers/{supplier_id}/contacts",
        json={"name": "Priya Shah", "email": "priya@example.com", "role": "Account Manager"},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["supplier_id"] == supplier_id

    list_response = client.get(f"/suppliers/{supplier_id}/contacts", headers=headers)
    assert list_response.status_code == 200
    names = [c["name"] for c in list_response.json()]
    assert "Priya Shah" in names


def test_update_and_delete_supplier_contact(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id = _create_supplier(client, headers)
    create_response = client.post(
        f"/suppliers/{supplier_id}/contacts", json={"name": "Priya Shah"}, headers=headers
    )
    contact_id = create_response.json()["id"]

    update_response = client.put(
        f"/suppliers/{supplier_id}/contacts/{contact_id}",
        json={"phone": "+44 20 7946 0000"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+44 20 7946 0000"

    delete_response = client.delete(
        f"/suppliers/{supplier_id}/contacts/{contact_id}", headers=headers
    )
    assert delete_response.status_code == 204

    list_response = client.get(f"/suppliers/{supplier_id}/contacts", headers=headers)
    assert list_response.json() == []


def test_contact_on_a_different_supplier_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id = _create_supplier(client, headers)
    other_supplier_response = client.post(
        "/suppliers",
        json={"name": "Other Co", "lead_time_days": 3, "reliability_score": 0.5},
        headers=headers,
    )
    other_supplier_id = other_supplier_response.json()["id"]
    create_response = client.post(
        f"/suppliers/{supplier_id}/contacts", json={"name": "Priya Shah"}, headers=headers
    )
    contact_id = create_response.json()["id"]

    response = client.put(
        f"/suppliers/{other_supplier_id}/contacts/{contact_id}",
        json={"phone": "+44 20 7946 0000"},
        headers=headers,
    )

    assert response.status_code == 404


def test_contacts_for_nonexistent_supplier_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/suppliers/999/contacts", headers=headers)

    assert response.status_code == 404
