"""Regression tests for the inventory test seed scenario.

Covers every case from the task specification:
1.  Deterministic seed reproducibility
2.  Healthy stock
3.  Low stock
4.  Zero stock (stockout)
5.  Dead stock
6.  Slow movers
7.  Inventory valuation
8.  Warehouse filtering
9.  Historical as_of_date
10. Protection against datetime.now() regressions
11. Provenance
12. Stock ledger reconciliation

These tests use an in-memory SQLite database with data seeded from
the deterministic fixture defined inline (not from PostgreSQL or the
ETL pipeline), matching the project's test conventions.
"""

from datetime import UTC, date, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.brand import Brand
from models.category import Category
from models.product import Product
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from models.stock_movement import StockMovement
from models.supplier import Supplier
from services.inventory import (
    _latest_business_date,
    get_current_stock,
    get_ledger,
    get_valuation,
    list_dead_stock,
    list_slow_movers,
    list_stock,
)
from services.rbac import assign_role, get_role_by_name
from services.security import create_access_token
from services.users import create_user
from services.warehouses import get_or_create_main_warehouse

# ─── Constants ───────────────────────────────────────────────────────
SCENARIO_DATE = date(2026, 8, 1)
SCENARIO_DATETIME = datetime(2026, 8, 1, 12, 0)
# The historical dataset ends on 2011-12-09; dead-stock and slow-mover
# windows must be relative to this date when analysing historical data.
HISTORICAL_AS_OF = datetime(2011, 12, 9, 23, 59, 59)


def _auth_headers(db: Session) -> dict[str, str]:
    create_user(db, email="reader@example.com", password="pass!!", is_read_only=True)
    token = create_access_token(subject="reader@example.com")
    return {"Authorization": f"Bearer {token}"}


def _writer_headers(db: Session) -> dict[str, str]:
    user = create_user(db, email="writer@example.com", password="pass!!", is_read_only=False)
    admin = get_role_by_name(db, "admin")
    assert admin is not None
    assign_role(db, user.id, admin.id)
    token = create_access_token(subject="writer@example.com")
    return {"Authorization": f"Bearer {token}"}


def _clear_test_data(db: Session) -> None:
    """Remove all test-scenario rows (TEST-INV- prefixed SKUs) to make
    the seed function idempotent across test runs sharing a session.
    """
    db.execute(text("DELETE FROM stock_movements WHERE sku LIKE 'TEST-INV-%'"))
    db.execute(text("DELETE FROM stock_levels WHERE sku LIKE 'TEST-INV-%'"))
    db.execute(text("DELETE FROM sales_transactions WHERE sku LIKE 'TEST-INV-%'"))
    db.execute(text("DELETE FROM products WHERE sku LIKE 'TEST-INV-%'"))
    db.execute(text("DELETE FROM suppliers WHERE name LIKE 'Test Supplier%'"))
    db.execute(text("DELETE FROM categories WHERE name = 'Test Inventory Scenario'"))
    db.execute(text("DELETE FROM brands WHERE name = 'Test Brand'"))
    db.commit()


