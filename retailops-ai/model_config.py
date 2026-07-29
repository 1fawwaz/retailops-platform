"""Loads config/models.yaml: role -> Gemini model ID and per-execution
budgets (CLAUDE.md section 7). No model name may appear anywhere else in
the codebase -- code asks for a role ("planner", "retriever", "decision"),
never a literal model string.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

SERVICE_ROOT = Path(__file__).resolve().parent
MODELS_CONFIG_PATH = SERVICE_ROOT / "config" / "models.yaml"


class ModelRoles(BaseModel):
    planner: str
    retriever: str
    decision: str


class ModelBudgets(BaseModel):
    max_tool_iterations: int
    max_tokens_per_execution: int


class ModelConfig(BaseModel):
    roles: ModelRoles
    budgets: ModelBudgets


@lru_cache
def get_model_config() -> ModelConfig:
    with MODELS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ModelConfig.model_validate(data)
