from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_permission
from database import get_db
from models.purchase_order_request import PurchaseOrderRequest
from models.user import User
from schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineRead,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ReceiveRequest,
)
from services.products import get_product
from services.purchase_orders import (
    InvalidTransitionError,
    OverReceiptNotConfirmedError,
    approve_purchase_order,
    cancel_purchase_order,
    close_purchase_order,
    create_purchase_order,
    get_purchase_order,
    get_purchase_order_lines,
    list_purchase_orders,
    receive_purchase_order,
    submit_purchase_order,
    update_purchase_order,
)
from services.suppliers import get_supplier
from services.warehouses import get_warehouse

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _to_read_model(po: PurchaseOrderRequest, db: Session) -> PurchaseOrderRead:
    lines = get_purchase_order_lines(db, po.id)
    return PurchaseOrderRead(
        id=po.id,
        supplier_id=po.supplier_id,
        warehouse_id=po.warehouse_id,
        status=po.status,
        created_by_user_id=po.created_by_user_id,
        created_at=po.created_at,
        updated_at=po.updated_at,
        lines=[PurchaseOrderLineRead.model_validate(line) for line in lines],
    )


def _get_po_or_404(db: Session, po_id: int) -> PurchaseOrderRequest:
    po = get_purchase_order(db, po_id)
    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
        )
    return po


def _validate_lines_reference_real_products(db: Session, skus: list[str]) -> None:
    for sku in skus:
        if get_product(db, sku) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{sku}' not found"
            )


@router.get("", response_model=list[PurchaseOrderRead])
def list_purchase_orders_route(
    status_filter: str | None = Query(default=None, alias="status"),
    supplier_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PurchaseOrderRead]:
    pos = list_purchase_orders(
        db, status=status_filter, supplier_id=supplier_id, limit=limit, offset=offset
    )
    return [_to_read_model(po, db) for po in pos]


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order_route(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    return _to_read_model(po, db)


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order_route(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("purchase_order:create")),
) -> PurchaseOrderRead:
    if get_supplier(db, data.supplier_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    if get_warehouse(db, data.warehouse_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    _validate_lines_reference_real_products(db, [line.sku for line in data.lines])
    po = create_purchase_order(db, data, created_by_user_id=user.id)
    return _to_read_model(po, db)


@router.put("/{po_id}", response_model=PurchaseOrderRead)
def update_purchase_order_route(
    po_id: int,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:update")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    if data.supplier_id is not None and get_supplier(db, data.supplier_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    if data.warehouse_id is not None and get_warehouse(db, data.warehouse_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    if data.lines is not None:
        _validate_lines_reference_real_products(db, [line.sku for line in data.lines])
    try:
        po = update_purchase_order(db, po, data)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)


@router.post("/{po_id}/submit", response_model=PurchaseOrderRead)
def submit_purchase_order_route(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:update")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    try:
        po = submit_purchase_order(db, po)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
def approve_purchase_order_route(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:update")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    try:
        po = approve_purchase_order(db, po)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
def cancel_purchase_order_route(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:update")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    try:
        po = cancel_purchase_order(db, po)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)


@router.post("/{po_id}/close", response_model=PurchaseOrderRead)
def close_purchase_order_route(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:update")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    try:
        po = close_purchase_order(db, po)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)


@router.post("/{po_id}/receive", response_model=PurchaseOrderRead)
def receive_purchase_order_route(
    po_id: int,
    data: ReceiveRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchase_order:receive")),
) -> PurchaseOrderRead:
    po = _get_po_or_404(db, po_id)
    try:
        po = receive_purchase_order(db, po, data)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OverReceiptNotConfirmedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read_model(po, db)
