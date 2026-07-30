# RetailOps AI
## An Autonomous Agent for Retail Operations — Complete Build Specification

**Starting point: nothing exists.** No repository, no database, no API, no prior work. Every line is written during this build.

**Timeline:** 18 working days.

---

# I. What you are building

An autonomous AI agent that operates a retail business. Given a goal — *"maintain healthy inventory"* — or a question — *"why did profit fall last month?"* — it plans its own approach, gathers the evidence it needs, decides whether that evidence is sufficient, gathers more if it isn't, quantifies the business impact of each possible action, and produces ranked recommendations where every single number can be traced back to its source.

It is not a chatbot with a database behind it. The distinction is that it **decides what to do next based on what it has already learned.**

## The agent frame

Every serious agent system has six parts. Naming them explicitly is how you keep the build coherent, and it is also how you explain the project in an interview.

| Component | In this project |
|---|---|
| **Environment** | StockPilot Core — a headless retail operations API the agent perceives and reasons over |
| **Perception** | A typed tool layer; the agent's only channel to the environment |
| **Policy** | Planner agent — decomposes goals, routes work, decides when it has enough |
| **Memory** | Conversation, execution, and rolling task memory in Postgres |
| **Judgment** | Decision Engine — ranks actions by computed business impact |
| **Guardrails** | Citation validator, iteration caps, untrusted-data envelopes, refusal paths |

You are building all six. Stages II–IX below follow that order, because each depends on the one before it.

## What makes it genuinely agentic

Keep this table. It becomes a README section and an interview answer.

| Property | Implementation |
|---|---|
| Goal decomposition | Planner turns a goal into an execution plan |
| Autonomous tool use | Agents select their own calls within role-scoped allow-lists |
| **Reflection and replanning** | After seeing data, the Planner judges sufficiency and can retrieve again |
| Multi-agent delegation | Six specialised agents, each with a bounded remit |
| Persistent memory | Conversation, execution, and task memory across turns |
| Self-correction | Validator failure triggers regeneration, then honest refusal |
| Bounded autonomy | Iteration caps, token budgets, circuit breakers |
| Adversarial robustness | Untrusted-data envelopes; injection case in the eval suite |
| Explicit uncertainty | Refuses when evidence is insufficient rather than guessing |
| Infrastructure resilience | Multi-provider LLM failover on infrastructure-class errors, invisible to the caller |

Most projects labelled "agentic" are fixed chains with an LLM at each node. **The replan loop is the dividing line.** It is not optional here.

## The four things that must never be cut

1. **Citation validator** — every number traces to a tool call
2. **Replan loop** — the agent reconsiders after seeing data
3. **Scenario evaluation suite** — the only honest source of metrics
4. **Live execution graph with citation drill-down** — makes reasoning visible

If you fall behind, cut features. Never these.

## The three invariants

**1. Grounding.** Every numeric claim traces to a `tool_call_id` and carries a provenance label. Enforced three ways: *structurally* (the Decision Engine and Report agents have zero tools, so they cannot fetch a number to invent one around), *at runtime* (a validator node rejects uncited or unlabelled numbers), and *by test* (a unit test proves the validator catches a deliberately fabricated figure).

**2. Full trace.** Every execution persists plan, agent steps, tool calls with raw responses, prompt version hashes, model IDs, token counts, timings. Under multi-provider failover, the trace records the **serving** provider and model per call, not the configured ones — a single execution may legitimately span providers.

**3. Untrusted data.** Product names and supplier notes are untrusted input. They enter prompts inside a delimited envelope declaring the content data, never instruction.

**Corollary the whole project rests on: the LLM never computes a business number.** It explains numbers that Python computed from cited inputs.

## Data provenance

Every metric carries one of four labels, threaded through schema, API, agent output, and UI:

| Label | Meaning | Example |
|---|---|---|
| `observed` | Straight from the source dataset | Revenue, units sold, dates |
| `derived` | Deterministically computed by a documented method | Stock, cost, category, reorder point |
| `predicted` | Forecasting model output | Demand forecast, days of cover |
| `inferred` | Reserved — avoid | — |

Provenance is **never upgraded**. A value computed from a `predicted` input stays `predicted`.

This is what makes a partly-synthetic dataset honest rather than misleading. It becomes a visible badge on every figure in the UI.

---

# II. Stage 0 — Foundation
**Day 0.** Get a running skeleton before writing any real code.

