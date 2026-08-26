# RetailOps / StockPilot status

Audit date: 2026-08-25

This is a verified working-status ledger, not a feature wish list. It supersedes
the outdated all-green assertion in `docs/PRODUCTION-SIGN-OFF.md` where the
current repository and checks disagree.

## System map

| Component | Purpose | Audit result |
| --- | --- | --- |
| `stockpilot-core` | FastAPI business API, PostgreSQL models and Alembic migrations | Substantially implemented: 66 OpenAPI paths / 88 operations, 18 resource routers, and 15 migrations. Foundation has migration and full-mypy defects. |
| `stockpilot-frontend` | Next.js ERP frontend | 35 routes covering the documented ERP resources. Tests and type check pass; lint reports 37 warnings; build completed compilation/typecheck but needs a clean, captured final run. |
| `retailops-ai` | FastAPI/LangGraph orchestration, agent persistence, provider pools, tools and evaluations | Substantially implemented. 374 tests pass. Full ruff/mypy gates presently fail. |
| `retailops-ai-frontend` | Standalone Next.js copilot frontend | Builds, lints, type-checks and tests cleanly (17 tests). |
| `retailops-ai/frontend` | Second, near-duplicate copilot frontend | Also builds, lints, type-checks and tests cleanly (17 tests). Ownership/deployment target is ambiguous and must be resolved to prevent drift. |

## Completed and verified

- StockPilot Core implements the documented authentication, product/category/brand,
  supplier/contact, warehouse/inventory, purchase-order, customer, sales/invoice/
  payment, analytics, forecast, administration, notification, audit-log, settings,
  and health API surfaces. The checked-in OpenAPI export matches 66 paths and 88
  operations.
- Core application modules (`api`, `models`, `schemas`, `services`, `ml`, settings,
  database) pass strict mypy: 106 source files checked with no errors.
- RetailOps AI contains real planner/replan, retrieval agents, decision/reporting,
  execution persistence, SSE, citations/provenance, Groq/Gemini provider fallback,
  multi-key rotation, and evaluation coverage. Its full pytest suite passed:
  374 tests in 18.59s, without live LLM calls.
- Both AI frontend copies pass lint, `tsc --noEmit`, unit tests, and production build.
- The StockPilot ERP frontend passes `tsc --noEmit` and 97 Vitest tests. Its test run
  logs missing `NEXT_PUBLIC_API_BASE_URL` diagnostics despite mocked fetches, which
  is noisy but did not fail the tests.
- Docker Compose has both local PostgreSQL services healthy. Both FastAPI applications
  import successfully (`stockpilot-core`: 24 route objects; `retailops-ai`: 8 route
  objects).

## Partial / unverified

- Core full pytest collects 235 tests and advances through the suite, but did not
  finish within the available 30-second execution window. The isolated forecast
  service test passes (6 tests in 2.23s). A complete captured run remains required.
- StockPilot ERP production build compiled and type-checked successfully, but its
  final page-generation result was not captured before the command window closed.
  Re-run it after foundation fixes and record the exit status.
- Deployment is configured for Render/Railway-style backends and Vercel frontends,
  but no live hosting, external CORS/session behavior, health smoke test, error
  tracking, or CI deployment was verified in this audit.
- Real RAG has not been established. The AI service has HTTP retrieval tools and
  persistence, but no pgvector dependency, vector model, migration, embedding
  pipeline, or retrieval-document corpus was found.
- Browser E2E, automated axe coverage, and Lighthouse performance checks are absent
  from the verified quality gate.

## Known bugs and quality-gate failures

1. `stockpilot-core` full `mypy .` fails with 165 errors. Application code is clean;
   the failures are concentrated in `scripts/import_india_seed.py` (untyped code and
   missing `psutil` stubs) and two `None` constraint-name calls in migration
   `5eb70655ed3a_add_india_schema_fields.py`.
