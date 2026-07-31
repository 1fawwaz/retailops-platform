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
    """Creates a supplier, a warehouse, and a product; returns their ids/sku."""
    supplier_response = client.post(
        "/suppliers",
        json={"name": "Acme Co", "lead_time_days": 7, "reliability_score": 0.9},
        headers=headers,
    )
    supplier_id = supplier_response.json()["id"]
    warehouse_response = client.post("/warehouses", json={"name": "Main"}, headers=headers)
    warehouse_id = warehouse_response.json()["id"]
    client.post("/products", json={"sku": "SKU-1", "unit_cost": 2.0}, headers=headers)
    return supplier_id, warehouse_id, "SKU-1"


def _create_draft_po(
    client: TestClient, headers: dict[str, str], supplier_id: int, warehouse_id: int, sku: str
) -> dict[str, Any]:
    response = client.post(
        "/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity_ordered": 100, "unit_cost": 2.0}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_create_purchase_order(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)

    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    assert po["status"] == "draft"
    assert po["supplier_id"] == supplier_id
    assert po["warehouse_id"] == warehouse_id
    assert len(po["lines"]) == 1
    assert po["lines"][0]["quantity_ordered"] == 100
    assert po["lines"][0]["quantity_received"] == 0


def test_create_purchase_order_with_unknown_supplier_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)
    _, warehouse_id, sku = _setup(client, headers)

    response = client.post(
        "/purchase-orders",
        json={
            "supplier_id": 999999,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": sku, "quantity_ordered": 10}],
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_create_purchase_order_with_unknown_sku_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, _ = _setup(client, headers)

    response = client.post(
        "/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": "NOPE", "quantity_ordered": 10}],
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_update_purchase_order_while_draft_replaces_lines(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    response = client.put(
        f"/purchase-orders/{po['id']}",
        json={"lines": [{"sku": sku, "quantity_ordered": 250}]},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()["lines"]) == 1
    assert response.json()["lines"][0]["quantity_ordered"] == 250


def test_update_purchase_order_after_submit_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    client.post(f"/purchase-orders/{po['id']}/submit", headers=headers)

    response = client.put(
        f"/purchase-orders/{po['id']}",
        json={"lines": [{"sku": sku, "quantity_ordered": 5}]},
        headers=headers,
    )

    assert response.status_code == 400


def test_submit_approve_and_cancel_lifecycle(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    submit_response = client.post(f"/purchase-orders/{po['id']}/submit", headers=headers)
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "submitted"

    approve_response = client.post(f"/purchase-orders/{po['id']}/approve", headers=headers)
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"


def test_cannot_approve_a_draft_purchase_order(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    response = client.post(f"/purchase-orders/{po['id']}/approve", headers=headers)

    assert response.status_code == 400


def test_cancel_allowed_from_draft_and_submitted_not_approved(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)

    draft_po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    cancel_draft = client.post(f"/purchase-orders/{draft_po['id']}/cancel", headers=headers)
    assert cancel_draft.status_code == 200
    assert cancel_draft.json()["status"] == "cancelled"

    submitted_po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    client.post(f"/purchase-orders/{submitted_po['id']}/submit", headers=headers)
    cancel_submitted = client.post(f"/purchase-orders/{submitted_po['id']}/cancel", headers=headers)
    assert cancel_submitted.status_code == 200
    assert cancel_submitted.json()["status"] == "cancelled"

    approved_po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    client.post(f"/purchase-orders/{approved_po['id']}/submit", headers=headers)
    client.post(f"/purchase-orders/{approved_po['id']}/approve", headers=headers)
    cancel_approved = client.post(f"/purchase-orders/{approved_po['id']}/cancel", headers=headers)
    assert cancel_approved.status_code == 400


def _create_approved_po(
    client: TestClient, headers: dict[str, str], supplier_id: int, warehouse_id: int, sku: str
) -> dict[str, Any]:
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    client.post(f"/purchase-orders/{po['id']}/submit", headers=headers)
    approve_response = client.post(f"/purchase-orders/{po['id']}/approve", headers=headers)
    return cast(dict[str, Any], approve_response.json())


def test_partial_then_full_receive_updates_inventory_and_status(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_approved_po(client, headers, supplier_id, warehouse_id, sku)
    line_id = po["lines"][0]["id"]

    partial_response = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 40}]},
        headers=headers,
    )
    assert partial_response.status_code == 200
    assert partial_response.json()["status"] == "partially_received"
    assert partial_response.json()["lines"][0]["quantity_received"] == 40

    stock_response = client.get("/inventory/stock", params={"search": sku}, headers=headers)
    assert stock_response.json()[0]["quantity_on_hand"] == 40

    full_response = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 60}]},
        headers=headers,
    )
    assert full_response.status_code == 200
    assert full_response.json()["status"] == "received"
    assert full_response.json()["lines"][0]["quantity_received"] == 100

    stock_response = client.get("/inventory/stock", params={"search": sku}, headers=headers)
    assert stock_response.json()[0]["quantity_on_hand"] == 100

    ledger_response = client.get(f"/inventory/{sku}/ledger", headers=headers)
    po_entries = [e for e in ledger_response.json() if e["movement_type"] == "purchase_order"]
    assert len(po_entries) == 2
    assert {e["quantity_delta"] for e in po_entries} == {40, 60}