```
Bootstrap a new project from nothing. No code, repository, or database
exists yet. Do not assume anything is already present.

Create:

  retailops-platform/
    stockpilot-core/          # the agent's environment
      api/  services/  models/  schemas/  ml/  scripts/  tests/
      alembic/  Dockerfile  pyproject.toml  .env.example
    retailops-ai/             # the agent itself
      api/  orchestration/  agents/  tools/  clients/  llm/providers/
      prompts/  evals/  tests/  config/
      alembic/  Dockerfile  pyproject.toml  .env.example
    contracts/stockpilot-api/{schemas,versions}/
    docs/adr/
    data/                     # gitignored
    docker-compose.yml  Makefile  .gitignore  README.md  CLAUDE.md

TASK 0.1 — Repo and tooling
  git init. Single repo, two services: the boundary is enforced by HTTP,
  not by repository separation.
  .gitignore: .env, data/, __pycache__, .venv, node_modules
  Python 3.11 venv per service, pinned deps in pyproject.toml.
  Pre-commit: ruff, mypy.
  Makefile targets: setup, db-up, db-down, ingest, test, eval,
  run-core, run-agents.
  MIT licence. Commit.

TASK 0.2 — Databases
  docker-compose with TWO Postgres 16 databases: stockpilot, retailops.
  Separate databases, not schemas — the service boundary must be real
  and impossible to cross by accident.
  Alembic initialised in both with an empty baseline migration.
  MILESTONE: both accept connections, both migrate up and down clean.

TASK 0.3 — Dataset
  Online Retail II (UCI / Kaggle, CC BY 4.0) into data/, gitignored.
  scripts/download_data.py fetches it and verifies a checksum so the
  pipeline is reproducible on a clean machine.
  Profile it and REPORT BEFORE PROCEEDING: row count, columns and
  dtypes, date range, distinct StockCodes, null counts per column,
  cancellation invoice count, non-positive quantity count.

TASK 0.4 — Skeletons that run
  Both services boot, GET /health returns 200. Both Dockerfiles build.
  make run-core and make run-agents work. One passing test each.
  GitHub Actions: install, ruff, mypy, pytest on push.

TASK 0.5 — ADR 001
  docs/adr/001-agent-environment-boundary.md — why the environment is a
  separate service, why HTTP rather than a shared library, what would
  have to be true to merge them. Write it before code shapes the
  decision.

  Commit. Tag: stage-0-foundation

STOP. Report the dataset profile and confirm both services boot.
```

---

# III. Stage 1 — The Environment
**Days 1–5.** The world the agent will act in. Build it well: an agent reasoning over a shallow environment produces shallow reasoning.

**Send one task per message.** Do not paste this stage as a single block — large batches produce code you cannot review and commits you cannot bisect.

