"""Stage 3 Task 3.3: the Planner's sufficiency judgement -- per the spec,
a first-class, persisted structured artifact, not an internal branching
condition buried in prose. `agents/base.py`'s planner prompt already
describes this as the Planner's third responsibility ("Judge
sufficiency"); this schema is what turns that into a structured
`generate_structured()` call instead of free text.

`agents_to_retry` isn't named in the spec's own example JSON (which
shows only `sufficient`/`missing`/`next_action`/`iteration`) -- it
exists so the graph can deterministically route a second, TARGETED
retrieval round to just the agent(s) that actually need to re-run,
rather than parsing which agent a natural-language `next_action`
string refers to. `iteration` is deliberately NOT part of this
LLM-facing schema: which retrieval round is being judged is
deterministic bookkeeping the graph already knows from its own state,
not something to ask the model to track and possibly drift on: the
graph attaches it after the fact, the same way business numbers are
never left to the LLM to compute.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalAgentName = Literal["inventory", "forecast", "analytics"]


class ReplanJudgement(BaseModel):
    sufficient: bool = Field(
        description="Whether the evidence gathered so far is enough to answer the "
        "original question."
    )
    missing: list[str] = Field(
        default_factory=list,
        description="Specific pieces of evidence still needed, e.g. 'supplier lead "
        "time for 3 SKUs'. Empty if sufficient.",
    )
    next_action: str = Field(
        description="One sentence: either that the answer is ready for the Report "
        "Agent, or exactly what the next retrieval round should ask for and from "
        "which agent(s)."
    )
    agents_to_retry: list[RetrievalAgentName] = Field(
        default_factory=list,
        description="Which retrieval agents to re-invoke for a targeted second round. "
        "Empty if sufficient.",
    )
