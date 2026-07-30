"""Stage 4 Task 4.3: rules-based priority tiering. Per spec: "priority =
rules-based tiering on revenue_at_risk and days_to_stockout, thresholds
in config." Either dimension alone can escalate the tier -- checked
critical -> high -> medium -> low, first match wins -- since a SKU
about to stock out imminently is urgent even with modest revenue_at_risk
(e.g. a cheap, fast-moving SKU), and a SKU with large revenue_at_risk is
urgent even with a few days of runway left. Thresholds live in
config/thresholds.yaml, never a literal here (CLAUDE.md section 8).

`revenue_at_risk` may be None (docs/stockpilot-gaps.md#2 -- no unit
price found for this SKU in either top/bottom-products ranking): the
days_to_stockout dimension alone still drives tiering in that case,
never a fabricated revenue figure.
"""

from __future__ import annotations

from typing import Literal

from thresholds_config import get_thresholds_config

Priority = Literal["critical", "high", "medium", "low"]


def compute_priority(*, revenue_at_risk: float | None, days_to_stockout: float) -> Priority:
    thresholds = get_thresholds_config().priority

    def _at_or_above(revenue_threshold: float) -> bool:
        return revenue_at_risk is not None and revenue_at_risk >= revenue_threshold

    if _at_or_above(thresholds.critical_revenue_at_risk) or (
        days_to_stockout <= thresholds.critical_days_to_stockout
    ):
        return "critical"
    if _at_or_above(thresholds.high_revenue_at_risk) or (
        days_to_stockout <= thresholds.high_days_to_stockout
    ):
        return "high"
    if _at_or_above(thresholds.medium_revenue_at_risk) or (
        days_to_stockout <= thresholds.medium_days_to_stockout
    ):
        return "medium"
    return "low"
