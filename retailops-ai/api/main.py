from fastapi import FastAPI

from logging_config import configure_logging

configure_logging()

app = FastAPI(title="RetailOps AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
