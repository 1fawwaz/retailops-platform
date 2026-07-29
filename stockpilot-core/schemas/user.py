from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "analyst@retailops.local", "password": "hunter2-example"}]
        }
    )

    email: EmailStr
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "email": "demo@retailops.local",
                    "is_active": True,
                    "is_read_only": True,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )

    id: int
    email: EmailStr
    is_active: bool
    is_read_only: bool
    created_at: datetime


class Token(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str
    token_type: str = "bearer"
