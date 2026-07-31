from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Decorations"}]})

    name: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{"id": 3, "name": "Decorations", "created_at": "2026-01-01T00:00:00Z"}]
        },
    )

    id: int
    name: str
    created_at: datetime