```
Build StockPilot Core: a headless FastAPI + PostgreSQL retail operations
API. This is the environment the agent will perceive and reason over.

STARTING STATE: only the Stage 0 skeleton exists — empty folders, a
booting /health endpoint, an empty database, the raw dataset in data/.
No schema, no endpoints, no models. Build everything from scratch.

HEADLESS. No frontend, no dashboard, no templates. Its only consumer is
the agent service. Ship OpenAPI docs and tests, nothing else.

TECH: Python 3.11, FastAPI, PostgreSQL 16, SQLAlchemy 2.x, Alembic,
Pydantic v2, pandas, NumPy, scikit-learn, pytest. All config via env
vars in settings.py. No hardcoded values anywhere.

DATA: Online Retail II. ~1M transactions, Dec 2009 – Dec 2011,
5,243 products. Columns: Invoice, StockCode, Description, Quantity,
InvoiceDate, Price, Customer ID, Country.

The dataset has NO cost price, stock levels, suppliers, or categories.
You will derive all four. Every derived field must be produced by a
seeded deterministic script, documented in docs/data-derivation.md,
and labelled provenance="derived" wherever it surfaces.
Never present derived data as observed.

PROVENANCE CONTRACT — every response carries:
  "_provenance": {"revenue": "observed", "current_stock": "derived", ...}
  "_derivation_ref": {"current_stock": "data-derivation.md#stock-ledger"}
Implement as a reusable Pydantic base model so it cannot be forgotten.
Add a test that FAILS if any endpoint returns a numeric field with no
provenance entry.

TASK 1 — Schema and migrations                        [Day 2]
  products, categories, suppliers, sales_transactions, stock_levels,
  stock_movements, purchase_orders, users.
  Every derived column carries a SQL comment naming its derivation
  section. Index for the Task 4 query patterns.
  MILESTONE: migrations apply up and down cleanly on an empty database.

TASK 2 — Auth and basic CRUD                          [Day 2]
  JWT, register/login, hashed passwords, protected routes, one seeded
  read-only demo user. Minimal CRUD on products and suppliers so the
  schema is exercisable before real data exists.
  MILESTONE: create and read a product through Swagger with auth
  enforced.

TASK 3 — ETL and derivations                          [Day 3]
  Data only. No new endpoints in this task.
  a. Clean: drop cancellations (Invoice starts 'C'), non-positive
     quantities, null StockCodes, test rows. Report counts per step.
  b. Product master from distinct StockCode + Description.
  c. Categories: TF-IDF + KMeans over descriptions into 8–12 clusters,
     hand-labelled, mapping file committed for reproducibility.
  d. Cost price: median unit price per SKU × margin_factor, sampled
     per category from a seeded distribution (0.55–0.80).
  e. Suppliers: 12–20, one per SKU, each with lead_time_days (3–21)
     and reliability_score. Seeded.
  f. Stock ledger: replay transactions chronologically for daily
     stock-on-hand per SKU. Seed an opening balance; inject simulated
     purchase orders where stock would go negative.
  g. reorder_point and safety_stock from observed demand variability
     and supplier lead time. Formula documented.
  Commit after EACH sub-step a–g. Seven commits, not one.
  MILESTONE: database fully populated, `make ingest` reproducible from
  empty on a clean machine, row counts and provenance summary reported.

TASK 4 — Inventory and analytics endpoints            [Day 4]
  GET /inventory/stock              (category, low_stock, search)
  GET /inventory/low-stock
  GET /inventory/dead-stock         (no movement in N days)
  GET /inventory/slow-movers
  GET /inventory/valuation          (capital tied up, by category)
  GET /products/{sku}               (detail + 90-day movement history)
  GET /suppliers/{id}               (lead time, reliability, SKUs)
  GET /analytics/revenue            (group_by=day|week|month|category)
  GET /analytics/profit             (revenue, cost, gross profit, margin)
  GET /analytics/turnover
  GET /analytics/abc
  GET /analytics/top-products       (metric=revenue|margin|units)
  GET /analytics/bottom-products
  GET /analytics/period-comparison  (two periods, metrics + deltas)

  Aggregation in SQL, not Python loops. Typed Pydantic responses.
  Consistent pagination and error shape. Provenance on every response.
  Commit after each group.

TASK 5 — Forecasting                                  [Day 5]
  POST /forecast/demand  {skus: [...], horizon_days: int}
  Per SKU: predicted daily demand, confidence interval, model used,
  training window, data_quality flag for thin-history SKUs.
  All provenance="predicted".

  Baseline first: seasonal naive + moving average. Then a
  gradient-boosted model on lag/rolling/calendar features — KEEP IT
  ONLY IF it beats the baseline on a held-out period. Report both
  scores honestly. If the GBM loses, ship the baseline and say so in
  the README.

  GET /forecast/accuracy — backtest MAE/MAPE per model.

TASK 6 — Contracts and handoff                        [Day 5]
  Export JSON Schema per endpoint to contracts/stockpilot-api/schemas/
  and freeze a copy as versions/v1.json. Add a contract test that fails
  if any response stops matching its frozen schema — this is what stops
  the agent silently breaking when the environment changes.

  docs/api-contract.md, docs/data-derivation.md, demo seed script,
  OpenAPI examples on every endpoint, >=80% coverage on analytics and
  forecast logic, README with an honest scope and data statement.

  ADRs: 002-postgresql.md, 003-provenance-model.md

  Tag: stage-1-environment

DO NOT BUILD: frontend, dashboards, PO creation flows, customer
management, multi-store, reporting UI. The agent service provides all
user-facing surface.
```

---

# IV. Stage 2 — Perception
**Days 6–7.** The agent's senses: how it reaches the environment, and how every observation gets recorded.

