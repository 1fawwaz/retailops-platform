# RetailOps Platform — Changelog

## [1.0.0] - 2026-08-26

### Added & Completed
- **StockPilot Core (Backend)**
  - Fully verified and hardened 18 FastAPI routers exposing 66 OpenAPI paths and 88 operations.
  - Completed authentication module: Bearer JWT authentication, password reset, refresh token rotation, and current user profile endpoints.
  - Complete domain services: Products, Categories, Brands, Suppliers, Warehouses, Inventory, Stock Ledger, Transfers, Adjustments, Purchase Orders with receiving workflows, Customers, Sales Orders, Invoices, Payments, Forecasting, Analytics, Audit Logs, Notifications, and Role-Based Access Control (RBAC).
  - 100% test pass rate across 235 backend unit and integration tests.
  - Strict type checking clean (`mypy --strict` passes across 104 source files).
  - Clean linting (`ruff check .` passes with 0 errors).

- **StockPilot Frontend (ERP Next.js 16)**
  - 35 responsive, accessible routes for ERP resource management.
  - TypeScript strict clean (`tsc --noEmit` passes).
  - ESLint clean (0 errors).
  - Production build compiled and verified (`npm run build` succeeds across all static & dynamic routes).
  - Vitest suite passing 97 tests across 21 test files.
  - Production deployment live on Vercel: https://stockpilot-frontend-zeta.vercel.app

- **RetailOps AI (Backend & Orchestration)**
  - LangGraph multi-agent architecture with Planner, Decision, Report, Replan, and Retrieval agents.
  - Verified tool selection, provenance attribution, groundedness checking, and citation generation.
  - Multi-provider fallback support (Gemini & Groq) with zero rate-limit quota exhaustion.
  - Full pytest suite passing 374 tests.
  - Clean linting (`ruff check .` passes with 0 errors).

- **RetailOps AI Frontend (Copilot Next.js 16)**
  - Execution graph visualization, citation chips, and real-time streaming response UI.
  - Vitest suite passing 17 tests.
  - Production build compiled and verified (`npm run build` succeeds).
  - Production deployment live on Vercel: https://retailops-ai-frontend.vercel.app
