# StockPilot Frontend

The StockPilot ERP business application — inventory, purchasing, and sales, with an embedded AI assistant. See `../docs/PRODUCT-SPEC.md` for what this app does, `../docs/ARCHITECTURE.md` for how it's built, and `../docs/BUILD.md` for the stage-by-stage build order this repo follows. `CLAUDE.md` holds the engineering rules and Definition of Done.

## How this relates to StockPilot Core and RetailOps AI

Four deployables make up the whole platform (`docs/ARCHITECTURE.md` §1):

- **StockPilot Core** — the FastAPI backend this app calls for all business data and authentication.
- **RetailOps AI Backend** — the LangGraph agent service the embedded AI sidebar calls directly (`docs/ARCHITECTURE.md` § AI Integration Architecture).
- **This app (StockPilot Frontend)** — the ERP business UI.
- **RetailOps AI Frontend** — the standalone AI Copilot UI, a separate codebase and separate deployment.

This app never touches PostgreSQL or a backend ORM model directly — business data comes exclusively through StockPilot Core's REST API (`contracts/`).

## Status

Dashboard, Inventory, Products, and Suppliers are wired to real StockPilot Core data (typed API clients, zod boundary validation, data tables). Auth and RBAC are live: sessions come from StockPilot Core, and permissions are resolved from `/me` and cached (`lib/auth/refreshPermissions.ts`) — no hardcoded role.

**Placeholder pages** (empty-state shells, no data wired yet): Analytics, Forecasts, Purchase Orders, Sales (orders/customers), Notifications, Audit Logs, Reports, and the Settings pages. StockPilot Core already exposes these APIs (see `../contracts/`); the pages are waiting on their build stages in `../docs/BUILD.md`, not on the backend.

**Known gaps, not silently deferred:**

- Real cross-domain single sign-on with RetailOps AI Frontend is not implemented — StockPilot Core issues a bearer token in the response body, not a shared cookie. Each frontend requires its own login. See `docs/adr/001-session-management.md`.
- The AI sidebar is a reserved mount point (`components/ai-sidebar/AiSidebarMount.tsx`), not yet embedded — it ships with BUILD.md Stage 10.

## Local setup

```bash
npm install
cp .env.example .env.local   # fill in NEXT_PUBLIC_API_BASE_URL at minimum
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

See `.env.example` for the full list and `../docs/ARCHITECTURE.md` § Environment Variables for what each one is for. Every value in `.env.example` is a placeholder — real values live in Vercel's environment settings per project.

## Tests

```bash
npm run lint        # eslint
npm run typecheck   # tsc --noEmit
npm run test         # vitest (unit + integration)
npm run build        # production build
```

CI (`.github/workflows/ci.yml`) runs all four on every PR.

## Deployed instance

Not yet deployed — comes with `BUILD.md` Stage 12.
