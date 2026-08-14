# ADR 004: Every model-output figure is grounded in a retrieved tool value and validated before serving

## Status

Accepted — implemented across the retailops-ai pipeline (orchestration/graph.py,
orchestration/validator.py, orchestration/workflows.py) and documented here to
close the ADR numbering gap (004/005 were never written; 005's subject, the
provider-abstraction layer, is already covered by ADR 007).

## Context

The product's core claim — "nothing here is fabricated" — is only true if a
generated answer can be shown to rest on real business data retrieved at
execution time, not on what the model happened to know. The LLM is fine to
summarize; it must not be allowed to invent numbers, priorities, or
confidence scores that have no traceable origin in a tool result.

Two concrete failure modes motivated a structural (not prompt-only) guard:

1. **The hollow answer.** If a model is asked to write a final answer without
   the evidence it needs, it will either refuse or fill gaps from memory. A
   prompt instruction alone is not enough — the agent can be given a role it
   doesn't have the inputs to perform (the Decision Engine was, until the
   dual-role fix), and no amount of prompting fixes a missing input contract.
2. **Plausible-but-wrong figures.** Even with evidence in context, a model
   can restate a number slightly differently, attach a confidence score no
   tool produced, or label a retrieved value as something stronger than its
   provenance allows. These are subtle and would pass a human skim.

## Decision

Three mechanisms, all enforced in code, make grounding a construction-time
property of every served answer:

- **Grounded retrieval.** Each agent that can call tools must bring back the
  *raw* tool value (bounded, `EVIDENCE_SECTION_CHARS`), so the evidence a
  downstream agent reasons over is a verbatim tool result, not a model's
  paraphrase of it. A "grounded" Replan (see the Stage-3 reliability work)
  only routes to agents there is real evidence to support; the loop is capped
  so it can't run forever on absent data.
- **Verbatim-figure contract.** A model asked to write figures into a final
  answer is told it must restate them exactly as they appear in the evidence
  (`prompts/decision/v1.md`'s dual-role contract), and that it must never
  self-assign a confidence/priority/risk score or state a number that is not
  verbatim in the input.
- **A validator that rejects ungrounded output.** `orchestration/validator.py
  ::validate_citations` runs before an answer is served: every numeric token
  in the draft must resolve to a grounded tool value (via a `tool_call_id` /
  field / provenance), and every citation must carry its provenance. If the
  validator fails, the pipeline re-runs the final-answer step boundedly; if
  it cannot be satisfied, the served answer says plainly what is missing
  rather than papering over it.

A decision-log (what the agent inferred and why) is kept, but it is never
allowed to present inference as an observed/derived/predicted figure.

## Why a validator, not just a prompt

Prompts are advisory; a validator is a gate. The failure mode being defended
against is precisely the one where the model, however well-prompted, produced
a superficially correct answer that a reader would accept. A deterministic
check that every number in the draft has a `tool_call_id`/field/provenance is
the difference between "we hope the model grounded itself" and "the pipeline
will not serve output that isn't groundable." It also gives the live
verification loop (`citation_attempts`, `citation_check`) a concrete,
grep-able signal per execution instead of a human re-reading prose.

## Consequences

- **Any new response surface that emits figures inherits the validation
  gate** — a final answer, recommendation, or report that carries a number
  must either satisfy `validate_citations` or name its gap. Skipping the
  validator is not an option for a figure-carrying path.
- **Evidence must be bounded and retained.** Grounding only works if the raw
  tool value survives into the reasoning context; trimming it too hard would
  silently re-open the hollow-answer hole. The bound is a deliberate
  trade-off between grounding and context cost.
- **Exact-figure restatement is a hard rule for downstream writers**, which
  reads more constrained than natural prose — accepted, because the product's
  integrity claim is worth the slightly stiffer language.

## What would have to be true to change this

- **A consumer that is willing to accept ungrounded, best-effort prose** for
  a specific surface (e.g. an internal-only chat with no correctness bar)
  could opt that surface out of the validator — but no such surface exists
  today, and the default stays "validated."
- **A downstream figure that is genuinely not traceable to a single tool
  value** (e.g. an aggregation the model performs across two retrieved sets)
  would need the validator extended to accept a *set* of grounding
  tool_call_ids rather than relaxing grounding itself.