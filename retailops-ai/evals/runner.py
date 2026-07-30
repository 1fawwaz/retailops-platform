"""Stage 5: runs all ten scenarios, each against its own fresh, isolated
temp-file SQLite database (the same WAL-mode pattern
tests/test_graph.py established for tolerating run_execution()'s
genuinely concurrent retrieval-agent threads -- an in-memory DB doesn't
survive that, see that fixture's own comment), and scores each with
evals/scorers.py.

This module is deliberately import-only (no argv handling, no file
I/O beyond building/tearing down a scenario's own temp DB) so it's
directly unit-testable; evals/run.py is the thin CLI wrapper `make eval`
actually invokes.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evals.scenarios import ALL_SCENARIOS
from evals.scenarios.base import Scenario, build_client
from evals.scorers import (
    AccuracyResult,
    score_accuracy,
    score_grounding,
    score_refusal,
    score_replan,
    score_routing,
)
from orchestration.models import Base

DEFAULT_BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"


@contextlib.contextmanager
def _temp_session_factory() -> Iterator[Callable[[], Session]]:
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()
        os.remove(path)
        for suffix in ("-wal", "-shm"):
            extra = path + suffix
            if os.path.exists(extra):
                os.remove(extra)


@dataclasses.dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    title: str
    grounding_passed: bool
    accuracy: AccuracyResult
    routing_passed: bool
    replan_passed: bool
    refusal_passed: bool
    tokens: int
    latency_seconds: float

    @property
    def passed(self) -> bool:
        return (
            self.grounding_passed
            and self.accuracy.passed
            and self.routing_passed
            and self.replan_passed
            and self.refusal_passed
        )


def run_scenario(scenario: Scenario) -> ScenarioResult:
    client = build_client(scenario.handler)
    with _temp_session_factory() as session_factory:
        start = time.perf_counter()
        outcome = scenario.run(client, session_factory)
        elapsed = time.perf_counter() - start
    outcome = dataclasses.replace(outcome, latency_seconds=elapsed)
    return ScenarioResult(
        scenario_id=scenario.id,
        title=scenario.title,
        grounding_passed=score_grounding(outcome),
        accuracy=score_accuracy(scenario, outcome),
        routing_passed=score_routing(scenario, outcome),
        replan_passed=score_replan(scenario, outcome),
        refusal_passed=score_refusal(scenario, outcome),
        tokens=outcome.total_tokens,
        latency_seconds=outcome.latency_seconds,
    )


def run_all_scenarios(scenarios: list[Scenario] | None = None) -> list[ScenarioResult]:
    chosen = scenarios if scenarios is not None else ALL_SCENARIOS
    return [run_scenario(scenario) for scenario in chosen]


@dataclasses.dataclass(frozen=True)
class EvalSummary:
    grounding_pct: float
    accuracy_pct: float
    routing_pct: float
    replan_pct: float
    refusal_pct: float
    total_tokens: int
    total_latency_seconds: float
    results: list[ScenarioResult]


def summarize(results: list[ScenarioResult]) -> EvalSummary:
    if not results:
        raise ValueError("cannot summarize an empty result set")
    n = len(results)
    return EvalSummary(
        grounding_pct=100.0 * sum(r.grounding_passed for r in results) / n,
        accuracy_pct=100.0 * sum(r.accuracy.passed for r in results) / n,
        routing_pct=100.0 * sum(r.routing_passed for r in results) / n,
        replan_pct=100.0 * sum(r.replan_passed for r in results) / n,
        refusal_pct=100.0 * sum(r.refusal_passed for r in results) / n,
        total_tokens=sum(r.tokens for r in results),
        total_latency_seconds=sum(r.latency_seconds for r in results),
        results=results,
    )


def load_baseline_accuracy(path: Path = DEFAULT_BASELINE_PATH) -> float | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return float(data["accuracy_pct"])


def write_baseline_accuracy(accuracy_pct: float, path: Path = DEFAULT_BASELINE_PATH) -> None:
    path.write_text(json.dumps({"accuracy_pct": accuracy_pct}, indent=2) + "\n")


def check_gate(summary: EvalSummary, baseline_accuracy: float | None) -> list[str]:
    """The spec's CI gate: grounding must be 100%; accuracy may not fall
    below the recorded baseline. Returns the list of gate failures (empty
    means pass) rather than raising, so a caller can print every reason
    at once instead of stopping at the first.
    """
    failures: list[str] = []
    if summary.grounding_pct < 100.0:
        failures.append(f"grounding {summary.grounding_pct:.1f}% is below the required 100%")
    if baseline_accuracy is None:
        failures.append("no baseline recorded yet -- run `make eval` with --record-baseline first")
    elif summary.accuracy_pct < baseline_accuracy:
        failures.append(
            f"accuracy {summary.accuracy_pct:.1f}% fell below baseline {baseline_accuracy:.1f}%"
        )
    return failures
