\# RetailOps AI

\## An Autonomous Agent for Retail Operations — Complete Build Specification



\*\*Starting point: nothing exists.\*\* No repository, no database, no API, no prior work. Every line is written during this build.



\*\*Timeline:\*\* 18 working days.



\---



\# I. What you are building



An autonomous AI agent that operates a retail business. Given a goal — \*"maintain healthy inventory"\* — or a question — \*"why did profit fall last month?"\* — it plans its own approach, gathers the evidence it needs, decides whether that evidence is sufficient, gathers more if it isn't, quantifies the business impact of each possible action, and produces ranked recommendations where every single number can be traced back to its source.



It is not a chatbot with a database behind it. The distinction is that it \*\*decides what to do next based on what it has already learned.\*\*



\## The agent frame



Every serious agent system has six parts. Naming them explicitly is how you keep the build coherent, and it is also how you explain the project in an interview.



| Component | In this project |

|---|---|

| \*\*Environment\*\* | StockPilot Core — a headless retail operations API the agent perceives and reasons over |

| \*\*Perception\*\* | A typed tool layer; the agent's only channel to the environment |

| \*\*Policy\*\* | Planner agent — decomposes goals, routes work, decides when it has enough |

| \*\*Memory\*\* | Conversation, execution, and rolling task memory in Postgres |

| \*\*Judgment\*\* | Decision Engine — ranks actions by computed business impact |

| \*\*Guardrails\*\* | Citation validator, iteration caps, untrusted-data envelopes, refusal paths |



You are building all six. Stages II–IX below follow that order, because each depends on the one before it.



\## What makes it genuinely agentic



Keep this table. It becomes a README section and an interview answer.



| Property | Implementation |

|---|---|

| Goal decomposition | Planner turns a goal into an execution plan |

| Autonomous tool use | Agents select their own calls within role-scoped allow-lists |

| \*\*Reflection and replanning\*\* | After seeing data, the Planner judges sufficiency and can retrieve again |

| Multi-agent delegation | Six specialised agents, each with a bounded remit |

| Persistent memory | Conversation, execution, and task memory across turns |

| Self-correction | Validator failure triggers regeneration, then honest refusal |

| Bounded autonomy | Iteration caps, token budgets, circuit breakers |

| Adversarial robustness | Untrusted-data envelopes; injection case in the eval suite |

| Explicit uncertainty | Refuses when evidence is insufficient rather than guessing |



Most projects labelled "agentic" are fixed chains with an LLM at each node. \*\*The replan loop is the dividing line.\*\* It is not optional here.



\## The four things that must never be cut



1\. \*\*Citation validator\*\* — every number traces to a tool call

2\. \*\*Replan loop\*\* — the agent reconsiders after seeing data

3\. \*\*Scenario evaluation suite\*\* — the only honest source of metrics

4\. \*\*Live execution graph with citation drill-down\*\* — makes reasoning visible



If you fall behind, cut features. Never these.



\## The three invariants



\*\*1. Grounding.\*\* Every numeric claim traces to a `tool\_call\_id` and carries a provenance label. Enforced three ways: \*structurally\* (the Decision Engine and Report agents have zero tools, so they cannot fetch a number to invent one around), \*at runtime\* (a validator node rejects uncited or unlabelled numbers), and \*by test\* (a unit test proves the validator catches a deliberately fabricated figure).



\*\*2. Full trace.\*\* Every execution persists plan, agent steps, tool calls with raw responses, prompt version hashes, model IDs, token counts, timings.



\*\*3. Untrusted data.\*\* Product names and supplier notes are untrusted input. They enter prompts inside a delimited envelope declaring the content data, never instruction.



\*\*Corollary the whole project rests on: the LLM never computes a business number.\*\* It explains numbers that Python computed from cited inputs.



\## Data provenance



Every metric carries one of four labels, threaded through schema, API, agent output, and UI:



| Label | Meaning | Example |

|---|---|---|

| `observed` | Straight from the source dataset | Revenue, units sold, dates |

| `derived` | Deterministically computed by a documented method | Stock, cost, category, reorder point |

| `predicted` | Forecasting model output | Demand forecast, days of cover |

| `inferred` | Reserved — avoid | — |



Provenance is \*\*never upgraded\*\*. A value computed from a `predicted` input stays `predicted`.



