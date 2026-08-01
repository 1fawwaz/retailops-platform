from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"amount": 24.95, "method": "bank_transfer"}]}
    )

    amount: float = Field(gt=0)
    method: str | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "invoice_id": 1,
                    "amount": 24.95,
                    "method": "bank_transfer",
                    "paid_at": "2026-02-02T09:00:00Z",
                }
            ]
        },
    )

    id: int
    invoice_id: int
    amount: float
    method: str | None
    paid_at: datetime
