"""Stage 4 Task 4.3: recommended order quantity. The spec's own
inventory_cost formula (`inventory_cost = recommended_order_qty ×
unit_cost`) depends on this value but never defines how to compute it
anywhere in the document -- confirmed by a full-text search, not an
oversight in reading. Resolved with the user rather than guessed
silently (see project memory): the standard reorder-to-target-level
formula, using only fields already wired up elsewhere in this codebase
(Task 4.1's reorder_timing tool uses the same four inputs) --

    recommended_order_qty = predicted_daily_demand * lead_time_days
                             + safety_stock - quantity_on_hand

i.e. order enough to cover demand through the supplier's lead time plus
the safety-stock buffer, given what's already on hand. Floored at 0 --
a SKU that already has more than enough stock needs no order, never a
negative quantity.
"""

from __future__ import annotations


def compute_recommended_order_qty(
    *,
    predicted_daily_demand: float,
    lead_time_days: int,
    safety_stock: int,
    quantity_on_hand: int,
) -> int:
    raw = predicted_daily_demand * lead_time_days + safety_stock - quantity_on_hand
    return max(0, round(raw))
