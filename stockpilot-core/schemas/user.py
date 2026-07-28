from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: EmailStr
    is_active: bool
    is_read_only: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
