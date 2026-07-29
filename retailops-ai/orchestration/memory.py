"""Stage 3 Task 3.4: conversation history and a bounded rolling window
of prior executions, both read fresh from Postgres on every call --
never held in-process (CLAUDE.md: "Postgres, never in-process") -- so a
follow-up question in the same conversation is correctly informed by
what was asked and found before, even across separate graph executions
(and, eventually, separate requests/processes once Task 3.6 adds the
HTTP layer).

"Rolling task memory" is a bounded window (the ROLLING_WINDOW_SIZE most
recent completed executions), not an LLM-generated summary: asking a
model to compress its own past answers would add a re-summarization
step with no provenance path back to the executions that produced the
original numbers, for no benefit this milestone (a follow-up question
resolving correctly) actually needs. It's also not unboundedly-growing
raw history -- each past execution's own already-grounded plan and
final answer is read back directly, capped to the last N turns, rather
than re-derived or compressed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from orchestration.models.execution import Execution
from orchestration.models.message import Message

ROLLING_WINDOW_SIZE = 5


def load_conversation_context(
    session_factory: Callable[[], Session], conversation_id: uuid.UUID | None
) -> str | None:
    """None for a standalone run (conversation_id is None) or a brand-new
    conversation with no completed turns yet. Otherwise a text block
    combining the raw message transcript (conversation history) with the
    most recent completed executions' own plan/final_answer (rolling
    task memory) -- meant to be prepended to the Planner's own prompt
    only, per spec ("...passed to the Planner"), not to every agent.

    Callers must load this BEFORE writing the current turn's own Message/
    Execution rows -- calling it any later would let the current turn
    see itself as if it were prior history.
    """
    if conversation_id is None:
        return None

    session = session_factory()
    try:
        messages = (
            session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            .scalars()
            .all()
        )
        recent_executions = (
            session.execute(
                select(Execution)
                .where(
                    Execution.conversation_id == conversation_id,
                    Execution.status == "completed",
                )
                .order_by(Execution.completed_at.desc())
                .limit(ROLLING_WINDOW_SIZE)
            )
            .scalars()
            .all()
        )
    finally:
        session.close()

    if not messages and not recent_executions:
        return None

    sections: list[str] = []
    if messages:
        transcript = "\n".join(f"{message.role}: {message.content}" for message in messages)
        sections.append(f"Conversation history so far:\n{transcript}")

    for execution in reversed(recent_executions):
        plan_text = execution.plan.get("text") if execution.plan else None
        sections.append(
            f"Earlier turn -- question: {execution.query}\n"
            f"Earlier turn -- plan: {plan_text}\n"
            f"Earlier turn -- answer: {execution.final_answer}"
        )

    return "\n\n".join(sections)
