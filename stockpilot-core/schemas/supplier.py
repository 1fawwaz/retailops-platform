from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.provenance import ProvenanceMixin


class SupplierCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Acme Wholesale Co", "lead_time_days": 7, "reliability_score": 0.92}
            ]
        }
    )

    name: str
    lead_time_days: int
    reliability_score: float


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"lead_time_days": 10}]})

    name: str | None = None
    lead_time_days: int | None = None
    reliability_score: float | None = None


class SupplierRead(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 7,
                    "name": "Acme Wholesale Co",
                    "lead_time_days": 7,
                    "reliability_score": 0.92,
                    "created_at": "2026-01-01T00:00:00Z",
                    "_provenance": {
                        "name": "observed",
                        "lead_time_days": "derived",
                        "reliability_score": "derived",
                    },
                    "_derivation_ref": {
                        "lead_time_days": "data-derivation.md#supplier-assignment",
                        "reliability_score": "data-derivation.md#supplier-assignment",
                    },
                }
            ]
        },
    )

    id: int
    name: str
    lead_time_days: int
    reliability_score: float
    created_at: datetime


SUPPLIER_PROVENANCE = {
    "name": "observed",
    "lead_time_days": "derived",
    "reliability_score": "derived",
}
SUPPLIER_DERIVATION_REF = {
    "lead_time_days": "data-derivation.md#supplier-assignment",
    "reliability_score": "data-derivation.md#supplier-assignment",
}


class SupplierDetail(SupplierRead):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 7,
                    "name": "Acme Wholesale Co",
                    "lead_time_days": 7,
                    "reliability_score": 0.92,
                    "created_at": "2026-01-01T00:00:00Z",
                    "skus": ["85048", "85049"],
                    "_provenance": {
                        "name": "observed",
                        "lead_time_days": "derived",
                        "reliability_score": "derived",
                    },
                    "_derivation_ref": {
                        "lead_time_days": "data-derivation.md#supplier-assignment",
                        "reliability_score": "data-derivation.md#supplier-assignment",
                    },
                }
            ]
        },
    )

    skus: list[str]
