"""Stage 3 Task 3.5: the citation validator. Two tests here are
REQUIRED by the spec and must never be skipped: rejecting a fabricated
figure, and rejecting a real number presented without its provenance
label.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from orchestration.models.execution import Execution
from orchestration.models.tool_call import ToolCall
from orchestration.validator import insufficient_data_message, validate_citations


def _new_execution(db_session: Session) -> uuid.UUID:
    execution = Execution(query="q", status="running")
    db_session.add(execution)
    db_session.commit()
    return execution.id


def _add_tool_call(
    db_session: Session,
    execution_id: uuid.UUID,
    *,
    raw_response: object,
    provenance_map: dict[str, str] | None = None,
) -> None:
    db_session.add(
        ToolCall(
            execution_id=execution_id,
            tool_name="get_product",
            args={},
            raw_response=raw_response,
            provenance_map=provenance_map or {},
            latency_ms=5,
            status="success",
        )
    )
    db_session.commit()


def test_validate_citations_returns_empty_for_a_draft_with_no_numbers(
    db_session: Session,
) -> None:
    execution_id = _new_execution(db_session)

    failures = validate_citations(
        "Everything looks fine, no issues to report.", lambda: db_session, execution_id
    )

    assert failures == []


def test_validate_citations_accepts_a_grounded_and_provenanced_number(
    db_session: Session,
) -> None:
    execution_id = _new_execution(db_session)
    _add_tool_call(
        db_session,
        execution_id,
        raw_response={"sku": "85048", "unit_cost": 2.15},
        provenance_map={"sku": "observed", "unit_cost": "derived"},
    )

    failures = validate_citations("The unit cost is $2.15.", lambda: db_session, execution_id)

    assert failures == []


def test_validate_citations_rejects_a_fabricated_figure(db_session: Session) -> None:
    """REQUIRED test -- must never be skipped."""
    execution_id = _new_execution(db_session)
    _add_tool_call(
        db_session,
        execution_id,
        raw_response={"sku": "85048", "unit_cost": 2.15},
        provenance_map={"sku": "observed", "unit_cost": "derived"},
    )

    failures = validate_citations(
        "Revenue at risk is $47,000 this month.", lambda: db_session, execution_id
    )

    assert len(failures) == 1
    assert failures[0].reason == "not_found"
    assert failures[0].value == 47000.0


def test_validate_citations_rejects_a_real_number_without_its_provenance_label(
    db_session: Session,
) -> None:
    """REQUIRED test -- must never be skipped."""
    execution_id = _new_execution(db_session)
    _add_tool_call(
        db_session,
        execution_id,
        raw_response={"sku": "85048", "unit_cost": 2.15, "internal_flag": 99},
        provenance_map={"sku": "observed", "unit_cost": "derived"},
        # "internal_flag" deliberately has no provenance label.
    )

    failures = validate_citations("There are 99 units affected.", lambda: db_session, execution_id)

    assert len(failures) == 1
    assert failures[0].reason == "missing_provenance"
    assert failures[0].value == 99.0


def test_validate_citations_uses_per_row_provenance_for_nested_movement_history(
    db_session: Session,
) -> None:
    """MovementHistoryEntry-style nested rows carry their own literal
    "provenance" string sibling instead of a flat field-name map.
    """
    execution_id = _new_execution(db_session)
    _add_tool_call(
        db_session,
        execution_id,
        raw_response={
            "sku": "85048",
            "movement_history": [{"quantity": 12, "provenance": "observed"}],
        },
        provenance_map={"sku": "observed"},
    )

    failures = validate_citations("12 units moved last week.", lambda: db_session, execution_id)

    assert failures == []


def test_validate_citations_dedupes_repeated_tokens(db_session: Session) -> None:
    execution_id = _new_execution(db_session)

    failures = validate_citations(
        "We are missing $500. We are still missing $500.", lambda: db_session, execution_id
    )

    assert len(failures) == 1


def test_insufficient_data_message_names_the_offending_values(db_session: Session) -> None:
    execution_id = _new_execution(db_session)

    failures = validate_citations("Fabricated: $999.", lambda: db_session, execution_id)
    message = insufficient_data_message(failures)

    assert message.startswith("INSUFFICIENT_DATA")
    assert "$999" in message
