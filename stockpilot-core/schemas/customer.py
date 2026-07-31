from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CustomerCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "phone": "+44 20 7946 0958",
                    "country": "United Kingdom",
                }
            ]
        }
    )

    name: str
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"phone": "+44 20 7946 0000"}]})

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "phone": "+44 20 7946 0958",
                    "country": "United Kingdom",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )

    id: int
    name: str
    email: str | None
    phone: str | None
    country: str | None
    created_at: datetime
