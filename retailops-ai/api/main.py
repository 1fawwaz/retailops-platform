import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import agent, health, recommendations, workflows
from api.errors import unhandled_exception_handler
from llm.providers.startup import validate_configured_models
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Stage 6 Task 6.4: "On boot, the service validates every configured
    # model ID (all roles plus fallback) against its provider's
    # model-list endpoint and fails fast..." -- confirmed live that a
    # bare TestClient(app) (this whole test suite's own pattern) never
    # triggers this at all, only a real server boot does.
    validate_configured_models()
    logger.info("Startup model validation passed for every configured role and fallback.")
    yield


app = FastAPI(title="RetailOps AI", lifespan=_lifespan)

# Stage 6 backend hardening: the last line of defense before a raw
# exception (and whatever sensitive detail it carries) would otherwise
# reach an HTTP response body -- see api/errors.py's own docstring for
# why this does NOT interfere with the 404s/401s/429s already raised as
# HTTPException elsewhere in this app.
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(agent.router)
app.include_router(health.router)
app.include_router(recommendations.router)
app.include_router(workflows.router)
