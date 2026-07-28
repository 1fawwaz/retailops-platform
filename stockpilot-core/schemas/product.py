from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.provenance import ProvenanceMixin


class ProductCreate(BaseModel):
    sku: str
    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    unit_cost: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None


class ProductUpdate(BaseModel):
    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    unit_cost: float | None = None
    reorder_point: int | None = None
    safety_stock: int | None = None


class ProductRead(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

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
