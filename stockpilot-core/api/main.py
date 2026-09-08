import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from settings import get_settings

app_settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stockpilot_core")
logger.info(
    "StockPilot Core starting with allowed origins: %s (regex: %s)",
    app_settings.cors_allowed_origins_list,
    app_settings.cors_allowed_origin_regex,
)

app = FastAPI(title="StockPilot Core")

# docs/ARCHITECTURE.md § CORS: only the known frontend origins, backend-
# owned config -- see settings.py's cors_allowed_origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_allowed_origins_list,
    allow_origin_regex=app_settings.cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


SERVICE_ROOT = Path(__file__).resolve().parent.parent


def _get_app_version() -> str:
    pyproject = SERVICE_ROOT / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version ="):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"


APP_VERSION = _get_app_version()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "StockPilot Core API",
        "status": "online",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "stockpilot-core",
        "version": APP_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }
