from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "type": "low_stock",
                    "message": "'85048' has crossed its reorder point (95 <= 120)",
                    "resource_type": "product",
                    "resource_id": "85048",
                    "is_read": False,
                    "created_at": "2026-02-01T09:00:00Z",
                }
            ]
        },
    )

    id: int
    type: str
    message: str
    resource_type: str | None
    resource_id: str | None
    is_read: bool
    created_at: datetime


class NotificationMarkRead(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"is_read": True}]})

    is_read: bool = True