```
Build the agent service foundation and its perception layer.

SEPARATE SERVICE. Talks to StockPilot ONLY over HTTP. Owns its own
Postgres database containing ONLY: conversations, messages, executions,
agent_steps, tool_calls, reports, recommendations, eval_runs.

NEVER: query StockPilot's database directly; re-implement inventory,
analytics, or forecasting logic; let an LLM compute a business number.

TECH: FastAPI, LangGraph, LangChain (tools and messages primitives
only), PostgreSQL, SQLAlchemy 2.x, Pydantic v2, LLM providers behind a
single provider interface, pytest.

ARCHITECTURE RULES
  Layering: api/ → orchestration/ → agents/ → tools/ → clients/.
  No upward imports. No skipping more than one level down.
  No model name in code OR docs — config/models.yaml is the only place
    model IDs appear, mapping roles to {provider, model}.
  No provider SDK outside llm/providers/. One interface:
    generate(), generate_structured(), stream().
  Prompts are versioned files: prompts/<agent>/vN.md, loaded by hash,
    hash recorded per execution. Never inline prompt strings.
  Tool LLM-facing schemas generated from Pydantic models, never
    hand-written.

TASK 2.1 — Scaffold and state
  Layered structure, settings.py, Alembic, Dockerfile, .env.example.
  Structured JSON logging with execution_id on every line.
  Schema for the memory tables listed above.

TASK 2.2 — Environment client
  clients/stockpilot.py — the ONLY module that speaks to StockPilot.
  Typed, retries with backoff, timeouts, circuit breaker.
  Models generated from contracts/stockpilot-api/versions/v1.json.
  MILESTONE: a live call to every StockPilot endpoint succeeds and
  returns a validated typed object.

TASK 2.3 — Tool layer
  Wrap each client method as a LangGraph tool with a strict input
  schema and a docstring the model can reason over.
  Every invocation writes a tool_calls row: execution_id, tool_call_id,
  args, raw response, provenance map, latency, status.
  MILESTONE: tools callable in isolation; every call leaves a row.

TASK 2.4 — Untrusted-data envelopes
  All retrieved business content enters prompts inside a delimited
  envelope declaring it data, never instruction. Unit test with an
  injected instruction inside a product description.

TASK 2.5 — Model configuration
  config/models.yaml — the ONLY place model IDs appear:
    roles:
      planner:                 # strong reasoning — planning, replanning
        provider: <configured>
        model: <configured>
      retriever:               # fast, cheap — retrieval agents
        provider: <configured>
        model: <configured>
      decision:                # strong reasoning — Decision Engine prose
        provider: <configured>
        model: <configured>
    budgets:
      max_tool_iterations: 12
      max_tokens_per_execution: 60000
  (A fallback block and a live-verified default provider ordering are
  added in Tasks 6.4–6.5 — see Stage 6.)
  Verify every configured ID against the provider's model-list endpoint
  before first use. Do not hardcode any ID elsewhere — not in code,
  not in this spec, not in CLAUDE.md.

  Tag: stage-2-perception
```

---

# V. Stage 3 — Reasoning
**Days 8–9.** The core of the project. This is where it becomes an agent rather than a pipeline.

```
Build the agent's reasoning loop.

TASK 3.1 — The six agents
  Create each with a versioned prompt file and a tool allow-list:

    Planner          decompose, route, judge sufficiency   [NO TOOLS]
    Inventory Agent  stock state                    [inventory tools]
    Forecast Agent   demand predictions              [forecast tools]
    Analytics Agent  financial and BI aggregates    [analytics tools]
    Report Agent     assemble typed report objects        [NO TOOLS]
    Decision Engine  rank, quantify, explain              [NO TOOLS]

  The tool-less agents are tool-less BY DESIGN. They can only reason
  over what the retrieval agents fetched, so they are structurally
  incapable of inventing a number. Do not give them tools "for
  convenience" — this is invariant 1.

TASK 3.2 — The graph
  LangGraph: entry → Planner → PARALLEL fan-out to retrieval agents →
  Report → Decision Engine → Validator → end.
  Typed state object carrying execution_id, query, plan, agent results,
  tool ledger, provenance map, errors, budgets.
  MILESTONE: retrieval agents provably run concurrently — show timings.

TASK 3.3 — THE REPLAN LOOP  ← the heart of the project
  After retrieval agents return, control goes BACK to the Planner,
  which answers one question: is this evidence sufficient to answer
  the goal?
    Sufficient   → proceed to Report
    Insufficient → issue a second, targeted retrieval round
  Bounded by max_tool_iterations.

  The Planner's sufficiency judgement is a FIRST-CLASS ARTIFACT, not
  an internal detail. Persist it to agent_steps as a structured record:
    {sufficient: false,
     missing: ["supplier lead time for 3 SKUs"],
     next_action: "forecast agent, targeted retrieval",
     iteration: 1}
  This is what the execution graph will render, and it is the single
  moment where a viewer sees the system reasoning rather than executing.

  A one-pass pipeline does NOT satisfy this task. Verification: at
  least one query must demonstrably trigger a second round, with the
  reasoning visible in the trace.

TASK 3.4 — Memory
  Conversation history per thread, execution history, rolling task
  memory passed to the Planner. Postgres, never in-process.
  MILESTONE: a follow-up question that depends on the previous turn
  answers correctly.

TASK 3.5 — Citation validator
  A graph node before every response. Extract numeric tokens from the
  draft; confirm each appears in a recorded tool response for this
  execution WITH its provenance carried through.
    Fail once  → regenerate with offending values stripped
    Fail twice → return INSUFFICIENT_DATA stating what is missing
  Two required tests: rejects a fabricated figure; rejects a real
  number presented without its provenance label. Neither may be
  skipped, ever.

TASK 3.6 — API and degradation
  POST /agent/query            → answer + execution trace
  GET  /agent/execution/{id}   → full trace
  GET  /health, /health/deep

  Failure behaviour:
    StockPilot unreachable → typed ToolUnavailable, graph degrades,
      the answer names the missing data explicitly
    Empty result set → a valid answer, not an error
    LLM timeout → backoff ×3, then a partial answer flagged incomplete
    Iteration cap hit → best effort, flagged as truncated reasoning
    Missing business data → NEVER substitute a default; state the gap

ACCEPTANCE FOR STAGE 3
  "What should I reorder today?" produces a real plan, ≥2 real tool
  calls, and a fully cited answer with provenance labels.
  At least one query triggers the replan loop with visible reasoning.
  Retrieval agents provably run in parallel.
  Killing StockPilot yields a graceful degraded answer, not a 500.
  Coverage ≥80% on agents, tools, orchestration, validator.

  ADRs: 004-grounding.md, 005-provider-abstraction.md
  Tag: stage-3-reasoning
```

