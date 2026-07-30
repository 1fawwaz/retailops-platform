"""Stage 3 Task 3.5: the citation validator -- a graph node that runs
before every response is finalized. CLAUDE.md invariant 1 makes Report
and Decision Engine tool-less BY DESIGN so they are structurally
incapable of inventing a number; this validator is the runtime
enforcement that actually PROVES that guarantee held for a given
execution, rather than trusting the architecture silently.

Extracts every numeric token from the Decision Engine's draft answer
and confirms each one traces back to a value that genuinely appears
somewhere in a `tool_calls.raw_response` recorded for this execution,
AND that the specific field it came from carries a provenance label --
via `tool_calls.provenance_map` (the flat per-field-name label dict
every StockPilot response carries, see tools/stockpilot_tools.py), or,
for the one place this codebase's own data uses a different shape
(`MovementHistoryEntry`'s per-row `provenance` string, since a flat
per-field map can't express a per-row split), a sibling "provenance" key
on the same object. A number that isn't found anywhere is treated as
fabricated; a number that IS found but whose field carries no
provenance label anywhere is treated as un-cited.

Fail once -> the graph regenerates the answer with the offending values
named explicitly (orchestration/graph.py's decision node reads
`citation_failures` to build that prompt). Fail twice -> the graph
gives up and returns a fixed INSUFFICIENT_DATA message naming what
couldn't be verified, rather than retrying a third time.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from orchestration.models.tool_call import ToolCall

# Mirrors orchestration/graph.py's own LLM_DEGRADED_ANSWER_PREFIX and this
# module's own insufficient_data_message() prefix EXACTLY -- duplicated as
# literals rather than imported, since graph.py imports FROM this module
# (validate_citations/insufficient_data_message) and importing back from
# graph.py would create a cycle. If either prefix ever changes, both call
# sites (_make_validator_node's own check, here) need updating together.
_SYSTEM_GENERATED_PREFIXES = ("INCOMPLETE:", "INSUFFICIENT_DATA:")

# Matches an optional currency sign, digits with optional thousands
# separators, an optional decimal part, and an optional trailing "%" --
# e.g. "$1,234.56", "42%", "7", "-3.5". Deliberately broad: it also
# matches incidental numbers (SKU codes, counts) as well as business
# metrics. Under-matching risks letting a fabricated business number
# slip through unchecked, which is the worse failure mode for a
# validator -- a documented limitation, not an oversight, is that a
# genuinely non-numeric-claim reading (e.g. a SKU written verbatim in
# the answer) must ALSO trace back to recorded tool data, which is true
# in practice since SKUs come from retrieved data too.
NUMBER_PATTERN = re.compile(r"-?[$£€]?\d[\d,]*(?:\.\d+)?%?")

_PROVENANCE_KEYS = {"_provenance", "_derivation_ref", "provenance"}


@dataclass(frozen=True)
class CitationFailure:
    token: str
    value: float
    reason: str  # "not_found" | "missing_provenance"


def _extract_numeric_tokens(text: str) -> list[str]:
    return NUMBER_PATTERN.findall(text)


def _normalize(token: str) -> float | None:
    # Rounded to 2 decimal places: a deliberate, documented tolerance so
    # trivial formatting differences between a raw stored value (e.g.
    # 42.0) and its prose rendering (e.g. "42") don't cause a false
    # rejection of a genuinely cited number. Not a general fix for every
    # formatting mismatch (percentages written in the draft as "15%" but
    # stored as a fraction 0.15 will still fail to match) -- a known,
    # accepted limitation rather than an attempt at full unit reconciliation.
    cleaned = token.replace("$", "").replace("£", "").replace("€", "")
    cleaned = cleaned.replace(",", "").replace("%", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _iter_numeric_leaves(value: object) -> Iterator[tuple[str, float, dict[str, Any]]]:
    """Yields (field_name, value, containing_object) for every numeric
    leaf anywhere in a tool's raw_response, however deeply nested --
    `containing_object` is the immediate dict the number came from, so
    its own sibling keys can be checked for a provenance label.

    Numeric-looking STRING values (e.g. a SKU like "85048") count too,
    not just genuine JSON numbers: a SKU cited in prose is just digits,
    indistinguishable from any other number by the time it's text, but
    this codebase stores SKUs as strings. A plain non-numeric string
    (a description, a date) fails `_normalize` and is correctly skipped,
    not recursed into further (strings have no children to flatten).
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PROVENANCE_KEYS:
                continue
            if isinstance(item, bool):
                continue
            if isinstance(item, int | float):
                yield key, round(float(item), 2), value
            elif isinstance(item, str):
                normalized = _normalize(item)
                if normalized is not None:
                    yield key, normalized, value
            else:
                yield from _iter_numeric_leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_numeric_leaves(item)


def _has_provenance(
    field_name: str, containing_object: dict[str, Any], provenance_map: dict[str, Any]
) -> bool:
    if field_name in provenance_map:
        return True
    sibling = containing_object.get("provenance")
    return isinstance(sibling, str) and bool(sibling)


