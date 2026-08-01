from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SalesOrderLineCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"sku": "85048", "quantity": 5, "unit_price": 4.99}]}
    )

    sku: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)


class SalesOrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_id": 1,
                    "warehouse_id": 1,
                    "lines": [{"sku": "85048", "quantity": 5, "unit_price": 4.99}],
                }
            ]
        }
    )

    customer_id: int
    warehouse_id: int
    lines: list[SalesOrderLineCreate] = Field(min_length=1)


class SalesOrderUpdate(BaseModel):
    """Only valid while the order is still Draft."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"lines": [{"sku": "85048", "quantity": 8, "unit_price": 4.99}]}]
        }
    )

    customer_id: int | None = None
    warehouse_id: int | None = None
    lines: list[SalesOrderLineCreate] | None = None


class SalesOrderLineRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{"id": 1, "sku": "85048", "quantity": 5, "unit_price": 4.99}]
        },
    )

    id: int
    sku: str
    quantity: int
    unit_price: float


class SalesOrderRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "customer_id": 1,
                    "warehouse_id": 1,
                    "status": "draft",
                    "created_by_user_id": 4,
                    "created_at": "2026-02-01T09:00:00Z",
                    "updated_at": "2026-02-01T09:00:00Z",
                    "lines": [{"id": 1, "sku": "85048", "quantity": 5, "unit_price": 4.99}],
                }
            ]
        },
    )

    id: int
    customer_id: int
    warehouse_id: int
    status: str
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    lines: list[SalesOrderLineRead]