---

# VI. Stage 4 — Judgment
**Days 10–11.** An agent that retrieves is useful. An agent that *ranks actions by consequence* is what a business would pay for.

```
Build the agent's judgment layer.

TASK 4.1 — Retrieval agent competence
  Inventory: stock by SKU/category, low stock vs reorder point,
    stockout-risk ranking, dead stock, slow movers. Thresholds come
    from config or StockPilot — NEVER chosen by the LLM.
  Forecast: forecasts with confidence intervals as returned;
    days_of_cover = stock / forecast daily demand; reorder timing from
    lead time + safety stock. Surface data_quality flags, never hide
    them.
  Analytics: revenue, gross profit, margin, inventory value, turnover,
    ABC, category performance, top/bottom performers, period deltas.

TASK 4.2 — Report Agent
  Pydantic schemas (ReorderReport, HealthReport, PerformanceReport)
  rendered to markdown. Structured objects, not LLM prose.

TASK 4.3 — DECISION ENGINE
  Its job is to rank and quantify, not narrate. Every recommendation:

    action            str
    priority          critical | high | medium | low
    reason            str    ← LLM writes this
    revenue_at_risk   Money  provenance: predicted
    inventory_cost    Money  provenance: derived
    confidence        float  provenance: derived
    risk_if_ignored   str    ← LLM writes this
    evidence          list[tool_call_id]

  ALL FOUR NUMBERS ARE COMPUTED IN PYTHON. The LLM never produces them.

    revenue_at_risk = forecast_daily_demand × unit_price
                      × projected_stockout_days
    inventory_cost  = recommended_order_qty × unit_cost
    confidence      = f(forecast CI width, data_quality flag,
                        history length) — documented formula in
                        services/confidence.py, unit tested
    priority        = rules-based tiering on revenue_at_risk and
                      days_to_stockout, thresholds in config

  Note revenue_at_risk is provenance="predicted", not "derived" — it
  descends from a forecast. Provenance never upgrades.

  REQUIRED TEST: run the Decision Engine twice at temperature > 0 and
  assert every numeric field is identical. If any value moves, an LLM
  is computing it. Fix it. "Confidence: 91%" from a language model is
  exactly the fabrication this project exists to prevent, and a
  citation validator alone will not catch it.

  Rank by revenue_at_risk. Persist to `recommendations` with
  status=pending.
  POST /recommendations/{id}/action {status: accepted|rejected, note}
  records the user's decision and timestamp.
  This is a decision LOG. Do not compute learning from it, do not claim
  the system improves from it, do not derive an accuracy score from it.

TASK 4.4 — Goal-driven workflows
  POST /workflow/inventory-health/run
    Goal: maintain healthy inventory. Retrieval → forecast → reorder
    set → quantities → ranked recommendations with full impact fields.
  POST /workflow/business-review/run
    Revenue, profit, margin trend vs prior period, inventory value,
    dead-stock capital, top/bottom 10, category performance, plus an
    explanation of the single largest change and its driver.

  BACKTEST MODE: both accept an as_of_date. When set, every report is
  stamped in its header AND in the API response: "Historical simulation
  as of <date>. Not live monitoring." The UI renders this prominently.
  Never present a backtest as current business state.

  Persist every run with inputs, outputs, duration, cost, tool ledger.
  GET /report/{id} + markdown export.

TASK 4.5 — Query coverage. All must work:
  - Which products should I reorder today?
  - Why did profit fall last month?
  - Which products are dead stock and how much capital is in them?
  - Which categories perform best, and why?
  - Which SKUs are at stockout risk this week?
  - What changed most vs last month?
  - "How's business?" → must clarify OR state its interpretation
  - a question needing absent data → must refuse cleanly

  Tag: stage-4-judgment
```

---

# VII. Stage 5 — Robustness
**Day 12.** Where you find out whether any of this actually works.

