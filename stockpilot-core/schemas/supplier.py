from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.provenance import ProvenanceMixin


class SupplierCreate(BaseModel):
    name: str
    lead_time_days: int
    reliability_score: float


class SupplierUpdate(BaseModel):
    name: str | None = None
    lead_time_days: int | None = None
    reliability_score: float | None = None


class SupplierRead(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

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
    skus: list[str]