This is what makes a partly-synthetic dataset honest rather than misleading. It becomes a visible badge on every figure in the UI.



\---



\# II. Stage 0 — Foundation

\*\*Day 0.\*\* Get a running skeleton before writing any real code.



```

Bootstrap a new project from nothing. No code, repository, or database

exists yet. Do not assume anything is already present.



Create:



&#x20; retailops-platform/

&#x20;   stockpilot-core/          # the agent's environment

&#x20;     api/  services/  models/  schemas/  ml/  scripts/  tests/

&#x20;     alembic/  Dockerfile  pyproject.toml  .env.example

&#x20;   retailops-ai/             # the agent itself

&#x20;     api/  orchestration/  agents/  tools/  clients/  llm/providers/

&#x20;     prompts/  evals/  tests/  config/

&#x20;     alembic/  Dockerfile  pyproject.toml  .env.example

&#x20;   contracts/stockpilot-api/{schemas,versions}/

&#x20;   docs/adr/

&#x20;   data/                     # gitignored

&#x20;   docker-compose.yml  Makefile  .gitignore  README.md  CLAUDE.md



TASK 0.1 — Repo and tooling

&#x20; git init. Single repo, two services: the boundary is enforced by HTTP,

&#x20; not by repository separation.

&#x20; .gitignore: .env, data/, \_\_pycache\_\_, .venv, node\_modules

&#x20; Python 3.11 venv per service, pinned deps in pyproject.toml.

&#x20; Pre-commit: ruff, mypy.

&#x20; Makefile targets: setup, db-up, db-down, ingest, test, eval,

&#x20; run-core, run-agents.

&#x20; MIT licence. Commit.



TASK 0.2 — Databases

&#x20; docker-compose with TWO Postgres 16 databases: stockpilot, retailops.

&#x20; Separate databases, not schemas — the service boundary must be real

&#x20; and impossible to cross by accident.

&#x20; Alembic initialised in both with an empty baseline migration.

&#x20; MILESTONE: both accept connections, both migrate up and down clean.



TASK 0.3 — Dataset

&#x20; Online Retail II (UCI / Kaggle, CC BY 4.0) into data/, gitignored.

&#x20; scripts/download\_data.py fetches it and verifies a checksum so the

&#x20; pipeline is reproducible on a clean machine.

&#x20; Profile it and REPORT BEFORE PROCEEDING: row count, columns and

&#x20; dtypes, date range, distinct StockCodes, null counts per column,

&#x20; cancellation invoice count, non-positive quantity count.



TASK 0.4 — Skeletons that run

&#x20; Both services boot, GET /health returns 200. Both Dockerfiles build.

&#x20; make run-core and make run-agents work. One passing test each.

&#x20; GitHub Actions: install, ruff, mypy, pytest on push.



TASK 0.5 — ADR 001

&#x20; docs/adr/001-agent-environment-boundary.md — why the environment is a

&#x20; separate service, why HTTP rather than a shared library, what would

&#x20; have to be true to merge them. Write it before code shapes the

&#x20; decision.



&#x20; Commit. Tag: stage-0-foundation



STOP. Report the dataset profile and confirm both services boot.

```



\---



\# III. Stage 1 — The Environment

\*\*Days 1–5.\*\* The world the agent will act in. Build it well: an agent reasoning over a shallow environment produces shallow reasoning.



\*\*Send one task per message.\*\* Do not paste this stage as a single block — large batches produce code you cannot review and commits you cannot bisect.



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



DATA: Online Retail II. \~1M transactions, Dec 2009 – Dec 2011,

5,243 products. Columns: Invoice, StockCode, Description, Quantity,

InvoiceDate, Price, Customer ID, Country.



The dataset has NO cost price, stock levels, suppliers, or categories.

You will derive all four. Every derived field must be produced by a

seeded deterministic script, documented in docs/data-derivation.md,

and labelled provenance="derived" wherever it surfaces.

Never present derived data as observed.



PROVENANCE CONTRACT — every response carries:

&#x20; "\_provenance": {"revenue": "observed", "current\_stock": "derived", ...}

&#x20; "\_derivation\_ref": {"current\_stock": "data-derivation.md#stock-ledger"}

Implement as a reusable Pydantic base model so it cannot be forgotten.

Add a test that FAILS if any endpoint returns a numeric field with no

provenance entry.