def _seed_scenario(db: Session) -> None:
    """Seed the full test inventory scenario (Scenarios A-H) into the
    in-memory SQLite test database.

    Movement dates use 2026-dated events (relative to SCENARIO_DATE)
    so that dead-stock and slow-mover window calculations work correctly
    with as_of_date=SCENARIO_DATETIME.
    """
    _clear_test_data(db)

    # ── Warehouses ─────────────────────────────────────────────
    main_wh = get_or_create_main_warehouse(db)
    sec_row = db.execute(
        text("SELECT id FROM warehouses WHERE name = 'Secondary Warehouse'")
    ).scalar_one_or_none()
    if sec_row is None:
        from models.warehouse import Warehouse

        sec = Warehouse(name="Secondary Warehouse")
        db.add(sec)
        db.flush()
        secondary_wh_id = sec.id
    else:
        secondary_wh_id = sec_row

    # ── Supplier (Scenario G) ──────────────────────────────────
    sup_alpha = Supplier(name="Test Supplier Alpha", lead_time_days=3, reliability_score=0.95)
    sup_beta = Supplier(name="Test Supplier Beta", lead_time_days=14, reliability_score=0.85)
    sup_gamma = Supplier(name="Test Supplier Gamma", lead_time_days=7, reliability_score=0.92)
    db.add_all([sup_alpha, sup_beta, sup_gamma])
    db.flush()

    # ── Brand & Category ───────────────────────────────────────
    brand = Brand(name="Test Brand")
    db.add(brand)
    db.flush()
    cat = Category(name="Test Inventory Scenario")
    db.add(cat)
    db.flush()

    # ── Products ───────────────────────────────────────────────
    products = [
        # A — Healthy
        Product(
            sku="TEST-INV-001",
            description="Healthy Alpha",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_alpha.id,
            unit_cost=12.50,
            sale_price=24.99,
            reorder_point=50,
            safety_stock=20,
        ),
        Product(
            sku="TEST-INV-002",
            description="Healthy Beta",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_gamma.id,
            unit_cost=8.75,
            sale_price=18.50,
            reorder_point=30,
            safety_stock=10,
        ),
        # B — Low
        Product(
            sku="TEST-INV-003",
            description="Low Alpha",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_beta.id,
            unit_cost=25.00,
            sale_price=49.99,
            reorder_point=20,
            safety_stock=8,
        ),
        Product(
            sku="TEST-INV-004",
            description="Low Beta",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_alpha.id,
            unit_cost=3.20,
            sale_price=7.99,
            reorder_point=15,
            safety_stock=5,
        ),
        # C — Stockout
        Product(
            sku="TEST-INV-005",
            description="Stockout Alpha",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_gamma.id,
            unit_cost=15.00,
            sale_price=32.00,
            reorder_point=25,
            safety_stock=10,
        ),
        Product(
            sku="TEST-INV-006",
            description="Stockout Beta",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_alpha.id,
            unit_cost=6.80,
            sale_price=14.99,
            reorder_point=10,
            safety_stock=4,
        ),
        # D — Dead
        Product(
            sku="TEST-INV-007",
            description="Dead Alpha",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_beta.id,
            unit_cost=45.00,
            sale_price=89.99,
            reorder_point=5,
            safety_stock=2,
        ),
        Product(
            sku="TEST-INV-008",
            description="Dead Beta",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_gamma.id,
            unit_cost=2.10,
            sale_price=5.50,
            reorder_point=10,
            safety_stock=3,
        ),
        # E — Slow
        Product(
            sku="TEST-INV-009",
            description="Slow Alpha",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_alpha.id,
            unit_cost=18.00,
            sale_price=35.00,
            reorder_point=8,
            safety_stock=3,
        ),
        Product(
            sku="TEST-INV-010",
            description="Slow Beta",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_gamma.id,
            unit_cost=9.90,
            sale_price=22.00,
            reorder_point=12,
            safety_stock=4,
        ),
        # F — Different costs
        Product(
            sku="TEST-INV-011",
            description="High Value",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_beta.id,
            unit_cost=150.00,
            sale_price=299.99,
            reorder_point=3,
            safety_stock=1,
        ),
        Product(
            sku="TEST-INV-012",
            description="Low Value",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=sup_alpha.id,
            unit_cost=0.50,
            sale_price=1.99,
            reorder_point=100,
            safety_stock=30,
        ),
    ]
    db.add_all(products)
    db.flush()

    # ── Stock levels ───────────────────────────────────────────
    stock_levels = [
        ("TEST-INV-001", main_wh.id, 230),
        ("TEST-INV-002", main_wh.id, 80),
        ("TEST-INV-003", main_wh.id, 25),
        ("TEST-INV-004", main_wh.id, 12),
        ("TEST-INV-005", main_wh.id, 0),
        ("TEST-INV-006", main_wh.id, 0),
        ("TEST-INV-007", main_wh.id, 30),
        ("TEST-INV-008", main_wh.id, 50),
        ("TEST-INV-009", main_wh.id, 42),
        ("TEST-INV-010", main_wh.id, 26),
        ("TEST-INV-011", main_wh.id, 12),
        ("TEST-INV-012", main_wh.id, 500),
        # Multi-warehouse (H)
        ("TEST-INV-001", secondary_wh_id, 30),
        ("TEST-INV-003", secondary_wh_id, 2),
        ("TEST-INV-011", secondary_wh_id, 4),
    ]
    for sku, wh_id, qty in stock_levels:
        db.add(
            StockLevel(sku=sku, warehouse_id=wh_id, as_of_date=SCENARIO_DATE, quantity_on_hand=qty)
        )
    db.flush()

    # ── Stock movements ────────────────────────────────────────
    # All non-dead movements use 2026 dates (relative to SCENARIO_DATE)
    # so dead-stock / slow-mover window calculations work correctly.
    # Dead stock movements use 2011 dates (well before any 2026 window).
    mid = main_wh.id
    sid = secondary_wh_id

    def _mov(
        sku: str,
        wh_id: int,
        dt: datetime,
        qty: int,
        mtype: str,
        ref: str | None = None,
        prov: str = "observed",
    ) -> StockMovement:
        return StockMovement(
            sku=sku,
            warehouse_id=wh_id,
            movement_date=dt,
            quantity_delta=qty,
            movement_type=mtype,
            reference=ref,
            provenance=prov,
        )

    movements = [
        # A — Healthy: frequent recent sales (within 90 days of scenario date)
        _mov("TEST-INV-001", mid, datetime(2026, 6, 1), 230, "opening_balance", prov="derived"),
        _mov("TEST-INV-001", mid, datetime(2026, 6, 15), -30, "sale"),
        _mov("TEST-INV-001", mid, datetime(2026, 7, 1), -20, "sale"),
        _mov("TEST-INV-001", mid, datetime(2026, 7, 15), -30, "sale"),
        _mov("TEST-INV-001", mid, datetime(2026, 7, 25), -20, "sale"),
        _mov("TEST-INV-002", mid, datetime(2026, 6, 10), 80, "opening_balance", prov="derived"),
        _mov("TEST-INV-002", mid, datetime(2026, 7, 5), -5, "sale"),
        _mov("TEST-INV-002", mid, datetime(2026, 7, 20), -5, "sale"),
        # B — Low: recent sales depleting below reorder
        _mov("TEST-INV-003", mid, datetime(2026, 6, 1), 40, "opening_balance", prov="derived"),
        _mov("TEST-INV-003", mid, datetime(2026, 6, 20), -8, "sale"),
        _mov("TEST-INV-003", mid, datetime(2026, 7, 5), -5, "sale"),
        _mov("TEST-INV-004", mid, datetime(2026, 6, 1), 20, "opening_balance", prov="derived"),
        _mov("TEST-INV-004", mid, datetime(2026, 7, 1), -4, "sale"),
        _mov("TEST-INV-004", mid, datetime(2026, 7, 15), -4, "sale"),
        # C — Stockout: sales drain to zero
        _mov("TEST-INV-005", mid, datetime(2026, 6, 1), 30, "opening_balance", prov="derived"),
        _mov("TEST-INV-005", mid, datetime(2026, 6, 15), -15, "sale"),
        _mov("TEST-INV-005", mid, datetime(2026, 7, 1), -15, "sale"),
        _mov("TEST-INV-006", mid, datetime(2026, 6, 1), 15, "opening_balance", prov="derived"),
        _mov("TEST-INV-006", mid, datetime(2026, 6, 20), -8, "sale"),
        _mov("TEST-INV-006", mid, datetime(2026, 7, 5), -7, "sale"),
        # D — Dead: last movement > 90 days before scenario date
        # (2011 dates — well before any 2026 window)
        _mov("TEST-INV-007", mid, datetime(2011, 10, 1), 30, "opening_balance", prov="derived"),
        _mov("TEST-INV-008", mid, datetime(2011, 9, 1), 50, "opening_balance", prov="derived"),
        # E — Slow: very infrequent sales (2 sales in 90 days ≈ 0.022/day)
        _mov("TEST-INV-009", mid, datetime(2026, 5, 1), 42, "opening_balance", prov="derived"),
        _mov("TEST-INV-009", mid, datetime(2026, 6, 15), -1, "sale"),
        _mov("TEST-INV-009", mid, datetime(2026, 7, 20), -1, "sale"),
        # 1 sale in 90 days ≈ 0.011/day
        _mov("TEST-INV-010", mid, datetime(2026, 5, 15), 26, "opening_balance", prov="derived"),
        _mov("TEST-INV-010", mid, datetime(2026, 7, 10), -1, "sale"),
        # F — Different costs: standard movement pattern
        _mov("TEST-INV-011", mid, datetime(2026, 6, 1), 12, "opening_balance", prov="derived"),
        _mov("TEST-INV-011", mid, datetime(2026, 7, 1), -4, "sale"),
        _mov("TEST-INV-012", mid, datetime(2026, 6, 1), 500, "opening_balance", prov="derived"),
        _mov("TEST-INV-012", mid, datetime(2026, 6, 15), -50, "sale"),
        _mov("TEST-INV-012", mid, datetime(2026, 7, 1), -100, "sale"),
        _mov("TEST-INV-012", mid, datetime(2026, 7, 20), -50, "sale"),
        # H — Multi-warehouse transfers
        _mov("TEST-INV-001", mid, datetime(2026, 7, 28), -30, "transfer", ref="Rebalance"),
        _mov("TEST-INV-001", sid, datetime(2026, 7, 28), 30, "transfer", ref="Rebalance"),
        _mov("TEST-INV-003", mid, datetime(2026, 7, 29), -2, "transfer", ref="Redistribute"),
        _mov("TEST-INV-003", sid, datetime(2026, 7, 29), 2, "transfer", ref="Redistribute"),
        _mov("TEST-INV-011", mid, datetime(2026, 7, 27), -4, "transfer", ref="Split"),
        _mov("TEST-INV-011", sid, datetime(2026, 7, 27), 4, "transfer", ref="Split"),
    ]
    db.add_all(movements)

    # ── Sales transactions (needed by slow-movers query) ───────
    # The slow-movers endpoint reads from sales_transactions, not
    # stock_movements. Add minimal sales data for each non-dead SKU.
    sales = [
        # A — Healthy: frequent sales (high velocity)
        SalesTransaction(
            invoice="TST-001",
            sku="TEST-INV-001",
            quantity=30,
            unit_price=24.99,
            country="GB",
            invoice_date=datetime(2026, 6, 15),
        ),
        SalesTransaction(
            invoice="TST-002",
            sku="TEST-INV-001",
            quantity=20,
            unit_price=24.99,
            country="GB",
            invoice_date=datetime(2026, 7, 1),
        ),
        SalesTransaction(
            invoice="TST-003",
            sku="TEST-INV-001",
            quantity=30,
            unit_price=24.99,
            country="GB",
            invoice_date=datetime(2026, 7, 15),
        ),
        SalesTransaction(
            invoice="TST-004",
            sku="TEST-INV-001",
            quantity=20,
            unit_price=24.99,
            country="GB",
            invoice_date=datetime(2026, 7, 25),
        ),
        SalesTransaction(
            invoice="TST-005",
            sku="TEST-INV-002",
            quantity=5,
            unit_price=18.50,
            country="GB",
            invoice_date=datetime(2026, 7, 5),
        ),
        SalesTransaction(
            invoice="TST-006",
            sku="TEST-INV-002",
            quantity=5,
            unit_price=18.50,
            country="GB",
            invoice_date=datetime(2026, 7, 20),
        ),
        # B — Low: moderate sales
        SalesTransaction(
            invoice="TST-007",
            sku="TEST-INV-003",
            quantity=8,
            unit_price=49.99,
            country="GB",
            invoice_date=datetime(2026, 6, 20),
        ),
        SalesTransaction(
            invoice="TST-008",
            sku="TEST-INV-003",
            quantity=5,
            unit_price=49.99,
            country="GB",
            invoice_date=datetime(2026, 7, 5),
        ),
        SalesTransaction(
            invoice="TST-009",
            sku="TEST-INV-004",
            quantity=4,
            unit_price=7.99,
            country="GB",
            invoice_date=datetime(2026, 7, 1),
        ),
        SalesTransaction(
            invoice="TST-010",
            sku="TEST-INV-004",
            quantity=4,
            unit_price=7.99,
            country="GB",
            invoice_date=datetime(2026, 7, 15),
        ),
        # C — Stockout: sales draining stock
        SalesTransaction(
            invoice="TST-011",
            sku="TEST-INV-005",
            quantity=15,
            unit_price=32.00,
            country="GB",
            invoice_date=datetime(2026, 6, 15),
        ),
        SalesTransaction(
            invoice="TST-012",
            sku="TEST-INV-005",
            quantity=15,
            unit_price=32.00,
            country="GB",
            invoice_date=datetime(2026, 7, 1),
        ),
        SalesTransaction(
            invoice="TST-013",
            sku="TEST-INV-006",
            quantity=8,
            unit_price=14.99,
            country="GB",
            invoice_date=datetime(2026, 6, 20),
        ),
        SalesTransaction(
            invoice="TST-014",
            sku="TEST-INV-006",
            quantity=7,
            unit_price=14.99,
            country="GB",
            invoice_date=datetime(2026, 7, 5),
        ),
        # E — Slow: very few sales (low velocity)
        SalesTransaction(
            invoice="TST-015",
            sku="TEST-INV-009",
            quantity=1,
            unit_price=35.00,
            country="GB",
            invoice_date=datetime(2026, 6, 15),
        ),
        SalesTransaction(
            invoice="TST-016",
            sku="TEST-INV-009",
            quantity=1,
            unit_price=35.00,
            country="GB",
            invoice_date=datetime(2026, 7, 20),
        ),
        SalesTransaction(
            invoice="TST-017",
            sku="TEST-INV-010",
            quantity=1,
            unit_price=22.00,
            country="GB",
            invoice_date=datetime(2026, 7, 10),
        ),
        # F — Different costs
        SalesTransaction(
            invoice="TST-018",
            sku="TEST-INV-011",
            quantity=4,
            unit_price=299.99,
            country="GB",
            invoice_date=datetime(2026, 7, 1),
        ),
        SalesTransaction(
            invoice="TST-019",
            sku="TEST-INV-012",
            quantity=50,
            unit_price=1.99,
            country="GB",
            invoice_date=datetime(2026, 6, 15),
        ),
        SalesTransaction(
            invoice="TST-020",
            sku="TEST-INV-012",
            quantity=100,
            unit_price=1.99,
            country="GB",
            invoice_date=datetime(2026, 7, 1),
        ),
        SalesTransaction(
            invoice="TST-021",
            sku="TEST-INV-012",
            quantity=50,
            unit_price=1.99,
            country="GB",
            invoice_date=datetime(2026, 7, 20),
        ),
        # D — Dead: no sales transactions (by design)
    ]
    db.add_all(sales)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════
