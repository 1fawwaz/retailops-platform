import pandas as pd

from scripts.etl.clean import clean


def _row(
    invoice: str, sku: str | None, description: str | None, quantity: int
) -> dict[str, object]:
    return {
        "Invoice": invoice,
        "StockCode": sku,
        "Description": description,
        "Quantity": quantity,
        "InvoiceDate": pd.Timestamp("2010-01-01"),
        "Price": 1.0,
        "Customer ID": 12345.0,
        "Country": "United Kingdom",
    }


def test_clean_drops_cancellations() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("C536366", "A1", "Widget", 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_cancellations"] == 1
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["Invoice"] == "536365"


def test_clean_drops_non_positive_quantity() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536367", "A1", "Widget", 0),
            _row("536368", "A1", "Widget", -5),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_non_positive_quantity"] == 2
    assert len(cleaned) == 1


def test_clean_drops_null_stockcode() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536369", None, "Mystery", 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_null_stockcode"] == 1
    assert len(cleaned) == 1


def test_clean_drops_test_rows() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536370", "TEST001", "This is a test product.", 1),
            _row("536371", "22355", "test", 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_test_rows"] == 2
    assert len(cleaned) == 1


def test_clean_drops_admin_codes_but_keeps_real_lookalikes() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536372", "POST", "POSTAGE", 1),
            _row("536373", "PADS", "PADS TO MATCH ALL CUSHIONS", 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_admin_codes"] == 1
    assert set(cleaned["StockCode"]) == {"A1", "PADS"}


def test_clean_reports_remaining_rows() -> None:
    df = pd.DataFrame([_row("536365", "A1", "Widget", 1) for _ in range(3)])

    _, counts = clean(df)

    assert counts["raw_rows"] == 3
    assert counts["remaining_rows"] == 3