def validate_citations(
    draft: str,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
) -> list[CitationFailure]:
    """Every numeric token in `draft` must trace back to a value recorded
    in this execution's own tool_calls, with provenance carried through.
    Returns the (possibly empty) list of tokens that don't.
    """
    tokens = _extract_numeric_tokens(draft)
    if not tokens:
        return []

    session = session_factory()
    try:
        tool_calls = session.query(ToolCall).filter(ToolCall.execution_id == execution_id).all()
    finally:
        session.close()

    grounded: set[float] = set()
    ungrounded: set[float] = set()
    for call in tool_calls:
        provenance_map = call.provenance_map or {}
        if call.raw_response is None:
            continue
        for field_name, value, containing in _iter_numeric_leaves(call.raw_response):
            if _has_provenance(field_name, containing, provenance_map):
                grounded.add(value)
            else:
                ungrounded.add(value)

    failures: list[CitationFailure] = []
    seen_values: set[float] = set()
    for token in tokens:
        normalized = _normalize(token)
        if normalized is None or normalized in seen_values:
            continue
        seen_values.add(normalized)
        if normalized in grounded:
            continue
        reason = "missing_provenance" if normalized in ungrounded else "not_found"
        failures.append(CitationFailure(token=token, value=normalized, reason=reason))
    return failures


def insufficient_data_message(failures: list[CitationFailure]) -> str:
    missing = "; ".join(f"{failure.token!r} ({failure.reason})" for failure in failures)
    return (
        "INSUFFICIENT_DATA: this answer cannot be fully grounded in the evidence "
        "gathered for this execution. The following values could not be verified "
        f"against a recorded tool response with its provenance carried through: {missing}."
    )


@dataclass(frozen=True)
class CitationResolution:
    """Task F4 ("citation drill-down"): WHERE a token resolves to, not
    just whether it does. `tool_call_id` is None for a token with no
    grounded match anywhere -- the frontend's own explicit
    docs/DESIGN-SPEC.md "MISSING SOURCE" case. Structurally this should
    never actually reach a client: validate_citations() already rejects
    any draft containing an ungrounded token before it's ever returned
    (Task 3.5). The two functions stay independent on purpose rather
    than one trusting the other's verdict, so a future change to one
    can't silently break the other's own guarantee.
    """

    token: str
    value: float
    tool_call_id: str | None
    tool_name: str | None
    agent: str | None
    field_name: str | None
    provenance: str | None


def resolve_citations(
    draft: str,
    session_factory: Callable[[], Session],
    execution_id: uuid.UUID,
    *,
    agent_by_tool_call_id: dict[str, str] | None = None,
) -> list[CitationResolution]:
    """Same numeric-token extraction and grounding rules
    validate_citations() uses, but for a draft already known to pass
    (the final, returned answer) -- resolves each token to the specific
    tool call, field, and provenance label it came from, for the
    frontend's provenance drawer (`GET /agent/execution/{id}` supplies
    the matching raw_response once the drawer needs to render it; this
    only needs to name WHICH tool_call_id to look up there). Skips
    system-generated notices (the Task 3.6 LLM-outage fallback, the
    INSUFFICIENT_DATA give-up message) the same way
    _make_validator_node does -- these aren't LLM-authored claims about
    business data, so citation chips on stray digits inside an error
    sentence would be noise, not grounding.

    When more than one tool call's response contains the same numeric
    value, the first grounded match found wins -- an honest "a real
    source", not a claim of exclusivity; validate_citations() already
    establishes the value is grounded at all, which is the actual
    guarantee this codebase makes.

    `agent_by_tool_call_id` is an OPTIONAL map from tool_call_id to the
    agent that made it, keyed by str(tool_call_id) -- deliberately NOT
    resolved here via ToolCall.agent_step_id, which is never actually
    populated anywhere in this codebase (a known, pre-existing gap
    since Task 2.3/3.1: nothing ever writes it when a ToolCall is
    created, confirmed live during this task's own verification when
    every citation's "agent" came back None). The caller
    (orchestration/executor.py::build_query_response_fields()) already
    has the real answer sitting in ExecutionState["tool_ledger"], tagged
    with the correct agent per entry since Task F3's own fix -- passed
    in here rather than re-deriving it a second, broken way.
    """
    if draft.startswith(_SYSTEM_GENERATED_PREFIXES):
        return []

    tokens = _extract_numeric_tokens(draft)
    if not tokens:
        return []

    agent_lookup = agent_by_tool_call_id or {}

    session = session_factory()
    try:
        calls = session.query(ToolCall).filter(ToolCall.execution_id == execution_id).all()
    finally:
        session.close()

    resolved: dict[float, CitationResolution] = {}
    for call in calls:
        if call.raw_response is None:
            continue
        provenance_map = call.provenance_map or {}
        for field_name, value, containing in _iter_numeric_leaves(call.raw_response):
            if value in resolved or not _has_provenance(field_name, containing, provenance_map):
                continue
            label = provenance_map.get(field_name) or containing.get("provenance")
            resolved[value] = CitationResolution(
                token="",  # filled in per-occurrence below
                value=value,
                tool_call_id=str(call.tool_call_id),
                tool_name=call.tool_name,
                agent=agent_lookup.get(str(call.tool_call_id)),
                field_name=field_name,
                provenance=str(label) if label else None,
            )

    citations: list[CitationResolution] = []
    seen: set[float] = set()
    for token in tokens:
        normalized = _normalize(token)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        match = resolved.get(normalized)
        if match is None:
            citations.append(
                CitationResolution(
                    token=token,
                    value=normalized,
                    tool_call_id=None,
                    tool_name=None,
                    agent=None,
                    field_name=None,
                    provenance=None,
                )
            )
        else:
            citations.append(
                CitationResolution(
                    token=token,
                    value=match.value,
                    tool_call_id=match.tool_call_id,
                    tool_name=match.tool_name,
                    agent=match.agent,
                    field_name=match.field_name,
                    provenance=match.provenance,
                )
            )
    return citations
