import math
from datetime import date
from typing import cast

import pandas as pd

from scripts.etl.stock_ledger import (
    OPENING_BALANCE_FLOOR,
    OPENING_BALANCE_MULTIPLIER,
    replay_stock_ledger,
)


def _transactions(sku: str, entries: list[tuple[str, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sku": [sku] * len(entries),
            "invoice_date": [pd.Timestamp(date) for date, _ in entries],
            "quantity": [qty for _, qty in entries],
        }
    )


def test_opening_balance_matches_documented_formula() -> None:
    # total qty = 25 over a 3-day window (2024-01-01 to 2024-01-03) -> avg = 25/3
    df = _transactions("A1", [("2024-01-01", 5), ("2024-01-03", 20)])

    result = replay_stock_ledger(df, {"A1": 1})

    opening = next(m for m in result.stock_movements if m["movement_type"] == "opening_balance")
    expected = max(OPENING_BALANCE_FLOOR, math.ceil(OPENING_BALANCE_MULTIPLIER * (25 / 3)))
    assert opening["quantity_delta"] == expected
    assert opening["provenance"] == "derived"


def test_purchase_order_injected_when_balance_would_go_negative() -> None:
    # opening=17 (see above); day1 -5 -> 12; day3 -20 -> -8, deficit 8,
    # order_qty = 8 + ceil(25/3) = 8 + 9 = 17 -> ending balance 9
    df = _transactions("A1", [("2024-01-01", 5), ("2024-01-03", 20)])

    result = replay_stock_ledger(df, {"A1": 1})

    assert len(result.purchase_orders) == 1
    po = result.purchase_orders[0]
    assert po["quantity"] == 17
    assert po["supplier_id"] == 1
    assert po["status"] == "received"
    assert po["order_date"] == po["expected_arrival_date"]

    last_level = result.stock_levels[-1]
    assert last_level["quantity_on_hand"] == 9


def test_stock_levels_never_go_negative() -> None:
    df = _transactions(
        "A1",
        [
            ("2024-01-01", 3),
            ("2024-01-02", 50),  # forces a purchase order
            ("2024-01-03", 40),  # forces another
            ("2024-01-05", 1),  # gap day (01-04) with no sales
        ],
    )

    result = replay_stock_ledger(df, {"A1": 1})

    assert all(cast(int, level["quantity_on_hand"]) >= 0 for level in result.stock_levels)


def test_stock_levels_cover_every_day_in_the_active_range_including_gaps() -> None:
    df = _transactions("A1", [("2024-01-01", 1), ("2024-01-05", 1)])

    result = replay_stock_ledger(df, {"A1": 1})

    dates = sorted(cast(date, level["as_of_date"]) for level in result.stock_levels)
    assert dates == [
        pd.Timestamp(d).date()
        for d in ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    ]


def test_multiple_skus_are_handled_independently() -> None:
    df = pd.concat(
        [
            _transactions("A1", [("2024-01-01", 5)]),
            _transactions("B1", [("2024-01-01", 3), ("2024-01-02", 3)]),
        ],
        ignore_index=True,
    )

    result = replay_stock_ledger(df, {"A1": 1, "B1": 2})

    skus_in_levels = {level["sku"] for level in result.stock_levels}
    assert skus_in_levels == {"A1", "B1"}
