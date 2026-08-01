from fastapi import FastAPI

from api.routers import (
    analytics,
    audit_logs,
    auth,
    brands,
    categories,
    customers,
    forecast,
    inventory,
    notifications,
    products,
    purchase_orders,
    roles,
    sales_orders,
    settings,
    suppliers,
    users,
    warehouses,
)

app = FastAPI(title="StockPilot Core")

app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(suppliers.router)
app.include_router(warehouses.router)
app.include_router(inventory.router)
app.include_router(purchase_orders.router)
app.include_router(customers.router)
app.include_router(sales_orders.sales_orders_router)
app.include_router(sales_orders.invoices_router)
app.include_router(analytics.router)
app.include_router(forecast.router)
app.include_router(roles.router)
app.include_router(users.router)
app.include_router(audit_logs.router)
app.include_router(notifications.router)
app.include_router(settings.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
