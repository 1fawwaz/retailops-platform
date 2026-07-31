"""Inventory read queries. All aggregation happens in SQL; this module
returns plain dataclasses that routers map onto provenance-labelled
Pydantic schemas.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Subquery

from models.category import Category
from models.product import Product
from models.sales_transaction import SalesTransaction
from models.stock_level import StockLevel
from models.stock_movement import StockMovement


def _latest_stock_level_by_warehouse_subquery() -> Subquery:
    """Per (sku, warehouse) stock_levels row with the most recent
    as_of_date. A SKU can have one current row per warehouse now that
    stock is location-scoped (docs/BUILD.md Backend Module 4).
    """
    latest_dates = (
        select(
            StockLevel.sku.label("sku"),
            StockLevel.warehouse_id.label("warehouse_id"),
            func.max(StockLevel.as_of_date).label("max_date"),
        )
        .group_by(StockLevel.sku, StockLevel.warehouse_id)
        .subquery()
    )
    return (
        select(
            StockLevel.sku.label("sku"),
            StockLevel.warehouse_id.label("warehouse_id"),
            StockLevel.quantity_on_hand.label("quantity_on_hand"),
            StockLevel.as_of_date.label("as_of_date"),
        )
        .join(
            latest_dates,
            (StockLevel.sku == latest_dates.c.sku)
            & (StockLevel.warehouse_id == latest_dates.c.warehouse_id)
            & (StockLevel.as_of_date == latest_dates.c.max_date),
        )
        .subquery()
    )


def _latest_stock_level_subquery() -> Subquery:
    """Per-SKU total quantity_on_hand: each warehouse's own latest row,
    summed. With a single warehouse (today's only real case) this is
    numerically identical to the pre-Module-4 single-location query --
    it only starts summing across locations once a second warehouse
    genuinely has stock.
    """
    per_warehouse = _latest_stock_level_by_warehouse_subquery()
    return (
        select(
            per_warehouse.c.sku.label("sku"),
            func.sum(per_warehouse.c.quantity_on_hand).label("quantity_on_hand"),
            func.max(per_warehouse.c.as_of_date).label("as_of_date"),
        )
        .group_by(per_warehouse.c.sku)
        .subquery()
    )


def get_current_stock(db: Session, sku: str) -> int | None:
    """Most recent total quantity_on_hand for a single SKU across every
    warehouse, or None if it has no stock_levels rows yet.
    """
    per_warehouse = _latest_stock_level_by_warehouse_subquery()
    stmt = select(func.sum(per_warehouse.c.quantity_on_hand)).where(per_warehouse.c.sku == sku)
    return db.execute(stmt).scalar_one_or_none()


@dataclass(frozen=True)
class StockRow:
    sku: str
    description: str | None
    category: str | None
    quantity_on_hand: int
    reorder_point: int | None
    safety_stock: int | None
    as_of_date: date
    is_low_stock: bool


def list_stock(
    db: Session,
    *,
    category: str | None = None,
    low_stock: bool | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StockRow]:
    latest = _latest_stock_level_subquery()
    is_low_stock_expr = case(
        (
            Product.reorder_point.is_not(None)
            & (latest.c.quantity_on_hand <= Product.reorder_point),
            True,
        ),
        else_=False,
    )
    stmt = (
        select(
            Product.sku,
            Product.description,
            Category.name,
            latest.c.quantity_on_hand,
            Product.reorder_point,
            Product.safety_stock,
            latest.c.as_of_date,
            is_low_stock_expr,
        )
        .join(latest, latest.c.sku == Product.sku)
        .outerjoin(Category, Category.id == Product.category_id)
    )
    if category is not None:
        stmt = stmt.where(func.lower(Category.name) == category.lower())
    if low_stock is not None:
        stmt = stmt.where(is_low_stock_expr.is_(low_stock))
    if search is not None:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Product.sku).like(pattern) | func.lower(Product.description).like(pattern)
        )
    stmt = stmt.order_by(Product.sku).limit(limit).offset(offset)
    rows: list[StockRow] = []
    for (
        sku,
        description,
        category_name,
        qty,
        reorder_point,
        safety_stock,
        as_of_date,
        is_low,
    ) in db.execute(stmt):
        rows.append(
            StockRow(
                sku=sku,
                description=description,
                category=category_name,
                quantity_on_hand=qty,
                reorder_point=reorder_point,
                safety_stock=safety_stock,
                as_of_date=as_of_date,
                is_low_stock=bool(is_low),
            )
        )
    return rows


@dataclass(frozen=True)
class DeadStockRow:
    sku: str
    description: str | None
    quantity_on_hand: int
    last_movement_date: datetime | None
    days_since_movement: int | None


def list_dead_stock(
    db: Session,
    *,
    days: int = 90,
    limit: int = 100,
    offset: int = 0,
) -> list[DeadStockRow]:
    latest = _latest_stock_level_subquery()
    last_movement = (
        select(
            StockMovement.sku.label("sku"),
            func.max(StockMovement.movement_date).label("last_movement_date"),
        )
        .group_by(StockMovement.sku)
        .subquery()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now - timedelta(days=days)
    stmt = (
        select(
            Product.sku,
            Product.description,
            latest.c.quantity_on_hand,
            last_movement.c.last_movement_date,
        )
        .join(latest, latest.c.sku == Product.sku)
        .outerjoin(last_movement, last_movement.c.sku == Product.sku)
        .where(
            last_movement.c.last_movement_date.is_(None)
            | (last_movement.c.last_movement_date < cutoff)
        )
        .order_by(Product.sku)
        .limit(limit)
        .offset(offset)
    )
    rows: list[DeadStockRow] = []
    for sku, description, qty, last_dt in db.execute(stmt):
        days_since = (now - last_dt).days if last_dt is not None else None
        rows.append(
            DeadStockRow(
                sku=sku,
                description=description,
                quantity_on_hand=qty,
                last_movement_date=last_dt,
                days_since_movement=days_since,
            )
        )
    return rows


@dataclass(frozen=True)
class SlowMoverRow:
    sku: str
    description: str | None
    quantity_on_hand: int
    units_sold: int
    avg_daily_demand: float


def list_slow_movers(
    db: Session,
    *,
    window_days: int = 90,
    velocity_threshold: float = 0.2,
    limit: int = 50,
    offset: int = 0,
) -> list[SlowMoverRow]:
    """SKUs in stock whose average daily sales velocity over the trailing
    window falls below velocity_threshold units/day. Distinct from
    dead-stock: these SKUs are still selling, just slowly.
    """
    latest = _latest_stock_level_subquery()
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=window_days)
    sales = (
        select(
            SalesTransaction.sku.label("sku"),
            func.sum(SalesTransaction.quantity).label("units_sold"),
        )
        .where(SalesTransaction.invoice_date >= cutoff)
        .group_by(SalesTransaction.sku)
        .subquery()
    )
    units_sold_expr = func.coalesce(sales.c.units_sold, 0)
    avg_daily_expr = units_sold_expr / float(window_days)
    stmt = (
        select(
            Product.sku,
            Product.description,
            latest.c.quantity_on_hand,
            units_sold_expr,
            avg_daily_expr,
        )
        .join(latest, latest.c.sku == Product.sku)
        .outerjoin(sales, sales.c.sku == Product.sku)
        .where(latest.c.quantity_on_hand > 0)
        .where(avg_daily_expr < velocity_threshold)
        .order_by(avg_daily_expr)
        .limit(limit)
        .offset(offset)
    )
    return [
        SlowMoverRow(
            sku=sku,
            description=description,
            quantity_on_hand=qty,
            units_sold=int(units_sold),
            avg_daily_demand=float(avg_daily),
        )
        for sku, description, qty, units_sold, avg_daily in db.execute(stmt)
    ]


@dataclass(frozen=True)
class ValuationRow:
    category: str | None
    quantity_on_hand: int
    inventory_value: float


@dataclass(frozen=True)
class Valuation:
    by_category: list[ValuationRow]
    total_quantity_on_hand: int
    total_inventory_value: float


def get_valuation(db: Session, *, category: str | None = None) -> Valuation:
    """Capital tied up in on-hand inventory (quantity_on_hand * unit_cost),
    grouped by category. Products with no derived unit_cost yet are
    excluded from the value sum (their units still count toward quantity).
    """
    latest = _latest_stock_level_subquery()
    value_expr = latest.c.quantity_on_hand * Product.unit_cost
    stmt = (
        select(
            Category.name,
            func.coalesce(func.sum(latest.c.quantity_on_hand), 0),
            func.coalesce(func.sum(value_expr), 0.0),
        )
        .select_from(Product)
        .join(latest, latest.c.sku == Product.sku)
        .outerjoin(Category, Category.id == Product.category_id)
        .group_by(Category.name)
        .order_by(Category.name)
    )
    if category is not None:
        stmt = stmt.where(func.lower(Category.name) == category.lower())
    by_category = [
        ValuationRow(category=name, quantity_on_hand=int(qty), inventory_value=float(value))
        for name, qty, value in db.execute(stmt)
    ]
    total_quantity = sum(row.quantity_on_hand for row in by_category)
    total_value = sum(row.inventory_value for row in by_category)
    return Valuation(
        by_category=by_category,
        total_quantity_on_hand=total_quantity,
        total_inventory_value=total_value,
    )


class InsufficientStockError(Exception):
    """A transfer or adjustment would drive a SKU's quantity at a
    warehouse below zero."""


class SameWarehouseTransferError(Exception):
    """A transfer's from_warehouse_id and to_warehouse_id are the same."""


def _get_latest_quantity(db: Session, sku: str, warehouse_id: int) -> int:
    stmt = (
        select(StockLevel.quantity_on_hand)
        .where(StockLevel.sku == sku, StockLevel.warehouse_id == warehouse_id)
        .order_by(StockLevel.as_of_date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() or 0


def apply_stock_delta(db: Session, sku: str, warehouse_id: int, delta: int, as_of: date) -> int:
    """Upsert the (sku, warehouse_id, as_of) stock_levels row, carrying
    forward the most recent known quantity at that warehouse. Multiple
    same-day calls compose correctly: each reads the running total left
    by the previous one, since a same-day row (if already created by an
    earlier call today) is itself the "most recent" row.
    """
    new_quantity = _get_latest_quantity(db, sku, warehouse_id) + delta
    row = db.scalar(
        select(StockLevel).where(
            StockLevel.sku == sku,
            StockLevel.warehouse_id == warehouse_id,
            StockLevel.as_of_date == as_of,
        )
    )
    if row is not None:
        row.quantity_on_hand = new_quantity
    else:
        db.add(
            StockLevel(
                sku=sku, warehouse_id=warehouse_id, as_of_date=as_of, quantity_on_hand=new_quantity
            )
        )
    return new_quantity


def transfer_stock(
    db: Session,
    *,
    sku: str,
    from_warehouse_id: int,
    to_warehouse_id: int,
    quantity: int,
    reason: str | None,
) -> None:
    if from_warehouse_id == to_warehouse_id:
        raise SameWarehouseTransferError("from_warehouse_id and to_warehouse_id must differ")
    source_current = _get_latest_quantity(db, sku, from_warehouse_id)
    if source_current < quantity:
        raise InsufficientStockError(
            f"Only {source_current} units of '{sku}' at warehouse {from_warehouse_id}, "
            f"cannot transfer {quantity}"
        )
    today = datetime.now(UTC).date()
    now = datetime.now(UTC).replace(tzinfo=None)
    apply_stock_delta(db, sku, from_warehouse_id, -quantity, today)
    apply_stock_delta(db, sku, to_warehouse_id, quantity, today)
    db.add(
        StockMovement(
            sku=sku,
            warehouse_id=from_warehouse_id,
            movement_date=now,
            quantity_delta=-quantity,
            movement_type="transfer",
            reference=reason,
            provenance="observed",
        )
    )
    db.add(
        StockMovement(
            sku=sku,
            warehouse_id=to_warehouse_id,
            movement_date=now,
            quantity_delta=quantity,
            movement_type="transfer",
            reference=reason,
            provenance="observed",
        )
    )
    db.commit()


def adjust_stock(
    db: Session, *, sku: str, warehouse_id: int, quantity_delta: int, reason: str
) -> int:
    current = _get_latest_quantity(db, sku, warehouse_id)
    if current + quantity_delta < 0:
        raise InsufficientStockError(
            f"Adjustment would drive '{sku}' at warehouse {warehouse_id} below zero "
            f"({current} + {quantity_delta})"
        )
    today = datetime.now(UTC).date()
    now = datetime.now(UTC).replace(tzinfo=None)
    new_quantity = apply_stock_delta(db, sku, warehouse_id, quantity_delta, today)
    db.add(
        StockMovement(
            sku=sku,
            warehouse_id=warehouse_id,
            movement_date=now,
            quantity_delta=quantity_delta,
            movement_type="adjustment",
            reference=reason,
            provenance="observed",
        )
    )
    db.commit()
    return new_quantity


@dataclass(frozen=True)
class LedgerRow:
    warehouse_id: int
    movement_date: datetime
    quantity_delta: int
    movement_type: str
    reference: str | None
    provenance: str


def get_ledger(db: Session, sku: str) -> list[LedgerRow]:
    stmt = (
        select(StockMovement)
        .where(StockMovement.sku == sku)
        .order_by(StockMovement.movement_date.desc())
    )
    return [
        LedgerRow(
            warehouse_id=m.warehouse_id,
            movement_date=m.movement_date,
            quantity_delta=m.quantity_delta,
            movement_type=m.movement_type,
            reference=m.reference,
            provenance=m.provenance,
        )
        for m in db.scalars(stmt)
    ]
