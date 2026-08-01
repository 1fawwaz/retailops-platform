from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.category import Category
from models.product import Product
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from models.stock_movement import StockMovement
from services.rbac import assign_role, get_role_by_name
from services.security import create_access_token
from services.users import create_user
from services.warehouses import get_or_create_main_warehouse

TODAY = date(2026, 7, 29)
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC).replace(tzinfo=None)


def _auth_headers(db_session: Session) -> dict[str, str]:
    create_user(db_session, email="reader@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="reader@example.com")
    return {"Authorization": f"Bearer {token}"}


def _writer_headers(db_session: Session) -> dict[str, str]:
    user = create_user(
        db_session, email="writer@example.com", password="hunter22!!", is_read_only=False
    )
    # Bypasses /auth/register's first-user-becomes-admin bootstrap
    # (docs/BUILD.md Backend Module 10), so assign it directly here to
    # get an equivalent "can do everything" test user.
    admin_role = get_role_by_name(db_session, "admin")
    assert admin_role is not None
    assign_role(db_session, user.id, admin_role.id)
    token = create_access_token(subject="writer@example.com")
    return {"Authorization": f"Bearer {token}"}


def _seed_widgets(db_session: Session) -> None:
    category = Category(name="Widgets")
    db_session.add(category)
    db_session.flush()

    low = Product(
        sku="LOW-1",
        description="Low stock widget",
        category_id=category.id,
        unit_cost=2.0,
        reorder_point=10,
        safety_stock=5,
    )
    healthy = Product(
        sku="OK-1",
        description="Healthy stock widget",
        category_id=category.id,
        unit_cost=3.0,
        reorder_point=10,
        safety_stock=5,
    )
    dead = Product(
        sku="DEAD-1",
        description="Dead stock widget",
        category_id=category.id,
        unit_cost=1.5,
        reorder_point=10,
        safety_stock=5,
    )
    db_session.add_all([low, healthy, dead])
    db_session.flush()
    warehouse = get_or_create_main_warehouse(db_session)

    db_session.add_all(
        [
            StockLevel(
                sku="LOW-1", warehouse_id=warehouse.id, as_of_date=TODAY, quantity_on_hand=3
            ),
            StockLevel(
                sku="OK-1", warehouse_id=warehouse.id, as_of_date=TODAY, quantity_on_hand=500
            ),
            StockLevel(
                sku="DEAD-1", warehouse_id=warehouse.id, as_of_date=TODAY, quantity_on_hand=20
            ),
        ]
    )
    db_session.add_all(
        [
            StockMovement(
                sku="LOW-1",
                warehouse_id=warehouse.id,
                movement_date=NOW - timedelta(days=1),
                quantity_delta=-1,
                movement_type="sale",
                provenance="observed",
            ),
            StockMovement(
                sku="OK-1",
                warehouse_id=warehouse.id,
                movement_date=NOW - timedelta(days=1),
                quantity_delta=-1,
                movement_type="sale",
                provenance="observed",
            ),
            StockMovement(
                sku="DEAD-1",
                warehouse_id=warehouse.id,
                movement_date=NOW - timedelta(days=200),
                quantity_delta=20,
                movement_type="opening_balance",
                provenance="derived",
            ),
        ]
    )
    db_session.add_all(
        [
            SalesTransaction(
                invoice="INV-1",
                sku="OK-1",
                quantity=100,
                unit_price=5.0,
                country="UK",
                invoice_date=NOW - timedelta(days=1),
            ),
            SalesTransaction(
                invoice="INV-2",
                sku="LOW-1",
                quantity=1,
                unit_price=5.0,
                country="UK",
                invoice_date=NOW - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()


def test_stock_low_stock_filter(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/inventory/stock", params={"low_stock": True}, headers=headers)

    assert response.status_code == 200
    skus = {item["sku"] for item in response.json()}
    assert skus == {"LOW-1"}


def test_stock_category_and_search_filters(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/inventory/stock", params={"category": "widgets", "search": "healthy"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["sku"] == "OK-1"
    assert "unit_cost" not in body[0]
    for field in ("quantity_on_hand", "reorder_point", "safety_stock"):
        assert field in body[0]["_provenance"]


def test_low_stock_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/inventory/low-stock", headers=headers)

    assert response.status_code == 200
    skus = {item["sku"] for item in response.json()}
    assert skus == {"LOW-1"}


def test_dead_stock_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/inventory/dead-stock", params={"days": 90}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    skus = {item["sku"] for item in body}
    assert skus == {"DEAD-1"}
    assert body[0]["days_since_movement"] >= 199


def test_slow_movers_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/inventory/slow-movers",
        params={"velocity_threshold": 0.5},
        headers=headers,
    )

    assert response.status_code == 200
    skus = {item["sku"] for item in response.json()}
    assert "LOW-1" in skus
    assert "OK-1" not in skus


def test_valuation_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/inventory/valuation", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["by_category"][0]["category"] == "Widgets"
    expected_value = 3 * 2.0 + 500 * 3.0 + 20 * 1.5
    assert body["total_inventory_value"] == expected_value
    for field in ("total_quantity_on_hand", "total_inventory_value"):
        assert field in body["_provenance"]


def test_adjustment_changes_stock_and_records_a_ledger_entry(
    client: TestClient, db_session: Session
) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    warehouse_id = get_or_create_main_warehouse(db_session).id

    response = client.post(
        "/inventory/adjustments",
        json={
            "sku": "OK-1",
            "warehouse_id": warehouse_id,
            "quantity_delta": -5,
            "reason": "Cycle count correction",
        },
        headers=headers,
    )
    assert response.status_code == 204, response.text

    stock_response = client.get("/inventory/stock", params={"search": "OK-1"}, headers=headers)
    assert stock_response.json()[0]["quantity_on_hand"] == 500 - 5  # seeded snapshot + adjustment

    ledger_response = client.get("/inventory/OK-1/ledger", headers=headers)
    entries = ledger_response.json()
    adjustment_entries = [e for e in entries if e["movement_type"] == "adjustment"]
    assert len(adjustment_entries) == 1
    assert adjustment_entries[0]["quantity_delta"] == -5
    assert adjustment_entries[0]["reference"] == "Cycle count correction"
    assert adjustment_entries[0]["warehouse_id"] == warehouse_id


def test_adjustment_driving_stock_below_zero_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    warehouse_id = get_or_create_main_warehouse(db_session).id

    response = client.post(
        "/inventory/adjustments",
        json={"sku": "LOW-1", "warehouse_id": warehouse_id, "quantity_delta": -999, "reason": "x"},
        headers=headers,
    )

    assert response.status_code == 400


def test_transfer_moves_stock_between_warehouses(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    main_id = get_or_create_main_warehouse(db_session).id
    other_response = client.post("/warehouses", json={"name": "North Depot"}, headers=headers)
    other_id = other_response.json()["id"]

    response = client.post(
        "/inventory/transfers",
        json={
            "sku": "OK-1",
            "from_warehouse_id": main_id,
            "to_warehouse_id": other_id,
            "quantity": 50,
            "reason": "Rebalancing",
        },
        headers=headers,
    )
    assert response.status_code == 204, response.text

    # Total across both warehouses is unchanged; the split moved.
    stock_response = client.get("/inventory/stock", params={"search": "OK-1"}, headers=headers)
    assert stock_response.json()[0]["quantity_on_hand"] == 500  # unchanged total

    ledger_response = client.get("/inventory/OK-1/ledger", headers=headers)
    transfer_entries = [e for e in ledger_response.json() if e["movement_type"] == "transfer"]
    assert len(transfer_entries) == 2
    deltas_by_warehouse = {e["warehouse_id"]: e["quantity_delta"] for e in transfer_entries}
    assert deltas_by_warehouse[main_id] == -50
    assert deltas_by_warehouse[other_id] == 50


def test_transfer_with_insufficient_stock_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    main_id = get_or_create_main_warehouse(db_session).id
    other_response = client.post("/warehouses", json={"name": "North Depot"}, headers=headers)
    other_id = other_response.json()["id"]

    response = client.post(
        "/inventory/transfers",
        json={
            "sku": "LOW-1",
            "from_warehouse_id": main_id,
            "to_warehouse_id": other_id,
            "quantity": 999,
        },
        headers=headers,
    )

    assert response.status_code == 400


def test_transfer_to_the_same_warehouse_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    main_id = get_or_create_main_warehouse(db_session).id

    response = client.post(
        "/inventory/transfers",
        json={
            "sku": "OK-1",
            "from_warehouse_id": main_id,
            "to_warehouse_id": main_id,
            "quantity": 1,
        },
        headers=headers,
    )

    assert response.status_code == 400


def test_transfer_for_unknown_sku_is_404(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    main_id = get_or_create_main_warehouse(db_session).id
    other_response = client.post("/warehouses", json={"name": "North Depot"}, headers=headers)
    other_id = other_response.json()["id"]

    response = client.post(
        "/inventory/transfers",
        json={
            "sku": "DOES-NOT-EXIST",
            "from_warehouse_id": main_id,
            "to_warehouse_id": other_id,
            "quantity": 1,
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_transfer_to_unknown_warehouse_is_404(client: TestClient, db_session: Session) -> None:
    _seed_widgets(db_session)
    headers = _writer_headers(db_session)
    main_id = get_or_create_main_warehouse(db_session).id

    response = client.post(
        "/inventory/transfers",
        json={
            "sku": "OK-1",
            "from_warehouse_id": main_id,
            "to_warehouse_id": 999999,
            "quantity": 1,
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_read_only_user_cannot_create_adjustments_or_transfers(
    client: TestClient, db_session: Session
) -> None:
    _seed_widgets(db_session)
    headers = _auth_headers(db_session)
    warehouse_id = get_or_create_main_warehouse(db_session).id

    adjustment_response = client.post(
        "/inventory/adjustments",
        json={"sku": "OK-1", "warehouse_id": warehouse_id, "quantity_delta": 1, "reason": "x"},
        headers=headers,
    )
    assert adjustment_response.status_code == 403

    transfer_response = client.post(
        "/inventory/transfers",
        json={
            "sku": "OK-1",
            "from_warehouse_id": warehouse_id,
            "to_warehouse_id": warehouse_id,
            "quantity": 1,
        },
        headers=headers,
    )
    assert transfer_response.status_code == 403


def test_ledger_for_unknown_sku_is_404(client: TestClient, db_session: Session) -> None:
    headers = _auth_headers(db_session)

    response = client.get("/inventory/DOES-NOT-EXIST/ledger", headers=headers)

    assert response.status_code == 404
