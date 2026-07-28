# ADR 001: The agent and its environment are separate services, communicating only over HTTP

## Status

Accepted — Day 0 (Stage 0 Foundation).

## Context

RetailOps AI has two halves: StockPilot Core, a headless retail operations API holding all business data and logic, and RetailOps AI, a LangGraph multi-agent layer that reasons about that business. In the six-part agent frame this project is built around, StockPilot Core is the **environment** and RetailOps AI's tool layer is its only **perception** channel. That framing is not decoration — it is the thing that makes the three invariants (grounding, full trace, untrusted-data envelopes) possible to enforce at all, and it has to be decided before any schema or endpoint exists, because it shapes the repository layout, the database topology, and the testing strategy from the first line of code.

The question this ADR answers: should the environment and the agent be one Python process sharing models and a database session, or two independently deployable services that only ever talk over HTTP?

## Decision

Two services in a single git repository, communicating **only over HTTP**, each owning its **own PostgreSQL database** (not a shared instance with separate schemas). RetailOps AI never imports StockPilot Core's ORM models, services, or database session, and never connects to StockPilot's database directly.

## Why a separate service, not a shared library or a monolith

**Grounding requires a real boundary to intercept.** Invariant 1 says every numeric claim traces to a `tool_call_id`. That only means something if there is a well-defined moment where "the agent asked the environment for data" happens — a request that can be assigned an ID, timed, and logged. An HTTP call has that boundary for free: request out, response in, both serializable. An in-process function call into a shared `services/inventory.py` does not; faking that boundary (wrapping every internal call to look like a logged "tool call") would be more machinery than just making the call over the network where the boundary already exists.

**Full trace requires something to capture.** Task 2.2's environment client and Task 2.3's tool layer persist raw tool responses into `tool_calls` rows for every invocation. That is a natural byproduct of an HTTP client — the response body is already sitting there as bytes to persist. In a shared-library world, "the raw response" doesn't exist as a distinct artifact; it's just whatever a Python function returned, and reconstructing an equivalent record would mean manually re-serializing every return value, which is strictly more work for a weaker guarantee.

**The contract needs an enforcement point.** Stage 1 Task 6 freezes StockPilot's response shapes as JSON Schema (`contracts/stockpilot-api/versions/v1.json`) and adds a contract test that fails if a response stops matching. That only catches anything because the agent's typed client is generated from a frozen snapshot of an independent service's API, not from whatever the environment's Python objects happen to look like today. A shared library has no equivalent failure mode — if StockPilot's internal model changes shape, an in-process caller either breaks at import time (loudly, but too late — production, not CI) or silently keeps working because it's the same objects. Neither is the same as a versioned contract test that exists specifically to catch environment drift breaking the agent.

**It keeps the "never" rules physically true, not just reviewed-true.** CLAUDE.md and the Stage 2 spec are explicit: RetailOps AI must never query StockPilot's database directly, never re-implement inventory/analytics/forecasting logic, and never let an LLM compute a business number. Those are easy rules to state and easy to erode one task at a time in a monolith, where "just import the helper, it's right there" is one line away. Across a real network boundary with no shared database credentials, "just import it" isn't an option — the rule is enforced by what's physically reachable, not by discipline alone.

**It matches how the project is actually deployed and scaled.** Stage 7 ships StockPilot Core and RetailOps AI to separate platforms (Railway/Render and Vercel) with independent scaling profiles — StockPilot is data/ETL/forecast-heavy, RetailOps AI is LLM-call-bound and bursty. A monolith would have to be split apart again at ship time; building it split from Day 0 means Stage 7 is a deploy, not a re-architecture.

## Why HTTP specifically, not gRPC, a message queue, or shared database views

- **FastAPI already emits the artifact the contract-freezing step needs.** OpenAPI/JSON Schema comes for free from Pydantic response models. Task 2.2's generated client and Task 6's frozen contract both build directly on that. gRPC would mean maintaining a parallel `.proto` schema that duplicates what FastAPI already produces, for no benefit here.
- **The interaction is synchronous request/response, not fire-and-forget.** An agent tool call needs its result back within the same reasoning step to decide what to do next. A message queue (Redis, etc.) fits async/decoupled workloads, not "call a tool, get the answer, keep reasoning" — and Redis is explicitly on this project's "deliberately not built" list as an optimization without a measured problem.
- **Reliability semantics are standard and already required.** Task 2.2 calls for retries with backoff, timeouts, and a circuit breaker in `clients/stockpilot.py`. These are well-trodden patterns for HTTP clients specifically; building equivalent reliability semantics for a bespoke RPC layer would be unproven extra work.

## Why separate databases, not separate schemas in one instance

A shared Postgres instance with two schemas is one misconfigured `GRANT`, one careless cross-schema join, or one shared ORM session away from RetailOps AI reading StockPilot's tables directly. That makes the boundary a matter of convention and code review, not fact. Two separate database servers, with credentials that only ever exist in one service's `.env`, make "read StockPilot's tables directly" not merely discouraged but physically impossible without opening a second connection to a different host with different credentials — which would be conspicuous in the code, not an accident.

## Consequences

- **Two of everything to operate**: two Dockerfiles, two databases, two Alembic histories, two CI matrix legs, and a contract that has to be deliberately re-frozen whenever StockPilot's API changes. Stage 0 already paid this setup cost in a few hours; it does not recur per task.
- **Network latency on every tool call**, where an in-process call would have been microseconds. This is acceptable here because the agent's own LLM calls dominate end-to-end latency by orders of magnitude, and the reliability requirements (Task 2.2) already assume network calls can fail and need handling regardless.
- **Local development needs both services and both databases running at once** to exercise the agent end-to-end (`make db-up`, `make run-core`, `make run-agents`). There is no single-process shortcut for a full local run.
- **StockPilot Core's API surface becomes a real, versioned interface** the moment Stage 1 Task 6 lands, not an implementation detail — changes to it are breaking changes to a consumer, and have to be treated that way.

## What would have to be true to merge them

This project does not merge them, and nothing in its actual requirements pushes toward it. For the record, here is what would have to change for a monolith to become the right call instead:

- **Sub-millisecond synchronous access requirements** — e.g. a live trading system where network round-trip latency itself broke correctness. This project is explicitly historical/backtest-oriented with no live write-back (see the "deliberately not built" list: write-back actions and proactive live monitoring are both out of scope), so this pressure doesn't exist here.
- **No interest in demonstrating the environment/agent boundary as an artifact.** The entire point of this build, stated in its own README framing, is to show a real perception/environment split for an audience that will read the code. Collapsing it would remove the thing the project exists to demonstrate — this isn't a constraint that might change, it's the goal.
- **A deployment target that can only run one process.** Stage 7 plans two independent deployments on two platforms; if that ever had to become "everything on one free-tier dyno," the services would need to merge or one would need to be retired, not just co-located.
- **The operational overhead measurably exceeding the project's time budget.** If maintaining two Dockerfiles, two CI legs, and a hand-frozen contract started consuming days rather than hours, that would be a real signal to reconsider. It hasn't — Stage 0 shows the actual cost is small and one-time.

Short version: nothing about this project's real constraints argues for merging. The separation is a durable architectural choice, not a placeholder.
