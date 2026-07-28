from fastapi import FastAPI

app = FastAPI(title="RetailOps AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
