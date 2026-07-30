"""Stage 4 Task 4.3: per-SKU unit price lookup -- a documented StockPilot
gap, not a StockPilot endpoint (see docs/stockpilot-gaps.md#2).
`unit_price` only exists inside StockPilot Core's raw sales_transaction
table; the only endpoints that expose a derivable price
(`revenue / units`) are the global top/bottom-products rankings, not
filterable by an exact SKU.

Resolved with the user (see project memory): search a large-limit
top/bottom-products fetch for the requested SKU and derive
`unit_price = revenue / units` if found; return None (never a guessed
or defaulted price) if the SKU appears in neither ranking. Coverage is
therefore bounded by `lookup_limit` (config/thresholds.yaml), not
exhaustive across the whole catalog -- an accepted, documented
limitation, not a bug.

Takes the already-built StructuredTool objects (tools/stockpilot_tools.py)
rather than a raw StockPilotClient, so each lookup still persists a
`tool_calls` row exactly the same way an agent's own tool call would --
the Decision Engine has no tools of its own (invariant 1), but the
numbers it's given must still be traceable via tool_call_id.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from clients.stockpilot_models import ProductPerformanceRow


def _price_from_rows(rows: list[ProductPerformanceRow], sku: str) -> float | None:
    for row in rows:
        if row.sku == sku and row.units > 0:
            return row.revenue / row.units
    return None


def find_unit_price(
    *,
    top_products_tool: StructuredTool,
    bottom_products_tool: StructuredTool,
    sku: str,
    limit: int,
) -> float | None:
    top_rows = top_products_tool.invoke({"metric": "revenue", "limit": limit})
    price = _price_from_rows(top_rows, sku)
    if price is not None:
        return price

    bottom_rows = bottom_products_tool.invoke({"metric": "revenue", "limit": limit})
    return _price_from_rows(bottom_rows, sku)
