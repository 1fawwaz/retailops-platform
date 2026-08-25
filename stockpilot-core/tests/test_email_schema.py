"""Unit tests for schemas.email.LocalEmail.

The project canonically uses the RFC 6761 reserved ".local" TLD
(demo@retailops.local) end to end, and pydantic's EmailStr rejects every
reserved domain unconditionally -- LocalEmail must accept the project's
own addresses while still rejecting malformed input, and must keep the
same JSON schema as EmailStr so the frozen OpenAPI contract is unchanged.
"""

import pytest
from pydantic import BaseModel, ValidationError

from schemas.email import LocalEmail


class EmailModel(BaseModel):
    email: LocalEmail


@pytest.mark.parametrize(
    "value",
    [
        "demo@retailops.local",
        "analyst@retailops.local",
        "someone@gmail.com",
        "user@example.co.uk",
    ],
)
def test_accepts_valid_addresses(value: str) -> None:
    assert EmailModel(email=value).email == value


@pytest.mark.parametrize(
    "value",
    [
        "not-an-email",
        "a@b",
        "demo@retailops.local with space",
        "@retailops.local",
        "demo@",
    ],
)
def test_rejects_malformed_addresses(value: str) -> None:
    with pytest.raises(ValidationError):
        EmailModel(email=value)


def test_json_schema_matches_emailstr_format() -> None:
    schema = EmailModel.model_json_schema()
    assert schema["properties"]["email"] == {
        "type": "string",
        "format": "email",
        "title": "Email",
    }