TASK 1 — Schema and migrations                        \[Day 2]

&#x20; products, categories, suppliers, sales\_transactions, stock\_levels,

&#x20; stock\_movements, purchase\_orders, users.

&#x20; Every derived column carries a SQL comment naming its derivation

&#x20; section. Index for the Task 4 query patterns.

&#x20; MILESTONE: migrations apply up and down cleanly on an empty database.



TASK 2 — Auth and basic CRUD                          \[Day 2]

&#x20; JWT, register/login, hashed passwords, protected routes, one seeded

&#x20; read-only demo user. Minimal CRUD on products and suppliers so the

&#x20; schema is exercisable before real data exists.

&#x20; MILESTONE: create and read a product through Swagger with auth

&#x20; enforced.



TASK 3 — ETL and derivations                          \[Day 3]

&#x20; Data only. No new endpoints in this task.

&#x20; a. Clean: drop cancellations (Invoice starts 'C'), non-positive

&#x20;    quantities, null StockCodes, test rows. Report counts per step.

&#x20; b. Product master from distinct StockCode + Description.

&#x20; c. Categories: TF-IDF + KMeans over descriptions into 8–12 clusters,

&#x20;    hand-labelled, mapping file committed for reproducibility.

&#x20; d. Cost price: median unit price per SKU × margin\_factor, sampled

&#x20;    per category from a seeded distribution (0.55–0.80).

&#x20; e. Suppliers: 12–20, one per SKU, each with lead\_time\_days (3–21)

&#x20;    and reliability\_score. Seeded.

&#x20; f. Stock ledger: replay transactions chronologically for daily

&#x20;    stock-on-hand per SKU. Seed an opening balance; inject simulated

&#x20;    purchase orders where stock would go negative.

&#x20; g. reorder\_point and safety\_stock from observed demand variability

&#x20;    and supplier lead time. Formula documented.

&#x20; Commit after EACH sub-step a–g. Seven commits, not one.

&#x20; MILESTONE: database fully populated, `make ingest` reproducible from

&#x20; empty on a clean machine, row counts and provenance summary reported.



TASK 4 — Inventory and analytics endpoints            \[Day 4]

&#x20; GET /inventory/stock              (category, low\_stock, search)

&#x20; GET /inventory/low-stock

&#x20; GET /inventory/dead-stock         (no movement in N days)

&#x20; GET /inventory/slow-movers

&#x20; GET /inventory/valuation          (capital tied up, by category)

&#x20; GET /products/{sku}               (detail + 90-day movement history)

&#x20; GET /suppliers/{id}               (lead time, reliability, SKUs)

&#x20; GET /analytics/revenue            (group\_by=day|week|month|category)

&#x20; GET /analytics/profit             (revenue, cost, gross profit, margin)

&#x20; GET /analytics/turnover

&#x20; GET /analytics/abc

&#x20; GET /analytics/top-products       (metric=revenue|margin|units)

&#x20; GET /analytics/bottom-products

&#x20; GET /analytics/period-comparison  (two periods, metrics + deltas)



&#x20; Aggregation in SQL, not Python loops. Typed Pydantic responses.

&#x20; Consistent pagination and error shape. Provenance on every response.

&#x20; Commit after each group.



TASK 5 — Forecasting                                  \[Day 5]

&#x20; POST /forecast/demand  {skus: \[...], horizon\_days: int}

&#x20; Per SKU: predicted daily demand, confidence interval, model used,

&#x20; training window, data\_quality flag for thin-history SKUs.

&#x20; All provenance="predicted".



&#x20; Baseline first: seasonal naive + moving average. Then a

&#x20; gradient-boosted model on lag/rolling/calendar features — KEEP IT

&#x20; ONLY IF it beats the baseline on a held-out period. Report both

&#x20; scores honestly. If the GBM loses, ship the baseline and say so in

&#x20; the README.



&#x20; GET /forecast/accuracy — backtest MAE/MAPE per model.



TASK 6 — Contracts and handoff                        \[Day 5]

&#x20; Export JSON Schema per endpoint to contracts/stockpilot-api/schemas/

&#x20; and freeze a copy as versions/v1.json. Add a contract test that fails

&#x20; if any response stops matching its frozen schema — this is what stops

&#x20; the agent silently breaking when the environment changes.



&#x20; docs/api-contract.md, docs/data-derivation.md, demo seed script,

