from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoleCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"name": "warehouse_clerk", "permissions": ["inventory:read"]}]
        }
    )

    name: str
    permissions: list[str]


class RoleUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"permissions": ["inventory:read", "inventory:update"]}]}
    )

    permissions: list[str]


class RoleRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "inventory_manager",
                    "permissions": ["inventory:read", "inventory:update"],
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )

    id: int
    name: str
    permissions: list[str]
    created_at: datetime