def test_over_receipt_without_confirmation_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_approved_po(client, headers, supplier_id, warehouse_id, sku)
    line_id = po["lines"][0]["id"]

    response = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 150}]},
        headers=headers,
    )

    assert response.status_code == 400


def test_over_receipt_with_confirmation_is_accepted(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_approved_po(client, headers, supplier_id, warehouse_id, sku)
    line_id = po["lines"][0]["id"]

    response = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 150, "over_receipt_confirmed": True}]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["lines"][0]["quantity_received"] == 150
    assert response.json()["status"] == "received"


def test_receive_against_a_draft_purchase_order_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    line_id = po["lines"][0]["id"]

    response = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 10}]},
        headers=headers,
    )

    assert response.status_code == 400


def test_close_only_allowed_after_fully_received(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_approved_po(client, headers, supplier_id, warehouse_id, sku)

    close_too_early = client.post(f"/purchase-orders/{po['id']}/close", headers=headers)
    assert close_too_early.status_code == 400

    line_id = po["lines"][0]["id"]
    client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line_id, "quantity": 100}]},
        headers=headers,
    )

    close_response = client.post(f"/purchase-orders/{po['id']}/close", headers=headers)
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"


def test_read_only_user_cannot_mutate_purchase_orders(
    client: TestClient, db_session: Session
) -> None:
    writer_headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, writer_headers)
    po = _create_draft_po(client, writer_headers, supplier_id, warehouse_id, sku)
    reader_headers = _read_only_headers(db_session)

    assert (
        client.post(f"/purchase-orders/{po['id']}/submit", headers=reader_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/purchase-orders",
            json={
                "supplier_id": supplier_id,
                "warehouse_id": warehouse_id,
                "lines": [{"sku": sku, "quantity_ordered": 1}],
            },
            headers=reader_headers,
        ).status_code
        == 403
    )


def test_cannot_delete_supplier_with_an_open_purchase_order(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    response = client.delete(f"/suppliers/{supplier_id}", headers=headers)

    assert response.status_code == 409


def test_supplier_deletable_once_its_purchase_orders_are_cancelled(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    po = _create_draft_po(client, headers, supplier_id, warehouse_id, sku)
    client.post(f"/purchase-orders/{po['id']}/cancel", headers=headers)

    response = client.delete(f"/suppliers/{supplier_id}", headers=headers)

    assert response.status_code == 204


def test_cannot_delete_product_with_an_open_purchase_order_line(client: TestClient) -> None:
    headers = _auth_headers(client)
    supplier_id, warehouse_id, sku = _setup(client, headers)
    _create_draft_po(client, headers, supplier_id, warehouse_id, sku)

    response = client.delete(f"/products/{sku}", headers=headers)

    assert response.status_code == 409
