from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.category import Category
from models.product import Product
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from models.stock_movement import StockMovement
from services.security import create_access_token
from services.users import create_user

TODAY = date(2026, 7, 29)
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC).replace(tzinfo=None)


def _auth_headers(db_session: Session) -> dict[str, str]:
    create_user(db_session, email="reader@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="reader@example.com")
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

    db_session.add_all(
        [
            StockLevel(sku="LOW-1", as_of_date=TODAY, quantity_on_hand=3),
            StockLevel(sku="OK-1", as_of_date=TODAY, quantity_on_hand=500),
            StockLevel(sku="DEAD-1", as_of_date=TODAY, quantity_on_hand=20),
        ]
    )
    db_session.add_all(
        [
            StockMovement(
                sku="LOW-1",
                movement_date=NOW - timedelta(days=1),
                quantity_delta=-1,
                movement_type="sale",
                provenance="observed",
            ),
            StockMovement(
                sku="OK-1",
                movement_date=NOW - timedelta(days=1),
                quantity_delta=-1,
                movement_type="sale",
                provenance="observed",
            ),
            StockMovement(
                sku="DEAD-1",
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