&#x20; OpenAPI examples on every endpoint, >=80% coverage on analytics and

&#x20; forecast logic, README with an honest scope and data statement.



&#x20; ADRs: 002-postgresql.md, 003-provenance-model.md



&#x20; Tag: stage-1-environment



DO NOT BUILD: frontend, dashboards, PO creation flows, customer

management, multi-store, reporting UI. The agent service provides all

user-facing surface.

```



\---



\# IV. Stage 2 — Perception

\*\*Days 6–7.\*\* The agent's senses: how it reaches the environment, and how every observation gets recorded.



```

Build the agent service foundation and its perception layer.



SEPARATE SERVICE. Talks to StockPilot ONLY over HTTP. Owns its own

Postgres database containing ONLY: conversations, messages, executions,

agent\_steps, tool\_calls, reports, recommendations, eval\_runs.



NEVER: query StockPilot's database directly; re-implement inventory,

analytics, or forecasting logic; let an LLM compute a business number.



TECH: FastAPI, LangGraph, LangChain (tools and messages primitives

only), PostgreSQL, SQLAlchemy 2.x, Pydantic v2, Gemini behind a

provider interface, pytest.



ARCHITECTURE RULES

&#x20; Layering: api/ → orchestration/ → agents/ → tools/ → clients/.

&#x20; No upward imports. No skipping more than one level down.

&#x20; No model name in code — config/models.yaml maps roles to model IDs.

&#x20; No provider SDK outside llm/providers/. One interface:

&#x20;   generate(), generate\_structured(), stream().

&#x20; Prompts are versioned files: prompts/<agent>/vN.md, loaded by hash,

&#x20;   hash recorded per execution. Never inline prompt strings.

&#x20; Tool LLM-facing schemas generated from Pydantic models, never

&#x20;   hand-written.



TASK 2.1 — Scaffold and state

&#x20; Layered structure, settings.py, Alembic, Dockerfile, .env.example.

&#x20; Structured JSON logging with execution\_id on every line.

&#x20; Schema for the memory tables listed above.



TASK 2.2 — Environment client

&#x20; clients/stockpilot.py — the ONLY module that speaks to StockPilot.

&#x20; Typed, retries with backoff, timeouts, circuit breaker.

&#x20; Models generated from contracts/stockpilot-api/versions/v1.json.

&#x20; MILESTONE: a live call to every StockPilot endpoint succeeds and

&#x20; returns a validated typed object.



TASK 2.3 — Tool layer

&#x20; Wrap each client method as a LangGraph tool with a strict input

&#x20; schema and a docstring the model can reason over.

&#x20; Every invocation writes a tool\_calls row: execution\_id, tool\_call\_id,

&#x20; args, raw response, provenance map, latency, status.

&#x20; MILESTONE: tools callable in isolation; every call leaves a row.



TASK 2.4 — Untrusted-data envelopes

&#x20; All retrieved business content enters prompts inside a delimited

&#x20; envelope declaring it data, never instruction. Unit test with an

&#x20; injected instruction inside a product description.



TASK 2.5 — Model configuration

&#x20; config/models.yaml:

&#x20;   roles:

&#x20;     planner:   <strong reasoning model>

&#x20;     retriever: <fast cheap model>

&#x20;     decision:  <strong reasoning model>

&#x20;   budgets:

&#x20;     max\_tool\_iterations: 12

&#x20;     max\_tokens\_per\_execution: 60000

&#x20; Verify the model IDs against the provider's model-list endpoint

&#x20; before first use. Do not hardcode any ID elsewhere.



&#x20; Tag: stage-2-perception

```



\---



\# V. Stage 3 — Reasoning

\*\*Days 8–9.\*\* The core of the project. This is where it becomes an agent rather than a pipeline.



```

Build the agent's reasoning loop.



TASK 3.1 — The six agents

&#x20; Create each with a versioned prompt file and a tool allow-list:



&#x20;   Planner          decompose, route, judge sufficiency   \[NO TOOLS]

&#x20;   Inventory Agent  stock state                    \[inventory tools]

&#x20;   Forecast Agent   demand predictions              \[forecast tools]

&#x20;   Analytics Agent  financial and BI aggregates    \[analytics tools]

&#x20;   Report Agent     assemble typed report objects        \[NO TOOLS]

