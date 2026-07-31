from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PurchaseOrderLineCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"sku": "85048", "quantity_ordered": 200}]}
    )

    sku: str
    quantity_ordered: int = Field(gt=0)
    unit_cost: float | None = None


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "supplier_id": 7,
                    "warehouse_id": 1,
                    "lines": [{"sku": "85048", "quantity_ordered": 200, "unit_cost": 2.15}],
                }
            ]
        }
    )

    supplier_id: int
    warehouse_id: int
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderUpdate(BaseModel):
    """Only valid while the PO is still Draft (docs/PRODUCT-SPEC.md §12).
    Lines, if provided, wholesale-replace the PO's existing lines.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lines": [{"sku": "85048", "quantity_ordered": 250}]}]}
    )

    supplier_id: int | None = None
    warehouse_id: int | None = None
    lines: list[PurchaseOrderLineCreate] | None = None


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "sku": "85048",
                    "quantity_ordered": 200,
                    "quantity_received": 0,
                    "unit_cost": 2.15,
                }
            ]
        },
    )

    id: int
    sku: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: float | None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "supplier_id": 7,
                    "warehouse_id": 1,
                    "status": "draft",
                    "created_by_user_id": 4,
                    "created_at": "2026-02-01T09:00:00Z",
                    "updated_at": "2026-02-01T09:00:00Z",
                    "lines": [
                        {
                            "id": 1,
                            "sku": "85048",
                            "quantity_ordered": 200,
                            "quantity_received": 0,
                            "unit_cost": 2.15,
                        }
                    ],
                }
            ]
        },
    )

    id: int
    supplier_id: int
    warehouse_id: int
    status: str
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineRead]


class ReceiveLineRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"line_id": 1, "quantity": 200, "over_receipt_confirmed": False}]
        }
    )

    line_id: int
    quantity: int = Field(gt=0)
    over_receipt_confirmed: bool = False


class ReceiveRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"lines": [{"line_id": 1, "quantity": 200, "over_receipt_confirmed": False}]}
            ]
        }
    )

    lines: list[ReceiveLineRequest] = Field(min_length=1)
