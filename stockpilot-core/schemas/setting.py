from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"currency": "GBP"}]})

    currency: str | None = None
    timezone: str | None = None
    low_stock_notifications_enabled: bool | None = None


class SettingsRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "currency": "GBP",
                    "timezone": "Europe/London",
                    "low_stock_notifications_enabled": True,
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )

    currency: str
    timezone: str
    low_stock_notifications_enabled: bool
    updated_at: datetime
