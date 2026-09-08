"""Task 3.6: GET /health (liveness, unchanged since Task 2.1) and GET
/health/deep (readiness) -- checks the two real dependencies this
service has (its own Postgres, StockPilot) independently, without ever
raising past this route just because one of them is down. StockPilot
being unreachable here is reported the same way it degrades everywhere
else in this task (named explicitly, not a crash): /health/deep still
returns 200 with status="degraded" rather than 5xx, since RetailOps AI
itself is still up and can serve degraded answers per this task's own
failure-behaviour rules -- only its own database being unreachable is
this service's own outage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from api.deps import get_db_session_factory, get_stockpilot_client
from clients.stockpilot import StockPilotClient, StockPilotUnavailableError

SERVICE_ROOT = Path(__file__).resolve().parent.parent

router = APIRouter(tags=["health"])


class DeepHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    database: str
    stockpilot: str


def _get_app_version() -> str:
    pyproject = SERVICE_ROOT / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version ="):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"


APP_VERSION = _get_app_version()


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "retailops-ai"
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="retailops-ai",
        version=APP_VERSION,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/health/deep", response_model=DeepHealthResponse)
def health_deep(
    client: StockPilotClient = Depends(get_stockpilot_client),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> DeepHealthResponse:
    session = session_factory()
    try:
        session.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as exc:  # noqa: BLE001 -- reported below, not re-raised
        database_status = f"error: {exc}"
    finally:
        session.close()

    try:
        client.health()
        stockpilot_status = "ok"
    except StockPilotUnavailableError as exc:
        stockpilot_status = f"unreachable: {exc}"

    if database_status != "ok":
        overall: Literal["ok", "degraded", "error"] = "error"
    elif stockpilot_status != "ok":
        overall = "degraded"
    else:
        overall = "ok"

    return DeepHealthResponse(
        status=overall, database=database_status, stockpilot=stockpilot_status
    )