```
Build the scenario evaluation suite. evals/scenarios/, ten scenarios,
each with a seeded database state, a question, expected facts, and an
expected agent path.

  01-normal-operations      baseline correctness
  02-seasonal-demand-spike  Nov/Dec surge — must not read seasonality
                            as a trend break
  03-new-sku-no-history     must surface data_quality, lower confidence,
                            and say so
  04-supplier-delay         extended lead time must change reorder
                            timing and priority
  05-empty-inventory        zero stock across a category
  06-missing-forecast       forecast endpoint returns nothing for the
                            requested SKUs
  07-api-unavailable        environment down → graceful degradation
  08-prompt-injection       injected instruction inside a product
                            description → must not comply
  09-ambiguous-question     must clarify or state its interpretation
  10-unanswerable-question  must refuse cleanly, no guessing

SCORERS
  grounding            % numeric claims cited AND correct AND labelled
  factual accuracy     vs expected values
  routing correctness  did the Planner choose the right agents
  replan correctness   did it replan when evidence was insufficient,
                       and NOT replan when it was sufficient
  refusal correctness  did it decline when it should have
  cost                 tokens per execution
  latency              wall clock per execution

`make eval` runs the suite. Record the baseline.
CI GATE: grounding must be 100%. Accuracy may not fall below baseline.

NOTE: the suite uses scripted LLM behaviour with zero real network
calls. It measures the system around the model, not provider quality.
This is stated plainly in the README.

These numbers are the only honest metrics you will put on a resume.

  ADR: 006-evaluation-strategy.md
  Tag: stage-5-robustness
```

---

# VIII. Stage 6 — Transparency
**Days 13–15.** Reasoning nobody can see is reasoning nobody will believe.

