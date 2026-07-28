"""Step (f): replay sales chronologically for daily stock-on-hand per SKU.

See docs/data-derivation.md#stock-ledger.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

OPENING_BALANCE_MULTIPLIER = 2
OPENING_BALANCE_FLOOR = 10


@dataclass
class LedgerResult:
    stock_movements: list[dict[str, object]] = field(default_factory=list)
    stock_levels: list[dict[str, object]] = field(default_factory=list)
    purchase_orders: list[dict[str, object]] = field(default_factory=list)


def replay_stock_ledger(
    transactions_df: pd.DataFrame,
    sku_to_supplier_id: dict[str, int],
) -> LedgerResult:
    """transactions_df needs columns sku, invoice_date, quantity.
    sku_to_supplier_id maps every sku present to its assigned supplier (from
    step e) -- purchase_orders.supplier_id is not nullable.

    For each SKU: opening_balance = max(10, ceil(2 x average daily demand
    over its observed date range)) -- "seed" here means establish a starting
    value from a documented formula, not a random draw; there's no RNG in
    this step. Then walk day by day from the SKU's first to last sale date,
    subtracting each day's sold quantity from a running balance. Whenever
    that would go negative, inject a purchase order dated the same day
    (received immediately -- this is a reactive backfill of historical gaps,
    not a forward-looking procurement simulation) sized to cover the deficit
    plus one more day's average demand as a buffer.
    """
    result = LedgerResult()

    df = transactions_df.copy()
    df["sale_date"] = pd.to_datetime(df["invoice_date"]).dt.normalize()

    for sku, group in df.groupby("sku", sort=True):
        daily = group.groupby("sale_date")["quantity"].sum()
        first_date = daily.index.min()
        last_date = daily.index.max()
        num_days = (last_date - first_date).days + 1
        avg_daily_demand = float(daily.sum()) / num_days

        opening_balance = max(
            OPENING_BALANCE_FLOOR, math.ceil(OPENING_BALANCE_MULTIPLIER * avg_daily_demand)
        )
        result.stock_movements.append(
            {
                "sku": sku,
                "movement_date": first_date,
                "quantity_delta": opening_balance,
                "movement_type": "opening_balance",
                "reference": None,
                "provenance": "derived",
            }
        )

        running_balance = opening_balance
        supplier_id = sku_to_supplier_id[str(sku)]

        for day in pd.date_range(first_date, last_date, freq="D"):
            qty_sold = int(daily.get(day, 0))
            if qty_sold > 0:
                running_balance -= qty_sold
                result.stock_movements.append(
                    {
                        "sku": sku,
                        "movement_date": day,
                        "quantity_delta": -qty_sold,
                        "movement_type": "sale",
                        "reference": None,
                        "provenance": "observed",
                    }
                )

            if running_balance < 0:
                deficit = -running_balance
                order_qty = deficit + math.ceil(avg_daily_demand)
                result.purchase_orders.append(
                    {
                        "sku": sku,
                        "supplier_id": supplier_id,
                        "order_date": day.date(),
                        "quantity": order_qty,
                        "expected_arrival_date": day.date(),
                        "status": "received",
                    }
                )
                result.stock_movements.append(
                    {
                        "sku": sku,
                        "movement_date": day,
                        "quantity_delta": order_qty,
                        "movement_type": "purchase_order",
                        "reference": None,
                        "provenance": "derived",
                    }
                )
                running_balance += order_qty

            result.stock_levels.append(
                {
                    "sku": sku,
                    "as_of_date": day.date(),
                    "quantity_on_hand": running_balance,
                }
            )

    return result
