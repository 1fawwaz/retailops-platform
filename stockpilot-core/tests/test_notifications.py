from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str = "admin@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_adjustment_crossing_reorder_point_notifies_admin(client: TestClient) -> None:
    admin_headers = _auth_headers(client)  # first user -> admin -> has inventory:update
    warehouse_id = client.post("/warehouses", json={"name": "Main"}, headers=admin_headers).json()[
        "id"
    ]
    client.post(
        "/products",
        json={"sku": "SKU-1", "reorder_point": 10, "safety_stock": 5},
        headers=admin_headers,
    )
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": 20, "reason": "seed"},
        headers=admin_headers,
    )

    # Above reorder point (20 > 10) -- no crossing yet.
    no_crossing_response = client.get("/notifications", headers=admin_headers)
    assert not any(n["type"] == "low_stock" for n in no_crossing_response.json())

    # Crosses below 10.
    client.post(
        "/inventory/adjustments",
        json={
            "sku": "SKU-1",
            "warehouse_id": warehouse_id,
            "quantity_delta": -15,
            "reason": "shrinkage",
        },
        headers=admin_headers,
    )

    response = client.get("/notifications", headers=admin_headers)
    low_stock = [n for n in response.json() if n["type"] == "low_stock"]
    assert len(low_stock) == 1
    assert low_stock[0]["resource_id"] == "SKU-1"
    assert low_stock[0]["is_read"] is False


def test_repeated_adjustments_while_already_low_do_not_notify_again(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    warehouse_id = client.post("/warehouses", json={"name": "Main"}, headers=admin_headers).json()[
        "id"
    ]
    client.post("/products", json={"sku": "SKU-1", "reorder_point": 10}, headers=admin_headers)
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": 5, "reason": "seed"},
        headers=admin_headers,
    )  # already below 10, first movement -- no "before" to cross from

    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": -1, "reason": "x"},
        headers=admin_headers,
    )  # still below 10, no new crossing

    response = client.get("/notifications", headers=admin_headers)
    assert not any(n["type"] == "low_stock" for n in response.json())


def test_submitting_a_purchase_order_notifies_approvers(client: TestClient) -> None:
    admin_headers = _auth_headers(client)  # admin has purchase_order:update
    supplier_id = client.post(
        "/suppliers",
        json={"name": "Acme", "lead_time_days": 5, "reliability_score": 0.9},
        headers=admin_headers,
    ).json()["id"]
    warehouse_id = client.post("/warehouses", json={"name": "Main"}, headers=admin_headers).json()[
        "id"
    ]
    client.post("/products", json={"sku": "SKU-1"}, headers=admin_headers)
    po_id = client.post(
        "/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "lines": [{"sku": "SKU-1", "quantity_ordered": 10}],
        },
        headers=admin_headers,
    ).json()["id"]

    client.post(f"/purchase-orders/{po_id}/submit", headers=admin_headers)

    response = client.get("/notifications", headers=admin_headers)
    po_notifications = [n for n in response.json() if n["type"] == "po_awaiting_approval"]
    assert len(po_notifications) == 1
    assert po_notifications[0]["resource_id"] == str(po_id)


def test_mark_notification_read_and_mark_all_read(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    warehouse_id = client.post("/warehouses", json={"name": "Main"}, headers=admin_headers).json()[
        "id"
    ]
    client.post("/products", json={"sku": "SKU-1", "reorder_point": 10}, headers=admin_headers)
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": 20, "reason": "seed"},
        headers=admin_headers,
    )
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": -15, "reason": "x"},
        headers=admin_headers,
    )
    notification_id = client.get("/notifications", headers=admin_headers).json()[0]["id"]

    mark_response = client.patch(
        f"/notifications/{notification_id}", json={"is_read": True}, headers=admin_headers
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["is_read"] is True

    unread_response = client.get(
        "/notifications", params={"unread_only": True}, headers=admin_headers
    )
    assert unread_response.json() == []

    mark_all_response = client.post("/notifications/mark-all-read", headers=admin_headers)
    assert mark_all_response.status_code == 204


def test_user_cannot_mark_someone_elses_notification_read(client: TestClient) -> None:
    admin_headers = _auth_headers(client)
    warehouse_id = client.post("/warehouses", json={"name": "Main"}, headers=admin_headers).json()[
        "id"
    ]
    client.post("/products", json={"sku": "SKU-1", "reorder_point": 10}, headers=admin_headers)
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": 20, "reason": "seed"},
        headers=admin_headers,
    )
    client.post(
        "/inventory/adjustments",
        json={"sku": "SKU-1", "warehouse_id": warehouse_id, "quantity_delta": -15, "reason": "x"},
        headers=admin_headers,
    )
    notification_id = client.get("/notifications", headers=admin_headers).json()[0]["id"]
    second_headers = _auth_headers(client, email="second@example.com")

    response = client.patch(
        f"/notifications/{notification_id}", json={"is_read": True}, headers=second_headers
    )

    assert response.status_code == 404
