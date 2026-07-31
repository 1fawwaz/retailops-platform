# TODO — stale `docs/BUILD-SPEC.md` legacy references

**Context:** `docs/BUILD-SPEC.md` used to hold the RetailOps AI / StockPilot Core build specification (Stage 0–7, JWT auth model, eval scenarios, provider fallback, etc.). That content has since been overwritten — the file (now renamed `docs/BUILD.md`, see the rename that added this TODO) currently holds the StockPilot Frontend (ERP) roadmap instead. The 8 references below were written when the old content was still there; they quote or describe things that are no longer at that path. Renaming the file would only make them cite the wrong document under a different name — the underlying problem is the citation content, not the filename.

**None of these were changed as part of the `BUILD-SPEC.md` → `BUILD.md` rename.** Each needs individual review: some may just need the quoted claim rewritten in the reviewer's own words (removing the citation); some may need a real replacement source (e.g. `docs/adr/` for a decision already made, or nothing at all if the surrounding prose stands on its own without the citation); none should be resolved by guessing what the old spec said.

**The original content is not lost — no guessing required.** The pre-overwrite `docs/BUILD-SPEC.md` (860 lines, "RetailOps AI — An Autonomous Agent for Retail Operations — Complete Build Specification") is still recoverable from git history, since the overwrite to ERP-roadmap content was never itself committed before this rename:

```
git show 22096ac:docs/BUILD-SPEC.md
```

(`22096ac` was `HEAD` at the time of this TODO — confirm it's still reachable, or `git log --all --oneline -- docs/BUILD-SPEC.md` if history has moved on.) Every one of the 8 citations below can be checked against this exact original text rather than rewritten from memory or inference.

## The 8 references

1. **`README.md:274`** — "The target architecture ... is specified in `docs/BUILD-SPEC.md`'s Stage 7." Describes the deployment target (Railway/Render, Vercel, seeded demo DB, CI gates). Deployment has since actually happened (see this session's Railway/Vercel work) — this whole paragraph is likely stale on its own merits, not just the citation.

2. **`retailops-ai/auth.py:3`** — `Per docs/BUILD-SPEC.md's own words -- "JWT integrated with StockPilot's auth, no second user system"`. Describes a real, still-true architectural fact (no second user system, shared JWT secret) — the quoted attribution is what's stale, not the fact itself. Likely fix: state it as the module's own design rationale, drop the citation.

3. **`retailops-ai/api/errors.py:6`** — `per docs/BUILD-SPEC.md's Stage 6 backend-hardening bullet`, describing the error-taxonomy design ("user-safe messages and full detail in logs only"). Same shape as #2 — the design is real and current, the citation isn't.

4. **`retailops-ai/evals/scorers.py:59`** — `None of the ten named scenarios in docs/BUILD-SPEC.md's own list call for genuine insufficiency-driven replanning`. This one actually depends on enumerable content (the ten scenarios) that no longer exists at the cited path — needs the actual scenario list cross-checked against `evals/scenarios/` directly rather than the stale doc.

5. **`retailops-ai/frontend/components/ProvenanceDrawer.tsx:16`** — `(BUILD-SPEC's own F4 wording)`, describing the "provable in one click" design goal. Same shape as #2/#3.

6. **`docs/adr/006-evaluation-strategy.md:9`** — `docs/BUILD-SPEC.md's Stage 5 asks for ten named scenarios...`. An ADR's Context section describing what prompted the decision — arguably fine to leave as a historical record of what was asked at the time (ADRs are append-only by convention), but flag for a maintainer decision rather than assuming.

7. **`docs/adr/007-multi-provider-fallback.md:9`** — `docs/BUILD-SPEC.md's Task 6.4 asks for a second LLM provider (Groq)...`. Same shape as #6 — historical ADR context.

8. **`stockpilot-core/README.md:4`** — `See docs/BUILD-SPEC.md for the full specification`. A direct pointer for a reader — currently sends them to the ERP frontend roadmap instead of anything about StockPilot Core. Highest-priority fix of the 8: this one actively misleads a reader today, not just an internal comment.

## Suggested triage order

Highest reader-facing impact first: **#8, #1** (READMEs, direct pointers) → **#4** (only one with checkable factual content) → **#2, #3, #5** (design-rationale comments, low risk but easy cleanup) → **#6, #7** (ADR historical context, may not need changing at all — ADRs document a point in time).
