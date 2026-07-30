"""Stage 4 Task 4.4: capital tied up in dead stock --
`sum(quantity_on_hand * unit_cost)` across every dead-stock SKU.
StockPilot's `get_dead_stock` endpoint returns `quantity_on_hand` and
`days_since_movement` but not cost (`clients/stockpilot_models.py::DeadStockItem`
has no cost field); `unit_cost` lives on the product record, so this
needs one `get_product` lookup per dead-stock SKU.

Bounded by `limit` (config/thresholds.yaml's `workflows.dead_stock_lookup_limit`
-- CLAUDE.md section 8, no hardcoded threshold here): the same
documented-limitation pattern as services/pricing.py's `lookup_limit` --
a catalog with more dead-stock SKUs than `limit` undercounts, stated
plainly rather than silently exhaustive-scanned at unbounded HTTP cost.
A SKU missing a recorded unit_cost is skipped from the sum (also
undercounting, not a fabricated cost) rather than raising, since this is
a summary aggregate over potentially many SKUs, not a single grounded
per-SKU decision the way Task 4.3's recommendations are.

Takes the already-built StructuredTool objects (tools/stockpilot_tools.py)
rather than a raw StockPilotClient, so every lookup still persists a
`tool_calls` row -- the same reasoning services/pricing.py documents.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool


def compute_dead_stock_capital(
    *,
    dead_stock_tool: StructuredTool,
    get_product_tool: StructuredTool,
    days: int,
    limit: int,
) -> float:
    items = dead_stock_tool.invoke({"days": days, "limit": limit, "offset": 0})
    total = 0.0
    for item in items:
        product = get_product_tool.invoke({"sku": item.sku})
        if product.unit_cost is not None:
            total += item.quantity_on_hand * product.unit_cost
    return total
