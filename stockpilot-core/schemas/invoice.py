from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvoiceRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "sales_order_id": 1,
                    "total_amount": 24.95,
                    "status": "unpaid",
                    "issued_at": "2026-02-01T09:00:00Z",
                }
            ]
        },
    )

    id: int
    sales_order_id: int
    total_amount: float
    status: str
    issued_at: datetime
