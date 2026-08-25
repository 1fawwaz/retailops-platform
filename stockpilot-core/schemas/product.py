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
                    "brand_id": 1,
                    "unit_cost": 2.15,
                    "sale_price": 4.99,
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
    brand_id: int | None = None
    unit_cost: float | None = None
    sale_price: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None
    image_url: str | None = None


class ProductUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"unit_cost": 2.25, "reorder_point": 130}]}
    )

    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    brand_id: int | None = None
    unit_cost: float | None = None
    sale_price: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None
    image_url: str | None = None


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
                    "brand_id": 1,
                    "unit_cost": 2.15,
                    "sale_price": 4.99,
                    "reorder_point": 120,
                    "safety_stock": 40,
                    "created_at": "2026-01-01T00:00:00Z",
                    "_provenance": {
                        "sku": "observed",
                        "description": "observed",
                        "unit_cost": "derived",
                        "sale_price": "derived",
                        "reorder_point": "derived",
                        "safety_stock": "derived",
                    },
                    "_derivation_ref": {
                        "unit_cost": "data-derivation.md#cost-price",
                        "sale_price": "BUILD.md Module 2 (avg sales_transactions.unit_price)",
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
    brand_id: int | None
    unit_cost: float | None
    sale_price: float | None
    reorder_point: int | None
    safety_stock: int | None
    image_url: str | None = None
    created_at: datetime
    id: str | None = None
    name: str | None = None

    category: str | None = None
    warehouse: str | None = None
    quantity: int | None = None
    inventory_value: float | None = None
    supplier: str | None = None


PRODUCT_PROVENANCE = {
    "sku": "observed",
    "description": "observed",
    "unit_cost": "derived",
    "sale_price": "derived",
    "reorder_point": "derived",
    "safety_stock": "derived",
    "quantity": "observed",
    "inventory_value": "derived",
}
PRODUCT_DERIVATION_REF = {
    "unit_cost": "data-derivation.md#cost-price",
    "sale_price": "BUILD.md Module 2 (avg sales_transactions.unit_price)",
    "reorder_point": "data-derivation.md#reorder-point",
    "safety_stock": "data-derivation.md#reorder-point",
    "inventory_value": "data-derivation.md#inventory-value",
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
                    "brand_id": 1,
                    "unit_cost": 2.15,
                    "sale_price": 4.99,
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
                        "sale_price": "derived",
                        "reorder_point": "derived",
                        "safety_stock": "derived",
                        "quantity_on_hand": "derived",
                    },
                    "_derivation_ref": {
                        "unit_cost": "data-derivation.md#cost-price",
                        "sale_price": "BUILD.md Module 2 (avg sales_transactions.unit_price)",
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


class ProductHistoryEntry(BaseModel):
    """One product_history row: a single field-level change. old_value
    and new_value are stringified since the changed field's type varies
    (int, float, str) -- an audit trail, not business data, so no
    provenance labelling.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "field_name": "unit_cost",
                    "old_value": "2.15",
                    "new_value": "2.25",
                    "changed_by_user_id": 4,
                    "changed_at": "2026-02-01T09:00:00Z",
                }
            ]
        },
    )

    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by_user_id: int | None
    changed_at: datetime
