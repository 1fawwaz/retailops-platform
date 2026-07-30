# ADR 006: A scripted-scenario eval suite, scored against a committed baseline, gates CI on grounding and accuracy

## Status

Accepted — Stage 5 (Robustness).

## Context

`docs/BUILD-SPEC.md`'s Stage 5 asks for ten named scenarios (`evals/scenarios/`),
each with a seeded database state, a question, expected facts, and an
expected agent path; seven scorers (grounding, factual accuracy, routing
correctness, replan correctness, refusal correctness, cost, latency); a
`make eval` entrypoint; and a CI gate — grounding must be 100%, accuracy
may not fall below a recorded baseline. This ADR is about the concrete
mechanism, not the ten scenarios' individual content (each scenario file's
own docstring covers that).

Two constraints already established earlier in this build shaped every
decision here, not new ones invented for this stage:

- **No live stockpilot-core or live Gemini in CI.** CI has no
  `GEMINI_API_KEY` secret, and this project's own key has had unreliable
  free-tier quota all build (Stage 3 Tasks 3.1/3.2). stockpilot-core has
  also been blocked from starting at all on this machine by a recurring
  Windows Application Control policy against pandas' compiled DLL (first
  seen after Stage 2 Task 2.1, still reproducing as of Stage 4). A suite
  that depended on either would be unrunnable in CI and unreliable
  locally — the opposite of what a gate needs.
- **A scripted `StockPilotClient` + scripted `generate()`/`generate_structured()`
  over the real graph is already this codebase's established pattern**
  for exercising the real orchestration machinery without either
  dependency (`tests/test_graph.py`, `tests/test_query_coverage.py`).
  Stage 5 applies that same pattern at suite scale, not a new one.

## Decision

**Seeded database state = a scripted `httpx2.MockTransport` handler, not a
live seeded Postgres instance.** Each scenario module owns a `handler`
(hand-built JSON responses matching StockPilot's frozen contract, via
shared builders in `evals/scenarios/fixtures.py`) and scripted LLM
responses (`ScriptedGenerate`/`ScriptedReplan`, `evals/scenarios/base.py`)
constructed from that scenario's own script, not sampled live. Nine of the
ten scenarios run the real general-chat path
(`orchestration/executor.py::run_execution()`, what `POST /agent/query`
calls); `04-supplier-delay` runs `orchestration/workflows.py::run_inventory_health_workflow()`
instead, since `priority` is a Task 4.3 Decision-Engine concept that path
alone produces. Everything downstream of the mock boundary is real: the
actual LangGraph graph, the actual six agents, the actual citation
validator, the actual replan node.

**This makes the suite a regression test of the surrounding machinery
given a plausible scripted model decision — not a live judge of actual
model quality.** Said plainly here, not blurred: grounding enforcement,
routing, replan wiring, degradation handling, and refusal formatting are
genuinely exercised; whether Gemini itself would produce the scripted
text on a given day is not tested by this suite at all. That is a real,
accepted scope boundary, not a limitation hiding as a strength.

**Scorers reuse production verdicts instead of re-deriving them.**
Grounding (`evals/scorers.py::score_grounding`) is exactly
`ScenarioOutcome.citation_passed` — the real citation validator's own
verdict from inside `run_execution()`, not a second regex-based check
built for the eval suite. Re-implementing citation logic a second time
would risk the eval suite and the production validator silently drifting
apart, each "passing" by a different definition of grounded. The one
exception (`04-supplier-delay`, the workflow path, which never runs the
validator node) is hardcoded `citation_passed=True` — a structural
guarantee, not an untested assumption: that workflow's Decision Engine has
zero tools and every number is Python-computed from cited tool calls
before the LLM ever sees it (invariant 1), the same guarantee the
validator would otherwise be checking for.

**Factual accuracy is substring matching against `expected_facts`/
`forbidden_substrings`, not a second LLM-as-judge call.** A judge model
would reintroduce exactly the live-Gemini dependency this suite exists to
avoid, and would score the *scoring* non-deterministically on top of an
already-scripted answer. Substring matching is coarse but deterministic
and legible — every scenario's own `expected_facts` documents in plain
English what the substring is standing in for.

**Routing correctness is "which retrieval agents made a real tool call,"
not "which agents the Planner named."** The graph's round-1 topology
(`orchestration/graph.py`, Task 3.2) unconditionally fans out to all three
retrieval agents regardless of relevance — round 1 never gives the
Planner a chance to choose a subset. `agents_from_tool_ledger` (already
built in `evals/scenarios/base.py`, reused from the Stage 4 Task 4.5
query-coverage tests) reads which agents' tools actually landed a real
`tool_calls` row instead, the practical, honestly-implementable meaning of
routing correctness given the architecture as built — not the meaning the
word would have if the Planner selected agents up front.

