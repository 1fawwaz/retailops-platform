from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "user_id": 4,
                    "permission": "purchase_order:update",
                    "method": "POST",
                    "path": "/purchase-orders/1/approve",
                    "created_at": "2026-02-01T09:00:00Z",
                }
            ]
        },
    )

    id: int
    user_id: int
    permission: str
    method: str
    path: str
    created_at: datetime
