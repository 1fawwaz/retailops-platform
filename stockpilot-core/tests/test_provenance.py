import pytest
from pydantic import ValidationError

from schemas.provenance import ProvenanceMixin


class _Metric(ProvenanceMixin):
    revenue: float
    sku: str


def test_numeric_field_with_provenance_is_accepted() -> None:
    metric = _Metric(revenue=42.0, sku="ABC", provenance={"revenue": "observed"})

    assert metric.revenue == 42.0
    assert metric.provenance == {"revenue": "observed"}


def test_numeric_field_missing_provenance_is_rejected() -> None:
    with pytest.raises(ValidationError, match="revenue"):
        _Metric(revenue=42.0, sku="ABC", provenance={})


def test_non_numeric_field_does_not_require_provenance() -> None:
    metric = _Metric(revenue=1.0, sku="ABC", provenance={"revenue": "observed"})

    assert "sku" not in metric.provenance
