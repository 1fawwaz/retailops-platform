from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.product import Product
from models.sales_transaction import SalesTransaction
from services.security import create_access_token
from services.users import create_user

NOW = datetime(2026, 7, 29, 12, 0)


def _auth_headers(db_session: Session) -> dict[str, str]:
    create_user(db_session, email="reader@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="reader@example.com")
    return {"Authorization": f"Bearer {token}"}


def _seed_forecast_data(db_session: Session) -> None:
    ok_sku = Product(sku="OK-1", description="Steady seller")
    thin_sku = Product(sku="THIN-1", description="New arrival")
    db_session.add_all([ok_sku, thin_sku])
    db_session.flush()

    transactions = []
    for day in range(40):
        transactions.append(
            SalesTransaction(
                invoice=f"INV-OK-{day}",
                sku="OK-1",
                quantity=5 + (day % 3),
                unit_price=9.99,
                country="UK",
                invoice_date=NOW - timedelta(days=39 - day),
            )
        )
    for day in range(5):
        transactions.append(
            SalesTransaction(
                invoice=f"INV-THIN-{day}",
                sku="THIN-1",
                quantity=2,
                unit_price=4.5,
                country="UK",
                invoice_date=NOW - timedelta(days=4 - day),
            )
        )
    db_session.add_all(transactions)
    db_session.commit()


def test_forecast_demand_returns_one_row_per_sku_in_order(
    client: TestClient, db_session: Session
) -> None:
    _seed_forecast_data(db_session)
    headers = _auth_headers(db_session)

    response = client.post(
        "/forecast/demand",
        json={"skus": ["OK-1", "THIN-1", "NEVER-SOLD"], "horizon_days": 14},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert [row["sku"] for row in body] == ["OK-1", "THIN-1", "NEVER-SOLD"]


def test_forecast_demand_ok_history_uses_a_real_model(
    client: TestClient, db_session: Session
) -> None:
    _seed_forecast_data(db_session)
    headers = _auth_headers(db_session)

    response = client.post(
        "/forecast/demand", json={"skus": ["OK-1"], "horizon_days": 14}, headers=headers
    )

    assert response.status_code == 200
    row = response.json()[0]
    assert row["data_quality"] == "ok"
    assert row["model_used"] in ("gbm", "seasonal_naive", "moving_average")
    assert row["predicted_daily_demand"] > 0
    assert row["confidence_interval_lower"] <= row["predicted_daily_demand"]
    assert row["confidence_interval_upper"] >= row["predicted_daily_demand"]
    assert row["training_window_start"] is not None
    assert row["training_window_end"] is not None
    for field in (
        "predicted_daily_demand",
        "confidence_interval_lower",
        "confidence_interval_upper",
    ):
        assert row["_provenance"][field] == "predicted"


def test_forecast_demand_thin_history_flagged(client: TestClient, db_session: Session) -> None:
    _seed_forecast_data(db_session)
    headers = _auth_headers(db_session)

    response = client.post(
        "/forecast/demand", json={"skus": ["THIN-1"], "horizon_days": 7}, headers=headers
    )

    assert response.status_code == 200
    row = response.json()[0]
    assert row["data_quality"] == "thin_history"
    assert row["model_used"] in ("seasonal_naive", "moving_average")


def test_forecast_demand_no_history_returns_zero(client: TestClient, db_session: Session) -> None:
    _seed_forecast_data(db_session)
    headers = _auth_headers(db_session)

    response = client.post(
        "/forecast/demand", json={"skus": ["NEVER-SOLD"], "horizon_days": 7}, headers=headers
    )

    assert response.status_code == 200
    row = response.json()[0]
    assert row["data_quality"] == "no_history"
    assert row["model_used"] == "none"
    assert row["predicted_daily_demand"] == 0.0
    assert row["training_window_start"] is None


def test_forecast_demand_rejects_empty_sku_list(client: TestClient, db_session: Session) -> None:
    headers = _auth_headers(db_session)

    response = client.post(
        "/forecast/demand", json={"skus": [], "horizon_days": 7}, headers=headers
    )

    assert response.status_code == 422


def test_forecast_accuracy_reports_all_models_honestly(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth_headers(db_session)

    response = client.get("/forecast/accuracy", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["selected_model"] in ("seasonal_naive", "moving_average", "gbm")
    for field in (
        "seasonal_naive_mae",
        "seasonal_naive_mape",
        "moving_average_mae",
        "moving_average_mape",
        "gbm_mae",
        "gbm_mape",
    ):
        assert isinstance(body[field], int | float)
        assert field in body["_provenance"]
        assert body["_provenance"][field] == "derived"