```
STATUS: backend hardening 6.1–6.5 SHIPPED.
Frontend NOT started — begins next.

BACKEND HARDENING

  ✔ 6.1  JWT integrated with StockPilot's auth — no second user
         system. SHIPPED. RetailOps validates StockPilot-issued
         JWTs; /agent/*, /recommendations/*, /workflow/*, /report/*
         protected; health endpoints public. Invalid and tampered
         tokens rejected. JWT_SECRET mismatch bug found and fixed.

  ✔ 6.2  SSE streaming on /agent/query — tokens, execution
         progress, replan and completion events. SHIPPED. Strictly
         opt-in via Accept: text/event-stream; JSON path
         byte-for-byte unchanged. Verified over real HTTP with real
         auth.

  ✔ 6.3  ERROR TAXONOMY + RATE LIMITING + DEGRADATION. SHIPPED
         (commit 9971548). Typed error taxonomy with user-safe
         messages, full detail in logs only; classifies Gemini 429
         quota, timeout, StockPilot unavailable, upstream failures,
         and defines which classes are failover-eligible. JSON
         endpoints return structured errors; SSE emits structured
         error events. Per-user rate limiting on LLM-cost routes;
         request timeouts. Known limitation, documented:
         execution_id log correlation is fixed on the blocking path
         only; the streaming path retains a contextvars limitation.

  ✔ 6.4  PROVIDER ABSTRACTION + GROQ FALLBACK. SHIPPED
         (commit b9451e1). LLMProvider interface in llm/providers/
         exposing generate(), generate_structured(), stream().
         GeminiProvider (refactor, behaviour identical) and
         GroqProvider (new); orchestration, agents, and tools
         unchanged in calling interface and control flow (the only
         extension outside the provider layer is persistence of the
         serving provider/model, via an Alembic migration — see
         ADR 007 for why this doesn't violate provider isolation).
         FallbackProvider chain: primary → fallback → graceful
         degradation, entirely inside the provider layer. Failover
         fires ONLY on failover-eligible classes from the 6.3
         taxonomy — verified NOT to fire on citation-validator
         rejections, schema validation failures, or malformed
         structured output (tests assert zero calls reach the
         fallback provider in these cases). Quota/429 fails over
         IMMEDIATELY with no in-provider retry; timeout retries per
         existing backoff first, then fails over. Both providers
         down → 6.3's degradation, never a 500. Streaming parity
         confirmed: pre-first-content-token failure switches
         providers transparently; mid-stream failure emits the
         structured SSE error event and degrades, never silently
         restarting the stream. Startup validation checks every
         configured model ID against its provider's live
         model-list endpoint. 301 tests, 99% coverage on
         llm/providers/. ADR 007 documents two real findings: a
         Groq tool-choice reliability issue and a cross-provider
         thought_signature pin fix.
         TRUST GATE PASSED: scripted eval suite unchanged (zero
         network calls); live end-to-end run through the full graph
         with Groq serving, citation validator passed first try;
         live failover proof with Gemini's known hard-zero quota —
         all 7 agent_steps served by Groq, event logged, serving
         model recorded in trace.

  ✔ 6.5  SWAP PRIMARY/FALLBACK PROVIDER ORDER. SHIPPED
         (commit — see git log for this task's own commit hash).
         Groq is now the configured PRIMARY (all three roles share
         openai/gpt-oss-120b); Gemini (gemini-3.5-flash) is the
         FALLBACK. Deployment/config decision, not an architecture
         change, exactly as scoped: config/models.yaml's role and
         fallback blocks swapped, Settings.llm_primary_provider's
         default flipped to "groq", LLM_PRIMARY_PROVIDER=groq set in
         .env by the user per the standing rule against Claude
         editing that file. Failover-eligibility logic,
         immediate-429/retry-timeout distinction, and streaming
         parity from 6.4 are UNCHANGED, as required — only which
         provider occupies which slot changed.

         Startup model-list validation re-run live for both
         providers in the new arrangement: openai/gpt-oss-120b
         resolves on Groq's list, gemini-3.5-flash resolves on
         Gemini's — confirmed the fallback path's own model is real
         even though it's no longer primary.

         A third real bug found via live testing, same category as
         6.4's two: Groq signals "request exceeds this account's
         per-minute token budget" as an uncaught HTTP 413
         (groq.APIStatusError, not groq.RateLimitError, which this
         SDK reserves for 429 only) — previously invisible since
         Groq only ever received post-failover traffic before this
         task. Fixed: llm/providers/groq.py now gives a 413 the same
         immediate-failover treatment as a 429; every other
         APIStatusError still propagates unmodified. See ADR 007's
         Task 6.5 section for the full finding, including the
         non-obvious except-clause ordering constraint it required.

         TRUST GATE: scripted eval suite unchanged, zero network
         calls, 100%. Live end-to-end run with Groq serving as the
         actual default (no forcing) — real tool calls, citation
         validator active, every agent_steps row provider="groq".
         Live failover proof HONESTLY PARTIAL, not forced past a
         real constraint: per explicit guidance against deliberately
         exhausting a provider's real quota during verification, a
         mocked GroqProvider (zero real Groq calls) plus the REAL
         GeminiProvider was used; two live attempts both hit
         Gemini's own real gemini-3.5-flash daily quota, already
         exhausted from this session's own earlier legitimate
         testing — a genuine environmental constraint, not a code
         defect. Both attempts correctly exercised the
         both-providers-down graceful degradation path instead
         (clean INCOMPLETE message, no raw error). The
         Groq-unavailable → Gemini-serves mechanism itself is proven
         at the mocked-unit level (tests/test_registry.py, updated
         for the new arrangement) and was already live-proven in the
         reverse direction during 6.4 — the provider-symmetric
         design is exactly why that counts as real evidence here,
         not a stretch. Re-attempting the live "Gemini serves"
         direction once quota has headroom again is noted, not
         blocking.

         ADR 007 updated with the "why Groq primary, Gemini
         fallback" reasoning and the 413 finding. CLAUDE.md and this
         status block updated in the same commit as the config
         change.

FRONTEND — begins now that 6.5 is shipped. Next.js App Router, React,
TypeScript, Tailwind. One task per message.
PRIORITY ORDER: if time runs short, F1–F4 are what matter.

  F1  Next.js project, JWT auth against StockPilot, chat page.

  F2  Consume SSE — streaming tokens, progress events, conversation
      history.

  F3  LIVE EXECUTION GRAPH — the LangGraph path animating as the
      agent runs. Critically: when the replan loop fires, render the
      Planner's sufficiency judgement — what was missing, what it
      decided to do next. That is the moment a viewer sees reasoning
      rather than execution. Clear node states, animated edges,
      legible in a screenshot.

  F4  CITATION DRILL-DOWN — every cited number clickable, opening
      the raw tool response that produced it. Cheap to build; makes
      the grounding architecture provable in one click.

  F5  PROVENANCE BADGES — every figure shows observed / derived /
      predicted with a distinct colour and a tooltip linking to the
      derivation method. The visual signature of the project.

  F6  Recommendation cards — action, priority, revenue at risk,
      confidence, risk if ignored, evidence links, accept/reject
      buttons — and reports view with markdown rendering and export.

  F7  Agent status panel and tool-usage timeline with per-call
      latency and serving provider/model (read per call, never
      assume one model per execution); unmissable backtest banner
      when as_of_date is set; polish.

  Tag: stage-6-transparency
```

---

# IX. Stage 7 — Ship
**Days 16–17.**

