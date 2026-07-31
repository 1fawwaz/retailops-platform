from fastapi import FastAPI

from api.routers import (
    analytics,
    auth,
    brands,
    categories,
    forecast,
    inventory,
    products,
    suppliers,
)

app = FastAPI(title="StockPilot Core")

app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(suppliers.router)
app.include_router(inventory.router)
app.include_router(analytics.router)
app.include_router(forecast.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
