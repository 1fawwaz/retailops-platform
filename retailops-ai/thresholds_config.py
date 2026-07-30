"""Loads config/thresholds.yaml: the Decision Engine's rules-based
thresholds (Stage 4 Task 4.3). Same shape as model_config.py's own
loader for config/models.yaml -- a Pydantic model + an lru_cache'd
loader function, so every threshold used in services/*.py traces back
to this one file, never a literal in code (CLAUDE.md section 8).
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

SERVICE_ROOT = Path(__file__).resolve().parent
THRESHOLDS_CONFIG_PATH = SERVICE_ROOT / "config" / "thresholds.yaml"


class PriorityThresholds(BaseModel):
    critical_revenue_at_risk: float
    critical_days_to_stockout: float
    high_revenue_at_risk: float
    high_days_to_stockout: float
    medium_revenue_at_risk: float
    medium_days_to_stockout: float


class ConfidenceThresholds(BaseModel):
    target_history_days: int


class PricingThresholds(BaseModel):
    lookup_limit: int


class ThresholdsConfig(BaseModel):
    priority: PriorityThresholds
    confidence: ConfidenceThresholds
    pricing: PricingThresholds


@lru_cache
def get_thresholds_config() -> ThresholdsConfig:
    with THRESHOLDS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ThresholdsConfig.model_validate(data)
