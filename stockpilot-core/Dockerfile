# syntax=docker/dockerfile:1
# ── stockpilot-core ────────────────────────────────────────────────────────────
# Build context: repo root (retailops-platform/)
# Dockerfile path: stockpilot-core/Dockerfile
# WORKDIR is /app/stockpilot-core so all relative imports work as in local dev.
FROM python:3.11-slim

# System deps needed by psycopg binary wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy the service directory (includes pyproject.toml, alembic/, api/, etc.)
COPY stockpilot-core/ ./stockpilot-core/

# 2. Install production dependencies from the service pyproject.toml.
#    We install into the system python (no venv needed inside Docker).
#    `pip install -e .` is NOT used — the app code is NOT a package;
#    it runs as flat modules from WORKDIR.  We just need the deps.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        "fastapi==0.140.8" \
        "uvicorn[standard]==0.51.0" \
        "pydantic==2.13.4" \
        "sqlalchemy==2.0.51" \
        "alembic==1.18.5" \
        "psycopg[binary]==3.3.4" \
        "python-dotenv==1.2.2" \
        "pandas==3.0.5" \
        "numpy==2.4.6" \
        "openpyxl==3.1.5" \
        "scikit-learn==1.9.0" \
        "pydantic-settings==2.14.2" \
        "bcrypt==5.0.0" \
        "pyjwt==2.13.0" \
        "python-multipart==0.0.32" \
        "email-validator==2.3.0"

WORKDIR /app/stockpilot-core

EXPOSE 8000

# Run migrations then start the API server.
# DATABASE_URL must be provided as an environment variable by Render.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
