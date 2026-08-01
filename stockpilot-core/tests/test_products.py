from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.stock_level import StockLevel
from models.stock_movement import StockMovement
from services.security import create_access_token
from services.users import create_user
from services.warehouses import get_or_create_main_warehouse

NUMERIC_PRODUCT_FIELDS = {"unit_cost", "sale_price", "reorder_point", "safety_stock"}


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


def test_product_detail_includes_current_stock_and_recent_history(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1"}, headers=headers)
    now = datetime.now(UTC).replace(tzinfo=None)
    warehouse = get_or_create_main_warehouse(db_session)
    db_session.add_all(
        [
            StockLevel(
                sku="SKU-1", warehouse_id=warehouse.id, as_of_date=date.today(), quantity_on_hand=42
            ),
            StockMovement(
                sku="SKU-1",
                warehouse_id=warehouse.id,
                movement_date=now - timedelta(days=1),
                quantity_delta=-2,
                movement_type="sale",
                provenance="observed",
            ),
            StockMovement(
                sku="SKU-1",
                warehouse_id=warehouse.id,
                movement_date=now - timedelta(days=200),
                quantity_delta=50,
                movement_type="opening_balance",
                provenance="derived",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/products/SKU-1", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["quantity_on_hand"] == 42
    assert len(body["movement_history"]) == 1
    assert body["movement_history"][0]["movement_type"] == "sale"
    assert body["movement_history"][0]["provenance"] == "observed"
    assert "quantity_on_hand" in body["_provenance"]


def test_create_and_read_product_with_brand_and_sale_price(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/brands", json={"name": "Acme Housewares"}, headers=headers)
    brand_id = client.get("/brands", headers=headers).json()[0]["id"]

    create_response = client.post(
        "/products",
        json={"sku": "SKU-1", "brand_id": brand_id, "sale_price": 9.99},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["brand_id"] == brand_id
    assert create_response.json()["sale_price"] == 9.99

    get_response = client.get("/products/SKU-1", headers=headers)
    body = get_response.json()
    assert body["brand_id"] == brand_id
    assert body["sale_price"] == 9.99


def test_update_records_product_history_with_the_changing_user(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1", "unit_cost": 1.0}, headers=headers)

    update_response = client.put("/products/SKU-1", json={"unit_cost": 2.5}, headers=headers)
    assert update_response.status_code == 200

    history_response = client.get("/products/SKU-1/history", headers=headers)
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1
    assert entries[0]["field_name"] == "unit_cost"
    assert entries[0]["old_value"] == "1.0"
    assert entries[0]["new_value"] == "2.5"
    assert entries[0]["changed_by_user_id"] is not None


def test_update_with_no_actual_change_does_not_add_a_history_entry(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1", "unit_cost": 1.0}, headers=headers)

    client.put("/products/SKU-1", json={"unit_cost": 1.0}, headers=headers)

    history_response = client.get("/products/SKU-1/history", headers=headers)
    assert history_response.json() == []


def test_read_only_user_can_read_but_not_write(client: TestClient, db_session: Session) -> None:
    writer_headers = _auth_headers(client)
    client.post("/products", json={"sku": "SKU-1"}, headers=writer_headers)

    demo_headers = _read_only_headers(db_session)

    read_response = client.get("/products/SKU-1", headers=demo_headers)
    assert read_response.status_code == 200

    write_response = client.post("/products", json={"sku": "SKU-2"}, headers=demo_headers)
    assert write_response.status_code == 403


def test_user_without_products_permission_cannot_create_a_product(client: TestClient) -> None:
    """Distinct from the is_read_only check above: this user is NOT
    read-only, but has zero roles assigned (the second user registered
    on a fresh deployment, docs/BUILD.md Backend Module 10) -- the real
    RBAC permission check must deny them independently.
    """
    _auth_headers(client, email="first@example.com")  # becomes admin
    second_headers = _auth_headers(client, email="second@example.com")

    response = client.post("/products", json={"sku": "SKU-1"}, headers=second_headers)

    assert response.status_code == 403
    assert "products:create" in response.json()["detail"]


def test_list_products_search_matches_sku_or_description(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post(
        "/products", json={"sku": "85048", "description": "Christmas glass ball"}, headers=headers
    )
    client.post("/products", json={"sku": "22841", "description": "Cake tin"}, headers=headers)

    by_sku = client.get("/products", params={"search": "8504"}, headers=headers)
    assert [p["sku"] for p in by_sku.json()] == ["85048"]

    by_description = client.get("/products", params={"search": "cake"}, headers=headers)
    assert [p["sku"] for p in by_description.json()] == ["22841"]


def test_list_products_filters_by_category(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/categories", json={"name": "Decorations"}, headers=headers)
    client.post("/categories", json={"name": "Kitchenware"}, headers=headers)
    categories = {c["name"]: c["id"] for c in client.get("/categories", headers=headers).json()}
    client.post(
        "/products",
        json={"sku": "85048", "category_id": categories["Decorations"]},
        headers=headers,
    )
    client.post(
        "/products",
        json={"sku": "22841", "category_id": categories["Kitchenware"]},
        headers=headers,
    )

    response = client.get("/products", params={"category": "decorations"}, headers=headers)

    assert [p["sku"] for p in response.json()] == ["85048"]


def test_list_products_respects_limit_and_offset(client: TestClient) -> None:
    headers = _auth_headers(client)
    for sku in ("SKU-1", "SKU-2", "SKU-3"):
        client.post("/products", json={"sku": sku}, headers=headers)

    first_page = client.get("/products", params={"limit": 2, "offset": 0}, headers=headers)
    second_page = client.get("/products", params={"limit": 2, "offset": 2}, headers=headers)

    assert [p["sku"] for p in first_page.json()] == ["SKU-1", "SKU-2"]
    assert [p["sku"] for p in second_page.json()] == ["SKU-3"]


def test_user_with_a_role_granting_the_permission_can_create_a_product(
    client: TestClient,
) -> None:
    admin_headers = _auth_headers(client, email="admin@example.com")
    manager_headers = _auth_headers(client, email="manager@example.com")
    users = client.get("/users", headers=admin_headers).json()
    manager_id = next(u["id"] for u in users if u["email"] == "manager@example.com")
    roles = client.get("/roles", headers=admin_headers).json()
    inventory_manager_role_id = next(r["id"] for r in roles if r["name"] == "inventory_manager")
    client.post(f"/users/{manager_id}/roles/{inventory_manager_role_id}", headers=admin_headers)

    response = client.post("/products", json={"sku": "SKU-1"}, headers=manager_headers)

    assert response.status_code == 201, response.text