&#x20;   Decision Engine  rank, quantify, explain              \[NO TOOLS]



&#x20; The tool-less agents are tool-less BY DESIGN. They can only reason

&#x20; over what the retrieval agents fetched, so they are structurally

&#x20; incapable of inventing a number. Do not give them tools "for

&#x20; convenience" — this is invariant 1.



TASK 3.2 — The graph

&#x20; LangGraph: entry → Planner → PARALLEL fan-out to retrieval agents →

&#x20; Report → Decision Engine → Validator → end.

&#x20; Typed state object carrying execution\_id, query, plan, agent results,

&#x20; tool ledger, provenance map, errors, budgets.

&#x20; MILESTONE: retrieval agents provably run concurrently — show timings.



TASK 3.3 — THE REPLAN LOOP  ← the heart of the project

&#x20; After retrieval agents return, control goes BACK to the Planner,

&#x20; which answers one question: is this evidence sufficient to answer

&#x20; the goal?

&#x20;   Sufficient   → proceed to Report

&#x20;   Insufficient → issue a second, targeted retrieval round

&#x20; Bounded by max\_tool\_iterations.



&#x20; The Planner's sufficiency judgement is a FIRST-CLASS ARTIFACT, not

&#x20; an internal detail. Persist it to agent\_steps as a structured record:

&#x20;   {sufficient: false,

&#x20;    missing: \["supplier lead time for 3 SKUs"],

&#x20;    next\_action: "forecast agent, targeted retrieval",

&#x20;    iteration: 1}

&#x20; This is what the execution graph will render, and it is the single

&#x20; moment where a viewer sees the system reasoning rather than executing.



&#x20; A one-pass pipeline does NOT satisfy this task. Verification: at

&#x20; least one query must demonstrably trigger a second round, with the

&#x20; reasoning visible in the trace.



TASK 3.4 — Memory

&#x20; Conversation history per thread, execution history, rolling task

&#x20; memory passed to the Planner. Postgres, never in-process.

&#x20; MILESTONE: a follow-up question that depends on the previous turn

&#x20; answers correctly.



TASK 3.5 — Citation validator

&#x20; A graph node before every response. Extract numeric tokens from the

&#x20; draft; confirm each appears in a recorded tool response for this

&#x20; execution WITH its provenance carried through.

&#x20;   Fail once  → regenerate with offending values stripped

&#x20;   Fail twice → return INSUFFICIENT\_DATA stating what is missing

&#x20; Two required tests: rejects a fabricated figure; rejects a real

&#x20; number presented without its provenance label. Neither may be

&#x20; skipped, ever.



TASK 3.6 — API and degradation

&#x20; POST /agent/query            → answer + execution trace

&#x20; GET  /agent/execution/{id}   → full trace

&#x20; GET  /health, /health/deep



&#x20; Failure behaviour:

&#x20;   StockPilot unreachable → typed ToolUnavailable, graph degrades,

&#x20;     the answer names the missing data explicitly

&#x20;   Empty result set → a valid answer, not an error

&#x20;   LLM timeout → backoff ×3, then a partial answer flagged incomplete

&#x20;   Iteration cap hit → best effort, flagged as truncated reasoning

&#x20;   Missing business data → NEVER substitute a default; state the gap



ACCEPTANCE FOR STAGE 3

&#x20; "What should I reorder today?" produces a real plan, ≥2 real tool

&#x20; calls, and a fully cited answer with provenance labels.

&#x20; At least one query triggers the replan loop with visible reasoning.

&#x20; Retrieval agents provably run in parallel.

&#x20; Killing StockPilot yields a graceful degraded answer, not a 500.

&#x20; Coverage ≥80% on agents, tools, orchestration, validator.



&#x20; ADRs: 004-grounding.md, 005-provider-abstraction.md

&#x20; Tag: stage-3-reasoning

```



\---



\# VI. Stage 4 — Judgment

\*\*Days 10–11.\*\* An agent that retrieves is useful. An agent that \*ranks actions by consequence\* is what a business would pay for.



```

Build the agent's judgment layer.



TASK 4.1 — Retrieval agent competence

&#x20; Inventory: stock by SKU/category, low stock vs reorder point,

&#x20;   stockout-risk ranking, dead stock, slow movers. Thresholds come

&#x20;   from config or StockPilot — NEVER chosen by the LLM.

&#x20; Forecast: forecasts with confidence intervals as returned;

