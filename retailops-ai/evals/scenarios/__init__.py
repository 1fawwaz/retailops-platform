"""Stage 5 scenario registry -- the ten scenarios evals/runner.py runs.

Each module under this package owns exactly one scenario (seeded
StockPilot responses via a MockTransport handler, scripted LLM
behavior, and a `run()` callable producing a normalized
ScenarioOutcome). This file just collects the ten `SCENARIO` objects
into one importable list, in spec order.
"""

from __future__ import annotations

from evals.scenarios.base import Scenario
from evals.scenarios.s01_normal_operations import SCENARIO as S01_NORMAL_OPERATIONS
from evals.scenarios.s02_seasonal_demand_spike import SCENARIO as S02_SEASONAL_DEMAND_SPIKE
from evals.scenarios.s03_new_sku_no_history import SCENARIO as S03_NEW_SKU_NO_HISTORY
from evals.scenarios.s04_supplier_delay import SCENARIO as S04_SUPPLIER_DELAY
from evals.scenarios.s05_empty_inventory import SCENARIO as S05_EMPTY_INVENTORY
from evals.scenarios.s06_missing_forecast import SCENARIO as S06_MISSING_FORECAST
from evals.scenarios.s07_api_unavailable import SCENARIO as S07_API_UNAVAILABLE
from evals.scenarios.s08_prompt_injection import SCENARIO as S08_PROMPT_INJECTION
from evals.scenarios.s09_ambiguous_question import SCENARIO as S09_AMBIGUOUS_QUESTION
from evals.scenarios.s10_unanswerable_question import SCENARIO as S10_UNANSWERABLE_QUESTION

ALL_SCENARIOS: list[Scenario] = [
    S01_NORMAL_OPERATIONS,
    S02_SEASONAL_DEMAND_SPIKE,
    S03_NEW_SKU_NO_HISTORY,
    S04_SUPPLIER_DELAY,
    S05_EMPTY_INVENTORY,
    S06_MISSING_FORECAST,
    S07_API_UNAVAILABLE,
    S08_PROMPT_INJECTION,
    S09_AMBIGUOUS_QUESTION,
    S10_UNANSWERABLE_QUESTION,
]
