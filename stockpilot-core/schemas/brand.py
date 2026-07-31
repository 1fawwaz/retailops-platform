from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BrandCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Acme Housewares"}]})

    name: str


class BrandRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{"id": 1, "name": "Acme Housewares", "created_at": "2026-01-01T00:00:00Z"}]
        },
    )

    id: int
    name: str
    created_at: datetime