2. `retailops-ai` full ruff fails with 12 issues and its full mypy run fails with 12
   errors. Some of these are in the user's uncommitted
   `scripts/verify_live_production.py`, which must be preserved and handled
   separately. Tracked-code issues include long lines, an unused loop variable, and
   nullable database-bind typing in `api/recommendations.py`.
3. `stockpilot-core` has a local database at revision `c80c9cae5095`, one additive
   migration behind head (`f7a8b9c0d1e2`). The pending migration adds nullable image
   and avatar URL columns.
4. `alembic upgrade head --sql` cannot render the Core migration chain from a blank
   database because migration `f4a5b6c7d8e9` executes a database query and calls
   `scalar_one()` in offline mode. Online migration behavior from an actual database
   still needs verification.
5. The ERP frontend lint command exits successfully but reports 37 warnings,
   predominantly unused imports/handlers plus one incomplete hook-dependency list.
6. The checked-in product/build documentation is materially stale: it still says
   most ERP frontend modules are unstarted, while current code contains routes and
   API clients for those modules. The production sign-off also claims green Python
   gates that are now red.
7. The deployment blueprint contains committed credential-like demo values. Do not
   treat them as safe production configuration; rotation/replacement requires the
   deployment owner's authority and must occur before live deployment.

## Backend/API gaps

- Product image support now has an `image_url` migration, but the actual object
  storage upload, validation, lifecycle, and client contract need verification.
- Per-warehouse filtering is not confirmed on the stock/low-stock/dead-stock/
  slow-movers/valuation read endpoints.
- Historical point-in-time inventory and forecast queries remain incomplete; current
  documentation describes an honest simulation fallback.
- There is no confirmed per-SKU unit-price API for exhaustive AI revenue-at-risk
  calculations.
- Password-reset delivery is admin/support-mediated, not a complete email delivery
  workflow. API-key management, forecast-revision notifications, AI-recommendation
  notifications, and full before/after audit diffs remain incomplete or unverified.

## Frontend gaps

- Need a page-by-page behavior audit against the current contract; route presence is
  not end-to-end verification.
- Product images, reports/PDF exports, filters/pagination on every list, responsive
  and accessibility states, and recommendation flows need evidence-based validation.
- The two copilot frontend directories duplicate source and deployment surface.
  Select one canonical deployable or introduce an explicit shared-source strategy.

## AI gaps

- No genuine pgvector RAG implementation was found. Add it only after defining the
  document corpus, embedding provider, retention, and citation contract.
- The documented streaming `execution_id` context propagation limitation remains;
  streaming logs cannot yet be reliably correlated in the same way as blocking runs.
- Live provider and production-API verification is intentionally unperformed in this
  audit to respect quota discipline. Existing mocked provider, fallback, citation,
  and replan tests pass.

## Deployment gaps

- Live Railway/Render/Vercel configuration, environment values, CORS origins, JWT
  session behavior, database migrations, health checks, and error tracking are not
  verified from this workspace.
- Render configuration and deployment documentation disagree on target terminology
  and session/cookie approach; reconcile them with the actual bearer-token contract.
- No `FINAL_REPORT.md` exists yet.

## Recommended implementation order

1. Fix the migration verification path and bring the local Core development database
   safely to head; add migration tests that cover both online upgrade and offline SQL
   generation where supported.
2. Restore clean ruff, format, and mypy gates without weakening strictness or
   overwriting the user's uncommitted verification-script changes.
3. Complete and capture Core pytest plus all production builds; reduce ERP lint
   warnings to zero and make test environment diagnostics intentional.
4. Audit each ERP route against the generated OpenAPI contract, then fill only
   confirmed behavior gaps with API-backed tests.
5. Resolve duplicate AI-frontend ownership and document one deployment topology.
6. Design and implement real pgvector RAG with source-grounded citations, then add
   retrieval and provenance regression tests.
7. Add E2E, accessibility, performance, deployment, and live smoke verification;
   rotate/remove credential-like values from versioned deployment configuration under
   deployment-owner authorization.
