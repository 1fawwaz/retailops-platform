from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "admin@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mutating_action_creates_an_audit_log_entry(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    users = client.get("/users", headers=admin_headers).json()
    admin_id = users[0]["id"]

    client.post("/products", json={"sku": "SKU-1"}, headers=admin_headers)

    response = client.get("/audit-logs", headers=admin_headers)

    assert response.status_code == 200
    entries = response.json()
    creation_entries = [
        e for e in entries if e["permission"] == "products:create" and e["path"] == "/products"
    ]
    assert len(creation_entries) == 1
    assert creation_entries[0]["user_id"] == admin_id
    assert creation_entries[0]["method"] == "POST"


def test_audit_log_filters_by_permission(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1"}, headers=admin_headers)
    client.post(
        "/suppliers",
        json={"name": "Acme", "lead_time_days": 5, "reliability_score": 0.9},
        headers=admin_headers,
    )

    response = client.get(
        "/audit-logs", params={"permission": "suppliers:create"}, headers=admin_headers
    )

    entries = response.json()
    assert all(e["permission"] == "suppliers:create" for e in entries)
    assert len(entries) == 1


def test_non_admin_cannot_view_audit_logs(client: TestClient) -> None:
    _auth_headers(client, email="admin@example.com")
    second_headers = _auth_headers(client, email="second@example.com")

    response = client.get("/audit-logs", headers=second_headers)

    assert response.status_code == 403


def test_granted_mutation_is_audited_as_granted(client: TestClient) -> None:
    admin_headers = _auth_headers(client)

    client.post("/products", json={"sku": "SKU-GRANTED"}, headers=admin_headers)

    response = client.get(
        "/audit-logs", params={"permission": "products:create"}, headers=admin_headers
    )
    assert response.status_code == 200
    entries = response.json()
    assert any(e["path"] == "/products" and e["outcome"] == "granted" for e in entries)
    assert all(e["outcome"] == "granted" for e in entries)


def test_denied_mutation_is_audited_as_denied(client: TestClient) -> None:
    # SEC-05: a user lacking a permission is still audited -- the denied
    # attempt is recorded with outcome="denied", not silently dropped.
    admin_headers = _auth_headers(client, email="admin@example.com")
    second_headers = _auth_headers(client, email="second@example.com")

    denied = client.post("/products", json={"sku": "SKU-DENIED"}, headers=second_headers)
    assert denied.status_code == 403

    response = client.get(
        "/audit-logs",
        params={"permission": "products:create", "outcome": "denied"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    denied_entries = [e for e in response.json() if e["path"] == "/products"]
    assert any(e["outcome"] == "denied" for e in denied_entries)


def test_audit_log_filters_by_outcome(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-OK"}, headers=admin_headers)

    granted = client.get("/audit-logs", params={"outcome": "granted"}, headers=admin_headers)
    assert granted.status_code == 200
    assert all(e["outcome"] == "granted" for e in granted.json())
