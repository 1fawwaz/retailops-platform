from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.email import LocalEmail


class UserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "analyst@retailops.local", "password": "hunter2-example"}]
        }
    )

    email: LocalEmail
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
    email: LocalEmail
    is_active: bool
    is_read_only: bool
    avatar_url: str | None = None
    created_at: datetime


class UserWithRolesRead(BaseModel):
    """docs/BUILD.md Backend Module 10's GET /users -- a user's profile
    plus their assigned role names, for role management.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "email": "demo@retailops.local",
                    "is_active": True,
                    "is_read_only": False,
                    "created_at": "2026-01-01T00:00:00Z",
                    "roles": ["inventory_manager"],
                }
            ]
        },
    )

    id: int
    email: LocalEmail
    is_active: bool
    is_read_only: bool
    avatar_url: str | None = None
    created_at: datetime
    roles: list[str]


class Token(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "8iQ2z...opaque-token...x9F",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"refresh_token": "8iQ2z...opaque-token...x9F"}]}
    )

    refresh_token: str | None = None


class AccessTokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "8iQ2z...opaque-token...x9F",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str
    # Present from SEC-02 onward: /refresh rotates the refresh token, so
    # the client must persist the returned one, not keep the old one.
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"refresh_token": "8iQ2z...opaque-token...x9F"}]}
    )

    refresh_token: str | None = None


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "analyst@retailops.local"}]}
    )

    email: LocalEmail


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "token": "8iQ2z...opaque-token...x9F",
                    "new_password": "a-new-strong-password",
                }
            ]
        }
    )

    token: str
    new_password: str = Field(min_length=8)
