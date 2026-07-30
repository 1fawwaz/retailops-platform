from fastapi import FastAPI

from api import agent, health, recommendations, workflows
from api.errors import unhandled_exception_handler
from logging_config import configure_logging

configure_logging()

app = FastAPI(title="RetailOps AI")

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
