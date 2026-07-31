from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WarehouseCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "North Depot"}]})

    name: str


class WarehouseRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{"id": 1, "name": "Main Warehouse", "created_at": "2026-01-01T00:00:00Z"}]
        },
    )

    id: int
    name: str
    created_at: datetime
