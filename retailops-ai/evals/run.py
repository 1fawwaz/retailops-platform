"""Stage 5 CLI entrypoint -- `make eval` runs this directly (the same
"invoke the script, not a `-m` package path" pattern every script under
scripts/ already uses, since this repo's own modules -- agents, clients,
orchestration, evals -- live flat under retailops-ai/, not nested inside
a `retailops_ai` package).

Prints a per-scenario table and a summary line, then enforces the
spec's CI gate: grounding must be 100%, and accuracy may not regress
below the recorded baseline (evals/baseline.json, committed to the
repo -- see docs/adr/006-evaluation-strategy.md). Exits non-zero on a
gate failure so CI can fail the build on it.

Run with --record-baseline to (re-)write baseline.json from this run's
own accuracy score. Deliberately a separate, explicit flag -- never
done implicitly by a normal `make eval` run, so a regression can't
quietly lower its own bar by re-recording itself as the new baseline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("RETAILOPS_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("STOCKPILOT_BASE_URL", "http://localhost:8000")
os.environ.setdefault("STOCKPILOT_USERNAME", "eval@example.com")
os.environ.setdefault("STOCKPILOT_PASSWORD", "eval-password-not-for-production")
os.environ.setdefault("GEMINI_API_KEY", "eval-key-not-for-production")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.runner import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    EvalSummary,
    check_gate,
    load_baseline_accuracy,
    run_all_scenarios,
    summarize,
    write_baseline_accuracy,
)

_COLUMNS = ("grounding", "accuracy", "routing", "replan", "refusal")


def _print_report(summary: EvalSummary) -> None:
    header = (
        f"{'scenario':<28}" + "".join(f"{col:<11}" for col in _COLUMNS) + f"{'tokens':<8}latency"
    )
    print(header)
    for r in summary.results:
        flags = (
            r.grounding_passed,
            r.accuracy.passed,
            r.routing_passed,
            r.replan_passed,
            r.refusal_passed,
        )
        row = f"{r.scenario_id:<28}" + "".join(
            f"{'PASS' if flag else 'FAIL':<11}" for flag in flags
        )
        row += f"{r.tokens:<8}{r.latency_seconds:.3f}s"
        print(row)
        for failure in r.accuracy.failures:
            print(f"    - {failure}")
    print()
    print(
        f"grounding={summary.grounding_pct:.1f}%  accuracy={summary.accuracy_pct:.1f}%  "
        f"routing={summary.routing_pct:.1f}%  replan={summary.replan_pct:.1f}%  "
        f"refusal={summary.refusal_pct:.1f}%  "
        f"tokens={summary.total_tokens}  latency={summary.total_latency_seconds:.3f}s"
    )


def main(argv: list[str]) -> int:
    record_baseline = "--record-baseline" in argv

    results = run_all_scenarios()
    summary = summarize(results)
    _print_report(summary)

    if record_baseline:
        write_baseline_accuracy(summary.accuracy_pct)
        print(
            f"\nBaseline recorded: accuracy={summary.accuracy_pct:.1f}% -> {DEFAULT_BASELINE_PATH}"
        )
        return 0

    baseline_accuracy = load_baseline_accuracy()
    failures = check_gate(summary, baseline_accuracy)
    if failures:
        print("\nCI GATE FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nCI GATE PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
