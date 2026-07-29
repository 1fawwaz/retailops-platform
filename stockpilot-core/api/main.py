from fastapi import FastAPI

from api.routers import analytics, auth, inventory, products, suppliers

app = FastAPI(title="StockPilot Core")

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(inventory.router)
app.include_router(analytics.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
