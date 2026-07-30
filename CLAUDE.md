# CLAUDE.md — RetailOps AI Platform

**Read this file before every task. It is the standing contract for this repository.**

---

## 1. What this project is

A two-service retail intelligence platform, built as a flagship portfolio project for roles in software engineering, AI engineering, data engineering, and data analytics. It must read as production work, not a student demo. Correctness, honesty, and reviewability matter more than feature count.

- **`stockpilot-core/`** — headless FastAPI + PostgreSQL retail operations API with demand forecasting. No frontend.
- **`retailops-ai/`** — LangGraph multi-agent layer that reasons over StockPilot's HTTP API. Owns the only UI.

The two services communicate **only over HTTP**, with **separate databases**. This boundary is the central architectural claim of the project and may not be crossed for convenience.

## 2. Starting state

**Absolute zero.** Nothing was built before this repository. There is no legacy code, no pre-existing schema, no partially complete service. If something appears to be missing, it is missing because it has not been written yet — build it per the specification, do not assume it exists elsewhere.

## 3. The canonical specification

`docs/BUILD-SPEC.md` is the single source of truth. It is **frozen**.

- Follow it exactly. Do not redesign the architecture.
- Do not add components it does not list. Do not remove components it does list.
- If you believe something in the spec is wrong or infeasible, **stop and say so**. Do not silently deviate.
- Improvement ideas go in Appendix D of the spec as unchecked items. They are not implemented during this build.

## 4. The three invariants (never weaken)

1. **Grounding.** Every numeric claim traces to a `tool_call_id` and carries a provenance label. The Decision Engine and Report agents have **zero tools** by design. A runtime Citation Validator rejects any output containing an uncited or unlabelled number.
2. **Full trace.** Every execution persists its plan, agent steps, tool calls with raw responses, prompt version hashes, model IDs, token counts, and timings. The **serving** provider and model are recorded per call — not the configured ones — since a single execution may legitimately span providers under failover.
3. **Untrusted data.** Retrieved business data is untrusted input. It enters prompts inside a delimited envelope declaring it data, never instruction.

**Corollary — the LLM never computes a business number.** Revenue at risk, inventory cost, confidence, and priority are computed in Python from cited inputs. The LLM writes explanatory prose only.

## 5. Data provenance

Every metric carries one of four labels, threaded through schema, API responses, agent outputs, and UI:

| Label | Meaning |
|---|---|
| `observed` | Directly from the source dataset |
| `derived` | Deterministically computed via a documented method |
| `predicted` | Output of the forecasting model |
| `inferred` | Reserved; avoid |

Provenance is **never upgraded**. A value computed from a `predicted` input stays `predicted`.

## 6. Tech stack (pinned — do not substitute)

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| API | FastAPI, Uvicorn |
| ORM / migrations | SQLAlchemy 2.x, Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL 16 |
| Containers | Docker, Docker Compose |
| Agents | LangGraph, LangChain (tools/messages primitives only) |
| LLM | Groq (primary) with Gemini as fallback, both behind one provider interface |
| ML / data | scikit-learn, pandas, NumPy |
| Testing | pytest, pytest-asyncio |
| Quality | ruff, mypy |
| CI | GitHub Actions |
| Frontend | Next.js (App Router), React, TypeScript, Tailwind |

## 7. Model configuration

Exact model IDs live in **one place**: `retailops-ai/config/models.yaml`. They appear nowhere else — not in code, not in this file, not in docs. This section documents the required *shape* of that config, not its values.

```yaml
roles:
  planner:                 # strong reasoning — planning and replanning
    provider: groq
    model: <configured>
  retriever:                # fast/cheap — inventory, forecast, analytics agents
    provider: groq
    model: <configured>
  decision:                 # Decision Engine prose only
    provider: groq
    model: <configured>
fallback:
  provider: gemini
  model: <configured>       # serves all roles on failover
budgets:
  max_tool_iterations: 12
  max_tokens_per_execution: 60000
```

**Before first use of any configured ID — and again before any provider-layer change — verify every ID against its provider's live model-list endpoint for this account and region.** Do not assume names from documentation or training data; model strings are renamed and retired frequently. If a configured ID is not returned by the provider, stop and ask (rule 11) — do not substitute a guess. Known constraint: Gemini 2.5-generation models are scheduled for shutdown in October 2026 and may not be configured.

On boot, the service validates every configured model ID (all roles plus fallback) against its provider's model-list endpoint and fails fast with a clear error naming the ID and provider if any is missing.

No provider SDK may be imported outside `retailops-ai/llm/providers/`. The rest of the codebase sees one interface: `generate()`, `generate_structured()`, `stream()`.

**Why Groq is primary and Gemini is the fallback:** this is a deployment/config decision, not a reversal of the architecture — the provider abstraction is symmetric by design, which is why the swap cost nothing structurally. Practically: the configured Gemini account's quota has been observed at hard-zero, so defaulting to it would waste a guaranteed-failed attempt on every request. Groq's rate limits are generous enough for normal traffic; Gemini remains available as fallback for when Groq's own per-minute limits are hit. `LLM_PRIMARY_PROVIDER` in `.env` controls which provider is primary; the failover logic below is symmetric and does not care which slot each provider occupies.

**Failover rules:**

