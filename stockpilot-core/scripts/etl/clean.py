"""Step (a): clean the raw Online Retail II transaction log.

See docs/data-derivation.md#cleaning for why each filter exists.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "online_retail_II.xlsx"
)

TEST_STOCK_CODES = {"TEST001", "TEST002"}

ADMIN_STOCK_CODES = {
    "POST",
    "DOT",
    "D",
    "M",
    "m",
    "ADJUST",
    "S",
    "B",
    "AMAZONFEE",
    "CRUK",
    "C2",
    "BANK CHARGES",
    "GIFT",
    # Found while sanity-checking step (d)'s derived unit_cost: these three
    # produced unit_cost=0.00 because their entire observed history is
    # administrative, not merchandise.
    "22016",  # 3 rows: 2 null description, 1 "Dotcomgiftshop Gift Voucher
    # £100.00" -- a gift voucher, not a physical product
    "23595",  # 1 row, Description "adjustment"
    "35600A",  # 1 row, Description "Found by jackie"
}

# The Dotcomgiftshop Gift Voucher family (gift_0001_10 through gift_0001_90):
# financial instruments, not merchandise, regardless of what garbled text
# appears in Description on any given row (some rows are null, one says
# "to push order througha s stock was").
GIFT_VOUCHER_STOCKCODE_PREFIX = "gift_"


def load_raw(path: Path = RAW_DATA_PATH) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None)
    return pd.concat(sheets.values(), ignore_index=True)


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    counts: dict[str, int] = {"raw_rows": len(df)}

    is_cancellation = df["Invoice"].astype(str).str.startswith("C")
    counts["dropped_cancellations"] = int(is_cancellation.sum())
    df = df.loc[~is_cancellation]

    is_non_positive_quantity = df["Quantity"] <= 0
    counts["dropped_non_positive_quantity"] = int(is_non_positive_quantity.sum())
    df = df.loc[~is_non_positive_quantity]

    is_null_stockcode = df["StockCode"].isna()
    counts["dropped_null_stockcode"] = int(is_null_stockcode.sum())
    df = df.loc[~is_null_stockcode]

    stockcode_upper = df["StockCode"].astype(str).str.upper()
    description_clean = df["Description"].astype(str).str.strip().str.lower()
    is_test_row = stockcode_upper.isin(TEST_STOCK_CODES) | (description_clean == "test")
    counts["dropped_test_rows"] = int(is_test_row.sum())
    df = df.loc[~is_test_row]

    stockcode_str = df["StockCode"].astype(str)
    is_admin_code = stockcode_str.isin(
        ADMIN_STOCK_CODES
    ) | stockcode_str.str.lower().str.startswith(GIFT_VOUCHER_STOCKCODE_PREFIX)
    counts["dropped_admin_codes"] = int(is_admin_code.sum())
    df = df.loc[~is_admin_code]

    counts["remaining_rows"] = len(df)
    return df.reset_index(drop=True), counts
