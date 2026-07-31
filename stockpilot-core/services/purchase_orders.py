from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.purchase_order_request import OPEN_STATUSES, PurchaseOrderRequest
from models.purchase_order_request_line import PurchaseOrderRequestLine
from models.stock_movement import StockMovement
from schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, ReceiveRequest
from services.inventory import apply_stock_delta


class InvalidTransitionError(Exception):
    """A purchase order status transition isn't allowed from its current status."""


class OverReceiptNotConfirmedError(Exception):
    """A receive line would exceed its ordered quantity without over_receipt_confirmed."""


def list_purchase_orders(
    db: Session,
    *,
    status: str | None = None,
    supplier_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[PurchaseOrderRequest]:
    stmt = select(PurchaseOrderRequest).order_by(PurchaseOrderRequest.id.desc())
    if status is not None:
        stmt = stmt.where(PurchaseOrderRequest.status == status)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrderRequest.supplier_id == supplier_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_purchase_order(db: Session, po_id: int) -> PurchaseOrderRequest | None:
    return db.get(PurchaseOrderRequest, po_id)


def get_purchase_order_lines(db: Session, po_id: int) -> list[PurchaseOrderRequestLine]:
    stmt = (
        select(PurchaseOrderRequestLine)
        .where(PurchaseOrderRequestLine.purchase_order_request_id == po_id)
        .order_by(PurchaseOrderRequestLine.id)
    )
    return list(db.scalars(stmt))


def create_purchase_order(
    db: Session, data: PurchaseOrderCreate, *, created_by_user_id: int | None
) -> PurchaseOrderRequest:
    po = PurchaseOrderRequest(
        supplier_id=data.supplier_id,
        warehouse_id=data.warehouse_id,
        status="draft",
        created_by_user_id=created_by_user_id,
    )
    db.add(po)
    db.flush()
    for line in data.lines:
        db.add(
            PurchaseOrderRequestLine(
                purchase_order_request_id=po.id,
                sku=line.sku,
                quantity_ordered=line.quantity_ordered,
                unit_cost=line.unit_cost,
            )
        )
    db.commit()
    db.refresh(po)
    return po


def update_purchase_order(
    db: Session, po: PurchaseOrderRequest, data: PurchaseOrderUpdate
) -> PurchaseOrderRequest:
    if po.status != "draft":
        raise InvalidTransitionError(
            "Only a Draft purchase order can be edited (docs/PRODUCT-SPEC.md §12)"
        )
    if data.supplier_id is not None:
        po.supplier_id = data.supplier_id
    if data.warehouse_id is not None:
        po.warehouse_id = data.warehouse_id
    if data.lines is not None:
        for existing_line in get_purchase_order_lines(db, po.id):
            db.delete(existing_line)
        db.flush()
        for new_line in data.lines:
            db.add(
                PurchaseOrderRequestLine(
                    purchase_order_request_id=po.id,
                    sku=new_line.sku,
                    quantity_ordered=new_line.quantity_ordered,
                    unit_cost=new_line.unit_cost,
                )
            )
    db.commit()
    db.refresh(po)
    return po


def submit_purchase_order(db: Session, po: PurchaseOrderRequest) -> PurchaseOrderRequest:
    if po.status != "draft":
        raise InvalidTransitionError(f"Cannot submit a purchase order in status '{po.status}'")
    po.status = "submitted"
    db.commit()
    db.refresh(po)
    return po


def approve_purchase_order(db: Session, po: PurchaseOrderRequest) -> PurchaseOrderRequest:
    if po.status != "submitted":
        raise InvalidTransitionError(f"Cannot approve a purchase order in status '{po.status}'")
    po.status = "approved"
    db.commit()
    db.refresh(po)
    return po


def cancel_purchase_order(db: Session, po: PurchaseOrderRequest) -> PurchaseOrderRequest:
    if po.status not in ("draft", "submitted"):
        raise InvalidTransitionError(
            f"Cannot cancel a purchase order in status '{po.status}' -- only Draft or Submitted "
            "purchase orders can be cancelled (docs/PRODUCT-SPEC.md §12)"
        )
    po.status = "cancelled"
    db.commit()
    db.refresh(po)
    return po


def close_purchase_order(db: Session, po: PurchaseOrderRequest) -> PurchaseOrderRequest:
    if po.status != "received":
        raise InvalidTransitionError(f"Cannot close a purchase order in status '{po.status}'")
    po.status = "closed"
    db.commit()
    db.refresh(po)
    return po


def receive_purchase_order(
    db: Session, po: PurchaseOrderRequest, data: ReceiveRequest
) -> PurchaseOrderRequest:
    if po.status not in ("approved", "partially_received"):
        raise InvalidTransitionError(
            f"Cannot receive against a purchase order in status '{po.status}'"
        )
    lines_by_id = {line.id: line for line in get_purchase_order_lines(db, po.id)}
    now = datetime.now(UTC).replace(tzinfo=None)
    for entry in data.lines:
        line = lines_by_id.get(entry.line_id)
        if line is None:
            raise ValueError(f"Line {entry.line_id} does not belong to purchase order {po.id}")
        new_total = line.quantity_received + entry.quantity
        if new_total > line.quantity_ordered and not entry.over_receipt_confirmed:
            raise OverReceiptNotConfirmedError(
                f"Receiving {entry.quantity} more of '{line.sku}' would bring total received to "
                f"{new_total}, exceeding the {line.quantity_ordered} ordered -- over-receipt "
                "requires explicit confirmation (docs/PRODUCT-SPEC.md §12)"
            )
        line.quantity_received = new_total
        apply_stock_delta(db, line.sku, po.warehouse_id, entry.quantity, now.date())
        db.add(
            StockMovement(
                sku=line.sku,
                warehouse_id=po.warehouse_id,
                movement_date=now,
                quantity_delta=entry.quantity,
                movement_type="purchase_order",
                reference=f"PO #{po.id}",
                provenance="observed",
            )
        )
    db.flush()
    all_lines = get_purchase_order_lines(db, po.id)
    po.status = (
        "received"
        if all(line.quantity_received >= line.quantity_ordered for line in all_lines)
        else "partially_received"
    )
    db.commit()
    db.refresh(po)
    return po


def supplier_has_open_purchase_orders(db: Session, supplier_id: int) -> bool:
    stmt = (
        select(PurchaseOrderRequest.id)
        .where(
            PurchaseOrderRequest.supplier_id == supplier_id,
            PurchaseOrderRequest.status.in_(OPEN_STATUSES),
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def product_has_open_purchase_order_lines(db: Session, sku: str) -> bool:
    stmt = (
        select(PurchaseOrderRequestLine.id)
        .join(
            PurchaseOrderRequest,
            PurchaseOrderRequest.id == PurchaseOrderRequestLine.purchase_order_request_id,
        )
        .where(
            PurchaseOrderRequestLine.sku == sku,
            PurchaseOrderRequest.status.in_(OPEN_STATUSES),
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None
