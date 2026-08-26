# RetailOps Platform — Deployment Guide

## Production Architecture Topology

```
                              ┌─────────────────────────┐
                              │        End User         │
                              └────────────┬────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
        ┌───────────▼────────────┐                    ┌───────────▼────────────┐
        │  StockPilot Frontend   │                    │ RetailOps AI Frontend  │
        │   (Next.js 16/Vercel)  │                    │  (Next.js 16/Vercel)   │
        └───────────┬────────────┘                    └───────────┬────────────┘
                    │                                             │
                    │ REST (JWT)                       REST / SSE │ (JWT)
                    │                                             │
        ┌───────────▼────────────┐   REST (Internal)  ┌───────────▼────────────┐
        │    StockPilot Core     │◄───────────────────┤      RetailOps AI      │
        │    (FastAPI/Render)    │                    │    (LangGraph/Render)  │
        └───────────┬────────────┘                    └────────────────────────┘
                    │
                    │ SQLAlchemy
        ┌───────────▼────────────┐
        │    Neon PostgreSQL     │
        │       Database         │
        └────────────────────────┘
```

## Live Deployment URLs

| Component | Target Platform | Live Production URL | Health Endpoint |
|---|---|---|---|
| StockPilot Frontend | Vercel | https://stockpilot-frontend-zeta.vercel.app | `/login` |
| RetailOps AI Frontend | Vercel | https://retailops-ai-frontend.vercel.app | `/login` |
| StockPilot Core API | Render | https://stockpilot-core.onrender.com | `/health` |
| RetailOps AI Backend | Render | https://retailops-ai.onrender.com | `/health` |
| PostgreSQL Database | Neon | `ep-dry-waterfall-a5v5649n.us-east-2.aws.neon.tech` | `5432` |

---

## Environment Variables Configuration

### StockPilot Core (`stockpilot-core`)
```env
DATABASE_URL=postgresql://neondb_owner:***@ep-dry-waterfall-a5v5649n.us-east-2.aws.neon.tech/neondb?sslmode=require
JWT_SECRET=production-secure-jwt-secret-key-32-bytes
JWT_ALGORITHM=HS256
CORS_ALLOWED_ORIGINS=https://stockpilot-frontend-zeta.vercel.app,https://retailops-ai-frontend.vercel.app
DEMO_USER_EMAIL=demo@retailops.local
DEMO_USER_PASSWORD=secure_demo_password
```

### RetailOps AI (`retailops-ai`)
```env
RETAILOPS_DATABASE_URL=postgresql://neondb_owner:***@ep-dry-waterfall-a5v5649n.us-east-2.aws.neon.tech/neondb?sslmode=require
STOCKPILOT_BASE_URL=https://stockpilot-core.onrender.com
JWT_SECRET=production-secure-jwt-secret-key-32-bytes
JWT_ALGORITHM=HS256
STOCKPILOT_USERNAME=demo@retailops.local
STOCKPILOT_PASSWORD=secure_demo_password
GEMINI_API_KEY_1=***
GROQ_API_KEY_1=***
LLM_PRIMARY_PROVIDER=gemini
```

### StockPilot Frontend (`stockpilot-frontend`)
```env
NEXT_PUBLIC_API_BASE_URL=https://stockpilot-core.onrender.com
NEXT_PUBLIC_AI_API_URL=https://retailops-ai.onrender.com
```

### RetailOps AI Frontend (`retailops-ai-frontend`)
```env
NEXT_PUBLIC_AI_API_URL=https://retailops-ai.onrender.com
NEXT_PUBLIC_STOCKPILOT_API_URL=https://stockpilot-core.onrender.com
```

---

## Database Migration & Seed Verification

1. Run Alembic Head Migration:
   ```bash
   python -m alembic upgrade head
   ```
2. Verify Migration Revision:
   ```bash
   python -m alembic current
   # Expected output: c80c9cae5095 (head)
   ```
