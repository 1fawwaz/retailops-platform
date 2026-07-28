from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.security import create_access_token
from services.users import create_user

NUMERIC_PRODUCT_FIELDS = {"unit_cost", "reorder_point", "safety_stock"}


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _read_only_headers(db_session: Session, email: str = "demo@example.com") -> dict[str, str]:
    create_user(db_session, email=email, password="hunter22!!", is_read_only=True)
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def test_create_and_read_product(client: TestClient) -> None:
    headers = _auth_headers(client)

    create_response = client.post(
        "/products",
        json={"sku": "SKU-1", "description": "Widget", "unit_cost": 4.5},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text

    get_response = client.get("/products/SKU-1", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["sku"] == "SKU-1"
    assert body["unit_cost"] == 4.5


def test_create_duplicate_sku_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1"}, headers=headers)

    response = client.post("/products", json={"sku": "SKU-1"}, headers=headers)

    assert response.status_code == 409


def test_get_nonexistent_product_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/products/NOPE", headers=headers)

    assert response.status_code == 404


def test_update_and_delete_product(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1", "unit_cost": 1.0}, headers=headers)

    update_response = client.put("/products/SKU-1", json={"unit_cost": 2.5}, headers=headers)
    assert update_response.status_code == 200
    assert update_response.json()["unit_cost"] == 2.5

    delete_response = client.delete("/products/SKU-1", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get("/products/SKU-1", headers=headers)
    assert get_response.status_code == 404


def test_every_numeric_field_has_provenance_entry(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post(
        "/products",
        json={"sku": "SKU-1", "unit_cost": 1.0, "reorder_point": 5, "safety_stock": 2},
        headers=headers,
    )

    response = client.get("/products/SKU-1", headers=headers)
    body = response.json()

    for field in NUMERIC_PRODUCT_FIELDS:
        assert field in body["_provenance"], f"{field} missing a provenance entry"


def test_read_only_user_can_read_but_not_write(client: TestClient, db_session: Session) -> None:
    writer_headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1"}, headers=writer_headers)

    demo_headers = _read_only_headers(db_session)

    read_response = client.get("/products/SKU-1", headers=demo_headers)
    assert read_response.status_code == 200

    write_response = client.post("/products", json={"sku": "SKU-2"}, headers=demo_headers)
    assert write_response.status_code == 403
