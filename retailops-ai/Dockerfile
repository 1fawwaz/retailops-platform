# ── retailops-ai ───────────────────────────────────────────────────────────────
# Build context: repo/retailops-platform/ (Monorepo root on Render)
# Working directory for service: /app/retailops-ai
FROM python:3.11-slim

# System deps: libpq5 for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install production dependencies explicitly
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

# Copy monorepo files into /app
COPY . .

# Set working directory to retailops-ai where alembic.ini, api/, agents/ live
WORKDIR /app/retailops-ai

ENV PYTHONPATH="/app/retailops-ai:/app"

EXPOSE 8001

# Shell form so ${PORT:-8001} is expanded by sh — Render injects PORT at runtime
CMD if [ -d "/app/retailops-ai" ]; then cd /app/retailops-ai; fi && alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8001}
