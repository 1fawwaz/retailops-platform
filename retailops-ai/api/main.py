from fastapi import FastAPI

from api import agent, health
from logging_config import configure_logging

configure_logging()

app = FastAPI(title="RetailOps AI")

app.include_router(agent.router)
app.include_router(health.router)
