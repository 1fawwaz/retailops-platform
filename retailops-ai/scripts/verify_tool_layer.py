"""Stage 2 Task 2.3 milestone check: tools callable in isolation; every
call leaves a row.

Requires a running stockpilot-core instance (STOCKPILOT_BASE_URL) and
retailops-ai's own Postgres database migrated to head (the tool_calls
table from Task 2.1). Calls a representative sample of tools directly
-- no graph, no LLM -- against real data, and confirms each one leaves
a real tool_calls row in the real database.

Run: python scripts/verify_tool_layer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.stockpilot import StockPilotClient  # noqa: E402
from database import get_session_factory  # noqa: E402
from orchestration.models.execution import Execution  # noqa: E402
from orchestration.models.tool_call import ToolCall  # noqa: E402
from settings import get_settings  # noqa: E402
from tools.stockpilot_tools import build_stockpilot_tools  # noqa: E402


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    session = session_factory()
    execution = Execution(query="verify tool layer", status="running")
    session.add(execution)
    session.commit()
    execution_id = execution.id
    session.close()

    with StockPilotClient(
        base_url=settings.stockpilot_base_url,
        username=settings.stockpilot_username,
        password=settings.stockpilot_password,
    ) as client:
        tools = build_stockpilot_tools(client, session_factory, execution_id)
        tools_by_name = {t.name: t for t in tools}

        print(f"Built {len(tools)} tools for execution {execution_id}")

        checks = [
            ("list_products", {"limit": 3, "offset": 0}),
            ("get_stock", {"limit": 3}),
            ("get_forecast_accuracy", {}),
        ]
        for name, args in checks:
            result = tools_by_name[name].invoke(args)
            print(f"  {name}({args}) -> {type(result).__name__} (isolated call succeeded)")

    verify_session = session_factory()
    try:
        rows = (
            verify_session.query(ToolCall)
            .filter(ToolCall.execution_id == execution_id)
            .order_by(ToolCall.created_at)
            .all()
        )
    finally:
        verify_session.close()

    print(f"\ntool_calls rows for execution {execution_id}: {len(rows)}")
    for row in rows:
        print(
            f"  tool_call_id={row.tool_call_id} tool_name={row.tool_name} "
            f"status={row.status} latency_ms={row.latency_ms}"
        )

    expected_names = {name for name, _ in checks}
    actual_names = {row.tool_name for row in rows}
    if len(rows) != len(checks) or actual_names != expected_names:
        raise SystemExit(
            f"Expected exactly one row per call ({expected_names}), got {actual_names}"
        )
    if any(row.status != "success" for row in rows):
        raise SystemExit("Not every row has status=success")

    print("\nMilestone verified: every isolated tool call left exactly one tool_calls row.")


if __name__ == "__main__":
    main()
