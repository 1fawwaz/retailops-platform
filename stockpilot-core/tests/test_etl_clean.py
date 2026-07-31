from pathlib import Path

import openpyxl
import pandas as pd

from scripts.etl.clean import clean, iter_raw_chunks


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


def test_clean_drops_gift_voucher_stockcode_family() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536374", "gift_0001_20", "Dotcomgiftshop Gift Voucher £20.00", 1),
            _row("536375", "gift_0001_80", None, 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_admin_codes"] == 2
    assert set(cleaned["StockCode"]) == {"A1"}


def test_clean_drops_specific_administrative_skus_found_in_the_data() -> None:
    df = pd.DataFrame(
        [
            _row("536365", "A1", "Widget", 1),
            _row("536376", "22016", "Dotcomgiftshop Gift Voucher £100.00", 1),
            _row("536377", "23595", "adjustment", 1),
            _row("536378", "35600A", "Found by jackie", 1),
        ]
    )

    cleaned, counts = clean(df)

    assert counts["dropped_admin_codes"] == 3
    assert set(cleaned["StockCode"]) == {"A1"}


def test_clean_reports_remaining_rows() -> None:
    df = pd.DataFrame([_row("536365", "A1", "Widget", 1) for _ in range(3)])

    _, counts = clean(df)

    assert counts["raw_rows"] == 3
    assert counts["remaining_rows"] == 3


def _write_workbook(path: Path, sheets: dict[str, list[tuple[object, ...]]]) -> None:
    header = ["Invoice", "StockCode", "Description", "Quantity"]
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    assert default_sheet is not None
    workbook.remove(default_sheet)
    for sheet_name, rows in sheets.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(header)
        for row in rows:
            sheet.append(row)
    workbook.save(path)


def test_iter_raw_chunks_splits_into_chunk_size_pieces(tmp_path: Path) -> None:
    path = tmp_path / "raw.xlsx"
    rows: list[tuple[object, ...]] = [(f"{i}", "A1", "Widget", 1) for i in range(10)]
    _write_workbook(path, {"Sheet1": rows})

    chunks = list(iter_raw_chunks(path, chunk_size=3))

    assert [len(chunk) for chunk in chunks] == [3, 3, 3, 1]
    assert sum(len(chunk) for chunk in chunks) == 10
    assert list(chunks[0].columns) == ["Invoice", "StockCode", "Description", "Quantity"]


def test_iter_raw_chunks_reads_every_sheet(tmp_path: Path) -> None:
    path = tmp_path / "raw.xlsx"
    _write_workbook(
        path,
        {
            "Year1": [("1", "A1", "Widget", 1), ("2", "A1", "Widget", 1)],
            "Year2": [("3", "B2", "Gadget", 1)],
        },
    )

    chunks = list(iter_raw_chunks(path, chunk_size=50_000))

    assert sum(len(chunk) for chunk in chunks) == 3
    all_invoices = {invoice for chunk in chunks for invoice in chunk["Invoice"]}
    assert all_invoices == {"1", "2", "3"}


def test_iter_raw_chunks_preserves_row_values(tmp_path: Path) -> None:
    path = tmp_path / "raw.xlsx"
    _write_workbook(path, {"Sheet1": [("536365", "A1", "Widget", 5)]})

    (chunk,) = list(iter_raw_chunks(path, chunk_size=50_000))

    assert chunk.iloc[0]["Invoice"] == "536365"
    assert chunk.iloc[0]["StockCode"] == "A1"
    assert chunk.iloc[0]["Description"] == "Widget"
    assert chunk.iloc[0]["Quantity"] == 5
