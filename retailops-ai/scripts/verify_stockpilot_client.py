"""Stage 2 Task 2.2 milestone check: a live call to every StockPilot
endpoint succeeds and returns a validated typed object.

Requires a running stockpilot-core instance (STOCKPILOT_BASE_URL) with a
populated database. Registers a throwaway write-capable user via the
client itself (unauthenticated /auth/register) so create/update/delete
endpoints can be verified too, alongside the read-only demo account
Settings normally configures. Not a pytest test: this is a one-time,
reproducible interactive check against a live dependency, the same
category as stockpilot-core's scripts/train_forecast_model.py --
pytest's suite stays hermetic and skip-free.

Run: python scripts/verify_stockpilot_client.py
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.stockpilot import StockPilotClient  # noqa: E402
from clients.stockpilot_models import (  # noqa: E402
    ProductCreate,
    ProductUpdate,
    SupplierCreate,
    SupplierUpdate,
)
from settings import get_settings  # noqa: E402

T = TypeVar("T")

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, func: Callable[[], T]) -> T | None:
    try:
        result = func()
        RESULTS.append((name, True, ""))
        return result
    except Exception as exc:  # noqa: BLE001 -- this script reports every failure, doesn't handle any
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        return None


def main() -> None:
    settings = get_settings()
    test_email = f"client-verify-{uuid.uuid4().hex[:8]}@example.com"
    test_password = "verify-hunter-2!!"
    test_sku = f"VERIFY-{uuid.uuid4().hex[:8].upper()}"
    test_supplier_name = f"Verify Supplier {uuid.uuid4().hex[:8]}"

    with StockPilotClient(
        base_url=settings.stockpilot_base_url,
        username=test_email,
        password=test_password,
    ) as write_client:
        check("health", write_client.health)
        check("register_user", lambda: write_client.register_user(test_email, test_password))

        check(
            "create_product",
            lambda: write_client.create_product(ProductCreate(sku=test_sku, description="verify")),
        )
        check("get_product", lambda: write_client.get_product(test_sku))
        check(
            "update_product",
            lambda: write_client.update_product(test_sku, ProductUpdate(description="verify2")),
        )

        created_supplier = check(
            "create_supplier",
            lambda: write_client.create_supplier(
                SupplierCreate(name=test_supplier_name, lead_time_days=5, reliability_score=0.9)
            ),
        )
        supplier_id = created_supplier.id if created_supplier is not None else None
        if supplier_id is not None:
            check("get_supplier", lambda: write_client.get_supplier(supplier_id))
            check(
                "update_supplier",
                lambda: write_client.update_supplier(
                    supplier_id,
                    SupplierUpdate(
                        name=f"{test_supplier_name} (updated)",
                        lead_time_days=6,
                        reliability_score=0.91,
                    ),
                ),
            )

        check("list_products", lambda: write_client.list_products(limit=5))
        check("list_suppliers", lambda: write_client.list_suppliers(limit=5))

        check("get_stock", lambda: write_client.get_stock(limit=5))
        check("get_low_stock", write_client.get_low_stock)
        check("get_dead_stock", write_client.get_dead_stock)
        check("get_slow_movers", write_client.get_slow_movers)
        check("get_inventory_valuation", write_client.get_inventory_valuation)

        check("get_revenue", write_client.get_revenue)
        check("get_profit", write_client.get_profit)
        check("get_turnover", write_client.get_turnover)
        check("get_abc", write_client.get_abc)
        check("get_top_products", write_client.get_top_products)
        check("get_bottom_products", write_client.get_bottom_products)

        products = check("list_products_for_forecast", lambda: write_client.list_products(limit=3))
        skus = [p.sku for p in products] if products else []
        if skus:
            check("forecast_demand", lambda: write_client.forecast_demand(skus, horizon_days=7))
        check("get_forecast_accuracy", write_client.get_forecast_accuracy)

        if supplier_id is not None:
            check("delete_supplier", lambda: write_client.delete_supplier(supplier_id))
        check("delete_product", lambda: write_client.delete_product(test_sku))

    print(f"{'ENDPOINT':<28} {'RESULT':<6} DETAIL")
    print("-" * 80)
    all_passed = True
    for name, passed, detail in RESULTS:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"{name:<28} {status:<6} {detail}")

    print("-" * 80)
    print(f"{len(RESULTS)} checks, {sum(1 for _, p, _ in RESULTS if p)} passed")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
