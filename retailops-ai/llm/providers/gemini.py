"""The ONLY module allowed to import the Gemini SDK (CLAUDE.md section 7,
ARCHITECTURE RULES: "No provider SDK outside llm/providers/"). The rest
of the codebase is meant to see one interface -- generate(),
generate_structured(), stream() -- but nothing calls an LLM yet (the six
agents don't exist until Stage 3), so building that full interface now
would be code with no caller, exactly what CLAUDE.md's coding rules warn
against. This currently exposes only what Task 2.5 (model configuration)
needs: listing what Gemini actually has available, to verify
config/models.yaml's model IDs before they're ever used.
"""

from __future__ import annotations

from google import genai

from settings import get_settings


def list_model_ids() -> list[str]:
    """Every model name Gemini's API currently reports as available to
    this API key, with the "models/" prefix stripped so callers can
    compare directly against config/models.yaml's bare IDs.
    """
    client = genai.Client(api_key=get_settings().gemini_api_key)
    return [model.name.removeprefix("models/") for model in client.models.list() if model.name]
