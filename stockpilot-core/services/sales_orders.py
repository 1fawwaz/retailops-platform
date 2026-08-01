from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.invoice import Invoice
from models.sales_order import SalesOrder
from models.sales_order_line import SalesOrderLine
from models.stock_movement import StockMovement
from schemas.sales_order import SalesOrderCreate, SalesOrderUpdate
from services.inventory import InsufficientStockError, apply_stock_delta, get_latest_quantity
from services.purchase_orders import InvalidTransitionError


def list_sales_orders(
    db: Session,
    *,
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SalesOrder]:
    stmt = select(SalesOrder).order_by(SalesOrder.id.desc())
    if status is not None:
        stmt = stmt.where(SalesOrder.status == status)
    if customer_id is not None:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_sales_order(db: Session, order_id: int) -> SalesOrder | None:
    return db.get(SalesOrder, order_id)


def get_sales_order_lines(db: Session, order_id: int) -> list[SalesOrderLine]:
    stmt = (
        select(SalesOrderLine)
        .where(SalesOrderLine.sales_order_id == order_id)
        .order_by(SalesOrderLine.id)
    )
    return list(db.scalars(stmt))


def create_sales_order(
    db: Session, data: SalesOrderCreate, *, created_by_user_id: int | None
) -> SalesOrder:
    order = SalesOrder(
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        status="draft",
        created_by_user_id=created_by_user_id,
    )
    db.add(order)
    db.flush()
    for line in data.lines:
        db.add(
            SalesOrderLine(
                sales_order_id=order.id,
                sku=line.sku,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
        )
    db.commit()
    db.refresh(order)
    return order


def update_sales_order(db: Session, order: SalesOrder, data: SalesOrderUpdate) -> SalesOrder:
    if order.status != "draft":
        raise InvalidTransitionError("Only a Draft sales order can be edited")
    if data.customer_id is not None:
        order.customer_id = data.customer_id
    if data.warehouse_id is not None:
        order.warehouse_id = data.warehouse_id
    if data.lines is not None:
        for existing_line in get_sales_order_lines(db, order.id):
            db.delete(existing_line)
        db.flush()
        for new_line in data.lines:
            db.add(
                SalesOrderLine(
                    sales_order_id=order.id,
                    sku=new_line.sku,
                    quantity=new_line.quantity,
                    unit_price=new_line.unit_price,
                )
            )
    db.commit()
    db.refresh(order)
    return order


def confirm_sales_order(db: Session, order: SalesOrder) -> SalesOrder:
    if order.status != "draft":
        raise InvalidTransitionError(f"Cannot confirm a sales order in status '{order.status}'")
    lines = get_sales_order_lines(db, order.id)
    total = sum(line.quantity * float(line.unit_price) for line in lines)
    db.add(Invoice(sales_order_id=order.id, total_amount=total, status="unpaid"))
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return order


def fulfill_sales_order(db: Session, order: SalesOrder) -> SalesOrder:
    if order.status != "confirmed":
        raise InvalidTransitionError(f"Cannot fulfill a sales order in status '{order.status}'")
    lines = get_sales_order_lines(db, order.id)
    for line in lines:
        available = get_latest_quantity(db, line.sku, order.warehouse_id)
        if available < line.quantity:
            raise InsufficientStockError(
                f"Only {available} units of '{line.sku}' at warehouse {order.warehouse_id}, "
                f"cannot fulfill {line.quantity}"
            )
    now = datetime.now(UTC).replace(tzinfo=None)
    for line in lines:
        apply_stock_delta(db, line.sku, order.warehouse_id, -line.quantity, now.date())
        db.add(
            StockMovement(
                sku=line.sku,
                warehouse_id=order.warehouse_id,
                movement_date=now,
                quantity_delta=-line.quantity,
                movement_type="sale",
                reference=f"SO #{order.id}",
                provenance="observed",
            )
        )
    order.status = "fulfilled"
    db.commit()
    db.refresh(order)
    return order


def cancel_sales_order(db: Session, order: SalesOrder) -> SalesOrder:
    if order.status not in ("draft", "confirmed"):
        raise InvalidTransitionError(
            f"Cannot cancel a sales order in status '{order.status}' -- only Draft or Confirmed "
            "sales orders can be cancelled"
        )
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


__all__ = [
    "InsufficientStockError",
    "InvalidTransitionError",
    "cancel_sales_order",
    "confirm_sales_order",
    "create_sales_order",
    "fulfill_sales_order",
    "get_sales_order",
    "get_sales_order_lines",
    "list_sales_orders",
    "update_sales_order",
]
