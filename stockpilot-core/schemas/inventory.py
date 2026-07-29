from datetime import date, datetime

from pydantic import ConfigDict

from schemas.provenance import ProvenanceMixin

STOCK_DERIVATION_REF = {
    "quantity_on_hand": "data-derivation.md#stock-ledger",
    "reorder_point": "data-derivation.md#reorder-point",
    "safety_stock": "data-derivation.md#reorder-point",
}


class StockItem(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    description: str | None
    category: str | None
    quantity_on_hand: int
    reorder_point: int | None
    safety_stock: int | None
    as_of_date: date
    is_low_stock: bool


STOCK_ITEM_PROVENANCE = {
    "quantity_on_hand": "derived",
    "reorder_point": "derived",
    "safety_stock": "derived",
}


class DeadStockItem(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    description: str | None
    quantity_on_hand: int
    last_movement_date: datetime | None
    days_since_movement: int | None


DEAD_STOCK_ITEM_PROVENANCE = {
    "quantity_on_hand": "derived",
    "days_since_movement": "derived",
}
DEAD_STOCK_ITEM_DERIVATION_REF = {
    "quantity_on_hand": "data-derivation.md#stock-ledger",
}


class SlowMoverItem(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    description: str | None
    quantity_on_hand: int
    units_sold: int
    avg_daily_demand: float


SLOW_MOVER_ITEM_PROVENANCE = {
    "quantity_on_hand": "derived",
    "units_sold": "derived",
    "avg_daily_demand": "derived",
}
SLOW_MOVER_ITEM_DERIVATION_REF = {
    "quantity_on_hand": "data-derivation.md#stock-ledger",
}


class ValuationRow(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    category: str | None
    quantity_on_hand: int
    inventory_value: float


VALUATION_ROW_PROVENANCE = {
    "quantity_on_hand": "derived",
    "inventory_value": "derived",
}
VALUATION_ROW_DERIVATION_REF = {
    "quantity_on_hand": "data-derivation.md#stock-ledger",
    "inventory_value": "data-derivation.md#cost-price",
}


class InventoryValuation(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    by_category: list[ValuationRow]
    total_quantity_on_hand: int
    total_inventory_value: float


INVENTORY_VALUATION_PROVENANCE = {
    "total_quantity_on_hand": "derived",
    "total_inventory_value": "derived",
}
