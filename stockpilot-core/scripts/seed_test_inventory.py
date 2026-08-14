"""Deterministic test inventory seed script.

Creates a reproducible inventory test scenario covering all required cases:
  A — Healthy stock    (quantity_on_hand > reorder_point)
  B — Low stock        (quantity_on_hand <= reorder_point)
  C — Stockout         (quantity_on_hand = 0)
  D — Dead stock       (no movement in the configured historical window)
  E — Slow movers      (low but non-zero historical demand)
  F — Different costs  (varying unit_costs for valuation testing)
  G — Different suppliers (varying lead times and reliability)
  H — Multi-warehouse  (Main + Secondary with deterministic allocation)

Provenance: every record created here is explicitly synthetic/test data,
labelled so it is never confused with the observed Online Retail II dataset.
The historical ETL data is NOT modified or replaced.

Usage:
    python scripts/seed_test_inventory.py

Requires a running PostgreSQL database with the schema already migrated.
The script is idempotent: re-running it drops and recreates only the
test-scenario data (rows with test SKUs prefixed 'TEST-INV-').

RANDOM_SEED = 42 for reproducibility, matching the project convention.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import get_session_factory  # noqa: E402
from models.brand import Brand  # noqa: E402
from models.category import Category  # noqa: E402
from models.product import Product  # noqa: E402
from models.stock_level import StockLevel  # noqa: E402
from models.stock_movement import StockMovement  # noqa: E402
from models.supplier import Supplier  # noqa: E402
from models.warehouse import Warehouse  # noqa: E402

# ─── Constants ───────────────────────────────────────────────────────
SEED = 42
TEST_SKU_PREFIX = "TEST-INV-"
TEST_CATEGORY_NAME = "Test Inventory Scenario"
TEST_BRAND_NAME = "Test Brand"

# Historical reference date for window-based analytics.
# The Online Retail II dataset ends on 2011-12-09; dead-stock and
# slow-mover windows should be computed relative to this date when
# analysing the historical data, not the machine's current date.
HISTORICAL_AS_OF_DATE = datetime(2011, 12, 9, 23, 59, 59)

# Scenario reference date: "today" for the test scenario
SCENARIO_DATE = date(2026, 8, 1)


@dataclass(frozen=True)
class SupplierSpec:
    name: str
    lead_time_days: int
    reliability_score: float


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    description: str
    unit_cost: float
    sale_price: float
    reorder_point: int
    safety_stock: int
    supplier_name: str
    scenario: str


@dataclass(frozen=True)
class StockSpec:
    sku: str
    warehouse_name: str
    quantity_on_hand: int


@dataclass(frozen=True)
class MovementSpec:
    sku: str
    warehouse_name: str
    movement_date: datetime
    quantity_delta: int
    movement_type: str
    reference: str | None
    provenance: str


# ─── Supplier definitions (Scenario G) ──────────────────────────────
SUPPLIERS: list[SupplierSpec] = [
    # Fast, reliable supplier
    SupplierSpec("Test Supplier Alpha", lead_time_days=3, reliability_score=0.95),
    # Slow, less reliable supplier
    SupplierSpec("Test Supplier Beta", lead_time_days=14, reliability_score=0.85),
    # Medium lead time
    SupplierSpec("Test Supplier Gamma", lead_time_days=7, reliability_score=0.92),
]

# ─── Product definitions (Scenarios A-F, G) ─────────────────────────
PRODUCTS: list[ProductSpec] = [
    # Scenario A — Healthy stock: 200 on hand, reorder_point=50
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}001",
        description="Healthy Stock Widget Alpha",
        unit_cost=12.50,
        sale_price=24.99,
        reorder_point=50,
        safety_stock=20,
        supplier_name="Test Supplier Alpha",
        scenario="A",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}002",
        description="Healthy Stock Widget Beta",
        unit_cost=8.75,
        sale_price=18.50,
        reorder_point=30,
        safety_stock=10,
        supplier_name="Test Supplier Gamma",
        scenario="A",
    ),
    # Scenario B — Low stock: 5 on hand, reorder_point=20
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}003",
        description="Low Stock Gadget Alpha",
        unit_cost=25.00,
        sale_price=49.99,
        reorder_point=20,
        safety_stock=8,
        supplier_name="Test Supplier Beta",
        scenario="B",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}004",
        description="Low Stock Gadget Beta",
        unit_cost=3.20,
        sale_price=7.99,
        reorder_point=15,
        safety_stock=5,
        supplier_name="Test Supplier Alpha",
        scenario="B",
    ),
    # Scenario C — Stockout: 0 on hand
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}005",
        description="Stockout Item Alpha",
        unit_cost=15.00,
        sale_price=32.00,
        reorder_point=25,
        safety_stock=10,
        supplier_name="Test Supplier Gamma",
        scenario="C",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}006",
        description="Stockout Item Beta",
        unit_cost=6.80,
        sale_price=14.99,
        reorder_point=10,
        safety_stock=4,
        supplier_name="Test Supplier Alpha",
        scenario="C",
    ),
    # Scenario D — Dead stock: on hand but no movement in window
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}007",
        description="Dead Stock Relic Alpha",
        unit_cost=45.00,
        sale_price=89.99,
        reorder_point=5,
        safety_stock=2,
        supplier_name="Test Supplier Beta",
        scenario="D",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}008",
        description="Dead Stock Relic Beta",
        unit_cost=2.10,
        sale_price=5.50,
        reorder_point=10,
        safety_stock=3,
        supplier_name="Test Supplier Gamma",
        scenario="D",
    ),
    # Scenario E — Slow movers: low demand, still selling
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}009",
        description="Slow Mover Alpha",
        unit_cost=18.00,
        sale_price=35.00,
        reorder_point=8,
        safety_stock=3,
        supplier_name="Test Supplier Alpha",
        scenario="E",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}010",
        description="Slow Mover Beta",
        unit_cost=9.90,
        sale_price=22.00,
        reorder_point=12,
        safety_stock=4,
        supplier_name="Test Supplier Gamma",
        scenario="E",
    ),
    # Scenario F — Different costs: varying unit_costs for valuation
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}011",
        description="High Value Item",
        unit_cost=150.00,
        sale_price=299.99,
        reorder_point=3,
        safety_stock=1,
        supplier_name="Test Supplier Beta",
        scenario="F",
    ),
    ProductSpec(
        sku=f"{TEST_SKU_PREFIX}012",
        description="Low Value Item",
        unit_cost=0.50,
        sale_price=1.99,
        reorder_point=100,
        safety_stock=30,
        supplier_name="Test Supplier Alpha",
        scenario="F",
    ),
]

# ─── Stock allocation (Scenarios A-F, H) ────────────────────────────
STOCK_LEVELS: list[StockSpec] = [
    # Scenario A — Healthy
    StockSpec(f"{TEST_SKU_PREFIX}001", "Main Warehouse", 200),
    StockSpec(f"{TEST_SKU_PREFIX}002", "Main Warehouse", 75),
    # Scenario B — Low
    StockSpec(f"{TEST_SKU_PREFIX}003", "Main Warehouse", 5),
    StockSpec(f"{TEST_SKU_PREFIX}004", "Main Warehouse", 3),
    # Scenario C — Stockout (zero on hand)
    StockSpec(f"{TEST_SKU_PREFIX}005", "Main Warehouse", 0),
    StockSpec(f"{TEST_SKU_PREFIX}006", "Main Warehouse", 0),
    # Scenario D — Dead stock
    StockSpec(f"{TEST_SKU_PREFIX}007", "Main Warehouse", 30),
    StockSpec(f"{TEST_SKU_PREFIX}008", "Main Warehouse", 50),
    # Scenario E — Slow movers
    StockSpec(f"{TEST_SKU_PREFIX}009", "Main Warehouse", 40),
    StockSpec(f"{TEST_SKU_PREFIX}010", "Main Warehouse", 25),
    # Scenario F — Different costs
    StockSpec(f"{TEST_SKU_PREFIX}011", "Main Warehouse", 8),
    StockSpec(f"{TEST_SKU_PREFIX}012", "Main Warehouse", 500),
    # Scenario H — Multi-warehouse: split stock across two warehouses
    StockSpec(f"{TEST_SKU_PREFIX}001", "Secondary Warehouse", 30),
    StockSpec(f"{TEST_SKU_PREFIX}003", "Secondary Warehouse", 2),
    StockSpec(f"{TEST_SKU_PREFIX}011", "Secondary Warehouse", 4),
]

# ─── Stock movements ────────────────────────────────────────────────
# These create the historical movement pattern that the dead-stock,
# slow-mover, and ledger queries will analyse.
# Reference date for movements: 2011-12-09 (matching the real dataset's
# last business date, so the as_of_date logic works correctly).
MOVEMENT_DATE_BASE = datetime(2011, 12, 9)


def _build_movements() -> list[MovementSpec]:
    """Build the full movement history for every test SKU.

    Each scenario gets a specific movement pattern:
    - A (healthy): frequent recent sales
    - B (low): recent sales exceeding reorder
    - C (stockout): recent sales draining stock to zero
    - D (dead): no movement in the last 200 days
    - E (slow): very infrequent sales
    - F (different costs): standard sales pattern
    - H (multi-warehouse): transfers between warehouses
    """
    movements: list[MovementSpec] = []

    def add(
        sku: str,
        warehouse: str,
        days_offset: int,
        qty: int,
        mtype: str,
        ref: str | None = None,
        prov: str = "observed",
    ) -> None:
        movements.append(
            MovementSpec(
                sku=sku,
                warehouse_name=warehouse,
                movement_date=MOVEMENT_DATE_BASE + timedelta(days=days_offset),
                quantity_delta=qty,
                movement_type=mtype,
                reference=ref,
                provenance=prov,
            )
        )

    # ── Scenario A: Healthy stock — frequent sales, well above reorder ──
    # Opening balance of 230, sell ~30 total → end at 200
    add(f"{TEST_SKU_PREFIX}001", "Main Warehouse", -60, 230, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}001", "Main Warehouse", -30, -8, "sale")
    add(f"{TEST_SKU_PREFIX}001", "Main Warehouse", -20, -6, "sale")
    add(f"{TEST_SKU_PREFIX}001", "Main Warehouse", -10, -10, "sale")
    add(f"{TEST_SKU_PREFIX}001", "Main Warehouse", -5, -6, "sale")

    # Opening balance of 80, sell ~5 → end at 75
    add(f"{TEST_SKU_PREFIX}002", "Main Warehouse", -45, 80, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}002", "Main Warehouse", -15, -5, "sale")

    # ── Scenario B: Low stock — recent sales pushing below reorder ──
    # Opening balance of 25, sell 20 → end at 5 (below reorder_point=20)
    add(f"{TEST_SKU_PREFIX}003", "Main Warehouse", -30, 25, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}003", "Main Warehouse", -10, -10, "sale")
    add(f"{TEST_SKU_PREFIX}003", "Main Warehouse", -5, -10, "sale")

    # Opening balance of 12, sell 9 → end at 3 (below reorder_point=15)
    add(f"{TEST_SKU_PREFIX}004", "Main Warehouse", -20, 12, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}004", "Main Warehouse", -8, -5, "sale")
    add(f"{TEST_SKU_PREFIX}004", "Main Warehouse", -3, -4, "sale")

    # ── Scenario C: Stockout — sales drain stock to zero ──
    # Opening balance of 30, sell 30 → end at 0
    add(f"{TEST_SKU_PREFIX}005", "Main Warehouse", -25, 30, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}005", "Main Warehouse", -15, -15, "sale")
    add(f"{TEST_SKU_PREFIX}005", "Main Warehouse", -5, -15, "sale")

    # Opening balance of 15, sell 15 → end at 0
    add(f"{TEST_SKU_PREFIX}006", "Main Warehouse", -20, 15, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}006", "Main Warehouse", -10, -8, "sale")
    add(f"{TEST_SKU_PREFIX}006", "Main Warehouse", -3, -7, "sale")

    # ── Scenario D: Dead stock — last movement > 90 days ago ──
    # Movement at day -200, no subsequent movement
    add(f"{TEST_SKU_PREFIX}007", "Main Warehouse", -200, 30, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}008", "Main Warehouse", -150, 50, "opening_balance", prov="derived")

    # ── Scenario E: Slow movers — very infrequent sales ──
    # 2 sales in 90 days = ~0.022/day (well below 0.2 threshold)
    add(f"{TEST_SKU_PREFIX}009", "Main Warehouse", -90, 42, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}009", "Main Warehouse", -60, -1, "sale")
    add(f"{TEST_SKU_PREFIX}009", "Main Warehouse", -15, -1, "sale")

    # 1 sale in 90 days = ~0.011/day
    add(f"{TEST_SKU_PREFIX}010", "Main Warehouse", -80, 26, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}010", "Main Warehouse", -40, -1, "sale")

    # ── Scenario F: Different costs — standard movement pattern ──
    add(f"{TEST_SKU_PREFIX}011", "Main Warehouse", -30, 12, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}011", "Main Warehouse", -10, -4, "sale")

    add(f"{TEST_SKU_PREFIX}012", "Main Warehouse", -40, 500, "opening_balance", prov="derived")
    add(f"{TEST_SKU_PREFIX}012", "Main Warehouse", -20, -50, "sale")
    add(f"{TEST_SKU_PREFIX}012", "Main Warehouse", -10, -100, "sale")
    add(f"{TEST_SKU_PREFIX}012", "Main Warehouse", -5, -50, "sale")

    # ── Scenario H: Multi-warehouse — transfers ──
    # Transfer 30 units of TEST-INV-001 from Main to Secondary
    add(
        f"{TEST_SKU_PREFIX}001",
        "Main Warehouse",
        -2,
        -30,
        "transfer",
        ref="Inter-warehouse rebalance",
    )
    add(
        f"{TEST_SKU_PREFIX}001",
        "Secondary Warehouse",
        -2,
        30,
        "transfer",
        ref="Inter-warehouse rebalance",
    )

    # Transfer 2 units of TEST-INV-003 from Main to Secondary
    add(
        f"{TEST_SKU_PREFIX}003",
        "Main Warehouse",
        -1,
        -2,
        "transfer",
        ref="Low-stock redistribution",
    )
    add(
        f"{TEST_SKU_PREFIX}003",
        "Secondary Warehouse",
        -1,
        2,
        "transfer",
        ref="Low-stock redistribution",
    )

    # Transfer 4 units of TEST-INV-011 from Main to Secondary
    add(f"{TEST_SKU_PREFIX}011", "Main Warehouse", -3, -4, "transfer", ref="High-value split")
    add(f"{TEST_SKU_PREFIX}011", "Secondary Warehouse", -3, 4, "transfer", ref="High-value split")

    return movements


MOVEMENTS = _build_movements()


def _clear_test_data(session: Session) -> None:
    """Remove only test-scenario rows (SKUs prefixed TEST-INV-)."""
    test_skus = [p.sku for p in PRODUCTS]
    placeholders = ", ".join([f":sku_{i}" for i in range(len(test_skus))])
    params = {f"sku_{i}": sku for i, sku in enumerate(test_skus)}

    for table in ["stock_movements", "stock_levels", "products"]:
        session.execute(text(f"DELETE FROM {table} WHERE sku IN ({placeholders})"), params)

    session.execute(
        text("DELETE FROM suppliers WHERE name LIKE 'Test Supplier%'"),
    )
    session.execute(
        text("DELETE FROM categories WHERE name = :cat_name"),
        {"cat_name": TEST_CATEGORY_NAME},
    )
    session.execute(
        text("DELETE FROM brands WHERE name = :brand_name"),
        {"brand_name": TEST_BRAND_NAME},
    )
    session.commit()


def seed_test_inventory() -> None:
    """Main seed function. Idempotent: clears existing test data first."""
    session = get_session_factory()()

    try:
        print("Clearing existing test inventory data...")
        _clear_test_data(session)

        # ── Warehouses ─────────────────────────────────────────────
        print("Ensuring warehouses exist...")
        main_wh = session.scalar(text("SELECT id FROM warehouses WHERE name = 'Main Warehouse'"))
        if main_wh is None:
            wh = Warehouse(name="Main Warehouse")
            session.add(wh)
            session.flush()
            main_wh = wh.id

        secondary_wh = session.scalar(
            text("SELECT id FROM warehouses WHERE name = 'Secondary Warehouse'")
        )
        if secondary_wh is None:
            wh = Warehouse(name="Secondary Warehouse")
            session.add(wh)
            session.flush()
            secondary_wh = wh.id

        warehouse_ids = {
            "Main Warehouse": int(main_wh),
            "Secondary Warehouse": int(secondary_wh),
        }
        print(f"  Main Warehouse: id={main_wh}")
        print(f"  Secondary Warehouse: id={secondary_wh}")

        # ── Brand ──────────────────────────────────────────────────
        brand = Brand(name=TEST_BRAND_NAME)
        session.add(brand)
        session.flush()
        print(f"  Brand: {TEST_BRAND_NAME} (id={brand.id})")

        # ── Category ───────────────────────────────────────────────
        category = Category(name=TEST_CATEGORY_NAME)
        session.add(category)
        session.flush()
        print(f"  Category: {TEST_CATEGORY_NAME} (id={category.id})")

        # ── Suppliers (Scenario G) ─────────────────────────────────
        print("Creating test suppliers...")
        supplier_ids: dict[str, int] = {}
        for spec in SUPPLIERS:
            supplier = Supplier(
                name=spec.name,
                lead_time_days=spec.lead_time_days,
                reliability_score=spec.reliability_score,
            )
            session.add(supplier)
            session.flush()
            supplier_ids[spec.name] = supplier.id
            print(
                f"  {spec.name}: lead_time={spec.lead_time_days}d, "
                f"reliability={spec.reliability_score:.2f} (id={supplier.id})"
            )

        # ── Products (Scenarios A-F) ───────────────────────────────
        print("Creating test products...")
        for product_spec in PRODUCTS:
            product = Product(
                sku=product_spec.sku,
                description=product_spec.description,
                category_id=category.id,
                brand_id=brand.id,
                supplier_id=supplier_ids[product_spec.supplier_name],
                unit_cost=product_spec.unit_cost,
                sale_price=product_spec.sale_price,
                reorder_point=product_spec.reorder_point,
                safety_stock=product_spec.safety_stock,
            )
            session.add(product)
        session.flush()
        print(f"  {len(PRODUCTS)} products created")

        # ── Stock Levels ───────────────────────────────────────────
        print("Creating stock levels...")
        for stock_spec in STOCK_LEVELS:
            wh_id = warehouse_ids[stock_spec.warehouse_name]
            sl = StockLevel(
                sku=stock_spec.sku,
                warehouse_id=wh_id,
                as_of_date=SCENARIO_DATE,
                quantity_on_hand=stock_spec.quantity_on_hand,
            )
            session.add(sl)
        session.flush()
        print(f"  {len(STOCK_LEVELS)} stock level rows created")

        # ── Stock Movements ────────────────────────────────────────
        print("Creating stock movements...")
        for mov in MOVEMENTS:
            wh_id = warehouse_ids[mov.warehouse_name]
            sm = StockMovement(
                sku=mov.sku,
                warehouse_id=wh_id,
                movement_date=mov.movement_date,
                quantity_delta=mov.quantity_delta,
                movement_type=mov.movement_type,
                reference=mov.reference,
                provenance=mov.provenance,
            )
            session.add(sm)
        session.flush()
        print(f"  {len(MOVEMENTS)} stock movement rows created")

        session.commit()
        print("\nSeed complete.")

        # ── Summary ────────────────────────────────────────────────
        print("\n=== Scenario Summary ===")
        print(f"  Products:  {len(PRODUCTS)}")
        print(f"  Suppliers: {len(SUPPLIERS)}")
        print(f"  Warehouses: {len(warehouse_ids)}")
        print(f"  Stock levels: {len(STOCK_LEVELS)}")
        print(f"  Stock movements: {len(MOVEMENTS)}")
        print(f"  Scenario date: {SCENARIO_DATE}")
        print(f"  Historical as_of_date: {HISTORICAL_AS_OF_DATE}")
        print()
        print("  Scenarios:")
        print("    A (Healthy):  TEST-INV-001, TEST-INV-002")
        print("    B (Low):      TEST-INV-003, TEST-INV-004")
        print("    C (Stockout): TEST-INV-005, TEST-INV-006")
        print("    D (Dead):     TEST-INV-007, TEST-INV-008")
        print("    E (Slow):     TEST-INV-009, TEST-INV-010")
        print("    F (Costs):    TEST-INV-011, TEST-INV-012")
        print("    G (Suppliers): 3 suppliers with varying lead times")
        print("    H (Multi-wh):  Main + Secondary Warehouse")
        print()
        print("  Run 'pytest tests/test_inventory.py -v' to verify.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_test_inventory()