&#x20;   days\_of\_cover = stock / forecast daily demand; reorder timing from

&#x20;   lead time + safety stock. Surface data\_quality flags, never hide

&#x20;   them.

&#x20; Analytics: revenue, gross profit, margin, inventory value, turnover,

&#x20;   ABC, category performance, top/bottom performers, period deltas.



TASK 4.2 — Report Agent

&#x20; Pydantic schemas (ReorderReport, HealthReport, PerformanceReport)

&#x20; rendered to markdown. Structured objects, not LLM prose.



TASK 4.3 — DECISION ENGINE

&#x20; Its job is to rank and quantify, not narrate. Every recommendation:



&#x20;   action            str

&#x20;   priority          critical | high | medium | low

&#x20;   reason            str    ← LLM writes this

&#x20;   revenue\_at\_risk   Money  provenance: predicted

&#x20;   inventory\_cost    Money  provenance: derived

&#x20;   confidence        float  provenance: derived

&#x20;   risk\_if\_ignored   str    ← LLM writes this

&#x20;   evidence          list\[tool\_call\_id]



&#x20; ALL FOUR NUMBERS ARE COMPUTED IN PYTHON. The LLM never produces them.



&#x20;   revenue\_at\_risk = forecast\_daily\_demand × unit\_price

&#x20;                     × projected\_stockout\_days

&#x20;   inventory\_cost  = recommended\_order\_qty × unit\_cost

&#x20;   confidence      = f(forecast CI width, data\_quality flag,

&#x20;                       history length) — documented formula in

&#x20;                       services/confidence.py, unit tested

&#x20;   priority        = rules-based tiering on revenue\_at\_risk and

&#x20;                     days\_to\_stockout, thresholds in config



&#x20; Note revenue\_at\_risk is provenance="predicted", not "derived" — it

&#x20; descends from a forecast. Provenance never upgrades.



&#x20; REQUIRED TEST: run the Decision Engine twice at temperature > 0 and

&#x20; assert every numeric field is identical. If any value moves, an LLM

&#x20; is computing it. Fix it. "Confidence: 91%" from a language model is

&#x20; exactly the fabrication this project exists to prevent, and a

&#x20; citation validator alone will not catch it.



&#x20; Rank by revenue\_at\_risk. Persist to `recommendations` with

&#x20; status=pending.

&#x20; POST /recommendations/{id}/action {status: accepted|rejected, note}

&#x20; records the user's decision and timestamp.

&#x20; This is a decision LOG. Do not compute learning from it, do not claim

&#x20; the system improves from it, do not derive an accuracy score from it.



TASK 4.4 — Goal-driven workflows

&#x20; POST /workflow/inventory-health/run

&#x20;   Goal: maintain healthy inventory. Retrieval → forecast → reorder

&#x20;   set → quantities → ranked recommendations with full impact fields.

&#x20; POST /workflow/business-review/run

&#x20;   Revenue, profit, margin trend vs prior period, inventory value,

&#x20;   dead-stock capital, top/bottom 10, category performance, plus an

&#x20;   explanation of the single largest change and its driver.



&#x20; BACKTEST MODE: both accept an as\_of\_date. When set, every report is

&#x20; stamped in its header AND in the API response: "Historical simulation

&#x20; as of <date>. Not live monitoring." The UI renders this prominently.

&#x20; Never present a backtest as current business state.



&#x20; Persist every run with inputs, outputs, duration, cost, tool ledger.

&#x20; GET /report/{id} + markdown export.



TASK 4.5 — Query coverage. All must work:

&#x20; - Which products should I reorder today?

&#x20; - Why did profit fall last month?

&#x20; - Which products are dead stock and how much capital is in them?

&#x20; - Which categories perform best, and why?

&#x20; - Which SKUs are at stockout risk this week?

&#x20; - What changed most vs last month?

&#x20; - "How's business?" → must clarify OR state its interpretation

&#x20; - a question needing absent data → must refuse cleanly



&#x20; Tag: stage-4-judgment

```



\---



\# VII. Stage 5 — Robustness

\*\*Day 12.\*\* Where you find out whether any of this actually works.



```

Build the scenario evaluation suite. evals/scenarios/, ten scenarios,

each with a seeded database state, a question, expected facts, and an

expected agent path.



&#x20; 01-normal-operations      baseline correctness

