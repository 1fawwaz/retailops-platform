"""Stage 3 Task 3.4: orchestration/memory.py's conversation-history and
rolling-task-memory loader.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from orchestration.memory import ROLLING_WINDOW_SIZE, load_conversation_context
from orchestration.models.conversation import Conversation
from orchestration.models.execution import Execution
from orchestration.models.message import Message


def test_returns_none_for_a_standalone_run(db_session: Session) -> None:
    assert load_conversation_context(lambda: db_session, None) is None


def test_returns_none_for_a_brand_new_conversation(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.commit()

    assert load_conversation_context(lambda: db_session, conversation.id) is None


def test_includes_message_transcript_and_recent_execution_summaries(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.commit()

    db_session.add(
        Message(conversation_id=conversation.id, role="user", content="How's inventory?")
    )
    db_session.add(Message(conversation_id=conversation.id, role="assistant", content="It's fine."))
    db_session.add(
        Execution(
            conversation_id=conversation.id,
            query="How's inventory?",
            status="completed",
            plan={"text": "check stock levels"},
            final_answer="It's fine.",
            completed_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    context = load_conversation_context(lambda: db_session, conversation.id)

    assert context is not None
    assert "user: How's inventory?" in context
    assert "assistant: It's fine." in context
    assert "check stock levels" in context
    assert "It's fine." in context


def test_excludes_executions_that_are_not_completed(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.commit()
    db_session.add(Execution(conversation_id=conversation.id, query="q", status="running"))
    db_session.add(Execution(conversation_id=conversation.id, query="q2", status="failed"))
    db_session.commit()

    assert load_conversation_context(lambda: db_session, conversation.id) is None


def test_rolling_window_keeps_only_the_most_recent_executions(db_session: Session) -> None:
    conversation = Conversation()
    db_session.add(conversation)
    db_session.commit()

    base = datetime.now(UTC)
    for i in range(ROLLING_WINDOW_SIZE + 2):
        db_session.add(
            Execution(
                conversation_id=conversation.id,
                query=f"question {i}",
                status="completed",
                final_answer=f"answer {i}",
                completed_at=base + timedelta(seconds=i),
            )
        )
    db_session.commit()

    context = load_conversation_context(lambda: db_session, conversation.id)

    assert context is not None
    # The two oldest executions should have aged out of the rolling window.
    assert "question 0" not in context
    assert "question 1" not in context
    assert "question 2" in context
    assert f"question {ROLLING_WINDOW_SIZE + 1}" in context
