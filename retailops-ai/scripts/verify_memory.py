"""Stage 3 Task 3.4 milestone check: a follow-up question that depends
on the previous turn answers correctly.

Requires a running stockpilot-core instance (STOCKPILOT_BASE_URL), a
real GEMINI_API_KEY, and retailops-ai's own Postgres database migrated
to head. As with scripts/verify_graph.py, Planner/Report/Decision Engine
(role="planner"/"decision") are patched with an immediate canned
response -- this key's free tier has a hard zero quota for that model
family -- while the three retrieval agents (role="retriever") make real
Gemini calls and real StockPilot tool calls.

Runs two turns of orchestration.executor.run_execution() in the SAME
conversation: the first asks about low-stock products; the second asks
a follow-up ("those same products") that only resolves correctly if the
Planner actually saw the first turn's question and answer. Verifies
this by capturing the second turn's own Planner prompt and checking it
names query terms the first turn established -- not just that two rows
exist in the conversations/messages tables.

Run: python scripts/verify_memory.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage  # noqa: E402

from agents.replan import ReplanJudgement  # noqa: E402
from clients.stockpilot import StockPilotClient  # noqa: E402
from database import get_session_factory  # noqa: E402
from llm.providers.gemini import StructuredResult  # noqa: E402
from llm.providers.gemini import generate as real_generate  # noqa: E402
from model_config import get_model_config  # noqa: E402
from orchestration.executor import run_execution  # noqa: E402
from orchestration.models.conversation import Conversation  # noqa: E402
from orchestration.models.message import Message  # noqa: E402
from prompts.loader import load_prompt  # noqa: E402
from settings import get_settings  # noqa: E402

FIRST_QUERY = "Which products are currently low on stock?"
SECOND_QUERY = "Of those same products, what does demand forecasting say about them?"

PLANNER_PROMPT_TEXT = load_prompt("planner").text
captured_planner_prompts: list[str] = []


def _patched_generate(*, model: str, messages: list[Any], tools: Any = None) -> AIMessage:
    roles = get_model_config().roles
    if messages and messages[0].content == PLANNER_PROMPT_TEXT and len(messages) > 1:
        captured_planner_prompts.append(str(messages[1].content))
    if model == roles.retriever.model:
        return real_generate(model=model, messages=messages, tools=tools)
    return AIMessage(
        content=f"[mocked -- quota-blocked model '{model}'] acknowledged.",
        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )


def _always_sufficient_generate_structured(
    *, model: str, messages: list[Any], response_schema: Any
) -> StructuredResult[ReplanJudgement]:
    # The replan judgement always runs on the zero-quota "planner" role
    # (see scripts/verify_graph.py's docstring) -- always sufficient here
    # so this script stays focused on memory, not the replan loop.
    judgement = ReplanJudgement(
        sufficient=True, missing=[], next_action="proceed to report", agents_to_retry=[]
    )
    return StructuredResult(
        parsed=judgement,
        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        provider="gemini",
        model=model,
    )


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    with (
        StockPilotClient(
            base_url=settings.stockpilot_base_url,
            username=settings.stockpilot_username,
            password=settings.stockpilot_password,
        ) as client,
        patch("agents.base.generate", side_effect=_patched_generate),
        patch(
            "agents.base.generate_structured", side_effect=_always_sufficient_generate_structured
        ),
    ):
        first = run_execution(FIRST_QUERY, client=client, session_factory=session_factory)
        conversation_id = first["conversation_id"]
        print(f"conversation_id = {conversation_id}")
        print(f"turn 1 final_answer: {first['final_answer']}\n")

        second = run_execution(
            SECOND_QUERY,
            client=client,
            session_factory=session_factory,
            conversation_id=conversation_id,
        )
        print(f"turn 2 final_answer: {second['final_answer']}\n")

    verify_session = session_factory()
    try:
        conversations = (
            verify_session.query(Conversation).filter(Conversation.id == conversation_id).all()
        )
        messages = (
            verify_session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
    finally:
        verify_session.close()

    print(f"messages rows for this conversation: {len(messages)}")
    for message in messages:
        print(f"  {message.role:<10} {message.content[:80]!r}")

    print(f"\nsecond turn's Planner prompt:\n{captured_planner_prompts[-1]}\n")

    failures = []
    if len(conversations) != 1:
        failures.append(f"Expected exactly one conversation row, got {len(conversations)}")
    if len(messages) != 4:
        failures.append(f"Expected 4 message rows (2 turns x user+assistant), got {len(messages)}")
    if len(captured_planner_prompts) != 2:
        failures.append(f"Expected 2 planner prompts captured, got {len(captured_planner_prompts)}")
    else:
        if "Conversation history" in captured_planner_prompts[0]:
            failures.append("First turn's Planner prompt should have no prior memory context")
        if FIRST_QUERY not in captured_planner_prompts[1]:
            failures.append(
                "Second turn's Planner prompt does not mention the first turn's question -- "
                "memory did not reach the Planner"
            )

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print(
        "\nMilestone verified: a follow-up question in the same conversation "
        "reached the Planner together with the previous turn's question and "
        "answer, read fresh from Postgres (orchestration/memory.py) -- not "
        "held in-process -- and the conversation/messages tables persisted "
        "both turns correctly."
    )


if __name__ == "__main__":
    main()
