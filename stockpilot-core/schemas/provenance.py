"""The provenance contract every response schema must satisfy.

Every numeric business field in a response carries a provenance label
(observed / derived / predicted / inferred) in `_provenance`, and an
optional pointer into docs/data-derivation.md in `_derivation_ref`.
Surrogate/foreign keys and timestamps are structural, not business
claims, so they are exempt.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXEMPT_FIELD_NAMES = {"id", "created_at", "updated_at"}
EXEMPT_FIELD_SUFFIXES = ("_id",)


def _is_exempt(field_name: str) -> bool:
    return field_name in EXEMPT_FIELD_NAMES or field_name.endswith(EXEMPT_FIELD_SUFFIXES)


class ProvenanceMixin(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provenance: dict[str, str] = Field(alias="_provenance")
    derivation_ref: dict[str, str] = Field(default_factory=dict, alias="_derivation_ref")

    @model_validator(mode="after")
    def _numeric_fields_have_provenance(self) -> Self:
        for field_name in type(self).model_fields:
            if field_name in ("provenance", "derivation_ref") or _is_exempt(field_name):
                continue
            value = getattr(self, field_name)
            if isinstance(value, int | float) and not isinstance(value, bool):
                if field_name not in self.provenance:
                    raise ValueError(f"Numeric field '{field_name}' has no provenance entry")
        return self
