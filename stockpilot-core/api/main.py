from fastapi import FastAPI

app = FastAPI(title="StockPilot Core")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
