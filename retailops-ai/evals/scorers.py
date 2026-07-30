"""Stage 5: pure scoring functions. Each takes a `Scenario` (the fixed
expectation) and the `ScenarioOutcome` its own `run()` produced, and
returns a pass/fail plus, where relevant, why it failed.

Grounding is deliberately NOT re-implemented here. It reuses the
citation validator's own verdict (orchestration/validator.py, already
exercised for real inside run_execution()) rather than re-deriving
numeric-claim correctness a second time in the eval harness --
`ScenarioOutcome.citation_passed` IS that verdict. For 04-supplier-delay
(the one scenario that runs orchestration/workflows.py instead of the
general chat path), citation_passed is hardcoded True in
evals/scenarios/base.py, not skipped: that workflow's Decision Engine
has zero tools and every number it reports is Python-computed from
cited tool calls before the LLM ever sees it (invariant 1), so grounding
there is guaranteed by construction rather than by the validator node
-- a structural guarantee, not an untested assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

from evals.scenarios.base import Scenario, ScenarioOutcome


def score_grounding(outcome: ScenarioOutcome) -> bool:
    return outcome.citation_passed


@dataclass(frozen=True)
class AccuracyResult:
    passed: bool
    failures: tuple[str, ...]


def score_accuracy(scenario: Scenario, outcome: ScenarioOutcome) -> AccuracyResult:
    text = outcome.final_text.lower()
    failures: list[str] = []
    for fact in scenario.expected_facts:
        if fact.substring.lower() not in text:
            failures.append(f"missing expected fact ({fact.description}): {fact.substring!r}")
    for forbidden in scenario.forbidden_substrings:
        if forbidden.lower() in text:
            failures.append(f"forbidden substring present: {forbidden!r}")
    return AccuracyResult(passed=not failures, failures=tuple(failures))


def score_routing(scenario: Scenario, outcome: ScenarioOutcome) -> bool:
    return outcome.tool_agents == scenario.expected_agents


def score_replan(scenario: Scenario, outcome: ScenarioOutcome) -> bool:
    """Did it replan when evidence was insufficient, and NOT replan when
    it was sufficient. `replan_rounds` is `len(replan_history)`, which
    is always >=1 for a chat-path scenario (round 1's own judgement is
    itself an entry) -- a genuine extra retrieval round only happens
    when a second entry gets appended, i.e. replan_rounds > 1.

    None of the ten named scenarios in docs/BUILD-SPEC.md's own list
    call for genuine insufficiency-driven replanning (that mechanism has
    its own dedicated deterministic test,
    tests/test_graph.py::test_replan_loop_triggers_a_second_targeted_retrieval_round,
    from Stage 3 Task 3.3) -- every scenario here defaults to
    `expect_replan=False`, so this scorer's real job today is confirming
    the Planner doesn't replan needlessly, not exercising the loop
    itself. Said plainly, not left implicit.
    """
    replanned = outcome.replan_rounds > 1
    return replanned == scenario.expect_replan


def score_refusal(scenario: Scenario, outcome: ScenarioOutcome) -> bool:
    if not scenario.expect_refusal:
        return True
    return outcome.tool_agents == frozenset()
