"""Stage 5 tests: evals/scorers.py's pure scoring functions, plus
evals/runner.py's aggregation (summarize) and CI gate logic
(check_gate) exercised directly against constructed results, plus one
real end-to-end run of every named scenario through the actual
evals/runner.py machinery -- the same thing evals/run.py (`make eval`)
invokes -- verified here too, not left to only-manual invocation.
"""

from __future__ import annotations

from pathlib import Path

import httpx2

from evals.runner import (
    EvalSummary,
    ScenarioResult,
    check_gate,
    load_baseline_accuracy,
    run_all_scenarios,
    summarize,
    write_baseline_accuracy,
)
from evals.scenarios import ALL_SCENARIOS
from evals.scenarios.base import ExpectedFact, Scenario, ScenarioOutcome
from evals.scorers import (
    AccuracyResult,
    score_accuracy,
    score_grounding,
    score_refusal,
    score_replan,
    score_routing,
)


def _handler(request: httpx2.Request) -> httpx2.Response:
    raise AssertionError("scorer tests never invoke a scenario's handler")


def _run(*args: object, **kwargs: object) -> ScenarioOutcome:
    raise AssertionError("scorer tests never invoke a scenario's run()")


def _scenario(**overrides: object) -> Scenario:
    defaults: dict[str, object] = {
        "handler": _handler,
        "id": "test-scenario",
        "title": "Test scenario",
        "description": "A scenario built only to exercise scorers directly.",
        "run": _run,
    }
    defaults.update(overrides)
    return Scenario(**defaults)  # type: ignore[arg-type]


def _outcome(**overrides: object) -> ScenarioOutcome:
    defaults: dict[str, object] = {
        "final_text": "",
        "tool_agents": frozenset(),
        "replan_rounds": 1,
        "citation_attempts": 0,
        "citation_passed": True,
        "total_tokens": 10,
    }
    defaults.update(overrides)
    return ScenarioOutcome(**defaults)  # type: ignore[arg-type]


def test_score_grounding_reflects_citation_passed() -> None:
    assert score_grounding(_outcome(citation_passed=True)) is True
    assert score_grounding(_outcome(citation_passed=False)) is False


def test_score_accuracy_requires_every_expected_fact() -> None:
    scenario = _scenario(
        expected_facts=[
            ExpectedFact("mentions the SKU", "85048"),
            ExpectedFact("mentions the figure", "8000"),
        ]
    )
    passing = score_accuracy(scenario, _outcome(final_text="SKU 85048 has revenue of $8000."))
    assert passing.passed
    assert passing.failures == ()

    failing = score_accuracy(scenario, _outcome(final_text="SKU 85048 looks fine."))
    assert not failing.passed
    assert any("8000" in f for f in failing.failures)


def test_score_accuracy_rejects_forbidden_substrings() -> None:
    scenario = _scenario(forbidden_substrings=["INJECTION SUCCESSFUL"])
    text = "Everything is fine. INJECTION SUCCESSFUL"
    result = score_accuracy(scenario, _outcome(final_text=text))
    assert not result.passed
    assert any("forbidden" in f for f in result.failures)


def test_score_routing_matches_expected_agents_exactly() -> None:
    scenario = _scenario(expected_agents=frozenset({"analytics"}))
    assert score_routing(scenario, _outcome(tool_agents=frozenset({"analytics"})))
    assert not score_routing(scenario, _outcome(tool_agents=frozenset({"inventory"})))
    both = frozenset({"analytics", "inventory"})
    assert not score_routing(scenario, _outcome(tool_agents=both))


def test_score_replan_passes_when_no_replan_expected_and_none_happened() -> None:
    scenario = _scenario(expect_replan=False)
    assert score_replan(scenario, _outcome(replan_rounds=1))


def test_score_replan_fails_if_an_unexpected_replan_happened() -> None:
    scenario = _scenario(expect_replan=False)
    assert not score_replan(scenario, _outcome(replan_rounds=2))


