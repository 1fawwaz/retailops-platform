from fastapi import FastAPI

from api import agent, health, recommendations, workflows
from logging_config import configure_logging

configure_logging()

app = FastAPI(title="RetailOps AI")

app.include_router(agent.router)
app.include_router(health.router)
app.include_router(recommendations.router)
app.include_router(workflows.router)
