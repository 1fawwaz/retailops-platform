"""Email validation that permits the project's canonical local domain.

The project's demo and example addresses use the RFC 6761 reserved
".local" TLD (demo@retailops.local, analyst@retailops.local) end to end:
.env files, contract examples, docs, and the frontend's zod .email() all
accept them. pydantic's EmailStr sits on top of email-validator, which
rejects every reserved/special-use domain unconditionally (the special-use
check in email_validator.syntax runs regardless of globally_deliverable),
so EmailStr rejects the project's own canonical addresses on
serialization -- observed live: GET /me returns 500 for
demo@retailops.local while login, which never round-trips the address
through EmailStr, succeeds.

This type validates with email-validator first and falls back to
structural checks only when the address's domain is a reserved/special-use
name (in which case deliverability is meaningless by definition). It keeps
the same JSON schema ("string" + "format": "email") as EmailStr so the
frozen OpenAPI contract does not change.
"""

from typing import Annotated

from email_validator import SPECIAL_USE_DOMAIN_NAMES, EmailNotValidError, validate_email
from pydantic import AfterValidator, StringConstraints, WithJsonSchema


def _domain_is_reserved(domain: str) -> bool:
    domain = domain.lower().rstrip(".")
    return any(domain == name or domain.endswith("." + name) for name in SPECIAL_USE_DOMAIN_NAMES)


def _validate_email(value: str) -> str:
    value = value.strip()
    domain = value.rpartition("@")[2]
    if _domain_is_reserved(domain):
        local_part = value.rpartition("@")[0]
        if not local_part or any(ch.isspace() for ch in value):
            raise ValueError("invalid email address: malformed local part or whitespace")
        if not domain or any(not label for label in domain.split(".")):
            raise ValueError("invalid email address: malformed domain part")
        return value
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(f"invalid email address: {exc}") from exc
    return value


LocalEmail = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    AfterValidator(_validate_email),
    WithJsonSchema({"type": "string", "format": "email"}),
]
