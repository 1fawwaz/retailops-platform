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
