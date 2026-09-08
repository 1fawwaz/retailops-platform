# syntax=docker/dockerfile:1
# ── retailops-ai ───────────────────────────────────────────────────────────────
# Build context: repo root (retailops-platform/)
# Dockerfile path: retailops-ai/Dockerfile
# WORKDIR is /app/retailops-ai so all relative imports work as in local dev.
FROM python:3.11-slim

# System deps: libpq5 for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy the service directory (includes pyproject.toml, alembic/, api/, agents/, etc.)
COPY retailops-ai/ ./retailops-ai/

# 2. Install production dependencies explicitly.
#    The app code is NOT a package — it runs as flat modules from WORKDIR.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        "fastapi==0.140.8" \
        "uvicorn[standard]==0.51.0" \
        "pydantic==2.13.4" \
        "pydantic-settings==2.14.2" \
        "sqlalchemy==2.0.51" \
        "alembic==1.18.5" \
        "psycopg[binary]==3.3.4" \
        "python-dotenv==1.2.2" \
        "httpx2==2.9.1" \
        "httpx==0.28.1" \
        "email-validator==2.3.0" \
        "langchain-core==1.5.2" \
        "langgraph==1.2.10" \
        "google-genai==2.14.0" \
        "groq==1.6.0" \
        "pyyaml==6.0.3" \
        "pyjwt==2.13.0"

WORKDIR /app/retailops-ai

EXPOSE 8001

# Run migrations then start the API server.
# RETAILOPS_DATABASE_URL must be provided as an environment variable by Render.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8001"]
