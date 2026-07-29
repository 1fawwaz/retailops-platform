from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.provenance import ProvenanceMixin


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
                    "category_id": 3,
                    "supplier_id": 7,
                    "unit_cost": 2.15,
                    "reorder_point": 120,
                    "safety_stock": 40,
                }
            ]
        }
    )

    sku: str
    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    unit_cost: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None


class ProductUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"unit_cost": 2.25, "reorder_point": 130}]}
    )

    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    unit_cost: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None


class ProductRead(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
                    "category_id": 3,
                    "supplier_id": 7,
                    "unit_cost": 2.15,
                    "reorder_point": 120,
                    "safety_stock": 40,
                    "created_at": "2026-01-01T00:00:00Z",
                    "_provenance": {
                        "sku": "observed",
                        "description": "observed",
                        "unit_cost": "derived",
                        "reorder_point": "derived",
                        "safety_stock": "derived",
                    },
                    "_derivation_ref": {
                        "unit_cost": "data-derivation.md#cost-price",
                        "reorder_point": "data-derivation.md#reorder-point",
                        "safety_stock": "data-derivation.md#reorder-point",
                    },
                }
            ]
        },
    )

    sku: str
    description: str | None
    category_id: int | None
    supplier_id: int | None
    unit_cost: float | None
    reorder_point: int | None
    safety_stock: int | None
    created_at: datetime


PRODUCT_PROVENANCE = {
    "sku": "observed",
    "description": "observed",
    "unit_cost": "derived",
    "reorder_point": "derived",
    "safety_stock": "derived",
}
PRODUCT_DERIVATION_REF = {
    "unit_cost": "data-derivation.md#cost-price",
    "reorder_point": "data-derivation.md#reorder-point",
    "safety_stock": "data-derivation.md#reorder-point",
}


class MovementHistoryEntry(BaseModel):
    """One stock_movements row. Carries its own provenance label rather
    than the ProvenanceMixin dict, since sale-driven rows are observed
    while opening-balance / injected-PO rows are derived -- a single
    static label per field couldn't express that per-row split.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "movement_date": "2026-01-14T00:00:00Z",
                    "quantity_delta": -12,
                    "movement_type": "sale",
                    "provenance": "observed",
                }
            ]
        },
    )

    movement_date: datetime
    quantity_delta: int
    movement_type: str
    provenance: str


class ProductDetail(ProductRead):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
                    "category_id": 3,
                    "supplier_id": 7,
                    "unit_cost": 2.15,
                    "reorder_point": 120,
                    "safety_stock": 40,
                    "created_at": "2026-01-01T00:00:00Z",
                    "quantity_on_hand": 96,
                    "movement_history": [
                        {
                            "movement_date": "2026-01-14T00:00:00Z",
                            "quantity_delta": -12,
                            "movement_type": "sale",
                            "provenance": "observed",
                        }
                    ],
                    "_provenance": {
                        "sku": "observed",
                        "description": "observed",
                        "unit_cost": "derived",
                        "reorder_point": "derived",
                        "safety_stock": "derived",
                        "quantity_on_hand": "derived",
                    },
                    "_derivation_ref": {
                        "unit_cost": "data-derivation.md#cost-price",
                        "reorder_point": "data-derivation.md#reorder-point",
                        "safety_stock": "data-derivation.md#reorder-point",
                        "quantity_on_hand": "data-derivation.md#stock-ledger",
                    },
                }
            ]
        },
    )

    quantity_on_hand: int | None
    movement_history: list[MovementHistoryEntry]


PRODUCT_DETAIL_PROVENANCE = {
    **PRODUCT_PROVENANCE,
    "quantity_on_hand": "derived",
}
PRODUCT_DETAIL_DERIVATION_REF = {
    **PRODUCT_DERIVATION_REF,
    "quantity_on_hand": "data-derivation.md#stock-ledger",
}
