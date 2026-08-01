from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_write_access
from database import get_db
from models.invoice import Invoice
from models.sales_order import SalesOrder
from models.user import User
from schemas.invoice import InvoiceRead
from schemas.payment import PaymentCreate, PaymentRead
from schemas.sales_order import (
    SalesOrderCreate,
    SalesOrderLineRead,
    SalesOrderRead,
    SalesOrderUpdate,
)
from services.customers import get_customer
from services.invoices import get_invoice, get_invoice_for_order, list_invoices
from services.payments import list_payments, record_payment
from services.products import get_product
from services.sales_orders import (
    InsufficientStockError,
    InvalidTransitionError,
    cancel_sales_order,
    confirm_sales_order,
    create_sales_order,
    fulfill_sales_order,
    get_sales_order,
    get_sales_order_lines,
    list_sales_orders,
    update_sales_order,
)
from services.warehouses import get_warehouse

sales_orders_router = APIRouter(prefix="/sales-orders", tags=["sales"])
invoices_router = APIRouter(prefix="/invoices", tags=["sales"])


def to_sales_order_read_model(order: SalesOrder, db: Session) -> SalesOrderRead:
    lines = get_sales_order_lines(db, order.id)
    return SalesOrderRead(
        id=order.id,
        customer_id=order.customer_id,
        warehouse_id=order.warehouse_id,
        status=order.status,
        created_by_user_id=order.created_by_user_id,
        created_at=order.created_at,
        updated_at=order.updated_at,
        lines=[SalesOrderLineRead.model_validate(line) for line in lines],
    )


def _get_order_or_404(db: Session, order_id: int) -> SalesOrder:
    order = get_sales_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found")
    return order


def _validate_lines_reference_real_products(db: Session, skus: list[str]) -> None:
    for sku in skus:
        if get_product(db, sku) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{sku}' not found"
            )


@sales_orders_router.get("", response_model=list[SalesOrderRead])
def list_sales_orders_route(
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SalesOrderRead]:
    orders = list_sales_orders(
        db, status=status_filter, customer_id=customer_id, limit=limit, offset=offset
    )
    return [to_sales_order_read_model(o, db) for o in orders]


@sales_orders_router.get("/{order_id}", response_model=SalesOrderRead)
def get_sales_order_route(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SalesOrderRead:
    order = _get_order_or_404(db, order_id)
    return to_sales_order_read_model(order, db)


@sales_orders_router.post("", response_model=SalesOrderRead, status_code=status.HTTP_201_CREATED)
def create_sales_order_route(
    data: SalesOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_write_access),
) -> SalesOrderRead:
    if get_customer(db, data.customer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if get_warehouse(db, data.warehouse_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    _validate_lines_reference_real_products(db, [line.sku for line in data.lines])
    order = create_sales_order(db, data, created_by_user_id=user.id)
    return to_sales_order_read_model(order, db)


@sales_orders_router.put("/{order_id}", response_model=SalesOrderRead)
def update_sales_order_route(
    order_id: int,
    data: SalesOrderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SalesOrderRead:
    order = _get_order_or_404(db, order_id)
    if data.customer_id is not None and get_customer(db, data.customer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if data.warehouse_id is not None and get_warehouse(db, data.warehouse_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    if data.lines is not None:
        _validate_lines_reference_real_products(db, [line.sku for line in data.lines])
    try:
        order = update_sales_order(db, order, data)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_sales_order_read_model(order, db)


@sales_orders_router.post("/{order_id}/confirm", response_model=SalesOrderRead)
def confirm_sales_order_route(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SalesOrderRead:
    order = _get_order_or_404(db, order_id)
    try:
        order = confirm_sales_order(db, order)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_sales_order_read_model(order, db)


@sales_orders_router.post("/{order_id}/fulfill", response_model=SalesOrderRead)
def fulfill_sales_order_route(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SalesOrderRead:
    order = _get_order_or_404(db, order_id)
    try:
        order = fulfill_sales_order(db, order)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_sales_order_read_model(order, db)


@sales_orders_router.post("/{order_id}/cancel", response_model=SalesOrderRead)
def cancel_sales_order_route(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SalesOrderRead:
    order = _get_order_or_404(db, order_id)
    try:
        order = cancel_sales_order(db, order)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_sales_order_read_model(order, db)


@sales_orders_router.get("/{order_id}/invoice", response_model=InvoiceRead)
def get_invoice_for_order_route(
    order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InvoiceRead:
    _get_order_or_404(db, order_id)
    invoice = get_invoice_for_order(db, order_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invoice yet -- the order hasn't been confirmed",
        )
    return InvoiceRead.model_validate(invoice)


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@invoices_router.get("", response_model=list[InvoiceRead])
def list_invoices_route(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[InvoiceRead]:
    return [InvoiceRead.model_validate(i) for i in list_invoices(db, limit=limit, offset=offset)]


@invoices_router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice_route(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InvoiceRead:
    return InvoiceRead.model_validate(_get_invoice_or_404(db, invoice_id))


@invoices_router.get("/{invoice_id}/payments", response_model=list[PaymentRead])
def list_payments_route(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PaymentRead]:
    _get_invoice_or_404(db, invoice_id)
    return [PaymentRead.model_validate(p) for p in list_payments(db, invoice_id)]


@invoices_router.post(
    "/{invoice_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED
)
def record_payment_route(
    invoice_id: int,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> PaymentRead:
    invoice = _get_invoice_or_404(db, invoice_id)
    return PaymentRead.model_validate(record_payment(db, invoice, data))