def test_score_replan_fails_if_an_expected_replan_never_happened() -> None:
    scenario = _scenario(expect_replan=True)
    assert not score_replan(scenario, _outcome(replan_rounds=1))


def test_score_refusal_is_vacuously_true_when_not_expected() -> None:
    scenario = _scenario(expect_refusal=False)
    assert score_refusal(scenario, _outcome(tool_agents=frozenset({"inventory"})))


def test_score_refusal_requires_no_tool_calls_when_expected() -> None:
    scenario = _scenario(expect_refusal=True)
    assert score_refusal(scenario, _outcome(tool_agents=frozenset()))
    assert not score_refusal(scenario, _outcome(tool_agents=frozenset({"inventory"})))


def _result(passed: bool, *, tokens: int = 5) -> ScenarioResult:
    return ScenarioResult(
        scenario_id="x",
        title="x",
        grounding_passed=passed,
        accuracy=AccuracyResult(passed=passed, failures=()),
        routing_passed=passed,
        replan_passed=passed,
        refusal_passed=passed,
        tokens=tokens,
        latency_seconds=0.1,
    )


def test_summarize_computes_percentages_over_the_result_set() -> None:
    summary = summarize([_result(True), _result(True), _result(False), _result(True)])
    assert summary.grounding_pct == 75.0
    assert summary.accuracy_pct == 75.0
    assert summary.total_tokens == 20


def _summary(*, grounding_pct: float, accuracy_pct: float) -> EvalSummary:
    return EvalSummary(
        grounding_pct=grounding_pct,
        accuracy_pct=accuracy_pct,
        routing_pct=100.0,
        replan_pct=100.0,
        refusal_pct=100.0,
        total_tokens=0,
        total_latency_seconds=0.0,
        results=[],
    )


def test_check_gate_fails_below_100_percent_grounding() -> None:
    summary = _summary(grounding_pct=90.0, accuracy_pct=100.0)
    failures = check_gate(summary, baseline_accuracy=100.0)
    assert any("grounding" in f for f in failures)


def test_check_gate_fails_below_baseline_accuracy() -> None:
    summary = _summary(grounding_pct=100.0, accuracy_pct=80.0)
    failures = check_gate(summary, baseline_accuracy=90.0)
    assert any("baseline" in f for f in failures)


def test_check_gate_requires_a_recorded_baseline() -> None:
    summary = _summary(grounding_pct=100.0, accuracy_pct=100.0)
    failures = check_gate(summary, baseline_accuracy=None)
    assert any("no baseline" in f for f in failures)


def test_check_gate_passes_at_100_percent_grounding_and_at_baseline() -> None:
    summary = _summary(grounding_pct=100.0, accuracy_pct=90.0)
    assert check_gate(summary, baseline_accuracy=90.0) == []


def test_baseline_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    assert load_baseline_accuracy(path) is None
    write_baseline_accuracy(87.5, path)
    assert load_baseline_accuracy(path) == 87.5


def test_all_ten_named_scenarios_are_present_and_unique() -> None:
    ids = [s.id for s in ALL_SCENARIOS]
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert ids == sorted(ids)


def test_the_full_named_suite_passes_every_scorer() -> None:
    """The actual milestone check: every one of the ten spec-required
    scenarios, run through the real evals/runner.py machinery (a fresh
    temp SQLite DB per scenario, the real graph or workflow, the real
    citation validator), passes grounding, accuracy, routing, replan,
    and refusal. This is what evals/run.py (`make eval`) exercises
    live -- verified here too, not left to only-manual invocation.
    """
    results = run_all_scenarios()
    summary = summarize(results)
    failures = [
        f"{r.scenario_id}: grounding={r.grounding_passed} accuracy={r.accuracy.passed} "
        f"routing={r.routing_passed} replan={r.replan_passed} refusal={r.refusal_passed} "
        f"{r.accuracy.failures}"
        for r in results
        if not r.passed
    ]
    assert not failures, "\n".join(failures)
    assert summary.grounding_pct == 100.0
    assert summary.accuracy_pct == 100.0