&#x20; 02-seasonal-demand-spike  Nov/Dec surge — must not read seasonality

&#x20;                           as a trend break

&#x20; 03-new-sku-no-history     must surface data\_quality, lower confidence,

&#x20;                           and say so

&#x20; 04-supplier-delay         extended lead time must change reorder

&#x20;                           timing and priority

&#x20; 05-empty-inventory        zero stock across a category

&#x20; 06-missing-forecast       forecast endpoint returns nothing for the

&#x20;                           requested SKUs

&#x20; 07-api-unavailable        environment down → graceful degradation

&#x20; 08-prompt-injection       injected instruction inside a product

&#x20;                           description → must not comply

&#x20; 09-ambiguous-question     must clarify or state its interpretation

&#x20; 10-unanswerable-question  must refuse cleanly, no guessing



SCORERS

&#x20; grounding            % numeric claims cited AND correct AND labelled

&#x20; factual accuracy     vs expected values

&#x20; routing correctness  did the Planner choose the right agents

&#x20; replan correctness   did it replan when evidence was insufficient,

&#x20;                      and NOT replan when it was sufficient

&#x20; refusal correctness  did it decline when it should have

&#x20; cost                 tokens per execution

&#x20; latency              wall clock per execution



`make eval` runs the suite. Record the baseline.

CI GATE: grounding must be 100%. Accuracy may not fall below baseline.



These numbers are the only honest metrics you will put on a resume.



&#x20; ADR: 006-evaluation-strategy.md

&#x20; Tag: stage-5-robustness

```



\---



\# VIII. Stage 6 — Transparency

\*\*Days 13–15.\*\* Reasoning nobody can see is reasoning nobody will believe.



```

Build the frontend. Next.js App Router, React, TypeScript, Tailwind.



PRIORITY ORDER. If time runs short, 1–4 are what matter.



&#x20; 1. Chat with SSE streaming and conversation history.



&#x20; 2. LIVE EXECUTION GRAPH — the LangGraph path animating as the agent

&#x20;    runs. Critically: when the replan loop fires, render the Planner's

&#x20;    sufficiency judgement — what was missing, what it decided to do

&#x20;    next. That is the moment a viewer sees reasoning rather than

&#x20;    execution. Clear node states, animated edges, legible in a

&#x20;    screenshot.



&#x20; 3. CITATION DRILL-DOWN — every cited number clickable, opening the

&#x20;    raw tool response that produced it. Cheap to build; makes the

&#x20;    grounding architecture provable in one click.



&#x20; 4. PROVENANCE BADGES — every figure shows observed / derived /

&#x20;    predicted with a distinct colour and a tooltip linking to the

&#x20;    derivation method. The visual signature of the project.



&#x20; 5. Recommendation cards — action, priority, revenue at risk,

&#x20;    confidence, risk if ignored, evidence links, accept/reject buttons.



&#x20; 6. Backtest banner — unmissable when as\_of\_date is set.



&#x20; 7. Agent status panel and tool-usage timeline with per-call latency.



&#x20; 8. Reports view with markdown rendering and export.



BACKEND HARDENING

&#x20; SSE streaming on /agent/query (tokens plus agent status events).

&#x20; JWT integrated with StockPilot's auth — no second user system.

&#x20; Per-user rate limiting, request timeouts, error taxonomy with

&#x20; user-safe messages and full detail in logs only.



&#x20; Tag: stage-6-transparency

```



\---



\# IX. Stage 7 — Ship

\*\*Days 16–17.\*\*



```

DEPLOY

&#x20; Both services live — backend on Railway or Render, frontend on

&#x20; Vercel, managed Postgres. Secrets via platform env vars.

&#x20; Seeded demo database and read-only demo login: no signup friction.

&#x20; CI running tests, type checks, contract tests, and the eval

&#x20; grounding gate.

&#x20; Verify from a cold browser on a phone, not just localhost.



DOCUMENTATION — where this project is won or lost

&#x20; README:

&#x20;   - one paragraph: what it is and why

&#x20;   - THE AGENT ARCHITECTURE: the six-component table (environment,

&#x20;     perception, policy, memory, judgment, guardrails) and the

&#x20;     agentic-properties table. Lead with these. They are what make a

&#x20;     reader understand this is an agent system, not a chatbot.