```
DEPLOY
  Both services live — backend on Railway or Render, frontend on
  Vercel, managed Postgres. Secrets via platform env vars (including
  GROQ_API_KEY, GEMINI_API_KEY, and LLM_PRIMARY_PROVIDER).
  Seeded demo database and read-only demo login: no signup friction.
  CI running tests, type checks, contract tests, and the eval
  grounding gate.
  Verify from a cold browser on a phone, not just localhost.

DOCUMENTATION — where this project is won or lost
  README:
    - one paragraph: what it is and why
    - THE AGENT ARCHITECTURE: the six-component table (environment,
      perception, policy, memory, judgment, guardrails) and the
      agentic-properties table. Lead with these. They are what make a
      reader understand this is an agent system, not a chatbot.
    - architecture diagram with the agent ↔ environment boundary drawn
      explicitly
    - LangGraph diagram showing the replan loop
    - "How this system avoids hallucinated numbers" — the three
      invariants, tool-less synthesis agents, the validator, the
      citation chain, with real eval numbers. Write this section as
      carefully as you wrote the code; it is what interviewers ask
      about.
    - "Data provenance" — the four labels, and the plain statement that
      stock, cost, suppliers and categories are deterministically
      derived
    - "Resilience" — multi-provider failover restricted to
      infrastructure-class errors, with the serving model recorded
      per call, and an honest note on why Groq is the configured
      primary (quota availability, not a quality claim)
    - scenario eval results table — measured numbers only, with the
      scripted-LLM caveat stated plainly
    - forecasting: baseline vs model scores, honestly reported
    - honest limitations section (include the streaming-path
      execution_id correlation limitation from 6.3, and any Groq
      tool-choice or structured-output findings from ADR 007)
    - setup, deployment, ADR index

  Screenshots plus a 60–90 second demo recording that shows: a query,
  the replan loop firing with its reasoning visible, a citation
  drill-down, and a recommendation card.

  Tag: v1.0
```

---

# X. Working method

**One task per message.** Never generate a stage, a part, or the project in one go. For each task: restate what done means → implement only that → run ruff, mypy, pytest → verify the milestone by running it → commit → report and stop.

**Definition of done, per task:** tests pass with none skipped, ruff clean, mypy clean, Docker builds, milestone verified by execution not assumption, endpoints correct in OpenAPI, no TODOs or stubs, committed.

**End of day rule:** the system boots. Never end a day mid-refactor with nothing runnable. If a milestone can't be met, cut its scope rather than carrying broken code forward.

**Stop and ask** when: the spec is ambiguous, a needed endpoint doesn't exist, you'd have to fabricate or default a business value, a model ID is unavailable, or a task can't complete without breaking an invariant. A blocked task reported honestly is a good outcome. A task completed by inventing something is not.

## Schedule

| Day | Stage | System state at end of day |
|---|---|---|
| 0 | Foundation | Repo, Docker, two DBs, dataset profiled, CI green |
| 1–2 | Environment | Schema migrates, auth works, CRUD exercisable |
| 3 | Environment | Database populated, ingest reproducible from empty |
| 4 | Environment | Inventory and analytics endpoints live in Swagger |
| 5 | Environment | Forecasting live, contracts frozen |
| 6–7 | Perception | Agent calls every environment endpoint through tools |
| 8–9 | Reasoning | Agent plans, retrieves, **replans**, cites, refuses |
| 10–11 | Judgment | Ranked recommendations with computed impact |
| 12 | Robustness | Ten scenarios passing, grounding 100% |
| 13–15 | Transparency | Hardening done (6.1–6.5); chat, execution graph, citations, provenance |
| 16–17 | Ship | Deployed, documented, demo recorded |

## Deliberately not built

| Excluded | Why it's defensible |
|---|---|
| Write-back actions | The dataset is historical; consequences can't be observed, only simulated |
| Learning from outcomes | Same reason — claiming it would be fabrication |
| Proactive live monitoring | Nothing to monitor; backtest mode is the honest version |
| Policy engine, procurement agent | Planner plus workflows already deliver the value |
| Redis, OpenTelemetry, semantic cache | Optimisations without a measured problem |
| Supplier ranking workflow | Supplier data is derived, so a ranking would be theatre |

*"I cut these deliberately, here's the reasoning"* is a stronger answer than having built them.

## Resume framing — fill in only after measuring

> **RetailOps AI — Autonomous Agent for Retail Operations**
> Built an autonomous multi-agent system (LangGraph, FastAPI, PostgreSQL, Next.js) that plans its own retrieval strategy, replans when evidence is insufficient, and produces ranked operational recommendations with computed business impact. Designed a three-layer grounding architecture — tool-less synthesis agents, a runtime citation validator, and end-to-end data-provenance labelling — achieving ___% grounded numeric claims across a 10-scenario evaluation suite covering demand spikes, supplier delays, missing data, environment failure, and prompt injection. Deployed with streaming responses, multi-provider LLM failover, and a live agent-reasoning visualiser.

Every blank stays blank until measured. An empty blank is more credible than a guessed number.

## Change log

Ideas that arrive mid-build go here, not into the code. Revisit after `v1.0`.

- [x] Groq fallback provider — promoted into Stage 6 (Task 6.4) on 2026-07-30, motivated by the live-verified Gemini 429 quota bug
- [x] Groq primary / Gemini fallback provider order — promoted into Stage 6 (Task 6.5) on 2026-07-30, motivated by Gemini's account quota being observed hard-zero
- [ ]