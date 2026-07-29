"""Stage 2 Task 2.5 milestone: verify config/models.yaml's model IDs
against Gemini's real model-list endpoint before first use, and reject
any Gemini 2.5 model (that generation is scheduled for shutdown October
2026, per CLAUDE.md).

Requires a real GEMINI_API_KEY in .env.

Run: python scripts/verify_model_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.providers.gemini import list_model_ids  # noqa: E402
from model_config import get_model_config  # noqa: E402

BANNED_GENERATION_PREFIX = "gemini-2.5"


def main() -> None:
    config = get_model_config()
    available = set(list_model_ids())

    configured = {
        "planner": config.roles.planner,
        "retriever": config.roles.retriever,
        "decision": config.roles.decision,
    }

    failures: dict[str, list[str]] = {role: [] for role in configured}
    for role, model_id in configured.items():
        if model_id not in available:
            failures[role].append(f"'{model_id}' is not in Gemini's current model list")
        if model_id.startswith(BANNED_GENERATION_PREFIX):
            failures[role].append(
                f"'{model_id}' is a Gemini 2.5 model, scheduled for shutdown October 2026 "
                "-- not allowed per CLAUDE.md"
            )

    print(f"{'ROLE':<12} {'MODEL ID':<32} RESULT")
    print("-" * 70)
    for role, model_id in configured.items():
        status = "OK" if not failures[role] else "FAIL"
        print(f"{role:<12} {model_id:<32} {status}")

    all_failures = [msg for messages in failures.values() for msg in messages]
    if all_failures:
        print("\n".join(all_failures))
        raise SystemExit(1)
    print("\nAll configured model IDs verified against the live Gemini model list.")


if __name__ == "__main__":
    main()
