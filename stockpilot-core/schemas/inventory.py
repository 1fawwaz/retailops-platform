from datetime import date, datetime

from pydantic import ConfigDict

from schemas.provenance import ProvenanceMixin

STOCK_DERIVATION_REF = {
    "quantity_on_hand": "data-derivation.md#stock-ledger",
    "reorder_point": "data-derivation.md#reorder-point",
    "safety_stock": "data-derivation.md#reorder-point",
}


class StockItem(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
                    "category": "Decorations",
                    "quantity_on_hand": 96,
                    "reorder_point": 120,
                    "safety_stock": 40,
                    "as_of_date": "2026-01-15",
                    "is_low_stock": True,
                    "_provenance": {
                        "quantity_on_hand": "derived",
                        "reorder_point": "derived",
                        "safety_stock": "derived",
                    },
                    "_derivation_ref": {
                        "quantity_on_hand": "data-derivation.md#stock-ledger",
                        "reorder_point": "data-derivation.md#reorder-point",
                        "safety_stock": "data-derivation.md#reorder-point",
                    },
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "22841",
                    "description": "ROUND CAKE TIN VINTAGE GREEN",
                    "quantity_on_hand": 18,
                    "last_movement_date": "2025-04-02T00:00:00Z",
                    "days_since_movement": 288,
                    "_provenance": {
                        "quantity_on_hand": "derived",
                        "days_since_movement": "derived",
                    },
                    "_derivation_ref": {"quantity_on_hand": "data-derivation.md#stock-ledger"},
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "21730",
                    "description": "GLASS STAR FROSTED T-LIGHT HOLDER",
                    "quantity_on_hand": 340,
                    "units_sold": 4,
                    "avg_daily_demand": 0.044,
                    "_provenance": {
                        "quantity_on_hand": "derived",
                        "units_sold": "derived",
                        "avg_daily_demand": "derived",
                    },
                    "_derivation_ref": {"quantity_on_hand": "data-derivation.md#stock-ledger"},
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "category": "Decorations",
                    "quantity_on_hand": 12480,
                    "inventory_value": 26832.50,
                    "_provenance": {"quantity_on_hand": "derived", "inventory_value": "derived"},
                    "_derivation_ref": {
                        "quantity_on_hand": "data-derivation.md#stock-ledger",
                        "inventory_value": "data-derivation.md#cost-price",
                    },
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "by_category": [
                        {
                            "category": "Decorations",
                            "quantity_on_hand": 12480,
                            "inventory_value": 26832.50,
                            "_provenance": {
                                "quantity_on_hand": "derived",
                                "inventory_value": "derived",
                            },
                            "_derivation_ref": {
                                "quantity_on_hand": "data-derivation.md#stock-ledger",
                                "inventory_value": "data-derivation.md#cost-price",
                            },
                        }
                    ],
                    "total_quantity_on_hand": 128400,
                    "total_inventory_value": 297512.10,
                    "_provenance": {
                        "total_quantity_on_hand": "derived",
                        "total_inventory_value": "derived",
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

    by_category: list[ValuationRow]
    total_quantity_on_hand: int
    total_inventory_value: float


INVENTORY_VALUATION_PROVENANCE = {
    "total_quantity_on_hand": "derived",
    "total_inventory_value": "derived",
}
