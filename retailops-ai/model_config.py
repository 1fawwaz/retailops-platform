"""Loads config/models.yaml: role -> (provider, model), the fallback
(provider, model), and per-execution budgets (CLAUDE.md section 7). No
model name may appear anywhere else in the codebase -- code asks for a
role ("planner", "retriever", "decision"), never a literal model string.

Stage 6 Task 6.4: `RoleModelConfig`/`FallbackModelConfig` now carry a
`provider` field alongside `model`, since two providers exist. Every
concrete piece of code that resolves "which model does this role use"
(agents/base.py::Agent.model_id) or "which provider serves this model"
(llm/providers/registry.py) reads it from here -- never hardcoded.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

SERVICE_ROOT = Path(__file__).resolve().parent
MODELS_CONFIG_PATH = SERVICE_ROOT / "config" / "models.yaml"


class RoleModelConfig(BaseModel):
    provider: str
    model: str


class FallbackModelConfig(BaseModel):
    provider: str
    model: str


class ModelRoles(BaseModel):
    planner: RoleModelConfig
    retriever: RoleModelConfig
    decision: RoleModelConfig


class ModelBudgets(BaseModel):
    max_tool_iterations: int
    max_tokens_per_execution: int


class ModelConfig(BaseModel):
    roles: ModelRoles
    fallback: FallbackModelConfig
    budgets: ModelBudgets


@lru_cache
def get_model_config() -> ModelConfig:
    with MODELS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ModelConfig.model_validate(data)
