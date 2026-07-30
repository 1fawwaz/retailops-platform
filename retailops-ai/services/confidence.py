"""Stage 4 Task 4.3: the Decision Engine's confidence formula. The spec
gives the three inputs ("forecast CI width, data_quality flag, history
length") and explicitly delegates the exact formula to be authored and
unit tested here -- unlike revenue_at_risk/inventory_cost/priority,
which the spec gives a concrete formula for, confidence only names its
inputs, so this module's job is to define and document that formula,
not guess at one the spec withheld.

Design: three independent [0, 1] factors, multiplied together, so a
weakness in ANY dimension pulls confidence down (a narrow CI on a
model trained on ok-quality but wisp-thin history shouldn't read as
"confident" just because the interval happens to be tight):

  ci_width_factor    = 1 / (1 + ci_width / predicted_daily_demand)
                        narrower CI relative to the demand rate itself
                        -> closer to 1. 0.0 when there's no demand to
                        form a ratio against (a no_history forecast).
  data_quality_factor = 1.0 "ok" / 0.6 "thin_history" / 0.2 "no_history"
                        (0.0 for any other value, defensively)
  history_factor      = min(1, history_days / target_history_days)
                        (config/thresholds.yaml -- CLAUDE.md section 8:
                        no hardcoded threshold in this module itself)

confidence = ci_width_factor * data_quality_factor * history_factor,
rounded to 4 decimal places. Always in [0, 1]; provenance "derived" is
attached by the caller (agents/decision.py), not stored here.
"""

from __future__ import annotations

from thresholds_config import get_thresholds_config

_DATA_QUALITY_FACTORS = {
    "ok": 1.0,
    "thin_history": 0.6,
    "no_history": 0.2,
}


def compute_confidence(
    *,
    confidence_interval_lower: float,
    confidence_interval_upper: float,
    predicted_daily_demand: float,
    data_quality: str,
    history_days: int,
) -> float:
    ci_width = confidence_interval_upper - confidence_interval_lower
    if predicted_daily_demand > 0:
        ci_width_factor = 1.0 / (1.0 + (ci_width / predicted_daily_demand))
    else:
        # No demand rate to form a meaningful ratio against (a
        # no_history forecast, predicted_daily_demand == 0 by design) --
        # treated as the worst case, not skipped or defaulted to neutral.
        ci_width_factor = 0.0

    data_quality_factor = _DATA_QUALITY_FACTORS.get(data_quality, 0.0)

    target_history_days = get_thresholds_config().confidence.target_history_days
    history_factor = min(1.0, max(0.0, history_days) / target_history_days)

    return round(ci_width_factor * data_quality_factor * history_factor, 4)