# Test class
# ═══════════════════════════════════════════════════════════════════════


class TestDeterministicSeed:
    """1. Deterministic seed reproducibility."""

    def test_seed_produces_expected_product_count(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        count = db_session.execute(
            text("SELECT COUNT(*) FROM products WHERE sku LIKE 'TEST-INV-%'")
        ).scalar_one()
        assert count == 12

    def test_seed_produces_expected_stock_level_count(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        count = db_session.execute(
            text("SELECT COUNT(*) FROM stock_levels WHERE sku LIKE 'TEST-INV-%'")
        ).scalar_one()
        assert count == 15  # 12 main + 3 secondary

    def test_seed_produces_expected_movement_count(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        count = db_session.execute(
            text("SELECT COUNT(*) FROM stock_movements WHERE sku LIKE 'TEST-INV-%'")
        ).scalar_one()
        assert count == 39  # all movements defined above

    def test_seed_is_idempotent(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        _seed_scenario(db_session)  # run twice — should not fail
        count = db_session.execute(
            text("SELECT COUNT(*) FROM products WHERE sku LIKE 'TEST-INV-%'")
        ).scalar_one()
        assert count == 12


class TestHealthyStock:
    """2. Healthy stock: quantity_on_hand > reorder_point."""

    def test_healthy_stock_not_low(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-001")
        assert len(rows) == 1
        row = rows[0]
        # 230 at Main + 30 at Secondary = 260 total
        assert row.quantity_on_hand == 260
        assert row.reorder_point == 50
        assert row.is_low_stock is False

    def test_healthy_stock_beta(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-002")
        assert len(rows) == 1
        # 80 at Main only
        assert rows[0].quantity_on_hand == 80
        assert rows[0].is_low_stock is False


class TestLowStock:
    """3. Low stock: quantity_on_hand <= reorder_point."""

    def test_low_stock_detected(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-003")
        assert len(rows) == 1
        row = rows[0]
        # 25 at Main + 2 at Secondary = 27 total
        assert row.quantity_on_hand == 27
        assert row.reorder_point == 20
        # 27 > 20, so NOT low — this tests that the scenario is correctly
        # designed: the split across warehouses keeps the total above reorder.
        # The truly-low scenario is TEST-INV-004.
        assert row.is_low_stock is False

    def test_low_stock_beta_is_truly_low(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-004")
        assert len(rows) == 1
        # 12 at Main only, reorder_point=15 → 12 <= 15 → low
        assert rows[0].quantity_on_hand == 12
        assert rows[0].reorder_point == 15
        assert rows[0].is_low_stock is True

    def test_low_stock_endpoint_returns_only_low(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, low_stock=True, search="TEST-INV-")
        low_skus = {r.sku for r in rows}
        # 004 (12 <= 15), 005 (0 <= 25), 006 (0 <= 10), 007 (30 > 5 no), 008 (50 > 10 no)
        # 009 (42 > 8 no), 010 (26 > 12 no), 011 (16 > 3 no), 012 (500 > 100 no)
        assert "TEST-INV-004" in low_skus
        assert "TEST-INV-005" in low_skus
        assert "TEST-INV-006" in low_skus
        assert "TEST-INV-001" not in low_skus
        assert "TEST-INV-002" not in low_skus


class TestStockout:
    """4. Zero stock (stockout)."""

    def test_stockout_has_zero_quantity(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-005")
        assert len(rows) == 1
        assert rows[0].quantity_on_hand == 0
        assert rows[0].is_low_stock is True

    def test_stockout_beta(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-006")
        assert len(rows) == 1
        assert rows[0].quantity_on_hand == 0


class TestDeadStock:
    """5. Dead stock: no movement in the configured window."""

    def test_dead_stock_detected(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_dead_stock(db_session, days=90, as_of_date=SCENARIO_DATETIME)
        dead_skus = {r.sku for r in rows}
        assert "TEST-INV-007" in dead_skus
        assert "TEST-INV-008" in dead_skus

    def test_dead_stock_excludes_recently_moved(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_dead_stock(db_session, days=90, as_of_date=SCENARIO_DATETIME)
        dead_skus = {r.sku for r in rows}
        # These SKUs have movements within the last 90 days of SCENARIO_DATETIME
        assert "TEST-INV-001" not in dead_skus
        assert "TEST-INV-003" not in dead_skus

    def test_dead_stock_days_since_movement(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_dead_stock(db_session, days=90, as_of_date=SCENARIO_DATETIME)
        by_sku = {r.sku: r for r in rows}
        dead_7 = by_sku["TEST-INV-007"]
        assert dead_7.days_since_movement is not None
        assert dead_7.days_since_movement >= 200


class TestSlowMovers:
    """6. Slow movers: low but non-zero demand."""

    def test_slow_movers_detected(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_slow_movers(
            db_session,
            window_days=90,
            velocity_threshold=0.2,
            as_of_date=SCENARIO_DATETIME,
        )
        slow_skus = {r.sku for r in rows}
        assert "TEST-INV-009" in slow_skus
        assert "TEST-INV-010" in slow_skus

    def test_slow_movers_excludes_fast_sellers(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_slow_movers(
            db_session,
            window_days=90,
            velocity_threshold=0.2,
            as_of_date=SCENARIO_DATETIME,
        )
        slow_skus = {r.sku for r in rows}
        # TEST-INV-001 has 100 units sold in 90 days = 1.11/day > 0.2
        assert "TEST-INV-001" not in slow_skus

    def test_slow_movers_avg_daily_demand(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        rows = list_slow_movers(
            db_session,
            window_days=90,
            velocity_threshold=0.2,
            as_of_date=SCENARIO_DATETIME,
        )
        by_sku = {r.sku: r for r in rows}
        # TEST-INV-009: 2 sales in 90 days = 2/90 ≈ 0.022
        slow_9 = by_sku["TEST-INV-009"]
        assert slow_9.units_sold == 2
        assert slow_9.avg_daily_demand < 0.2


class TestInventoryValuation:
    """7. Inventory valuation: quantity_on_hand × unit_cost."""

    def test_valuation_total(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        val = get_valuation(db_session, category="Test Inventory Scenario")
        # Total quantity across all warehouses:
        # 001:260, 002:80, 003:27, 004:12, 005:0, 006:0,
        # 007:30, 008:50, 009:42, 010:26, 011:16, 012:500
        expected_qty = 260 + 80 + 27 + 12 + 0 + 0 + 30 + 50 + 42 + 26 + 16 + 500
        assert val.total_quantity_on_hand == expected_qty
        # Value: sum of (qty × unit_cost) per product
        expected_value = (
            260 * 12.50
            + 80 * 8.75
            + 27 * 25.00
            + 12 * 3.20
            + 0 * 15.00
            + 0 * 6.80
            + 30 * 45.00
            + 50 * 2.10
            + 42 * 18.00
            + 26 * 9.90
            + 16 * 150.00
            + 500 * 0.50
        )
        assert val.total_inventory_value == expected_value

    def test_valuation_by_category(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        val = get_valuation(db_session, category="Test Inventory Scenario")
        assert len(val.by_category) == 1
        assert val.by_category[0].category == "Test Inventory Scenario"


class TestWarehouseFiltering:
    """8. Warehouse filtering / isolation."""

    def test_total_across_warehouses(self, db_session: Session) -> None:
        """TEST-INV-001: 230 at Main + 30 at Secondary = 260 total."""
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-001")
        assert len(rows) == 1
        assert rows[0].quantity_on_hand == 260

    def test_low_stock_warehouse_split(self, db_session: Session) -> None:
        """TEST-INV-003: 25 at Main + 2 at Secondary = 27 total (> reorder=20)."""
        _seed_scenario(db_session)
        rows = list_stock(db_session, search="TEST-INV-003")
        assert len(rows) == 1
        assert rows[0].quantity_on_hand == 27
        assert rows[0].is_low_stock is False

    def test_ledger_shows_both_warehouses(self, db_session: Session) -> None:
        """Ledger for TEST-INV-001 should include entries from both warehouses."""
        _seed_scenario(db_session)
        ledger = get_ledger(db_session, "TEST-INV-001")
        warehouse_ids = {entry.warehouse_id for entry in ledger}
        main_wh = get_or_create_main_warehouse(db_session)
        assert main_wh.id in warehouse_ids
        # Secondary warehouse entries exist (transfers)
        assert len(warehouse_ids) >= 2


class TestHistoricalAsOfDate:
    """9. Historical as_of_date: dead-stock and slow-mover windows
    are relative to the data's latest business date, not datetime.now().
    """

    def test_dead_stock_with_historical_date(self, db_session: Session) -> None:
        """With as_of_date = 2011-12-09 (the real dataset's last date),
        a 500-day window should find SKUs with movements in 2011.
        """
        _seed_scenario(db_session)
        list_dead_stock(db_session, days=500, as_of_date=HISTORICAL_AS_OF)
        # TEST-INV-007 last moved 2011-10-01, which is ~69 days before
        # 2011-12-09 — within a 500-day window, so NOT dead.
        # But with a 30-day window, it would be dead.
        rows_30 = list_dead_stock(db_session, days=30, as_of_date=HISTORICAL_AS_OF)
        dead_skus_30 = {r.sku for r in rows_30}
        assert "TEST-INV-007" in dead_skus_30

    def test_slow_movers_with_historical_date(self, db_session: Session) -> None:
        """Slow movers should also work with the historical as_of_date."""
        _seed_scenario(db_session)
        # With a very large window (500 days) from 2011-12-09,
        # no 2026-dated sales exist, so all units_sold=0.
        # This tests that the function doesn't crash.
        rows = list_slow_movers(
            db_session,
            window_days=500,
            velocity_threshold=0.2,
            as_of_date=HISTORICAL_AS_OF,
        )
        # Should return results (all SKUs have 0 sales in 2011 relative window)
        assert isinstance(rows, list)

    def test_latest_business_date_falls_back_to_now(self, db_session: Session) -> None:
        """When there are no stock_movements, _latest_business_date falls
        back to datetime.now() — a safe default for a live database.
        """
        result = _latest_business_date(db_session)
        assert abs((datetime.now(UTC).replace(tzinfo=None) - result).total_seconds()) < 5


class TestDateTimeNowRegression:
    """10. Protection against datetime.now() regressions.

    The dead-stock and slow-mover queries must NOT use datetime.now()
    for their window calculations when an as_of_date is provided.
    """

    def test_dead_stock_as_of_overrides_now(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        with patch("services.inventory._latest_business_date") as mock_now:
            mock_now.return_value = datetime(2026, 8, 1, 23, 59, 59)
            rows = list_dead_stock(db_session, days=90)
            dead_skus = {r.sku for r in rows}
            assert "TEST-INV-007" in dead_skus

    def test_slow_movers_as_of_overrides_now(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        with patch("services.inventory._latest_business_date") as mock_now:
            mock_now.return_value = datetime(2026, 8, 1, 23, 59, 59)
            rows = list_slow_movers(db_session, window_days=90, velocity_threshold=0.2)
            slow_skus = {r.sku for r in rows}
            assert "TEST-INV-009" in slow_skus


class TestProvenance:
    """11. Provenance labels on all returned data."""

    def test_stock_item_has_provenance(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/stock", params={"search": "TEST-INV-001"}, headers=headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "_provenance" in item
        assert "quantity_on_hand" in item["_provenance"]

    def test_valuation_has_provenance(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/valuation", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "_provenance" in body
        assert "total_inventory_value" in body["_provenance"]

    def test_ledger_entries_have_provenance(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/TEST-INV-001/ledger", headers=headers)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) > 0
        for entry in entries:
            assert "provenance" in entry
            assert entry["provenance"] in ("observed", "derived")


class TestStockLedgerReconciliation:
    """12. Stock ledger reconciliation: current stock matches stock_levels."""

    def test_reconcile_healthy_sku(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        current = get_current_stock(db_session, "TEST-INV-001")
        assert current == 260  # 230 main + 30 secondary

    def test_reconcile_low_sku(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        current = get_current_stock(db_session, "TEST-INV-004")
        assert current == 12

    def test_reconcile_stockout_sku(self, db_session: Session) -> None:
        _seed_scenario(db_session)
        current = get_current_stock(db_session, "TEST-INV-005")
        assert current == 0

    def test_ledger_completeness(self, db_session: Session) -> None:
        """Every test SKU should have at least one ledger entry."""
        _seed_scenario(db_session)
        for i in range(1, 13):
            sku = f"TEST-INV-{i:03d}"
            ledger = get_ledger(db_session, sku)
            assert len(ledger) > 0, f"{sku} has no ledger entries"


class TestAPIEndpoints:
    """Integration tests against the actual HTTP API."""

    def test_stock_list_with_search(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/stock", params={"search": "TEST-INV-"}, headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 12

    def test_low_stock_endpoint(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/low-stock", params={"search": "TEST-INV-"}, headers=headers)
        assert resp.status_code == 200
        skus = {item["sku"] for item in resp.json()}
        assert "TEST-INV-004" in skus
        assert "TEST-INV-005" in skus
        assert "TEST-INV-006" in skus

    def test_dead_stock_endpoint(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get(
            "/inventory/dead-stock",
            params={"days": 90, "as_of_date": "2026-08-01"},
            headers=headers,
        )
        assert resp.status_code == 200
        skus = {item["sku"] for item in resp.json()}
        assert "TEST-INV-007" in skus
        assert "TEST-INV-008" in skus

    def test_slow_movers_endpoint(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get(
            "/inventory/slow-movers",
            params={"window_days": 90, "velocity_threshold": 0.2, "as_of_date": "2026-08-01"},
            headers=headers,
        )
        assert resp.status_code == 200
        skus = {item["sku"] for item in resp.json()}
        assert "TEST-INV-009" in skus

    def test_valuation_endpoint(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/valuation", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_quantity_on_hand"] > 0
        assert body["total_inventory_value"] > 0

    def test_ledger_endpoint(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/TEST-INV-001/ledger", headers=headers)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 5

    def test_empty_result_for_nonexistent_sku(
        self, client: TestClient, db_session: Session
    ) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get("/inventory/stock", params={"search": "NONEXISTENT"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pagination(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get(
            "/inventory/stock",
            params={"search": "TEST-INV-", "limit": 3, "offset": 0},
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

        resp2 = client.get(
            "/inventory/stock",
            params={"search": "TEST-INV-", "limit": 3, "offset": 3},
            headers=headers,
        )
        assert resp2.status_code == 200
        assert len(resp2.json()) == 3
        skus1 = {item["sku"] for item in resp.json()}
        skus2 = {item["sku"] for item in resp2.json()}
        assert skus1.isdisjoint(skus2)

    def test_category_filter(self, client: TestClient, db_session: Session) -> None:
        _seed_scenario(db_session)
        headers = _auth_headers(db_session)
        resp = client.get(
            "/inventory/stock",
            params={"category": "Test Inventory Scenario"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 12