- Fallback fires **only** on failover-eligible error classes from the error taxonomy: quota exceeded (429), timeout after retries, provider unavailable. Never on validation failures, malformed output, or citation-validator rejections — those are not provider problems, and they follow their existing paths on whichever provider is serving.
- Failover timing differs by class: quota/429 fails over **immediately**, with no in-provider retry — a quota error is deterministic within its window, so retrying it wastes time. Timeout retries per the existing backoff policy first, then fails over.
- Failover is invisible to the caller: the request succeeds normally, with no error surfaced. The original failure and the fallback event go to structured logs, and the **serving** provider and model are recorded per call in the execution trace (invariant 2), not the configured ones. A single execution may legitimately span providers.
- Fallback logic lives entirely inside the provider layer, behind the single interface. Orchestration and agents must not know which provider answered.
- Streaming works on both providers. If the primary fails before the first content token, the stream transparently comes from the fallback. If it fails mid-stream (after content has already reached the client), the structured SSE error event is emitted and the response degrades — the stream is never silently restarted on another provider.
- If both providers fail, the caller receives a structured, user-safe degradation response/event (per the error taxonomy) — never a raw provider error, a stack trace, or a provider name. Where partial results exist (e.g. some tool calls already succeeded), the degraded response states what was retrieved rather than returning a bare failure.
- Any provider-layer change must pass the trust gate before being trusted: the Stage 5 scripted eval suite passes unchanged (zero real network calls), plus a live end-to-end smoke test through the full graph with the change in effect, plus a live failover proof.

## 8. Coding rules

- **Strict typing.** Full annotations. `mypy --strict` clean. No bare `Any` — if you genuinely need it, add a comment justifying it.
- **No hardcoded values.** URLs, keys, thresholds, model names, table names: config or env only.
- **Clean layering.** `api/ → orchestration/ → agents/ → tools/ → clients/`. No upward imports, no skipping more than one level down.
- **No placeholders.** No `TODO`, no `pass  # implement later`, no stub returning fake data. If you cannot finish something, stop and say so rather than shipping a shell.
- **No mock data presented as real.** Ever.
- **Tests with every task.** ≥80% coverage on business logic, agents, tools, and the validator.
- PEP 8 via ruff. SOLID where it earns its keep — do not add abstraction layers the spec does not call for.

## 9. Workflow protocol (this is the important section)

**One task per session turn. Never generate the whole project, a whole phase, or a whole part in one go.**

For each task:

1. Restate the task and what "done" means before writing code.
2. Implement only that task.
3. Run `ruff`, `mypy`, and `pytest`. Fix every failure.
4. Verify the task's milestone check from the spec actually passes — run it, don't assume.
5. Commit with a clear message.
6. **Report and stop.** Wait for approval before the next task.

Do not begin the next task because it seems obvious. Do not batch commits. Do not refactor code from an earlier task without being asked.

## 10. Definition of done (per task)

- [ ] `pytest` passes, no skipped tests
- [ ] `ruff` clean
- [ ] `mypy` clean
- [ ] Docker builds
- [ ] The task's milestone check verified by running it
- [ ] Endpoints appear correctly in OpenAPI/Swagger
- [ ] No TODOs, stubs, or placeholder returns
- [ ] Committed

**End of day rule:** the system must boot. Never end a day mid-refactor with nothing runnable. If a day's milestone can't be met, cut its scope rather than carrying broken code forward.

## 11. Stop and ask — do not guess

Halt and ask when:

- The spec is ambiguous or appears contradictory
- A needed StockPilot endpoint doesn't exist (log it in `docs/stockpilot-gaps.md` first)
- You'd have to fabricate, simulate, or default a business value to proceed
- A library or model ID in the stack is unavailable or deprecated
- A task can't be completed without breaking an invariant or a coding rule
- The dataset doesn't contain a field the task assumes

A blocked task reported honestly is a good outcome. A task completed by inventing something is not.

## 12. Environment

Windows 11, VS Code, Docker Desktop, Git, Python 3.11, Claude Code CLI. Prefer cross-platform commands. Use `docker compose` (v2 syntax). Make targets should work in PowerShell.

## 13. Secrets

`.env` is gitignored and never read into a commit, a log, or a chat response. `.env.example` is committed with empty values:

```
DATABASE_URL=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
RETAILOPS_DATABASE_URL=
STOCKPILOT_BASE_URL=
GEMINI_API_KEY=
GROQ_API_KEY=
LLM_PRIMARY_PROVIDER=
JWT_SECRET=
JWT_ALGORITHM=HS256
```

Never print a secret's value. Never suggest committing one. If a key is needed and missing, say which one and stop.

## 14. Dataset

Online Retail II (UCI / Kaggle, CC BY 4.0). Lives in `data/`, gitignored, fetched by `scripts/download_data.py` with a checksum so the pipeline is reproducible on a clean machine. Attribution goes in the README.

The dataset has **no** cost price, stock levels, suppliers, or categories. All four are derived by a seeded, documented script and labelled `derived` everywhere they surface. This is disclosed plainly in the README, not buried.

## 15. Git

Single repository, `main` branch, MIT licence. Commit after every task. Tag milestones: `day-0-bootstrap`, `stockpilot-core-complete`, `retailops-phase-1`, `retailops-phase-2`, `v1.0`.

Commit messages: what changed and why, imperative mood, one line plus body if needed. No "wip", no "fixes", no emoji.

## 16. Honesty

No metric appears in any README, doc, or commit message unless it was measured — and the doc states how it was measured. Every limitation gets written down. If the forecasting model loses to the seasonal-naive baseline, ship the baseline and report both scores.

This rule is not negotiable. The entire value of this project rests on it being true.