from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.category import Category
from models.product import Product
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from services.security import create_access_token
from services.users import create_user


def _auth_headers(db_session: Session) -> dict[str, str]:
    create_user(db_session, email="reader@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="reader@example.com")
    return {"Authorization": f"Bearer {token}"}


def _seed_sales(db_session: Session) -> None:
    widgets = Category(name="Widgets")
    gadgets = Category(name="Gadgets")
    db_session.add_all([widgets, gadgets])
    db_session.flush()

    best_seller = Product(
        sku="BEST-1", description="Best seller", category_id=widgets.id, unit_cost=2.0
    )
    mid = Product(sku="MID-1", description="Mid performer", category_id=widgets.id, unit_cost=5.0)
    worst = Product(
        sku="WORST-1", description="Worst performer", category_id=gadgets.id, unit_cost=1.0
    )
    db_session.add_all([best_seller, mid, worst])
    db_session.flush()

    db_session.add_all(
        [
            StockLevel(sku="BEST-1", as_of_date=date(2026, 1, 15), quantity_on_hand=100),
            StockLevel(sku="MID-1", as_of_date=date(2026, 1, 15), quantity_on_hand=50),
            StockLevel(sku="WORST-1", as_of_date=date(2026, 1, 15), quantity_on_hand=20),
        ]
    )
    db_session.add_all(
        [
            SalesTransaction(
                invoice="INV-1",
                sku="BEST-1",
                quantity=100,
                unit_price=10.0,
                country="UK",
                invoice_date=datetime(2026, 1, 10, 9, 0),
            ),
            SalesTransaction(
                invoice="INV-2",
                sku="MID-1",
                quantity=10,
                unit_price=10.0,
                country="UK",
                invoice_date=datetime(2026, 1, 10, 9, 0),
            ),
            SalesTransaction(
                invoice="INV-3",
                sku="WORST-1",
                quantity=1,
                unit_price=10.0,
                country="UK",
                invoice_date=datetime(2026, 1, 10, 9, 0),
            ),
            SalesTransaction(
                invoice="INV-4",
                sku="BEST-1",
                quantity=50,
                unit_price=10.0,
                country="UK",
                invoice_date=datetime(2026, 2, 5, 9, 0),
            ),
        ]
    )
    db_session.commit()


def test_revenue_grouped_by_category(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/analytics/revenue", params={"group_by": "category"}, headers=headers)

    assert response.status_code == 200
    body = {row["period"]: row for row in response.json()}
    assert body["Widgets"]["revenue"] == (100 + 50 + 10) * 10.0
    assert body["Gadgets"]["revenue"] == 1 * 10.0
    for row in body.values():
        assert "revenue" in row["_provenance"]


def test_revenue_grouped_by_month_with_date_filter(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/analytics/revenue",
        params={"group_by": "month", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["period"] == "2026-01"
    assert body[0]["revenue"] == (100 + 10 + 1) * 10.0


def test_profit_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get("/analytics/profit", params={"group_by": "category"}, headers=headers)

    assert response.status_code == 200
    body = {row["period"]: row for row in response.json()}
    widgets_revenue = (100 + 50 + 10) * 10.0
    widgets_cost = 150 * 2.0 + 10 * 5.0
    assert body["Widgets"]["cost"] == widgets_cost
    assert body["Widgets"]["gross_profit"] == widgets_revenue - widgets_cost
    for row in body.values():
        for field in ("revenue", "cost", "gross_profit", "margin"):
            assert field in row["_provenance"]


def test_profit_grouped_by_month_with_date_filter(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/analytics/profit",
        params={"group_by": "month", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["period"] == "2026-01"


def test_turnover_endpoint(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/analytics/turnover",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=headers,
    )

    assert response.status_code == 200
    rows = {row["category"]: row for row in response.json()}
    assert rows["Widgets"]["units_sold"] == 110
    assert rows["Widgets"]["avg_quantity_on_hand"] == 75.0


def test_abc_classification(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    # Revenue shares here: BEST-1 ~93.2%, MID-1 ~99.4% cumulative, WORST-1 100%.
    # Custom thresholds so all three classes are exercised.
    response = client.get(
        "/analytics/abc",
        params={
            "a_threshold": 0.95,
            "b_threshold": 0.999,
            "start_date": "2026-01-01",
            "end_date": "2026-02-28",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = {row["sku"]: row for row in response.json()}
    assert body["BEST-1"]["abc_class"] == "A"
    assert body["MID-1"]["abc_class"] == "B"
    assert body["WORST-1"]["abc_class"] == "C"
    for row in body.values():
        assert "revenue" in row["_provenance"]
        assert "cumulative_pct" in row["_provenance"]


def test_top_and_bottom_products(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    top_response = client.get(
        "/analytics/top-products",
        params={
            "metric": "revenue",
            "limit": 1,
            "start_date": "2026-01-01",
            "end_date": "2026-02-28",
        },
        headers=headers,
    )
    bottom_response = client.get(
        "/analytics/bottom-products", params={"metric": "revenue", "limit": 1}, headers=headers
    )

    assert top_response.status_code == 200
    assert bottom_response.status_code == 200
    assert top_response.json()[0]["sku"] == "BEST-1"
    assert bottom_response.json()[0]["sku"] == "WORST-1"


def test_top_products_by_units_and_margin(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    units_response = client.get(
        "/analytics/top-products", params={"metric": "units", "limit": 1}, headers=headers
    )
    margin_response = client.get(
        "/analytics/top-products", params={"metric": "margin", "limit": 3}, headers=headers
    )

    assert units_response.status_code == 200
    assert margin_response.status_code == 200
    assert units_response.json()[0]["sku"] == "BEST-1"
    assert {row["sku"] for row in margin_response.json()} == {"BEST-1", "MID-1", "WORST-1"}


def test_period_comparison(client: TestClient, db_session: Session) -> None:
    _seed_sales(db_session)
    headers = _auth_headers(db_session)

    response = client.get(
        "/analytics/period-comparison",
        params={
            "period1_start": "2026-01-01",
            "period1_end": "2026-01-31",
            "period2_start": "2026-02-01",
            "period2_end": "2026-02-28",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["period1_revenue"] == (100 + 10 + 1) * 10.0
    assert body["period2_revenue"] == 50 * 10.0
    assert body["revenue_delta"] == body["period2_revenue"] - body["period1_revenue"]
    for field in ("period1_revenue", "period2_revenue", "revenue_delta", "revenue_delta_pct"):
        assert field in body["_provenance"]
