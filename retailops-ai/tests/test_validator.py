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
from orchestration.validator import insufficient_data_message, resolve_citations, validate_citations


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
    tool_name: str = "get_product",
    agent_step_id: int | None = None,
) -> uuid.UUID:
    call = ToolCall(
        execution_id=execution_id,
        agent_step_id=agent_step_id,
        tool_name=tool_name,
        args={},
        raw_response=raw_response,
        provenance_map=provenance_map or {},
        latency_ms=5,
        status="success",
    )
    db_session.add(call)
    db_session.commit()
    return call.tool_call_id


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


def test_resolve_citations_returns_empty_for_a_draft_with_no_numbers(db_session: Session) -> None:
    execution_id = _new_execution(db_session)

    citations = resolve_citations(
        "Everything looks fine, no issues to report.", lambda: db_session, execution_id
    )

    assert citations == []


def test_resolve_citations_names_the_tool_call_field_and_agent_a_number_came_from(
    db_session: Session,
) -> None:
    """agent_by_tool_call_id is how the real caller
    (orchestration/executor.py::build_query_response_fields()) supplies
    agent attribution -- NOT ToolCall.agent_step_id, which is never
    actually populated anywhere in this codebase (a known,
    pre-existing gap, confirmed live: every citation's "agent" came
    back None until this was fixed to read from
    ExecutionState["tool_ledger"] instead, the same source Task F3's
    own agent tagging already uses).
    """
    execution_id = _new_execution(db_session)
    tool_call_id = _add_tool_call(
        db_session,
        execution_id,
        raw_response={"sku": "85048", "unit_cost": 2.15},
        provenance_map={"sku": "observed", "unit_cost": "derived"},
        tool_name="get_product",
    )

    citations = resolve_citations(
        "The unit cost is $2.15.",
        lambda: db_session,
        execution_id,
        agent_by_tool_call_id={str(tool_call_id): "inventory"},
    )

    assert len(citations) == 1
    citation = citations[0]
    assert citation.value == 2.15
    assert citation.tool_call_id == str(tool_call_id)
    assert citation.tool_name == "get_product"
    assert citation.agent == "inventory"
    assert citation.field_name == "unit_cost"
    assert citation.provenance == "derived"


def test_resolve_citations_flags_an_ungrounded_number_with_no_tool_call_id(
    db_session: Session,
) -> None:
    """MISSING SOURCE, in docs/DESIGN-SPEC.md's own vocabulary --
    structurally shouldn't reach a real client (validate_citations
    already rejects this draft before it's ever returned), but the
    resolver's own behaviour is tested independently of that guarantee.
    """
    execution_id = _new_execution(db_session)

    citations = resolve_citations(
        "Revenue at risk is $47,000 this month.", lambda: db_session, execution_id
    )

    assert len(citations) == 1
    assert citations[0].tool_call_id is None
    assert citations[0].tool_name is None
    assert citations[0].agent is None
    assert citations[0].value == 47000.0


def test_resolve_citations_uses_the_sibling_provenance_for_nested_movement_history(
    db_session: Session,
) -> None:
    execution_id = _new_execution(db_session)
    tool_call_id = _add_tool_call(
        db_session,
        execution_id,
        raw_response={
            "sku": "85048",
            "movement_history": [{"quantity": 12, "provenance": "observed"}],
        },
        provenance_map={"sku": "observed"},
    )

    citations = resolve_citations("12 units moved last week.", lambda: db_session, execution_id)

    assert len(citations) == 1
    assert citations[0].tool_call_id == str(tool_call_id)
    assert citations[0].field_name == "quantity"
    assert citations[0].provenance == "observed"


def test_resolve_citations_skips_system_generated_notices(db_session: Session) -> None:
    """Digits inside the Task 3.6 LLM-outage fallback or the
    INSUFFICIENT_DATA give-up message aren't an LLM claim about business
    data -- citation chips on them would be noise, not grounding.
    """
    execution_id = _new_execution(db_session)

    assert (
        resolve_citations(
            "INCOMPLETE: the decision step could not reach the LLM after 3 retries.",
            lambda: db_session,
            execution_id,
        )
        == []
    )
    assert (
        resolve_citations(
            "INSUFFICIENT_DATA: this answer cannot be fully grounded. 'Ungrounded ($42)'",
            lambda: db_session,
            execution_id,
        )
        == []
    )


def test_resolve_citations_dedupes_repeated_tokens(db_session: Session) -> None:
    execution_id = _new_execution(db_session)
    _add_tool_call(
        db_session,
        execution_id,
        raw_response={"unit_cost": 2.15},
        provenance_map={"unit_cost": "derived"},
    )

    citations = resolve_citations(
        "The unit cost is $2.15. Again, $2.15.", lambda: db_session, execution_id
    )

    assert len(citations) == 1