**Replan correctness checks that no scenario replans when it shouldn't —
none of the ten currently scripts genuine insufficiency.** None of the
spec's ten named scenarios describes a case that needs the Planner to
judge the evidence insufficient and trigger a second, targeted retrieval
round; that exact mechanism already has its own dedicated deterministic
test (`tests/test_graph.py::test_replan_loop_triggers_a_second_targeted_retrieval_round`,
Stage 3 Task 3.3). Rather than invent an eleventh scenario the spec
doesn't ask for just to exercise it a second time, `score_replan` verifies
the honest, real thing this suite's ten scenarios *do* cover: the Planner
correctly judges each of them sufficient in one round and does not replan
needlessly. `Scenario.expect_replan` exists and is checked either way, so
a future scenario that does need it is a one-flag addition, not a new
mechanism.

**The runner builds a fresh, isolated temp-file SQLite database per
scenario**, WAL-mode with a busy timeout — not a single shared DB across
the suite, and not `:memory:`. `run_execution()`'s retrieval agents
genuinely run in parallel threads, each opening its own session and
committing independently; a shared in-memory DB doesn't tolerate that
(`tests/test_graph.py`'s own fixture comment covers why in detail — the
same constraint, not rediscovered here). Reusing one DB across scenarios
was rejected too: a leftover row from an earlier scenario silently
changing a later scenario's own "seeded state" is exactly the kind of bug
a from-scratch DB per scenario makes structurally impossible instead of
merely unlikely.

**The baseline is a single number — accuracy — recorded in a committed
`evals/baseline.json`, written only by an explicit `--record-baseline`
flag, never implicitly.** Grounding has no baseline to fall below: the
spec's own gate text treats it as an absolute (100%, always), so it's
checked directly against that constant, no file involved. Accuracy is the
one score expected to legitimately need a comparison point over time —
CLAUDE.md's honesty rule already asks that no metric appear undocumented,
so the file this compares against is checked into the repo and its
provenance (this ADR) is not implicit. A normal `make eval`/CI run only
*reads* `baseline.json`; only a human deliberately passing
`--record-baseline` can move it, so a regression can never quietly lower
its own bar by re-recording itself as the new baseline. Recorded once
this session at 100% accuracy across all ten scenarios (`git log` on
`evals/baseline.json` for the commit) — the honest number this repo will
compare every future run against, not an assumed target.

**Cost and latency are reported, not gated.** The spec lists them as
scorers but the CI-gate paragraph names only grounding and accuracy —
read literally, not expanded. `evals/run.py`'s printed summary carries
both per-scenario and totalled, so a real regression (e.g. token usage
tripling) is visible to a human reading `make eval` output, without
inventing a threshold the spec never specified and that would have to be
a fabricated number to pick.

## Why `evals/run.py` isn't unit-tested the way `evals/runner.py`/`evals/scorers.py` are

`evals/run.py` is a thin CLI wrapper — argv parsing, env-var defaults
(mirroring `tests/conftest.py`'s own `os.environ.setdefault` block, since
`Settings` has no defaults of its own and this script isn't run under
pytest), and print formatting around `evals/runner.py`'s real logic. This
matches the existing, already-precedented shape of every script under
`retailops-ai/scripts/` (`verify_graph.py`, `verify_agents.py`, ...) —
none of those are unit-tested directly either; they're verified by
actually running them as that task's own milestone check. `evals/run.py`
follows the same convention: verified by running it live
(`--record-baseline` then a normal invocation, both done for this task),
not by wrapping it in a subprocess test that would mostly just re-test
`argparse`. `evals/runner.py` and `evals/scorers.py` — the actual scoring
and aggregation logic — are fully unit-tested (`tests/test_evals.py`),
including one test that runs the real ten-scenario suite end to end
through `run_all_scenarios()`, the same call `evals/run.py` makes.

## Consequences

- **A future eleventh scenario, or a scenario needing genuine replanning,
  is additive**: a new `evals/scenarios/sNN_*.py` module with a `SCENARIO`
  object, registered in `evals/scenarios/__init__.py::ALL_SCENARIOS`. No
  runner or scorer change needed unless the new scenario needs a
  genuinely new signal none of the five existing scorers capture.
- **A real regression in grounding or accuracy fails CI immediately**,
  with the exact scenario and reason printed (`evals/run.py`'s
  per-scenario failure lines), not just a bare pass/fail.
- **Raising the accuracy baseline requires a deliberate, reviewable
  action** (`--record-baseline`, then commit the changed
  `evals/baseline.json` in its own diff) — never a side effect of an
  unrelated change.
- **This suite says nothing about whether live Gemini would actually
  produce grounded, accurate answers on a given day.** That gap is
  disclosed here and in `evals/scenarios/base.py`'s own module docstring,
  not papered over. Closing it would require either a billing-enabled
  Gemini key with reliable quota (blocking live verification since Stage
  3 Task 3.1) or accepting a non-deterministic, non-CI-safe suite —
  neither available within this build's constraints.

## What would have to be true to change this

- **A reliable, CI-safe way to call live Gemini** (a billing-enabled key,
  quota that survives concurrent calls) would justify adding a *second*,
  explicitly-labelled live suite alongside this scripted one — not
  replacing it, since the scripted suite's determinism and CI-gate role
  would still be needed even with live coverage available.
- **A stockpilot-core environment not blocked by the Application Control
  policy** would make a live-seeded-Postgres variant of "seeded database
  state" possible to evaluate on its own merits — untested territory
  today, not a design that was tried and rejected.