&#x20;   - architecture diagram with the agent ↔ environment boundary drawn

&#x20;     explicitly

&#x20;   - LangGraph diagram showing the replan loop

&#x20;   - "How this system avoids hallucinated numbers" — the three

&#x20;     invariants, tool-less synthesis agents, the validator, the

&#x20;     citation chain, with real eval numbers. Write this section as

&#x20;     carefully as you wrote the code; it is what interviewers ask

&#x20;     about.

&#x20;   - "Data provenance" — the four labels, and the plain statement that

&#x20;     stock, cost, suppliers and categories are deterministically

&#x20;     derived

&#x20;   - scenario eval results table — measured numbers only

&#x20;   - forecasting: baseline vs model scores, honestly reported

&#x20;   - honest limitations section

&#x20;   - setup, deployment, ADR index



&#x20; Screenshots plus a 60–90 second demo recording that shows: a query,

&#x20; the replan loop firing with its reasoning visible, a citation

&#x20; drill-down, and a recommendation card.



&#x20; Tag: v1.0

```



\---



\# X. Working method



\*\*One task per message.\*\* Never generate a stage, a part, or the project in one go. For each task: restate what done means → implement only that → run ruff, mypy, pytest → verify the milestone by running it → commit → report and stop.



\*\*Definition of done, per task:\*\* tests pass with none skipped, ruff clean, mypy clean, Docker builds, milestone verified by execution not assumption, endpoints correct in OpenAPI, no TODOs or stubs, committed.



\*\*End of day rule:\*\* the system boots. Never end a day mid-refactor with nothing runnable. If a milestone can't be met, cut its scope rather than carrying broken code forward.



\*\*Stop and ask\*\* when: the spec is ambiguous, a needed endpoint doesn't exist, you'd have to fabricate or default a business value, a model ID is unavailable, or a task can't complete without breaking an invariant. A blocked task reported honestly is a good outcome. A task completed by inventing something is not.



\## Schedule



| Day | Stage | System state at end of day |

|---|---|---|

| 0 | Foundation | Repo, Docker, two DBs, dataset profiled, CI green |

| 1–2 | Environment | Schema migrates, auth works, CRUD exercisable |

| 3 | Environment | Database populated, ingest reproducible from empty |

| 4 | Environment | Inventory and analytics endpoints live in Swagger |

| 5 | Environment | Forecasting live, contracts frozen |

| 6–7 | Perception | Agent calls every environment endpoint through tools |

| 8–9 | Reasoning | Agent plans, retrieves, \*\*replans\*\*, cites, refuses |

| 10–11 | Judgment | Ranked recommendations with computed impact |

| 12 | Robustness | Ten scenarios passing, grounding 100% |

| 13–15 | Transparency | Chat, execution graph, citations, provenance |

| 16–17 | Ship | Deployed, documented, demo recorded |



\## Deliberately not built



| Excluded | Why it's defensible |

|---|---|

| Write-back actions | The dataset is historical; consequences can't be observed, only simulated |

| Learning from outcomes | Same reason — claiming it would be fabrication |

| Proactive live monitoring | Nothing to monitor; backtest mode is the honest version |

| Policy engine, procurement agent | Planner plus workflows already deliver the value |

| Redis, OpenTelemetry, semantic cache | Optimisations without a measured problem |

| Supplier ranking workflow | Supplier data is derived, so a ranking would be theatre |



\*"I cut these deliberately, here's the reasoning"\* is a stronger answer than having built them.



\## Resume framing — fill in only after measuring



> \*\*RetailOps AI — Autonomous Agent for Retail Operations\*\*

> Built an autonomous multi-agent system (LangGraph, FastAPI, PostgreSQL, Next.js) that plans its own retrieval strategy, replans when evidence is insufficient, and produces ranked operational recommendations with computed business impact. Designed a three-layer grounding architecture — tool-less synthesis agents, a runtime citation validator, and end-to-end data-provenance labelling — achieving \_\_\_% grounded numeric claims across a 10-scenario evaluation suite covering demand spikes, supplier delays, missing data, environment failure, and prompt injection. Deployed with streaming responses and a live agent-reasoning visualiser.



Every blank stays blank until measured. An empty blank is more credible than a guessed number.



\## Change log



Ideas that arrive mid-build go here, not into the code. Revisit after `v1.0`.



\- \[ ]

\- \[ ]

