from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.security import create_access_token
from services.users import create_user


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _read_only_headers(db_session: Session, email: str = "demo@example.com") -> dict[str, str]:
    create_user(db_session, email=email, password="hunter22!!", is_read_only=True)
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def _setup(client: TestClient, headers: dict[str, str]) -> tuple[int, int, str]:
    """Creates a customer, a warehouse, and a product with stock on hand
    (via a receiving PO); returns their ids/sku."""
    customer_response = client.post("/customers", json={"name": "Priya Shah"}, headers=headers)
    customer_id = customer_response.json()["id"]
    warehouse_response = client.post("/warehouses", json={"name": "Main"}, headers=headers)
    warehouse_id = warehouse_response.json()["id"]
    client.post("/products", json={"sku": "SKU-1", "unit_cost": 2.0}, headers=headers)
    client.post(
        "/inventory/adjustments",
        json={
            "sku": "SKU-1",
            "warehouse_id": warehouse_id,
            "quantity_delta": 100,
            "reason": "seed",
        },
        headers=headers,
    )
    return customer_id, warehouse_id, "SKU-1"


def _create_draft_order(
    client: TestClient, headers: dict[str, str], customer_id: int, warehouse_id: int, sku: str
) -> dict[str, Any]:
    response = client.post(
        "/sales-orders",
        json={
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity": 10, "unit_price": 4.99}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_create_sales_order(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)

    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)

    assert order["status"] == "draft"
    assert order["customer_id"] == customer_id
    assert len(order["lines"]) == 1
    assert order["lines"][0]["quantity"] == 10


def test_create_sales_order_with_unknown_customer_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)
    _, warehouse_id, sku = _setup(client, headers)

    response = client.post(
        "/sales-orders",
        json={
            "customer_id": 999999,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity": 1, "unit_price": 4.99}],
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_update_sales_order_while_draft_replaces_lines(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)

    response = client.put(
        f"/sales-orders/{order['id']}",
        json={"lines": [{"sku": sku, "quantity": 3, "unit_price": 5.5}]},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()["lines"]) == 1
    assert response.json()["lines"][0]["quantity"] == 3


def test_confirm_creates_an_invoice_matching_the_order_total(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)

    confirm_response = client.post(f"/sales-orders/{order['id']}/confirm", headers=headers)
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"

    invoice_response = client.get(f"/sales-orders/{order['id']}/invoice", headers=headers)
    assert invoice_response.status_code == 200
    assert invoice_response.json()["total_amount"] == 49.9
    assert invoice_response.json()["status"] == "unpaid"


def test_update_after_confirm_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    client.post(f"/sales-orders/{order['id']}/confirm", headers=headers)

    response = client.put(
        f"/sales-orders/{order['id']}",
        json={"lines": [{"sku": sku, "quantity": 1, "unit_price": 1.0}]},
        headers=headers,
    )

    assert response.status_code == 400


def test_fulfill_deducts_inventory_and_records_a_sale_movement(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    client.post(f"/sales-orders/{order['id']}/confirm", headers=headers)

    fulfill_response = client.post(f"/sales-orders/{order['id']}/fulfill", headers=headers)
    assert fulfill_response.status_code == 200
    assert fulfill_response.json()["status"] == "fulfilled"

    stock_response = client.get("/inventory/stock", params={"search": sku}, headers=headers)
    assert stock_response.json()[0]["quantity_on_hand"] == 90  # 100 seeded - 10 sold

    ledger_response = client.get(f"/inventory/{sku}/ledger", headers=headers)
    sale_entries = [
        e
        for e in ledger_response.json()
        if e["movement_type"] == "sale" and e["reference"] == f"SO #{order['id']}"
    ]
    assert len(sale_entries) == 1
    assert sale_entries[0]["quantity_delta"] == -10


def test_fulfill_with_insufficient_stock_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    response = client.post(
        "/sales-orders",
        json={
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity": 9999, "unit_price": 4.99}],
        },
        headers=headers,
    )
    order = response.json()
    client.post(f"/sales-orders/{order['id']}/confirm", headers=headers)

    fulfill_response = client.post(f"/sales-orders/{order['id']}/fulfill", headers=headers)

    assert fulfill_response.status_code == 400


def test_fulfill_a_draft_order_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)

    response = client.post(f"/sales-orders/{order['id']}/fulfill", headers=headers)

    assert response.status_code == 400


def test_cancel_allowed_from_draft_and_confirmed_not_fulfilled(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)

    draft_order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    cancel_draft = client.post(f"/sales-orders/{draft_order['id']}/cancel", headers=headers)
    assert cancel_draft.status_code == 200
    assert cancel_draft.json()["status"] == "cancelled"

    confirmed_order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    client.post(f"/sales-orders/{confirmed_order['id']}/confirm", headers=headers)
    cancel_confirmed = client.post(f"/sales-orders/{confirmed_order['id']}/cancel", headers=headers)
    assert cancel_confirmed.status_code == 200

    fulfilled_order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    client.post(f"/sales-orders/{fulfilled_order['id']}/confirm", headers=headers)
    client.post(f"/sales-orders/{fulfilled_order['id']}/fulfill", headers=headers)
    cancel_fulfilled = client.post(f"/sales-orders/{fulfilled_order['id']}/cancel", headers=headers)
    assert cancel_fulfilled.status_code == 400


def test_recording_payments_updates_invoice_status(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    order = _create_draft_order(client, headers, customer_id, warehouse_id, sku)
    client.post(f"/sales-orders/{order['id']}/confirm", headers=headers)
    invoice = client.get(f"/sales-orders/{order['id']}/invoice", headers=headers).json()

    partial_response = client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 20.0, "method": "card"},
        headers=headers,
    )
    assert partial_response.status_code == 201

    partially_paid_invoice = client.get(f"/invoices/{invoice['id']}", headers=headers).json()
    assert partially_paid_invoice["status"] == "partially_paid"

    client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 29.9, "method": "card"},
        headers=headers,
    )

    paid_invoice = client.get(f"/invoices/{invoice['id']}", headers=headers).json()
    assert paid_invoice["status"] == "paid"

    payments_response = client.get(f"/invoices/{invoice['id']}/payments", headers=headers)
    assert len(payments_response.json()) == 2


def test_customer_orders_endpoint_lists_their_sales_orders(client: TestClient) -> None:
    headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, headers)
    _create_draft_order(client, headers, customer_id, warehouse_id, sku)

    other_customer = client.post("/customers", json={"name": "Sam Lee"}, headers=headers)
    other_customer_id = other_customer.json()["id"]
    _create_draft_order(client, headers, other_customer_id, warehouse_id, sku)

    response = client.get(f"/customers/{customer_id}/orders", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["customer_id"] == customer_id


def test_read_only_user_cannot_mutate_sales_orders(client: TestClient, db_session: Session) -> None:
    writer_headers = _auth_headers(client)
    customer_id, warehouse_id, sku = _setup(client, writer_headers)
    reader_headers = _read_only_headers(db_session)

    response = client.post(
        "/sales-orders",
        json={
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity": 1, "unit_price": 1.0}],
        },
        headers=reader_headers,
    )

    assert response.status_code == 403
