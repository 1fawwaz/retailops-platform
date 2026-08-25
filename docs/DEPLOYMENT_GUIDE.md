# StockPilot AI v3.4 — Cloud Deployment Guide

This guide details the deployment procedure for **StockPilot AI v3.4**, including Vercel frontend deployment, Railway backend deployment, managed PostgreSQL configuration, CORS/HTTPS/Cookie setup, health checks, and rollback procedures.

---

## 1. Environment Architecture & Topology

```
                  ┌─────────────────────────────────────────┐
                  │          StockPilot Frontend            │
                  │             (Vercel)                    │
                  └──────────────────┬──────────────────────┘
                                     │ (HTTPS / httpOnly Cookie)
                  ┌──────────────────┴──────────────────────┐
                  │                                         │
                  ▼                                         ▼
   ┌─────────────────────────────┐           ┌─────────────────────────────┐
   │       StockPilot Core       │           │        RetailOps AI         │
   │       (Railway App 1)       │           │       (Railway App 2)       │
   └──────────────┬──────────────┘           └──────────────┬──────────────┘
                  │                                         │
                  └──────────────────┬──────────────────────┘
                                     ▼
                      ┌─────────────────────────────┐
                      │     Managed PostgreSQL      │
                      │     (Railway / AWS RDS)     │
                      └─────────────────────────────┘
```

---

## 2. Environment Variables Configuration

### A. `stockpilot-core` (Railway / Production Server)

| Variable | Description | Example / Required Setting |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/stockpilot` |
| `JWT_SECRET` | 256-bit secret key for JWT signing | `<high-entropy-random-secret>` |
| `JWT_ALGORITHM` | Algorithm for JWT | `HS256` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend domains | `https://stockpilot.vercel.app` |
| `COOKIE_DOMAIN` | Shared parent domain for httpOnly SSO cookies | `.stockpilot.com` (or `None` for single domain) |
| `COOKIE_SECURE` | Enforce HTTPS for cookies | `True` |
| `COOKIE_SAMESITE` | Cookie SameSite policy | `lax` |

### B. `retailops-ai` (Railway / Production Server)

| Variable | Description | Example / Required Setting |
|---|---|---|
| `RETAILOPS_DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/stockpilot` |
| `STOCKPILOT_BASE_URL` | Internal URL for `stockpilot-core` service | `http://stockpilot-core.railway.internal:8000` |
| `GROQ_API_KEY_1..N` | Groq LLM rotation key pool | `gsk_...` |
| `GEMINI_API_KEY_1..N` | Gemini LLM rotation key pool | `AIzaSy...` |
| `JWT_SECRET` | Must match `stockpilot-core` `JWT_SECRET` | `<shared-high-entropy-secret>` |
| `REQUEST_TIMEOUT_SECONDS` | Maximum request timeout for agent execution | `300.0` |

### C. `stockpilot-frontend` (Vercel)

| Variable | Description | Example / Required Setting |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Public HTTPS URL for `stockpilot-core` | `https://api.stockpilot.com` |
| `NEXT_PUBLIC_AI_BASE_URL` | Public HTTPS URL for `retailops-ai` | `https://ai.stockpilot.com` |

---

## 3. Database Migration & Startup

Automatic Alembic migrations run on backend startup before serving requests.

```bash
# Run database migrations manually or in deployment pipeline
cd stockpilot-core && alembic upgrade head
cd ../retailops-ai && alembic upgrade head
```

---

## 4. Health Check Endpoints

Both services expose `/health` endpoints for Railway/Vercel liveness and readiness probes:

- `GET https://api.stockpilot.com/health` → `{"status": "ok"}`
- `GET https://ai.stockpilot.com/health` → `{"status": "ok"}`

---

## 5. Rollback Plan

1. **Database Rollback**:
   - Alembic supports downgrade steps: `alembic downgrade -1`.
   - Automated daily snapshots are maintained on the managed PostgreSQL instance.

2. **Backend Services (Railway)**:
   - Rollback to previous deployment tag via Railway Dashboard → Deployments → Rollback.

3. **Frontend (Vercel)**:
   - Instant rollback via Vercel Dashboard → Deployments → Promote Previous to Production.
