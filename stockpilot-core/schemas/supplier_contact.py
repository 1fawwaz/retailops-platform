from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SupplierContactCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Priya Shah",
                    "email": "priya@acmewholesale.example",
                    "phone": "+44 20 7946 0958",
                    "role": "Account Manager",
                }
            ]
        }
    )

    name: str
    email: str | None = None
    phone: str | None = None
    role: str | None = None


class SupplierContactUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"phone": "+44 20 7946 0000"}]})

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None


class SupplierContactRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "supplier_id": 7,
                    "name": "Priya Shah",
                    "email": "priya@acmewholesale.example",
                    "phone": "+44 20 7946 0958",
                    "role": "Account Manager",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )

    id: int
    supplier_id: int
    name: str
    email: str | None
    phone: str | None
    role: str | None
    created_at: datetime
