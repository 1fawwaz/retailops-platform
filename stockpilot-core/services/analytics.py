"""Analytics read queries. All aggregation happens in SQL (including
running totals for ABC classification, via window functions); this
module returns plain dataclasses that routers map onto
provenance-labelled Pydantic schemas. Every number here is `derived`
-- a deterministic aggregate over observed sales_transactions rows
(and, for cost-based metrics, the derived unit_cost column).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import ColumnElement, Float, case, cast, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from models.category import Category
from models.product import Product
from models.purchase_order_request import OPEN_STATUSES, PurchaseOrderRequest
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from models.stock_movement import StockMovement
from models.supplier import Supplier
from services.inventory import latest_stock_level_subquery


def _period_bucket_expr(
    column: InstrumentedAttribute[datetime], group_by: str, dialect_name: str
) -> ColumnElement[str]:
    """String bucket label for day/week/month grouping. Day and month
    formats are unambiguous across dialects; week bucket boundaries
    follow each database's native week-numbering (Postgres ISO week via
    to_char vs SQLite's %W), which can disagree by a day near year
    boundaries between the Postgres production DB and the SQLite test
    fixture.
    """
    if dialect_name == "postgresql":
        formats = {"day": "YYYY-MM-DD", "week": 'IYYY-"W"IW', "month": "YYYY-MM"}
        return func.to_char(column, formats[group_by])
    formats_sqlite = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}
    return func.strftime(formats_sqlite[group_by], column)


def _date_filters(start_date: date | None, end_date: date | None) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if start_date is not None:
        filters.append(SalesTransaction.invoice_date >= start_date)
    if end_date is not None:
        filters.append(SalesTransaction.invoice_date < end_date + timedelta(days=1))
    return filters


@dataclass(frozen=True)
class RevenuePeriodRow:
    period: str
    revenue: float
    units: int


def get_revenue(
    db: Session,
    *,
    group_by: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[RevenuePeriodRow]:
    revenue_expr = func.sum(SalesTransaction.quantity * SalesTransaction.unit_price)
    units_expr = func.sum(SalesTransaction.quantity)

    if group_by == "category":
        period_expr: ColumnElement[str] = func.coalesce(Category.name, "Uncategorized")
    else:
        dialect_name = db.get_bind().dialect.name
        period_expr = _period_bucket_expr(SalesTransaction.invoice_date, group_by, dialect_name)

    stmt = (
        select(period_expr, revenue_expr, units_expr)
        .select_from(SalesTransaction)
        .join(Product, Product.sku == SalesTransaction.sku)
        .outerjoin(Category, Category.id == Product.category_id)
        .group_by(period_expr)
        .order_by(period_expr)
    )
    for condition in _date_filters(start_date, end_date):
        stmt = stmt.where(condition)

    return [
        RevenuePeriodRow(period=period, revenue=float(revenue), units=int(units))
        for period, revenue, units in db.execute(stmt)
    ]


@dataclass(frozen=True)
class ProfitPeriodRow:
    period: str
    revenue: float
    cost: float
    gross_profit: float
    margin: float | None


def get_profit(
    db: Session,
    *,
    group_by: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ProfitPeriodRow]:
    """cost is summed only over line items whose SKU already has a
    derived unit_cost; SKUs still missing one contribute to revenue but
    not cost, so gross_profit is a slight overestimate for those rows
    until unit_cost backfills.
    """
    revenue_expr = func.sum(SalesTransaction.quantity * SalesTransaction.unit_price)
    cost_expr = func.coalesce(func.sum(SalesTransaction.quantity * Product.unit_cost), 0.0)

    if group_by == "category":
        period_expr: ColumnElement[str] = func.coalesce(Category.name, "Uncategorized")
    else:
        dialect_name = db.get_bind().dialect.name
        period_expr = _period_bucket_expr(SalesTransaction.invoice_date, group_by, dialect_name)

    stmt = (
        select(period_expr, revenue_expr, cost_expr)
        .select_from(SalesTransaction)
        .join(Product, Product.sku == SalesTransaction.sku)
        .outerjoin(Category, Category.id == Product.category_id)
        .group_by(period_expr)
        .order_by(period_expr)
    )
    for condition in _date_filters(start_date, end_date):
        stmt = stmt.where(condition)

    rows: list[ProfitPeriodRow] = []
    for period, revenue, cost in db.execute(stmt):
        revenue = float(revenue)
        cost = float(cost)
        gross_profit = revenue - cost
        margin = gross_profit / revenue if revenue else None
        rows.append(
            ProfitPeriodRow(
                period=period, revenue=revenue, cost=cost, gross_profit=gross_profit, margin=margin
            )
        )
    return rows


@dataclass(frozen=True)
class TurnoverRow:
    category: str | None
    units_sold: int
    avg_quantity_on_hand: float
    turnover_ratio: float | None


def get_turnover(db: Session, *, start_date: date, end_date: date) -> list[TurnoverRow]:
    """Turnover ratio = units sold in the window / average
    quantity_on_hand over the same window, per category. A category
    with zero average stock in the window gets a null ratio (undefined,
    not zero). Assumes every product carries a category, true after ETL
    step (c); an uncategorized product would not appear here.
    """
    units_sold_sq = (
        select(
            Product.category_id.label("category_id"),
            func.sum(SalesTransaction.quantity).label("units_sold"),
        )
        .select_from(SalesTransaction)
        .join(Product, Product.sku == SalesTransaction.sku)
        .where(SalesTransaction.invoice_date >= start_date)
        .where(SalesTransaction.invoice_date < end_date + timedelta(days=1))
        .group_by(Product.category_id)
        .subquery()
    )
    # Sum across warehouses per (sku, date) first (docs/BUILD.md Backend
    # Module 4 made stock_levels location-scoped -- one row per
    # warehouse now, not one per sku-date), THEN average across
    # sku-days per category. Numerically identical to the pre-Module-4
    # query with today's single warehouse; stays correct once a second
    # warehouse genuinely has stock, instead of silently averaging
    # per-warehouse fragments instead of per-SKU daily totals.
    per_sku_date_sq = (
        select(
            StockLevel.sku.label("sku"),
            StockLevel.as_of_date.label("as_of_date"),
            func.sum(StockLevel.quantity_on_hand).label("quantity_on_hand"),
        )
        .where(StockLevel.as_of_date >= start_date)
        .where(StockLevel.as_of_date <= end_date)
        .group_by(StockLevel.sku, StockLevel.as_of_date)
        .subquery()
    )
    avg_stock_sq = (
        select(
            Product.category_id.label("category_id"),
            func.avg(per_sku_date_sq.c.quantity_on_hand).label("avg_quantity_on_hand"),
        )
        .select_from(per_sku_date_sq)
        .join(Product, Product.sku == per_sku_date_sq.c.sku)
        .group_by(Product.category_id)
        .subquery()
    )
    stmt = (
        select(
            Category.name,
            func.coalesce(units_sold_sq.c.units_sold, 0),
            func.coalesce(avg_stock_sq.c.avg_quantity_on_hand, 0.0),
        )
        .select_from(Category)
        .outerjoin(units_sold_sq, units_sold_sq.c.category_id == Category.id)
        .outerjoin(avg_stock_sq, avg_stock_sq.c.category_id == Category.id)
        .order_by(Category.name)
    )
    rows: list[TurnoverRow] = []
    for name, units_sold, avg_qty in db.execute(stmt):
        units_sold = int(units_sold)
        avg_qty = float(avg_qty)
        ratio = units_sold / avg_qty if avg_qty > 0 else None
        rows.append(
            TurnoverRow(
                category=name,
                units_sold=units_sold,
                avg_quantity_on_hand=avg_qty,
                turnover_ratio=ratio,
            )
        )
    return rows


@dataclass(frozen=True)
class AbcRow:
    sku: str
    revenue: float
    cumulative_pct: float
    abc_class: str


def get_abc_classification(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    a_threshold: float = 0.8,
    b_threshold: float = 0.95,
) -> list[AbcRow]:
    """ABC classification via Pareto analysis on revenue contribution:
    class A = SKUs making up the top a_threshold share of cumulative
    revenue (ranked descending), B = up to b_threshold, C = the rest.
    Cumulative share is a SQL window function running total, not a
    Python loop.
    """
    revenue_expr = func.sum(SalesTransaction.quantity * SalesTransaction.unit_price)
    stmt = select(SalesTransaction.sku, revenue_expr.label("revenue")).group_by(
        SalesTransaction.sku
    )
    for condition in _date_filters(start_date, end_date):
        stmt = stmt.where(condition)
    per_sku = stmt.subquery()

    running_total = func.sum(per_sku.c.revenue).over(
        order_by=per_sku.c.revenue.desc(), rows=(None, 0)
    )
    grand_total = func.sum(per_sku.c.revenue).over()
    cumulative_pct_expr = running_total / grand_total

    ranked_stmt = select(per_sku.c.sku, per_sku.c.revenue, cumulative_pct_expr).order_by(
        per_sku.c.revenue.desc()
    )

    rows: list[AbcRow] = []
    for sku, revenue, cumulative_pct in db.execute(ranked_stmt):
        revenue = float(revenue)
        cumulative_pct = float(cumulative_pct)
        if cumulative_pct <= a_threshold:
            abc_class = "A"
        elif cumulative_pct <= b_threshold:
            abc_class = "B"
        else:
            abc_class = "C"
        rows.append(
            AbcRow(sku=sku, revenue=revenue, cumulative_pct=cumulative_pct, abc_class=abc_class)
        )
    return rows


@dataclass(frozen=True)
class ProductPerformanceRow:
    sku: str
    description: str | None
    revenue: float
    units: int
    margin: float | None


def _ranked_products(
    db: Session,
    *,
    metric: str,
    limit: int,
    ascending: bool,
    start_date: date | None,
    end_date: date | None,
) -> list[ProductPerformanceRow]:
    revenue_expr = cast(func.sum(SalesTransaction.quantity * SalesTransaction.unit_price), Float)
    units_expr = func.sum(SalesTransaction.quantity)
    cost_expr = cast(
        func.coalesce(func.sum(SalesTransaction.quantity * Product.unit_cost), 0.0), Float
    )
    order_expr: ColumnElement[float]
    if metric == "revenue":
        order_expr = revenue_expr
    elif metric == "units":
        order_expr = cast(units_expr, Float)
    else:
        order_expr = cast((revenue_expr - cost_expr) / func.nullif(revenue_expr, 0), Float)

    stmt = (
        select(Product.sku, Product.description, revenue_expr, units_expr, cost_expr)
        .select_from(SalesTransaction)
        .join(Product, Product.sku == SalesTransaction.sku)
        .group_by(Product.sku, Product.description)
    )
    for condition in _date_filters(start_date, end_date):
        stmt = stmt.where(condition)
    stmt = stmt.order_by(order_expr.asc() if ascending else order_expr.desc()).limit(limit)

    rows: list[ProductPerformanceRow] = []
    for sku, description, revenue, units, cost in db.execute(stmt):
        revenue = float(revenue)
        units = int(units)
        cost = float(cost)
        gross_profit = revenue - cost
        margin = gross_profit / revenue if revenue else None
        rows.append(
            ProductPerformanceRow(
                sku=sku, description=description, revenue=revenue, units=units, margin=margin
            )
        )
    return rows


def get_top_products(
    db: Session,
    *,
    metric: str,
    limit: int = 10,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ProductPerformanceRow]:
    return _ranked_products(
        db, metric=metric, limit=limit, ascending=False, start_date=start_date, end_date=end_date
    )


def get_bottom_products(
    db: Session,
    *,
    metric: str,
    limit: int = 10,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ProductPerformanceRow]:
    return _ranked_products(
        db, metric=metric, limit=limit, ascending=True, start_date=start_date, end_date=end_date
    )


@dataclass(frozen=True)
class PeriodTotals:
    revenue: float
    units: int
    cost: float
    gross_profit: float
    margin: float | None


def get_period_totals(db: Session, *, start_date: date, end_date: date) -> PeriodTotals:
    revenue_expr = func.coalesce(
        func.sum(SalesTransaction.quantity * SalesTransaction.unit_price), 0.0
    )
    units_expr = func.coalesce(func.sum(SalesTransaction.quantity), 0)
    cost_expr = func.coalesce(func.sum(SalesTransaction.quantity * Product.unit_cost), 0.0)
    stmt = (
        select(revenue_expr, units_expr, cost_expr)
        .select_from(SalesTransaction)
        .join(Product, Product.sku == SalesTransaction.sku)
        .where(SalesTransaction.invoice_date >= start_date)
        .where(SalesTransaction.invoice_date < end_date + timedelta(days=1))
    )
    revenue, units, cost = db.execute(stmt).one()
    revenue = float(revenue)
    units = int(units)
    cost = float(cost)
    gross_profit = revenue - cost
    margin = gross_profit / revenue if revenue else None
    return PeriodTotals(
        revenue=revenue, units=units, cost=cost, gross_profit=gross_profit, margin=margin
    )


@dataclass(frozen=True)
class PeriodComparisonData:
    period1_start: date
    period1_end: date
    period1: PeriodTotals
    period2_start: date
    period2_end: date
    period2: PeriodTotals
    revenue_delta: float
    revenue_delta_pct: float | None
    units_delta: int
    units_delta_pct: float | None
    gross_profit_delta: float
    gross_profit_delta_pct: float | None


def _pct_delta(old: float, new: float) -> float | None:
    return (new - old) / old if old else None


def get_period_comparison(
    db: Session,
    *,
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
) -> PeriodComparisonData:
    period1 = get_period_totals(db, start_date=period1_start, end_date=period1_end)
    period2 = get_period_totals(db, start_date=period2_start, end_date=period2_end)
    return PeriodComparisonData(
        period1_start=period1_start,
        period1_end=period1_end,
        period1=period1,
        period2_start=period2_start,
        period2_end=period2_end,
        period2=period2,
        revenue_delta=period2.revenue - period1.revenue,
        revenue_delta_pct=_pct_delta(period1.revenue, period2.revenue),
        units_delta=period2.units - period1.units,
        units_delta_pct=_pct_delta(period1.units, period2.units),
        gross_profit_delta=period2.gross_profit - period1.gross_profit,
        gross_profit_delta_pct=_pct_delta(period1.gross_profit, period2.gross_profit),
    )


@dataclass(frozen=True)
class SupplierRollupRow:
    """Cross-supplier rollup, distinct from the per-supplier detail
    already served by GET /suppliers/{id} (docs/BUILD.md Backend
    Module 3). sku_count and total_inventory_value are derived by
    joining the existing Products/Inventory data to each supplier;
    open/total PO counts are derived from Backend Module 5's real
    purchase_order_requests -- none of this is a new data source, just
    a new aggregation over what already exists.
    """

    supplier_id: int
    name: str
    lead_time_days: int
    reliability_score: float
    sku_count: int
    total_inventory_value: float
    open_purchase_order_count: int
    total_purchase_order_count: int


def get_supplier_rollup(db: Session) -> list[SupplierRollupRow]:
    latest_stock = latest_stock_level_subquery()
    inventory_sq = (
        select(
            Product.supplier_id.label("supplier_id"),
            func.count(Product.sku.distinct()).label("sku_count"),
            func.coalesce(func.sum(latest_stock.c.quantity_on_hand * Product.unit_cost), 0.0).label(
                "total_inventory_value"
            ),
        )
        .select_from(Product)
        .outerjoin(latest_stock, latest_stock.c.sku == Product.sku)
        .where(Product.supplier_id.is_not(None))
        .group_by(Product.supplier_id)
        .subquery()
    )
    po_sq = (
        select(
            PurchaseOrderRequest.supplier_id.label("supplier_id"),
            func.count(PurchaseOrderRequest.id).label("total_purchase_order_count"),
            func.sum(case((PurchaseOrderRequest.status.in_(OPEN_STATUSES), 1), else_=0)).label(
                "open_purchase_order_count"
            ),
        )
        .group_by(PurchaseOrderRequest.supplier_id)
        .subquery()
    )
    stmt = (
        select(
            Supplier.id,
            Supplier.name,
            Supplier.lead_time_days,
            Supplier.reliability_score,
            func.coalesce(inventory_sq.c.sku_count, 0),
            func.coalesce(inventory_sq.c.total_inventory_value, 0.0),
            func.coalesce(po_sq.c.open_purchase_order_count, 0.0),
            func.coalesce(po_sq.c.total_purchase_order_count, 0),
        )
        .select_from(Supplier)
        .outerjoin(inventory_sq, inventory_sq.c.supplier_id == Supplier.id)
        .outerjoin(po_sq, po_sq.c.supplier_id == Supplier.id)
        .order_by(Supplier.name)
    )
    return [
        SupplierRollupRow(
            supplier_id=supplier_id,
            name=name,
            lead_time_days=lead_time_days,
            reliability_score=float(reliability_score),
            sku_count=int(sku_count),
            total_inventory_value=float(total_value),
            open_purchase_order_count=int(open_po_count),
            total_purchase_order_count=int(total_po_count),
        )
        for (
            supplier_id,
            name,
            lead_time_days,
            reliability_score,
            sku_count,
            total_value,
            open_po_count,
            total_po_count,
        ) in db.execute(stmt)
    ]


@dataclass(frozen=True)
class PurchaseOrderKpis:
    """docs/BUILD.md Backend Module 8. avg_days_to_receive is derived
    from the real stock_movements rows Backend Module 5's receive
    endpoint writes (movement_type='purchase_order', reference tags
    which PO) -- not a separately-tracked timestamp that could drift
    from what actually happened.
    """

    open_purchase_order_count: int
    avg_days_to_receive: float | None


def get_purchase_order_kpis(db: Session) -> PurchaseOrderKpis:
    open_count = db.execute(
        select(func.count())
        .select_from(PurchaseOrderRequest)
        .where(PurchaseOrderRequest.status.in_(OPEN_STATUSES))
    ).scalar_one()

    received_pos = list(
        db.scalars(
            select(PurchaseOrderRequest).where(
                PurchaseOrderRequest.status.in_(("received", "closed"))
            )
        )
    )
    days_to_receive: list[float] = []
    for po in received_pos:
        last_received_at = db.execute(
            select(func.max(StockMovement.movement_date)).where(
                StockMovement.reference == f"PO #{po.id}",
                StockMovement.movement_type == "purchase_order",
            )
        ).scalar_one_or_none()
        if last_received_at is not None:
            days_to_receive.append((last_received_at - po.created_at).total_seconds() / 86400)

    avg_days = sum(days_to_receive) / len(days_to_receive) if days_to_receive else None
    return PurchaseOrderKpis(
        open_purchase_order_count=int(open_count), avg_days_to_receive=avg_days
    )
